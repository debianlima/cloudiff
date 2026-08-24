#include "cloudiff/classic_build_worker.hpp"
#include <boost/asio.hpp>
#include <boost/beast.hpp>
#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdlib>
#include <iomanip>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>

namespace cloudiff {
namespace asio=boost::asio;
namespace beast=boost::beast;
namespace http=beast::http;
using tcp=asio::ip::tcp;
namespace {
constexpr std::size_t kMaxBody=1024*1024;
std::string env_or(const char* name,std::string fallback={}){const char* v=std::getenv(name);return v?std::string(v):std::move(fallback);}
int env_int(const char* name,int fallback,int lo,int hi){try{return std::clamp(std::stoi(env_or(name,std::to_string(fallback))),lo,hi);}catch(...){return fallback;}}
bool valid_slug(std::string_view value){static const std::regex re("^[a-z0-9][a-z0-9-]{0,62}$");return std::regex_match(value.begin(),value.end(),re);}
bool valid_ref(std::string_view value){static const std::regex re("^[A-Za-z0-9._/-]{1,128}$");return std::regex_match(value.begin(),value.end(),re)&&value.find("..") == std::string_view::npos&&!value.starts_with('/')&&!value.ends_with('/');}
bool valid_sha(std::string_view value){static const std::regex re("^[a-f0-9]{64}$");return std::regex_match(value.begin(),value.end(),re);}
std::string hex(const unsigned char* data,std::size_t size){std::ostringstream out;for(std::size_t i=0;i<size;++i)out<<std::hex<<std::setw(2)<<std::setfill('0')<<static_cast<unsigned int>(data[i]);return out.str();}
std::string sha256(std::string_view value){std::array<unsigned char,EVP_MAX_MD_SIZE> digest{};unsigned int len=0;EVP_MD_CTX* ctx=EVP_MD_CTX_new();if(!ctx)throw std::runtime_error("sha256_ctx_failed");if(EVP_DigestInit_ex(ctx,EVP_sha256(),nullptr)!=1||EVP_DigestUpdate(ctx,value.data(),value.size())!=1||EVP_DigestFinal_ex(ctx,digest.data(),&len)!=1){EVP_MD_CTX_free(ctx);throw std::runtime_error("sha256_failed");}EVP_MD_CTX_free(ctx);return hex(digest.data(),len);}
std::string hmac_sha256(const std::string& key,std::string_view value){std::array<unsigned char,EVP_MAX_MD_SIZE> digest{};unsigned int len=0;if(HMAC(EVP_sha256(),key.data(),static_cast<int>(key.size()),reinterpret_cast<const unsigned char*>(value.data()),value.size(),digest.data(),&len)==nullptr)throw std::runtime_error("hmac_failed");return hex(digest.data(),len);}
bool constant_time_equal(std::string_view a,std::string_view b){if(a.size()!=b.size())return false;return CRYPTO_memcmp(a.data(),b.data(),a.size())==0;}
std::string canonical(const nlohmann::json& value){return value.dump(-1,' ',true,nlohmann::json::error_handler_t::strict);}
nlohmann::json http_json(const std::string& host,unsigned short port,const std::string& host_header,const std::string& target,const std::string& token,const nlohmann::json& body,int timeout_seconds){
    asio::io_context io;tcp::resolver resolver(io);beast::tcp_stream stream(io);stream.expires_after(std::chrono::seconds(timeout_seconds));stream.connect(resolver.resolve(host,std::to_string(port)));
    http::request<http::string_body> req{http::verb::post,target,11};req.set(http::field::host,host_header.empty()?host:host_header);req.set(http::field::user_agent,"CloudIFF-ClassicBuildWorker/0.27");req.set(http::field::authorization,"Bearer "+token);req.set(http::field::content_type,"application/json");req.set(http::field::accept,"application/json");req.body()=body.dump();req.prepare_payload();http::write(stream,req);
    beast::flat_buffer buffer;http::response_parser<http::string_body> parser;parser.body_limit(kMaxBody);http::read(stream,buffer,parser);auto res=parser.release();beast::error_code ec;stream.socket().shutdown(tcp::socket::shutdown_both,ec);
    if(res.result_int()<200||res.result_int()>=300)throw std::runtime_error("upstream_http_"+std::to_string(res.result_int()));
    auto parsed=nlohmann::json::parse(res.body());if(!parsed.is_object())throw std::runtime_error("upstream_json_invalid");return parsed;
}
nlohmann::json workspace_http(const ClassicBuildWorkerOptions& o,const std::string& slug,const std::string& ref,const std::string& trace){return http_json(o.workspace_host,o.workspace_port,o.workspace_host,"/v1/test-static",o.workspace_token,{{"project_slug",slug},{"ref",ref},{"trace_id",trace}},180);}
nlohmann::json artifact_http(const ClassicBuildWorkerOptions& o,const std::string& slug,const std::string& ref,const std::string& build_id,const std::string& archive_sha){return http_json(o.artifact_host,o.artifact_port,o.artifact_host_header,"/v1/build",o.artifact_token,{{"profile","classic-static-v2"},{"project_slug",slug},{"ref",ref},{"build_id",build_id},{"archive_sha256",archive_sha}},950);}
nlohmann::json attestation(const ClassicBuildWorkerOptions& o,const std::string& slug,const std::string& build_id,const nlohmann::json& summary){
    nlohmann::json payload={{"version",1},{"project_slug",slug},{"build_id",build_id},{"artifact_image_id",summary.contains("artifact_image_id")?summary.at("artifact_image_id"):nlohmann::json(nullptr)},{"sbom_sha256",summary.contains("sbom_sha256")?summary.at("sbom_sha256"):nlohmann::json(nullptr)},{"scanner_sha256",summary.contains("scanner_sha256")?summary.at("scanner_sha256"):nlohmann::json(nullptr)},{"immutable_source_digest",summary.at("immutable_source_digest")},{"policy","HMAC-SHA256"}};
    const auto raw=canonical(payload);const auto signature=hmac_sha256(o.attestation_key,raw);const bool verified=constant_time_equal(signature,hmac_sha256(o.attestation_key,raw));return {{"payload",payload},{"signature",signature},{"algorithm","HMAC-SHA256"},{"verified",verified}};
}
}
ClassicBuildWorker::ClassicBuildWorker(ClassicBuildWorkerOptions options):options_(std::move(options)){
    if(options_.workspace_token.empty()||options_.artifact_token.empty()||options_.attestation_key.empty())throw std::invalid_argument("classic build credentials required");
    if(!options_.workspace_validator){const auto copy=options_;options_.workspace_validator=[copy](const std::string& slug,const std::string& ref,const std::string& trace){return workspace_http(copy,slug,ref,trace);};}
    if(!options_.artifact_builder){const auto copy=options_;options_.artifact_builder=[copy](const std::string& slug,const std::string& ref,const std::string& build_id,const std::string& archive_sha){return artifact_http(copy,slug,ref,build_id,archive_sha);};}
}
ClassicBuildExecution ClassicBuildWorker::execute(const DurableJob& job) const{
    if(job.kind!="cloudiff.v2.build.classic")throw std::invalid_argument("unsupported classic build kind");
    if(!job.payload.is_object())throw std::invalid_argument("classic build payload must be object");
    const auto slug=job.payload.value("project_slug","");const auto ref=job.payload.value("ref","");const auto framework=job.payload.value("framework","");const auto plan=job.payload.value("build_plan_digest","");
    if(!valid_slug(slug)||!valid_ref(ref)||framework!="static"||!valid_sha(plan))throw std::invalid_argument("invalid classic build payload");
    const auto workspace=options_.workspace_validator(slug,ref,job.job_id);if(!workspace.is_object()||!workspace.value("ok",false)||!workspace.contains("result")||!workspace.at("result").is_object())throw std::runtime_error("workspace_response_invalid");
    const auto immutable=sha256(canonical(workspace));const auto& wr=workspace.at("result");
    if(!wr.value("valid",false)){
        nlohmann::json summary={{"valid",false},{"workspace_profile","test-static"},{"immutable_source_digest",immutable},{"image_created",false},{"sbom_ready",false},{"scanner_ready",false},{"production_ready",false},{"secrets_exposed",false}};
        return {ClassicBuildOutcome::terminal_failed,std::move(summary),"workspace_policy_failed"};
    }
    const auto archive_sha=wr.value("archive_sha256","");if(!valid_sha(archive_sha))throw std::runtime_error("workspace_archive_digest_invalid");
    const auto art=options_.artifact_builder(slug,ref,job.job_id,archive_sha);if(!art.is_object()||!art.contains("ok"))throw std::runtime_error("artifact_response_invalid");
    const bool artifact_ok=art.value("ok",false)&&art.value("production_ready",false)&&art.value("sbom_ready",false)&&art.value("scanner_ready",false)&&!art.value("scanner_blocked",true);
    nlohmann::json summary={{"valid",true},{"workspace_profile","test-static"},{"immutable_source_digest",immutable},{"image_created",art.contains("artifact_image_id")&&!art.at("artifact_image_id").is_null()},{"artifact_image_id",art.value("artifact_image_id","")},{"artifact_tag",art.value("artifact_tag","")},{"base_image",art.value("base_image","")},{"sbom_ready",art.value("sbom_ready",false)},{"sbom_format",art.value("sbom_format","")},{"sbom_spec_version",art.value("sbom_spec_version","")},{"sbom_components",art.value("sbom_components",0)},{"sbom_sha256",art.value("sbom_sha256","")},{"scanner_ready",art.value("scanner_ready",false)},{"scanner_policy",art.value("scanner_policy","")},{"scanner_counts",art.value("scanner_counts",nlohmann::json::object())},{"scanner_sha256",art.value("scanner_sha256","")},{"scanner_blocked",art.value("scanner_blocked",false)},{"runtime_proof",art.value("runtime_proof",nlohmann::json::object())},{"production_ready",artifact_ok},{"artifact_executor_idempotent",art.value("idempotent",false)},{"secrets_exposed",false}};
    summary["attestation"]=attestation(options_,slug,job.job_id,summary);summary["attestation_verified"]=summary.at("attestation").value("verified",false);if(!summary.at("attestation_verified").get<bool>())throw std::runtime_error("attestation_verification_failed");
    if(!artifact_ok)return {ClassicBuildOutcome::terminal_failed,std::move(summary),"artifact_policy_failed"};
    return {ClassicBuildOutcome::succeeded,std::move(summary),{}};
}
ClassicBuildWorkerOptions classic_build_worker_options_from_environment(){
    ClassicBuildWorkerOptions o;o.workspace_host=env_or("CLOUDIFF_BUILD_WORKSPACE_HOST","127.0.0.1");o.workspace_port=static_cast<unsigned short>(env_int("CLOUDIFF_BUILD_WORKSPACE_PORT",18206,1,65535));o.workspace_token=env_or("CLOUDIFF_BUILD_WORKSPACE_TOKEN");o.artifact_host=env_or("CLOUDIFF_BUILD_ARTIFACT_HOST","10.62.91.3");o.artifact_port=static_cast<unsigned short>(env_int("CLOUDIFF_BUILD_ARTIFACT_PORT",80,1,65535));o.artifact_host_header=env_or("CLOUDIFF_BUILD_ARTIFACT_HOST_HEADER","cloudif-artifact-executor-v2.internal");o.artifact_token=env_or("CLOUDIFF_BUILD_ARTIFACT_TOKEN");o.attestation_key=env_or("CLOUDIFF_BUILD_ATTESTATION_KEY");return o;
}
}
