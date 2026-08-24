#include "cloudiff/npm_publisher_provider.hpp"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <string>
#include <thread>
#include <vector>
#include <unistd.h>

int main(){
    const auto root=std::filesystem::temp_directory_path()/("cloudiff-publisher-test-"+std::to_string(::getpid()));
    std::filesystem::remove_all(root); std::filesystem::create_directories(root);
    const auto state_file=root/"state.json", nginx_file=root/"http.conf";
    nlohmann::json seed={
      {"projects",{{"1007",{{"active_deploy",3},{"stable_cert","cloudif-p1007"},{"versions",{{"3",{{"cert","cloudif-p1007-d3"}}}}}}}}},
      {"aliases",{{"labhard",{{"public_number",1007},{"active_deploy",3},{"cert","cloudif-alias-labhard"},{"versions",{{"3",{{"cert","cloudif-alias-labhard-d3"}}}}}}}}},
      {"stages",{{"1007-w1-preview",{{"public_number",1007},{"stage","preview"},{"number",1},{"cert","cloudif-stage-1007-w1-preview"}}}}},
      {"tenants",{{"tenantdemo",{{"cert","cloudif-tenant-tenantdemo"}}},{"aluno",{{"cert","cloudif-tenant-aluno"}}}}}
    };
    {std::ofstream out(state_file);out<<seed.dump(2)<<'\n';}
    cloudiff::PublisherOptions opts; opts.token="unit-secret"; opts.state_path=state_file; opts.nginx_conf_path=nginx_file; opts.dry_run=true;
    cloudiff::NpmPublisherProvider provider(opts);

    auto r=provider.handle("GET","/health","",""); assert(r.status==200); assert(r.body.at("service")=="cloudif-npm-publisher");
    r=provider.handle("POST","/publish","wrong",R"({"public_number":1010,"deploy_number":2})"); assert(r.status==403); assert(r.body.at("error")=="forbidden");
    r=provider.handle("POST","/missing","unit-secret","{}"); assert(r.status==404);

    r=provider.handle("POST","/version","unit-secret",R"({"public_number":1010,"deploy_number":2})"); assert(r.status==200); assert(r.body.at("version_url")=="https://1010-d2.cloudiff.duckdns.org/");
    r=provider.handle("POST","/stage","unit-secret",R"({"public_number":1010,"stage":"homologation","number":2})"); assert(r.status==200); assert(r.body.at("stage_code")=="H2");
    r=provider.handle("POST","/alias","unit-secret",R"({"public_number":1010,"deploy_number":2,"alias":"demoalias"})"); assert(r.status==200); assert(r.body.at("stable_url")=="https://demoalias.cloudiff.duckdns.org/");
    r=provider.handle("POST","/publish","unit-secret",R"({"public_number":1010,"deploy_number":2,"alias":"demoalias"})"); assert(r.status==200); assert(r.body.at("stable_url")=="https://1010.cloudiff.duckdns.org/");
    const auto state_after_publish=provider.state_snapshot();
    r=provider.handle("POST","/publish","unit-secret",R"({"public_number":1010,"deploy_number":2,"alias":"demoalias"})"); assert(r.status==200);
    assert(provider.state_snapshot().at("projects").at("1010").at("stable_cert")==state_after_publish.at("projects").at("1010").at("stable_cert"));

    r=provider.handle("POST","/tenant","unit-secret",R"({"tenant":"tenantnew"})"); assert(r.status==200); assert(r.body.at("certificate")=="cloudif-tenant-tenantnew");
    r=provider.handle("POST","/tenant","unit-secret",R"({"tenant":"TenantBad"})"); assert(r.status==422); assert(r.body.at("error")=="ValueError");
    r=provider.handle("POST","/alias","unit-secret",R"({"public_number":1010,"deploy_number":2,"alias":"1234"})"); assert(r.status==422); assert(r.body.at("detail")=="invalid_alias");
    r=provider.handle("POST","/stage","unit-secret",R"({"public_number":1010,"stage":"bad","number":1})"); assert(r.status==422);

    std::vector<std::thread> threads;
    for(int i=0;i<8;++i)threads.emplace_back([&provider,i]{auto x=provider.handle("POST","/version","unit-secret",nlohmann::json{{"public_number",2000+i},{"deploy_number",1}}.dump());assert(x.status==200);});
    for(auto& t:threads)t.join();
    auto snap=provider.state_snapshot(); for(int i=0;i<8;++i)assert(snap.at("projects").contains(std::to_string(2000+i)));

    std::ifstream nginx(nginx_file); std::string rendered((std::istreambuf_iterator<char>(nginx)),{});
    assert(rendered.find("server_name tenantdemo.cloudiff.duckdns.org;")!=std::string::npos);
    assert(rendered.find("server_name aluno.cloudiff.duckdns.org;")==std::string::npos);
    assert(rendered.find("proxy_pass http://10.62.92.7:8099;")!=std::string::npos);
    assert(rendered.find("server_name 1007.cloudiff.duckdns.org;")!=std::string::npos);
    assert(rendered.find("server_name 1007-d3.cloudiff.duckdns.org;")!=std::string::npos);
    assert(rendered.find("server_name 1007-w1-preview.cloudiff.duckdns.org;")!=std::string::npos);
    assert(rendered.find("server_name labhard.cloudiff.duckdns.org;")!=std::string::npos);
    assert(rendered.find("proxy_pass http://10.62.91.2:18150;")!=std::string::npos);
    assert(rendered.find("# CloudIF managed publications BEGIN")!=std::string::npos);
    assert(rendered.find("# CloudIF managed publications END")!=std::string::npos);

    r=provider.handle("POST","/unpublish","unit-secret",R"({"public_number":1010})"); assert(r.status==200); assert(r.body.at("removed")==true); assert(!provider.state_snapshot().at("aliases").contains("demoalias"));
    r=provider.handle("POST","/tenant/delete","unit-secret",R"({"tenant":"tenantnew"})"); assert(r.status==200); assert(r.body.at("removed")==true); assert(r.body.at("certificate_preserved")=="cloudif-tenant-tenantnew");

    const auto perms=std::filesystem::status(state_file).permissions(); assert((perms&std::filesystem::perms::group_read)==std::filesystem::perms::none); assert((perms&std::filesystem::perms::others_read)==std::filesystem::perms::none);
    snap=provider.state_snapshot(); for(const char* k:{"projects","aliases","stages","tenants"})assert(snap.contains(k)&&snap.at(k).is_object());

    // v9 live canary: preserve config outside managed markers and execute only fixed commands.
    const auto live_state=root/"live-state.json", live_conf=root/"live-http.conf";
    {std::ofstream out(live_state);out<<seed.dump(2)<<'\n';}
    const std::string original_conf="# OUTER PREFIX\n# CloudIF managed publications BEGIN\nold managed block\n# CloudIF managed publications END\n# OUTER SUFFIX\n";
    {std::ofstream out(live_conf);out<<original_conf;}
    cloudiff::PublisherOptions live=opts; live.state_path=live_state; live.nginx_conf_path=live_conf; live.dry_run=false;
    live.nginx_test_command={"/bin/true"}; live.nginx_reload_command={"/bin/true"};
    cloudiff::NpmPublisherProvider live_provider(live);
    r=live_provider.handle("POST","/unpublish","unit-secret",R"({"public_number":1007})"); assert(r.status==200);
    {std::ifstream in(live_conf);std::string text((std::istreambuf_iterator<char>(in)),{});assert(text.starts_with("# OUTER PREFIX\n"));assert(text.ends_with("# OUTER SUFFIX\n"));assert(text.find("server_name 1007.cloudiff.duckdns.org;")==std::string::npos);}
    bool found_backup=false;for(const auto& e:std::filesystem::directory_iterator(root))if(e.path().filename().string().starts_with("live-http.conf.bkp-v2-canary-"))found_backup=true;assert(found_backup);

    // Forced nginx -t failure must restore the exact previous config and leave state file uncommitted.
    {std::ofstream out(live_state,std::ios::trunc);out<<seed.dump(2)<<'\n';}{std::ofstream out(live_conf,std::ios::trunc);out<<original_conf;}
    cloudiff::PublisherOptions rollback=live; rollback.nginx_test_command={"/bin/false"}; rollback.nginx_reload_command={"/bin/true"};
    cloudiff::NpmPublisherProvider rollback_provider(rollback);
    r=rollback_provider.handle("POST","/unpublish","unit-secret",R"({"public_number":1007})"); assert(r.status==422); assert(r.body.at("error")=="RuntimeError");
    {std::ifstream in(live_conf);std::string text((std::istreambuf_iterator<char>(in)),{});assert(text==original_conf);}
    {std::ifstream in(live_state);nlohmann::json persisted;in>>persisted;assert(persisted.at("projects").contains("1007"));}

    // ACME issuance is intentionally not part of v9: missing/mismatched cert must fail closed.
    const auto cert_state=root/"cert-state.json", cert_conf=root/"cert-http.conf";
    {std::ofstream out(cert_state);out<<R"({"projects":{},"aliases":{},"stages":{},"tenants":{}})";}{std::ofstream out(cert_conf);out<<original_conf;}
    cloudiff::PublisherOptions no_acme=live; no_acme.state_path=cert_state; no_acme.nginx_conf_path=cert_conf; no_acme.certificate_root=root/"missing-certs";
    cloudiff::NpmPublisherProvider no_acme_provider(no_acme);
    r=no_acme_provider.handle("POST","/tenant","unit-secret",R"({"tenant":"wouldneedcert"})"); assert(r.status==422); assert(r.body.at("error")=="RuntimeError"); assert(r.body.at("detail")=="certificate_missing_or_mismatch_v10:cloudif-tenant-wouldneedcert");


    // v10 ACME: command is executed without shell, postcondition verifies SAN, and concurrent requests coalesce.
    const auto acme_root=root/"acme-certs", acme_state=root/"acme-state.json", acme_conf=root/"acme-http.conf", acme_count=root/"acme-count.txt", fake_certbot=root/"fake-certbot.sh";
    std::filesystem::create_directories(acme_root);
    {std::ofstream out(acme_state);out<<R"({"projects":{},"aliases":{},"stages":{},"tenants":{}})";}{std::ofstream out(acme_conf);out<<original_conf;}
    {
      std::ofstream sh(fake_certbot);
      sh<<"#!/bin/sh\nset -eu\nROOT='"<<acme_root.string()<<"'\nCOUNT='"<<acme_count.string()<<"'\nname=''\ndomain=''\n"
           "while [ $# -gt 0 ]; do case \"$1\" in --cert-name) name=\"$2\"; shift 2;; -d) [ -n \"$domain\" ] || domain=\"$2\"; shift 2;; *) shift;; esac; done\n"
           "[ -n \"$name\" ] && [ -n \"$domain\" ]\n"
           "n=0; [ ! -f \"$COUNT\" ] || n=$(cat \"$COUNT\"); echo $((n+1)) > \"$COUNT\"\n"
           "mkdir -p \"$ROOT/$name\"\n"
           "openssl req -x509 -nodes -newkey rsa:2048 -keyout \"$ROOT/$name/privkey.pem\" -out \"$ROOT/$name/fullchain.pem\" -days 1 -subj \"/CN=$domain\" -addext \"subjectAltName=DNS:$domain\" >/dev/null 2>&1\n";
    }
    std::filesystem::permissions(fake_certbot,std::filesystem::perms::owner_read|std::filesystem::perms::owner_write|std::filesystem::perms::owner_exec,std::filesystem::perm_options::replace);
    cloudiff::PublisherOptions acme=live;acme.state_path=acme_state;acme.nginx_conf_path=acme_conf;acme.certificate_root=acme_root;acme.acme_enabled=true;acme.certbot_command_prefix={fake_certbot.string()};
    cloudiff::NpmPublisherProvider acme_provider(acme);
    std::vector<std::thread> acme_threads;std::vector<int> acme_status(8,0);
    for(int i=0;i<8;++i)acme_threads.emplace_back([&acme_provider,&acme_status,i]{auto x=acme_provider.handle("POST","/tenant","unit-secret",R"({"tenant":"acmeunit"})");acme_status[static_cast<std::size_t>(i)]=x.status;});
    for(auto& t:acme_threads)t.join();for(int code:acme_status)assert(code==200);
    {std::ifstream in(acme_count);int count=0;in>>count;assert(count==1);}
    assert(std::filesystem::exists(acme_root/"cloudif-tenant-acmeunit"/"fullchain.pem"));
    assert(acme_provider.state_snapshot().at("tenants").contains("acmeunit"));

    // Certbot execution failure must fail closed before state/config commit.
    const auto fail_state=root/"acme-fail-state.json", fail_conf=root/"acme-fail-http.conf";
    {std::ofstream out(fail_state);out<<R"({"projects":{},"aliases":{},"stages":{},"tenants":{}})";}{std::ofstream out(fail_conf);out<<original_conf;}
    cloudiff::PublisherOptions acme_fail=live;acme_fail.state_path=fail_state;acme_fail.nginx_conf_path=fail_conf;acme_fail.certificate_root=root/"acme-fail-certs";acme_fail.acme_enabled=true;acme_fail.certbot_command_prefix={"/bin/false"};
    cloudiff::NpmPublisherProvider acme_fail_provider(acme_fail);
    r=acme_fail_provider.handle("POST","/tenant","unit-secret",R"({"tenant":"acmefail"})");assert(r.status==422);assert(r.body.at("error")=="RuntimeError");assert(r.body.at("detail").get<std::string>().starts_with("command_failed:/bin/false:"));
    {std::ifstream in(fail_state);nlohmann::json persisted;in>>persisted;assert(persisted.at("tenants").empty());}
    {std::ifstream in(fail_conf);std::string text((std::istreambuf_iterator<char>(in)),{});assert(text==original_conf);}

    // Successful command with no valid resulting certificate must fail the X509 postcondition.
    const auto mismatch_state=root/"acme-mismatch-state.json", mismatch_conf=root/"acme-mismatch-http.conf";
    {std::ofstream out(mismatch_state);out<<R"({"projects":{},"aliases":{},"stages":{},"tenants":{}})";}{std::ofstream out(mismatch_conf);out<<original_conf;}
    cloudiff::PublisherOptions mismatch=live;mismatch.state_path=mismatch_state;mismatch.nginx_conf_path=mismatch_conf;mismatch.certificate_root=root/"acme-mismatch-certs";mismatch.acme_enabled=true;mismatch.certbot_command_prefix={"/bin/true"};
    cloudiff::NpmPublisherProvider mismatch_provider(mismatch);
    r=mismatch_provider.handle("POST","/tenant","unit-secret",R"({"tenant":"acmemismatch"})");assert(r.status==422);assert(r.body.at("detail")=="certificate_san_mismatch:cloudif-tenant-acmemismatch");

    std::filesystem::remove_all(root); return 0;
}
