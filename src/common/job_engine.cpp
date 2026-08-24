#include "cloudiff/job_engine.hpp"
#include <uuid/uuid.h>
#include <algorithm>
#include <functional>
#include <stdexcept>
#include <string>
#include <vector>
namespace cloudiff {
namespace {
std::string uuid_string(){uuid_t v{};uuid_generate_random(v);char out[37]{};uuid_unparse_lower(v,out);return out;}
void require_result(PGconn* c,PGresult* r,ExecStatusType expected,const char* op){
 if(r==nullptr||PQresultStatus(r)!=expected){std::string m=std::string(op)+": "+(r?PQresultErrorMessage(r):PQerrorMessage(c));if(r)PQclear(r);throw std::runtime_error(m);}
}
PGresult* params(PGconn* c,const char* sql,const std::vector<std::string>& s){
 std::vector<const char*> v;v.reserve(s.size());for(const auto& x:s)v.push_back(x.c_str());
 return PQexecParams(c,sql,static_cast<int>(v.size()),nullptr,v.data(),nullptr,nullptr,0);
}
long long retry_delay(const std::string& id,int attempt,int base,int maxd){
 if(base<=0||maxd<=0)return 0;int exp=std::clamp(attempt-1,0,30);long long raw=std::min<long long>(maxd,static_cast<long long>(base)*(1LL<<exp));
 if(raw<=1)return raw;auto h=static_cast<unsigned long long>(std::hash<std::string>{}(id+":"+std::to_string(attempt)));long long w=std::max<long long>(1,raw/4);
 return std::min<long long>(maxd,raw+static_cast<long long>(h%static_cast<unsigned long long>(w+1)));
}
}
JobEngine::JobEngine(std::string ci){connection_=PQconnectdb(ci.c_str());if(connection_==nullptr||PQstatus(connection_)!=CONNECTION_OK){std::string m=connection_?PQerrorMessage(connection_):"PQconnectdb returned null";if(connection_)PQfinish(connection_);connection_=nullptr;throw std::runtime_error("job engine postgres connect: "+m);}}
JobEngine::~JobEngine(){if(connection_)PQfinish(connection_);}
void JobEngine::command(const char* sql){PGresult* r=PQexec(connection_,sql);require_result(connection_,r,PGRES_COMMAND_OK,sql);PQclear(r);}
std::string JobEngine::enqueue(const std::string& kind,const std::string& partition,const std::string& idem,const nlohmann::json& payload,int max_attempts){
 if(kind.empty()||partition.empty()||idem.empty())throw std::invalid_argument("job identifiers must not be empty");if(max_attempts<1)throw std::invalid_argument("max_attempts must be >= 1");
 std::string proposed=uuid_string();const char* sql=R"SQL(WITH inserted AS (
 INSERT INTO cloudiff_v2.jobs(job_id,kind,status,partition_key,idempotency_key,payload,max_attempts)
 VALUES($1::uuid,$2,'ready',$3,$4,$5::jsonb,$6::integer) ON CONFLICT(idempotency_key) DO NOTHING RETURNING job_id)
 SELECT job_id::text FROM inserted UNION ALL SELECT job_id::text FROM cloudiff_v2.jobs WHERE idempotency_key=$4 LIMIT 1)SQL";
 PGresult* r=params(connection_,sql,{proposed,kind,partition,idem,payload.dump(),std::to_string(max_attempts)});require_result(connection_,r,PGRES_TUPLES_OK,"enqueue");
 if(PQntuples(r)!=1){PQclear(r);throw std::runtime_error("enqueue did not return job_id");}std::string id=PQgetvalue(r,0,0);PQclear(r);return id;
}
std::vector<DurableJob> JobEngine::claim(const std::string& worker,int limit,int lease_seconds){
 if(worker.empty())throw std::invalid_argument("worker_id required");if(limit<=0)return {};
 PGresult* r=params(connection_,"SELECT job_id::text,kind,partition_key,idempotency_key,payload::text,attempt,max_attempts FROM cloudiff_v2.claim_jobs($1,$2::integer,$3::integer)",{worker,std::to_string(limit),std::to_string(std::max(1,lease_seconds))});
 require_result(connection_,r,PGRES_TUPLES_OK,"claim");std::vector<DurableJob> out;out.reserve(static_cast<std::size_t>(PQntuples(r)));
 for(int row=0;row<PQntuples(r);++row){DurableJob j;j.job_id=PQgetvalue(r,row,0);j.kind=PQgetvalue(r,row,1);j.partition_key=PQgetvalue(r,row,2);j.idempotency_key=PQgetvalue(r,row,3);j.payload=nlohmann::json::parse(PQgetvalue(r,row,4));j.attempt=std::stoi(PQgetvalue(r,row,5));j.max_attempts=std::stoi(PQgetvalue(r,row,6));out.push_back(std::move(j));}PQclear(r);return out;
}

std::vector<DurableJob> JobEngine::claim_kinds(const std::string& worker,int limit,int lease_seconds,const std::vector<std::string>& kinds){
 if(worker.empty())throw std::invalid_argument("worker_id required");if(limit<=0||kinds.empty())return {};
 std::string csv;for(const auto& kind:kinds){if(kind.empty()||kind.find(',')!=std::string::npos)throw std::invalid_argument("invalid job kind");if(!csv.empty())csv.push_back(',');csv+=kind;}
 PGresult* r=params(connection_,"SELECT job_id::text,kind,partition_key,idempotency_key,payload::text,attempt,max_attempts FROM cloudiff_v2.claim_jobs_for_kinds($1,$2::integer,$3::integer,string_to_array($4,','))",{worker,std::to_string(limit),std::to_string(std::max(1,lease_seconds)),csv});
 require_result(connection_,r,PGRES_TUPLES_OK,"claim kinds");std::vector<DurableJob> out;out.reserve(static_cast<std::size_t>(PQntuples(r)));
 for(int row=0;row<PQntuples(r);++row){DurableJob j;j.job_id=PQgetvalue(r,row,0);j.kind=PQgetvalue(r,row,1);j.partition_key=PQgetvalue(r,row,2);j.idempotency_key=PQgetvalue(r,row,3);j.payload=nlohmann::json::parse(PQgetvalue(r,row,4));j.attempt=std::stoi(PQgetvalue(r,row,5));j.max_attempts=std::stoi(PQgetvalue(r,row,6));out.push_back(std::move(j));}PQclear(r);return out;
}
bool JobEngine::complete(const std::string& id,const std::string& worker,const nlohmann::json& result){
 command("BEGIN");try{
 PGresult* r=params(connection_,"UPDATE cloudiff_v2.jobs SET status='succeeded',result=$3::jsonb,lease_owner=NULL,lease_expires_at=NULL,retry_at=NULL,last_error=NULL,updated_at=now() WHERE job_id=$1::uuid AND status='leased' AND lease_owner=$2 RETURNING attempt",{id,worker,result.dump()});require_result(connection_,r,PGRES_TUPLES_OK,"complete job");
 if(PQntuples(r)!=1){PQclear(r);command("ROLLBACK");return false;}std::string a=PQgetvalue(r,0,0);PQclear(r);
 r=params(connection_,"UPDATE cloudiff_v2.job_attempts SET finished_at=now(),outcome='succeeded',error=NULL WHERE job_id=$1::uuid AND attempt=$2::integer",{id,a});require_result(connection_,r,PGRES_COMMAND_OK,"complete attempt");PQclear(r);
 r=params(connection_,"DELETE FROM cloudiff_v2.job_partition_leases WHERE job_id=$1::uuid AND worker_id=$2",{id,worker});require_result(connection_,r,PGRES_COMMAND_OK,"release partition");PQclear(r);command("COMMIT");return true;
 }catch(...){PGresult* r=PQexec(connection_,"ROLLBACK");if(r)PQclear(r);throw;}
}
FailureDisposition JobEngine::fail(const std::string& id,const std::string& worker,const std::string& error,int base,int maxd){
 command("BEGIN");try{
 PGresult* r=params(connection_,"SELECT attempt,max_attempts FROM cloudiff_v2.jobs WHERE job_id=$1::uuid AND status='leased' AND lease_owner=$2 FOR UPDATE",{id,worker});require_result(connection_,r,PGRES_TUPLES_OK,"lock failed job");
 if(PQntuples(r)!=1){PQclear(r);command("ROLLBACK");throw std::runtime_error("job is not leased by worker");}int a=std::stoi(PQgetvalue(r,0,0)),m=std::stoi(PQgetvalue(r,0,1));PQclear(r);
 bool terminal=a>=m;long long delay=retry_delay(id,a,base,std::max(base,maxd));std::string state=terminal?"dead_letter":"waiting_retry";
 r=params(connection_,"UPDATE cloudiff_v2.jobs SET status=$3,last_error=$4,lease_owner=NULL,lease_expires_at=NULL,retry_at=CASE WHEN $3='waiting_retry' THEN now()+make_interval(secs=>$5::integer) ELSE NULL END,updated_at=now() WHERE job_id=$1::uuid AND status='leased' AND lease_owner=$2",{id,worker,state,error,std::to_string(delay)});require_result(connection_,r,PGRES_COMMAND_OK,"fail job");PQclear(r);
 r=params(connection_,"UPDATE cloudiff_v2.job_attempts SET finished_at=now(),outcome=$3,error=$4 WHERE job_id=$1::uuid AND attempt=$2::integer",{id,std::to_string(a),state,error});require_result(connection_,r,PGRES_COMMAND_OK,"fail attempt");PQclear(r);
 r=params(connection_,"DELETE FROM cloudiff_v2.job_partition_leases WHERE job_id=$1::uuid AND worker_id=$2",{id,worker});require_result(connection_,r,PGRES_COMMAND_OK,"release failed partition");PQclear(r);command("COMMIT");return terminal?FailureDisposition::dead_letter:FailureDisposition::waiting_retry;
 }catch(...){PGresult* r=PQexec(connection_,"ROLLBACK");if(r)PQclear(r);throw;}
}
bool JobEngine::fail_terminal(const std::string& id,const std::string& worker,const std::string& error,const nlohmann::json& result){
 command("BEGIN");try{
 PGresult* r=params(connection_,"UPDATE cloudiff_v2.jobs SET status='failed',result=$4::jsonb,last_error=$3,lease_owner=NULL,lease_expires_at=NULL,retry_at=NULL,updated_at=now() WHERE job_id=$1::uuid AND status='leased' AND lease_owner=$2 RETURNING attempt",{id,worker,error,result.dump()});require_result(connection_,r,PGRES_TUPLES_OK,"terminal fail job");
 if(PQntuples(r)!=1){PQclear(r);command("ROLLBACK");return false;}const std::string attempt=PQgetvalue(r,0,0);PQclear(r);
 r=params(connection_,"UPDATE cloudiff_v2.job_attempts SET finished_at=now(),outcome='failed',error=$3 WHERE job_id=$1::uuid AND attempt=$2::integer",{id,attempt,error});require_result(connection_,r,PGRES_COMMAND_OK,"terminal fail attempt");PQclear(r);
 r=params(connection_,"DELETE FROM cloudiff_v2.job_partition_leases WHERE job_id=$1::uuid AND worker_id=$2",{id,worker});require_result(connection_,r,PGRES_COMMAND_OK,"release terminal partition");PQclear(r);command("COMMIT");return true;
 }catch(...){PGresult* r=PQexec(connection_,"ROLLBACK");if(r)PQclear(r);throw;}
}
bool JobEngine::renew_lease(const std::string& id,const std::string& worker,int lease){
 command("BEGIN");try{std::string secs=std::to_string(std::max(1,lease));
 PGresult* r=params(connection_,"UPDATE cloudiff_v2.jobs SET lease_expires_at=now()+make_interval(secs=>$3::integer),updated_at=now() WHERE job_id=$1::uuid AND status='leased' AND lease_owner=$2 RETURNING partition_key",{id,worker,secs});require_result(connection_,r,PGRES_TUPLES_OK,"renew job lease");
 if(PQntuples(r)!=1){PQclear(r);command("ROLLBACK");return false;}PQclear(r);
 r=params(connection_,"UPDATE cloudiff_v2.job_partition_leases SET lease_expires_at=now()+make_interval(secs=>$3::integer) WHERE job_id=$1::uuid AND worker_id=$2",{id,worker,secs});require_result(connection_,r,PGRES_COMMAND_OK,"renew partition lease");PQclear(r);command("COMMIT");return true;
 }catch(...){PGresult* r=PQexec(connection_,"ROLLBACK");if(r)PQclear(r);throw;}
}
bool JobEngine::cancel(const std::string& id,const std::string& reason){
 command("BEGIN");try{
 PGresult* r=params(connection_,"UPDATE cloudiff_v2.jobs SET status='cancelled',last_error=$2,lease_owner=NULL,lease_expires_at=NULL,retry_at=NULL,updated_at=now() WHERE job_id=$1::uuid AND status NOT IN ('succeeded','dead_letter','cancelled') RETURNING job_id",{id,reason});require_result(connection_,r,PGRES_TUPLES_OK,"cancel job");bool changed=PQntuples(r)==1;PQclear(r);
 r=params(connection_,"DELETE FROM cloudiff_v2.job_partition_leases WHERE job_id=$1::uuid",{id});require_result(connection_,r,PGRES_COMMAND_OK,"release cancelled partition");PQclear(r);command("COMMIT");return changed;
 }catch(...){PGresult* r=PQexec(connection_,"ROLLBACK");if(r)PQclear(r);throw;}
}

std::optional<JobSnapshot> JobEngine::get(const std::string& id){
 PGresult* r=params(connection_,R"SQL(SELECT job_id::text,kind,status,partition_key,idempotency_key,payload::text,COALESCE(result::text,'null'),attempt,max_attempts,COALESCE(lease_owner,''),COALESCE(extract(epoch from lease_expires_at)::bigint,0),COALESCE(extract(epoch from retry_at)::bigint,0),COALESCE(trace_id,''),COALESCE(last_error,''),extract(epoch from created_at)::bigint,extract(epoch from updated_at)::bigint FROM cloudiff_v2.jobs WHERE job_id=$1::uuid)SQL",{id});
 require_result(connection_,r,PGRES_TUPLES_OK,"get job");if(PQntuples(r)!=1){PQclear(r);return std::nullopt;}JobSnapshot j;j.job_id=PQgetvalue(r,0,0);j.kind=PQgetvalue(r,0,1);j.status=PQgetvalue(r,0,2);j.partition_key=PQgetvalue(r,0,3);j.idempotency_key=PQgetvalue(r,0,4);j.payload=nlohmann::json::parse(PQgetvalue(r,0,5));j.result=nlohmann::json::parse(PQgetvalue(r,0,6));j.attempt=std::stoi(PQgetvalue(r,0,7));j.max_attempts=std::stoi(PQgetvalue(r,0,8));j.lease_owner=PQgetvalue(r,0,9);j.lease_expires_at=std::stoll(PQgetvalue(r,0,10));j.retry_at=std::stoll(PQgetvalue(r,0,11));j.trace_id=PQgetvalue(r,0,12);j.last_error=PQgetvalue(r,0,13);j.created_at=std::stoll(PQgetvalue(r,0,14));j.updated_at=std::stoll(PQgetvalue(r,0,15));PQclear(r);return j;
}
std::vector<JobAttemptSnapshot> JobEngine::attempts(const std::string& id){
 PGresult* r=params(connection_,R"SQL(SELECT attempt,worker_id,extract(epoch from started_at)::bigint,COALESCE(extract(epoch from finished_at)::bigint,0),COALESCE(outcome,''),COALESCE(error,'') FROM cloudiff_v2.job_attempts WHERE job_id=$1::uuid ORDER BY attempt)SQL",{id});require_result(connection_,r,PGRES_TUPLES_OK,"job attempts");std::vector<JobAttemptSnapshot> out;out.reserve(static_cast<std::size_t>(PQntuples(r)));for(int row=0;row<PQntuples(r);++row){JobAttemptSnapshot a;a.attempt=std::stoi(PQgetvalue(r,row,0));a.worker_id=PQgetvalue(r,row,1);a.started_at=std::stoll(PQgetvalue(r,row,2));a.finished_at=std::stoll(PQgetvalue(r,row,3));a.outcome=PQgetvalue(r,row,4);a.error=PQgetvalue(r,row,5);out.push_back(std::move(a));}PQclear(r);return out;
}
std::string JobEngine::status(const std::string& id){PGresult* r=params(connection_,"SELECT status FROM cloudiff_v2.jobs WHERE job_id=$1::uuid",{id});require_result(connection_,r,PGRES_TUPLES_OK,"job status");if(PQntuples(r)!=1){PQclear(r);return {};}std::string s=PQgetvalue(r,0,0);PQclear(r);return s;}
}
