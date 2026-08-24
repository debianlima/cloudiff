#pragma once
#include "cloudiff/node_identity.hpp"
#include <nlohmann/json.hpp>
#include <string>
#include <vector>
namespace cloudiff {
[[nodiscard]] nlohmann::json make_node_observed_event(const NodeIdentity& identity,const std::string& role,const std::vector<std::string>& capabilities={"inventory","health","telemetry-host"});
}
