/* Capacitive touch pads on the sensor plate: T0 (GPIO4), T4 (GPIO13),
 * T6 (GPIO14), T3 (GPIO15), ESP-IDF touch_sens driver (touch V1). Readings
 * drop when a pad is touched; a pad counts as touched when its filtered value
 * is CONFIG_D32_TOUCH_THRESH_PCT percent below its calibration baseline. */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BOARD_TOUCH_PAD1 = 0,   /* T0, GPIO4 */
    BOARD_TOUCH_PAD2,       /* T4, GPIO13 */
    BOARD_TOUCH_PAD3,       /* T6, GPIO14 */
    BOARD_TOUCH_PAD4,       /* T3, GPIO15 */
    BOARD_TOUCH_COUNT
} board_touch_pad_t;

/* Starts continuous scanning and calibrates (keep hands off the pads). */
esp_err_t board_touch_init(void);
void board_touch_deinit(void);
bool board_touch_ready(void);
/* Re-measure the baselines (keep hands off). */
esp_err_t board_touch_calibrate(void);
/* Filtered reading. */
esp_err_t board_touch_read(board_touch_pad_t pad, uint32_t *value);
uint32_t board_touch_baseline(board_touch_pad_t pad);
bool board_touch_touched(board_touch_pad_t pad);
/* Bit n set when pad n is touched. */
uint8_t board_touch_mask(void);
/* Touch channel number (Tn) of a pad. */
int board_touch_channel(board_touch_pad_t pad);

#ifdef __cplusplus
}
#endif
