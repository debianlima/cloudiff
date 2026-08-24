#pragma once
#include <atomic>
#include <filesystem>
#include <functional>
#include <mutex>
#include <nlohmann/json.hpp>
#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace cloudiff {
struct ArtifactCommandResult final {
    int exit_code{0};
    std::string stdout_text;
    std::string stderr_text;
};
using ArtifactCommandRunner = std::function<ArtifactCommandResult(const std::vector<std::string>&, int)>;
struct ArtifactArchive final {
    std::vector<unsigned char> bytes;
    std::string sha256;
};
using ArtifactArchiveFetcher = std::function<ArtifactArchive(const std::string&, const std::string&, const std::string&)>;
struct ArtifactEngineOptions final {
    std::string bind_address{"127.0.0.1"};
    unsigned short port{18226};
    std::string token;
    std::string classic_token;
    std::filesystem::path artifact_root{"/var/lib/cloudiff-v2/artifact-shadow"};
    std::filesystem::path scanner_cache{"/srv/cloudif/scanners/trivy-cache"};
    std::string base_image{"cgr.dev/chainguard/nginx@sha256:e4ff957080737c90a9ecfeaa40e3d19ea9d687e9cacda2f2a031c75ffcdd72b7"};
    std::string syft_image;
    std::string trivy_image;
    std::string tag_prefix{"cloudiff-v2-shadow-static"};
    std::unordered_map<std::string,std::filesystem::path> static_sites;
    int max_concurrent_builds{1};
    ArtifactCommandRunner command_runner;
    ArtifactArchiveFetcher archive_fetcher;
    std::string forja_host{"10.62.91.2"};
    unsigned short forja_port{18095};
    std::string forja_token;
    std::filesystem::path toolchain_catalog{"/opt/cloudiff-v2/artifact-shadow-current/config/toolchain-catalog-v2.json"};
    std::filesystem::path signing_key{"/etc/cloudiff-v2/artifact-signing-ed25519.pem"};
    std::filesystem::path signing_public_key{"/etc/cloudiff-v2/artifact-signing-ed25519.pub.pem"};
};
struct ArtifactEngineResponse final {
    int status{500};
    nlohmann::json body;
};
class ArtifactEngine final {
public:
    explicit ArtifactEngine(ArtifactEngineOptions options);
    [[nodiscard]] ArtifactEngineResponse handle(std::string_view method,
                                                std::string_view path,
                                                std::string_view authorization,
                                                std::string_view body);
private:
    ArtifactEngineOptions options_;
    std::atomic<int> active_builds_{0};
    std::mutex in_flight_mutex_;
    std::unordered_set<std::string> in_flight_;
    [[nodiscard]] ArtifactEngineResponse build_static(const nlohmann::json& request);
    [[nodiscard]] ArtifactEngineResponse validate_toolchain_archive(const nlohmann::json& request);
    [[nodiscard]] ArtifactEngineResponse build_toolchain_bundle(const nlohmann::json& request);
    [[nodiscard]] ArtifactEngineResponse build_multiservice_bundle(const nlohmann::json& request);
    [[nodiscard]] std::filesystem::path result_path(std::string_view build_id) const;
};
[[nodiscard]] ArtifactEngineOptions artifact_engine_options_from_environment();
[[nodiscard]] ArtifactCommandResult run_artifact_command(const std::vector<std::string>& command,int timeout_seconds);
int run_artifact_engine_server(const ArtifactEngineOptions& options);
}
