#include "cloudiff/artifact_engine.hpp"
#include <archive.h>
#include <archive_entry.h>
#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <regex>
#include <string>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <unistd.h>

namespace {
std::string sha64(char c){return "sha256:"+std::string(64,c);}
std::filesystem::path mounted_out(const std::vector<std::string>& cmd){
    for(std::size_t i=0;i+1<cmd.size();++i){
        if(cmd[i]=="-v"){
            const auto pos=cmd[i+1].find(":/out");
            if(pos!=std::string::npos)return std::filesystem::path(cmd[i+1].substr(0,pos));
        }
    }
    return {};
}
bool contains(const std::vector<std::string>& cmd,const std::string& value){return std::find(cmd.begin(),cmd.end(),value)!=cmd.end();}

std::vector<unsigned char> make_archive(){
    std::vector<unsigned char> buffer(1024*1024);std::size_t used=0;struct archive* a=archive_write_new();assert(a);assert(archive_write_add_filter_gzip(a)==ARCHIVE_OK);assert(archive_write_set_format_pax_restricted(a)==ARCHIVE_OK);assert(archive_write_open_memory(a,buffer.data(),buffer.size(),&used)==ARCHIVE_OK);
    auto add=[&](const char* name,const std::string& data){struct archive_entry* e=archive_entry_new();archive_entry_set_pathname(e,name);archive_entry_set_filetype(e,AE_IFREG);archive_entry_set_perm(e,0644);archive_entry_set_size(e,static_cast<la_int64_t>(data.size()));assert(archive_write_header(a,e)==ARCHIVE_OK);assert(archive_write_data(a,data.data(),data.size())==static_cast<la_ssize_t>(data.size()));archive_entry_free(e);};
    add("repo-root/site/index.html","fixture\n");add("repo-root/web/index.html","web fixture\n");add("repo-root/docs/index.html","docs fixture\n");add("repo-root/.env","SHOULD_BE_FILTERED=true\n");assert(archive_write_close(a)==ARCHIVE_OK);assert(archive_write_free(a)==ARCHIVE_OK);buffer.resize(used);return buffer;
}
}

int main(){
    const auto root=std::filesystem::temp_directory_path()/("cloudiff-artifact-test-"+std::to_string(::getpid()));
    const auto site=root/"site";std::filesystem::create_directories(site);{std::ofstream out(site/"index.html");out<<"fixture";}
    std::atomic<int> docker_builds{0};std::atomic<bool> fail_next_build{false};std::atomic<bool> multiservice_readonly_config_seen{false};std::unordered_set<std::string> built_images;std::unordered_map<std::string,nlohmann::json> image_labels;std::atomic<bool> hold_build{false};std::mutex gate_mutex;std::condition_variable gate_cv;bool build_started=false;bool release_build=false;
    cloudiff::ArtifactCommandRunner runner=[&](const std::vector<std::string>& cmd,int){
        cloudiff::ArtifactCommandResult r{};
        if(cmd.size()>=2&&cmd[0]=="docker"&&cmd[1]=="build"){
            docker_builds.fetch_add(1);
            const auto it=std::find(cmd.begin(),cmd.end(),"-t");const std::string tag=(it!=cmd.end()&&std::next(it)!=cmd.end())?*std::next(it):"";
            if(tag.starts_with("cloudif-toolchain/")||tag.starts_with("cloudif-app/")){
                const auto dockerfile=std::filesystem::path(cmd.back())/"Dockerfile";std::ifstream in(dockerfile);std::string text((std::istreambuf_iterator<char>(in)),{});nlohmann::json labels=nlohmann::json::object();
                for(const auto& key:{"org.cloudiff.toolchain-digest","org.cloudiff.validated-toolchain-digest","org.cloudiff.config-digest","org.cloudiff.project","org.cloudiff.service","org.cloudiff.kind","org.cloudiff.application-digest","org.cloudiff.archive-sha256","org.cloudiff.environment-digest","org.cloudiff.build-environment-digest","org.cloudiff.runtime-config-sha256"}){std::regex re(std::string(key)+R"(=\"([^\"]+)\")");std::smatch m;if(std::regex_search(text,m,re))labels[key]=m[1].str();}
                if(tag.starts_with("cloudif-app/")){const auto nginx=std::filesystem::path(cmd.back())/"nginx.conf";assert(std::filesystem::is_regular_file(nginx));std::ifstream ni(nginx);std::string nc((std::istreambuf_iterator<char>(ni)),{});assert(text.find("COPY --chown=65532:65532 nginx.conf /etc/nginx/nginx.conf")!=std::string::npos);assert(nc.find("pid /tmp/nginx.pid")!=std::string::npos);assert(nc.find("client_body_temp_path /tmp/client_temp")!=std::string::npos);assert(nc.find("proxy_temp_path /tmp/proxy_temp")!=std::string::npos);assert(nc.find("/var/lib/nginx/tmp")==std::string::npos);multiservice_readonly_config_seen=true;}
                image_labels[tag]=labels;built_images.insert(tag);return r;
            }
            if(fail_next_build.exchange(false)){r.exit_code=1;r.stderr_text="synthetic build failure";return r;}
            if(hold_build.load()){std::unique_lock lock(gate_mutex);build_started=true;gate_cv.notify_all();gate_cv.wait(lock,[&]{return release_build;});}
            return r;
        }
        if(cmd.size()>=3&&cmd[0]=="docker"&&cmd[1]=="image"&&cmd[2]=="inspect"){
            if(contains(cmd,"--format")){r.stdout_text=sha64('a')+"\n";return r;}
            const std::string image=cmd.size()>3?cmd[3]:"";
            if(image.starts_with("cgr.dev/chainguard/nginx@sha256:")){r.stdout_text=nlohmann::json::array({{{"Id",image.substr(image.find("sha256:"))},{"RepoDigests",nlohmann::json::array({image})},{"Config",{{"User","65532"},{"Labels",nlohmann::json::object()}}},{"Created","fixture"},{"Size",1000}}}).dump();return r;}
            if(image.starts_with("cloudif-toolchain/")||image.starts_with("cloudif-app/")){if(!built_images.contains(image)){r.exit_code=1;return r;}const auto id=image.starts_with("cloudif-toolchain/")?sha64('e'):sha64('f');r.stdout_text=nlohmann::json::array({{{"Id",id},{"RepoDigests",nlohmann::json::array()},{"Config",{{"User","65532"},{"Labels",image_labels[image]}}},{"Created","fixture"},{"Size",2000}}}).dump();return r;}
            r.exit_code=1;return r;
        }
        if(cmd.size()>=2&&cmd[0]=="docker"&&cmd[1]=="inspect"){r.stdout_text="true\n";return r;}
        if(cmd.size()>=2&&cmd[0]=="docker"&&cmd[1]=="run"){
            const auto out=mounted_out(cmd);
            if(!out.empty()&&(contains(cmd,"cyclonedx-json=/out/sbom.cdx.json")||contains(cmd,"cyclonedx-json=/out/toolchain-sbom.cdx.json")||contains(cmd,"cyclonedx-json=/out/application-sbom.cdx.json"))){
                std::filesystem::create_directories(out);const auto file=contains(cmd,"cyclonedx-json=/out/application-sbom.cdx.json")?out/"application-sbom.cdx.json":(contains(cmd,"cyclonedx-json=/out/toolchain-sbom.cdx.json")?out/"toolchain-sbom.cdx.json":out/"sbom.cdx.json");std::ofstream f(file);f<<R"({"bomFormat":"CycloneDX","specVersion":"1.6","components":[{"name":"fixture"}]})";
            } else if(!out.empty()&&(contains(cmd,"/out/trivy.json")||contains(cmd,"/out/toolchain-trivy.json")||contains(cmd,"/out/application-trivy.json"))){
                std::filesystem::create_directories(out);const auto file=contains(cmd,"/out/application-trivy.json")?out/"application-trivy.json":(contains(cmd,"/out/toolchain-trivy.json")?out/"toolchain-trivy.json":out/"trivy.json");std::ofstream f(file);f<<R"({"Results":[{"Vulnerabilities":[{"Severity":"LOW"}]}]})";
            }
            if(contains(cmd,"-d"))r.stdout_text="container-id\n";
            return r;
        }
        if(cmd.size()>=2&&cmd[0]=="docker"&&cmd[1]=="rm")return r;
        r.exit_code=127;r.stderr_text="unexpected command";return r;
    };

    cloudiff::ArtifactEngineOptions opts;
    opts.token="unit-secret";opts.classic_token="classic-secret";opts.artifact_root=root/"artifacts";opts.scanner_cache=root/"cache";opts.syft_image="anchore/syft@"+sha64('b');opts.trivy_image="aquasec/trivy@"+sha64('c');
    // Remove duplicated "sha256:" from helper composition.
    opts.syft_image="anchore/syft@sha256:"+std::string(64,'b');opts.trivy_image="aquasec/trivy@sha256:"+std::string(64,'c');
    opts.static_sites.emplace("fixture-project",site);opts.max_concurrent_builds=1;opts.command_runner=runner;

    const auto catalog=root/"toolchain-catalog-v2.json";
    {std::ofstream out(catalog);out<<R"({"version":2,"architectures":["amd64"],"networkPolicies":{"none":{"supported":true}},"baseImages":{"static":{"versions":{"default":{"status":"approved","image":"cgr.dev/chainguard/nginx@sha256:e4ff957080737c90a9ecfeaa40e3d19ea9d687e9cacda2f2a031c75ffcdd72b7","imageId":"sha256:e4ff957080737c90a9ecfeaa40e3d19ea9d687e9cacda2f2a031c75ffcdd72b7","architectures":["amd64"],"user":"65532","scannerCounts":{},"scannerBlocked":false,"scanDate":"2026-08-20"}}}},"blockedRuntimes":{"node":{"24":{"status":"blocked","reason":"security_scan_failed","scannerEvidence":[{}]}}},"systemPackages":{},"tools":{},"provisionPolicy":{"enabled":false,"reason":"no-approved-shell-build-runtime"},"scannerPolicy":{"block":["HIGH","CRITICAL"],"offlineCache":true}})";}
    const auto private_key=root/"signing.pem",public_key=root/"signing.pub.pem";
    auto kr=cloudiff::run_artifact_command({"openssl","genpkey","-algorithm","ED25519","-out",private_key.string()},20);assert(kr.exit_code==0);
    kr=cloudiff::run_artifact_command({"openssl","pkey","-in",private_key.string(),"-pubout","-out",public_key.string()},20);assert(kr.exit_code==0);
    const auto archive_bytes=make_archive();
    opts.toolchain_catalog=catalog;opts.signing_key=private_key;opts.signing_public_key=public_key;opts.forja_token="unused-injected";
    opts.archive_fetcher=[archive_bytes](const std::string& slug,const std::string& ref,const std::string& expected){assert(slug=="fixture-project"||slug=="multi-project"||slug=="archive-only");assert(ref=="main");assert(expected==std::string(64,'a'));return cloudiff::ArtifactArchive{archive_bytes,expected};};
    cloudiff::ArtifactEngine engine(opts);

    auto r=engine.handle("GET","/health","","");assert(r.status==200);assert(r.body.at("service")=="artifact-executor");assert(r.body.at("secrets_exposed")==false);
    r=engine.handle("POST","/v1/artifacts","",R"({"project_slug":"fixture-project","build_id":"11111111-1111-1111-1111-111111111111"})");assert(r.status==401);assert(r.body.at("error")=="unauthorized");
    r=engine.handle("POST","/v1/toolchain/build","Bearer unit-secret","{}");assert(r.status==400);assert(r.body.at("error")=="required_field_missing");
    r=engine.handle("POST","/v1/multiservice/build","Bearer unit-secret","{}");assert(r.status==400);assert(r.body.at("error")=="required_field_missing");
    r=engine.handle("POST","/v1/build","Bearer unit-secret",R"({"profile":"multiservice-v1"})");assert(r.status==422);assert(r.body.at("error").at("code")=="invalid_profile");
    r=engine.handle("POST","/v1/build","Bearer unit-secret",nlohmann::json{{"profile","classic-static-v2"},{"project_slug","archive-only"},{"ref","main"},{"build_id","15151515-1515-1515-1515-151515151515"},{"archive_sha256",std::string(64,'a')}}.dump());assert(r.status==403&&r.body.at("error")=="classic_token_required");
    r=engine.handle("POST","/v1/build","Bearer classic-secret",nlohmann::json{{"profile","static-v1"},{"project_slug","fixture-project"},{"build_id","15151515-1515-1515-1515-151515151516"}}.dump());assert(r.status==403&&r.body.at("error")=="artifact_token_scope");
    r=engine.handle("GET","/v1/artifacts/11111111-1111-1111-1111-111111111111","Bearer classic-secret","");assert(r.status==403&&r.body.at("error")=="artifact_token_scope");

    const std::string id1="11111111-1111-1111-1111-111111111111";
    r=engine.handle("POST","/v1/artifacts","Bearer unit-secret",nlohmann::json{{"project_slug","fixture-project"},{"build_id",id1}}.dump());
    assert(r.status==200);assert(r.body.at("ok")==true);assert(r.body.at("idempotent")==false);assert(r.body.at("production_ready")==true);assert(r.body.at("artifact_image_id")==sha64('a'));
    assert(r.body.at("sbom_ready")==true);assert(r.body.at("scanner_ready")==true);assert(r.body.at("scanner_blocked")==false);assert(r.body.at("runtime_proof").at("user")=="65532:65532");
    assert(r.body.at("runtime_proof").at("read_only")==true);assert(r.body.at("runtime_proof").at("cap_drop")==nlohmann::json::array({"ALL"}));assert(r.body.at("runtime_proof").at("published_ports").empty());
    assert(docker_builds.load()==1);
    r=engine.handle("POST","/v1/artifacts","Bearer unit-secret",nlohmann::json{{"project_slug","fixture-project"},{"build_id",id1}}.dump());assert(r.status==200);assert(r.body.at("idempotent")==true);assert(docker_builds.load()==1);
    r=engine.handle("GET","/v1/artifacts/"+id1,"Bearer unit-secret","");assert(r.status==200);assert(r.body.at("status")=="succeeded");assert(r.body.at("artifact").at("artifact_image_id")==sha64('a'));
    const std::string classic_id="16161616-1616-1616-1616-161616161616";
    r=engine.handle("POST","/v1/build","Bearer classic-secret",nlohmann::json{{"profile","classic-static-v2"},{"project_slug","archive-only"},{"ref","main"},{"build_id",classic_id},{"archive_sha256",std::string(64,'a')}}.dump());assert(r.status==200);assert(r.body.at("ok")==true);assert(r.body.at("source_mode")=="forja-archive");assert(r.body.at("archive_sha256")==std::string(64,'a'));assert(r.body.at("ref")=="main");assert(!opts.static_sites.contains("archive-only"));
    r=engine.handle("POST","/v1/build","Bearer classic-secret",nlohmann::json{{"profile","classic-static-v2"},{"project_slug","archive-only"},{"ref","main"},{"build_id",classic_id},{"archive_sha256",std::string(64,'a')}}.dump());assert(r.status==200);assert(r.body.at("idempotent")==true);
    r=engine.handle("POST","/v1/build","Bearer classic-secret",nlohmann::json{{"profile","classic-static-v2"},{"project_slug","archive-only"},{"ref","../bad"},{"build_id","17171717-1717-1717-1717-171717171717"},{"archive_sha256",std::string(64,'a')}}.dump());assert(r.status==400);assert(r.body.at("error")=="invalid_archive_source");

    // Failure does not persist success and the same build_id can recover on re-execution.
    const std::string id2="22222222-2222-2222-2222-222222222222";fail_next_build=true;
    r=engine.handle("POST","/v1/artifacts","Bearer unit-secret",nlohmann::json{{"project_slug","fixture-project"},{"build_id",id2}}.dump());assert(r.status==500);assert(r.body.at("error")=="artifact_pipeline_failed");
    r=engine.handle("GET","/v1/artifacts/"+id2,"Bearer unit-secret","");assert(r.status==404);
    r=engine.handle("POST","/v1/artifacts","Bearer unit-secret",nlohmann::json{{"project_slug","fixture-project"},{"build_id",id2}}.dump());assert(r.status==200);assert(r.body.at("idempotent")==false);

    // Capacity gate: one slow build occupies the only slot; another is rejected with 429.
    const std::string id3="33333333-3333-3333-3333-333333333333",id4="44444444-4444-4444-4444-444444444444";hold_build=true;build_started=false;release_build=false;cloudiff::ArtifactEngineResponse slow;
    std::thread t([&]{slow=engine.handle("POST","/v1/artifacts","Bearer unit-secret",nlohmann::json{{"project_slug","fixture-project"},{"build_id",id3}}.dump());});
    {std::unique_lock lock(gate_mutex);gate_cv.wait_for(lock,std::chrono::seconds(2),[&]{return build_started;});assert(build_started);}
    r=engine.handle("POST","/v1/artifacts","Bearer unit-secret",nlohmann::json{{"project_slug","fixture-project"},{"build_id",id4}}.dump());assert(r.status==429);assert(r.body.at("error")=="artifact_busy");
    {std::scoped_lock lock(gate_mutex);release_build=true;}gate_cv.notify_all();t.join();assert(slow.status==200);hold_build=false;


    // v13 toolchain validation/build: side-effect-free validation, static build, Ed25519 and security blocker for Node 24.
    const auto tc_request=nlohmann::json{{"job_id","toolchain_aaaaaaaaaaaaaaaaaaaaaaaa"},{"project_slug","fixture-project"},{"ref","main"},{"archive_sha256",std::string(64,'a')},{"config_revision",1},{"config_digest",std::string(64,'b')},{"toolchain_digest",std::string(64,'c')},{"plan_digest",std::string(64,'d')},{"services",nlohmann::json::array({{{"name","web"},{"path","."},{"runtime","static"},{"version",nullptr},{"hookSteps",nlohmann::json::array()}}})},{"toolchain",nlohmann::json::object()},{"trace_id","unit-v13"}};
    const int builds_before_validate=docker_builds.load();r=engine.handle("POST","/v1/toolchain/validate","Bearer unit-secret",tc_request.dump());assert(r.status==200);assert(r.body.at("valid")==true);assert(r.body.at("sideEffectFree")==true);assert(r.body.at("imagesCreated")==0);assert(r.body.at("containersChanged")==false);assert(r.body.at("services").size()==1);assert(docker_builds.load()==builds_before_validate);
    auto node_request=tc_request;node_request["services"][0]["runtime"]="node";node_request["services"][0]["version"]="24";r=engine.handle("POST","/v1/toolchain/validate","Bearer unit-secret",node_request.dump());assert(r.status==200);assert(r.body.at("valid")==false);assert(!r.body.at("blockers").empty());
    r=engine.handle("POST","/v1/toolchain/build","Bearer unit-secret",tc_request.dump());assert(r.status==200);assert(r.body.at("ok")==true);assert(r.body.at("status")=="ready");assert(r.body.at("activationRequired")==true);assert(r.body.at("containersChanged")==false);assert(r.body.at("imageCount")==1);assert(r.body.at("imagesCreated")==1);assert(r.body.at("toolchains")[0].at("signatureVerified")==true);assert(r.body.at("toolchains")[0].at("signatureAlgorithm")=="Ed25519");assert(r.body.at("toolchains")[0].at("scannerBlocked")==false);assert(r.body.at("toolchains")[0].at("secretsIncluded")==false);
    const auto tc_image=r.body.at("toolchains")[0].at("image").at("imageId");r=engine.handle("POST","/v1/toolchain/build","Bearer unit-secret",tc_request.dump());assert(r.status==200);assert(r.body.at("imagesCreated")==0);assert(r.body.at("toolchains")[0].at("reused")==true);assert(r.body.at("toolchains")[0].at("image").at("imageId")==tc_image);
    auto active_request=tc_request;active_request["activeToolchainImages"]={{"web",{{"imageRef","x"}}}};r=engine.handle("POST","/v1/toolchain/build","Bearer unit-secret",active_request.dump());assert(r.status==409);assert(r.body.at("error").at("code")=="active_toolchain_reuse_deferred");


    // v14 multiservice: two static services, safe environment contract, signatures, idempotency and plan conflict.
    const auto env_digest=std::string(64,'6');const auto build_env_digest=std::string(64,'7');const auto runtime_env_digest=std::string(64,'8');
    nlohmann::json ms_request={{"job_id","build_ffffffffffffffffffffffff"},{"project_slug","multi-project"},{"ref","main"},{"archive_sha256",std::string(64,'a')},{"config_revision",2},{"config_digest",std::string(64,'b')},{"toolchain_digest",std::string(64,'c')},{"plan_digest",std::string(64,'d')},{"services",nlohmann::json::array({{{"name","web"},{"path","web"},{"runtime","static"},{"version",nullptr},{"publish","."},{"port",8081},{"healthcheck","/healthz"},{"hookSteps",nlohmann::json::array()},{"excludePaths",nlohmann::json::array({"docs"})}},{{"name","docs"},{"path","docs"},{"runtime","static"},{"version",nullptr},{"publish","."},{"port",8082},{"hookSteps",nlohmann::json::array()},{"excludePaths",nlohmann::json::array({"web"})}}})},{"toolchain",nlohmann::json::object()},{"trace_id","unit-v14"},{"environment","development"},{"effectiveEnvironment",{{"publicBuildEnvironment",{{"web",{{"PUBLIC_FLAG","public-value"}}},{"docs",nlohmann::json::object()}}},{"publicRuntimeEnvironment",{{"web",{{"MODE","read"}}},{"docs",nlohmann::json::object()}}},{"secretBuildReferences",nlohmann::json::object()},{"secretRuntimeReferences",{{"web",{{"API_KEY","vault://project/api-key"}}},{"docs",nlohmann::json::object()}}},{"buildEnvironmentDigest",build_env_digest},{"runtimeEnvironmentDigest",runtime_env_digest},{"environmentDigest",env_digest},{"secretValuesIncluded",false}}}};
    const int ms_before=docker_builds.load();r=engine.handle("POST","/v1/multiservice/build","Bearer unit-secret",ms_request.dump());assert(r.status==200);assert(r.body.at("ok")==true);assert(r.body.at("serviceCount")==2);assert(r.body.at("toolchains").size()==2);assert(r.body.at("applications").size()==2);assert(r.body.at("sourceRemoved")==true);assert(r.body.at("signaturesVerified")==true);assert(r.body.at("containersChanged")==false);assert(r.body.at("secretsIncluded")==false);assert(r.body.at("idempotent")==false);assert(r.body.at("imagesCreated")==4);assert(docker_builds.load()==ms_before+4);
    assert(multiservice_readonly_config_seen.load());for(const auto& app:r.body.at("applications")){assert(app.at("runtime")=="static");assert(app.at("scannerBlocked")==false);assert(app.at("signatureVerified")==true);assert(app.at("image").at("user")=="65532");assert(app.at("containerPort")==8080);assert(app.at("runtimeReadOnlyCompatible")==true);assert(app.at("runtimeWritablePaths")==nlohmann::json::array({"/tmp"}));assert(app.at("nginxConfigPath")=="/etc/nginx/nginx.conf");assert(app.at("runtimeConfigSha256").get<std::string>().size()==64);assert(app.at("image").at("labels").at("org.cloudiff.runtime-config-sha256")==app.at("runtimeConfigSha256"));}
    const auto serialized=r.body.dump();assert(serialized.find("vault://project/api-key")==std::string::npos);assert(serialized.find("public-value")==std::string::npos);assert(serialized.find("API_KEY")!=std::string::npos);assert(serialized.find("PUBLIC_FLAG")!=std::string::npos);
    const int ms_after=docker_builds.load();r=engine.handle("POST","/v1/multiservice/build","Bearer unit-secret",ms_request.dump());assert(r.status==200);assert(r.body.at("idempotent")==true);assert(docker_builds.load()==ms_after);
    auto conflict=ms_request;conflict["plan_digest"]=std::string(64,'9');r=engine.handle("POST","/v1/multiservice/build","Bearer unit-secret",conflict.dump());assert(r.status==409);assert(r.body.at("error")=="job_id_conflict");
    auto ms_node=ms_request;ms_node["job_id"]="build_eeeeeeeeeeeeeeeeeeeeeeee";ms_node["plan_digest"]=std::string(64,'5');ms_node["services"][0]["runtime"]="node";ms_node["services"][0]["version"]="24";r=engine.handle("POST","/v1/multiservice/build","Bearer unit-secret",ms_node.dump());assert(r.status==409);assert(r.body.at("error").at("code")=="runtime_policy_blocked");
    auto ms_secret=ms_request;ms_secret["job_id"]="build_dddddddddddddddddddddddd";ms_secret["plan_digest"]=std::string(64,'4');ms_secret["effectiveEnvironment"]["secretBuildReferences"]={{"web",{{"BUILD_TOKEN","vault://project/build-token"}}}};r=engine.handle("POST","/v1/multiservice/build","Bearer unit-secret",ms_secret.dump());assert(r.status==409);assert(r.body.at("error")=="build_secret_injection_unavailable");
    const auto ms_result=opts.artifact_root/"multiservice"/"build_ffffffffffffffffffffffff"/"result.json";assert(std::filesystem::is_regular_file(ms_result));assert(!std::filesystem::exists(opts.artifact_root/"multiservice"/"build_ffffffffffffffffffffffff"/"source-work"));const auto ms_perms=std::filesystem::status(ms_result).permissions();assert((ms_perms&std::filesystem::perms::group_read)==std::filesystem::perms::none);assert((ms_perms&std::filesystem::perms::others_read)==std::filesystem::perms::none);

    // Unsafe source entry is rejected before Docker is invoked.
    const auto unsafe=root/"unsafe";std::filesystem::create_directories(unsafe);std::filesystem::create_symlink("/etc/passwd",unsafe/"link");opts.static_sites["unsafe-project"]=unsafe;cloudiff::ArtifactEngine unsafe_engine(opts);const int before=docker_builds.load();
    r=unsafe_engine.handle("POST","/v1/artifacts","Bearer unit-secret",R"({"project_slug":"unsafe-project","build_id":"55555555-5555-5555-5555-555555555555"})");assert(r.status==400);assert(r.body.at("error")=="unsafe_source_entry");assert(docker_builds.load()==before);

    const auto result=opts.artifact_root/"results"/(id1+".json");assert(std::filesystem::is_regular_file(result));const auto perms=std::filesystem::status(result).permissions();assert((perms&std::filesystem::perms::group_read)==std::filesystem::perms::none);assert((perms&std::filesystem::perms::others_read)==std::filesystem::perms::none);
    std::filesystem::remove_all(root);return 0;
}
