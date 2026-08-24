#pragma once
#include <libpq-fe.h>
#include <nlohmann/json.hpp>
#include <optional>
#include <string>
#include <vector>
namespace cloudiff {
struct DurableJob { std::string job_id,kind,partition_key,idempotency_key; nlohmann::json payload; int attempt{0}; int max_attempts{1}; };
struct JobSnapshot {
 std::string job_id,kind,status,partition_key,idempotency_key,lease_owner,trace_id,last_error;
 nlohmann::json payload,result;
 int attempt{0},max_attempts{1};
 long long lease_expires_at{0},retry_at{0},created_at{0},updated_at{0};
};
struct JobAttemptSnapshot { int attempt{0}; std::string worker_id,outcome,error; long long started_at{0},finished_at{0}; };
enum class FailureDisposition { waiting_retry, dead_letter };
class JobEngine final {
public:
 explicit JobEngine(std::string conninfo); ~JobEngine(); JobEngine(const JobEngine&)=delete; JobEngine& operator=(const JobEngine&)=delete;
 [[nodiscard]] std::string enqueue(const std::string&,const std::string&,const std::string&,const nlohmann::json&,int max_attempts=5);
 [[nodiscard]] std::vector<DurableJob> claim(const std::string&,int,int);
 [[nodiscard]] std::vector<DurableJob> claim_kinds(const std::string&,int,int,const std::vector<std::string>&);
 [[nodiscard]] bool complete(const std::string&,const std::string&,const nlohmann::json&);
 [[nodiscard]] FailureDisposition fail(const std::string&,const std::string&,const std::string&,int,int);
 [[nodiscard]] bool fail_terminal(const std::string&,const std::string&,const std::string&,const nlohmann::json&);
 [[nodiscard]] bool renew_lease(const std::string&,const std::string&,int);
 [[nodiscard]] bool cancel(const std::string&,const std::string&);
 [[nodiscard]] std::string status(const std::string&);
 [[nodiscard]] std::optional<JobSnapshot> get(const std::string&);
 [[nodiscard]] std::vector<JobAttemptSnapshot> attempts(const std::string&);
private: PGconn* connection_{nullptr}; void command(const char*);
};
}
