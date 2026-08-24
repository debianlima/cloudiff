#include "cloudiff/classic_build_worker.hpp"
#include "cloudiff/job_engine.hpp"
#include <boost/asio/post.hpp>
#include <boost/asio/thread_pool.hpp>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <iostream>
#include <string>
#include <thread>
#include <vector>
#include <unistd.h>
namespace {
std::atomic<bool> stop_requested{false};void on_signal(int){stop_requested.store(true);}
std::string env_or(const char* n,std::string f={}){const char* v=std::getenv(n);return v?std::string(v):std::move(f);}
int env_int(const char* n,int f,int lo,int hi){try{return std::clamp(std::stoi(env_or(n,std::to_string(f))),lo,hi);}catch(...){return f;}}
std::string worker_id(){char h[256]{};::gethostname(h,sizeof(h)-1);return std::string(h)+":"+std::to_string(::getpid());}
std::vector<std::string> split_kinds(std::string value){std::vector<std::string> out;std::size_t start=0;while(start<=value.size()){const auto pos=value.find(',',start);auto part=value.substr(start,pos==std::string::npos?std::string::npos:pos-start);part.erase(0,part.find_first_not_of(" \t"));const auto end=part.find_last_not_of(" \t");if(end!=std::string::npos)part.resize(end+1);if(!part.empty()&&std::find(out.begin(),out.end(),part)==out.end())out.push_back(part);if(pos==std::string::npos)break;start=pos+1;}return out;}
void emit(const char* level,const std::string& job_id,const std::string& message){std::cerr<<nlohmann::json{{"service","cloudiff-worker"},{"level",level},{"job_id",job_id},{"message",message}}.dump()<<'\n';}
void process(const std::string& ci,const std::string& wid,const cloudiff::DurableJob& j,int lease_seconds,int retry_base,int retry_max){
    std::jthread renewer;
    if(j.kind=="cloudiff.v2.build.classic"){
        const auto interval=std::max(1,lease_seconds/3);const auto id=j.job_id;
        renewer=std::jthread([ci,wid,id,lease_seconds,interval](std::stop_token stop){
            while(!stop.stop_requested()){
                for(int second=0;second<interval&&!stop.stop_requested();++second)std::this_thread::sleep_for(std::chrono::seconds(1));
                if(stop.stop_requested())break;
                try{cloudiff::JobEngine lease_engine(ci);if(!lease_engine.renew_lease(id,wid,lease_seconds))break;}
                catch(const std::exception& e){emit("warning",id,std::string("lease_renew_failed: ")+e.what());break;}
            }
        });
    }
    try{
        cloudiff::JobEngine e(ci);
        if(j.kind=="cloudiff.v2.noop"){
            (void)e.complete(j.job_id,wid,{{"ok",true},{"attempt",j.attempt}});
        }else if(j.kind=="cloudiff.v2.fail_once"){
            if(j.attempt==1)(void)e.fail(j.job_id,wid,"injected fail_once",1,30);else(void)e.complete(j.job_id,wid,{{"ok",true},{"recovered_after",j.attempt}});
        }else if(j.kind=="cloudiff.v2.build.classic"){
            try{
                cloudiff::ClassicBuildWorker executor(cloudiff::classic_build_worker_options_from_environment());const auto result=executor.execute(j);
                if(result.outcome==cloudiff::ClassicBuildOutcome::succeeded){if(!e.complete(j.job_id,wid,result.result))throw std::runtime_error("classic build completion lease lost");}
                else if(!e.fail_terminal(j.job_id,wid,result.error,result.result))throw std::runtime_error("classic build terminal completion lease lost");
            }catch(const std::invalid_argument& x){
                const nlohmann::json result={{"ok",false},{"error","invalid_build_payload"},{"secrets_exposed",false}};if(!e.fail_terminal(j.job_id,wid,"invalid_build_payload",result))throw;emit("warning",j.job_id,x.what());
            }catch(const std::exception& x){
                (void)e.fail(j.job_id,wid,x.what(),retry_base,retry_max);emit("warning",j.job_id,std::string("classic build retry: ")+x.what());
            }
        }else{
            (void)e.fail(j.job_id,wid,"unsupported job kind: "+j.kind,1,60);
        }
    }catch(const std::exception& x){emit("error",j.job_id,x.what());}
    if(renewer.joinable())renewer.request_stop();
}
}
int main(int argc,char** argv){
    if(argc>1&&std::string(argv[1])=="--version"){std::cout<<"cloudiff-worker 0.27.0-shadow\n";return 0;}bool once=false;for(int i=1;i<argc;++i)if(std::string(argv[i])=="--once")once=true;
    try{
        std::string ci=env_or("CLOUDIFF_POSTGRES_CONNINFO");if(ci.empty())throw std::runtime_error("CLOUDIFF_POSTGRES_CONNINFO required");std::string wid=env_or("CLOUDIFF_WORKER_ID",worker_id());
        int concurrency=env_int("CLOUDIFF_WORKER_CONCURRENCY",4,1,32),lease=env_int("CLOUDIFF_WORKER_LEASE_SECONDS",30,5,3600),poll=env_int("CLOUDIFF_WORKER_POLL_MS",250,25,10000),retry_base=env_int("CLOUDIFF_BUILD_RETRY_BASE_SECONDS",15,0,3600),retry_max=env_int("CLOUDIFF_BUILD_RETRY_MAX_SECONDS",300,1,86400);
        auto allowed=split_kinds(env_or("CLOUDIFF_WORKER_ALLOWED_KINDS","cloudiff.v2.noop,cloudiff.v2.fail_once"));if(allowed.empty())throw std::runtime_error("CLOUDIFF_WORKER_ALLOWED_KINDS must not be empty");
        std::signal(SIGINT,on_signal);std::signal(SIGTERM,on_signal);boost::asio::thread_pool pool(static_cast<std::size_t>(concurrency));std::atomic<int> inflight{0};cloudiff::JobEngine claimer(ci);
        do{int available=concurrency-inflight.load();if(available>0){auto jobs=claimer.claim_kinds(wid,available,lease,allowed);for(auto& j:jobs){inflight.fetch_add(1);boost::asio::post(pool,[&,j]{process(ci,wid,j,lease,retry_base,retry_max);inflight.fetch_sub(1);});}if(once){while(inflight.load()>0)std::this_thread::sleep_for(std::chrono::milliseconds(10));break;}}std::this_thread::sleep_for(std::chrono::milliseconds(poll));}while(!stop_requested.load());pool.join();return 0;
    }catch(const std::exception& x){std::cerr<<"cloudiff-worker: "<<x.what()<<'\n';return 2;}
}
