#include "cloudiff/node_identity.hpp"
#include <cassert>
#include <fstream>
#include <stdexcept>
#include <string>
int main() {
    assert(cloudiff::is_uuid("988cbfab-6f23-4c53-975b-61bc2e638a75"));
    assert(!cloudiff::is_uuid("4478c580d2a3456c895c607d559de74a"));
    const std::string path="/tmp/cloudiff-node-id-test";
    { std::ofstream f(path); f << "988cbfab-6f23-4c53-975b-61bc2e638a75\n"; }
    auto id=cloudiff::NodeIdentity::from_file(path);
    assert(id.value()=="988cbfab-6f23-4c53-975b-61bc2e638a75");
    bool threw=false; try { cloudiff::NodeIdentity bad("not-a-node-id"); } catch (const std::invalid_argument&) { threw=true; }
    assert(threw);
    return 0;
}
