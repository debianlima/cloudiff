#include "cloudiff/reconciliation.hpp"
#include <array>
#include <string_view>

namespace cloudiff {
namespace {
bool desired_available(const nlohmann::json& state) {
    if (!state.is_object()) return false;
    if (state.contains("ok") && state["ok"].is_boolean() && !state["ok"].get<bool>()) return false;
    if (state.contains("available") && state["available"].is_boolean() && !state["available"].get<bool>()) return false;
    return true;
}
bool observed_unhealthy(const nlohmann::json& state) {
    if (!state.is_object()) return false;
    const auto it=state.find("status");
    if (it==state.end() || !it->is_string()) return false;
    const std::string value=it->get<std::string>();
    constexpr std::array<std::string_view,6> bad{"failed","error","unhealthy","stopped","dead","exited"};
    for (const auto candidate: bad) if (value==candidate) return true;
    return false;
}
}
CloudIFFProjectReconciliationResult evaluate_reconciliation(const CloudIFFProjectReconciliationInput& input) {
    CloudIFFProjectReconciliationResult out{"failed","invalid-input",input.desired_revision,input.observed_revision};
    if (input.resource_id.empty() || input.resource_type.empty() || input.desired_revision<0 || input.observed_revision<0 ||
        !input.desired_state.is_object() || !input.observed_state.is_object()) return out;
    if (!desired_available(input.desired_state)) {
        out.decision="blocked"; out.reason="desired-state-unavailable"; return out;
    }
    if (observed_unhealthy(input.observed_state)) {
        out.decision="degraded"; out.reason="observed-state-unhealthy"; return out;
    }
    if (input.desired_revision==input.observed_revision && input.desired_state==input.observed_state) {
        out.decision="noop"; out.reason="desired-observed-converged"; return out;
    }
    out.decision="reconcile";
    if (input.desired_revision!=input.observed_revision) out.reason="revision-drift";
    else out.reason="state-drift";
    return out;
}
nlohmann::json reconciliation_to_json(const CloudIFFProjectReconciliationInput& input,
                                      const CloudIFFProjectReconciliationResult& result) {
    return {{"resource_id",input.resource_id},{"resource_type",input.resource_type},
            {"desired_state",input.desired_state},{"observed_state",input.observed_state},
            {"desired_revision",result.desired_revision},{"observed_revision",result.observed_revision},
            {"decision",result.decision},{"reason",result.reason}};
}
}
