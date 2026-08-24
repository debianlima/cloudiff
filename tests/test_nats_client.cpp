#include "cloudiff/nats_client.hpp"
#include <cassert>
#include <cstdlib>
#include <nats/nats.h>
#include <stdexcept>
#include <string>
#include <thread>
#include <chrono>

namespace {
std::string env_required(const char* name){ const char* v=std::getenv(name); if(!v||!*v) throw std::runtime_error(std::string(name)+" required"); return v; }
cloudiff::NatsAuthConfig auth(const char* user,const char* pass){ return {env_required(user),env_required(pass)}; }
}
int main(){
    const auto url=env_required("CLOUDIFF_NATS_URL"); auto tls=cloudiff::nats_tls_from_environment();
    cloudiff::NatsClient subscriber(url,auth("CLOUDIFF_NATS_TEST_SUBSCRIBE_USER","CLOUDIFF_NATS_TEST_SUBSCRIBE_PASSWORD"),tls);
    natsSubscription* sub=nullptr; assert(natsConnection_SubscribeSync(&sub,subscriber.native(),"cloudiff.v2.node.observed")==NATS_OK);
    cloudiff::NatsClient publisher(url,auth("CLOUDIFF_NATS_TEST_PUBLISH_USER","CLOUDIFF_NATS_TEST_PUBLISH_PASSWORD"),tls);
    publisher.publish("cloudiff.v2.node.observed","cpp-v7-auth-ok");
    natsMsg* msg=nullptr; assert(natsSubscription_NextMsg(&msg,sub,2000)==NATS_OK);
    std::string body(natsMsg_GetData(msg),static_cast<std::size_t>(natsMsg_GetDataLength(msg))); assert(body=="cpp-v7-auth-ok");
    natsMsg_Destroy(msg);
    if(const char* wait=std::getenv("CLOUDIFF_NATS_TEST_RECONNECT_WAIT_SECONDS");wait&&*wait){
        const int seconds=std::stoi(wait);if(seconds>0)std::this_thread::sleep_for(std::chrono::seconds(seconds));
        publisher.publish("cloudiff.v2.node.observed","cpp-v36-reconnect-ok",5000);
        msg=nullptr;assert(natsSubscription_NextMsg(&msg,sub,5000)==NATS_OK);
        body.assign(natsMsg_GetData(msg),static_cast<std::size_t>(natsMsg_GetDataLength(msg)));assert(body=="cpp-v36-reconnect-ok");natsMsg_Destroy(msg);
    }
    natsSubscription_Destroy(sub); return 0;
}
