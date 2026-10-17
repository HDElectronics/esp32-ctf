/* Minimal host test runner for components/ctf_core (no external deps). */
#include <stdio.h>
#include "ctf_core.h"

static int g_failures;
static int g_checks;

#define CHECK(cond)                                                         \
    do {                                                                    \
        g_checks++;                                                         \
        if (!(cond)) {                                                      \
            g_failures++;                                                   \
            fprintf(stderr, "%s:%d: CHECK failed: %s\n", __FILE__, __LINE__, \
                    #cond);                                                 \
        }                                                                   \
    } while (0)

#define RUN(test_fn)                         \
    do {                                     \
        int before = g_failures;             \
        test_fn();                           \
        printf("%s %s\n", g_failures == before ? "PASS" : "FAIL", #test_fn); \
    } while (0)

static void test_placeholder(void)
{
    CHECK(ctf_core_placeholder() == 0);
}

int main(void)
{
    RUN(test_placeholder);
    printf("%d checks, %d failures\n", g_checks, g_failures);
    return g_failures ? 1 : 0;
}
