#include <arpa/inet.h>
#include <curl/curl.h>
#include <fcntl.h>
#include <ifaddrs.h>
#include <netdb.h>
#include <net/if.h>
#include <nlohmann/json.hpp>
#include <sys/socket.h>
#include <sys/statvfs.h>
#include <unistd.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <csignal>
#include <cstring>
#include <cstdlib>
#include <cstdint>
#include <fstream>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <map>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

using json = nlohmann::json;
static std::atomic<bool> running{true};
static int server_fd=-1;

static std::string read_text(const std::string& p) {
    std::ifstream f(p);
    std::ostringstream s;
    if (f) s << f.rdbuf();
    std::string out=s.str();
    while(!out.empty() && (out.back()=='\n'||out.back()=='\r')) out.pop_back();
    return out;
}
static long long read_ll(const std::string& p) { try { return std::stoll(read_text(p)); } catch (...) { return 0; } }
static std::string hostname() { char b[256]{}; return gethostname(b,sizeof(b)-1)==0 ? b : "unknown"; }
static std::string now_iso() {
    auto t=std::time(nullptr); std::tm tm{}; localtime_r(&t,&tm); char b[64]{};
    std::strftime(b,sizeof(b),"%Y-%m-%dT%H:%M:%S%z",&tm); return b;
}
static json memory_summary() {
    std::ifstream f("/proc/meminfo"); std::map<std::string,long long> v; std::string k,unit; long long n;
    while(f>>k>>n>>unit){ if(!k.empty()&&k.back()==':') k.pop_back(); v[k]=n*1024; }
    long long total=v["MemTotal"], free=v["MemFree"], avail=v["MemAvailable"], buffers=v["Buffers"], cached=v["Cached"]+v["SReclaimable"];
    long long used=total-avail; // close to modern free(1) semantics
    long long buff_cache=buffers+cached;
    return {{"total",total},{"used",used},{"free",free},{"buff_cache",buff_cache},{"available",avail}};
}
static json root_disk() {
    struct statvfs s{}; if(statvfs("/",&s)!=0) return json::object();
    unsigned long long size=(unsigned long long)s.f_blocks*s.f_frsize;
    unsigned long long avail=(unsigned long long)s.f_bavail*s.f_frsize;
    unsigned long long freeall=(unsigned long long)s.f_bfree*s.f_frsize;
    unsigned long long used=size-freeall;
    std::string source,fs;
    std::ifstream m("/proc/mounts"); std::string src,target,fstype,opts; int a,b;
    while(m>>src>>target>>fstype>>opts>>a>>b){ if(target=="/"){source=src;fs=fstype;break;} }
    unsigned long long denom=used+avail; int pct=denom ? int((used*100 + denom-1)/denom) : 0;
    return {{"source",source},{"fstype",fs},{"size",size},{"used",used},{"avail",avail},{"pcent",std::to_string(pct)+"%"},{"target","/"}};
}
static bool physical_block_device(const std::filesystem::path& p) {
    const auto name=p.filename().string();
    if(name.rfind("loop",0)==0||name.rfind("ram",0)==0||name.rfind("zram",0)==0||name.rfind("dm-",0)==0||name.rfind("md",0)==0||name.rfind("sr",0)==0||name.rfind("fd",0)==0) return false;
    std::error_code ec;
    return std::filesystem::exists(p/"device",ec) && !ec;
}
static json storage_summary() {
    json disks=json::array(); unsigned long long total=0;
    std::error_code ec;
    for(const auto& e: std::filesystem::directory_iterator("/sys/block",ec)) {
        if(ec) break;
        if(!physical_block_device(e.path())) continue;
        const auto sectors=read_ll((e.path()/"size").string());
        if(sectors<=0) continue;
        const auto size=static_cast<unsigned long long>(sectors)*512ULL;
        disks.push_back({{"name",e.path().filename().string()},{"size",size}}); total+=size;
    }
    std::sort(disks.begin(),disks.end(),[](const json&a,const json&b){return a["name"]<b["name"];});
    return {{"physical_total",total},{"disk_count",disks.size()},{"physical_disks",disks}};
}

static json network_summary() {
    json interfaces=json::array(); unsigned long long rxT=0,txT=0;
    for(const auto& e: std::filesystem::directory_iterator("/sys/class/net")) {
        std::string n=e.path().filename().string();
        if(n=="lo"||n.rfind("docker",0)==0||n.rfind("br-",0)==0||n.rfind("veth",0)==0||n.rfind("virbr",0)==0||n.rfind("tun",0)==0||n.rfind("tap",0)==0) continue;
        std::string state=read_text(e.path().string()+"/operstate"); if(state!="up"&&state!="unknown") continue;
        auto rx=read_ll(e.path().string()+"/statistics/rx_bytes"), tx=read_ll(e.path().string()+"/statistics/tx_bytes");
        interfaces.push_back({{"name",n},{"rx_bytes",rx},{"tx_bytes",tx}}); rxT+=rx;txT+=tx;
    }
    std::sort(interfaces.begin(), interfaces.end(), [](const json&a,const json&b){return a["name"]<b["name"];});
    return {{"rx_bytes",rxT},{"tx_bytes",txT},{"interfaces",interfaces}};
}
static size_t curl_write(char* p,size_t s,size_t n,void* u){ static_cast<std::string*>(u)->append(p,s*n); return s*n; }
static json docker_summary() {
    static std::mutex mu; static json cached; static auto last=std::chrono::steady_clock::time_point{};
    { std::lock_guard<std::mutex> g(mu); auto now=std::chrono::steady_clock::now();
      if(!cached.is_null() && now-last < std::chrono::seconds(2)) return cached; }
    CURL* c=curl_easy_init(); if(!c) return {{"available",false},{"containers",json::array()}};
    std::string body; curl_easy_setopt(c,CURLOPT_UNIX_SOCKET_PATH,"/var/run/docker.sock");
    curl_easy_setopt(c,CURLOPT_URL,"http://localhost/containers/json?all=1"); curl_easy_setopt(c,CURLOPT_WRITEFUNCTION,curl_write); curl_easy_setopt(c,CURLOPT_WRITEDATA,&body); curl_easy_setopt(c,CURLOPT_TIMEOUT_MS,1500L);
    CURLcode rc=curl_easy_perform(c); long code=0; curl_easy_getinfo(c,CURLINFO_RESPONSE_CODE,&code); curl_easy_cleanup(c);
    if(rc!=CURLE_OK||code!=200) return {{"available",false},{"containers",json::array()}};
    try {
        auto a=json::parse(body); json out=json::array();
        for(auto &x:a){ std::string name=""; if(x.contains("Names")&&!x["Names"].empty()){name=x["Names"][0].get<std::string>();if(!name.empty()&&name[0]=='/')name.erase(0,1);} out.push_back({{"name",name},{"image",x.value("Image","")},{"status",x.value("Status","")}}); if(out.size()>=200)break; }
        json result={{"available",true},{"count",a.size()},{"containers",out}};
        { std::lock_guard<std::mutex> g(mu); cached=result; last=std::chrono::steady_clock::now(); }
        return result;
    } catch(...) { return {{"available",false},{"containers",json::array()}}; }
}
static int prefix_len(const sockaddr* mask) {
    if(!mask) return 0;
    int bits=0;
    if(mask->sa_family==AF_INET){ auto v=ntohl(((sockaddr_in*)mask)->sin_addr.s_addr); bits=__builtin_popcount(v); }
    else if(mask->sa_family==AF_INET6){ auto &a=((sockaddr_in6*)mask)->sin6_addr; for(unsigned char c: a.s6_addr) bits+=__builtin_popcount((unsigned)c); }
    return bits;
}
static std::string ip_summary() {
    std::map<std::string,std::vector<std::string>> addrs; ifaddrs* head=nullptr;
    if(getifaddrs(&head)==0){
        for(auto* p=head;p;p=p->ifa_next){ if(!p->ifa_addr) continue; int fam=p->ifa_addr->sa_family; if(fam!=AF_INET&&fam!=AF_INET6) continue;
            char h[NI_MAXHOST]{}; socklen_t len=fam==AF_INET?sizeof(sockaddr_in):sizeof(sockaddr_in6);
            if(getnameinfo(p->ifa_addr,len,h,sizeof(h),nullptr,0,NI_NUMERICHOST)==0) { std::string addr(h); auto pct=addr.find("%"); if(pct!=std::string::npos) addr.resize(pct); addrs[p->ifa_name].push_back(addr+"/"+std::to_string(prefix_len(p->ifa_netmask))); }
        } freeifaddrs(head);
    }
    std::vector<std::string> names; for(const auto&e:std::filesystem::directory_iterator("/sys/class/net")) names.push_back(e.path().filename().string()); std::sort(names.begin(),names.end());
    std::ostringstream o; for(const auto& n:names){ std::string state=read_text("/sys/class/net/"+n+"/operstate"); std::transform(state.begin(),state.end(),state.begin(),::toupper);
        o<<std::left<<std::setw(17)<<n<<std::setw(15)<<state; auto it=addrs.find(n); if(it!=addrs.end()) for(auto &a:it->second)o<<a<<" "; o<<"\n"; }
    auto out=o.str(); if(!out.empty())out.pop_back(); return out;
}
static json metrics() {
    return {{"ok",true},{"host",hostname()},{"time",now_iso()},{"memory",memory_summary()},{"disk_root",root_disk()},{"storage",storage_summary()},
            {"loadavg",read_text("/proc/loadavg")},{"uptime",read_text("/proc/uptime")},{"ips",ip_summary()},
            {"network",network_summary()},{"docker",docker_summary()}};
}
static std::string response(int code,const json& j){ std::string b=j.dump(2); std::ostringstream o; o<<"HTTP/1.1 "<<code<<(code==200?" OK":" Not Found")<<"\r\nContent-Type: application/json; charset=utf-8\r\nCache-Control: no-store\r\nContent-Length: "<<b.size()<<"\r\nConnection: close\r\n\r\n"<<b; return o.str(); }
static void client(int fd){
    char b[4096]{}; ssize_t n=recv(fd,b,sizeof(b)-1,0); if(n<=0){close(fd);return;} std::string req(b,n), path="/"; auto a=req.find(' '), z=a==std::string::npos?a:req.find(' ',a+1); if(a!=std::string::npos&&z!=std::string::npos) path=req.substr(a+1,z-a-1);
    json j; int code=200; if(path=="/"||path=="/health") j={{"ok",true},{"service","cloudif-node-metrics"},{"host",hostname()}}; else if(path.rfind("/metrics",0)==0) j=metrics(); else {code=404;j={{"ok",false},{"error","not_found"}};}
    auto r=response(code,j); send(fd,r.data(),r.size(),MSG_NOSIGNAL); close(fd);
}
int main(int argc,char**argv){
    if(argc>1 && std::string(argv[1])=="--self-test") {
        const auto m=metrics();
        std::cout<<m.dump(2)<<"\n";
        const bool ok=m.value("ok",false)
            && m.value("memory",json::object()).value("total",0ULL)>0
            && m.value("disk_root",json::object()).value("size",0ULL)>0
            && m.value("storage",json::object()).value("physical_total",0ULL)>0
            && m.value("storage",json::object()).value("disk_count",0ULL)>0;
        return ok?0:3;
    }
    const char* env_host=std::getenv("CLOUDIF_METRICS_HOST");
    const char* env_port=std::getenv("CLOUDIF_METRICS_PORT");
    std::string host=env_host&&*env_host?env_host:"127.0.0.1";
    int port=env_port&&*env_port?std::stoi(env_port):18196;
    if(argc>1) {
        std::string a1=argv[1];
        if(a1.find('.')!=std::string::npos || a1=="0.0.0.0" || a1=="localhost") { host=a1; if(argc>2) port=std::stoi(argv[2]); }
        else port=std::stoi(a1);
    }
    curl_global_init(CURL_GLOBAL_DEFAULT); auto stop=[](int){ running=false; if(server_fd>=0){ ::shutdown(server_fd,SHUT_RDWR); ::close(server_fd); server_fd=-1; } }; signal(SIGTERM,stop); signal(SIGINT,stop);
    if(port < 1 || port > 65535){std::cerr<<"invalid port\n";return 2;}
    int s=socket(AF_INET,SOCK_STREAM,0), yes=1; server_fd=s; setsockopt(s,SOL_SOCKET,SO_REUSEADDR,&yes,sizeof(yes)); sockaddr_in a{};a.sin_family=AF_INET;a.sin_port=htons(static_cast<std::uint16_t>(port));
    if(inet_pton(AF_INET,host.c_str(),&a.sin_addr)!=1){std::cerr<<"invalid bind host\n";return 2;}
    if(bind(s,(sockaddr*)&a,sizeof(a))||listen(s,128)){perror("bind/listen");return 2;} std::cerr<<"cloudif-node-metrics-cpp listening "<<host<<":"<<port<<"\n";
    while(running){ int c=accept(s,nullptr,nullptr); if(c<0){if(errno==EINTR)continue;break;} std::thread(client,c).detach(); }
    if(server_fd>=0) close(server_fd);
    server_fd=-1;
    curl_global_cleanup();
    return 0;
}
