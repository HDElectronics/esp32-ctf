# Portable C: no IDF/FreeRTOS includes. Also built by test/host on Linux.
file(GLOB CTF_CORE_SRCS "${CMAKE_CURRENT_LIST_DIR}/*.c")
idf_component_register(SRCS ${CTF_CORE_SRCS}
                       INCLUDE_DIRS "include"
                       REQUIRES "")
