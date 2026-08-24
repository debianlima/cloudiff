#include "cloudiff/build_broker.hpp"
#include "cloudiff/job_engine.hpp"
#include <libpq-fe.h>
#include <openssl/evp.h>
#include <array>
#include <cassert>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>

namespace {
void require_ok(PGconn* c,PGresult* r){assert(r);assert(PQresultStatus(r)==PGRES_COMMAND_OK);PQclear(r);(void)c;}
void cleanup(const char* ci){PGconn* c=PQconnectdb(ci);assert(c&&PQstatus(c)==CONNECTION_OK);auto* r=PQexec(c,"DELETE FROM cloudiff_v2.jobs WHERE kind='cloudiff.v2.build.classic' AND payload->>'project_slug' LIKE 'v15-%'");require_ok(c,r);PQfinish(c);}
std::string sha256(std::string_view value){EVP_MD_CTX* raw=EVP_MD_CTX_new();assert(raw);std::unique_ptr<EVP_MD_CTX,decltype(&EVP_MD_CTX_free)> ctx(raw,EVP_MD_CTX_free);assert(EVP_DigestInit_ex(ctx.get(),EVP_sha256(),nullptr)==1);assert(EVP_DigestUpdate(ctx.get(),value.data(),value.size())==1);std::array<unsigned char,EVP_MAX_MD_SIZE> digest{};unsigned int len=0;assert(EVP_DigestFinal_ex(ctx.get(),digest.data(),&len)==1);std::ostringstream out;for(unsigned int i=0;i<len;++i)out<<std::hex<<std::setw(2)<<std::setfill('0')<<static_cast<unsigned int>(digest[i]);return out.str();}
}
int main(){
 const char* ci=std::getenv("CLOUDIFF_POSTGRES_CONNINFO");assert(ci);cleanup(ci);
 const std::string plan_digest(64,'a');cloudiff::BuildBrokerOptions options;options.token="unit-secret";options.postgres_conninfo=ci;options.plan_fetcher=[&](const std::string& framework){return nlohmann::json{{"ok",true},{"side_effect_free",true},{"plan",{{"framework",framework}}},{"build_plan_digest",plan_digest},{"commands_derived_from_policy",true},{"production_effects_enabled",false}};};cloudiff::BuildBroker broker(options);
 auto r=broker.handle("GET","/health","","");assert(r.status==200);assert(r.body.at("service")=="build-broker");assert(r.body.at("queue")=="postgresql-skip-locked");assert(r.body.at("production_ready")==false);
 r=broker.handle("POST","/v1/builds","",R"({})");assert(r.status==401);assert(r.body.at("error")=="unauthorized");
 r=broker.handle("POST","/v1/builds","Bearer unit-secret","not-json");assert(r.status==400);assert(r.body.at("error")=="invalid_json");
 const nlohmann::json request={{"project_slug","v15-fixture"},{"ref","main"},{"framework","static"},{"build_plan_digest",plan_digest}};
 r=broker.handle("POST","/v1/plan","Bearer unit-secret",R"({"framework":"static"})");assert(r.status==200);assert(r.body.at("build_plan_digest")==plan_digest);assert(r.body.at("side_effect_free")==true);
 r=broker.handle("POST","/v1/builds","Bearer unit-secret",request.dump());assert(r.status==202);assert(r.body.at("phase")=="reserve");assert(r.body.at("status")=="queued");assert(r.body.at("idempotent")==true);const auto build_id=r.body.at("build_id").get<std::string>();assert(build_id.size()==36);
 // Exact legacy idempotency material is preserved.
 cloudiff::JobEngine engine(ci);auto snapshot=engine.get(build_id);assert(snapshot);const auto expected=sha256("v15-fixture|main|static|"+plan_digest+"|preview|build.request");assert(snapshot->idempotency_key==expected);assert(snapshot->kind=="cloudiff.v2.build.classic");assert(snapshot->partition_key=="v15-fixture");assert(snapshot->status=="ready");assert(snapshot->attempt==0);assert(snapshot->result.is_null());
 r=broker.handle("POST","/v1/execute","Bearer unit-secret",request.dump());assert(r.status==202);assert(r.body.at("build_id")==build_id);assert(r.body.at("status")=="queued");
 r=broker.handle("GET","/v1/projects/v15-fixture/builds/"+build_id,"Bearer unit-secret","");assert(r.status==200);const auto build=r.body.at("build");assert(build.at("id")==build_id);assert(build.at("project_slug")=="v15-fixture");assert(build.at("status")=="queued");assert(build.at("attempts")==0);assert(build.at("result").is_null());assert(build.at("retry_scheduled")==false);assert(build.at("dead_letter")==false);assert(build.at("secrets_exposed")==false);
 r=broker.handle("GET","/v1/projects/v15-fixture/builds/"+build_id+"/logs","Bearer unit-secret","");assert(r.status==200);assert(r.body.at("logs").get<std::string>().find("reserved")!=std::string::npos);assert(r.body.at("logs").get<std::string>().find("status:queued")!=std::string::npos);
 r=broker.handle("GET","/v1/projects/v15-fixture/builds/"+build_id+"/artifact","Bearer unit-secret","");assert(r.status==200);assert(r.body.at("artifact").is_null());assert(r.body.at("attestation_verified")==false);assert(r.body.at("downloadable")==false);
 r=broker.handle("GET","/v1/projects/other/builds/"+build_id,"Bearer unit-secret","");assert(r.status==404);assert(r.body.at("error")=="build_not_found");
 // Generic shadow worker must not claim classic build jobs.
 auto generic=engine.claim_kinds("v15-generic",8,10,{"cloudiff.v2.noop","cloudiff.v2.fail_once"});(void)generic;snapshot=engine.get(build_id);assert(snapshot&&snapshot->status=="ready"&&snapshot->attempt==0);
 // Explicit future build worker can claim the same job; synthesize the v16 result shape and complete it.
 auto claimed=engine.claim_kinds("v15-explicit",8,10,{"cloudiff.v2.build.classic"});bool found=false;for(const auto& j:claimed)if(j.job_id==build_id){found=true;assert(j.attempt==1);}assert(found);
 const nlohmann::json att={{"payload",{{"version",1},{"project_slug","v15-fixture"},{"build_id",build_id},{"artifact_image_id","sha256:"+std::string(64,'b')},{"sbom_sha256",std::string(64,'c')},{"scanner_sha256",std::string(64,'d')},{"immutable_source_digest",std::string(64,'e')},{"policy","HMAC-SHA256"}}},{"signature",std::string(64,'f')},{"algorithm","HMAC-SHA256"},{"verified",true}};
 const nlohmann::json result={{"valid",true},{"workspace_profile","test-static"},{"immutable_source_digest",std::string(64,'e')},{"image_created",true},{"artifact_image_id","sha256:"+std::string(64,'b')},{"sbom_ready",true},{"sbom_sha256",std::string(64,'c')},{"scanner_ready",true},{"scanner_sha256",std::string(64,'d')},{"scanner_blocked",false},{"scanner_counts",{{"HIGH",0},{"CRITICAL",0}}},{"production_ready",true},{"secrets_exposed",false},{"attestation",att},{"attestation_verified",true}};
 assert(engine.complete(build_id,"v15-explicit",result));
 r=broker.handle("GET","/v1/projects/v15-fixture/builds/"+build_id,"Bearer unit-secret","");assert(r.status==200);assert(r.body.at("build").at("status")=="succeeded");assert(r.body.at("build").at("attempts")==1);assert(r.body.at("build").at("result").at("attestation").at("algorithm")=="HMAC-SHA256");
 r=broker.handle("GET","/v1/projects/v15-fixture/builds/"+build_id+"/artifact","Bearer unit-secret","");assert(r.status==200);assert(r.body.at("attestation_verified")==true);assert(r.body.at("artifact").at("attestation").at("signature").get<std::string>().size()==64);
 r=broker.handle("GET","/v1/projects/v15-fixture/builds/"+build_id+"/logs","Bearer unit-secret","");assert(r.status==200);assert(r.body.at("logs").get<std::string>().find("outcome=succeeded")!=std::string::npos);
 // Idempotent reservation after completion returns the same UUID and terminal status.
 r=broker.handle("POST","/v1/builds","Bearer unit-secret",request.dump());assert(r.status==202);assert(r.body.at("build_id")==build_id);assert(r.body.at("status")=="succeeded");
 auto bad=request;bad["framework"]="node";r=broker.handle("POST","/v1/builds","Bearer unit-secret",bad.dump());assert(r.status==422);assert(r.body.at("error").at("code")=="framework_execution_not_ready");
 bad=request;bad["build_plan_digest"]=std::string(64,'9');r=broker.handle("POST","/v1/builds","Bearer unit-secret",bad.dump());assert(r.status==422);assert(r.body.at("error").at("code")=="build_plan_digest_mismatch");
 r=broker.handle("POST","/internal/drain","Bearer unit-secret","{}");assert(r.status==501);assert(r.body.at("error").at("code")=="migration_deferred");
 cleanup(ci);std::cout<<"build_broker_contract=PASS\n";return 0;
}
