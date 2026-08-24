#include "cloudiff/postgres_client.hpp"
#include <stdexcept>
#include <string>
#include <vector>

namespace cloudiff {
namespace {
void require_result(PGconn* conn, PGresult* result, ExecStatusType expected, const char* operation) {
    if (result == nullptr || PQresultStatus(result) != expected) {
        const std::string message = std::string(operation) + ": " + (result ? PQresultErrorMessage(result) : PQerrorMessage(conn));
        if (result) PQclear(result);
        throw std::runtime_error(message);
    }
}
PGresult* params(PGconn* conn, const char* sql, const std::vector<std::string>& storage) {
    std::vector<const char*> values;
    values.reserve(storage.size());
    for (const auto& value : storage) values.push_back(value.c_str());
    return PQexecParams(conn, sql, static_cast<int>(values.size()), nullptr, values.data(), nullptr, nullptr, 0);
}
}
PostgresClient::PostgresClient(std::string conninfo) {
    connection_ = PQconnectdb(conninfo.c_str());
    if (connection_ == nullptr || PQstatus(connection_) != CONNECTION_OK) {
        const std::string message = connection_ ? PQerrorMessage(connection_) : "PQconnectdb returned null";
        if (connection_) PQfinish(connection_);
        connection_ = nullptr;
        throw std::runtime_error("postgres connect: " + message);
    }
}
PostgresClient::~PostgresClient() { if (connection_) PQfinish(connection_); }
void PostgresClient::command(const char* sql) {
    PGresult* r = PQexec(connection_, sql);
    require_result(connection_, r, PGRES_COMMAND_OK, sql);
    PQclear(r);
}
bool PostgresClient::apply_observation(const nlohmann::json& event) {
    const auto& payload = event.at("payload");
    const std::string event_id = event.at("event_id").get<std::string>();
    const std::string event_type = event.at("type").get<std::string>();
    const std::string occurred_at = event.at("occurred_at").get<std::string>();
    const std::string producer = event.at("producer").get<std::string>();
    const std::string resource_id = event.at("resource_id").get<std::string>();
    const std::string trace_id = event.at("trace_id").get<std::string>();
    const std::string node_id = payload.at("node_id").get<std::string>();
    const std::string hostname = payload.at("hostname").get<std::string>();
    const std::string role = payload.at("role").get<std::string>();
    const std::string observed_at = payload.at("observed_at").get<std::string>();
    const std::string capabilities = payload.at("capabilities").dump();
    const std::string state = payload.dump();
    const std::string revision = std::to_string(payload.at("revision").get<long long>());
    const std::string event_payload = event.at("payload").dump();
    command("BEGIN");
    try {
        const char* event_sql = R"SQL(
            INSERT INTO cloudiff_v2.events(event_id,event_type,occurred_at,producer,resource_id,trace_id,payload)
            VALUES($1::uuid,$2,$3::timestamptz,$4,$5,$6,$7::jsonb)
            ON CONFLICT(event_id) DO NOTHING RETURNING event_id
        )SQL";
        PGresult* r = params(connection_, event_sql, {event_id,event_type,occurred_at,producer,resource_id,trace_id,event_payload});
        require_result(connection_, r, PGRES_TUPLES_OK, "insert event");
        const bool inserted = PQntuples(r) == 1;
        PQclear(r);
        if (!inserted) { command("COMMIT"); return false; }

        const char* node_sql = R"SQL(
            INSERT INTO cloudiff_v2.nodes(node_id,hostname,role,capabilities,observed_at,last_seen_at,metadata)
            VALUES($1::uuid,$2,$3,ARRAY(SELECT jsonb_array_elements_text($4::jsonb)),$5::timestamptz,$5::timestamptz,$6::jsonb)
            ON CONFLICT(node_id) DO UPDATE SET
              hostname=EXCLUDED.hostname, role=EXCLUDED.role, capabilities=EXCLUDED.capabilities,
              observed_at=EXCLUDED.observed_at, last_seen_at=EXCLUDED.last_seen_at, metadata=EXCLUDED.metadata
            WHERE EXCLUDED.observed_at >= cloudiff_v2.nodes.observed_at
        )SQL";
        r = params(connection_, node_sql, {node_id,hostname,role,capabilities,observed_at,state});
        require_result(connection_, r, PGRES_COMMAND_OK, "upsert node"); PQclear(r);

        const char* observed_sql = R"SQL(
            INSERT INTO cloudiff_v2.observed_state(resource_type,resource_id,revision,state,observed_at,node_id)
            VALUES('node',$1::text,$2::bigint,$3::jsonb,$4::timestamptz,$1::uuid)
            ON CONFLICT(resource_type,resource_id) DO UPDATE SET
              revision=EXCLUDED.revision, state=EXCLUDED.state, observed_at=EXCLUDED.observed_at, node_id=EXCLUDED.node_id
            WHERE EXCLUDED.observed_at >= cloudiff_v2.observed_state.observed_at
        )SQL";
        r = params(connection_, observed_sql, {node_id,revision,state,observed_at});
        require_result(connection_, r, PGRES_COMMAND_OK, "upsert observed_state"); PQclear(r);

        const char* audit_sql = R"SQL(
            INSERT INTO cloudiff_v2.audit_log(actor,action,resource_type,resource_id,trace_id,details)
            VALUES($1,'node.observed','node',$2,$3,$4::jsonb)
        )SQL";
        r = params(connection_, audit_sql, {producer,node_id,trace_id,event_payload});
        require_result(connection_, r, PGRES_COMMAND_OK, "insert audit"); PQclear(r);
        command("COMMIT");
        return true;
    } catch (...) {
        PGresult* r = PQexec(connection_, "ROLLBACK"); if (r) PQclear(r);
        throw;
    }
}
}
