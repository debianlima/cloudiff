#pragma once
#include <nlohmann/json.hpp>
#include <string>
namespace cloudiff {
struct TelemetryOptions {
    std::string cadvisor_host{"127.0.0.1"};
    unsigned short cadvisor_port{18081};
    bool containers_enabled{true};
    std::size_t max_containers{256};
};
[[nodiscard]] nlohmann::json collect_telemetry(const TelemetryOptions& options={});
}
