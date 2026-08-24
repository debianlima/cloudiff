#pragma once
#include <string_view>

namespace cloudiff {
enum class JobStatus { ready, leased, waiting_retry, succeeded, failed, dead_letter, cancelled };
[[nodiscard]] std::string_view to_string(JobStatus status) noexcept;
[[nodiscard]] bool can_transition(JobStatus from, JobStatus to) noexcept;
}
