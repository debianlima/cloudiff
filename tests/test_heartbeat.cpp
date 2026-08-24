#include "cloudiff/heartbeat.hpp"
#include <cassert>
int main(){
  cloudiff::NodeIdentity id("988cbfab-6f23-4c53-975b-61bc2e638a75");
  auto e=cloudiff::make_node_observed_event(id,"edge",{"inventory","health","telemetry-host","portal-host"});
  assert(e.at("type")=="node.observed");
  assert(e.at("resource_id")==id.value());
  const auto& p=e.at("payload");
  assert(p.at("node_id")==id.value());
  assert(p.at("role")=="edge");
  assert(p.at("capabilities").size()==4);
  assert(p.at("telemetry").at("hierarchy")=="environment>node>container>service");
  assert(p.at("revision").get<long long>()>0);
  return 0;
}
