#include "cloudiff/node_identity.hpp"
#include <cctype>
#include <fstream>
#include <stdexcept>

namespace cloudiff {
namespace {
bool is_hex(char c) noexcept {
    const auto u = static_cast<unsigned char>(c);
    return std::isxdigit(u) != 0;
}
std::string trim(std::string value) {
    while (!value.empty() && std::isspace(static_cast<unsigned char>(value.back())) != 0) value.pop_back();
    std::size_t start = 0;
    while (start < value.size() && std::isspace(static_cast<unsigned char>(value[start])) != 0) ++start;
    return value.substr(start);
}
}
bool is_uuid(std::string_view value) noexcept {
    if (value.size() != 36) return false;
    for (std::size_t i = 0; i < value.size(); ++i) {
        if (i == 8 || i == 13 || i == 18 || i == 23) {
            if (value[i] != '-') return false;
        } else if (!is_hex(value[i])) {
            return false;
        }
    }
    return true;
}
NodeIdentity::NodeIdentity(std::string value) : value_(trim(std::move(value))) {
    if (!is_uuid(value_)) throw std::invalid_argument("invalid CloudIFF node_id");
}
NodeIdentity NodeIdentity::from_file(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot open node_id file: " + path.string());
    std::string value;
    std::getline(input, value);
    return NodeIdentity(std::move(value));
}
}
