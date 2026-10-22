# d32_pack_parse.c is portable (cJSON + libc): test/host can compile it on Linux.
idf_component_register(SRCS "d32_pack_parse.c" "d32_pack.c"
                       INCLUDE_DIRS "include"
                       PRIV_REQUIRES log vfs)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra)
