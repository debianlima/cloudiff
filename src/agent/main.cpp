#include "cloudiff/heartbeat.hpp"
#include "cloudiff/admin_observability.hpp"
#include "cloudiff/artifact_engine.hpp"
#include "cloudiff/nats_client.hpp"
#include "cloudiff/node_identity.hpp"
#include "cloudiff/npm_publisher_provider.hpp"
#include "cloudiff/mcp_upload.hpp"
#include "cloudiff/runtime_executor.hpp"
#include "cloudiff/secure_distribution.hpp"
#include <boost/asio.hpp>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

namespace {
std::string env_or(const char* name, std::string fallback={}) { const char* v=std::getenv(name); return v?std::string(v):std::move(fallback); }
int env_int(const char* name,int fallback) { try { return std::stoi(env_or(name,std::to_string(fallback))); } catch (...) { return fallback; } }
std::vector<std::string> split_caps(std::string value){std::vector<std::string> out;std::size_t start=0;while(start<=value.size()){auto end=value.find(',',start);auto item=value.substr(start,end==std::string::npos?std::string::npos:end-start);if(!item.empty())out.push_back(item);if(end==std::string::npos)break;start=end+1;}if(out.empty())out={"inventory","health","telemetry-host"};return out;}
}
int main(int argc,char** argv) {
    try {
        std::filesystem::path node_file="/etc/cloudiff-v2/node-id"; std::string role=env_or("CLOUDIFF_NODE_ROLE","other"); const auto capabilities=split_caps(env_or("CLOUDIFF_NODE_CAPABILITIES","inventory,health,telemetry-host")); bool once=false; bool publisher=false; bool artifact_executor=false; bool runtime_executor=false; bool mcp_upload=false; bool secure_distribution=false; bool admin_observability=false;
        for(int i=1;i<argc;++i){ std::string a=argv[i]; if(a=="--node-id-file"&&i+1<argc)node_file=argv[++i]; else if(a=="--role"&&i+1<argc)role=argv[++i]; else if(a=="--once")once=true; else if(a=="--publisher")publisher=true; else if(a=="--artifact-executor")artifact_executor=true; else if(a=="--runtime-executor")runtime_executor=true; else if(a=="--mcp-upload")mcp_upload=true; else if(a=="--secure-distribution")secure_distribution=true; else if(a=="--admin-observability")admin_observability=true; else if(a=="--version"){std::cout<<"cloudiff-agent 0.36.0-shadow\n";return 0;} }
        if(publisher) return cloudiff::run_npm_publisher_server(cloudiff::publisher_options_from_environment());
        if(artifact_executor) return cloudiff::run_artifact_engine_server(cloudiff::artifact_engine_options_from_environment());
        if(runtime_executor) return cloudiff::run_runtime_executor_server(cloudiff::runtime_executor_options_from_environment());
        if(mcp_upload) return cloudiff::run_mcp_upload_server(cloudiff::mcp_upload_options_from_environment());
        if(secure_distribution) return cloudiff::run_secure_distribution_server(cloudiff::secure_distribution_options_from_environment());
        if(admin_observability) return cloudiff::run_admin_observability_server(cloudiff::admin_observability_options_from_environment());
        const auto id=cloudiff::NodeIdentity::from_file(node_file);
        if(once){ std::cout<<cloudiff::make_node_observed_event(id,role,capabilities).at("payload").dump()<<'\n'; return 0; }
        const auto url=env_or("CLOUDIFF_NATS_URL"); const auto auth=cloudiff::nats_auth_from_environment();
        if(url.empty()||auth.user.empty()||auth.password.empty()) throw std::runtime_error("CLOUDIFF_NATS_URL/USER/PASSWORD required");
        cloudiff::NatsClient nats(url,auth,cloudiff::nats_tls_from_environment()); boost::asio::io_context io; boost::asio::signal_set signals(io,SIGINT,SIGTERM);
        signals.async_wait([&](const boost::system::error_code&,int){io.stop();});
        auto timer=std::make_shared<boost::asio::steady_timer>(io); const int interval=std::max(1,env_int("CLOUDIFF_HEARTBEAT_INTERVAL_SECONDS",15));
        std::function<void()> tick;
        tick=[&,timer]{
            try { auto ev=cloudiff::make_node_observed_event(id,role,capabilities); nats.publish("cloudiff.v2.node.observed",ev.dump()); }
            catch(const std::exception& e){ std::cerr<<"{\"service\":\"cloudiff-agent\",\"level\":\"error\",\"message\":\""<<e.what()<<"\"}\n"; }
            timer->expires_after(std::chrono::seconds(interval)); timer->async_wait([&](const boost::system::error_code& ec){if(!ec)tick();});
        };
        tick(); io.run(); return 0;
    } catch(const std::exception& e){ std::cerr<<"cloudiff-agent: "<<e.what()<<'\n'; return 2; }
}
