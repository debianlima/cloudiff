#include "cloudiff/build_broker.hpp"
#include "cloudiff/job_engine.hpp"
#include <boost/asio.hpp>
#include <boost/beast.hpp>
#include <openssl/evp.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cstdlib>
#include <iomanip>
#include <memory>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <thread>

namespace cloudiff {
namespace asio=boost::asio;
namespace beast=boost::beast;
namespace http=beast::http;
using tcp=asio::ip::tcp;
namespace {
constexpr std::size_t kMaxBody=1024U*1024U;
constexpr std::string_view kClassicKind="cloudiff.v2.build.classic";
class BuildBrokerError final:public std::runtime_error{
public:BuildBrokerError(int status,std::string code):std::runtime_error(code),status_(status),code_(std::move(code)){}
[[nodiscard]] int status()const noexcept{return status_;}
[[nodiscard]] const std::string& code()const noexcept{return code_;}
private:int status_;std::string code_;
};
std::string env_or(const char* name,std::string fallback={}){const char* v=std::getenv(name);return v?std::string(v):std::move(fallback);}
int env_int(const char* name,int fallback,int lo,int hi){try{return std::clamp(std::stoi(env_or(name,std::to_string(fallback))),lo,hi);}catch(...){return fallback;}}
bool constant_time_equal(std::string_view a,std::string_view b){unsigned int diff=static_cast<unsigned int>(a.size()^b.size());const auto n=std::max(a.size(),b.size());for(std::size_t i=0;i<n;++i){const unsigned char x=i<a.size()?static_cast<unsigned char>(a[i]):0;const unsigned char y=i<b.size()?static_cast<unsigned char>(b[i]):0;diff|=static_cast<unsigned int>(x^y);}return diff==0U;}
std::string sha256(std::string_view value){EVP_MD_CTX* raw=EVP_MD_CTX_new();if(!raw)throw std::runtime_error("sha256_ctx_failed");std::unique_ptr<EVP_MD_CTX,decltype(&EVP_MD_CTX_free)> ctx(raw,EVP_MD_CTX_free);if(EVP_DigestInit_ex(ctx.get(),EVP_sha256(),nullptr)!=1||EVP_DigestUpdate(ctx.get(),value.data(),value.size())!=1)throw std::runtime_error("sha256_failed");std::array<unsigned char,EVP_MAX_MD_SIZE> digest{};unsigned int len=0;if(EVP_DigestFinal_ex(ctx.get(),digest.data(),&len)!=1)throw std::runtime_error("sha256_failed");std::ostringstream out;for(unsigned int i=0;i<len;++i)out<<std::hex<<std::setw(2)<<std::setfill('0')<<static_cast<unsigned int>(digest[i]);return out.str();}
bool valid_slug(std::string_view v){static const std::regex re("^[a-z0-9][a-z0-9-]{0,62}$");return std::regex_match(v.begin(),v.end(),re);}
bool valid_ref(std::string_view v){static const std::regex re("^[A-Za-z0-9._/-]{1,128}$");return std::regex_match(v.begin(),v.end(),re);}
bool valid_digest(std::string_view v){static const std::regex re("^[0-9a-f]{64}$");return std::regex_match(v.begin(),v.end(),re);}
std::string external_status(std::string_view status){if(status=="ready"||status=="waiting_retry")return "queued";if(status=="leased")return "running";return std::string(status);}
std::string sanitize(std::string text){if(text.size()>20000)text.resize(20000);static const std::regex re(R"(((?:authorization|token|password|secret|api[_-]?key)\s*[:=]\s*)\S+)",std::regex::icase);return std::regex_replace(text,re,"$1[redacted]");}
nlohmann::json fetch_plan_http(const std::string& host,unsigned short port,const std::string& framework){asio::io_context io;tcp::resolver resolver(io);beast::tcp_stream stream(io);stream.expires_after(std::chrono::seconds(15));stream.connect(resolver.resolve(host,std::to_string(port)));nlohmann::json payload={{"framework",framework}};http::request<http::string_body> req{http::verb::post,"/v1/plan",11};req.set(http::field::host,host);req.set(http::field::user_agent,"CloudIFF-BuildBroker/0.15");req.set(http::field::content_type,"application/json");req.set(http::field::accept,"application/json");req.body()=payload.dump();req.prepare_payload();http::write(stream,req);beast::flat_buffer buffer;http::response_parser<http::string_body> parser;parser.body_limit(kMaxBody);http::read(stream,buffer,parser);auto res=parser.release();beast::error_code ec;stream.socket().shutdown(tcp::socket::shutdown_both,ec);if(res.result()!=http::status::ok)throw BuildBrokerError(502,"runtime_plan_unavailable");return nlohmann::json::parse(res.body());}
std::string idempotency_key(const nlohmann::json& request){const auto raw=request.at("project_slug").get<std::string>()+"|"+request.at("ref").get<std::string>()+"|"+request.at("framework").get<std::string>()+"|"+request.at("build_plan_digest").get<std::string>()+"|preview|build.request";return sha256(raw);}
nlohmann::json validate_reservation(const nlohmann::json& request,const BuildBrokerOptions& options){for(const char* key:{"project_slug","ref","framework","build_plan_digest"})if(!request.contains(key)||!request.at(key).is_string())throw BuildBrokerError(422,std::string("missing_")+key);const auto slug=request.at("project_slug").get<std::string>(),ref=request.at("ref").get<std::string>(),framework=request.at("framework").get<std::string>(),digest=request.at("build_plan_digest").get<std::string>();if(!valid_slug(slug)||!valid_ref(ref))throw BuildBrokerError(422,"invalid_identifier");if(framework!="static")throw BuildBrokerError(422,"framework_execution_not_ready");if(!valid_digest(digest))throw BuildBrokerError(422,"invalid_plan_digest");const auto plan=options.plan_fetcher(framework);if(!plan.value("ok",false)||!plan.contains("build_plan_digest")||!plan.at("build_plan_digest").is_string()||!constant_time_equal(plan.at("build_plan_digest").get<std::string>(),digest))throw BuildBrokerError(422,"build_plan_digest_mismatch");return {{"project_slug",slug},{"ref",ref},{"framework",framework},{"build_plan_digest",digest}};}
nlohmann::json build_json(const JobSnapshot& job){const auto& p=job.payload;const bool dead=job.status=="dead_letter";return {{"id",job.job_id},{"project_slug",p.value("project_slug","")},{"ref",p.value("ref","")},{"framework",p.value("framework","")},{"plan_digest",p.value("build_plan_digest","")},{"status",external_status(job.status)},{"created_at",job.created_at},{"updated_at",job.updated_at},{"attempts",job.attempt},{"next_attempt_at",job.status=="waiting_retry"?job.retry_at:0LL},{"dead_reason",dead?nlohmann::json("max_attempts_exceeded"):nlohmann::json(nullptr)},{"result",job.result},{"retry_scheduled",job.status=="waiting_retry"},{"dead_letter",dead},{"secrets_exposed",false}};}
std::string logs_for(const JobSnapshot& job,const std::vector<JobAttemptSnapshot>& attempts){std::ostringstream out;out<<"reserved\n";for(const auto& a:attempts){out<<"attempt:"<<a.attempt<<" worker="<<a.worker_id;if(!a.outcome.empty())out<<" outcome="<<a.outcome;out<<'\n';if(!a.error.empty())out<<"error:"<<a.error<<'\n';}out<<"status:"<<external_status(job.status)<<'\n';if(!job.last_error.empty())out<<"last_error:"<<job.last_error<<'\n';return sanitize(out.str());}
}
BuildBroker::BuildBroker(BuildBrokerOptions options):options_(std::move(options)){if(options_.token.empty())throw std::invalid_argument("build broker token required");if(options_.postgres_conninfo.empty())throw std::invalid_argument("postgres conninfo required");if(!options_.plan_fetcher){const auto host=options_.runtime_host;const auto port=options_.runtime_port;options_.plan_fetcher=[host,port](const std::string& framework){return fetch_plan_http(host,port,framework);};}}
BuildBrokerResponse BuildBroker::handle(std::string_view method,
                                        std::string_view path,
                                        std::string_view authorization,
                                        std::string_view body) const {
    if (method == "GET" && path == "/health") {
        return BuildBrokerResponse{200, nlohmann::json{{"ok", true}, {"service", "build-broker"},
            {"queue", "postgresql-skip-locked"}, {"production_ready", false}, {"secrets_exposed", false}}};
    }
    if (!constant_time_equal(authorization, "Bearer " + options_.token)) {
        return BuildBrokerResponse{401, nlohmann::json{{"ok", false}, {"error", "unauthorized"}}};
    }
    try {
        if (method == "POST") {
            nlohmann::json request;
            try {
                request = nlohmann::json::parse(body.empty() ? "{}" : std::string(body));
            } catch (...) {
                return BuildBrokerResponse{400, nlohmann::json{{"ok", false}, {"error", "invalid_json"}}};
            }
            if (!request.is_object()) {
                return BuildBrokerResponse{400, nlohmann::json{{"ok", false}, {"error", "invalid_json"}}};
            }
            if (path == "/v1/plan") {
                return BuildBrokerResponse{200, options_.plan_fetcher(request.value("framework", ""))};
            }
            if (path == "/v1/builds" || path == "/v1/execute") {
                const auto payload = validate_reservation(request, options_);
                JobEngine engine(options_.postgres_conninfo);
                const auto id = engine.enqueue(std::string(kClassicKind),
                    payload.at("project_slug").get<std::string>(), idempotency_key(payload), payload, 3);
                const auto snapshot = engine.get(id);
                if (!snapshot) throw std::runtime_error("enqueued job not found");
                return BuildBrokerResponse{202, nlohmann::json{{"ok", true}, {"phase", "reserve"},
                    {"build_id", id}, {"status", external_status(snapshot->status)},
                    {"idempotent", true}, {"secrets_exposed", false}}};
            }
            if (path == "/internal/drain" || path.starts_with("/v1/toolchain/") ||
                path.starts_with("/v1/multiservice/")) {
                return BuildBrokerResponse{501, nlohmann::json{{"ok", false},
                    {"error", nlohmann::json{{"code", "migration_deferred"},
                        {"message", "Rota permanece no BuildBroker legado nesta unidade."}}},
                    {"secrets_exposed", false}}};
            }
            return BuildBrokerResponse{404, nlohmann::json{{"ok", false}, {"error", "not_found"}}};
        }
        if (method == "GET") {
            static const std::regex route(
                R"(^/v1/projects/([a-z0-9][a-z0-9-]{0,62})/builds/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(/logs|/artifact)?$)");
            std::cmatch match;
            const std::string request_path(path);
            if (!std::regex_match(request_path.c_str(), match, route)) {
                return BuildBrokerResponse{404, nlohmann::json{{"ok", false}, {"error", "not_found"}}};
            }
            JobEngine engine(options_.postgres_conninfo);
            const auto job = engine.get(match[2].str());
            if (!job || job->kind != kClassicKind || job->payload.value("project_slug", "") != match[1].str()) {
                return BuildBrokerResponse{404, nlohmann::json{{"ok", false}, {"error", "build_not_found"}}};
            }
            const auto suffix = match[3].str();
            if (suffix == "/logs") {
                return BuildBrokerResponse{200, nlohmann::json{{"ok", true}, {"project_slug", match[1].str()},
                    {"build_id", job->job_id}, {"logs", logs_for(*job, engine.attempts(job->job_id))},
                    {"secrets_exposed", false}}};
            }
            if (suffix == "/artifact") {
                const bool verified = job->result.is_object() && job->result.value("attestation_verified", false);
                return BuildBrokerResponse{200, nlohmann::json{{"ok", true}, {"project_slug", match[1].str()},
                    {"build_id", job->job_id}, {"artifact", job->result}, {"attestation_verified", verified},
                    {"downloadable", false}, {"secrets_exposed", false}}};
            }
            return BuildBrokerResponse{200, nlohmann::json{{"ok", true}, {"build", build_json(*job)}}};
        }
        return BuildBrokerResponse{404, nlohmann::json{{"ok", false}, {"error", "not_found"}}};
    } catch (const BuildBrokerError& e) {
        return BuildBrokerResponse{e.status(), nlohmann::json{{"ok", false},
            {"error", nlohmann::json{{"code", e.code()},
                {"message", "A solicitação contém campos ausentes ou incompatíveis."}}},
            {"secrets_exposed", false}}};
    } catch (...) {
        return BuildBrokerResponse{500, nlohmann::json{{"ok", false},
            {"error", nlohmann::json{{"code", "build_broker_internal_error"},
                {"message", "Falha interna do broker."}}},
            {"secrets_exposed", false}}};
    }
}
BuildBrokerOptions build_broker_options_from_environment(){BuildBrokerOptions o;o.bind_address=env_or("CLOUDIFF_BUILD_BROKER_BIND","127.0.0.1");o.port=static_cast<unsigned short>(env_int("CLOUDIFF_BUILD_BROKER_PORT",18221,1,65535));o.token=env_or("CLOUDIFF_BUILD_TOKEN");o.postgres_conninfo=env_or("CLOUDIFF_POSTGRES_CONNINFO");o.runtime_host=env_or("CLOUDIFF_BUILD_RUNTIME_HOST","127.0.0.1");o.runtime_port=static_cast<unsigned short>(env_int("CLOUDIFF_BUILD_RUNTIME_PORT",18212,1,65535));return o;}
int run_build_broker_server(const BuildBrokerOptions& options){BuildBroker broker(options);asio::io_context io;tcp::acceptor acceptor(io,{asio::ip::make_address(options.bind_address),options.port});acceptor.set_option(asio::socket_base::reuse_address(true));for(;;){tcp::socket socket(io);acceptor.accept(socket);std::thread([&broker,s=std::move(socket)]()mutable{try{beast::flat_buffer buffer;http::request_parser<http::string_body> parser;parser.body_limit(kMaxBody);http::read(s,buffer,parser);auto req=parser.release();const auto auth_view=req[http::field::authorization];const std::string auth(auth_view.data(),auth_view.size());const std::string target(req.target().data(),req.target().size());auto response=broker.handle(req.method_string(),target,auth,req.body());http::response<http::string_body> res{static_cast<http::status>(response.status),req.version()};res.set(http::field::content_type,"application/json");res.set(http::field::cache_control,"no-store");res.set("X-Content-Type-Options","nosniff");res.keep_alive(false);res.body()=response.body.dump();res.prepare_payload();http::write(s,res);beast::error_code ec;s.shutdown(tcp::socket::shutdown_send,ec);}catch(...){}}).detach();}}
}
