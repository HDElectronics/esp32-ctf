#pragma once
/* Private to d32_modules: the adapter tables and the calls adapters make to
 * each other. */
#include <stddef.h>

#include "d32_mod_logic.h"
#include "d32_modules.h"

extern const d32_mod_ops_t d32_mod_radio;   /* M1, mod_radio.c */
extern const d32_mod_ops_t d32_mod_timer;   /* M2, mod_timer.c */
extern const d32_mod_ops_t d32_mod_keypad;  /* M3, mod_keypad.c */
extern const d32_mod_ops_t d32_mod_wires;   /* M4, mod_wires.c */
extern const d32_mod_ops_t d32_mod_probe;   /* M5, mod_probe.c */
extern const d32_mod_ops_t d32_mod_sensors; /* M6, mod_sensors.c */

/* Slot indices (engine order). */
enum { D32_M1 = 0, D32_M2, D32_M3, D32_M4, D32_M5, D32_M6 };

/* M4: the patch hint of the current round ("A1-B4 ..."); false when M4 is
 * disabled, not on "patch-a" or no round is armed. */
bool d32_mod_wires_hint(char *out, size_t cap);

/* M3: the service PIN of the current round; false when M3 is disabled, not
 * on "menu" or no round is armed. */
bool d32_mod_keypad_pin(char out[D32_ML_PIN_LEN + 1]);
