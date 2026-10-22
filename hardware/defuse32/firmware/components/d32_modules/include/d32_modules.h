#pragma once
/* d32_modules: module adapters between d32_engine and d32_board, one file per
 * plate (mod_radio.c ... mod_sensors.c) plus this registry.
 *
 * Threading: every call here runs in the game task, with the caller holding
 * the lock that guards the d32_t. The keypad OLED (SH1106) and the Simon LEDs
 * belong to the adapters; the game task owns the other LEDs, the TM1637 and
 * the servo. The LED chain is latched by the game task (board_leds_show()).
 *
 * v0 challenges (FIRMWARE.md "Firmware behaviour (v0)"): see README.md. */
#include <stdbool.h>
#include <stdint.h>

#include "d32_engine.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Adapter interface. Every hook is optional. */
typedef struct {
    const char *name;   /* plate name, "radio" ... "sensors" */
    /* Pack variant for the next round (IDLE). Returns false when the adapter
     * does not know the variant; it then runs as a placeholder whose code is
     * only visible through the console (`round codes`). */
    bool (*configure)(int slot, const char *variant);
    /* Round armed with `seed` (the engine already derived the codes). */
    void (*arm)(d32_t *d, int slot, uint32_t seed);
    /* Every game tick (10 ms) while the task runs, in every phase. */
    void (*poll)(d32_t *d, int slot, uint32_t now_ms);
    /* Engine event (after the game task handled it). */
    void (*event)(d32_t *d, int slot, const d32_event_t *ev, uint32_t now_ms);
    /* Round reset to IDLE. */
    void (*reset)(int slot);
    /* Game-master debug lines for `round codes` (printf). */
    void (*gm_print)(const d32_t *d, int slot);
} d32_mod_ops_t;

/* Applies the slot config (enabled + variant) to the adapters. Disabled slots
 * get no hooks called until the next configure, except M3 (keypad: code
 * entry) and M4 (wire matrix: final wire), which always run and get a NULL
 * variant when disabled. */
void d32_modules_configure(const d32_config_t *cfg);
void d32_modules_arm(d32_t *d, uint32_t seed);
void d32_modules_poll(d32_t *d, uint32_t now_ms);
void d32_modules_event(d32_t *d, const d32_event_t *ev, uint32_t now_ms);
void d32_modules_reset(void);
/* `round codes` extras (patch pattern, touch sequence, service PIN). */
void d32_modules_gm_print(const d32_t *d);
/* True when the slot is enabled and its adapter knows the variant. */
bool d32_modules_variant_known(int slot);
const d32_mod_ops_t *d32_modules_ops(int slot);

/* ---- keypad OLED (owned by the M3 adapter) ---- */

/* Two message lines under the code entry line (NULL or "" = blank). Shown
 * even when M3 is disabled in the pack (the keypad stays the code-entry
 * device for every module). */
void d32_keypad_message(const char *line1, const char *line2);
/* "Mn CODE XXXXXX" from d32_code_for(); used by the challenges. */
void d32_keypad_reveal(const d32_t *d, int slot);
/* Fragment line ("FRAG 1:B 4:E"); "" clears it. */
void d32_keypad_frags(const char *text);

/* ---- buzzer arbiter ---- */

typedef enum {
    D32_BUZZ_MORSE = 0, /* M2 Morse: only when nothing else is sounding */
    D32_BUZZ_TICK = 1,  /* second beep: over Morse, not over a cue */
    D32_BUZZ_CUE = 2,   /* key press / strike / disarm / result: always */
} d32_buzz_prio_t;

/* Plays a tone unless a higher-priority one is still sounding. Returns true
 * when it played. */
bool d32_buzz(d32_buzz_prio_t prio, uint32_t hz, uint32_t ms, uint32_t now_ms);
/* True while a tone of `prio` started by d32_buzz is still sounding. */
bool d32_buzz_active(d32_buzz_prio_t prio, uint32_t now_ms);

#ifdef __cplusplus
}
#endif
