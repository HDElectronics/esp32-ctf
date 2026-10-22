/* Code derivation, code entry and the final wire. */
#include <ctype.h>
#include <string.h>

#include "test_util.h"

/* Independent re-derivation from FIRMWARE.md "Codes". */
static void expected_code(uint32_t seed, int slot, const char *variant, char out[7])
{
    char label[64];
    uint8_t b[3];
    snprintf(label, sizeof(label), "D32:%08X:M%d:%s", (unsigned)seed, slot + 1, variant);
    ctf_derive(label, b, 3);
    snprintf(out, 7, "%02X%02X%02X", b[0], b[1], b[2]);
}

static int expected_wire(uint32_t seed)
{
    char label[32];
    snprintf(label, sizeof(label), "D32:%08X:wire", (unsigned)seed);
    return (int)(ctf_derive_u32(label) % 6u);
}

/* A well-formed code that matches no slot of the current round. */
static void unused_code(const d32_t *d, char out[7])
{
    char code[7];
    strcpy(out, "000000");
    for (int k = 0; k < 16; k++) {
        bool clash = false;
        for (int i = 0; i < D32_SLOTS; i++) {
            if (d32_code_for(d, i, code) && strcmp(code, out) == 0) {
                clash = true;
            }
        }
        if (!clash) {
            return;
        }
        out[0] = "0123456789ABCDEF"[k];
    }
}

static void test_derivation_stable(void)
{
    d32_t d;
    d32_config_t c;
    d32_config_default(&c);
    strcpy(c.slot[0].variant, "ble-read");
    strcpy(c.slot[2].variant, "menu");
    setup(&d, &c);
    d32_arm(&d, SEED_A);

    char got[7], want[7];
    for (int i = 0; i < D32_SLOTS; i++) {
        CHECK(d32_code_for(&d, i, got));
        expected_code(SEED_A, i, c.slot[i].variant, want);
        CHECK(strcmp(got, want) == 0);
        CHECK(strlen(got) == 6);
        for (int k = 0; k < 6; k++) {
            CHECK(isxdigit((unsigned char)got[k]) && !islower((unsigned char)got[k]));
        }
    }
    CHECK(d32_target_wire(&d) == expected_wire(SEED_A));
    CHECK(!d32_code_for(&d, 6, got));
    CHECK(!d32_code_for(&d, -1, got));

    /* same MAC + seed -> same codes on a fresh engine */
    d32_t e;
    setup(&e, &c);
    d32_arm(&e, SEED_A);
    for (int i = 0; i < D32_SLOTS; i++) {
        char a[7], b[7];
        d32_code_for(&d, i, a);
        d32_code_for(&e, i, b);
        CHECK(strcmp(a, b) == 0);
    }
    CHECK(d32_target_wire(&d) == d32_target_wire(&e));
}

static void test_derivation_differs(void)
{
    d32_t a, b;
    char ca[D32_SLOTS][7], cb[7];
    setup(&a, NULL);
    d32_arm(&a, SEED_A);
    for (int i = 0; i < D32_SLOTS; i++) {
        d32_code_for(&a, i, ca[i]);
    }
    /* modules differ from each other */
    for (int i = 0; i < D32_SLOTS; i++) {
        for (int j = i + 1; j < D32_SLOTS; j++) {
            CHECK(strcmp(ca[i], ca[j]) != 0);
        }
    }
    /* another seed changes every code */
    setup(&b, NULL);
    d32_arm(&b, SEED_B);
    for (int i = 0; i < D32_SLOTS; i++) {
        d32_code_for(&b, i, cb);
        CHECK(strcmp(ca[i], cb) != 0);
    }
    /* the variant is part of the label */
    d32_config_t c;
    d32_config_default(&c);
    strcpy(c.slot[3].variant, "patch-a");
    setup(&b, &c);
    d32_arm(&b, SEED_A);
    d32_code_for(&b, 3, cb);
    CHECK(strcmp(ca[3], cb) != 0);
    d32_code_for(&b, 2, cb);
    CHECK(strcmp(ca[2], cb) == 0);
    /* another board (MAC) changes the codes */
    ctf_init(TEST_MAC_B, NULL);
    d32_init(&b, NULL);
    d32_arm(&b, SEED_A);
    d32_code_for(&b, 0, cb);
    CHECK(strcmp(ca[0], cb) != 0);
    ctf_init(TEST_MAC_A, NULL);

    /* all six colours occur as target over a handful of seeds */
    unsigned seen = 0;
    for (uint32_t s = 0; s < 200 && seen != 0x3F; s++) {
        seen |= 1u << expected_wire(s);
    }
    CHECK(seen == 0x3F);
}

static void test_submit_normalisation(void)
{
    d32_t d;
    setup(&d, NULL);
    CHECK(d32_submit_code(&d, "123456", NULL) == D32_CODE_NOT_ARMED);
    d32_arm(&d, SEED_A);

    char code[7], text[32];
    int slot = -1;
    d32_code_for(&d, 2, code);
    /* lower case, spaces inside and around, tabs */
    snprintf(text, sizeof(text), " %c%c %c%c\t%c%c \n", tolower((unsigned char)code[0]),
             tolower((unsigned char)code[1]), tolower((unsigned char)code[2]),
             tolower((unsigned char)code[3]), tolower((unsigned char)code[4]),
             tolower((unsigned char)code[5]));
    CHECK(d32_submit_code(&d, text, &slot) == D32_CODE_DISARMED);
    CHECK(slot == 2);
    CHECK(d32_slot_state(&d, 2) == D32_SLOT_DISARMED);
    slot = -1;
    CHECK(d32_submit_code(&d, code, &slot) == D32_CODE_ALREADY);
    CHECK(slot == 2);
    CHECK(d32_strikes(&d) == 0);

    /* invalid: no strike */
    CHECK(d32_submit_code(&d, "", NULL) == D32_CODE_INVALID);
    CHECK(d32_submit_code(&d, "   ", NULL) == D32_CODE_INVALID);
    CHECK(d32_submit_code(&d, NULL, NULL) == D32_CODE_INVALID);
    CHECK(d32_submit_code(&d, "12345", NULL) == D32_CODE_INVALID);
    CHECK(d32_submit_code(&d, "1234567", NULL) == D32_CODE_INVALID);
    CHECK(d32_submit_code(&d, "12345G", NULL) == D32_CODE_INVALID);
    CHECK(d32_submit_code(&d, "12-345", NULL) == D32_CODE_INVALID);
    CHECK(d32_submit_code(&d, "0x1234", NULL) == D32_CODE_INVALID);
    CHECK(d32_strikes(&d) == 0);

    /* rejected: strike */
    char bad[7];
    unused_code(&d, bad);
    CHECK(d32_submit_code(&d, bad, NULL) == D32_CODE_REJECTED);
    CHECK(d32_strikes(&d) == 1);
    CHECK(d32_rate_permille(&d) == 1250);
    CHECK(d32_phase(&d) == D32_ARMED);
    d32_submit_code(&d, bad, NULL);
    CHECK(d32_submit_code(&d, bad, NULL) == D32_CODE_REJECTED);
    CHECK(d32_phase(&d) == D32_LOST);
    CHECK(d32_end_reason(&d) == D32_END_STRIKES);
    CHECK(d32_submit_code(&d, code, NULL) == D32_CODE_NOT_ARMED);
}

static void test_submit_in_final(void)
{
    d32_t d;
    setup(&d, NULL);
    d32_arm(&d, SEED_A);
    disarm_all(&d);
    CHECK(d32_phase(&d) == D32_FINAL);
    char code[7], bad[7];
    d32_code_for(&d, 5, code);
    CHECK(d32_submit_code(&d, code, NULL) == D32_CODE_ALREADY);
    CHECK(d32_phase(&d) == D32_FINAL);
    unused_code(&d, bad);
    CHECK(d32_submit_code(&d, bad, NULL) == D32_CODE_REJECTED);
    CHECK(d32_strikes(&d) == 1);
    CHECK(d32_phase(&d) == D32_FINAL);
}

static void test_disabled_slot_code_not_accepted(void)
{
    /* a disabled slot's would-be code is just a wrong code */
    d32_t d;
    d32_config_t c = cfg_slots(0x01);
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    char m2[7], m1[7];
    expected_code(SEED_A, 1, "", m2);
    d32_code_for(&d, 0, m1);
    if (strcmp(m1, m2) != 0) {
        CHECK(d32_submit_code(&d, m2, NULL) == D32_CODE_REJECTED);
    }
    CHECK(d32_submit_code(&d, m1, NULL) == D32_CODE_DISARMED);
    CHECK(d32_phase(&d) == D32_FINAL);
}

void run_code_tests(void)
{
    RUN(test_derivation_stable);
    RUN(test_derivation_differs);
    RUN(test_submit_normalisation);
    RUN(test_submit_in_final);
    RUN(test_disabled_slot_code_not_accepted);
}

/* ---- wires ---- */

static void test_wire_early(void)
{
    d32_t d;
    setup(&d, NULL);
    CHECK(d32_wire_pulled(&d, 0) == D32_WIRE_NOT_ARMED);
    d32_arm(&d, SEED_A);
    CHECK(d32_wire_pulled(&d, -1) == D32_WIRE_INVALID);
    CHECK(d32_wire_pulled(&d, 6) == D32_WIRE_INVALID);
    CHECK(d32_strikes(&d) == 0);
    /* even the target wire is a strike before FINAL */
    CHECK(d32_wire_pulled(&d, d32_target_wire(&d)) == D32_WIRE_EARLY);
    CHECK(d32_strikes(&d) == 1);
    CHECK(d32_phase(&d) == D32_ARMED);
    drain(&d);
    CHECK(d32_wire_pulled(&d, (d32_target_wire(&d) + 1) % 6) == D32_WIRE_EARLY);
    d32_event_t ev = EXPECT_EV(&d, D32_EV_STRIKE);
    CHECK(ev.reason == D32_STRIKE_WIRE);
    CHECK(ev.strikes == 2);
}

static void test_wire_final(void)
{
    d32_t d;
    setup(&d, NULL);
    for (int w = 0; w < D32_WIRES; w++) {
        d32_reset(&d);
        d32_arm(&d, SEED_A);
        d32_tick(&d, 12345);
        d32_strike(&d, D32_STRIKE_MANUAL);
        disarm_all(&d);
        int t = d32_target_wire(&d);
        uint32_t left = d32_time_left_ms(&d);
        d32_wire_result_t r = d32_wire_pulled(&d, w);
        if (w == t) {
            CHECK(r == D32_WIRE_WON);
            CHECK(d32_phase(&d) == D32_WON);
            CHECK(d32_end_reason(&d) == D32_END_WON);
            uint32_t ms = 0;
            uint8_t s = 0;
            CHECK(d32_score(&d, &ms, &s));
            CHECK(ms == left && ms == 45u * 60000u - 12345u);
            CHECK(s == 1);
        } else {
            CHECK(r == D32_WIRE_LOST);
            CHECK(d32_phase(&d) == D32_LOST);
            CHECK(d32_end_reason(&d) == D32_END_WIRE);
            CHECK(!d32_score(&d, NULL, NULL));
        }
        CHECK(d32_wire_pulled(&d, t) == D32_WIRE_NOT_ARMED);
    }
}

void run_wire_tests(void)
{
    RUN(test_wire_early);
    RUN(test_wire_final);
}
