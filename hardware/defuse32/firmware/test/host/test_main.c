/* Minimal host test runner for d32_engine, d32_mod_logic, the d32_board
 * tilt math and the d32_pack parse core (the `pack` group needs cJSON, see CMakeLists.txt).
 * Usage: d32_engine_tests [group]   (no group = all groups). */
#include <string.h>

#include "test_util.h"

int g_failures;
int g_checks;

const uint8_t TEST_MAC_A[6] = {0x24, 0x6f, 0x28, 0x12, 0x34, 0x56};
const uint8_t TEST_MAC_B[6] = {0x24, 0x6f, 0x28, 0x12, 0x34, 0x57};

void setup(d32_t *d, const d32_config_t *cfg)
{
    ctf_init(TEST_MAC_A, NULL); /* memory-only backend */
    d32_init(d, cfg);
}

d32_config_t cfg_slots(unsigned mask)
{
    d32_config_t c;
    d32_config_default(&c);
    for (int i = 0; i < D32_SLOTS; i++) {
        c.slot[i].enabled = (mask >> i) & 1u;
    }
    return c;
}

void disarm_all(d32_t *d)
{
    char code[D32_CODE_LEN + 1];
    for (int i = 0; i < D32_SLOTS; i++) {
        if (d32_slot_state(d, i) == D32_SLOT_ARMED && d32_code_for(d, i, code)) {
            d32_submit_code(d, code, NULL);
        }
    }
}

int drain(d32_t *d)
{
    int n = 0;
    while (d32_poll_event(d, NULL)) {
        n++;
    }
    return n;
}

d32_event_t expect_event(d32_t *d, d32_event_type_t type, const char *file, int line)
{
    d32_event_t ev;
    memset(&ev, 0, sizeof(ev));
    g_checks++;
    if (!d32_poll_event(d, &ev)) {
        g_failures++;
        fprintf(stderr, "%s:%d: expected event %d, queue empty\n", file, line, (int)type);
        memset(&ev, 0, sizeof(ev));
        return ev;
    }
    if (ev.type != type) {
        g_failures++;
        fprintf(stderr, "%s:%d: expected event %d, got %d\n", file, line, (int)type,
                (int)ev.type);
    }
    return ev;
}

static const struct {
    const char *name;
    void (*fn)(void);
} GROUPS[] = {
    {"config", run_config_tests}, {"phase", run_phase_tests}, {"timer", run_timer_tests},
    {"codes", run_code_tests},    {"wires", run_wire_tests},  {"frags", run_frag_tests},
    {"events", run_event_tests},  {"modlogic", run_modlogic_tests},
    {"tilt", run_tilt_tests},
#ifdef D32_HAVE_CJSON
    {"pack", run_pack_tests},
#endif
};

int main(int argc, char **argv)
{
    const char *only = argc > 1 ? argv[1] : NULL;
    int ran = 0;
    for (size_t i = 0; i < sizeof(GROUPS) / sizeof(GROUPS[0]); i++) {
        if (only == NULL || strcmp(only, GROUPS[i].name) == 0) {
            GROUPS[i].fn();
            ran++;
        }
    }
    if (ran == 0) {
        fprintf(stderr, "unknown group: %s\n", only);
        return 2;
    }
    printf("%d checks, %d failures\n", g_checks, g_failures);
    return g_failures ? 1 : 0;
}
