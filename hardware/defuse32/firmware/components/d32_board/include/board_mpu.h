/* GY-521 MPU-6050 (0x68) on the carrier: accelerometer and a simple tilt
 * angle against a reference orientation (captured at init, or on demand). */
#pragma once

#include <stdbool.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t board_mpu_init(void);
void board_mpu_deinit(void);
bool board_mpu_present(void);
/* Acceleration in g (range +-2 g). */
esp_err_t board_mpu_accel(float g[3]);
/* Store the current gravity vector as the "level" reference. */
esp_err_t board_mpu_set_reference(void);
/* tilt_deg: angle between gravity now and the reference (0-180).
 * pitch/roll: classic angles from the raw axes, degrees. Any pointer may be NULL. */
esp_err_t board_mpu_tilt(float *tilt_deg, float *pitch_deg, float *roll_deg);

#ifdef __cplusplus
}
#endif
