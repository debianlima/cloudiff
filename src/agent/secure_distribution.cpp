#include "cloudiff/secure_distribution.hpp"
#include <boost/asio.hpp>
#include <boost/beast.hpp>
#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace cloudiff {
namespace asio=boost::asio; namespace beast=boost::beast; namespace http=beast::http; using tcp=asio::ip::tcp;
namespace {
constexpr std::size_t kMaxRequestBody=8192;
std::string env_or(const char* n,std::string f={}){const char* v=std::getenv(n);return v?std::string(v):std::move(f);}
int env_int(const char* n,int f,int lo,int hi){try{return std::clamp(std::stoi(env_or(n,std::to_string(f))),lo,hi);}catch(...){return f;}}
bool valid_id(std::string_view v){static const std::regex re("^[a-z0-9][a-z0-9._-]{0,63}$");return std::regex_match(v.begin(),v.end(),re);}
bool valid_audience(std::string_view v){static const std::regex re("^[A-Za-z0-9._:-]{1,128}$");return std::regex_match(v.begin(),v.end(),re);}
std::string hex(const unsigned char* p,std::size_t n){static constexpr char h[]="0123456789abcdef";std::string out(n*2,'0');for(std::size_t i=0;i<n;++i){out[i*2]=h[(p[i]>>4)&0xf];out[i*2+1]=h[p[i]&0xf];}return out;}
std::string sha256(std::string_view value){std::array<unsigned char,EVP_MAX_MD_SIZE> d{};unsigned int len=0;EVP_MD_CTX* c=EVP_MD_CTX_new();if(!c)throw std::runtime_error("sha256_ctx_failed");if(EVP_DigestInit_ex(c,EVP_sha256(),nullptr)!=1||EVP_DigestUpdate(c,value.data(),value.size())!=1||EVP_DigestFinal_ex(c,d.data(),&len)!=1){EVP_MD_CTX_free(c);throw std::runtime_error("sha256_failed");}EVP_MD_CTX_free(c);return hex(d.data(),len);}
bool ct_equal(std::string_view a,std::string_view b){if(a.size()!=b.size())return false;return CRYPTO_memcmp(a.data(),b.data(),a.size())==0;}
nlohmann::json load_json(const std::string& path){std::ifstream in(path);if(!in)throw std::runtime_error("json_open_failed");nlohmann::json x;in>>x;return x;}
std::string read_file(const nlohmann::json& member){const auto path=member.at("path").get<std::string>();const auto max=member.at("max_bytes").get<std::size_t>();std::ifstream in(path,std::ios::binary);if(!in)throw std::runtime_error("distribution_source_open_failed");std::string out;out.reserve(std::min<std::size_t>(max,65536));std::array<char,8192> buf{};while(in){in.read(buf.data(),static_cast<std::streamsize>(buf.size()));const auto got=in.gcount();if(got>0){if(out.size()+static_cast<std::size_t>(got)>max)throw std::runtime_error("distribution_source_too_large");out.append(buf.data(),static_cast<std::size_t>(got));}}if(out.empty())throw std::runtime_error("distribution_source_empty");return out;}
const nlohmann::json* collection(const nlohmann::json& cat,std::string_view id){for(const auto& c:cat.at("collections"))if(c.value("id","")==id)return &c;return nullptr;}
const nlohmann::json* member(const nlohmann::json& c,std::string_view id){for(const auto& m:c.at("members"))if(m.value("id","")==id)return &m;return nullptr;}
bool contains_string(const nlohmann::json& a,std::string_view v){if(!a.is_array())return false;for(const auto& x:a)if(x.is_string()&&x.get<std::string>()==v)return true;return false;}
struct Snapshot final {std::string generation; nlohmann::json manifest; std::map<std::string,std::string> bodies;};
Snapshot snapshot(const nlohmann::json& c){std::vector<nlohmann::json> rows;std::map<std::string,std::string>bodies;for(const auto& m:c.at("members")){const auto id=m.at("id").get<std::string>();auto body=read_file(m);rows.push_back({{"id",id},{"sha256",sha256(body)},{"size",body.size()},{"media_type",m.at("media_type")}});bodies.emplace(id,std::move(body));}std::sort(rows.begin(),rows.end(),[](const auto&a,const auto&b){return a.at("id").template get<std::string>()<b.at("id").template get<std::string>();});std::string canonical;for(const auto& r:rows)canonical+=r.at("id").get<std::string>()+"|"+r.at("sha256").get<std::string>()+"|"+std::to_string(r.at("size").get<std::size_t>())+"\n";const auto gen=sha256(canonical);return {gen,{{"ok",true},{"collection",c.at("id")},{"generation",gen},{"members",rows},{"cache","no-store"}},std::move(bodies)};}
SecureDistributionResponse json_error(int status,const char* code){return {status,nlohmann::json{{"ok",false},{"error",code},{"secrets_exposed",false}}.dump(),"application/json",{{"Cache-Control","no-store"},{"X-Content-Type-Options","nosniff"}}};}
bool authorized(const nlohmann::json& caps,std::string_view auth,std::string_view aud,std::string_view col,std::int64_t now){if(!valid_audience(aud)||!auth.starts_with("Bearer ")||auth.size()<=7)return false;const auto token_hash=sha256(auth.substr(7));for(const auto& c:caps.at("capabilities")){if(c.value("audience","")!=aud)continue;if(c.value("expires_at",0LL)<=now)continue;if(!contains_string(c.value("collections",nlohmann::json::array()),col))continue;const auto expected=c.value("token_sha256","");if(expected.size()==64&&ct_equal(token_hash,expected))return true;}return false;}
}
SecureDistributionProvider::SecureDistributionProvider(nlohmann::json catalog,nlohmann::json capabilities,std::function<std::int64_t()> clock):catalog_(std::move(catalog)),capabilities_(std::move(capabilities)),clock_(std::move(clock)){
    if(!clock_)clock_=[]{return static_cast<std::int64_t>(std::chrono::system_clock::to_time_t(std::chrono::system_clock::now()));};
    if(catalog_.value("version",0)!=1||!catalog_.contains("collections")||!catalog_.at("collections").is_array())throw std::invalid_argument("invalid_distribution_catalog");
    if(capabilities_.value("version",0)!=1||!capabilities_.contains("capabilities")||!capabilities_.at("capabilities").is_array())throw std::invalid_argument("invalid_distribution_capabilities");
    for(const auto& c:catalog_.at("collections")){if(!valid_id(c.value("id",""))||!c.contains("audiences")||!c.contains("members"))throw std::invalid_argument("invalid_distribution_collection");for(const auto& m:c.at("members"))if(!valid_id(m.value("id",""))||!m.contains("path")||!m.contains("max_bytes"))throw std::invalid_argument("invalid_distribution_member");}
}
SecureDistributionResponse SecureDistributionProvider::handle(std::string_view method,std::string_view path,std::string_view authorization,std::string_view audience,std::string_view expected_generation) const{
    if(method=="GET"&&path=="/health")return {200,nlohmann::json{{"ok",true},{"service","secure-distribution"},{"version",1},{"secrets_exposed",false}}.dump(),"application/json",{{"Cache-Control","no-store"}}};
    if(method!="GET")return json_error(405,"method_not_allowed");if(path.find('?')!=std::string_view::npos)return json_error(400,"query_not_allowed");
    constexpr std::string_view prefix="/v1/collections/";if(!path.starts_with(prefix))return json_error(404,"not_found");auto rest=path.substr(prefix.size());const auto slash=rest.find('/');if(slash==std::string_view::npos)return json_error(404,"not_found");const auto cid=rest.substr(0,slash);if(!valid_id(cid))return json_error(404,"not_found");const auto* c=collection(catalog_,cid);if(!c)return json_error(404,"collection_not_found");if(!contains_string(c->at("audiences"),audience)||!authorized(capabilities_,authorization,audience,cid,clock_()))return json_error(403,"capability_denied");
    const auto tail=rest.substr(slash);
    try{
        auto snap=snapshot(*c);
        if(tail=="/manifest"){snap.manifest["audience"]=std::string(audience);return {200,snap.manifest.dump(),"application/json",{{"Cache-Control","no-store"},{"X-CloudIFF-Generation",snap.generation}}};}
        constexpr std::string_view obj="/objects/";if(!tail.starts_with(obj))return json_error(404,"not_found");const auto mid=tail.substr(obj.size());if(!valid_id(mid)||mid.find('/')!=std::string_view::npos)return json_error(404,"not_found");const auto* m=member(*c,mid);if(!m)return json_error(404,"object_not_found");if(expected_generation.empty())return json_error(428,"expected_generation_required");if(!ct_equal(expected_generation,snap.generation))return json_error(409,"generation_changed");const auto it=snap.bodies.find(std::string(mid));if(it==snap.bodies.end())return json_error(404,"object_not_found");const auto digest=sha256(it->second);return {200,it->second,m->at("media_type").get<std::string>(),{{"Cache-Control","no-store"},{"X-Content-Type-Options","nosniff"},{"X-CloudIFF-SHA256",digest},{"X-CloudIFF-Size",std::to_string(it->second.size())},{"X-CloudIFF-Generation",snap.generation}}};
    }catch(const std::exception&){return json_error(503,"distribution_source_unavailable");}
}
SecureDistributionOptions secure_distribution_options_from_environment(){SecureDistributionOptions o;o.bind_address=env_or("CLOUDIFF_DISTRIBUTION_BIND","10.62.91.3");o.port=static_cast<unsigned short>(env_int("CLOUDIFF_DISTRIBUTION_PORT",18240,1,65535));o.catalog_path=env_or("CLOUDIFF_DISTRIBUTION_CATALOG",o.catalog_path);o.capabilities_path=env_or("CLOUDIFF_DISTRIBUTION_CAPABILITIES",o.capabilities_path);return o;}
int run_secure_distribution_server(const SecureDistributionOptions& options){SecureDistributionProvider provider(load_json(options.catalog_path),load_json(options.capabilities_path));asio::io_context io;tcp::acceptor acceptor(io,{asio::ip::make_address(options.bind_address),options.port});acceptor.set_option(asio::socket_base::reuse_address(true));for(;;){tcp::socket socket(io);acceptor.accept(socket);try{beast::flat_buffer buffer;http::request_parser<http::string_body> parser;parser.body_limit(kMaxRequestBody);http::read(socket,buffer,parser);auto req=parser.release();std::string target(req.target());const auto auth_v=req[http::field::authorization];const std::string auth(auth_v.data(),auth_v.size());const auto aud_v=req["X-CloudIFF-Audience"];const std::string aud(aud_v.data(),aud_v.size());const auto gen_v=req["X-CloudIFF-Expected-Generation"];const std::string gen(gen_v.data(),gen_v.size());auto r=provider.handle(req.method_string(),target,auth,aud,gen);http::response<http::string_body> res{static_cast<http::status>(r.status),req.version()};res.set(http::field::content_type,r.content_type);for(const auto&[k,v]:r.headers)res.set(k,v);res.keep_alive(false);res.body()=std::move(r.body);res.prepare_payload();http::write(socket,res);beast::error_code ec;socket.shutdown(tcp::socket::shutdown_send,ec);}catch(const std::exception&){} }}
}
