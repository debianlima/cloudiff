#include "cloudiff/job_state.hpp"
#include <cassert>
int main() {
    using cloudiff::JobStatus;
    assert(cloudiff::can_transition(JobStatus::ready, JobStatus::leased));
    assert(cloudiff::can_transition(JobStatus::leased, JobStatus::succeeded));
    assert(cloudiff::can_transition(JobStatus::leased, JobStatus::waiting_retry));
    assert(cloudiff::can_transition(JobStatus::waiting_retry, JobStatus::ready));
    assert(cloudiff::can_transition(JobStatus::waiting_retry, JobStatus::dead_letter));
    assert(!cloudiff::can_transition(JobStatus::succeeded, JobStatus::ready));
    // Reexecution of terminal success is idempotent/no-op at the state layer.
    assert(cloudiff::can_transition(JobStatus::succeeded, JobStatus::succeeded));
    return 0;
}
