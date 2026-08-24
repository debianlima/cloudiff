#include "cloudiff/secure_distribution.hpp"
#include <openssl/evp.h>
#include <array>
#include <cassert>
#include <filesystem>
#include <fstream>
#include <string>
#include <unistd.h>

namespace {
std::string sha256(std::string_view v){std::array<unsigned char,EVP_MAX_MD_SIZE>d{};unsigned int n=0;auto*c=EVP_MD_CTX_new();assert(c);assert(EVP_DigestInit_ex(c,EVP_sha256(),nullptr)==1);assert(EVP_DigestUpdate(c,v.data(),v.size())==1);assert(EVP_DigestFinal_ex(c,d.data(),&n)==1);EVP_MD_CTX_free(c);static constexpr char h[]="0123456789abcdef";std::string out(n*2,'0');for(unsigned int i=0;i<n;++i){out[i*2]=h[(d[i]>>4)&15];out[i*2+1]=h[d[i]&15];}return out;}
void write(const std::filesystem::path&p,std::string_view v){std::ofstream o(p,std::ios::binary);o<<v;o.close();}
}
int main(){
    const auto root=std::filesystem::temp_directory_path()/std::filesystem::path("cloudiff-dist-test-"+std::to_string(::getpid()));std::filesystem::create_directories(root);const auto cert=root/"fullchain.pem",key=root/"privkey.pem";write(cert,"CERT-A\n");write(key,"KEY-A\n");
    nlohmann::json catalog={{"version",1},{"collections",nlohmann::json::array({{{"id","nats-server-cert"},{"audiences",nlohmann::json::array({"node-a"})},{"members",nlohmann::json::array({{{"id","fullchain.pem"},{"path",cert.string()},{"media_type","application/x-pem-file"},{"max_bytes",65536}},{{"id","privkey.pem"},{"path",key.string()},{"media_type","application/x-pem-file"},{"max_bytes",65536}}})}}})}};
    const std::string token="unit-capability-token";nlohmann::json caps={{"version",1},{"capabilities",nlohmann::json::array({{{"audience","node-a"},{"token_sha256",sha256(token)},{"collections",nlohmann::json::array({"nats-server-cert"})},{"expires_at",2000}}})}};
    cloudiff::SecureDistributionProvider p(catalog,caps,[]{return 1000;});
    auto r=p.handle("GET","/health","","","");assert(r.status==200);
    r=p.handle("GET","/v1/collections/nats-server-cert/manifest","Bearer wrong","node-a","");assert(r.status==403);
    r=p.handle("GET","/v1/collections/nats-server-cert/manifest","Bearer "+token,"node-b","");assert(r.status==403);
    r=p.handle("GET","/v1/collections/nats-server-cert/manifest?token=x","Bearer "+token,"node-a","");assert(r.status==400);
    r=p.handle("POST","/v1/collections/nats-server-cert/manifest","Bearer "+token,"node-a","");assert(r.status==405);
    auto m1=p.handle("GET","/v1/collections/nats-server-cert/manifest","Bearer "+token,"node-a","");auto m2=p.handle("GET","/v1/collections/nats-server-cert/manifest","Bearer "+token,"node-a","");assert(m1.status==200&&m1.body==m2.body);auto mj=nlohmann::json::parse(m1.body);assert(mj.at("collection")=="nats-server-cert"&&mj.at("audience")=="node-a"&&mj.at("members").size()==2);const auto gen=mj.at("generation").get<std::string>();assert(gen.size()==64);
    r=p.handle("GET","/v1/collections/nats-server-cert/objects/fullchain.pem","Bearer "+token,"node-a","");assert(r.status==428);
    r=p.handle("GET","/v1/collections/nats-server-cert/objects/fullchain.pem","Bearer "+token,"node-a",gen);assert(r.status==200&&r.body=="CERT-A\n"&&r.headers.at("X-CloudIFF-SHA256")==sha256("CERT-A\n")&&r.headers.at("X-CloudIFF-Generation")==gen);
    r=p.handle("GET","/v1/collections/nats-server-cert/objects/../privkey.pem","Bearer "+token,"node-a",gen);assert(r.status==404);
    write(cert,"CERT-B\n");r=p.handle("GET","/v1/collections/nats-server-cert/objects/fullchain.pem","Bearer "+token,"node-a",gen);assert(r.status==409);auto m3=p.handle("GET","/v1/collections/nats-server-cert/manifest","Bearer "+token,"node-a","");assert(m3.status==200&&nlohmann::json::parse(m3.body).at("generation")!=gen);
    cloudiff::SecureDistributionProvider expired(catalog,caps,[]{return 3000;});r=expired.handle("GET","/v1/collections/nats-server-cert/manifest","Bearer "+token,"node-a","");assert(r.status==403);
    auto scoped=caps;scoped["capabilities"][0]["collections"]=nlohmann::json::array({"other"});cloudiff::SecureDistributionProvider denied(catalog,scoped,[]{return 1000;});r=denied.handle("GET","/v1/collections/nats-server-cert/manifest","Bearer "+token,"node-a","");assert(r.status==403);
    std::filesystem::remove_all(root);return 0;
}
