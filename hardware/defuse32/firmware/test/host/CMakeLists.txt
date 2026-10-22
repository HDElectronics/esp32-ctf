cmake_minimum_required(VERSION 3.16)
project(d32_host_tests C)

# Host tests for the portable parts of the Defuse32 firmware:
#   d32_engine (links ctf_core from the repo root), the pure logic of
#   d32_modules (d32_mod_logic.c), the d32_board tilt math (board_tilt.c)
#   and the d32_pack parse core (needs cJSON).
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

set(FW_DIR ${CMAKE_CURRENT_LIST_DIR}/../..)
set(CTF_CORE_DIR ${FW_DIR}/../../../components/ctf_core)
set(D32_ENGINE_DIR ${FW_DIR}/components/d32_engine)
set(D32_MODULES_DIR ${FW_DIR}/components/d32_modules)
set(D32_PACK_DIR ${FW_DIR}/components/d32_pack)
set(D32_BOARD_DIR ${FW_DIR}/components/d32_board)
file(GLOB CTF_CORE_SRCS CONFIGURE_DEPENDS ${CTF_CORE_DIR}/*.c)
file(GLOB D32_ENGINE_SRCS CONFIGURE_DEPENDS ${D32_ENGINE_DIR}/*.c)
file(GLOB TEST_SRCS CONFIGURE_DEPENDS ${CMAKE_CURRENT_LIST_DIR}/test_*.c)

# cJSON for the pack parser tests, first match wins:
#   1. -DD32_CJSON_DIR=<dir with cJSON.c and cJSON.h>
#   2. the copy the ESP-IDF component manager put in
#      hardware/defuse32/firmware/managed_components/espressif__cjson/cJSON
#      (present after one `idf.py build` / `idf.py reconfigure`)
#   3. a system cJSON (e.g. Debian/Ubuntu libcjson-dev)
# Without any of them the `pack` group is skipped with a warning.
set(D32_CJSON_DIR "" CACHE PATH "Directory with cJSON.c and cJSON.h")
set(_managed_cjson ${FW_DIR}/managed_components/espressif__cjson/cJSON)
if(NOT D32_CJSON_DIR AND EXISTS ${_managed_cjson}/cJSON.c)
    set(D32_CJSON_DIR ${_managed_cjson})
endif()
set(HAVE_CJSON OFF)
if(D32_CJSON_DIR AND EXISTS ${D32_CJSON_DIR}/cJSON.c)
    # Third-party code: built on its own, without our -Werror.
    add_library(d32_cjson STATIC ${D32_CJSON_DIR}/cJSON.c)
    target_include_directories(d32_cjson PUBLIC ${D32_CJSON_DIR})
    set(HAVE_CJSON ON)
    message(STATUS "cJSON for the pack tests: ${D32_CJSON_DIR}")
else()
    find_path(CJSON_INCLUDE_DIR cJSON.h PATH_SUFFIXES cjson)
    find_library(CJSON_LIBRARY cjson)
    if(CJSON_INCLUDE_DIR AND CJSON_LIBRARY)
        add_library(d32_cjson INTERFACE)
        target_include_directories(d32_cjson INTERFACE ${CJSON_INCLUDE_DIR})
        target_link_libraries(d32_cjson INTERFACE ${CJSON_LIBRARY})
        set(HAVE_CJSON ON)
        message(STATUS "cJSON for the pack tests: system ${CJSON_LIBRARY}")
    endif()
endif()

if(NOT HAVE_CJSON)
    message(WARNING "cJSON not found: d32_pack tests skipped. Run `idf.py reconfigure` once in "
                    "hardware/defuse32/firmware (fetches managed_components) or pass -DD32_CJSON_DIR=<dir>.")
    list(FILTER TEST_SRCS EXCLUDE REGEX "test_pack\\.c$")
endif()

add_executable(d32_engine_tests ${TEST_SRCS} ${D32_ENGINE_SRCS} ${CTF_CORE_SRCS}
               ${D32_MODULES_DIR}/d32_mod_logic.c ${D32_BOARD_DIR}/board_tilt.c)
target_include_directories(d32_engine_tests PRIVATE
    ${D32_ENGINE_DIR}/include ${CTF_CORE_DIR}/include ${D32_MODULES_DIR}/include
    ${D32_PACK_DIR}/include ${CMAKE_CURRENT_LIST_DIR})
# d32_board: tests include only the portable board_tilt.h (board.h needs IDF).
target_include_directories(d32_engine_tests PRIVATE ${D32_BOARD_DIR}/include)
target_compile_options(d32_engine_tests PRIVATE -Wall -Wextra -Werror)
target_link_libraries(d32_engine_tests PRIVATE m)
if(HAVE_CJSON)
    target_sources(d32_engine_tests PRIVATE ${D32_PACK_DIR}/d32_pack_parse.c)
    target_compile_definitions(d32_engine_tests PRIVATE D32_HAVE_CJSON=1)
    target_link_libraries(d32_engine_tests PRIVATE d32_cjson)
endif()

enable_testing()
# One ctest entry per group; `d32_engine_tests` with no argument runs them all.
set(D32_GROUPS config phase timer codes wires frags events modlogic tilt)
if(HAVE_CJSON)
    list(APPEND D32_GROUPS pack)
endif()
foreach(group ${D32_GROUPS})
    add_test(NAME d32_${group} COMMAND d32_engine_tests ${group})
endforeach()
