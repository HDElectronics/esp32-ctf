/* GL5528 LDR divider on GPIO36 (ADC1_CH0), oneshot ADC driver. More light
 * = lower LDR resistance = higher voltage. */
#pragma once

#include <stdbool.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t board_ldr_init(void);
void board_ldr_deinit(void);
bool board_ldr_ready(void);
/* raw: 0-4095. mv: calibrated millivolts, or -1 without calibration (either
 * pointer may be NULL). */
esp_err_t board_ldr_read(int *raw, int *mv);

#ifdef __cplusplus
}
#endif
