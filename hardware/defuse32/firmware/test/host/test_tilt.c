/* d32_board portable tilt math (board_tilt.c): LIS3DH raw to g, reference,
 * tilt angle, pitch / roll. */
#include <math.h>

#include "board_tilt.h"
#include "test_util.h"

static bool near(float a, float b, float tol)
{
    return fabsf(a - b) <= tol;
}

static void test_lis3dh_raw(void)
{
    /* Normal mode +-2 g: 10-bit left-justified, 4 mg per digit. */
    CHECK(near(board_tilt_lis3dh_raw_to_g(0), 0.0f, 1e-6f));
    CHECK(near(board_tilt_lis3dh_raw_to_g(250 * 64), 1.0f, 1e-5f));      /* 250 digits = 1 g */
    CHECK(near(board_tilt_lis3dh_raw_to_g(-250 * 64), -1.0f, 1e-5f));
    CHECK(near(board_tilt_lis3dh_raw_to_g(64), 0.004f, 1e-6f));
    CHECK(near(board_tilt_lis3dh_raw_to_g(-64), -0.004f, 1e-6f));
    CHECK(near(board_tilt_lis3dh_raw_to_g(32767), 511 * 0.004f, 1e-5f));  /* full scale */
    CHECK(near(board_tilt_lis3dh_raw_to_g(-32768), -512 * 0.004f, 1e-5f));
}

static void test_reference(void)
{
    float ref[3] = {0.0f, 0.0f, 1.0f};
    const float g[3] = {0.0f, 0.6f, 0.8f};
    CHECK(board_tilt_set_ref(g, ref));
    CHECK(near(ref[0], 0.0f, 1e-6f) && near(ref[1], 0.6f, 1e-6f) && near(ref[2], 0.8f, 1e-6f));
    /* Scaled vector: same unit reference. */
    const float g2[3] = {0.0f, 1.2f, 1.6f};
    CHECK(board_tilt_set_ref(g2, ref));
    CHECK(near(ref[1], 0.6f, 1e-6f) && near(ref[2], 0.8f, 1e-6f));
    /* Free fall / garbage keeps the old reference. */
    const float weak[3] = {0.05f, 0.05f, 0.1f};
    CHECK(!board_tilt_set_ref(weak, ref));
    CHECK(near(ref[1], 0.6f, 1e-6f) && near(ref[2], 0.8f, 1e-6f));
    const float zero[3] = {0.0f, 0.0f, 0.0f};
    CHECK(!board_tilt_set_ref(zero, ref));
    const float nan3[3] = {NAN, 0.0f, 1.0f};
    CHECK(!board_tilt_set_ref(nan3, ref));
    CHECK(near(ref[1], 0.6f, 1e-6f));
}

static void test_angle(void)
{
    float ref[3];
    const float level[3] = {0.0f, 0.0f, 1.0f};
    CHECK(board_tilt_set_ref(level, ref));
    CHECK(near(board_tilt_angle(level, ref), 0.0f, 0.1f));
    /* Magnitude does not matter. */
    const float level2[3] = {0.0f, 0.0f, 1.3f};
    CHECK(near(board_tilt_angle(level2, ref), 0.0f, 0.1f));
    const float side[3] = {1.0f, 0.0f, 0.0f};
    CHECK(near(board_tilt_angle(side, ref), 90.0f, 0.1f));
    const float upside[3] = {0.0f, 0.0f, -1.0f};
    CHECK(near(board_tilt_angle(upside, ref), 180.0f, 0.1f));
    /* 30 degrees around X. */
    const float t30[3] = {0.0f, sinf(30.0f * 3.14159265f / 180.0f), cosf(30.0f * 3.14159265f / 180.0f)};
    CHECK(near(board_tilt_angle(t30, ref), 30.0f, 0.1f));
    /* Zero vector: 0, no NaN. */
    const float zero[3] = {0.0f, 0.0f, 0.0f};
    CHECK(near(board_tilt_angle(zero, ref), 0.0f, 1e-6f));
    /* Angle is relative to a non-vertical reference (case mounted sideways). */
    const float mount[3] = {0.0f, 1.0f, 0.0f};
    CHECK(board_tilt_set_ref(mount, ref));
    CHECK(near(board_tilt_angle(mount, ref), 0.0f, 0.1f));
    CHECK(near(board_tilt_angle(level, ref), 90.0f, 0.1f));
    /* Raw LIS3DH samples end to end: 1 g on Z vs ~0.5 g X / 0.866 g Z = 30 deg. */
    const float a[3] = {board_tilt_lis3dh_raw_to_g(0), board_tilt_lis3dh_raw_to_g(0),
                        board_tilt_lis3dh_raw_to_g(250 * 64)};
    const float b[3] = {board_tilt_lis3dh_raw_to_g(125 * 64), board_tilt_lis3dh_raw_to_g(0),
                        board_tilt_lis3dh_raw_to_g(217 * 64)};
    CHECK(board_tilt_set_ref(a, ref));
    CHECK(near(board_tilt_angle(b, ref), 30.0f, 0.5f));
}

static void test_pitch_roll(void)
{
    const float level[3] = {0.0f, 0.0f, 1.0f};
    CHECK(near(board_tilt_pitch(level), 0.0f, 0.1f));
    CHECK(near(board_tilt_roll(level), 0.0f, 0.1f));
    const float nose[3] = {-1.0f, 0.0f, 0.0f};
    CHECK(near(board_tilt_pitch(nose), 90.0f, 0.1f));
    const float right[3] = {0.0f, 1.0f, 0.0f};
    CHECK(near(board_tilt_roll(right), 90.0f, 0.1f));
}

void run_tilt_tests(void)
{
    RUN(test_lis3dh_raw);
    RUN(test_reference);
    RUN(test_angle);
    RUN(test_pitch_roll);
}
