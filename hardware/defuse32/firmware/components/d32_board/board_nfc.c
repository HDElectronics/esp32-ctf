/* PN532 stub: presence probe only (see board_nfc.h for the TODO). */
#include "board.h"

#include "esp_log.h"

static const char *TAG = "board_nfc";
static bool s_present;

esp_err_t board_nfc_init(void)
{
    s_present = board_i2c_ready() && board_i2c_probe(BOARD_I2C_ADDR_NFC) == ESP_OK;
    if (!s_present) {
        ESP_LOGW(TAG, "PN532 (0x%02X) not found", BOARD_I2C_ADDR_NFC);
        return ESP_ERR_NOT_FOUND;
    }
    ESP_LOGI(TAG, "PN532 answered at 0x%02X (driver not implemented yet)", BOARD_I2C_ADDR_NFC);
    return ESP_OK;
}

void board_nfc_deinit(void)
{
    s_present = false;
}

bool board_nfc_present(void)
{
    return s_present;
}
