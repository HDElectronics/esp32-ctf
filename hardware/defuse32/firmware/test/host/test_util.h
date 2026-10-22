#pragma once
/* Shared CHECK/RUN macros and helpers for the Defuse32 host tests. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#include "ctf_core.h"
#include "d32_engine.h"

extern int g_failures;
extern int g_checks;

#define CHECK(cond)                                                          \
    do {                                                                     \
        g_checks++;                                                          \
        if (!(cond)) {                                                       \
            g_failures++;                                                    \
            fprintf(stderr, "%s:%d: CHECK failed: %s\n", __FILE__, __LINE__, \
                    #cond);                                                  \
        }                                                                    \
    } while (0)

#define RUN(test_fn)                                                          \
    do {                                                                      \
        int before = g_failures;                                              \
        test_fn();                                                            \
        printf("%s %s\n", g_failures == before ? "PASS" : "FAIL", #test_fn); \
    } while (0)

extern const uint8_t TEST_MAC_A[6];
extern const uint8_t TEST_MAC_B[6];

#define SEED_A 0x1234ABCDu
#define SEED_B 0x0BADF00Du

/* ctf_init(TEST_MAC_A, memory-only) + d32_init(d, cfg) (cfg NULL = defaults). */
void setup(d32_t *d, const d32_config_t *cfg);
/* Config with only the slots in mask (bit i = slot i) enabled. */
d32_config_t cfg_slots(unsigned mask);
/* Disarms every enabled module with its own code. */
void disarm_all(d32_t *d);
/* Pops all queued events; returns how many. */
int drain(d32_t *d);
/* Pops one event and checks its type; returns the event (zeroed if none). */
d32_event_t expect_event(d32_t *d, d32_event_type_t type, const char *file, int line);
#define EXPECT_EV(d, t) expect_event((d), (t), __FILE__, __LINE__)

/* Test groups (one per file). */
void run_config_tests(void);
void run_phase_tests(void);
void run_timer_tests(void);
void run_code_tests(void);
void run_wire_tests(void);
void run_frag_tests(void);
void run_event_tests(void);
void run_modlogic_tests(void);
void run_tilt_tests(void);
void run_pack_tests(void);
