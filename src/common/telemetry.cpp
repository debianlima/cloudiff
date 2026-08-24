#include "cloudiff/telemetry.hpp"
#include <boost/asio.hpp>
#include <boost/beast.hpp>
#include <sys/sysinfo.h>
#include <unistd.h>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <string>
#include <vector>

namespace cloudiff {
namespace {
std::string now_utc(){const auto now=std::chrono::system_clock::now();const auto tt=std::chrono::system_clock::to_time_t(now);std::tm tm{};gmtime_r(&tt,&tm);std::ostringstream out;out<<std::put_time(&tm,"%Y-%m-%dT%H:%M:%SZ");return out.str();}
std::array<double,3> loadavg(){std::ifstream in("/proc/loadavg");std::array<double,3> a{0,0,0};in>>a[0]>>a[1]>>a[2];return a;}
std::uint64_t mem_available(){std::ifstream in("/proc/meminfo");std::string key,unit;std::uint64_t value=0;while(in>>key>>value>>unit){if(key=="MemAvailable:")return value*1024ULL;}return 0;}
std::string cadvisor_body(const TelemetryOptions& o){namespace asio=boost::asio;namespace beast=boost::beast;namespace http=beast::http;using tcp=asio::ip::tcp;asio::io_context io;tcp::resolver resolver(io);beast::tcp_stream stream(io);stream.expires_after(std::chrono::seconds(2));stream.connect(resolver.resolve(o.cadvisor_host,std::to_string(o.cadvisor_port)));http::request<http::empty_body> req{http::verb::get,"/api/v1.3/subcontainers",11};req.set(http::field::host,o.cadvisor_host);req.set(http::field::user_agent,"CloudIFF-Agent-Telemetry/1");http::write(stream,req);beast::flat_buffer buffer;http::response_parser<http::string_body> parser;parser.body_limit(8*1024*1024);http::read(stream,buffer,parser);auto res=parser.release();beast::error_code ec;stream.socket().shutdown(tcp::socket::shutdown_both,ec);if(res.result()!=http::status::ok)throw std::runtime_error("cadvisor_http_"+std::to_string(res.result_int()));return res.body();}
nlohmann::json containers(const TelemetryOptions& o){nlohmann::json out={{"status",o.containers_enabled?"unavailable":"disabled"},{"source","cadvisor-local"},{"items",nlohmann::json::array()},{"truncated",false}};if(!o.containers_enabled)return out;try{auto doc=nlohmann::json::parse(cadvisor_body(o));if(!doc.is_array())return out;std::size_t count=0;for(const auto& c:doc){if(count>=o.max_containers){out["truncated"]=true;break;}const auto name=c.value("name","");if(name=="/"||name.empty())continue;std::string id=c.value("id","");if(id.empty())id=name;double cpu=0;std::uint64_t mem=0,rx=0,tx=0;const auto& stats=c.contains("stats")&&c["stats"].is_array()&&!c["stats"].empty()?c["stats"].back():nlohmann::json::object();if(stats.contains("cpu"))cpu=stats["cpu"].value("usage",nlohmann::json::object()).value("total",0.0)/1e9;if(stats.contains("memory"))mem=stats["memory"].value("usage",0ULL);if(stats.contains("network")){for(const auto& iface:stats["network"].value("interfaces",nlohmann::json::array())){rx+=iface.value("rx_bytes",0ULL);tx+=iface.value("tx_bytes",0ULL);}}out["items"].push_back({{"name",name},{"id",id},{"cpu_usage_seconds",cpu},{"memory_usage_bytes",mem},{"network_rx_bytes",rx},{"network_tx_bytes",tx}});++count;}out["status"]="available";}catch(...){ }return out;}
}
nlohmann::json collect_telemetry(const TelemetryOptions& o){struct sysinfo si{};if(::sysinfo(&si)!=0)throw std::runtime_error("sysinfo failed");const auto fs=std::filesystem::space("/");const auto l=loadavg();return {{"version",1},{"hierarchy","environment>node>container>service"},{"collected_at",now_utc()},{"host",{{"cpu_count",static_cast<int>(std::max<long>(1,::sysconf(_SC_NPROCESSORS_ONLN)))},{"load1",l[0]},{"load5",l[1]},{"load15",l[2]},{"ram_total_bytes",static_cast<std::uint64_t>(si.totalram)*si.mem_unit},{"ram_available_bytes",mem_available()},{"root_capacity_bytes",fs.capacity},{"root_available_bytes",fs.available},{"uptime_seconds",static_cast<std::uint64_t>(std::max<long>(0,si.uptime))},{"agent_version","0.36.0"}}},{"containers",containers(o)}};}
}
