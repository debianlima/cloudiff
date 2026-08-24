#pragma once
#include <nlohmann/json.hpp>
#include <string>
#include <string_view>
#include <vector>

namespace cloudiff {
struct McpUploadOptions final {
    std::string bind_address{"127.0.0.1"};
    unsigned short port{18234};
    std::string token;
    std::vector<std::string> allowed_download_suffixes{"oaiusercontent.com","openai.com","chatgpt.com"};
};
struct McpUploadResponse final { int status{500}; nlohmann::json body; };
class McpUploadPlanner final {
public:
    explicit McpUploadPlanner(McpUploadOptions options);
    [[nodiscard]] McpUploadResponse handle(std::string_view method,std::string_view path,std::string_view authorization,std::string_view body) const;
private:
    McpUploadOptions options_;
};
[[nodiscard]] McpUploadOptions mcp_upload_options_from_environment();
int run_mcp_upload_server(const McpUploadOptions& options);
}
