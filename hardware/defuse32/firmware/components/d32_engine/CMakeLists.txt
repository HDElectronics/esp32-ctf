# Portable C: no IDF/FreeRTOS includes. Also built by test/host on Linux.
idf_component_register(SRCS "d32_engine.c"
                       INCLUDE_DIRS "include"
                       REQUIRES ctf_core)
