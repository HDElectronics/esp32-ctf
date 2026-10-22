/* Config, phase transitions, training mode, timer and strike rate. */
#include <string.h>

#include "test_util.h"

/* ---- config ---- */

static void test_config_defaults(void)
{
    d32_t d;
    setup(&d, NULL);
    const d32_config_t *c = d32_config(&d);
    CHECK(c->minutes == 45);
    CHECK(c->max_strikes == 3);
    CHECK(c->strike_rate_permille == 1250);
    CHECK(!c->training);
    CHECK(d32_enabled_count(&d) == 6);
    CHECK(d32_phase(&d) == D32_IDLE);
    CHECK(d32_time_left_ms(&d) == 45u * 60000u);
    char t[6];
    CHECK(strcmp(d32_time_str(&d, t), "45:00") == 0);
    CHECK(d32_rate_permille(&d) == 1000);
    CHECK(d32_rate_ppm(&d) == 1000000u);
    for (int i = 0; i < D32_SLOTS; i++) {
        CHECK(d32_slot_state(&d, i) == D32_SLOT_IDLE);
    }
    CHECK(d32_slot_state(&d, -1) == D32_SLOT_DISABLED);
    CHECK(d32_slot_state(&d, 6) == D32_SLOT_DISABLED);
    CHECK(d32_event_count(&d) == 0);
}

static void test_config_sanitize(void)
{
    d32_config_t c;
    d32_config_default(&c);
    CHECK(d32_config_sanitize(&c) == 0);

    c.minutes = 0;
    c.max_strikes = 10;
    c.strike_rate_permille = 999;
    memset(c.slot[2].variant, 'x', D32_VARIANT_MAX); /* unterminated */
    CHECK(d32_config_sanitize(&c) == 4);
    CHECK(c.minutes == 45);
    CHECK(c.max_strikes == 3);
    CHECK(c.strike_rate_permille == 1250);
    CHECK(strlen(c.slot[2].variant) == D32_VARIANT_MAX - 1);

    c.minutes = 100;
    c.max_strikes = 0;
    c.strike_rate_permille = 4001;
    CHECK(d32_config_sanitize(&c) == 3);
    CHECK(c.minutes == 45 && c.max_strikes == 3 && c.strike_rate_permille == 1250);

    c.minutes = 99;
    c.max_strikes = 9;
    c.strike_rate_permille = 1000;
    CHECK(d32_config_sanitize(&c) == 0);

    /* d32_init sanitises its copy */
    d32_t d;
    c.minutes = 0;
    setup(&d, &c);
    CHECK(d32_config(&d)->minutes == 45);
}

static void test_set_config(void)
{
    d32_t d;
    setup(&d, NULL);
    d32_config_t c = cfg_slots(0x05);
    c.minutes = 2;
    CHECK(d32_set_config(&d, &c));
    CHECK(d32_time_left_ms(&d) == 120000u);
    CHECK(d32_slot_state(&d, 0) == D32_SLOT_IDLE);
    CHECK(d32_slot_state(&d, 1) == D32_SLOT_DISABLED);
    CHECK(d32_enabled_count(&d) == 2);
    CHECK(d32_arm(&d, SEED_A) == D32_ARM_OK);
    CHECK(!d32_set_config(&d, &c)); /* not IDLE */
    CHECK(!d32_set_config(&d, NULL));
}

void run_config_tests(void)
{
    RUN(test_config_defaults);
    RUN(test_config_sanitize);
    RUN(test_set_config);
}

/* ---- phases ---- */

static void check_idle_clean(d32_t *d)
{
    char code[D32_CODE_LEN + 1];
    char w[D32_COLOUR_MAX + 1];
    CHECK(d32_phase(d) == D32_IDLE);
    CHECK(d32_end_reason(d) == D32_END_NONE);
    CHECK(d32_strikes(d) == 0);
    CHECK(d32_rate_ppm(d) == 1000000u);
    CHECK(d32_time_left_ms(d) == (uint32_t)d32_config(d)->minutes * 60000u);
    CHECK(d32_target_wire(d) == -1);
    CHECK(!d32_code_for(d, 0, code));
    CHECK(d32_disarmed_count(d) == 0);
    CHECK(d32_colour_len(d) == 0);
    CHECK(strcmp(d32_revealed_word(d, w), "") == 0);
    CHECK(d32_revealed_mask(d) == 0);
    for (int i = 0; i < D32_SLOTS; i++) {
        CHECK(d32_slot_frags(d, i, NULL, 0) == 0);
        CHECK(d32_slot_state(d, i) ==
              (d32_config(d)->slot[i].enabled ? D32_SLOT_IDLE : D32_SLOT_DISABLED));
    }
}

static void test_arm(void)
{
    d32_t d;
    setup(&d, NULL);
    CHECK(d32_arm(&d, SEED_A) == D32_ARM_OK);
    CHECK(d32_phase(&d) == D32_ARMED);
    CHECK(d32_target_wire(&d) >= 0 && d32_target_wire(&d) < 6);
    for (int i = 0; i < D32_SLOTS; i++) {
        CHECK(d32_slot_state(&d, i) == D32_SLOT_ARMED);
    }
    CHECK(d32_arm(&d, SEED_B) == D32_ARM_BUSY);
    CHECK(d32_phase(&d) == D32_ARMED);

    d32_config_t none = cfg_slots(0);
    setup(&d, &none);
    CHECK(d32_arm(&d, SEED_A) == D32_ARM_NO_MODULES);
    CHECK(d32_phase(&d) == D32_IDLE);
}

static void test_reset_from_every_phase(void)
{
    d32_t d;
    d32_config_t c = cfg_slots(0x3F);

    /* IDLE -> IDLE: no event */
    setup(&d, &c);
    d32_reset(&d);
    check_idle_clean(&d);
    CHECK(d32_event_count(&d) == 0);

    /* ARMED */
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    d32_strike(&d, D32_STRIKE_MANUAL);
    d32_tick(&d, 5000);
    d32_submit_code(&d, "000000", NULL); /* probably wrong; either way not idle */
    d32_reset(&d);
    check_idle_clean(&d);
    CHECK(d32_event_count(&d) == 1);
    CHECK(EXPECT_EV(&d, D32_EV_PHASE).phase == D32_IDLE);

    /* FINAL */
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    disarm_all(&d);
    CHECK(d32_phase(&d) == D32_FINAL);
    d32_reset(&d);
    check_idle_clean(&d);
    CHECK(EXPECT_EV(&d, D32_EV_PHASE).phase == D32_IDLE);

    /* WON */
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    disarm_all(&d);
    CHECK(d32_wire_pulled(&d, d32_target_wire(&d)) == D32_WIRE_WON);
    CHECK(d32_phase(&d) == D32_WON);
    d32_reset(&d);
    check_idle_clean(&d);

    /* LOST */
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    for (int i = 0; i < 3; i++) {
        d32_strike(&d, D32_STRIKE_MANUAL);
    }
    CHECK(d32_phase(&d) == D32_LOST);
    d32_reset(&d);
    check_idle_clean(&d);

    /* can arm again after reset, with the same codes for the same seed */
    char a[7], b[7];
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    d32_code_for(&d, 0, a);
    d32_reset(&d);
    CHECK(d32_arm(&d, SEED_A) == D32_ARM_OK);
    d32_code_for(&d, 0, b);
    CHECK(strcmp(a, b) == 0);
}

static void test_final_needs_enabled_only(void)
{
    d32_t d;
    d32_config_t c = cfg_slots(0x15); /* M1, M3, M5 */
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    char code[7];
    CHECK(!d32_code_for(&d, 1, code)); /* disabled */
    CHECK(d32_slot_state(&d, 1) == D32_SLOT_DISABLED);

    CHECK(d32_code_for(&d, 0, code));
    CHECK(d32_submit_code(&d, code, NULL) == D32_CODE_DISARMED);
    CHECK(d32_phase(&d) == D32_ARMED);
    CHECK(d32_code_for(&d, 2, code));
    CHECK(d32_submit_code(&d, code, NULL) == D32_CODE_DISARMED);
    CHECK(d32_phase(&d) == D32_ARMED);
    CHECK(d32_disarmed_count(&d) == 2);
    CHECK(d32_code_for(&d, 4, code));
    CHECK(d32_submit_code(&d, code, NULL) == D32_CODE_DISARMED);
    CHECK(d32_phase(&d) == D32_FINAL);
    CHECK(d32_disarmed_count(&d) == 3);
    CHECK(d32_slot_state(&d, 1) == D32_SLOT_DISABLED);
    CHECK(d32_slot_state(&d, 3) == D32_SLOT_DISABLED);
    CHECK(d32_slot_state(&d, 5) == D32_SLOT_DISABLED);
}

static void test_training(void)
{
    d32_t d;
    d32_config_t c;
    d32_config_default(&c);
    c.training = true;
    setup(&d, &c);
    CHECK(d32_arm(&d, SEED_A) == D32_ARM_OK);
    drain(&d);

    uint32_t t0 = d32_time_left_ms(&d);
    d32_tick(&d, 60u * 60000u); /* an hour: nothing happens */
    CHECK(d32_time_left_ms(&d) == t0);
    CHECK(d32_phase(&d) == D32_ARMED);

    CHECK(!d32_strike(&d, D32_STRIKE_MANUAL));
    CHECK(!d32_tilt(&d, 1000));

    /* find a code that matches no slot */
    char bad[7] = "000000";
    char code[7];
    for (int i = 0; i < D32_SLOTS; i++) {
        d32_code_for(&d, i, code);
        if (strcmp(code, bad) == 0) {
            bad[0] = '1';
        }
    }
    for (int i = 0; i < 5; i++) {
        CHECK(d32_submit_code(&d, bad, NULL) == D32_CODE_REJECTED);
    }
    CHECK(d32_wire_pulled(&d, 0) == D32_WIRE_EARLY);
    CHECK(d32_strikes(&d) == 0);
    CHECK(d32_rate_ppm(&d) == 1000000u);
    CHECK(d32_phase(&d) == D32_ARMED);
    /* REJECTED events are still queued (UI feedback), no STRIKE events */
    CHECK(d32_event_count(&d) == 5);
    for (int i = 0; i < 5; i++) {
        EXPECT_EV(&d, D32_EV_REJECTED);
    }

    disarm_all(&d);
    CHECK(d32_phase(&d) == D32_FINAL);
    int t = d32_target_wire(&d);
    CHECK(d32_wire_pulled(&d, t) == D32_WIRE_WON);
    uint32_t ms;
    uint8_t s;
    CHECK(d32_score(&d, &ms, &s));
    CHECK(ms == t0 && s == 0);

    /* wrong wire still ends the round in training */
    d32_reset(&d);
    d32_arm(&d, SEED_A);
    disarm_all(&d);
    CHECK(d32_wire_pulled(&d, (d32_target_wire(&d) + 1) % 6) == D32_WIRE_LOST);
    CHECK(d32_phase(&d) == D32_LOST);
    CHECK(d32_end_reason(&d) == D32_END_WIRE);
}

void run_phase_tests(void)
{
    RUN(test_arm);
    RUN(test_reset_from_every_phase);
    RUN(test_final_needs_enabled_only);
    RUN(test_training);
}

/* ---- timer and rate ---- */

static void test_countdown(void)
{
    d32_t d;
    d32_config_t c;
    char t[6];
    d32_config_default(&c);
    c.minutes = 1;
    setup(&d, &c);
    d32_tick(&d, 1000); /* IDLE: no-op */
    CHECK(d32_time_left_ms(&d) == 60000u);
    d32_arm(&d, SEED_A);
    CHECK(strcmp(d32_time_str(&d, t), "01:00") == 0);
    d32_tick(&d, 1);
    CHECK(d32_time_left_ms(&d) == 59999u);
    CHECK(strcmp(d32_time_str(&d, t), "01:00") == 0); /* ceil */
    d32_tick(&d, 999);
    CHECK(strcmp(d32_time_str(&d, t), "00:59") == 0);
    d32_tick(&d, 58000);
    CHECK(d32_time_left_ms(&d) == 1000u);
    CHECK(strcmp(d32_time_str(&d, t), "00:01") == 0);
    d32_tick(&d, 999);
    CHECK(d32_time_left_ms(&d) == 1u);
    CHECK(strcmp(d32_time_str(&d, t), "00:01") == 0);
    CHECK(d32_phase(&d) == D32_ARMED);
    d32_tick(&d, 0);
    CHECK(d32_time_left_ms(&d) == 1u);
    d32_tick(&d, 5000); /* overshoot clamps to 0 */
    CHECK(d32_time_left_ms(&d) == 0u);
    CHECK(strcmp(d32_time_str(&d, t), "00:00") == 0);
    CHECK(d32_phase(&d) == D32_LOST);
    CHECK(d32_end_reason(&d) == D32_END_TIME);
    d32_tick(&d, 1000); /* LOST: no-op */
    CHECK(d32_time_left_ms(&d) == 0u);
    CHECK(!d32_score(&d, NULL, NULL));

    /* timer keeps running in FINAL */
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    disarm_all(&d);
    d32_tick(&d, 60000);
    CHECK(d32_phase(&d) == D32_LOST);
    CHECK(d32_end_reason(&d) == D32_END_TIME);

    /* 99 minutes formats as 99:00 */
    c.minutes = 99;
    setup(&d, &c);
    CHECK(strcmp(d32_time_str(&d, t), "99:00") == 0);
}

static void test_rate_exact(void)
{
    d32_t d;
    d32_config_t c;
    d32_config_default(&c);
    c.minutes = 10;
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    d32_tick(&d, 1000);
    CHECK(d32_time_left_ms(&d) == 599000u);

    CHECK(d32_strike(&d, D32_STRIKE_MANUAL));
    CHECK(d32_rate_ppm(&d) == 1250000u);
    CHECK(d32_rate_permille(&d) == 1250);
    d32_tick(&d, 1000);
    CHECK(d32_time_left_ms(&d) == 597750u);

    CHECK(d32_strike(&d, D32_STRIKE_MANUAL));
    CHECK(d32_rate_ppm(&d) == 1562500u);
    CHECK(d32_rate_permille(&d) == 1563); /* 1562.5 rounds half up */
    d32_tick(&d, 1000);                    /* 1562.5 ms: 1562 now, 0.5 carried */
    CHECK(d32_time_left_ms(&d) == 596188u);
    d32_tick(&d, 1); /* 1.5625 + 0.5 = 2.0625 */
    CHECK(d32_time_left_ms(&d) == 596186u);
    CHECK(d32_phase(&d) == D32_ARMED);
    CHECK(d32_strikes(&d) == 2);
}

static void test_rate_split_ticks(void)
{
    /* many small ticks == one big tick, exactly */
    d32_t a, b;
    d32_config_t c;
    d32_config_default(&c);
    c.minutes = 30;
    c.max_strikes = 9;
    c.strike_rate_permille = 1333;
    setup(&a, &c);
    setup(&b, &c);
    d32_arm(&a, SEED_A);
    d32_arm(&b, SEED_A);
    for (int s = 0; s < 4; s++) {
        d32_strike(&a, D32_STRIKE_MANUAL);
        d32_strike(&b, D32_STRIKE_MANUAL);
    }
    CHECK(d32_rate_ppm(&a) == d32_rate_ppm(&b));
    d32_tick(&a, 10007);
    for (int i = 0; i < 10007; i++) {
        d32_tick(&b, 1);
    }
    CHECK(d32_time_left_ms(&a) == d32_time_left_ms(&b));
    /* 1333^4 in ppm with per-step rounding: 1333000, 1776889, 2368593, 3157334 */
    CHECK(d32_rate_ppm(&a) == 3157334u);
    /* 10007 * 3.157334 = 31595.441... */
    CHECK(d32_time_left_ms(&a) == 1800000u - 31595u);
}

static void test_rate_custom_and_flat(void)
{
    d32_t d;
    d32_config_t c;
    d32_config_default(&c);
    c.max_strikes = 9;
    c.strike_rate_permille = 1500;
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    d32_strike(&d, D32_STRIKE_MANUAL);
    CHECK(d32_rate_ppm(&d) == 1500000u);
    d32_strike(&d, D32_STRIKE_MANUAL);
    CHECK(d32_rate_ppm(&d) == 2250000u);
    d32_strike(&d, D32_STRIKE_MANUAL);
    CHECK(d32_rate_ppm(&d) == 3375000u);
    CHECK(d32_rate_permille(&d) == 3375);

    /* per-step rounding is half up: 1787569 * 1.337 = 2389979.753 -> 2389980 */
    c.strike_rate_permille = 1337;
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    d32_strike(&d, D32_STRIKE_MANUAL);
    d32_strike(&d, D32_STRIKE_MANUAL);
    CHECK(d32_rate_ppm(&d) == 1787569u);
    d32_strike(&d, D32_STRIKE_MANUAL);
    CHECK(d32_rate_ppm(&d) == 2389980u);
    CHECK(d32_rate_permille(&d) == 2390);

    c.strike_rate_permille = 1000; /* flat: strikes never speed up the clock */
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    for (int i = 0; i < 8; i++) {
        d32_strike(&d, D32_STRIKE_MANUAL);
    }
    CHECK(d32_rate_ppm(&d) == 1000000u);
    d32_tick(&d, 1000);
    CHECK(d32_time_left_ms(&d) == 45u * 60000u - 1000u);

    /* max rate, max strikes: no overflow */
    c.strike_rate_permille = 4000;
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    for (int i = 0; i < 8; i++) {
        d32_strike(&d, D32_STRIKE_MANUAL);
    }
    CHECK(d32_rate_ppm(&d) == 1000000000u); /* 4^5 > 1000x: capped */
    CHECK(d32_rate_permille(&d) == 1000000u);
    d32_tick(&d, 41);
    CHECK(d32_time_left_ms(&d) == 45u * 60000u - 41000u);
    d32_tick(&d, 0xFFFFFFFFu); /* largest dt at the cap: no overflow, clamps to 0 */
    CHECK(d32_time_left_ms(&d) == 0u);
    CHECK(d32_phase(&d) == D32_LOST);
}

static void test_max_strikes(void)
{
    d32_t d;
    setup(&d, NULL);
    d32_arm(&d, SEED_A);
    CHECK(d32_strike(&d, D32_STRIKE_MANUAL));
    CHECK(d32_strike(&d, D32_STRIKE_MANUAL));
    CHECK(d32_phase(&d) == D32_ARMED);
    CHECK(d32_strike(&d, D32_STRIKE_MANUAL));
    CHECK(d32_phase(&d) == D32_LOST);
    CHECK(d32_end_reason(&d) == D32_END_STRIKES);
    CHECK(d32_strikes(&d) == 3);
    CHECK(!d32_strike(&d, D32_STRIKE_MANUAL)); /* round over */
    CHECK(d32_strikes(&d) == 3);

    d32_config_t c;
    d32_config_default(&c);
    c.max_strikes = 1;
    setup(&d, &c);
    CHECK(!d32_strike(&d, D32_STRIKE_MANUAL)); /* IDLE */
    d32_arm(&d, SEED_A);
    d32_strike(&d, D32_STRIKE_MANUAL);
    CHECK(d32_phase(&d) == D32_LOST);

    /* strikes count in FINAL too */
    c.max_strikes = 2;
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    disarm_all(&d);
    d32_strike(&d, D32_STRIKE_MANUAL);
    CHECK(d32_phase(&d) == D32_FINAL);
    d32_strike(&d, D32_STRIKE_MANUAL);
    CHECK(d32_phase(&d) == D32_LOST);
}

static void test_tilt_rate_limit(void)
{
    d32_t d;
    d32_config_t c;
    d32_config_default(&c);
    c.max_strikes = 9;
    setup(&d, &c);
    CHECK(!d32_tilt(&d, 0)); /* IDLE */
    d32_arm(&d, SEED_A);
    CHECK(d32_tilt(&d, 1000));
    CHECK(d32_strikes(&d) == 1);
    CHECK(!d32_tilt(&d, 1000));
    CHECK(!d32_tilt(&d, 5999)); /* < 5 s after the counted tilt */
    CHECK(d32_strikes(&d) == 1);
    CHECK(d32_tilt(&d, 6000));
    CHECK(d32_strikes(&d) == 2);
    CHECK(!d32_tilt(&d, 10999)); /* ignored tilts do not extend the window */
    CHECK(d32_tilt(&d, 11000));
    CHECK(d32_strikes(&d) == 3);
    /* first tilt at time 0 still counts */
    d32_reset(&d);
    d32_arm(&d, SEED_A);
    CHECK(d32_tilt(&d, 0));
    CHECK(!d32_tilt(&d, 4999));
    /* clock wrap-around */
    d32_reset(&d);
    d32_arm(&d, SEED_A);
    CHECK(d32_tilt(&d, 0xFFFFF000u));
    CHECK(!d32_tilt(&d, 0x00000387u)); /* 4999 ms later */
    CHECK(d32_tilt(&d, 0x00000388u));  /* 5000 ms later */
    /* reset clears the window */
    d32_reset(&d);
    d32_arm(&d, SEED_A);
    CHECK(d32_tilt(&d, 0x00000389u));
}

void run_timer_tests(void)
{
    RUN(test_countdown);
    RUN(test_rate_exact);
    RUN(test_rate_split_ticks);
    RUN(test_rate_custom_and_flat);
    RUN(test_max_strikes);
    RUN(test_tilt_rate_limit);
}
