/* Event queue: order, contents, overflow; static names. */
#include <string.h>

#include "test_util.h"

static void test_round_event_order_won(void)
{
    d32_t d;
    d32_config_t c = cfg_slots(0x03); /* M1, M2 */
    c.minutes = 1;
    setup(&d, &c);
    CHECK(!d32_poll_event(&d, NULL));
    d32_arm(&d, SEED_A);
    d32_event_t ev = EXPECT_EV(&d, D32_EV_PHASE);
    CHECK(ev.phase == D32_ARMED);
    CHECK(ev.time_left_ms == 60000u);
    CHECK(!d32_poll_event(&d, &ev));

    /* ticks: one event per displayed second change, none within a second */
    d32_tick(&d, 1); /* 59999 ms still shows 01:00 */
    CHECK(d32_event_count(&d) == 0);
    d32_tick(&d, 998);
    CHECK(d32_event_count(&d) == 0);
    d32_tick(&d, 1);
    ev = EXPECT_EV(&d, D32_EV_TICK);
    CHECK(ev.seconds == 59);
    CHECK(ev.time_left_ms == 59000u);
    d32_tick(&d, 3500); /* crosses several seconds: one event */
    ev = EXPECT_EV(&d, D32_EV_TICK);
    CHECK(ev.seconds == 56);
    CHECK(d32_event_count(&d) == 0);

    /* disarm M2 then M1 */
    char code[7];
    d32_frag_t f[D32_MAX_FRAGS];
    d32_code_for(&d, 1, code);
    d32_submit_code(&d, code, NULL);
    ev = EXPECT_EV(&d, D32_EV_DISARMED);
    CHECK(ev.slot == 1);
    int k = d32_slot_frags(&d, 1, f, D32_MAX_FRAGS);
    CHECK(ev.nfrags == k);
    for (int i = 0; i < k; i++) {
        CHECK(ev.frags[i].pos == f[i].pos && ev.frags[i].letter == f[i].letter);
    }
    CHECK(d32_event_count(&d) == 0);
    d32_code_for(&d, 0, code);
    d32_submit_code(&d, code, NULL);
    ev = EXPECT_EV(&d, D32_EV_DISARMED);
    CHECK(ev.slot == 0);
    CHECK(ev.nfrags + k == d32_colour_len(&d));
    ev = EXPECT_EV(&d, D32_EV_PHASE);
    CHECK(ev.phase == D32_FINAL);
    /* already: no event */
    d32_submit_code(&d, code, NULL);
    CHECK(d32_event_count(&d) == 0);

    d32_wire_pulled(&d, d32_target_wire(&d));
    ev = EXPECT_EV(&d, D32_EV_PHASE);
    CHECK(ev.phase == D32_WON);
    ev = EXPECT_EV(&d, D32_EV_RESULT);
    CHECK(ev.reason == D32_END_WON);
    CHECK(ev.time_left_ms == 56000u - 500u);
    CHECK(ev.strikes == 0);
    CHECK(!d32_poll_event(&d, &ev));
}

static void test_strike_events_and_loss(void)
{
    d32_t d;
    setup(&d, NULL);
    d32_arm(&d, SEED_A);
    drain(&d);
    char bad[7] = "000000", code[7];
    for (int i = 0; i < D32_SLOTS; i++) {
        d32_code_for(&d, i, code);
        if (strcmp(code, bad) == 0) {
            bad[0] = '1';
        }
    }
    d32_submit_code(&d, bad, NULL);
    EXPECT_EV(&d, D32_EV_REJECTED);
    d32_event_t ev = EXPECT_EV(&d, D32_EV_STRIKE);
    CHECK(ev.reason == D32_STRIKE_CODE);
    CHECK(ev.strikes == 1);
    CHECK(ev.rate_permille == 1250);

    d32_tilt(&d, 100);
    ev = EXPECT_EV(&d, D32_EV_STRIKE);
    CHECK(ev.reason == D32_STRIKE_TILT);
    CHECK(ev.strikes == 2);
    CHECK(ev.rate_permille == 1563);
    d32_tilt(&d, 200); /* rate limited: nothing */
    CHECK(d32_event_count(&d) == 0);

    d32_strike(&d, D32_STRIKE_MANUAL);
    ev = EXPECT_EV(&d, D32_EV_STRIKE);
    CHECK(ev.reason == D32_STRIKE_MANUAL);
    CHECK(ev.strikes == 3);
    ev = EXPECT_EV(&d, D32_EV_PHASE);
    CHECK(ev.phase == D32_LOST);
    ev = EXPECT_EV(&d, D32_EV_RESULT);
    CHECK(ev.reason == D32_END_STRIKES);
    CHECK(ev.strikes == 3);
    CHECK(d32_event_count(&d) == 0);
}

static void test_timeout_events(void)
{
    d32_t d;
    d32_config_t c;
    d32_config_default(&c);
    c.minutes = 1;
    setup(&d, &c);
    d32_arm(&d, SEED_A);
    drain(&d);
    d32_tick(&d, 70000);
    d32_event_t ev = EXPECT_EV(&d, D32_EV_TICK);
    CHECK(ev.seconds == 0);
    ev = EXPECT_EV(&d, D32_EV_PHASE);
    CHECK(ev.phase == D32_LOST);
    ev = EXPECT_EV(&d, D32_EV_RESULT);
    CHECK(ev.reason == D32_END_TIME);
    CHECK(ev.time_left_ms == 0);
    CHECK(d32_event_count(&d) == 0);

    /* reset drops pending events and queues PHASE(IDLE) */
    d32_tick(&d, 1); /* no-op */
    d32_reset(&d);
    ev = EXPECT_EV(&d, D32_EV_PHASE);
    CHECK(ev.phase == D32_IDLE);
    CHECK(d32_event_count(&d) == 0);
    /* arm keeps the queued IDLE event */
    d32_reset(&d);
    d32_arm(&d, SEED_A);
    d32_reset(&d);
    d32_arm(&d, SEED_A);
    ev = EXPECT_EV(&d, D32_EV_PHASE);
    CHECK(ev.phase == D32_IDLE);
    ev = EXPECT_EV(&d, D32_EV_PHASE);
    CHECK(ev.phase == D32_ARMED);
}

static void test_overflow(void)
{
    d32_t d;
    d32_config_t c;
    d32_config_default(&c);
    c.minutes = 99;
    setup(&d, &c);
    d32_arm(&d, SEED_A); /* 1 PHASE event */
    for (int i = 0; i < 40; i++) {
        d32_tick(&d, 1000); /* 40 TICK events: 5939 .. 5900 */
    }
    /* 41 queued into 32 slots: the 9 oldest (PHASE + 8 ticks) are dropped */
    CHECK(d32_event_count(&d) == D32_EVQ_LEN);
    CHECK(d32_events_dropped(&d) == 9);
    d32_event_t ev;
    uint32_t want = 5940 - 9;
    int n = 0;
    while (d32_poll_event(&d, &ev)) {
        CHECK(ev.type == D32_EV_TICK);
        CHECK(ev.seconds == want);
        want--;
        n++;
    }
    CHECK(n == D32_EVQ_LEN);
    CHECK(want == 5899);
    CHECK(d32_event_count(&d) == 0);

    /* ring keeps working after wrapping */
    d32_tick(&d, 1000);
    ev = EXPECT_EV(&d, D32_EV_TICK);
    CHECK(ev.seconds == 5899);
    CHECK(d32_events_dropped(&d) == 9);

    /* reset clears the drop counter */
    d32_reset(&d);
    CHECK(d32_events_dropped(&d) == 0);
    CHECK(d32_event_count(&d) == 1);
}

static void test_names(void)
{
    static const char *ids[] = {"M1", "M2", "M3", "M4", "M5", "M6"};
    static const char *names[] = {"radio", "timer", "keypad", "wires", "probe", "sensors"};
    static const char *colours[] = {"RED", "BLUE", "YELLOW", "GREEN", "WHITE", "BLACK"};
    for (int i = 0; i < 6; i++) {
        CHECK(strcmp(d32_slot_id(i), ids[i]) == 0);
        CHECK(strcmp(d32_slot_name(i), names[i]) == 0);
        CHECK(strcmp(d32_wire_colour(i), colours[i]) == 0);
    }
    CHECK(d32_slot_id(6) == NULL && d32_slot_name(-1) == NULL && d32_wire_colour(6) == NULL);
    CHECK(strcmp(d32_phase_name(D32_IDLE), "idle") == 0);
    CHECK(strcmp(d32_phase_name(D32_ARMED), "armed") == 0);
    CHECK(strcmp(d32_phase_name(D32_FINAL), "final") == 0);
    CHECK(strcmp(d32_phase_name(D32_WON), "won") == 0);
    CHECK(strcmp(d32_phase_name(D32_LOST), "lost") == 0);
}

void run_event_tests(void)
{
    RUN(test_round_event_order_won);
    RUN(test_strike_events_and_loss);
    RUN(test_timeout_events);
    RUN(test_overflow);
    RUN(test_names);
}
