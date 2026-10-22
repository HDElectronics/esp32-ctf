/* Portable: no IDF headers (built by test/host too). */
#include "board_tilt.h"

#include <math.h>

#define RAD2DEG 57.2957795f

float board_tilt_lis3dh_raw_to_g(int16_t raw)
{
    /* Divide instead of shifting: right shift of a negative value is
     * implementation defined. The low 6 bits are zero in normal mode. */
    return (float)(raw / 64) * 0.004f;
}

static float norm3(const float g[3])
{
    return sqrtf(g[0] * g[0] + g[1] * g[1] + g[2] * g[2]);
}

bool board_tilt_set_ref(const float g[3], float ref[3])
{
    float n = norm3(g);
    if (!(n >= 0.2f)) {
        return false;
    }
    for (int i = 0; i < 3; i++) {
        ref[i] = g[i] / n;
    }
    return true;
}

float board_tilt_angle(const float g[3], const float ref[3])
{
    float n = norm3(g);
    float c = n > 0.0f ? (g[0] * ref[0] + g[1] * ref[1] + g[2] * ref[2]) / n : 1.0f;
    if (c > 1.0f) c = 1.0f;
    if (c < -1.0f) c = -1.0f;
    return acosf(c) * RAD2DEG;
}

float board_tilt_pitch(const float g[3])
{
    return atan2f(-g[0], sqrtf(g[1] * g[1] + g[2] * g[2])) * RAD2DEG;
}

float board_tilt_roll(const float g[3])
{
    return atan2f(g[1], g[2]) * RAD2DEG;
}
