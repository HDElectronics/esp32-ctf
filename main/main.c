#include <stdio.h>
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_idf_version.h"
#include "esp_system.h"
#include "ctf_core.h"
#include "ctf_platform.h"
#include "track_serial.h"
#include "track_crypto.h"
#include "track_hw.h"
#include "track_re.h"
#include "track_ble.h"
#include "track_btc.h"
#include "track_web.h"
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

/* SER-01: boot log noise with the flag scrolled in the middle (SPEC "Serial"). */
static void print_boot_banner(void)
{
    char flag[18];
    ctf_flag("SER-01", flag);

    ESP_LOGI("cpu_start", "Multicore app, app cpu up");
    ESP_LOGI("clk", "RTC_SLOW_CLK: internal 150k, CPU 160 MHz, APB 80 MHz");
    ESP_LOGI("efuse", "pkg D0WD, 2 cores, BT/BLE, Wi-Fi");
    ESP_LOGI("spi_flash", "detected chip: generic, 4 MB, mode DIO @ 40 MHz");
    ESP_LOGI("part_tbl", "nvs      data/nvs     0x009000 0x006000");
    ESP_LOGI("part_tbl", "phy_init data/phy     0x00f000 0x001000");
    ESP_LOGI("part_tbl", "factory  app/factory  0x010000 0x280000");
    ESP_LOGI("part_tbl", "notes    data/0x40    0x290000 0x001000");
    ESP_LOGI("part_tbl", "storage  data/spiffs  0x291000 0x16f000");
    ESP_LOGI("heap_init", "region 0x3ffae6e0 len 0x00001920 (DRAM)");
    ESP_LOGI("heap_init", "region 0x3ffb8000 len 0x00028000 (DRAM)");
    ESP_LOGI("gpio_drv", "matrix init ok, 34 pads, iomux default");
    ESP_LOGI("adc_cal", "eFuse Vref 1100 mV, two-point: not burned");
    ESP_LOGI("sys_diag", "selftest token %s (ok)", flag);
    ESP_LOGI("touch_drv", "T0..T9 baseline captured, filter IIR 16");
    ESP_LOGI("ledc", "timer0 5 kHz 13-bit, ch0 idle");
    ESP_LOGI("uart", "uart0 115200 8N1, rx fifo 128, tx fifo 128");
    ESP_LOGI("uart", "uart2 reserved (gpio16/17)");
    ESP_LOGI("nvs", "namespace 'ctf' opened, 1 entries");
    ESP_LOGI("rtc_wdt", "disabled, task wdt 5 s on idle0/idle1");
    ESP_LOGI("pm", "dfs disabled, light sleep disabled");
    ESP_LOGI("phy_init", "calibration data: cached (0x0f000)");
    ESP_LOGI("coexist", "sw coex v0.9, prefer balance");
    ESP_LOGI("app_init", "esp32_ctf, IDF %s", esp_get_idf_version());
    ESP_LOGI("main_task", "started on cpu 0, calling app_main()");

    uint8_t mac[6];
    ctf_platform_mac(mac);
    printf("\n"
           "==========================================\n"
           "  ESP32 CTF\n"
           "  mode: %s\n"
           "  board MAC: %02X:%02X:%02X:%02X:%02X:%02X\n"
           "  type `help` to get started\n"
           "==========================================\n\n",
           ctf_platform_mode_name(ctf_platform_mode()),
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

void app_main(void)
{
    ctf_platform_init();
    print_boot_banner();

    /* Always-on tracks. */
    track_serial_start();
    track_crypto_start();
    track_hw_start();
    track_re_start();

    /* Mode tracks (never Wi-Fi in radio mode, never Bluetooth in net mode). */
    if (ctf_platform_mode() == CTF_MODE_RADIO) {
        track_ble_start();
        track_btc_start(); /* needs track_ble's Bluedroid init */
    } else {
        track_web_start();
    }

    ESP_LOGI(TAG, "free heap (8-bit): %u bytes",
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_8BIT));
    ctf_console_start();
#if CONFIG_CTF_SIZE_PROBE
    static volatile int run_probe = 0;
    if (run_probe) {
        ctf_size_probe();
    }
#endif
}
