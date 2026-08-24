#pragma once
#include <functional>
#include <nlohmann/json.hpp>
#include <string>
#include <string_view>

namespace cloudiff {
struct BuildBrokerOptions final {
    std::string bind_address{"127.0.0.1"};
    unsigned short port{18221};
    std::string token;
    std::string postgres_conninfo;
    std::string runtime_host{"127.0.0.1"};
    unsigned short runtime_port{18212};
    std::function<nlohmann::json(const std::string&)> plan_fetcher;
};
struct BuildBrokerResponse final {
    int status{500};
    nlohmann::json body;
};
class BuildBroker final {
public:
    explicit BuildBroker(BuildBrokerOptions options);
    [[nodiscard]] BuildBrokerResponse handle(std::string_view method,
                                             std::string_view path,
                                             std::string_view authorization,
                                             std::string_view body) const;
private:
    BuildBrokerOptions options_;
};
[[nodiscard]] BuildBrokerOptions build_broker_options_from_environment();
int run_build_broker_server(const BuildBrokerOptions& options);
}
