#include "ctf_platform.h"
#include "ctf_platform_priv.h"

#include <string.h>
#include "ctf_core.h"
#include "esp_console.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "nvs.h"
#include "nvs_flash.h"

#define NVS_NS        "ctf"
#define NVS_KEY_PROG  "progress"
#define NVS_KEY_MODE  "mode"

static const char *TAG = "ctf_platform";

static nvs_handle_t s_nvs;
static bool s_nvs_ok;
static SemaphoreHandle_t s_lock;
static uint8_t s_mac[6];
static ctf_mode_t s_mode = CTF_MODE_RADIO;

static bool be_load(void *buf, size_t len, void *ctx)
{
    (void)ctx;
    if (!s_nvs_ok) {
        return false;
    }
    size_t sz = 0;
    if (nvs_get_blob(s_nvs, NVS_KEY_PROG, NULL, &sz) != ESP_OK || sz != len) {
        return false;
    }
    return nvs_get_blob(s_nvs, NVS_KEY_PROG, buf, &sz) == ESP_OK && sz == len;
}

static bool be_save(const void *buf, size_t len, void *ctx)
{
    (void)ctx;
    if (!s_nvs_ok) {
        return false;
    }
    if (nvs_set_blob(s_nvs, NVS_KEY_PROG, buf, len) != ESP_OK) {
        return false;
    }
    return nvs_commit(s_nvs) == ESP_OK;
}

static void be_lock(void *ctx)
{
    (void)ctx;
    xSemaphoreTake(s_lock, portMAX_DELAY);
}

static void be_unlock(void *ctx)
{
    (void)ctx;
    xSemaphoreGive(s_lock);
}

static const ctf_backend_t s_backend = {
    .load = be_load, .save = be_save, .lock = be_lock, .unlock = be_unlock, .ctx = NULL,
};

void ctf_platform_init(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    if (err == ESP_OK) {
        err = nvs_open(NVS_NS, NVS_READWRITE, &s_nvs);
    }
    s_nvs_ok = (err == ESP_OK);
    if (!s_nvs_ok) {
        ESP_LOGE(TAG, "NVS unavailable (%s): progress will not persist", esp_err_to_name(err));
    }

    uint8_t m = CTF_MODE_RADIO;
    if (s_nvs_ok && nvs_get_u8(s_nvs, NVS_KEY_MODE, &m) == ESP_OK && m == CTF_MODE_NET) {
        s_mode = CTF_MODE_NET;
    } else {
        s_mode = CTF_MODE_RADIO;
    }

    ESP_ERROR_CHECK(esp_efuse_mac_get_default(s_mac));

    s_lock = xSemaphoreCreateMutex();
    configASSERT(s_lock);
    ctf_init(s_mac, &s_backend);

    esp_console_config_t cfg = ESP_CONSOLE_CONFIG_DEFAULT();
    cfg.max_cmdline_length = 256;
    cfg.max_cmdline_args = 16;
    ESP_ERROR_CHECK(esp_console_init(&cfg));
    ESP_ERROR_CHECK(esp_console_register_help_command());
    ctf_commands_register();
}

void ctf_platform_mac(uint8_t mac[6])
{
    memcpy(mac, s_mac, 6);
}

ctf_mode_t ctf_platform_mode(void)
{
    return s_mode;
}

const char *ctf_platform_mode_name(ctf_mode_t mode)
{
    return mode == CTF_MODE_NET ? "net" : "radio";
}

void ctf_platform_set_mode_and_reboot(ctf_mode_t mode)
{
    if (s_nvs_ok) {
        if (nvs_set_u8(s_nvs, NVS_KEY_MODE, (uint8_t)mode) != ESP_OK || nvs_commit(s_nvs) != ESP_OK) {
            ESP_LOGE(TAG, "failed to save mode");
        }
    }
    printf("Switching to %s mode, rebooting...\n", ctf_platform_mode_name(mode));
    fflush(stdout);
    vTaskDelay(pdMS_TO_TICKS(100));
    esp_restart();
}
