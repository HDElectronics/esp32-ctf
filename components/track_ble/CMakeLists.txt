idf_component_register(SRCS "track_ble.c"
                       INCLUDE_DIRS "include"
                       PRIV_REQUIRES bt log esp_timer heap console ctf_core ctf_platform)
