# Module adapters (one file per plate) + registry. d32_mod_logic.c is portable
# (no IDF headers) and is also built by test/host.
idf_component_register(SRCS "d32_modules.c" "d32_mod_logic.c"
                            "mod_radio.c" "mod_timer.c" "mod_keypad.c"
                            "mod_wires.c" "mod_probe.c" "mod_sensors.c"
                       INCLUDE_DIRS "include"
                       REQUIRES d32_engine
                       PRIV_REQUIRES d32_board ctf_core log)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra)
