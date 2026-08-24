#include "cloudiff/npm_publisher_provider.hpp"
#include <boost/asio.hpp>
#include <boost/beast.hpp>
#include <openssl/pem.h>
#include <openssl/x509v3.h>
#include <algorithm>
#include <chrono>
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <thread>
#include <sys/wait.h>
#include <signal.h>
#include <unistd.h>

namespace cloudiff {
namespace asio = boost::asio;
namespace beast = boost::beast;
namespace http = beast::http;
using tcp = asio::ip::tcp;

namespace {
class ValidationError final : public std::runtime_error { using std::runtime_error::runtime_error; };
std::string env_or(const char* name,std::string fallback={}){const char* v=std::getenv(name);return v?std::string(v):std::move(fallback);}
bool env_bool(const char* name,bool fallback){auto v=env_or(name);if(v.empty())return fallback;std::transform(v.begin(),v.end(),v.begin(),[](unsigned char c){return static_cast<char>(std::tolower(c));});return v=="1"||v=="true"||v=="yes"||v=="on";}
int env_int(const char* name,int fallback){try{return std::stoi(env_or(name,std::to_string(fallback)));}catch(...){return fallback;}}
std::string now_utc(){const auto now=std::chrono::system_clock::now();const auto tt=std::chrono::system_clock::to_time_t(now);std::tm tm{};gmtime_r(&tt,&tm);std::ostringstream o;o<<std::put_time(&tm,"%Y-%m-%dT%H:%M:%SZ");return o.str();}
bool constant_time_equal(std::string_view a,std::string_view b){unsigned char diff=static_cast<unsigned char>(a.size()^b.size());const auto n=std::max(a.size(),b.size());for(std::size_t i=0;i<n;++i){const unsigned char x=i<a.size()?static_cast<unsigned char>(a[i]):0;const unsigned char y=i<b.size()?static_cast<unsigned char>(b[i]):0;diff=static_cast<unsigned char>(diff|(x^y));}return diff==0;}
bool valid_label(std::string_view s){if(s.empty()||s.size()>63||s.front()=='-'||s.back()=='-')return false;return std::all_of(s.begin(),s.end(),[](unsigned char c){return std::islower(c)||std::isdigit(c)||c=='-';});}
bool safe_dns_name(const std::string& name){
    if(name.empty()||name.size()>253)return false;
    std::size_t start=0;
    while(start<name.size()){
        const auto dot=name.find('.',start);const auto end=dot==std::string::npos?name.size():dot;
        if(!valid_label(std::string_view(name).substr(start,end-start)))return false;
        if(dot==std::string::npos)break;start=dot+1;
    }
    return name.ends_with(".cloudiff.duckdns.org");
}
bool safe_cert(std::string_view s){return !s.empty()&&s.size()<=200&&std::all_of(s.begin(),s.end(),[](unsigned char c){return std::isalnum(c)||c=='-'||c=='_'||c=='.';});}
long long as_int(const nlohmann::json& value,const char* field){try{if(value.is_number_integer())return value.get<long long>();if(value.is_string()){std::size_t used=0;auto s=value.get<std::string>();auto v=std::stoll(s,&used);if(used==s.size())return v;}}catch(...){}throw ValidationError(std::string("invalid_")+field);}
void validate_num(long long num,long long maximum,const char* field){if(num<1||num>maximum)throw ValidationError(std::string("invalid_")+field);}
void ensure_maps(nlohmann::json& state){if(!state.is_object())state=nlohmann::json::object();for(const char* k:{"projects","aliases","stages","tenants"})if(!state.contains(k)||!state[k].is_object())state[k]=nlohmann::json::object();}

void run_command(const std::vector<std::string>& command,int timeout_seconds){
    if(command.empty())throw std::runtime_error("command_empty");
    pid_t pid=fork();
    if(pid<0)throw std::runtime_error("fork_failed");
    if(pid==0){
        std::vector<char*> argv;argv.reserve(command.size()+1);
        for(const auto& part:command)argv.push_back(const_cast<char*>(part.c_str()));
        argv.push_back(nullptr);execvp(argv[0],argv.data());_exit(127);
    }
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(std::max(1,timeout_seconds));
    int status=0;
    for(;;){
        const pid_t r=waitpid(pid,&status,WNOHANG);
        if(r==pid)break;
        if(r<0)throw std::runtime_error("waitpid_failed");
        if(std::chrono::steady_clock::now()>=deadline){kill(pid,SIGKILL);(void)waitpid(pid,&status,0);throw std::runtime_error("command_timeout:"+command.front());}
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    if(!WIFEXITED(status)||WEXITSTATUS(status)!=0)throw std::runtime_error("command_failed:"+command.front()+":"+std::to_string(WIFEXITED(status)?WEXITSTATUS(status):-1));
}
bool certificate_covers(const std::filesystem::path& cert,const std::vector<std::string>& domains){
    FILE* file=fopen(cert.c_str(),"r");if(!file)return false;
    X509* x=PEM_read_X509(file,nullptr,nullptr,nullptr);fclose(file);if(!x)return false;
    bool ok=true;for(const auto& domain:domains){if(X509_check_host(x,domain.c_str(),domain.size(),0,nullptr)!=1){ok=false;break;}}
    X509_free(x);return ok;
}
std::string error_detail(const std::exception& e){std::string s=e.what();if(s.size()>500)s.resize(500);return s;}
}

NpmPublisherProvider::NpmPublisherProvider(PublisherOptions options):options_(std::move(options)){
    if(options_.token.empty())throw std::invalid_argument("publisher token required");
    if(std::filesystem::exists(options_.state_path)){
        std::ifstream in(options_.state_path); if(!in)throw std::runtime_error("state_open_failed"); in>>state_;
    }else state_=nlohmann::json::object();
    ensure_maps(state_);
}
std::string NpmPublisherProvider::ensure_certificate(const std::string& name,const std::vector<std::string>& requested_domains) const{
    if(!safe_cert(name))throw ValidationError("invalid_certificate_name");
    std::vector<std::string> domains=requested_domains;
    std::sort(domains.begin(),domains.end());domains.erase(std::unique(domains.begin(),domains.end()),domains.end());
    if(domains.empty()||!std::all_of(domains.begin(),domains.end(),safe_dns_name))throw ValidationError("invalid_certificate_domain");
    if(options_.dry_run)return name;
    std::scoped_lock cert_lock(certificate_mutex_);
    const auto cert=options_.certificate_root/name/"fullchain.pem";
    if(std::filesystem::exists(cert)&&certificate_covers(cert,domains))return name;
    if(!options_.acme_enabled)throw std::runtime_error("certificate_missing_or_mismatch_v10:"+name);
    auto command=options_.certbot_command_prefix;
    command.push_back("--cert-name");command.push_back(name);
    for(const auto& domain:domains){command.push_back("-d");command.push_back(domain);}
    command.insert(command.end(),{"--non-interactive","--agree-tos","--register-unsafely-without-email","--keep-until-expiring"});
    if(std::filesystem::exists(cert))command.push_back("--force-renewal");
    run_command(command,300);
    if(!std::filesystem::exists(cert)||!certificate_covers(cert,domains))throw std::runtime_error("certificate_san_mismatch:"+name);
    return name;
}
void NpmPublisherProvider::save_state_locked(){
    std::filesystem::create_directories(options_.state_path.parent_path());
    auto tmp=options_.state_path;tmp+=".tmp";
    {std::ofstream out(tmp,std::ios::trunc);if(!out)throw std::runtime_error("state_write_failed");out<<state_.dump(2)<<'\n';out.flush();if(!out)throw std::runtime_error("state_flush_failed");}
    std::filesystem::permissions(tmp,std::filesystem::perms::owner_read|std::filesystem::perms::owner_write,std::filesystem::perm_options::replace);
    std::filesystem::rename(tmp,options_.state_path);
}
std::string NpmPublisherProvider::render_managed_block(const nlohmann::json& state) const{
    std::ostringstream out; out<<"# CloudIF managed publications BEGIN\n";
    auto pair=[&](const std::string& host,const std::string& cert,const std::string& upstream,const std::string& host_header,bool tenant){
        if(!valid_label(host.substr(0,host.find('.')))||!safe_cert(cert))throw ValidationError("unsafe_render_value");
        out<<"server {\n    listen 80;\n    listen [::]:80;\n    server_name "<<host<<";\n"
           <<"    location ^~ /.well-known/acme-challenge/ { root /data/letsencrypt-acme-challenge; default_type text/plain; }\n"
           <<"    location / { return 301 https://$host$request_uri; }\n}\n"
           <<"server {\n    listen 443 ssl;\n    listen [::]:443 ssl;\n    http2 on;\n    server_name "<<host<<";\n"
           <<"    ssl_certificate /etc/letsencrypt/live/"<<cert<<"/fullchain.pem;\n"
           <<"    ssl_certificate_key /etc/letsencrypt/live/"<<cert<<"/privkey.pem;\n"
           <<"    include conf.d/include/ssl-ciphers.conf;\n"
           <<"    add_header Strict-Transport-Security \"max-age=31536000; includeSubDomains\" always;\n"
           <<"    add_header X-Content-Type-Options nosniff always;\n";
        if(tenant)out<<"    add_header Referrer-Policy strict-origin-when-cross-origin always;\n    add_header Content-Security-Policy \"upgrade-insecure-requests; block-all-mixed-content\" always;\n";
        else out<<"    add_header Content-Security-Policy \"frame-ancestors 'self' https://cloudiff.duckdns.org\" always;\n";
        out<<"    location / {\n        proxy_http_version 1.1;\n        proxy_set_header Host "<<host_header<<";\n"
           <<"        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
           <<"        proxy_set_header X-Forwarded-Proto https;\n        proxy_set_header X-Forwarded-Host $host;\n"
           <<"        proxy_set_header Upgrade $http_upgrade;\n        proxy_set_header Connection \"upgrade\";\n"
           <<"        proxy_pass "<<upstream<<";\n    }\n}\n\n";
    };
    const auto tenants=state.value("tenants",nlohmann::json::object());
    for(auto it=tenants.begin();it!=tenants.end();++it){if(it.key()=="aluno")continue;const auto cert=it.value().value("cert","");pair(it.key()+".cloudiff.duckdns.org",cert,"http://10.62.92.7:8099","$host",true);}
    const auto projects=state.value("projects",nlohmann::json::object());
    std::vector<std::pair<int,std::string>> pkeys;for(auto it=projects.begin();it!=projects.end();++it){try{pkeys.emplace_back(std::stoi(it.key()),it.key());}catch(...){throw ValidationError("invalid_project_state");}}std::sort(pkeys.begin(),pkeys.end());
    for(const auto& [num,key]:pkeys){const auto& p=projects.at(key);const int active=p.value("active_deploy",0);const std::string scert=p.value("stable_cert","");if(active>0&&!scert.empty())pair(std::to_string(num)+".cloudiff.duckdns.org",scert,"http://10.62.91.2:18150","$host",false);const auto versions=p.value("versions",nlohmann::json::object());std::vector<int> deps;for(auto it=versions.begin();it!=versions.end();++it)deps.push_back(std::stoi(it.key()));std::sort(deps.begin(),deps.end());for(int dep:deps){const auto cert=versions.at(std::to_string(dep)).value("cert","");pair(std::to_string(num)+"-d"+std::to_string(dep)+".cloudiff.duckdns.org",cert,"http://10.62.91.2:18150","$host",false);}}
    const auto stages=state.value("stages",nlohmann::json::object());for(auto it=stages.begin();it!=stages.end();++it)pair(it.key()+".cloudiff.duckdns.org",it.value().value("cert",""),"http://10.62.91.2:18150","$host",false);
    const auto aliases=state.value("aliases",nlohmann::json::object());for(auto it=aliases.begin();it!=aliases.end();++it){const auto& a=it.value();const int num=a.value("public_number",0);const int active=a.value("active_deploy",0);pair(it.key()+".cloudiff.duckdns.org",a.value("cert",""),"http://10.62.91.2:18150",std::to_string(num)+".cloudiff.duckdns.org",false);auto versions=a.value("versions",nlohmann::json::object());if(versions.empty()&&a.contains("version_cert")&&active>0)versions[std::to_string(active)]={{"cert",a.value("version_cert","")}};std::vector<int> deps;for(auto v=versions.begin();v!=versions.end();++v)deps.push_back(std::stoi(v.key()));std::sort(deps.begin(),deps.end());for(int dep:deps)pair(std::to_string(dep)+"."+it.key()+".cloudiff.duckdns.org",versions.at(std::to_string(dep)).value("cert",""),"http://10.62.91.2:18150",std::to_string(num)+"-d"+std::to_string(dep)+".cloudiff.duckdns.org",false);}
    out<<"# CloudIF managed publications END\n";return out.str();
}
void NpmPublisherProvider::render_locked(){
    const auto managed=render_managed_block(state_);
    std::filesystem::create_directories(options_.nginx_conf_path.parent_path());
    if(options_.dry_run){
        auto tmp=options_.nginx_conf_path;tmp+=".tmp";
        {std::ofstream out(tmp,std::ios::trunc);if(!out)throw std::runtime_error("nginx_shadow_write_failed");out<<managed;out.flush();if(!out)throw std::runtime_error("nginx_shadow_flush_failed");}
        std::filesystem::permissions(tmp,std::filesystem::perms::owner_read|std::filesystem::perms::owner_write,std::filesystem::perm_options::replace);
        std::filesystem::rename(tmp,options_.nginx_conf_path);return;
    }
    std::ifstream in(options_.nginx_conf_path);if(!in)throw std::runtime_error("nginx_live_open_failed");
    const std::string old((std::istreambuf_iterator<char>(in)),{});
    const std::string begin="# CloudIF managed publications BEGIN",end="# CloudIF managed publications END";
    std::string next=old;const auto b=old.find(begin);const auto e=b==std::string::npos?std::string::npos:old.find(end,b);
    if(b!=std::string::npos&&e!=std::string::npos)next.replace(b,e+end.size()-b,managed);
    else{if(!next.empty()&&next.back()!='\n')next.push_back('\n');next+="\n"+managed+"\n";}
    const auto epoch=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
    auto backup=options_.nginx_conf_path;backup+=".bkp-v2-canary-"+std::to_string(epoch);
    std::filesystem::copy_file(options_.nginx_conf_path,backup,std::filesystem::copy_options::overwrite_existing);
    const auto mode=std::filesystem::status(options_.nginx_conf_path).permissions();
    auto tmp=options_.nginx_conf_path;tmp+=".tmp-v2-canary";
    {std::ofstream out(tmp,std::ios::trunc);if(!out)throw std::runtime_error("nginx_live_write_failed");out<<next;out.flush();if(!out)throw std::runtime_error("nginx_live_flush_failed");}
    std::filesystem::permissions(tmp,mode,std::filesystem::perm_options::replace);std::filesystem::rename(tmp,options_.nginx_conf_path);
    try{run_command(options_.nginx_test_command,30);run_command(options_.nginx_reload_command,30);}
    catch(...){std::filesystem::copy_file(backup,options_.nginx_conf_path,std::filesystem::copy_options::overwrite_existing);try{run_command(options_.nginx_reload_command,30);}catch(...){}throw;}
}
nlohmann::json NpmPublisherProvider::state_snapshot() const{std::scoped_lock lock(mutex_);return state_;}
PublisherResponse NpmPublisherProvider::handle(std::string_view method,std::string_view path,std::string_view presented_token,std::string_view body){
    if(method=="GET"&&path=="/health")return {200,{{"ok",true},{"service","cloudif-npm-publisher"}}};
    if(method!="POST")return {404,{{"ok",false},{"error","not_found"}}};
    if(!constant_time_equal(presented_token,options_.token))return {403,{{"ok",false},{"error","forbidden"}}};
    nlohmann::json payload;try{payload=nlohmann::json::parse(body.empty()?"{}":std::string(body));}catch(const std::exception& e){return {422,{{"ok",false},{"error","JSONDecodeError"},{"detail",error_detail(e)}}};}
    std::scoped_lock lock(mutex_);const auto before=state_;
    try{
        auto version=[&](long long num,long long dep){validate_num(num,999999999,"number");validate_num(dep,999999,"number");auto key=std::to_string(num),dkey=std::to_string(dep);auto& p=state_["projects"][key];if(!p.is_object())p={{"active_deploy",0},{"versions",nlohmann::json::object()}};if(!p.contains("versions")||!p["versions"].is_object())p["versions"]=nlohmann::json::object();std::string cert;if(p["versions"].contains(dkey)&&p["versions"][dkey].is_object())cert=p["versions"][dkey].value("cert","");if(cert.empty())cert=ensure_certificate("cloudif-p"+key+"-d"+dkey,{key+"-d"+dkey+".cloudiff.duckdns.org"});p["versions"][dkey]={{"cert",cert},{"created_at",now_utc()}};return cert;};
        auto alias=[&](long long num,long long dep,const std::string& name){if(!valid_label(name)||std::all_of(name.begin(),name.end(),[](unsigned char c){return std::isdigit(c);}))throw ValidationError("invalid_alias");if(state_["tenants"].contains(name))throw ValidationError("alias_in_use");auto& aliases=state_["aliases"];if(aliases.contains(name)&&aliases[name].value("public_number",0LL)!=num)throw ValidationError("alias_in_use");auto& item=aliases[name];if(!item.is_object())item=nlohmann::json::object();std::string cert=item.value("cert","");if(cert.empty())cert=ensure_certificate("cloudif-alias-"+name,{name+".cloudiff.duckdns.org"});const auto dkey=std::to_string(dep);std::string vcert;if(item.contains("versions")&&item["versions"].contains(dkey))vcert=item["versions"][dkey].value("cert","");if(vcert.empty())vcert=ensure_certificate("cloudif-alias-"+name+"-d"+dkey,{dkey+"."+name+".cloudiff.duckdns.org"});item["public_number"]=num;item["active_deploy"]=dep;item["cert"]=cert;item["versions"][dkey]={{"cert",vcert}};item["updated_at"]=now_utc();return nlohmann::json{{"ok",true},{"alias",name},{"stable_url","https://"+name+".cloudiff.duckdns.org/"},{"version_url","https://"+dkey+"."+name+".cloudiff.duckdns.org/"}};};
        nlohmann::json result;
        if(path=="/version"){
            const auto num=as_int(payload.at("public_number"),"number"),dep=as_int(payload.at("deploy_number"),"number");version(num,dep);result={{"ok",true},{"public_number",num},{"deploy_number",dep},{"version_url","https://"+std::to_string(num)+"-d"+std::to_string(dep)+".cloudiff.duckdns.org/"}};
        }else if(path=="/stage"){
            const auto num=as_int(payload.at("public_number"),"number"),number=as_int(payload.at("number"),"number");validate_num(num,999999999,"stage");validate_num(number,999999,"stage");const std::string stage=payload.value("stage","");char letter=0;if(stage=="preview")letter='w';else if(stage=="homologation")letter='h';else if(stage=="publication")letter='p';else throw ValidationError("invalid_stage");const std::string name=std::to_string(num)+"-"+letter+std::to_string(number)+"-"+stage;auto& item=state_["stages"][name];std::string cert=item.is_object()?item.value("cert",""):"";if(cert.empty())cert=ensure_certificate("cloudif-stage-"+name,{name+".cloudiff.duckdns.org"});item={{"public_number",num},{"stage",stage},{"number",number},{"cert",cert},{"updated_at",now_utc()}};std::string code(1,static_cast<char>(std::toupper(letter)));code+=std::to_string(number);result={{"ok",true},{"public_number",num},{"stage",stage},{"number",number},{"stage_code",code},{"hostname",name+".cloudiff.duckdns.org"},{"url","https://"+name+".cloudiff.duckdns.org/"}};
        }else if(path=="/alias"){
            const auto num=as_int(payload.at("public_number"),"number"),dep=as_int(payload.at("deploy_number"),"number");validate_num(num,999999999,"number");validate_num(dep,999999,"number");result=alias(num,dep,payload.value("alias",""));
        }else if(path=="/publish"){
            const auto num=as_int(payload.at("public_number"),"number"),dep=as_int(payload.at("deploy_number"),"number");validate_num(num,999999999,"number");validate_num(dep,999999,"number");const auto vcert=version(num,dep);auto& p=state_["projects"][std::to_string(num)];std::string scert=p.value("stable_cert","");if(scert.empty())scert=ensure_certificate("cloudif-p"+std::to_string(num),{std::to_string(num)+".cloudiff.duckdns.org"});p["stable_cert"]=scert;p["active_deploy"]=dep;p["versions"][std::to_string(dep)]["cert"]=vcert;const auto alias_name=payload.value("alias","");if(!alias_name.empty())(void)alias(num,dep,alias_name);result={{"ok",true},{"public_number",num},{"deploy_number",dep},{"stable_url","https://"+std::to_string(num)+".cloudiff.duckdns.org/"},{"version_url","https://"+std::to_string(num)+"-d"+std::to_string(dep)+".cloudiff.duckdns.org/"}};
        }else if(path=="/unpublish"){
            const auto num=as_int(payload.at("public_number"),"number");auto key=std::to_string(num);const bool removed=state_["projects"].erase(key)>0;nlohmann::json removed_aliases=nlohmann::json::array();std::vector<std::string> doomed;for(auto it=state_["aliases"].begin();it!=state_["aliases"].end();++it)if(it.value().value("public_number",0LL)==num)doomed.push_back(it.key());for(const auto& name:doomed){state_["aliases"].erase(name);removed_aliases.push_back(name);}result={{"ok",true},{"public_number",num},{"removed",removed},{"removed_aliases",removed_aliases}};
        }else if(path=="/tenant"){
            const std::string tenant=payload.value("tenant","");if(!valid_label(tenant))throw ValidationError("invalid_tenant");auto& item=state_["tenants"][tenant];std::string cert=item.is_object()?item.value("cert",""):"";if(cert.empty())cert=ensure_certificate("cloudif-tenant-"+tenant,{tenant+".cloudiff.duckdns.org"});item={{"cert",cert},{"updated_at",now_utc()}};result={{"ok",true},{"tenant",tenant},{"hostname",tenant+".cloudiff.duckdns.org"},{"url","https://"+tenant+".cloudiff.duckdns.org/"},{"certificate",cert}};
        }else if(path=="/tenant/delete"){
            const std::string tenant=payload.value("tenant","");if(!valid_label(tenant))throw ValidationError("invalid_tenant");std::string cert;if(state_["tenants"].contains(tenant))cert=state_["tenants"][tenant].value("cert","");const bool removed=state_["tenants"].erase(tenant)>0;result={{"ok",true},{"tenant",tenant},{"removed",removed},{"certificate_preserved",cert}};
        }else return {404,{{"ok",false},{"error","not_found"}}};
        render_locked();save_state_locked();return {200,std::move(result)};
    }catch(const ValidationError& e){state_=before;return {422,{{"ok",false},{"error","ValueError"},{"detail",error_detail(e)}}};}
    catch(const std::exception& e){state_=before;return {422,{{"ok",false},{"error","RuntimeError"},{"detail",error_detail(e)}}};}
}
PublisherOptions publisher_options_from_environment(){PublisherOptions o;o.bind_address=env_or("CLOUDIFF_PUBLISHER_BIND","127.0.0.1");o.port=static_cast<unsigned short>(std::clamp(env_int("CLOUDIFF_PUBLISHER_PORT",18260),1,65535));o.token=env_or("CLOUDIFF_PUBLISHER_TOKEN");o.state_path=env_or("CLOUDIFF_PUBLISHER_STATE","/var/lib/cloudiff-v2/publisher-shadow/state.json");o.nginx_conf_path=env_or("CLOUDIFF_PUBLISHER_NGINX_CONF","/var/lib/cloudiff-v2/publisher-shadow/http.conf");o.dry_run=env_bool("CLOUDIFF_PUBLISHER_DRY_RUN",true);o.acme_enabled=env_bool("CLOUDIFF_PUBLISHER_ACME_ENABLED",false);o.certificate_root=env_or("CLOUDIFF_PUBLISHER_CERT_ROOT","/srv/cloudif/proxy/npm/letsencrypt/live");return o;}
int run_npm_publisher_server(const PublisherOptions& options){
    NpmPublisherProvider provider(options);asio::io_context io;tcp::acceptor acceptor(io,{asio::ip::make_address(options.bind_address),options.port});acceptor.set_option(asio::socket_base::reuse_address(true));
    for(;;){tcp::socket socket(io);acceptor.accept(socket);std::thread([&provider,s=std::move(socket)]() mutable {try{beast::flat_buffer buffer;http::request_parser<http::string_body> parser;parser.body_limit(1024*1024);http::read(s,buffer,parser);auto req=parser.release();std::string target(req.target());if(auto q=target.find('?');q!=std::string::npos)target.resize(q);const auto token_view=req["X-CloudIF-Token"];const std::string token(token_view.data(),token_view.size());auto r=provider.handle(req.method_string(),target,token,req.body());http::response<http::string_body> res{static_cast<http::status>(r.status),req.version()};res.set(http::field::content_type,"application/json");res.keep_alive(false);res.body()=r.body.dump();res.prepare_payload();http::write(s,res);beast::error_code ec;s.shutdown(tcp::socket::shutdown_send,ec);}catch(const std::exception&){}}).detach();}
}
}
