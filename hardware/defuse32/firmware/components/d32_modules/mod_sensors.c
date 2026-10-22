/* M6 sensors adapter (variant "touch-4"), v0.
 *
 * Challenge: touch the four pads (T0, T4, T6, T3 = pads 1-4) in the round's
 * order (d32_touch_sequence(), a permutation derived from the seed). While M6
 * is armed, the four Simon LEDs blink that order as the hint (LED n = pad n).
 * The full sequence shows the M6 code on the keypad OLED. A wrong pad only
 * restarts the sequence (no strike in v0). */
#include <stdio.h>
#include <string.h>

#include "board.h"
#include "d32_mod_internal.h"
#include "d32_mod_logic.h"
#include "esp_log.h"

static const char *TAG = "mod_sensors";

#define TOUCH_MS     20
#define TOUCH_STABLE 3        /* samples: 60 ms */
#define HINT_ON_MS   500
#define HINT_OFF_MS  250
#define HINT_PAUSE_MS 2000
#define HINT_LEVEL   255      /* white; board_leds scales the brightness */

static bool s_known;
static bool s_armed;
static bool s_revealed;
static uint8_t s_seq[D32_ML_PADS];
static d32_seqm_t s_match;
static d32_debounce_t s_db;
static uint32_t s_next_touch;
static uint32_t s_hint_t0;
static int s_lit = -2;        /* Simon LED currently lit, -1 none, -2 unknown */
static bool s_warned;

static void simon_show(int lit)
{
    if (lit == s_lit) {
        return;
    }
    s_lit = lit;
    for (int i = 0; i < D32_ML_PADS; i++) {
        uint8_t v = (i == lit) ? HINT_LEVEL : 0;
        board_leds_set((board_led_t)(BOARD_LED_SIMON1 + i), v, v, v);
    }
}

static bool sn_configure(int slot, const char *variant)
{
    (void)slot;
    s_known = variant && strcmp(variant, "touch-4") == 0;
    s_armed = false;
    return s_known;
}

static void sn_arm(d32_t *d, int slot, uint32_t seed)
{
    (void)d;
    (void)slot;
    s_armed = false;
    s_revealed = false;
    if (!s_known) {
        return;
    }
    d32_touch_sequence(seed, s_seq);
    d32_seqm_init(&s_match, s_seq);
    memset(&s_db, 0, sizeof(s_db));
    s_armed = true;
    s_hint_t0 = 0;
}

/* LED to light in the hint cycle: 4 x (on + off), then a pause. */
static int hint_led(uint32_t now_ms)
{
    if (!s_hint_t0) {
        s_hint_t0 = now_ms ? now_ms : 1;
    }
    const uint32_t step = HINT_ON_MS + HINT_OFF_MS;
    uint32_t t = (now_ms - s_hint_t0) % (D32_ML_PADS * step + HINT_PAUSE_MS);
    if (t >= D32_ML_PADS * step || t % step >= HINT_ON_MS) {
        return -1;
    }
    return s_seq[t / step];
}

static void sn_poll(d32_t *d, int slot, uint32_t now_ms)
{
    d32_phase_t ph = d32_phase(d);
    bool active = s_armed && !s_revealed && ph == D32_ARMED &&
                  d32_slot_state(d, slot) == D32_SLOT_ARMED;
    simon_show(active ? hint_led(now_ms) : -1);
    if (!active || (int32_t)(now_ms - s_next_touch) < 0) {
        return;
    }
    s_next_touch = now_ms + TOUCH_MS;
    if (!board_touch_ready()) {
        if (!s_warned) {
            ESP_LOGW(TAG, "touch pads not available: M6 code via the console only");
            s_warned = true;
        }
        return;
    }
    uint16_t pressed = 0;
    d32_debounce_feed(&s_db, board_touch_mask(), TOUCH_STABLE, &pressed, NULL);
    for (int pad = 0; pad < D32_ML_PADS && pressed; pad++) {
        if (!(pressed & (1u << pad))) {
            continue;
        }
        d32_seq_result_t r = d32_seqm_feed(&s_match, (uint8_t)pad);
        ESP_LOGD(TAG, "pad %d: %d", pad + 1, (int)r);
        if (r == D32_SEQ_DONE) {
            s_revealed = true;
            ESP_LOGI(TAG, "touch sequence complete: M6 code shown on the keypad");
            d32_keypad_reveal(d, slot);
            break;
        }
    }
}

static void sn_reset(int slot)
{
    (void)slot;
    s_armed = false;
    s_revealed = false;
    simon_show(-1);
}

static void sn_gm_print(const d32_t *d, int slot)
{
    (void)slot;
    if (s_armed && d32_phase(d) != D32_IDLE) {
        printf("  M6 touch order: pad %d, %d, %d, %d (1=T0 2=T4 3=T6 4=T3)\n",
               s_seq[0] + 1, s_seq[1] + 1, s_seq[2] + 1, s_seq[3] + 1);
    }
}

const d32_mod_ops_t d32_mod_sensors = {
    .name = "sensors",
    .configure = sn_configure,
    .arm = sn_arm,
    .poll = sn_poll,
    .reset = sn_reset,
    .gm_print = sn_gm_print,
};
