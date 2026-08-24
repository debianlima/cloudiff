#include "cloudiff/telemetry.hpp"
#include <cassert>
#include <string>
int main(){cloudiff::TelemetryOptions o;o.containers_enabled=false;auto t=cloudiff::collect_telemetry(o);assert(t["version"]==1);assert(t["hierarchy"]=="environment>node>container>service");assert(t["host"]["cpu_count"].get<int>()>=1);assert(t["host"]["ram_total_bytes"].get<unsigned long long>()>0);assert(t["containers"]["status"]=="disabled");assert(t["containers"]["items"].empty());assert(t.dump().find("password")==std::string::npos);return 0;}
