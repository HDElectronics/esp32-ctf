/* Game task: owns the d32_engine context and the module adapters, polls the
 * inputs (key switch, tilt), drives the round UI (TM1637, WS2812, buzzer,
 * servo) and serves the console's round commands. Every function here is
 * thread safe (one mutex around the engine). */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "d32_engine.h"

/* ctf_core key (chip MAC, RAM backend), engine and adapters from the current
 * pack. Call once, after the boot pack is selected. */
void game_init(void);
/* Starts the 10 ms game task. */
void game_start(void);

/* New round with esp_random() as the seed, settings from the current pack
 * (minutes > 0 overrides the round length, 1..99). A finished round (won or
 * lost) is reset first; an armed one returns D32_ARM_BUSY. */
d32_arm_result_t game_round_start(int minutes);
void game_round_reset(void);
bool game_round_active(void);   /* ARMED or FINAL */

d32_code_result_t game_submit_code(const char *text, int *slot_out);
d32_wire_result_t game_wire(int index);
bool game_strike(void);

/* Console output. */
void game_print_status(void);
/* Game master debug: codes of the enabled modules, target wire, adapter
 * extras. Never shown to players. */
void game_print_codes(void);
