#include "cloudiff/job_engine.hpp"
#include <libpq-fe.h>
#include <cassert>
#include <barrier>
#include <vector>
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <thread>
namespace { void cleanup(const char* ci){PGconn* c=PQconnectdb(ci);assert(PQstatus(c)==CONNECTION_OK);PGresult* r=PQexec(c,"DELETE FROM cloudiff_v2.jobs WHERE idempotency_key LIKE 'itest-v5:%' OR idempotency_key LIKE 'itest-v16:%'");assert(PQresultStatus(r)==PGRES_COMMAND_OK);PQclear(r);PQfinish(c);} }
int main(){
 const char* ci=std::getenv("CLOUDIFF_POSTGRES_CONNINFO");assert(ci);cleanup(ci);cloudiff::JobEngine a(ci),b(ci);
    // Real race: two independent PostgreSQL sessions compete for the same partition.
    const auto r1=a.enqueue("cloudiff.v2.noop","project:RACE","itest-v5:race1",{{"n",1}},3);
    const auto r2=a.enqueue("cloudiff.v2.noop","project:RACE","itest-v5:race2",{{"n",2}},3);
    std::barrier gate(3); std::vector<cloudiff::DurableJob> left,right;
    std::thread t1([&]{ cloudiff::JobEngine e(ci); gate.arrive_and_wait(); left=e.claim("race-left",1,5); });
    std::thread t2([&]{ cloudiff::JobEngine e(ci); gate.arrive_and_wait(); right=e.claim("race-right",1,5); });
    gate.arrive_and_wait(); t1.join(); t2.join();
    assert(left.size()+right.size()==1);
    if(!left.empty()) assert(a.complete(left[0].job_id,"race-left",{{"race",true}}));
    if(!right.empty()) assert(a.complete(right[0].job_id,"race-right",{{"race",true}}));
    (void)a.cancel(a.status(r1)=="succeeded"?r2:r1,"test cleanup");
 auto a1=a.enqueue("cloudiff.v2.noop","project:A","itest-v5:a1",{{"value",1}},3);auto a1d=a.enqueue("cloudiff.v2.noop","project:A","itest-v5:a1",{{"value",999}},3);assert(a1==a1d);
 auto a2=a.enqueue("cloudiff.v2.noop","project:A","itest-v5:a2",{{"value",2}},3);auto b1=a.enqueue("cloudiff.v2.noop","project:B","itest-v5:b1",{{"value",3}},3);
 auto first=a.claim("worker-A",1,5);assert(first.size()==1&&first[0].job_id==a1);auto parallel=b.claim("worker-B",10,5);assert(parallel.size()==1&&parallel[0].job_id==b1);
 assert(a.complete(a1,"worker-A",{{"ok",true}}));auto same=b.claim("worker-B",10,5);assert(same.size()==1&&same[0].job_id==a2);assert(b.complete(a2,"worker-B",{{"ok",true}}));assert(b.complete(b1,"worker-B",{{"ok",true}}));
 auto crash=a.enqueue("cloudiff.v2.noop","project:C","itest-v5:crash",{{"crash",true}},3);auto c1=a.claim("worker-crash",1,1);assert(c1.size()==1&&c1[0].job_id==crash&&c1[0].attempt==1);std::this_thread::sleep_for(std::chrono::milliseconds(1300));auto c2=b.claim("worker-recovery",1,5);assert(c2.size()==1&&c2[0].job_id==crash&&c2[0].attempt==2);assert(b.complete(crash,"worker-recovery",{{"recovered",true}}));
 auto dying=a.enqueue("cloudiff.v2.always_fail","project:D","itest-v5:dead",{{"fail",true}},2);auto d1=a.claim("worker-D",1,5);assert(d1.size()==1&&d1[0].attempt==1);assert(a.fail(dying,"worker-D","injected",0,0)==cloudiff::FailureDisposition::waiting_retry);assert(a.status(dying)=="waiting_retry");auto d2=b.claim("worker-D2",1,5);assert(d2.size()==1&&d2[0].job_id==dying&&d2[0].attempt==2);assert(b.fail(dying,"worker-D2","injected again",0,0)==cloudiff::FailureDisposition::dead_letter);assert(b.status(dying)=="dead_letter");
 auto terminal=a.enqueue("cloudiff.v2.build.classic","project:T","itest-v16:terminal",{{"policy",false}},3);auto tf=a.claim_kinds("worker-T",1,30,{"cloudiff.v2.build.classic"});assert(tf.size()==1&&tf[0].job_id==terminal&&tf[0].attempt==1);assert(a.fail_terminal(terminal,"worker-T","workspace_policy_failed",{{"valid",false},{"secrets_exposed",false}}));auto ts=a.get(terminal);assert(ts&&ts->status=="failed"&&ts->retry_at==0&&ts->lease_owner.empty()&&ts->result.at("valid")==false);auto ta=a.attempts(terminal);assert(ta.size()==1&&ta[0].outcome=="failed"&&ta[0].error=="workspace_policy_failed");auto no_retry=b.claim_kinds("worker-T2",1,30,{"cloudiff.v2.build.classic"});assert(no_retry.empty());
 cleanup(ci);std::cout<<"job_engine_integration=PASS\n";return 0;
}
