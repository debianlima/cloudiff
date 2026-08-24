#pragma once
#include <nlohmann/json.hpp>
#include <functional>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace cloudiff {
enum class RuntimeProfile { PREVIEW, TEST, HOMOLOGATION, CANARY, PRODUCTION, SEALED };
struct RuntimeCommandResult final { int exit_code{0}; std::string stdout_text; std::string stderr_text; };
using RuntimeCommandRunner = std::function<RuntimeCommandResult(const std::vector<std::string>&,int)>;
struct RuntimeExecutorOptions final {
    std::string bind_address{"127.0.0.1"};
    unsigned short port{18232};
    std::string token;
    bool effects_enabled{false};
    RuntimeCommandRunner command_runner;
};
struct RuntimeResponse final { int status{500}; nlohmann::json body; };
[[nodiscard]] std::optional<RuntimeProfile> runtime_profile_from_string(std::string_view value);
[[nodiscard]] std::string runtime_profile_name(RuntimeProfile profile);
[[nodiscard]] nlohmann::json runtime_profile_policy(RuntimeProfile profile);
class RuntimeExecutor final {
public:
    explicit RuntimeExecutor(RuntimeExecutorOptions options);
    [[nodiscard]] RuntimeResponse handle(std::string_view method,std::string_view path,std::string_view authorization,std::string_view body) const;
private:
    RuntimeExecutorOptions options_;
};
[[nodiscard]] RuntimeExecutorOptions runtime_executor_options_from_environment();
int run_runtime_executor_server(const RuntimeExecutorOptions& options);
}
