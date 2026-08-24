#include "cloudiff/mcp_upload.hpp"
#include <boost/asio.hpp>
#include <boost/beast.hpp>
#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <regex>
#include <stdexcept>
#include <string>

namespace cloudiff {
namespace asio=boost::asio;
namespace beast=boost::beast;
namespace http=beast::http;
using tcp=asio::ip::tcp;
namespace {
constexpr std::size_t kMaxBody=64*1024;
std::string env_or(const char* name,std::string fallback={}){const char* v=std::getenv(name);return v?std::string(v):std::move(fallback);}
int env_int(const char* name,int fallback,int lo,int hi){try{return std::clamp(std::stoi(env_or(name,std::to_string(fallback))),lo,hi);}catch(...){return fallback;}}
bool constant_time_equal(std::string_view a,std::string_view b){unsigned char diff=static_cast<unsigned char>(a.size()^b.size());const auto n=std::max(a.size(),b.size());for(std::size_t i=0;i<n;++i){const auto x=i<a.size()?static_cast<unsigned char>(a[i]):0;const auto y=i<b.size()?static_cast<unsigned char>(b[i]):0;diff=static_cast<unsigned char>(diff|(x^y));}return diff==0;}
bool valid_slug(std::string_view v){static const std::regex re("^[a-z0-9][a-z0-9-]{0,62}$");return std::regex_match(v.begin(),v.end(),re);}
bool valid_artifact(std::string_view v){static const std::regex re("^art_[a-f0-9]{24}$");return std::regex_match(v.begin(),v.end(),re);}
bool valid_file_id(std::string_view v){static const std::regex re("^[A-Za-z0-9_-]{6,192}$");return std::regex_match(v.begin(),v.end(),re);}
bool valid_sha(std::string_view v){static const std::regex re("^[a-f0-9]{64}$");return std::regex_match(v.begin(),v.end(),re);}
std::string lower(std::string value){std::transform(value.begin(),value.end(),value.begin(),[](unsigned char c){return static_cast<char>(std::tolower(c));});return value;}
bool suffix_allowed(std::string_view host,const std::vector<std::string>& suffixes){for(const auto& raw:suffixes){const auto s=lower(raw);if(host==s)return true;if(host.size()>s.size()&&host.ends_with(s)&&host[host.size()-s.size()-1]=='.')return true;}return false;}
struct UrlShape { bool valid{false}; std::string host; bool has_query{false}; };
UrlShape parse_download_url(std::string_view raw,const std::vector<std::string>& suffixes){
    if(raw.size()<9||!raw.starts_with("https://"))return {};
    for(char raw_c:raw){const auto c=static_cast<unsigned char>(raw_c);if(c<0x20||c==0x7f||std::isspace(c))return {};}
    auto rest=raw.substr(8);const auto slash=rest.find_first_of("/?#");auto authority=rest.substr(0,slash);if(authority.empty()||authority.find('@')!=std::string_view::npos)return {};
    std::string_view host=authority;if(const auto colon=authority.rfind(':');colon!=std::string_view::npos){if(authority.substr(colon)!=(std::string_view)":443")return {};host=authority.substr(0,colon);}if(host.empty()||host.find(':')!=std::string_view::npos)return {};
    std::string h=lower(std::string(host));static const std::regex dns("^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$");if(!std::regex_match(h,dns)||h.find("..")!=std::string::npos||!suffix_allowed(h,suffixes))return {};
    UrlShape out;out.valid=true;out.host=std::move(h);out.has_query=raw.find('?')!=std::string_view::npos;return out;
}
std::string path_classification(std::string_view raw){if(raw.starts_with("sandbox:/"))return "sandbox";if(raw.starts_with("file://"))return "file_uri";if(raw.find("/mnt/data/")!=std::string_view::npos||raw=="/mnt/data")return "mnt_data";if(raw.starts_with('/'))return "absolute_path";return {};}
McpUploadResponse error(int status,const char* code){return {status,{{"ok",false},{"error",code},{"side_effect_free",true},{"filesystem_access_attempted",false},{"external_network_attempted",false},{"secrets_exposed",false}}};}
bool only_keys(const nlohmann::json& x,std::initializer_list<std::string_view> allowed){for(auto it=x.begin();it!=x.end();++it){bool found=false;for(auto k:allowed)if(it.key()==k){found=true;break;}if(!found)return false;}return true;}
nlohmann::json base_plan(const std::string& requested,const std::string& effective,const std::string& mode){return {{"ok",true},{"requested_tool",requested},{"effective_tool",effective},{"mode",mode},{"side_effect_free",true},{"filesystem_access_attempted",false},{"external_network_attempted",false},{"workspace_mutation",false},{"download_url_persisted",false},{"secrets_exposed",false}};}
}
McpUploadPlanner::McpUploadPlanner(McpUploadOptions options):options_(std::move(options)){if(options_.token.empty())throw std::invalid_argument("mcp upload token required");if(options_.allowed_download_suffixes.empty())throw std::invalid_argument("download suffix allowlist required");for(auto& s:options_.allowed_download_suffixes){s=lower(s);while(!s.empty()&&s.front()=='.')s.erase(s.begin());if(s.empty())throw std::invalid_argument("invalid download suffix");}}
McpUploadResponse McpUploadPlanner::handle(std::string_view method,std::string_view path,std::string_view authorization,std::string_view body) const{
    if(method=="GET"&&path=="/health")return {200,{{"ok",true},{"service","mcp-upload-planner"},{"mode","shadow-plan-only"},{"effects_enabled",false},{"tools",nlohmann::json::array({"workspace.artifact.import","workspace.artifact.upload.file"})},{"secrets_exposed",false}}};
    if(!constant_time_equal(authorization,"Bearer "+options_.token))return error(401,"unauthorized");if(method!="POST"||path!="/v1/plan")return error(404,"not_found");
    nlohmann::json req;try{req=nlohmann::json::parse(body.empty()?"{}":std::string(body));}catch(...){return error(400,"invalid_json");}if(!req.is_object())return error(422,"invalid_request");
    const auto tool=req.value("requested_tool",std::string{});const bool is_import=tool=="workspace.artifact.import",is_existing=tool=="workspace.artifact.upload.file";if(!is_import&&!is_existing)return error(422,"unsupported_tool");
    const auto slug=req.value("slug",std::string{});if(!valid_slug(slug)||!req.contains("file"))return error(422,"invalid_request");
    if(is_import){
        if(!only_keys(req,{"requested_tool","slug","file","filename","expected_size","expected_sha256","ttl_seconds"}))return error(422,"unexpected_field");
        const auto filename=req.value("filename",std::string{});if(filename.empty()||filename.size()>240||filename.find('/')!=std::string::npos||filename.find('\\')!=std::string::npos)return error(422,"invalid_filename");
        if(!req.contains("expected_size")||!req.at("expected_size").is_number_integer()||req.at("expected_size").get<long long>()<0||req.at("expected_size").get<long long>()>1073741824LL)return error(422,"invalid_expected_size");
        if(!valid_sha(req.value("expected_sha256",std::string{})))return error(422,"invalid_expected_sha256");
        if(req.contains("ttl_seconds")&&(!req.at("ttl_seconds").is_number_integer()||req.at("ttl_seconds").get<int>()<300||req.at("ttl_seconds").get<int>()>86400))return error(422,"invalid_ttl");
    }else{
        if(!only_keys(req,{"requested_tool","slug","artifact_id","file"})||!valid_artifact(req.value("artifact_id",std::string{})))return error(422,"invalid_artifact_id");
    }
    const auto& file=req.at("file");
    if(file.is_string()){
        const auto classification=path_classification(file.get<std::string>());if(classification.empty())return error(422,"openai_file_param_object_required");
        if(is_import){auto plan=base_plan(tool,"workspace.artifact.upload.start","portal_upload_start");plan["file_params_hydrated"]=false;plan["host_hydration_required"]=true;plan["automatic_fallback"]=true;plan["fallback_reason"]="host_file_param_not_hydrated";plan["file_shape"]={{"classification",classification},{"value_type","string"}};plan["fallback_input"]={{"slug",slug},{"filename",req.at("filename")},{"expected_size",req.at("expected_size")},{"expected_sha256",req.at("expected_sha256")},{"ttl_seconds",req.value("ttl_seconds",7200)}};return {200,std::move(plan)};}
        auto plan=base_plan(tool,"workspace.artifact.upload.file.select","file_picker");plan["file_params_hydrated"]=false;plan["host_hydration_required"]=true;plan["automatic_fallback"]=true;plan["fallback_reason"]="host_file_param_not_hydrated";plan["file_shape"]={{"classification",classification},{"value_type","string"}};plan["fallback_input"]={{"slug",slug},{"artifact_id",req.at("artifact_id")}};plan["ui_resource"]="ui://cloudiff/artifact-upload-v1.html";return {200,std::move(plan)};
    }
    if(!file.is_object()||!only_keys(file,{"download_url","file_id","mime_type","file_name"})||!file.contains("download_url")||!file.contains("file_id")||!file.at("download_url").is_string()||!file.at("file_id").is_string())return error(422,"openai_file_param_object_required");
    const auto file_id=file.at("file_id").get<std::string>();if(!valid_file_id(file_id))return error(422,"invalid_file_id");const auto shape=parse_download_url(file.at("download_url").get<std::string>(),options_.allowed_download_suffixes);if(!shape.valid)return error(422,"download_url_not_allowed");
    if(file.contains("file_name")&&(!file.at("file_name").is_string()||file.at("file_name").get<std::string>().size()>240))return error(422,"invalid_file_name");if(file.contains("mime_type")&&(!file.at("mime_type").is_string()||file.at("mime_type").get<std::string>().size()>255))return error(422,"invalid_mime_type");
    auto plan=base_plan(tool,tool,"direct_https_stream");plan["file_params_hydrated"]=true;plan["host_hydration_required"]=false;plan["automatic_fallback"]=false;plan["file"]={{"file_id",file_id},{"download_host",shape.host},{"download_has_query",shape.has_query}};if(file.contains("file_name")&&!file.at("file_name").get<std::string>().empty())plan["file"]["file_name"]=file.at("file_name");if(file.contains("mime_type")&&!file.at("mime_type").get<std::string>().empty())plan["file"]["mime_type"]=file.at("mime_type");return {200,std::move(plan)};
}
McpUploadOptions mcp_upload_options_from_environment(){McpUploadOptions o;o.bind_address=env_or("CLOUDIFF_MCP_UPLOAD_BIND","127.0.0.1");o.port=static_cast<unsigned short>(env_int("CLOUDIFF_MCP_UPLOAD_PORT",18234,1,65535));o.token=env_or("CLOUDIFF_MCP_UPLOAD_TOKEN");const auto raw=env_or("CLOUDIFF_MCP_UPLOAD_DOWNLOAD_SUFFIXES","oaiusercontent.com,openai.com,chatgpt.com");o.allowed_download_suffixes.clear();std::size_t start=0;while(start<=raw.size()){const auto pos=raw.find(',',start);auto item=raw.substr(start,pos==std::string::npos?std::string::npos:pos-start);item.erase(0,item.find_first_not_of(" \t"));const auto end=item.find_last_not_of(" \t");if(end!=std::string::npos)item.resize(end+1);if(!item.empty())o.allowed_download_suffixes.push_back(item);if(pos==std::string::npos)break;start=pos+1;}return o;}
int run_mcp_upload_server(const McpUploadOptions& options){McpUploadPlanner planner(options);asio::io_context io;tcp::acceptor acceptor(io,{asio::ip::make_address(options.bind_address),options.port});acceptor.set_option(asio::socket_base::reuse_address(true));for(;;){tcp::socket socket(io);acceptor.accept(socket);try{beast::flat_buffer buffer;http::request_parser<http::string_body> parser;parser.body_limit(kMaxBody);http::read(socket,buffer,parser);auto req=parser.release();std::string target(req.target());if(auto q=target.find('?');q!=std::string::npos)target.resize(q);const auto av=req[http::field::authorization];const std::string auth(av.data(),av.size());auto r=planner.handle(req.method_string(),target,auth,req.body());http::response<http::string_body> res{static_cast<http::status>(r.status),req.version()};res.set(http::field::content_type,"application/json");res.set(http::field::cache_control,"no-store");res.set("X-Content-Type-Options","nosniff");res.keep_alive(false);res.body()=r.body.dump();res.prepare_payload();http::write(socket,res);beast::error_code ec;socket.shutdown(tcp::socket::shutdown_send,ec);}catch(const std::exception&){} }}
}
