#include "cloudiff/runtime_executor.hpp"
#include <algorithm>
#include <cassert>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
std::string image_json(const std::string& id,const std::string& user="65532"){return nlohmann::json::array({{{"Id",id},{"Config",{{"User",user}}}}}).dump();}
std::string container_json(const std::string& network,bool exposed_unpublished=false,bool published=false){nlohmann::json ports=nlohmann::json::object(),bindings=nlohmann::json::object();if(exposed_unpublished)ports["8080/tcp"]=nullptr;if(published){ports["8080/tcp"]=nlohmann::json::array({{{"HostIp","0.0.0.0"},{"HostPort","18080"}}});bindings["8080/tcp"]=ports["8080/tcp"];}return nlohmann::json::array({{{"Config",{{"User","65532:65532"}}},{"State",{{"Running",true}}},{"HostConfig",{{"ReadonlyRootfs",true},{"NetworkMode",network},{"Memory",134217728},{"PidsLimit",128},{"CapDrop",nlohmann::json::array({"ALL"})},{"SecurityOpt",nlohmann::json::array({"no-new-privileges"})},{"Tmpfs",{{"/tmp","rw,noexec,nosuid,size=16m,mode=1777"}}},{"PortBindings",bindings}}},{"NetworkSettings",{{"Ports",ports}}}}}).dump();}
bool contains(const std::vector<std::string>& v,const std::string& value){return std::find(v.begin(),v.end(),value)!=v.end();}
}
int main(){
    using cloudiff::RuntimeProfile;
    const auto preview=cloudiff::runtime_profile_policy(RuntimeProfile::PREVIEW);assert(preview.at("memory_mib")==128&&preview.at("network")=="cloudif-publications"&&preview.at("traffic_scope")=="preview-proxy");
    const auto test=cloudiff::runtime_profile_policy(RuntimeProfile::TEST);assert(test.at("network")=="none"&&test.at("activation_allowed")==false&&test.at("remove_after_execution")==true);
    const auto homolog=cloudiff::runtime_profile_policy(RuntimeProfile::HOMOLOGATION);assert(homolog.at("network_alias")=="cloudif-prod-homologation"&&homolog.at("rollback_required")==true);
    const auto canary=cloudiff::runtime_profile_policy(RuntimeProfile::CANARY);assert(canary.at("network")=="cloudif-production-canary"&&canary.at("network_alias")=="cloudif-prod-canary");
    const auto prod=cloudiff::runtime_profile_policy(RuntimeProfile::PRODUCTION);assert(prod.at("memory_mib")==192&&prod.at("external_health_match")==true&&prod.at("traffic_scope")=="public-production");
    const auto sealed=cloudiff::runtime_profile_policy(RuntimeProfile::SEALED);assert(sealed.at("sealed")==true&&sealed.at("mutation_allowed")==false&&sealed.at("production_effects_enabled")==false&&sealed.at("restore_validation_required")==true);
    for(const char* name:{"PREVIEW","TEST","HOMOLOGATION","CANARY","PRODUCTION","SEALED"}){auto p=cloudiff::runtime_profile_from_string(name);assert(p);assert(cloudiff::runtime_profile_name(*p)==name);}assert(!cloudiff::runtime_profile_from_string("preview"));

    cloudiff::RuntimeExecutor shadow({"127.0.0.1",18232,"unit-secret",false,{}});
    auto r=shadow.handle("GET","/health","","");assert(r.status==200&&r.body.at("mode")=="shadow-plan-only"&&r.body.at("effects_enabled")==false);
    r=shadow.handle("POST","/v1/plan","Bearer wrong",R"({"profile":"TEST"})");assert(r.status==401);
    r=shadow.handle("POST","/v1/plan","Bearer unit-secret",R"({"profile":"PREVIEW"})");assert(r.status==200&&r.body.at("side_effect_free")==true&&r.body.at("plan").at("ttl_seconds")==3600);
    r=shadow.handle("POST","/v1/plan","Bearer unit-secret",R"({"profile":"PREVIEW","ttl_seconds":299})");assert(r.status==422);
    r=shadow.handle("POST","/v1/execute","Bearer unit-secret",R"({"profile":"TEST"})");assert(r.status==409&&r.body.at("error")=="effects_not_enabled_v18");

    const std::string image="sha256:"+std::string(64,'a'),source=std::string(64,'b');
    std::vector<std::vector<std::string>> commands;std::string active_name;bool exists=false;
    cloudiff::RuntimeCommandRunner runner=[&](const std::vector<std::string>& cmd,int)->cloudiff::RuntimeCommandResult{
        commands.push_back(cmd);
        if(cmd.size()>=4&&cmd[0]=="docker"&&cmd[1]=="image"&&cmd[2]=="inspect")return {0,image_json(image),{}};
        if(cmd.size()>=3&&cmd[0]=="docker"&&cmd[1]=="rm"&&cmd[2]=="-f"){exists=false;return {0,"",{}};}
        if(cmd.size()>=2&&cmd[0]=="docker"&&cmd[1]=="run"){auto it=std::find(cmd.begin(),cmd.end(),"--name");assert(it!=cmd.end()&&std::next(it)!=cmd.end());active_name=*std::next(it);exists=true;return {0,"container-id\n",{}};}
        if(cmd.size()>=3&&cmd[0]=="docker"&&cmd[1]=="inspect"){if(!exists)return {1,"","not found"};auto it=std::find(commands.back().begin(),commands.back().end(),"unused");(void)it;std::string network="none";for(auto rit=commands.rbegin();rit!=commands.rend();++rit){auto n=std::find(rit->begin(),rit->end(),"--network");if(n!=rit->end()&&std::next(n)!=rit->end()){network=*std::next(n);break;}}return {0,container_json(network,network=="cloudif-publications",false),{}};}
        return {127,"","unexpected"};
    };
    cloudiff::RuntimeExecutor live({"127.0.0.1",18233,"unit-secret",true,runner});
    r=live.handle("GET","/health","","");assert(r.status==200&&r.body.at("mode")=="canary-test-preview"&&r.body.at("live_profiles")==nlohmann::json::array({"TEST","PREVIEW"}));
    const auto test_req=nlohmann::json{{"profile","TEST"},{"execution_id","rt_0123456789abcdefabcd"},{"artifact_image_id",image},{"immutable_source_digest",source}}.dump();
    r=live.handle("POST","/v1/execute","Bearer unit-secret",test_req);assert(r.status==200&&r.body.at("container_removed")==true&&r.body.at("network")=="none"&&r.body.at("public_traffic_activated")==false&&!exists);
    bool saw_test_run=false;for(const auto& cmd:commands)if(cmd.size()>2&&cmd[0]=="docker"&&cmd[1]=="run"){saw_test_run=true;assert(contains(cmd,"none"));assert(contains(cmd,"--read-only"));assert(contains(cmd,"128m"));assert(contains(cmd,"128"));assert(contains(cmd,"ALL"));assert(!contains(cmd,"-p")&&!contains(cmd,"--publish"));}assert(saw_test_run);

    commands.clear();const auto preview_req=nlohmann::json{{"profile","PREVIEW"},{"execution_id","rt_abcdef0123456789abcd"},{"artifact_image_id",image},{"immutable_source_digest",source},{"ttl_seconds",600}}.dump();
    r=live.handle("POST","/v1/execute","Bearer unit-secret",preview_req);assert(r.status==200&&r.body.at("network")=="cloudif-publications"&&r.body.at("ttl_seconds")==600&&r.body.at("container_removed")==true&&!exists);bool saw_preview=false;for(const auto& cmd:commands)if(cmd.size()>2&&cmd[0]=="docker"&&cmd[1]=="run"){saw_preview=true;assert(contains(cmd,"cloudif-publications"));assert(!contains(cmd,"-p")&&!contains(cmd,"--publish"));}assert(saw_preview);
    r=live.handle("POST","/v1/execute","Bearer unit-secret",nlohmann::json{{"profile","PRODUCTION"},{"execution_id","rt_11111111111111111111"},{"artifact_image_id",image},{"immutable_source_digest",source}}.dump());assert(r.status==409&&r.body.at("error")=="profile_effects_not_enabled_v18");
    r=live.handle("POST","/v1/execute","Bearer unit-secret",nlohmann::json{{"profile","TEST"},{"execution_id","bad"},{"artifact_image_id",image},{"immutable_source_digest",source}}.dump());assert(r.status==422);

    bool published_exists=false;cloudiff::RuntimeCommandRunner published_runner=[&](const std::vector<std::string>& cmd,int)->cloudiff::RuntimeCommandResult{if(cmd.size()>=4&&cmd[1]=="image"&&cmd[2]=="inspect")return {0,image_json(image),{}};if(cmd.size()>=3&&cmd[1]=="rm"){published_exists=false;return {0,"",{}};}if(cmd.size()>=2&&cmd[1]=="run"){published_exists=true;return {0,"container-id",{}};}if(cmd.size()>=2&&cmd[1]=="inspect"){if(!published_exists)return {1,"","not found"};return {0,container_json("cloudif-publications",true,true),{}};}return {1,"",{}};};cloudiff::RuntimeExecutor published_guard({"127.0.0.1",18233,"unit-secret",true,published_runner});r=published_guard.handle("POST","/v1/execute","Bearer unit-secret",preview_req);assert(r.status==500&&r.body.at("detail")=="published_ports_not_allowed"&&!published_exists);

    bool cleanup_after_failure=false;cloudiff::RuntimeCommandRunner failing=[&](const std::vector<std::string>& cmd,int)->cloudiff::RuntimeCommandResult{
        if(cmd.size()>=4&&cmd[1]=="image"&&cmd[2]=="inspect")return {0,image_json(image),{}};
        if(cmd.size()>=3&&cmd[1]=="rm"&&cmd[2]=="-f"){cleanup_after_failure=true;return {0,"",{}};}
        if(cmd.size()>=2&&cmd[1]=="run")return {0,"container-id",{}};
        if(cmd.size()>=2&&cmd[1]=="inspect")return {0,"not-json",{}};
        return {1,"",{}};
    };
    cloudiff::RuntimeExecutor live_fail({"127.0.0.1",18233,"unit-secret",true,failing});cleanup_after_failure=false;r=live_fail.handle("POST","/v1/execute","Bearer unit-secret",test_req);assert(r.status==500&&r.body.at("error")=="runtime_canary_failed"&&r.body.at("container_removed")==true&&cleanup_after_failure);

    cloudiff::RuntimeCommandRunner root_image=[&](const std::vector<std::string>& cmd,int)->cloudiff::RuntimeCommandResult{if(cmd.size()>=4&&cmd[1]=="image")return {0,image_json(image,"root"),{}};return {0,"",{}};};cloudiff::RuntimeExecutor root_guard({"127.0.0.1",18233,"unit-secret",true,root_image});r=root_guard.handle("POST","/v1/execute","Bearer unit-secret",test_req);assert(r.status==409&&r.body.at("error")=="artifact_image_not_rootless");
    return 0;
}
