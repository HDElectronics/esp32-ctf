idf_component_register(SRCS "track_web.c" "web_http.c" "web_net.c"
                       INCLUDE_DIRS "include"
                       EMBED_TXTFILES "www/index.html" "www/page.html" "www/docs.html"
                                      "www/login.html" "www/diag.html" "www/submit.html"
                                      "www/robots.txt"
                       PRIV_REQUIRES log console esp_wifi esp_netif esp_event esp_http_server
                                     esp_timer heap spiffs lwip espressif__mdns
                                     ctf_core ctf_platform)
