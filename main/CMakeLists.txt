idf_component_register(SRCS "main.c"
                       INCLUDE_DIRS "."
                       PRIV_REQUIRES heap log esp_system bt esp_wifi esp_netif esp_event nvs_flash esp_http_server
                                     ctf_core ctf_platform track_serial track_crypto track_hw
                                     track_re track_ble track_btc track_web)
