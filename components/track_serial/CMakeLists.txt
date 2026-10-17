idf_component_register(SRCS "track_serial.c"
                       INCLUDE_DIRS "include"
                       PRIV_REQUIRES ctf_core ctf_platform console esp_driver_uart freertos log)
