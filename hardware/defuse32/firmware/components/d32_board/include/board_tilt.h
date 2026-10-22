/* Portable tilt math (no IDF headers; also built by test/host): raw
 * accelerometer samples to g, the "level" reference and the tilt angle. */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* LIS3DH output register value (16-bit, left-justified) to g. In normal mode
 * at +-2 g the data is 10 bits (raw >> 6) at 4 mg per digit. */
float board_tilt_lis3dh_raw_to_g(int16_t raw);

/* Stores g normalised as the "level" reference. Returns false (ref unchanged)
 * when |g| < 0.2 g: free fall or garbage. */
bool board_tilt_set_ref(const float g[3], float ref[3]);

/* Angle in degrees (0-180) between g and the unit reference ref. A zero
 * vector gives 0. */
float board_tilt_angle(const float g[3], const float ref[3]);

/* Classic pitch / roll from the raw axes, degrees. */
float board_tilt_pitch(const float g[3]);
float board_tilt_roll(const float g[3]);

#ifdef __cplusplus
}
#endif
