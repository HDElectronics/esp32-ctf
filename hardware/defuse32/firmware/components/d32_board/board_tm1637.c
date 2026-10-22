#include "board.h"

#include <stdio.h>
#include "esp_log.h"
#include "esp_rom_sys.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

static const char *TAG = "board_tm1637";

#define TM_DELAY_US     5
#define TM_CMD_DATA     0x40    /* write, auto increment */
#define TM_CMD_ADDR     0xC0    /* address 0 */
#define TM_CMD_DISPLAY  0x80    /* | 0x08 on | brightness 0-7 */

static bool s_present;
static bool s_pins_ready;
static uint8_t s_ctrl = TM_CMD_DISPLAY | 0x08 | 4;
static SemaphoreHandle_t s_lock;

static const uint8_t s_hex[16] = {
    0x3F, 0x06, 0x5B, 0x4F, 0x66, 0x6D, 0x7D, 0x07,
    0x7F, 0x6F, 0x77, 0x7C, 0x39, 0x5E, 0x79, 0x71,
};

uint8_t board_tm1637_glyph(char c)
{
    if (c >= '0' && c <= '9') return s_hex[c - '0'];
    if (c >= 'A' && c <= 'F') return s_hex[10 + c - 'A'];
    if (c >= 'a' && c <= 'f') return s_hex[10 + c - 'a'];
    if (c == '-') return 0x40;
    if (c == '_') return 0x08;
    return 0x00;
}

static inline void clk(int v) { gpio_set_level(BOARD_PIN_TM_CLK, v); esp_rom_delay_us(TM_DELAY_US); }
static inline void dio(int v) { gpio_set_level(BOARD_PIN_TM_DIO, v); esp_rom_delay_us(TM_DELAY_US); }

static void tm_start(void)
{
    dio(1);
    clk(1);
    dio(0);
    clk(0);
}

static void tm_stop(void)
{
    clk(0);
    dio(0);
    clk(1);
    dio(1);
}

/* LSB first; returns true when the chip pulled DIO low for the ACK. */
static bool tm_write(uint8_t b)
{
    for (int i = 0; i < 8; i++) {
        clk(0);
        dio(b & 1);
        clk(1);
        b >>= 1;
    }
    clk(0);
    dio(1);                 /* release DIO for the ACK */
    clk(1);
    bool ack = gpio_get_level(BOARD_PIN_TM_DIO) == 0;
    clk(0);
    return ack;
}

static bool tm_cmd(uint8_t c)
{
    tm_start();
    bool ack = tm_write(c);
    tm_stop();
    return ack;
}

static esp_err_t tm_show(const uint8_t seg[4])
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
    bool ok = tm_cmd(TM_CMD_DATA);
    tm_start();
    ok &= tm_write(TM_CMD_ADDR);
    for (int i = 0; i < 4; i++) {
        ok &= tm_write(seg[i]);
    }
    tm_stop();
    ok &= tm_cmd(s_ctrl);
    xSemaphoreGive(s_lock);
    return ok ? ESP_OK : ESP_ERR_TIMEOUT;
}

esp_err_t board_tm1637_init(void)
{
    if (!s_lock) {
        s_lock = xSemaphoreCreateMutex();
    }
    if (!s_pins_ready) {
        gpio_config_t io = {
            .pin_bit_mask = (1ULL << BOARD_PIN_TM_CLK) | (1ULL << BOARD_PIN_TM_DIO),
            .mode = GPIO_MODE_INPUT_OUTPUT_OD,
            .pull_up_en = GPIO_PULLUP_ENABLE,
            .pull_down_en = GPIO_PULLDOWN_DISABLE,
            .intr_type = GPIO_INTR_DISABLE,
        };
        gpio_config(&io);
        gpio_set_level(BOARD_PIN_TM_CLK, 1);
        gpio_set_level(BOARD_PIN_TM_DIO, 1);
        s_pins_ready = true;
    }
    const uint8_t blank[4] = { 0x40, 0x40, 0x40, 0x40 }; /* "----" */
    s_present = true;
    if (tm_show(blank) != ESP_OK) {
        s_present = false;
        ESP_LOGW(TAG, "no ACK on CLK=%d DIO=%d: display absent", BOARD_PIN_TM_CLK, BOARD_PIN_TM_DIO);
        return ESP_ERR_NOT_FOUND;
    }
    return ESP_OK;
}

void board_tm1637_deinit(void)
{
    if (s_present) {
        xSemaphoreTake(s_lock, portMAX_DELAY);
        tm_cmd(TM_CMD_DISPLAY); /* display off */
        xSemaphoreGive(s_lock);
    }
    s_present = false;
    if (s_pins_ready) {
        gpio_reset_pin(BOARD_PIN_TM_CLK);
        gpio_reset_pin(BOARD_PIN_TM_DIO);
        s_pins_ready = false;
    }
}

bool board_tm1637_present(void)
{
    return s_present;
}

esp_err_t board_tm1637_segments(const uint8_t seg[4])
{
    if (!s_present) {
        return ESP_ERR_INVALID_STATE;
    }
    return tm_show(seg);
}

esp_err_t board_tm1637_text(const char *four, bool colon)
{
    uint8_t seg[4] = { 0 };
    for (int i = 0; i < 4 && four && four[i]; i++) {
        seg[i] = board_tm1637_glyph(four[i]);
    }
    if (colon) {
        seg[1] |= 0x80;
    }
    return board_tm1637_segments(seg);
}

esp_err_t board_tm1637_time(int minutes, int seconds, bool colon)
{
    if (minutes < 0) minutes = 0;
    if (minutes > 99) minutes = 99;
    if (seconds < 0) seconds = 0;
    if (seconds > 59) seconds = 59;
    char t[5];
    snprintf(t, sizeof(t), "%02d%02d", minutes, seconds);
    return board_tm1637_text(t, colon);
}

esp_err_t board_tm1637_brightness(uint8_t level, bool on)
{
    if (!s_present) {
        return ESP_ERR_INVALID_STATE;
    }
    if (level > 7) {
        level = 7;
    }
    xSemaphoreTake(s_lock, portMAX_DELAY);
    s_ctrl = (uint8_t)(TM_CMD_DISPLAY | (on ? 0x08 : 0x00) | level);
    bool ok = tm_cmd(s_ctrl);
    xSemaphoreGive(s_lock);
    return ok ? ESP_OK : ESP_ERR_TIMEOUT;
}
