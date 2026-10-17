idf_component_register(SRCS "track_btc.c"
                       INCLUDE_DIRS "include"
                       PRIV_REQUIRES bt log esp_timer heap ctf_core ctf_platform track_ble)
