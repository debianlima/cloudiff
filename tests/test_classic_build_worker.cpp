#include "cloudiff/classic_build_worker.hpp"
#include <cassert>
#include <stdexcept>
#include <string>

namespace {
cloudiff::DurableJob job(){
    cloudiff::DurableJob j;j.job_id="16161616-1616-1616-1616-161616161616";j.kind="cloudiff.v2.build.classic";j.partition_key="fixture-project";j.idempotency_key="unit";j.attempt=1;j.max_attempts=3;
    j.payload={{"project_slug","fixture-project"},{"ref","main"},{"framework","static"},{"build_plan_digest",std::string(64,'e')}};return j;
}
nlohmann::json workspace_valid(){return {{"ok",true},{"result",{{"valid",true},{"archive_sha256",std::string(64,'a')},{"warnings",nlohmann::json::array({{{"message","ação"}}})}}},{"container_removed",true},{"temp_removed",true}};}
nlohmann::json artifact_valid(){return {{"ok",true},{"build_id","16161616-1616-1616-1616-161616161616"},{"project_slug","fixture-project"},{"artifact_image_id","sha256:"+std::string(64,'b')},{"artifact_tag","cloudiff-v2-shadow-static/fixture-project:build-16161616-161"},{"base_image","cgr.dev/chainguard/nginx@sha256:"+std::string(64,'f')},{"sbom_ready",true},{"sbom_format","CycloneDX"},{"sbom_spec_version","1.6"},{"sbom_components",1},{"sbom_sha256",std::string(64,'c')},{"scanner_ready",true},{"scanner_policy","block HIGH/CRITICAL"},{"scanner_counts",{{"LOW",1}}},{"scanner_sha256",std::string(64,'d')},{"scanner_blocked",false},{"runtime_proof",{{"user","65532:65532"},{"read_only",true},{"cap_drop",nlohmann::json::array({"ALL"})},{"published_ports",nlohmann::json::array()},{"listen_port",8080}}},{"production_ready",true},{"idempotent",false}};}
cloudiff::ClassicBuildWorkerOptions base_options(){cloudiff::ClassicBuildWorkerOptions o;o.workspace_token="workspace-secret";o.artifact_token="artifact-secret";o.attestation_key="unit-attestation-key";return o;}
}
int main(){
    {cloudiff::ClassicBuildWorkerOptions defaults;assert(defaults.artifact_host=="10.62.91.3"&&defaults.artifact_port==80&&defaults.artifact_host_header=="cloudif-artifact-executor-v2.internal");}
    int workspace_calls=0,artifact_calls=0;auto o=base_options();
    o.workspace_validator=[&](const std::string& slug,const std::string& ref,const std::string& trace){++workspace_calls;assert(slug=="fixture-project"&&ref=="main"&&trace=="16161616-1616-1616-1616-161616161616");return workspace_valid();};
    o.artifact_builder=[&](const std::string& slug,const std::string& ref,const std::string& bid,const std::string& sha){++artifact_calls;assert(slug=="fixture-project"&&ref=="main"&&bid=="16161616-1616-1616-1616-161616161616"&&sha==std::string(64,'a'));return artifact_valid();};
    cloudiff::ClassicBuildWorker worker(o);auto r=worker.execute(job());assert(r.outcome==cloudiff::ClassicBuildOutcome::succeeded);assert(r.error.empty());assert(workspace_calls==1&&artifact_calls==1);assert(r.result.at("valid")==true);assert(r.result.at("production_ready")==true);assert(r.result.at("immutable_source_digest")=="58d81779957f8f4f2209f65cb08d68fd20c55ace7c5a9a42ecf1cac8de266490");assert(r.result.at("attestation_verified")==true);assert(r.result.at("attestation").at("algorithm")=="HMAC-SHA256");assert(r.result.at("attestation").at("signature")=="7c69719235a76e2f84e6b6130b9c27ca8a6c417662a353f632e8a39b474abf66");assert(r.result.at("attestation").at("signature").get<std::string>().size()==64);

    auto policy=base_options();policy.workspace_validator=[](const auto&,const auto&,const auto&){auto x=workspace_valid();x["result"]["valid"]=false;x["result"]["violations"]=nlohmann::json::array({{{"code","policy"}}});return x;};policy.artifact_builder=[](const auto&,const auto&,const auto&,const auto&)->nlohmann::json{throw std::runtime_error("artifact must not run");};cloudiff::ClassicBuildWorker policy_worker(policy);r=policy_worker.execute(job());assert(r.outcome==cloudiff::ClassicBuildOutcome::terminal_failed);assert(r.error=="workspace_policy_failed");assert(r.result.at("valid")==false);assert(r.result.at("production_ready")==false);assert(!r.result.contains("attestation"));

    auto blocked=base_options();blocked.workspace_validator=[](const auto&,const auto&,const auto&){return workspace_valid();};blocked.artifact_builder=[](const auto&,const auto&,const auto&,const auto&){auto x=artifact_valid();x["ok"]=false;x["scanner_blocked"]=true;x["production_ready"]=false;return x;};cloudiff::ClassicBuildWorker blocked_worker(blocked);r=blocked_worker.execute(job());assert(r.outcome==cloudiff::ClassicBuildOutcome::terminal_failed);assert(r.error=="artifact_policy_failed");assert(r.result.at("valid")==true);assert(r.result.at("production_ready")==false);assert(r.result.at("attestation_verified")==true);

    auto transport=base_options();transport.workspace_validator=[](const auto&,const auto&,const auto&)->nlohmann::json{throw std::runtime_error("synthetic_transport_failure");};transport.artifact_builder=[](const auto&,const auto&,const auto&,const auto&){return artifact_valid();};cloudiff::ClassicBuildWorker transport_worker(transport);bool threw=false;try{(void)transport_worker.execute(job());}catch(const std::runtime_error& e){threw=std::string(e.what())=="synthetic_transport_failure";}assert(threw);

    auto bad_job=job();bad_job.payload["ref"]="../bad";bool invalid=false;try{(void)worker.execute(bad_job);}catch(const std::invalid_argument&){invalid=true;}assert(invalid);
    return 0;
}
