#include "cloudiff/heartbeat.hpp"
#include "cloudiff/telemetry.hpp"
#include <sys/sysinfo.h>
#include <sys/utsname.h>
#include <unistd.h>
#include <uuid/uuid.h>
#include <chrono>
#include <filesystem>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace cloudiff {
namespace {
std::string uuid_string() {
    uuid_t value{}; uuid_generate_random(value); char out[37]{}; uuid_unparse_lower(value, out); return out;
}
std::string now_utc() {
    const auto now=std::chrono::system_clock::now(); const auto tt=std::chrono::system_clock::to_time_t(now);
    std::tm tm{}; gmtime_r(&tt,&tm); std::ostringstream out; out<<std::put_time(&tm,"%Y-%m-%dT%H:%M:%SZ"); return out.str();
}
long long revision_now() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::system_clock::now().time_since_epoch()).count();
}
std::string host() { char b[256]{}; if (::gethostname(b,sizeof(b)-1)!=0) throw std::runtime_error("gethostname failed"); return b; }
}
 nlohmann::json make_node_observed_event(const NodeIdentity& identity,const std::string& role,const std::vector<std::string>& capabilities) {
    struct utsname un{}; if (::uname(&un)!=0) throw std::runtime_error("uname failed");
    const auto ts=now_utc(); const auto telemetry=collect_telemetry();
    nlohmann::json payload={{"node_id",identity.value()},{"hostname",host()},{"role",role},{"observed_at",ts},
      {"capabilities",capabilities},{"revision",revision_now()},
      {"system",{{"kernel",un.release},{"machine",un.machine},{"uptime_seconds",telemetry.at("host").at("uptime_seconds")},
       {"ram_total_bytes",telemetry.at("host").at("ram_total_bytes")},{"ram_free_bytes",telemetry.at("host").at("ram_available_bytes")},
       {"root_capacity_bytes",telemetry.at("host").at("root_capacity_bytes")},{"root_available_bytes",telemetry.at("host").at("root_available_bytes")}}},
      {"telemetry",telemetry}};
    return {{"event_id",uuid_string()},{"type","node.observed"},{"occurred_at",ts},{"producer","cloudiff-agent"},
            {"resource_id",identity.value()},{"trace_id",uuid_string()},{"payload",std::move(payload)}};
}
}
