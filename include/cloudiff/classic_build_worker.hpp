#pragma once
#include "cloudiff/job_engine.hpp"
#include <functional>
#include <nlohmann/json.hpp>
#include <string>

namespace cloudiff {
enum class ClassicBuildOutcome { succeeded, terminal_failed };
struct ClassicBuildExecution final {
    ClassicBuildOutcome outcome{ClassicBuildOutcome::terminal_failed};
    nlohmann::json result;
    std::string error;
};
using ClassicWorkspaceValidator = std::function<nlohmann::json(const std::string&,const std::string&,const std::string&)>;
using ClassicArtifactBuilder = std::function<nlohmann::json(const std::string&,const std::string&,const std::string&,const std::string&)>;
struct ClassicBuildWorkerOptions final {
    std::string workspace_host{"127.0.0.1"};
    unsigned short workspace_port{18206};
    std::string workspace_token;
    std::string artifact_host{"10.62.91.3"};
    unsigned short artifact_port{80};
    std::string artifact_host_header{"cloudif-artifact-executor-v2.internal"};
    std::string artifact_token;
    std::string attestation_key;
    ClassicWorkspaceValidator workspace_validator;
    ClassicArtifactBuilder artifact_builder;
};
class ClassicBuildWorker final {
public:
    explicit ClassicBuildWorker(ClassicBuildWorkerOptions options);
    [[nodiscard]] ClassicBuildExecution execute(const DurableJob& job) const;
private:
    ClassicBuildWorkerOptions options_;
};
[[nodiscard]] ClassicBuildWorkerOptions classic_build_worker_options_from_environment();
}
