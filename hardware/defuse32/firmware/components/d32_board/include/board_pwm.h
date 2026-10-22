/* LEDC outputs: passive buzzer on GPIO26 (via Q1) and the SG90 servo on
 * GPIO27 (50 Hz). */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t board_buzzer_init(void);
void board_buzzer_deinit(void);
/* Start a tone and return immediately; it stops by itself after `ms`
 * (ms = 0: until board_buzzer_stop()). A new tone replaces the current one.
 * hz outside 50-10000 is rejected. */
esp_err_t board_buzzer_tone(uint32_t hz, uint32_t ms);
esp_err_t board_buzzer_stop(void);
bool board_buzzer_busy(void);

esp_err_t board_servo_init(void);
void board_servo_deinit(void);
/* 0-180 degrees (500-2500 us pulse). The servo stays unpowered (no pulses)
 * until the first call. */
esp_err_t board_servo_angle(int degrees);
esp_err_t board_servo_open(void);     /* CONFIG_D32_SERVO_OPEN_DEG */
esp_err_t board_servo_close(void);    /* CONFIG_D32_SERVO_CLOSED_DEG */
/* Stop the pulses (servo goes limp, saves current). */
esp_err_t board_servo_release(void);

#ifdef __cplusplus
}
#endif
