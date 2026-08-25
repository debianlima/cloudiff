#pragma once
#include <cstdint>
#include <string>
#include <nlohmann/json.hpp>

namespace cloudiff {
struct CloudIFFProjectReconciliationInput {
    std::string resource_id;
    std::string resource_type;
    nlohmann::json desired_state;
    nlohmann::json observed_state;
    std::int64_t desired_revision{0};
    std::int64_t observed_revision{0};
};
struct CloudIFFProjectReconciliationResult {
    std::string decision;
    std::string reason;
    std::int64_t desired_revision{0};
    std::int64_t observed_revision{0};
};
CloudIFFProjectReconciliationResult evaluate_reconciliation(const CloudIFFProjectReconciliationInput& input);
nlohmann::json reconciliation_to_json(const CloudIFFProjectReconciliationInput& input,
                                      const CloudIFFProjectReconciliationResult& result);
}
