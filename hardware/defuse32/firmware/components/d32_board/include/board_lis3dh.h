/* LIS3DH accelerometer on the carrier (rev 2): I2C 0x19 (SA0 high), CS high
 * (I2C mode), INT1/INT2 not connected, so it is polled. Normal mode, 50 Hz,
 * +-2 g. Tilt is the angle against a reference orientation (captured at
 * init, or on demand). */
#pragma once

#include <stdbool.h>
#include "esp_err.h"
#include "board_tilt.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t board_lis3dh_init(void);
void board_lis3dh_deinit(void);
bool board_lis3dh_present(void);
/* Acceleration in g (range +-2 g, 4 mg resolution). */
esp_err_t board_lis3dh_accel(float g[3]);
/* Store the current gravity vector as the "level" reference. */
esp_err_t board_lis3dh_set_reference(void);
/* tilt_deg: angle between gravity now and the reference (0-180).
 * pitch/roll: classic angles from the raw axes, degrees. Any pointer may be NULL. */
esp_err_t board_lis3dh_tilt(float *tilt_deg, float *pitch_deg, float *roll_deg);

#ifdef __cplusplus
}
#endif
