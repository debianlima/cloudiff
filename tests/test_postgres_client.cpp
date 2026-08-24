#include "cloudiff/postgres_client.hpp"
#include <cassert>
#include <cstdlib>
#include <libpq-fe.h>
#include <nlohmann/json.hpp>
#include <string>
int main(){
    const char* ci=std::getenv("CLOUDIFF_POSTGRES_CONNINFO"); assert(ci);
    PGconn* raw=PQconnectdb(ci); assert(PQstatus(raw)==CONNECTION_OK);
    PQclear(PQexec(raw,"DELETE FROM cloudiff_v2.audit_log WHERE resource_id='00000000-0000-4000-8000-000000000099'; DELETE FROM cloudiff_v2.observed_state WHERE resource_id='00000000-0000-4000-8000-000000000099'; DELETE FROM cloudiff_v2.events WHERE event_id='00000000-0000-4000-8000-000000000199'; DELETE FROM cloudiff_v2.nodes WHERE node_id='00000000-0000-4000-8000-000000000099';"));
    cloudiff::PostgresClient db(ci);
    nlohmann::json ev={{"event_id","00000000-0000-4000-8000-000000000199"},{"type","node.observed"},{"occurred_at","2026-08-20T12:00:00Z"},{"producer","test"},{"resource_id","00000000-0000-4000-8000-000000000099"},{"trace_id","trace-test"},{"payload",{{"node_id","00000000-0000-4000-8000-000000000099"},{"hostname","test-node"},{"role","other"},{"observed_at","2026-08-20T12:00:00Z"},{"capabilities",{"health"}},{"revision",1}}}};
    assert(db.apply_observation(ev)); assert(!db.apply_observation(ev));
    PGresult* r=PQexec(raw,"SELECT (SELECT count(*) FROM cloudiff_v2.events WHERE event_id='00000000-0000-4000-8000-000000000199'),(SELECT count(*) FROM cloudiff_v2.audit_log WHERE resource_id='00000000-0000-4000-8000-000000000099'),(SELECT count(*) FROM cloudiff_v2.observed_state WHERE resource_id='00000000-0000-4000-8000-000000000099');");
    assert(PQresultStatus(r)==PGRES_TUPLES_OK); assert(std::string(PQgetvalue(r,0,0))=="1"); assert(std::string(PQgetvalue(r,0,1))=="1"); assert(std::string(PQgetvalue(r,0,2))=="1"); PQclear(r);
    PQclear(PQexec(raw,"DELETE FROM cloudiff_v2.audit_log WHERE resource_id='00000000-0000-4000-8000-000000000099'; DELETE FROM cloudiff_v2.observed_state WHERE resource_id='00000000-0000-4000-8000-000000000099'; DELETE FROM cloudiff_v2.events WHERE event_id='00000000-0000-4000-8000-000000000199'; DELETE FROM cloudiff_v2.nodes WHERE node_id='00000000-0000-4000-8000-000000000099';")); PQfinish(raw); return 0;
}
