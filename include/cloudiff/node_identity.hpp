#pragma once
#include <filesystem>
#include <string>
#include <string_view>

namespace cloudiff {
bool is_uuid(std::string_view value) noexcept;
class NodeIdentity final {
public:
    static NodeIdentity from_file(const std::filesystem::path& path);
    explicit NodeIdentity(std::string value);
    [[nodiscard]] const std::string& value() const noexcept { return value_; }
private:
    std::string value_;
};
}
