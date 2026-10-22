/* WS2812 chain (15 LEDs) on GPIO25 via U4, RMT backend of espressif/led_strip.
 * Indices follow the SPEC chain order. Writes go to a buffer; call
 * board_leds_show() to latch them. A missing chain cannot be detected. */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BOARD_LED_RADIO_LINK1 = 0,  /* M1 radio link LEDs */
    BOARD_LED_RADIO_LINK2,
    BOARD_LED_RADIO_STATUS,     /* M1 */
    BOARD_LED_STRIKE1,          /* M2 timer strikes */
    BOARD_LED_STRIKE2,
    BOARD_LED_STRIKE3,
    BOARD_LED_TIMER_STATUS,     /* M2 */
    BOARD_LED_KEYPAD_STATUS,    /* M3 */
    BOARD_LED_WIRES_STATUS,     /* M4 */
    BOARD_LED_PROBE_STATUS,     /* M5 */
    BOARD_LED_SIMON1,           /* M6 Simon buttons */
    BOARD_LED_SIMON2,
    BOARD_LED_SIMON3,
    BOARD_LED_SIMON4,
    BOARD_LED_SENSOR_STATUS,    /* M6 */
    BOARD_LED_COUNT             /* 15 */
} board_led_t;

esp_err_t board_leds_init(void);
void board_leds_deinit(void);
bool board_leds_ready(void);

/* Global brightness scale 0-255 applied on set (default 64: the chain runs
 * off the 5 V rail next to the servo). */
void board_leds_brightness(uint8_t scale);
esp_err_t board_leds_set(board_led_t led, uint8_t r, uint8_t g, uint8_t b);
esp_err_t board_leds_fill(uint8_t r, uint8_t g, uint8_t b);
esp_err_t board_leds_show(void);
/* All off, latched immediately. */
esp_err_t board_leds_clear(void);

#ifdef __cplusplus
}
#endif
