#include "cloudiff/nats_client.hpp"
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdlib>
#include <nats/nats.h>
#include <stdexcept>
#include <string>
#include <thread>

namespace {
std::string env_required(const char* name){ const char* v=std::getenv(name); if(!v||!*v) throw std::runtime_error(std::string(name)+" required"); return v; }
cloudiff::NatsAuthConfig auth(const char* user,const char* pass){ return {env_required(user),env_required(pass)}; }
void require_ok(natsStatus st){ assert(st==NATS_OK); }
void on_async_error(natsConnection*,natsSubscription*,natsStatus,void* closure){ static_cast<std::atomic<int>*>(closure)->fetch_add(1); }
void configure_tls(natsOptions* opts,const cloudiff::NatsTlsConfig& tls){
    require_ok(natsOptions_SetSecure(opts,true));
    require_ok(natsOptions_LoadCATrustedCertificates(opts,tls.ca_file.c_str()));
    require_ok(natsOptions_LoadCertificatesChain(opts,tls.cert_file.c_str(),tls.key_file.c_str()));
    require_ok(natsOptions_SetExpectedHostname(opts,tls.expected_hostname.c_str()));
}
}
int main(){
    const auto url=env_required("CLOUDIFF_NATS_URL"); const auto pub=auth("CLOUDIFF_NATS_TEST_PUBLISH_USER","CLOUDIFF_NATS_TEST_PUBLISH_PASSWORD");
    const auto sub_auth=auth("CLOUDIFF_NATS_TEST_SUBSCRIBE_USER","CLOUDIFF_NATS_TEST_SUBSCRIBE_PASSWORD");
    auto tls=cloudiff::nats_tls_from_environment(); assert(tls.enabled); assert(!tls.expected_hostname.empty());

    // Valid mTLS + independent credentials + permitted subjects.
    cloudiff::NatsClient subscriber(url,sub_auth,tls); natsSubscription* sub=nullptr;
    assert(natsConnection_SubscribeSync(&sub,subscriber.native(),"cloudiff.v2.node.observed")==NATS_OK);
    cloudiff::NatsClient publisher(url,pub,tls); publisher.publish("cloudiff.v2.node.observed","mtls-v7-ok");
    natsMsg* msg=nullptr; assert(natsSubscription_NextMsg(&msg,sub,2000)==NATS_OK);
    std::string body(natsMsg_GetData(msg),static_cast<std::size_t>(natsMsg_GetDataLength(msg))); assert(body=="mtls-v7-ok");
    natsMsg_Destroy(msg); natsSubscription_Destroy(sub);

    bool hostname_rejected=false;
    try { auto bad=tls; bad.expected_hostname="wrong.invalid"; cloudiff::NatsClient invalid(url,pub,bad); }
    catch(const std::exception&) { hostname_rejected=true; }
    assert(hostname_rejected);

    bool wrong_password_rejected=false;
    try { auto bad=pub; bad.password="intentionally-wrong-password"; cloudiff::NatsClient invalid(url,bad,tls); }
    catch(const std::exception&) { wrong_password_rejected=true; }
    assert(wrong_password_rejected);

    // Trusted CA + correct username/password, but no client certificate: mTLS must reject it.
    natsOptions* no_cert_opts=nullptr; require_ok(natsOptions_Create(&no_cert_opts));
    require_ok(natsOptions_SetURL(no_cert_opts,url.c_str())); require_ok(natsOptions_SetUserInfo(no_cert_opts,pub.user.c_str(),pub.password.c_str()));
    require_ok(natsOptions_SetSecure(no_cert_opts,true)); require_ok(natsOptions_LoadCATrustedCertificates(no_cert_opts,tls.ca_file.c_str()));
    require_ok(natsOptions_SetExpectedHostname(no_cert_opts,tls.expected_hostname.c_str()));
    natsConnection* no_cert=nullptr; const auto no_cert_status=natsConnection_Connect(&no_cert,no_cert_opts);
    if(no_cert)natsConnection_Destroy(no_cert); natsOptions_Destroy(no_cert_opts); assert(no_cert_status!=NATS_OK);

    // Agent credential is publish-only: a subscription must produce an async permission error.
    std::atomic<int> async_errors{0}; natsOptions* denied_opts=nullptr; require_ok(natsOptions_Create(&denied_opts));
    require_ok(natsOptions_SetURL(denied_opts,url.c_str())); require_ok(natsOptions_SetUserInfo(denied_opts,pub.user.c_str(),pub.password.c_str()));
    require_ok(natsOptions_SetErrorHandler(denied_opts,on_async_error,&async_errors)); configure_tls(denied_opts,tls);
    natsConnection* denied_conn=nullptr; require_ok(natsConnection_Connect(&denied_conn,denied_opts)); natsOptions_Destroy(denied_opts);
    natsSubscription* denied_sub=nullptr; require_ok(natsConnection_SubscribeSync(&denied_sub,denied_conn,"cloudiff.v2.node.observed"));
    (void)natsConnection_FlushTimeout(denied_conn,1000); std::this_thread::sleep_for(std::chrono::milliseconds(300));
    assert(async_errors.load()>0); natsSubscription_Destroy(denied_sub); natsConnection_Destroy(denied_conn);
    return 0;
}
