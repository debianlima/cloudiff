#pragma once
#include <nlohmann/json.hpp>
#include <string>
namespace cloudiff {
struct AdminObservabilityResponse { int status{500}; nlohmann::json body=nlohmann::json::object(); };
struct AdminObservabilityOptions {
    std::string bind_address{"127.0.0.1"};
    unsigned short port{18260};
    std::string token;
    std::string postgres_conninfo;
};
class AdminObservability final {
public:
    explicit AdminObservability(AdminObservabilityOptions options);
    [[nodiscard]] AdminObservabilityResponse handle(const std::string& method,const std::string& target,const std::string& authorization,const std::string& body) const;
private: AdminObservabilityOptions options_;
};
[[nodiscard]] AdminObservabilityOptions admin_observability_options_from_environment();
int run_admin_observability_server(const AdminObservabilityOptions& options);
}
