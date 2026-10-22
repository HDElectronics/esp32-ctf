/* Board bring-up, teardown and the presence table. */
#include "board.h"

#include <stdio.h>
#include "esp_log.h"

static const char *TAG = "board";
static board_presence_t s_p;

esp_err_t board_init(void)
{
    /* Probe-plate W25Q32 CS: keep the flash deselected without fighting a
     * player's programmer on the header (input + pull-up, not driven). */
    gpio_config_t cs = {
        .pin_bit_mask = 1ULL << BOARD_PIN_FLASH_CS,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&cs);
    board_sd_park_cs();
    board_encoder_switch_init();

    s_p = (board_presence_t){ 0 };
    s_p.i2c_bus = board_i2c_init() == ESP_OK;
    board_mcp_init();
    s_p.mcp_u2 = board_mcp_present(BOARD_MCP_U2);
    s_p.mcp_u3 = board_mcp_present(BOARD_MCP_U3);
    board_oled_init();
    s_p.oled_m1 = board_oled_present(BOARD_OLED_M1);
    s_p.oled_m3 = board_oled_present(BOARD_OLED_M3);
    s_p.lis3dh = board_lis3dh_init() == ESP_OK;
    s_p.nfc = board_nfc_init() == ESP_OK;
    s_p.eeprom = board_i2c_probe(BOARD_I2C_ADDR_EEPROM) == ESP_OK;
    if (s_p.i2c_bus && !s_p.eeprom) {
        ESP_LOGW(TAG, "24C32 EEPROM (0x%02X) not found", BOARD_I2C_ADDR_EEPROM);
    }

    s_p.tm1637 = board_tm1637_init() == ESP_OK;
    s_p.leds = board_leds_init() == ESP_OK;
    s_p.buzzer = board_buzzer_init() == ESP_OK;
    s_p.servo = board_servo_init() == ESP_OK;
    s_p.touch = board_touch_init() == ESP_OK;
    s_p.ir = board_ir_init() == ESP_OK;
    s_p.ldr = board_ldr_init() == ESP_OK;
    board_presence();
    return ESP_OK;
}

void board_deinit(void)
{
    if (board_sd_mounted()) {
        board_sd_unmount();
    }
    board_uart2_deinit();
    board_ldr_deinit();
    board_ir_deinit();
    board_touch_deinit();
    board_servo_deinit();
    board_buzzer_deinit();
    board_leds_deinit();
    board_tm1637_deinit();
    board_nfc_deinit();
    board_lis3dh_deinit();
    board_oled_deinit();
    board_mcp_deinit();
    board_i2c_deinit();
    s_p = (board_presence_t){ 0 };
}

const board_presence_t *board_presence(void)
{
    bool det = false;
    s_p.sd_card = board_sd_card_detected(&det) == ESP_OK && det;
    s_p.sd_mounted = board_sd_mounted();
    return &s_p;
}

static void row(const char *name, const char *where, bool ok, const char *okword, const char *badword)
{
    printf("  %-24s %-7s %s\n", name, where, ok ? okword : badword);
}

void board_print_presence(void)
{
    const board_presence_t *p = board_presence();
    printf("  %-24s %-7s %s\n", "device", "where", "status");
    row("I2C bus / 3V3P rail", "21/22", p->i2c_bus, "ok", "DOWN (5 V input off?)");
    row("MCP23017 U2", "0x20", p->mcp_u2, "ok", "missing");
    row("MCP23017 U3", "0x21", p->mcp_u3, "ok", "missing");
    row("PN532 NFC (stub)", "0x24", p->nfc, "ok", "missing");
    row("SSD1306 OLED (M1)", "0x3C", p->oled_m1, "ok", "missing");
    row("SH1106 OLED (M3)", "0x3D", p->oled_m3, "ok", "missing");
    row("24C32 EEPROM (M5)", "0x50", p->eeprom, "ok", "missing");
    row("LIS3DH tilt", "0x19", p->lis3dh, "ok", "missing");
    row("TM1637 display (M2)", "32/33", p->tm1637, "ok", "missing");
    row("WS2812 chain x15", "25", p->leds, "driver ok (not probed)", "driver failed");
    row("buzzer", "26", p->buzzer, "ok", "driver failed");
    row("servo", "27", p->servo, "ok", "driver failed");
    row("touch T0/T4/T6/T3", "4..15", p->touch, "ok", "check pads");
    row("IR receiver", "34", p->ir, "driver ok (not probed)", "driver failed");
    row("LDR", "36", p->ldr, "ok", "driver failed");
    if (p->mcp_u2) {
        row("microSD card", "DET", p->sd_card, "inserted", "none");
    } else {
        row("microSD card", "DET", false, "", "unknown (U2 missing)");
    }
    row("microSD FATFS", "/sd", p->sd_mounted, "mounted", "not mounted");
}
