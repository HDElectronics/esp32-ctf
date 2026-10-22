/* Inputs behind the MCP23017s (SPEC rev 1b): 4x4 keypad (U2), Simon buttons
 * (U2), key switch (U2 GPB4), SD card detect (U2 GPB5), wire patch matrix
 * (U3), rotary encoder A/B (U3) and its switch (GPIO39). All MCP calls return
 * ESP_ERR_INVALID_STATE when the expander is absent.
 *
 * Strobe lines (keypad columns COL1-4 = U2 GPA4-6 + GPB6, wire posts WA1-6 =
 * U3 GPA0-4 + GPB6) emulate open drain: during a scan the active line is
 * driven low and every other strobe is an input (high impedance). Between
 * scans all strobes are driven low together. The output-only GPA7/GPB7 pins
 * are never strobes. */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define BOARD_KEYPAD_KEYS   16
#define BOARD_WIRE_POSTS    6

/* Raw keypad scan: bit (row * 4 + col) set when that key is down. */
esp_err_t board_keypad_scan(uint16_t *pressed);
/* Key char for a key index: overlay layout
 *   1 2 3 A
 *   4 5 6 B
 *   7 8 9 C
 *   0 F E D        ('?' for an out-of-range index) */
char board_keypad_char(int index);
/* Debounced poller: call every ~10 ms. Returns the char of a newly pressed
 * key (stable for 3 polls), or 0. */
char board_keypad_poll(void);

/* Wire patch matrix: conn[a] = bitmask of B posts (bit b = WB(b+1)) that are
 * connected to post WA(a+1). */
esp_err_t board_wires_scan(uint8_t conn[BOARD_WIRE_POSTS]);
/* B post index (0-5) connected to A post `a`, -1 if none, -2 if several. */
int board_wires_b_for_a(const uint8_t conn[BOARD_WIRE_POSTS], int a);

/* Rotary encoder (KY-040): call often (every 1-2 ms while turning matters;
 * A/B are polled over I2C). `steps` accumulates quadrature steps, one detent
 * is usually 4 steps. The switch (GPIO39) is updated even when U3 is absent
 * (the call then returns ESP_ERR_INVALID_STATE and leaves `steps` alone). */
typedef struct {
    int32_t steps;      /* accumulated quarter steps */
    bool pressed;       /* switch currently down */
    bool clicked;       /* press edge since the previous poll */
} board_encoder_t;
esp_err_t board_encoder_poll(board_encoder_t *enc);
/* GPIO39 setup (called by board_init) and the raw switch state (false while
 * the 3V3P rail is off). */
esp_err_t board_encoder_switch_init(void);
bool board_encoder_switch_down(void);

/* Simon buttons SIM1-4: bit n set when SIM(n+1) is pressed. */
esp_err_t board_simon_read(uint8_t *mask);
/* Key switch turned to ARM (polarity: CONFIG_D32_KEYSW_ARMED_LOW). */
esp_err_t board_keyswitch_armed(bool *armed);
/* microSD inserted according to DET (polarity: CONFIG_D32_SD_DET_ACTIVE_HIGH). */
esp_err_t board_sd_card_detected(bool *present);

#ifdef __cplusplus
}
#endif
