idf_component_register(SRCS "ctf_platform.c" "ctf_console.c" "ctf_commands.c" "ctf_api.c"
                       INCLUDE_DIRS "include"
                       REQUIRES ctf_core console
                       PRIV_REQUIRES nvs_flash esp_driver_uart esp_hw_support esp_system
                                     esp_timer freertos log)
