#include "cloudiff/mcp_upload.hpp"
#include <cassert>
#include <string>

int main(){
    cloudiff::McpUploadPlanner p({"127.0.0.1",18234,"unit-secret",{"oaiusercontent.com","openai.com","chatgpt.com"}});
    auto r=p.handle("GET","/health","","");assert(r.status==200&&r.body.at("mode")=="shadow-plan-only"&&r.body.at("effects_enabled")==false);
    r=p.handle("POST","/v1/plan","Bearer wrong",R"({"requested_tool":"workspace.artifact.import"})");assert(r.status==401);
    const std::string sha(64,'a');
    const auto hydrated=nlohmann::json{{"requested_tool","workspace.artifact.import"},{"slug","laboratorio-de-hardware"},{"file",{{"download_url","https://files.oaiusercontent.com/abc?sig=temporary"},{"file_id","file_1234567890abcdef"},{"file_name","dados.zip"},{"mime_type","application/zip"}}},{"filename","dados.zip"},{"expected_size",1234},{"expected_sha256",sha},{"ttl_seconds",3600}}.dump();
    auto a=p.handle("POST","/v1/plan","Bearer unit-secret",hydrated);auto b=p.handle("POST","/v1/plan","Bearer unit-secret",hydrated);assert(a.status==200&&a.body==b.body);assert(a.body.at("mode")=="direct_https_stream"&&a.body.at("effective_tool")=="workspace.artifact.import"&&a.body.at("file_params_hydrated")==true&&a.body.at("filesystem_access_attempted")==false&&a.body.at("external_network_attempted")==false&&a.body.at("download_url_persisted")==false);assert(a.body.at("file").at("download_host")=="files.oaiusercontent.com"&&a.body.dump().find("temporary")==std::string::npos);
    const auto path_import=nlohmann::json{{"requested_tool","workspace.artifact.import"},{"slug","laboratorio-de-hardware"},{"file","/mnt/data/dados.zip"},{"filename","dados.zip"},{"expected_size",1234},{"expected_sha256",sha}}.dump();
    r=p.handle("POST","/v1/plan","Bearer unit-secret",path_import);assert(r.status==200&&r.body.at("mode")=="portal_upload_start"&&r.body.at("effective_tool")=="workspace.artifact.upload.start"&&r.body.at("automatic_fallback")==true&&r.body.at("fallback_reason")=="host_file_param_not_hydrated"&&r.body.at("file_shape").at("classification")=="mnt_data"&&r.body.dump().find("/mnt/data")==std::string::npos);
    const auto path_existing=nlohmann::json{{"requested_tool","workspace.artifact.upload.file"},{"slug","laboratorio-de-hardware"},{"artifact_id","art_111111111111111111111111"},{"file","sandbox:/mnt/data/dados.zip"}}.dump();
    r=p.handle("POST","/v1/plan","Bearer unit-secret",path_existing);assert(r.status==200&&r.body.at("mode")=="file_picker"&&r.body.at("effective_tool")=="workspace.artifact.upload.file.select"&&r.body.at("ui_resource")=="ui://cloudiff/artifact-upload-v1.html"&&r.body.dump().find("sandbox:")==std::string::npos);
    const auto existing_hydrated=nlohmann::json{{"requested_tool","workspace.artifact.upload.file"},{"slug","laboratorio-de-hardware"},{"artifact_id","art_111111111111111111111111"},{"file",{{"download_url","https://uploads.openai.com/file"},{"file_id","file_abcdef123456"}}}}.dump();
    r=p.handle("POST","/v1/plan","Bearer unit-secret",existing_hydrated);assert(r.status==200&&r.body.at("mode")=="direct_https_stream");
    for(const char* url:{"http://files.oaiusercontent.com/x","https://evil.example/x","https://user@files.oaiusercontent.com/x","https://files.oaiusercontent.com:8443/x"}){auto q=nlohmann::json::parse(hydrated);q["file"]["download_url"]=url;r=p.handle("POST","/v1/plan","Bearer unit-secret",q.dump());assert(r.status==422&&r.body.at("error")=="download_url_not_allowed");}
    auto scalar=nlohmann::json::parse(hydrated);scalar["file"]="https://files.oaiusercontent.com/x";r=p.handle("POST","/v1/plan","Bearer unit-secret",scalar.dump());assert(r.status==422&&r.body.at("error")=="openai_file_param_object_required");
    auto unknown=nlohmann::json::parse(hydrated);unknown["extra"]=1;r=p.handle("POST","/v1/plan","Bearer unit-secret",unknown.dump());assert(r.status==422&&r.body.at("error")=="unexpected_field");
    return 0;
}
