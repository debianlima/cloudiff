#pragma once
#include <nats/nats.h>
#include <string>
#include <string_view>

namespace cloudiff {
struct NatsAuthConfig final {
    std::string user;
    std::string password;
};
struct NatsTlsConfig final {
    bool enabled{false};
    std::string ca_file;
    std::string cert_file;
    std::string key_file;
    std::string expected_hostname;
};
[[nodiscard]] NatsAuthConfig nats_auth_from_environment();
[[nodiscard]] NatsTlsConfig nats_tls_from_environment();
class NatsClient final {
public:
    NatsClient(std::string url, NatsAuthConfig auth, NatsTlsConfig tls = {});
    ~NatsClient();
    NatsClient(const NatsClient&) = delete;
    NatsClient& operator=(const NatsClient&) = delete;
    NatsClient(NatsClient&&) = delete;
    NatsClient& operator=(NatsClient&&) = delete;
    void publish(std::string_view subject, std::string_view payload, int flush_timeout_ms = 2000);
    [[nodiscard]] natsConnection* native() noexcept { return connection_; }
private:
    natsConnection* connection_{nullptr};
};
}
