#include "cloudiff/nats_client.hpp"
#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <stdexcept>
#include <string>

namespace cloudiff {
namespace {
void check(natsStatus status, const char* operation) {
    if (status != NATS_OK) throw std::runtime_error(std::string(operation) + ": " + natsStatus_GetText(status));
}
std::string env_value(const char* name) {
    const char* value=std::getenv(name);
    return value?std::string(value):std::string{};
}
void validate_auth(const NatsAuthConfig& auth) {
    if (auth.user.empty() || auth.password.empty()) throw std::invalid_argument("NATS user/password credential is incomplete");
}
void validate_tls(const NatsTlsConfig& tls) {
    if (!tls.enabled) return;
    if (tls.ca_file.empty() || tls.cert_file.empty() || tls.key_file.empty() || tls.expected_hostname.empty())
        throw std::invalid_argument("TLS enabled but CA/cert/key/expected hostname is incomplete");
}
}
NatsAuthConfig nats_auth_from_environment() {
    return NatsAuthConfig{env_value("CLOUDIFF_NATS_USER"),env_value("CLOUDIFF_NATS_PASSWORD")};
}
NatsTlsConfig nats_tls_from_environment() {
    auto enabled_value=env_value("CLOUDIFF_NATS_TLS_ENABLED");
    std::transform(enabled_value.begin(),enabled_value.end(),enabled_value.begin(),[](unsigned char c){return static_cast<char>(std::tolower(c));});
    const bool enabled=enabled_value=="1" || enabled_value=="true" || enabled_value=="yes" || enabled_value=="on";
    return NatsTlsConfig{enabled,env_value("CLOUDIFF_NATS_TLS_CA"),env_value("CLOUDIFF_NATS_TLS_CERT"),env_value("CLOUDIFF_NATS_TLS_KEY"),env_value("CLOUDIFF_NATS_TLS_EXPECTED_HOSTNAME")};
}
NatsClient::NatsClient(std::string url, NatsAuthConfig auth, NatsTlsConfig tls) {
    validate_auth(auth); validate_tls(tls);
    natsOptions* options=nullptr;
    check(natsOptions_Create(&options),"natsOptions_Create");
    try {
        check(natsOptions_SetURL(options,url.c_str()),"natsOptions_SetURL");
        check(natsOptions_SetUserInfo(options,auth.user.c_str(),auth.password.c_str()),"natsOptions_SetUserInfo");
        check(natsOptions_SetAllowReconnect(options,true),"natsOptions_SetAllowReconnect");
        check(natsOptions_SetMaxReconnect(options,86400),"natsOptions_SetMaxReconnect");
        check(natsOptions_SetReconnectWait(options,1000),"natsOptions_SetReconnectWait");
        check(natsOptions_SetReconnectJitter(options,250,1000),"natsOptions_SetReconnectJitter");
        if (tls.enabled) {
            check(natsOptions_SetSecure(options,true),"natsOptions_SetSecure");
            check(natsOptions_LoadCATrustedCertificates(options,tls.ca_file.c_str()),"natsOptions_LoadCATrustedCertificates");
            check(natsOptions_LoadCertificatesChain(options,tls.cert_file.c_str(),tls.key_file.c_str()),"natsOptions_LoadCertificatesChain");
            check(natsOptions_SetExpectedHostname(options,tls.expected_hostname.c_str()),"natsOptions_SetExpectedHostname");
        }
        check(natsConnection_Connect(&connection_,options),"natsConnection_Connect");
        natsOptions_Destroy(options);
    } catch (...) { natsOptions_Destroy(options); throw; }
}
NatsClient::~NatsClient(){ if(connection_!=nullptr)natsConnection_Destroy(connection_); }
void NatsClient::publish(std::string_view subject,std::string_view payload,int flush_timeout_ms){
    const std::string subj(subject),body(payload);
    check(natsConnection_PublishString(connection_,subj.c_str(),body.c_str()),"natsConnection_PublishString");
    check(natsConnection_FlushTimeout(connection_,flush_timeout_ms),"natsConnection_FlushTimeout");
}
}
