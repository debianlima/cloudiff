#pragma once
#include <libpq-fe.h>
#include <nlohmann/json.hpp>
#include <string>

namespace cloudiff {
class PostgresClient final {
public:
    explicit PostgresClient(std::string conninfo);
    ~PostgresClient();
    PostgresClient(const PostgresClient&) = delete;
    PostgresClient& operator=(const PostgresClient&) = delete;
    [[nodiscard]] bool apply_observation(const nlohmann::json& event);
private:
    PGconn* connection_{nullptr};
    void command(const char* sql);
};
}
