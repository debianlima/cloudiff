#include "cloudiff/nats_client.hpp"
#include "cloudiff/build_broker.hpp"
#include "cloudiff/postgres_client.hpp"
#include <nlohmann/json.hpp>
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>

namespace {
std::string env_required(const char* name){const char* v=std::getenv(name); if(!v||!*v)throw std::runtime_error(std::string(name)+" required"); return v;}
struct Context{cloudiff::PostgresClient* db; std::atomic<int>* processed;};
void on_message(natsConnection*, natsSubscription*, natsMsg* msg, void* closure){
    auto* ctx=static_cast<Context*>(closure);
    try{ std::string body(natsMsg_GetData(msg),static_cast<std::size_t>(natsMsg_GetDataLength(msg))); auto event=nlohmann::json::parse(body);
         const bool applied=ctx->db->apply_observation(event); if(applied)++(*ctx->processed);
         std::cout<<nlohmann::json{{"service","cloudiff-control"},{"event_id",event.value("event_id","")},{"applied",applied}}.dump()<<'\n'; }
    catch(const std::exception& e){ std::cerr<<nlohmann::json{{"service","cloudiff-control"},{"level","error"},{"message",e.what()}}.dump()<<'\n'; }
    natsMsg_Destroy(msg);
}
}
int main(int argc,char** argv){
    try{
        bool once=false,build_broker=false; for(int i=1;i<argc;++i){std::string a=argv[i]; if(a=="--once")once=true; else if(a=="--build-broker")build_broker=true; else if(a=="--version"){std::cout<<"cloudiff-control 0.15.0-shadow\n";return 0;}}
        if(build_broker)return cloudiff::run_build_broker_server(cloudiff::build_broker_options_from_environment());
        cloudiff::PostgresClient db(env_required("CLOUDIFF_POSTGRES_CONNINFO")); cloudiff::NatsClient nats(env_required("CLOUDIFF_NATS_URL"),cloudiff::nats_auth_from_environment(),cloudiff::nats_tls_from_environment());
        std::atomic<int> processed{0}; Context ctx{&db,&processed}; natsSubscription* sub=nullptr;
        auto st=natsConnection_Subscribe(&sub,nats.native(),"cloudiff.v2.node.observed",on_message,&ctx); if(st!=NATS_OK)throw std::runtime_error(natsStatus_GetText(st));
        st=natsSubscription_SetPendingLimits(sub,1024,8*1024*1024); if(st!=NATS_OK)throw std::runtime_error(natsStatus_GetText(st));
        const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(once?10:31536000);
        while(std::chrono::steady_clock::now()<deadline && (!once||processed.load()==0)) std::this_thread::sleep_for(std::chrono::milliseconds(100));
        natsSubscription_Destroy(sub); return once && processed.load()==0 ? 4 : 0;
    }catch(const std::exception& e){std::cerr<<"cloudiff-control: "<<e.what()<<'\n';return 2;}
}
