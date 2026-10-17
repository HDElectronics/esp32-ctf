idf_component_register(SRCS "track_hw.c"
                       INCLUDE_DIRS "include"
                       PRIV_REQUIRES log ctf_core console freertos esp_timer esp_rom
                                     esp_driver_gpio esp_driver_ledc
                                     esp_driver_touch_sens esp_driver_pcnt)
