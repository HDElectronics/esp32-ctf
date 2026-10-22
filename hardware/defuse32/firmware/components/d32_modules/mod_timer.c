/* M2 timer adapter (variant "buzzer-morse"), v0.
 *
 * The round clock itself (TM1637, second beeps) is driven by the game task.
 * Challenge: while the round runs and M2 is armed, the buzzer plays the M2
 * code in Morse (700 Hz, 100 ms per unit, 14 silent units between
 * repetitions), between the second beeps. A second beep or a UI cue takes
 * the buzzer for a moment; the Morse element then resumes for its remaining
 * time, so the timing of the code stays intact. */
#include <stdio.h>
#include <string.h>

#include "board.h"
#include "d32_mod_internal.h"
#include "d32_mod_logic.h"
#include "esp_log.h"

static const char *TAG = "mod_timer";

#define MORSE_HZ       700
#define MORSE_UNIT_MS  100
#define MORSE_TAIL     14       /* units of silence before the code repeats */
#define MORSE_START_MS 2000     /* silence after arming */
#define MORSE_MIN_MS   15       /* do not restart a tone for less than this */
#define MORSE_STEPS    64

static bool s_known;
static d32_morse_step_t s_steps[MORSE_STEPS];
static int s_nsteps;
static int s_idx;
static uint32_t s_step_end;
static bool s_started;
static bool s_playing;

static bool t_configure(int slot, const char *variant)
{
    (void)slot;
    s_known = variant && strcmp(variant, "buzzer-morse") == 0;
    s_nsteps = 0;
    return s_known;
}

static void t_arm(d32_t *d, int slot, uint32_t seed)
{
    (void)seed;
    char code[D32_CODE_LEN + 1];
    s_nsteps = 0;
    s_started = false;
    s_playing = false;
    if (!s_known || !d32_code_for(d, slot, code)) {
        return;
    }
    s_nsteps = d32_morse_timeline(code, MORSE_TAIL, s_steps, MORSE_STEPS);
    if (s_nsteps <= 0) {
        ESP_LOGW(TAG, "Morse timeline failed");
        s_nsteps = 0;
    }
}

static void stop(uint32_t now_ms)
{
    if (s_playing && d32_buzz_active(D32_BUZZ_MORSE, now_ms)) {
        board_buzzer_stop();
    }
    s_playing = false;
}

static void t_poll(d32_t *d, int slot, uint32_t now_ms)
{
    d32_phase_t ph = d32_phase(d);
    bool run = s_nsteps > 0 && (ph == D32_ARMED || ph == D32_FINAL) &&
               d32_slot_state(d, slot) == D32_SLOT_ARMED;
    if (!run) {
        stop(now_ms);
        s_started = false;
        return;
    }
    if (!s_started) {
        /* Begin with the silent tail step so the code starts after a pause. */
        s_started = true;
        s_idx = s_nsteps - 1;
        s_step_end = now_ms + MORSE_START_MS;
    }
    if ((int32_t)(now_ms - s_step_end) > 1000) {
        s_step_end = now_ms; /* the task was held up: resync instead of racing */
    }
    while ((int32_t)(now_ms - s_step_end) >= 0) {
        s_idx = (s_idx + 1) % s_nsteps;
        s_step_end += (uint32_t)s_steps[s_idx].units * MORSE_UNIT_MS;
    }
    if (!s_steps[s_idx].on) {
        s_playing = false;
        return;
    }
    uint32_t remaining = s_step_end - now_ms;
    if (remaining >= MORSE_MIN_MS && !d32_buzz_active(D32_BUZZ_MORSE, now_ms)) {
        s_playing = d32_buzz(D32_BUZZ_MORSE, MORSE_HZ, remaining, now_ms) || s_playing;
    }
}

static void t_reset(int slot)
{
    (void)slot;
    s_nsteps = 0;
    s_started = false;
    s_playing = false;
}

static void t_gm_print(const d32_t *d, int slot)
{
    char code[D32_CODE_LEN + 1];
    if (s_known && d32_code_for(d, slot, code)) {
        printf("  M2 Morse on the buzzer: %s (%d ms per unit)\n", code, MORSE_UNIT_MS);
    }
}

const d32_mod_ops_t d32_mod_timer = {
    .name = "timer",
    .configure = t_configure,
    .arm = t_arm,
    .poll = t_poll,
    .reset = t_reset,
    .gm_print = t_gm_print,
};
