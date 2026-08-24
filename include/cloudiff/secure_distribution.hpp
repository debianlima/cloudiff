#pragma once
#include <cstdint>
#include <functional>
#include <map>
#include <nlohmann/json.hpp>
#include <string>
#include <string_view>

namespace cloudiff {
struct SecureDistributionResponse final {
    int status{500};
    std::string body;
    std::string content_type{"application/json"};
    std::map<std::string,std::string> headers;
};
struct SecureDistributionOptions final {
    std::string bind_address{"10.62.91.3"};
    unsigned short port{18240};
    std::string catalog_path{"/opt/cloudiff-v2/secure-distribution-current/config/secure-distribution-v1.json"};
    std::string capabilities_path{"/etc/cloudiff-v2/secure-distribution-capabilities.json"};
};
class SecureDistributionProvider final {
public:
    SecureDistributionProvider(nlohmann::json catalog,nlohmann::json capabilities,std::function<std::int64_t()> clock={});
    [[nodiscard]] SecureDistributionResponse handle(std::string_view method,std::string_view path,std::string_view authorization,std::string_view audience,std::string_view expected_generation={}) const;
private:
    nlohmann::json catalog_;
    nlohmann::json capabilities_;
    std::function<std::int64_t()> clock_;
};
[[nodiscard]] SecureDistributionOptions secure_distribution_options_from_environment();
int run_secure_distribution_server(const SecureDistributionOptions& options);
}
