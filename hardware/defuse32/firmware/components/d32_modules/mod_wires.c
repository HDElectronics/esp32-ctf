/* M4 wires adapter (variant "patch-a"), v0.
 *
 * Each coloured lead stays in its A post: WA1 red, WA2 blue, WA3 yellow,
 * WA4 green, WA5 white, WA6 black (wire index = A post index, the engine's
 * colour order). Players move the B ends.
 *
 * Challenge (ARMED, M4 armed): patch every A post to the B post of the round's
 * pattern (d32_patch_pattern(), hinted in the M5 UART2 banner). When the
 * matrix matches for two scans in a row, the M4 code appears on the keypad
 * OLED.
 *
 * Final wire (FINAL, any variant, also with M4 disabled in the pack): an A post that was connected and reads
 * unconnected for two scans in a row is a pulled lead: d32_wire_pulled(a).
 * Before FINAL, moving leads is part of the patch puzzle and never strikes. */
#include <stdio.h>
#include <string.h>

#include "board.h"
#include "d32_mod_internal.h"
#include "d32_mod_logic.h"
#include "esp_log.h"

static const char *TAG = "mod_wires";

#define SCAN_MS   100
#define STABLE    2     /* scans */

static bool s_patch;            /* variant "patch-a" */
static bool s_armed;            /* pattern valid for this round */
static uint8_t s_pattern[D32_ML_POSTS];
static bool s_revealed;
static uint8_t s_match_count;
static uint8_t s_gone[D32_ML_POSTS];  /* consecutive scans unconnected after being connected */
static bool s_connected[D32_ML_POSTS];
static bool s_scan_ok;
static uint32_t s_next_scan;
static bool s_warned;

bool d32_mod_wires_hint(char *out, size_t cap)
{
    if (!s_patch || !s_armed) {
        return false;
    }
    return d32_patch_hint(s_pattern, out, cap) > 0;
}

static bool w_configure(int slot, const char *variant)
{
    (void)slot;
    s_patch = variant && strcmp(variant, "patch-a") == 0;
    s_armed = false;
    return s_patch;
}

static void w_arm(d32_t *d, int slot, uint32_t seed)
{
    (void)d;
    (void)slot;
    s_armed = false;
    if (s_patch) {
        d32_patch_pattern(seed, s_pattern);
        s_armed = true;
    }
    s_revealed = false;
    s_match_count = 0;
    memset(s_gone, 0, sizeof(s_gone));
    memset(s_connected, 0, sizeof(s_connected));
}

static void check_pulls(d32_t *d, const uint8_t conn[D32_ML_POSTS])
{
    for (int a = 0; a < D32_ML_POSTS; a++) {
        if (conn[a]) {
            s_connected[a] = true;
            s_gone[a] = 0;
            continue;
        }
        if (!s_connected[a]) {
            continue;
        }
        if (++s_gone[a] >= STABLE) {
            s_connected[a] = false;
            s_gone[a] = 0;
            d32_wire_result_t r = d32_wire_pulled(d, a);
            ESP_LOGI(TAG, "lead WA%d (%s) pulled: result %d", a + 1, d32_wire_colour(a), (int)r);
            return; /* one pull per scan; the round is over after it anyway */
        }
    }
}

static void w_poll(d32_t *d, int slot, uint32_t now_ms)
{
    if ((int32_t)(now_ms - s_next_scan) < 0) {
        return;
    }
    s_next_scan = now_ms + SCAN_MS;
    uint8_t conn[BOARD_WIRE_POSTS];
    if (board_wires_scan(conn) != ESP_OK) {
        if (!s_warned) {
            ESP_LOGW(TAG, "wire matrix unreadable (U3 missing): use the console `wire <0-5>`");
            s_warned = true;
        }
        s_scan_ok = false;
        return;
    }
    s_scan_ok = true;
    d32_phase_t ph = d32_phase(d);
    if (ph == D32_FINAL) {
        check_pulls(d, conn);
    } else {
        /* Track which posts are connected so FINAL starts from the real state. */
        for (int a = 0; a < D32_ML_POSTS; a++) {
            s_connected[a] = conn[a] != 0;
            s_gone[a] = 0;
        }
    }
    if (ph == D32_ARMED && s_armed && !s_revealed && d32_slot_state(d, slot) == D32_SLOT_ARMED) {
        if (d32_patch_matches(conn, s_pattern)) {
            if (++s_match_count >= STABLE) {
                s_revealed = true;
                ESP_LOGI(TAG, "patch pattern matched: M4 code shown on the keypad");
                d32_keypad_reveal(d, slot);
            }
        } else {
            s_match_count = 0;
        }
    }
}

static void w_reset(int slot)
{
    (void)slot;
    s_armed = false;
    s_revealed = false;
    s_match_count = 0;
}

static void w_gm_print(const d32_t *d, int slot)
{
    (void)slot;
    char hint[48];
    if (d32_phase(d) != D32_IDLE && d32_mod_wires_hint(hint, sizeof(hint))) {
        printf("  M4 patch pattern: %s\n", hint);
    }
    if (!s_scan_ok) {
        printf("  M4 wire matrix not readable: use `wire <0-5>`\n");
    }
}

const d32_mod_ops_t d32_mod_wires = {
    .name = "wires",
    .configure = w_configure,
    .arm = w_arm,
    .poll = w_poll,
    .reset = w_reset,
    .gm_print = w_gm_print,
};
