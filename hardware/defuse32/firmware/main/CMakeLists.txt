idf_component_register(SRCS "main.c" "console_cmds.c" "game.c"
                       INCLUDE_DIRS "."
                       PRIV_REQUIRES d32_board d32_pack d32_engine d32_modules ctf_core
                                     console esp_app_format esp_hw_support
                                     esp_system esp_timer freertos log)
target_compile_options(${COMPONENT_LIB} PRIVATE -Wall -Wextra)
