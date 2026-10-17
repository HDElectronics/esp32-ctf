idf_component_register(SRCS "track_re.c"
                       INCLUDE_DIRS "include"
                       PRIV_REQUIRES log console nvs_flash esp_partition spiffs
                                     ctf_core ctf_platform)
