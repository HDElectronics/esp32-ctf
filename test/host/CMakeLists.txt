cmake_minimum_required(VERSION 3.16)
project(ctf_core_host_tests C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

set(CTF_CORE_DIR ${CMAKE_CURRENT_LIST_DIR}/../../components/ctf_core)
file(GLOB CTF_CORE_SRCS CONFIGURE_DEPENDS ${CTF_CORE_DIR}/*.c)
file(GLOB TEST_SRCS CONFIGURE_DEPENDS ${CMAKE_CURRENT_LIST_DIR}/test_*.c)

add_executable(ctf_core_tests ${TEST_SRCS} ${CTF_CORE_SRCS})
target_include_directories(ctf_core_tests PRIVATE ${CTF_CORE_DIR}/include ${CMAKE_CURRENT_LIST_DIR})
target_compile_options(ctf_core_tests PRIVATE -Wall -Wextra -Werror)

enable_testing()
add_test(NAME ctf_core_tests COMMAND ctf_core_tests)
