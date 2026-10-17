#include <stdio.h>
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "sdkconfig.h"

#if CONFIG_CTF_SIZE_PROBE
#include "esp_bt.h"
#include "esp_bt_main.h"
#include "esp_gatts_api.h"
#include "esp_spp_api.h"
#include "esp_wifi.h"
#include "esp_http_server.h"
#include "mdns.h"

/* Never runs: referenced through a volatile flag so the linker keeps the stacks. */
static void ctf_size_probe(void)
{
    esp_bt_controller_config_t bt_cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    esp_bt_controller_init(&bt_cfg);
    esp_bt_controller_enable(ESP_BT_MODE_BTDM);
    esp_bluedroid_init();
    esp_bluedroid_enable();
    esp_ble_gatts_register_callback(NULL);
    esp_ble_gatts_app_register(0);
    esp_spp_cfg_t spp_cfg = { .mode = ESP_SPP_MODE_CB, .enable_l2cap_ertm = true };
    esp_spp_enhanced_init(&spp_cfg);
    esp_spp_start_srv(ESP_SPP_SEC_NONE, ESP_SPP_ROLE_SLAVE, 0, "probe");

    wifi_init_config_t wifi_cfg = WIFI_INIT_CONFIG_DEFAULT();
    esp_wifi_init(&wifi_cfg);
    esp_wifi_set_mode(WIFI_MODE_AP);
    esp_wifi_start();

    httpd_handle_t server = NULL;
    httpd_config_t http_cfg = HTTPD_DEFAULT_CONFIG();
    httpd_start(&server, &http_cfg);

    mdns_init();
    mdns_hostname_set("probe");
}
#endif

static const char *TAG = "ctf";

void app_main(void)
{
    ESP_LOGI(TAG, "ESP32 CTF scaffold: hello");
    ESP_LOGI(TAG, "free heap (8-bit): %u bytes",
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_8BIT));
#if CONFIG_CTF_SIZE_PROBE
    static volatile int run_probe = 0;
    if (run_probe) {
        ctf_size_probe();
    }
#endif
}
