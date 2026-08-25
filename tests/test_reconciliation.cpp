#include "cloudiff/reconciliation.hpp"
#include <cassert>
#include <iostream>
using cloudiff::CloudIFFProjectReconciliationInput;
using cloudiff::evaluate_reconciliation;
int main(){
    CloudIFFProjectReconciliationInput in{"node-1","node",{{"status","active"}},{{"status","active"}},4,4};
    auto r=evaluate_reconciliation(in);assert(r.decision=="noop"&&r.reason=="desired-observed-converged");
    in.observed_revision=3;r=evaluate_reconciliation(in);assert(r.decision=="reconcile"&&r.reason=="revision-drift");
    in.observed_revision=4;in.observed_state={{"status","other"}};r=evaluate_reconciliation(in);assert(r.decision=="reconcile"&&r.reason=="state-drift");
    in.desired_state={{"ok",false}};r=evaluate_reconciliation(in);assert(r.decision=="blocked"&&r.reason=="desired-state-unavailable");
    in.desired_state={{"status","active"}};in.observed_state={{"status","unhealthy"}};r=evaluate_reconciliation(in);assert(r.decision=="degraded"&&r.reason=="observed-state-unhealthy");
    in.resource_id.clear();r=evaluate_reconciliation(in);assert(r.decision=="failed"&&r.reason=="invalid-input");
    std::cout<<"RECONCILIATION=PASS noop,reconcile,blocked,degraded,failed\n";
}
