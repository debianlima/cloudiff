#include "cloudiff/reconciliation.hpp"
#include <iostream>
#include <nlohmann/json.hpp>

int main() {
    try {
        nlohmann::json j; std::cin>>j;
        cloudiff::CloudIFFProjectReconciliationInput in{
            j.value("resource_id",std::string{}),j.value("resource_type",std::string{}),
            j.value("desired_state",nlohmann::json::object()),j.value("observed_state",nlohmann::json::object()),
            j.value("desired_revision",0LL),j.value("observed_revision",0LL)};
        const auto result=cloudiff::evaluate_reconciliation(in);
        std::cout<<cloudiff::reconciliation_to_json(in,result).dump()<<'\n';
        return result.decision=="failed" ? 2 : 0;
    } catch (const std::exception& e) {
        std::cerr<<"reconciliation-input-error:"<<e.what()<<'\n'; return 2;
    }
}
