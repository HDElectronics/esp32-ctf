#pragma once
/* Shared CHECK/RUN macros and an in-memory ctf_backend_t for host tests. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#include "ctf_core.h"

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

/* In-memory store; the lock hooks track nesting to catch re-entrant locking. */
typedef struct {
    uint8_t buf[128];
    size_t len;
    bool has;
    int saves;
    int depth;
    int max_depth;
    int locks;
} mem_store_t;

void mem_store_clear(mem_store_t *m);
ctf_backend_t mem_backend(mem_store_t *m);

extern const uint8_t TEST_MAC_A[6];
extern const uint8_t TEST_MAC_B[6];

/* Test groups (one per file). */
void run_crypto_tests(void);
void run_catalog_tests(void);
void run_flag_tests(void);
void run_progress_tests(void);
