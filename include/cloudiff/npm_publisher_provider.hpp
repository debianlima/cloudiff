#pragma once
#include <filesystem>
#include <mutex>
#include <nlohmann/json.hpp>
#include <string>
#include <string_view>
#include <vector>

namespace cloudiff {
struct PublisherOptions final {
    std::string bind_address{"127.0.0.1"};
    unsigned short port{18260};
    std::string token;
    std::filesystem::path state_path{"/var/lib/cloudiff-v2/publisher-shadow/state.json"};
    std::filesystem::path nginx_conf_path{"/var/lib/cloudiff-v2/publisher-shadow/http.conf"};
    bool dry_run{true};
    bool acme_enabled{false};
    std::filesystem::path certificate_root{"/srv/cloudif/proxy/npm/letsencrypt/live"};
    std::vector<std::string> certbot_command_prefix{"docker","exec","cloudif-nginx-proxy-manager","certbot","certonly","--webroot","-w","/data/letsencrypt-acme-challenge"};
    std::vector<std::string> nginx_test_command{"docker","exec","cloudif-nginx-proxy-manager","nginx","-t"};
    std::vector<std::string> nginx_reload_command{"docker","exec","cloudif-nginx-proxy-manager","nginx","-s","reload"};
};
struct PublisherResponse final {
    int status{500};
    nlohmann::json body;
};
class NpmPublisherProvider final {
public:
    explicit NpmPublisherProvider(PublisherOptions options);
    [[nodiscard]] PublisherResponse handle(std::string_view method,
                                           std::string_view path,
                                           std::string_view presented_token,
                                           std::string_view body);
    [[nodiscard]] nlohmann::json state_snapshot() const;
    [[nodiscard]] std::string render_managed_block(const nlohmann::json& state) const;
private:
    PublisherOptions options_;
    mutable std::mutex mutex_;
    mutable std::mutex certificate_mutex_;
    nlohmann::json state_;
    [[nodiscard]] std::string ensure_certificate(const std::string& name, const std::vector<std::string>& domains) const;
    void save_state_locked();
    void render_locked();
};
[[nodiscard]] PublisherOptions publisher_options_from_environment();
int run_npm_publisher_server(const PublisherOptions& options);
}
