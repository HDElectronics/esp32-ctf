#include "board.h"

#include "esp_log.h"
#include "led_strip.h"

static const char *TAG = "board_leds";

static led_strip_handle_t s_strip;
static uint8_t s_scale = 64;

esp_err_t board_leds_init(void)
{
    if (s_strip) {
        return ESP_OK;
    }
    led_strip_config_t sc = {
        .strip_gpio_num = BOARD_PIN_LED_DATA,
        .max_leds = BOARD_LED_COUNT,
        .led_model = LED_MODEL_WS2812,
        .color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_GRB,
        .flags.invert_out = false,  /* U4 is a non-inverting buffer */
    };
    led_strip_rmt_config_t rc = {
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = 10 * 1000 * 1000,
        .mem_block_symbols = 64,
        .flags.with_dma = false,    /* classic ESP32 RMT has no DMA */
    };
    esp_err_t err = led_strip_new_rmt_device(&sc, &rc, &s_strip);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "led_strip init failed: %s", esp_err_to_name(err));
        s_strip = NULL;
        return err;
    }
    led_strip_clear(s_strip);
    return ESP_OK;
}

void board_leds_deinit(void)
{
    if (s_strip) {
        led_strip_clear(s_strip);
        led_strip_del(s_strip);
        s_strip = NULL;
    }
}

bool board_leds_ready(void)
{
    return s_strip != NULL;
}

void board_leds_brightness(uint8_t scale)
{
    s_scale = scale;
}

static inline uint32_t sc(uint8_t v)
{
    return ((uint32_t)v * s_scale + 127) / 255;
}

esp_err_t board_leds_set(board_led_t led, uint8_t r, uint8_t g, uint8_t b)
{
    if (!s_strip) {
        return ESP_ERR_INVALID_STATE;
    }
    if (led >= BOARD_LED_COUNT) {
        return ESP_ERR_INVALID_ARG;
    }
    return led_strip_set_pixel(s_strip, led, sc(r), sc(g), sc(b));
}

esp_err_t board_leds_fill(uint8_t r, uint8_t g, uint8_t b)
{
    for (int i = 0; i < BOARD_LED_COUNT; i++) {
        esp_err_t err = board_leds_set((board_led_t)i, r, g, b);
        if (err != ESP_OK) {
            return err;
        }
    }
    return ESP_OK;
}

esp_err_t board_leds_show(void)
{
    return s_strip ? led_strip_refresh(s_strip) : ESP_ERR_INVALID_STATE;
}

esp_err_t board_leds_clear(void)
{
    return s_strip ? led_strip_clear(s_strip) : ESP_ERR_INVALID_STATE;
}
