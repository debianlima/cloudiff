#include "cloudiff/job_state.hpp"
namespace cloudiff {
std::string_view to_string(JobStatus status) noexcept {
    switch (status) {
        case JobStatus::ready: return "ready";
        case JobStatus::leased: return "leased";
        case JobStatus::waiting_retry: return "waiting_retry";
        case JobStatus::succeeded: return "succeeded";
        case JobStatus::failed: return "failed";
        case JobStatus::dead_letter: return "dead_letter";
        case JobStatus::cancelled: return "cancelled";
    }
    return "unknown";
}
bool can_transition(JobStatus from, JobStatus to) noexcept {
    if (from == to) return true;
    switch (from) {
        case JobStatus::ready: return to == JobStatus::leased || to == JobStatus::cancelled;
        case JobStatus::leased: return to == JobStatus::succeeded || to == JobStatus::waiting_retry || to == JobStatus::failed || to == JobStatus::cancelled;
        case JobStatus::waiting_retry: return to == JobStatus::ready || to == JobStatus::dead_letter || to == JobStatus::cancelled;
        case JobStatus::failed: return to == JobStatus::waiting_retry || to == JobStatus::dead_letter;
        case JobStatus::succeeded:
        case JobStatus::dead_letter:
        case JobStatus::cancelled: return false;
    }
    return false;
}
}
