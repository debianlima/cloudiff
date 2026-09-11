if(NOT DEFINED AGENT OR AGENT STREQUAL "")
  message(FATAL_ERROR "AGENT executable path is required")
endif()

set(node_id "988cbfab-6f23-4c53-975b-61bc2e638a75")
set(node_file "${CMAKE_CURRENT_BINARY_DIR}/cloudiff-agent-once-node-id.txt")
file(WRITE "${node_file}" "${node_id}\n")

execute_process(
  COMMAND "${CMAKE_COMMAND}" -E env
          "CLOUDIFF_NODE_CAPABILITIES=inventory,health,telemetry-host"
          "${AGENT}" --node-id-file "${node_file}" --role shadow --once
  RESULT_VARIABLE rc
  OUTPUT_VARIABLE out
  ERROR_VARIABLE err
  OUTPUT_STRIP_TRAILING_WHITESPACE
  ERROR_STRIP_TRAILING_WHITESPACE
)
file(REMOVE "${node_file}")

if(NOT rc EQUAL 0)
  message(FATAL_ERROR "cloudiff-agent --once failed rc=${rc}: ${err}")
endif()

string(JSON observed_node ERROR_VARIABLE json_error GET "${out}" node_id)
if(json_error)
  message(FATAL_ERROR "invalid --once JSON: ${json_error}")
endif()
if(NOT observed_node STREQUAL node_id)
  message(FATAL_ERROR "node_id mismatch: ${observed_node}")
endif()

string(JSON role GET "${out}" role)
if(NOT role STREQUAL "shadow")
  message(FATAL_ERROR "role mismatch: ${role}")
endif()

string(JSON cap_count LENGTH "${out}" capabilities)
if(NOT cap_count EQUAL 3)
  message(FATAL_ERROR "unexpected capability count: ${cap_count}")
endif()
foreach(index RANGE 0 2)
  string(JSON cap_${index} GET "${out}" capabilities ${index})
endforeach()
if(NOT cap_0 STREQUAL "inventory" OR
   NOT cap_1 STREQUAL "health" OR
   NOT cap_2 STREQUAL "telemetry-host")
  message(FATAL_ERROR "capability contract mismatch")
endif()

string(JSON revision_type TYPE "${out}" revision)
if(NOT revision_type STREQUAL "NUMBER")
  message(FATAL_ERROR "revision must be numeric")
endif()
string(JSON ram_total GET "${out}" system ram_total_bytes)
string(JSON root_capacity GET "${out}" system root_capacity_bytes)
if(ram_total LESS_EQUAL 0 OR root_capacity LESS_EQUAL 0)
  message(FATAL_ERROR "telemetry totals must be positive")
endif()

message(STATUS "CLOUDIFF_AGENT_ONCE=PASS")
