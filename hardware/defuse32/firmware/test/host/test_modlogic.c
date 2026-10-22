/* d32_modules pure logic: Morse, seed-derived patterns, keypad entry. */
#include <ctype.h>
#include <string.h>

#include "d32_mod_logic.h"
#include "test_util.h"

static void test_morse_symbols(void)
{
    CHECK(strcmp(d32_morse_symbol('0'), "-----") == 0);
    CHECK(strcmp(d32_morse_symbol('5'), ".....") == 0);
    CHECK(strcmp(d32_morse_symbol('9'), "----.") == 0);
    CHECK(strcmp(d32_morse_symbol('A'), ".-") == 0);
    CHECK(strcmp(d32_morse_symbol('b'), "-...") == 0);
    CHECK(strcmp(d32_morse_symbol('E'), ".") == 0);
    CHECK(strcmp(d32_morse_symbol('F'), "..-.") == 0);
    CHECK(d32_morse_symbol('G') == NULL);
    CHECK(d32_morse_symbol(' ') == NULL);
}

static void test_morse_timeline(void)
{
    d32_morse_step_t st[64];
    /* "E": dot, then the tail. */
    CHECK(d32_morse_timeline("E", 7, st, 64) == 2);
    CHECK(st[0].on && st[0].units == 1);
    CHECK(!st[1].on && st[1].units == 7);
    /* "AE": . - | . tail */
    CHECK(d32_morse_timeline("AE", 14, st, 64) == 6);
    CHECK(st[0].on && st[0].units == 1);
    CHECK(!st[1].on && st[1].units == 1);
    CHECK(st[2].on && st[2].units == 3);
    CHECK(!st[3].on && st[3].units == 3);
    CHECK(st[4].on && st[4].units == 1);
    CHECK(!st[5].on && st[5].units == 14);
    /* Tail 0 still leaves a gap. */
    CHECK(d32_morse_timeline("E", 0, st, 64) == 2 && st[1].units == 1);
    /* "0": 5 dashes, 4 gaps: 19 units on+off before the tail. */
    int n = d32_morse_timeline("0", 7, st, 64);
    CHECK(n == 10);
    unsigned units = 0;
    for (int i = 0; i < n - 1; i++) {
        units += st[i].units;
    }
    CHECK(units == 19);
    /* Worst case for a 6-char code fits in 60 steps. */
    CHECK(d32_morse_timeline("000000", 14, st, 60) == 60);
    CHECK(d32_morse_timeline("000000", 14, st, 59) == -1);
    /* Steps alternate on/off, starting on. */
    n = d32_morse_timeline("3E9D01", 14, st, 64);
    CHECK(n > 0);
    for (int i = 0; i < n; i++) {
        CHECK(st[i].on == ((i % 2) == 0));
    }
    CHECK(d32_morse_timeline("", 7, st, 64) == -1);
    CHECK(d32_morse_timeline("12G", 7, st, 64) == -1);
    CHECK(d32_morse_timeline(NULL, 7, st, 64) == -1);
}

static bool is_perm(const uint8_t *v, int n)
{
    unsigned seen = 0;
    for (int i = 0; i < n; i++) {
        if (v[i] >= n || (seen & (1u << v[i]))) {
            return false;
        }
        seen |= 1u << v[i];
    }
    return true;
}

/* Independent re-derivation of the documented algorithm. */
static void expected_perm(uint32_t seed, const char *what, uint8_t *out, int n)
{
    char label[32];
    uint8_t rnd[8];
    snprintf(label, sizeof(label), "D32:%08X:%s", (unsigned)seed, what);
    ctf_derive(label, rnd, (size_t)n);
    for (int i = 0; i < n; i++) {
        out[i] = (uint8_t)i;
    }
    for (int i = n - 1; i > 0; i--) {
        int j = rnd[i] % (i + 1);
        uint8_t t = out[i];
        out[i] = out[j];
        out[j] = t;
    }
}

static void test_patch_pattern(void)
{
    ctf_init(TEST_MAC_A, NULL);
    uint8_t p[6], q[6], want[6];
    d32_patch_pattern(SEED_A, p);
    d32_patch_pattern(SEED_A, q);
    CHECK(is_perm(p, 6));
    CHECK(memcmp(p, q, 6) == 0);
    expected_perm(SEED_A, "patch", want, 6);
    CHECK(memcmp(p, want, 6) == 0);
    /* Different seeds give different patterns (at least one of 16). */
    bool differs = false;
    for (uint32_t s = 1; s <= 16; s++) {
        d32_patch_pattern(SEED_A + s, q);
        CHECK(is_perm(q, 6));
        differs |= memcmp(p, q, 6) != 0;
    }
    CHECK(differs);
    /* Board specific: another MAC gives another pattern for some seed. */
    ctf_init(TEST_MAC_B, NULL);
    differs = false;
    for (uint32_t s = 0; s < 16; s++) {
        d32_patch_pattern(SEED_A + s, q);
        ctf_init(TEST_MAC_A, NULL);
        d32_patch_pattern(SEED_A + s, want);
        ctf_init(TEST_MAC_B, NULL);
        differs |= memcmp(want, q, 6) != 0;
    }
    CHECK(differs);
    ctf_init(TEST_MAC_A, NULL);
}

static void test_patch_match_and_hint(void)
{
    const uint8_t perm[6] = { 3, 0, 5, 1, 4, 2 };
    uint8_t conn[6];
    for (int a = 0; a < 6; a++) {
        conn[a] = (uint8_t)(1u << perm[a]);
    }
    CHECK(d32_patch_matches(conn, perm));
    conn[2] |= 1u << 0; /* extra lead on A3 */
    CHECK(!d32_patch_matches(conn, perm));
    conn[2] = 1u << perm[2];
    conn[5] = 0;        /* A6 unpatched */
    CHECK(!d32_patch_matches(conn, perm));
    conn[5] = 1u << perm[4]; /* wrong post */
    CHECK(!d32_patch_matches(conn, perm));

    char hint[48];
    CHECK(d32_patch_hint(perm, hint, sizeof(hint)) == 35);
    CHECK(strcmp(hint, "A1-B4 A2-B1 A3-B6 A4-B2 A5-B5 A6-B3") == 0);
    CHECK(d32_patch_hint(perm, hint, 36) == 35);
    CHECK(d32_patch_hint(perm, hint, 35) == -1 && hint[0] == '\0');
}

static void test_touch_sequence(void)
{
    ctf_init(TEST_MAC_A, NULL);
    uint8_t seq[4], want[4];
    d32_touch_sequence(SEED_B, seq);
    CHECK(is_perm(seq, 4));
    expected_perm(SEED_B, "touch", want, 4);
    CHECK(memcmp(seq, want, 4) == 0);

    d32_seqm_t m;
    d32_seqm_init(&m, seq);
    CHECK(d32_seqm_feed(&m, seq[0]) == D32_SEQ_PROGRESS);
    CHECK(d32_seqm_feed(&m, seq[1]) == D32_SEQ_PROGRESS);
    CHECK(d32_seqm_feed(&m, seq[2]) == D32_SEQ_PROGRESS);
    CHECK(d32_seqm_feed(&m, seq[3]) == D32_SEQ_DONE);
    CHECK(m.pos == 0);
    /* Wrong pad restarts; a wrong pad that is the first of the sequence counts as step 1. */
    CHECK(d32_seqm_feed(&m, seq[0]) == D32_SEQ_PROGRESS);
    CHECK(d32_seqm_feed(&m, seq[2]) == D32_SEQ_WRONG);
    CHECK(m.pos == 0);
    CHECK(d32_seqm_feed(&m, seq[0]) == D32_SEQ_PROGRESS);
    CHECK(d32_seqm_feed(&m, seq[0]) == D32_SEQ_WRONG);
    CHECK(m.pos == 1);
    CHECK(d32_seqm_feed(&m, seq[1]) == D32_SEQ_PROGRESS);
    CHECK(d32_seqm_feed(&m, seq[2]) == D32_SEQ_PROGRESS);
    CHECK(d32_seqm_feed(&m, seq[3]) == D32_SEQ_DONE);
}

static void expected_pin(uint32_t seed, unsigned counter, char out[7])
{
    char label[40];
    uint8_t b[3];
    if (counter == 0) {
        snprintf(label, sizeof(label), "D32:%08X:menu", (unsigned)seed);
    } else {
        snprintf(label, sizeof(label), "D32:%08X:menu:%u", (unsigned)seed, counter);
    }
    ctf_derive(label, b, 3);
    snprintf(out, 7, "%02X%02X%02X", b[0], b[1], b[2]);
}

static void test_service_pin(void)
{
    ctf_init(TEST_MAC_A, NULL);
    char pin[7], again[7], want[7];
    CHECK(d32_service_pin(SEED_A, NULL, 0, pin) == 0);
    CHECK(d32_service_pin(SEED_A, NULL, 0, again) == 0);
    CHECK(strlen(pin) == 6);
    CHECK(strcmp(pin, again) == 0);
    expected_pin(SEED_A, 0, want);
    CHECK(strcmp(pin, want) == 0);
    for (uint32_t s = 0; s < 64; s++) {
        d32_service_pin(s * 2654435761u, NULL, 0, pin);
        for (int i = 0; i < 6; i++) {
            CHECK(isxdigit((unsigned char)pin[i]) && !islower((unsigned char)pin[i]));
        }
    }
    /* Never equal to a module code of the round (checked against the engine). */
    d32_t d;
    setup(&d, NULL);
    CHECK(d32_arm(&d, SEED_B) == D32_ARM_OK);
    char codes[D32_SLOTS][7];
    const char *list[D32_SLOTS];
    for (int i = 0; i < D32_SLOTS; i++) {
        list[i] = d32_code_for(&d, i, codes[i]) ? codes[i] : NULL;
    }
    CHECK(d32_service_pin(SEED_B, list, D32_SLOTS, pin) >= 0);
    for (int i = 0; i < D32_SLOTS; i++) {
        CHECK(strcmp(pin, codes[i]) != 0);
    }
    /* The PIN is checked before the engine: a code equal to it would be a
     * strike there, so it must not exist. */
    CHECK(d32_submit_code(&d, pin, NULL) == D32_CODE_REJECTED);
}

static void test_service_pin_collision(void)
{
    ctf_init(TEST_MAC_A, NULL);
    char c0[7], c1[7], c2[7], pin[7];
    expected_pin(SEED_A, 0, c0);
    expected_pin(SEED_A, 1, c1);
    expected_pin(SEED_A, 2, c2);
    CHECK(strcmp(c0, c1) != 0 && strcmp(c1, c2) != 0);
    /* A module code equal to the counter-0 PIN: derive again with counter 1. */
    const char *one[] = { "000000", c0, NULL, "" };
    CHECK(d32_service_pin(SEED_A, one, 4, pin) == 1);
    CHECK(strcmp(pin, c1) == 0);
    /* Both counter 0 and 1 taken: counter 2. */
    const char *two[] = { c1, "ABCDEF", c0 };
    CHECK(d32_service_pin(SEED_A, two, 3, pin) == 2);
    CHECK(strcmp(pin, c2) == 0);
    /* Codes that do not collide change nothing. */
    const char *none[] = { "123456", "ABCDEF" };
    if (strcmp(c0, "123456") != 0 && strcmp(c0, "ABCDEF") != 0) {
        CHECK(d32_service_pin(SEED_A, none, 2, pin) == 0);
        CHECK(strcmp(pin, c0) == 0);
    }
}

static void test_base64(void)
{
    char out[16];
    CHECK(d32_base64((const uint8_t *)"foobar", 6, out, sizeof(out)) == 8);
    CHECK(strcmp(out, "Zm9vYmFy") == 0);
    CHECK(d32_base64((const uint8_t *)"fooba", 5, out, sizeof(out)) == 8 && strcmp(out, "Zm9vYmE=") == 0);
    CHECK(d32_base64((const uint8_t *)"foob", 4, out, sizeof(out)) == 8 && strcmp(out, "Zm9vYg==") == 0);
    CHECK(d32_base64((const uint8_t *)"f", 1, out, sizeof(out)) == 4 && strcmp(out, "Zg==") == 0);
    CHECK(d32_base64((const uint8_t *)"", 0, out, sizeof(out)) == 0 && out[0] == '\0');
    CHECK(d32_base64((const uint8_t *)"3E9D01", 6, out, sizeof(out)) == 8 && strcmp(out, "M0U5RDAx") == 0);
    const uint8_t hi[3] = { 0xFB, 0xFF, 0xBF };
    CHECK(d32_base64(hi, 3, out, sizeof(out)) == 4 && strcmp(out, "+/+/") == 0);
    CHECK(d32_base64((const uint8_t *)"foobar", 6, out, 9) == 8);
    CHECK(d32_base64((const uint8_t *)"foobar", 6, out, 8) == -1 && out[0] == '\0');
}

static void test_debounce(void)
{
    d32_debounce_t db;
    memset(&db, 0, sizeof(db));
    uint16_t on, off;
    CHECK(d32_debounce_feed(&db, 0x0001, 2, &on, &off) == 0 && on == 0);
    CHECK(d32_debounce_feed(&db, 0x0001, 2, &on, &off) == 0x0001 && on == 0x0001 && off == 0);
    CHECK(d32_debounce_feed(&db, 0x0001, 2, &on, &off) == 0x0001 && on == 0);
    /* A one-sample glitch is ignored. */
    CHECK(d32_debounce_feed(&db, 0x0000, 2, &on, &off) == 0x0001 && off == 0);
    CHECK(d32_debounce_feed(&db, 0x0001, 2, &on, &off) == 0x0001 && on == 0);
    CHECK(d32_debounce_feed(&db, 0x8000, 2, &on, &off) == 0x0001);
    CHECK(d32_debounce_feed(&db, 0x8000, 2, &on, &off) == 0x8000 && on == 0x8000 && off == 0x0001);
}

static void test_keyhold(void)
{
    d32_keyhold_t k;
    memset(&k, 0, sizeof(k));
    char dig = 0;
    /* Every key, D and E included, types its digit on release. */
    const char *keys = "0123456789ABCDEFabcdef";
    for (const char *p = keys; *p; p++) {
        CHECK(d32_keyhold_press(&k, *p, 100, &dig) == D32_KEY_NONE);
        CHECK(d32_keyhold_tick(&k, 150) == D32_KEY_NONE);
        dig = 0;
        CHECK(d32_keyhold_release(&k, *p, 200, &dig) == D32_KEY_DIGIT);
        CHECK(dig == (char)toupper((unsigned char)*p));
    }
    CHECK(d32_keyhold_press(&k, 'G', 0, &dig) == D32_KEY_NONE && k.held == 0);
    /* Hold 800 ms: clear once, the key types nothing. */
    CHECK(d32_keyhold_press(&k, '7', 1000, &dig) == D32_KEY_NONE);
    CHECK(d32_keyhold_tick(&k, 1000 + D32_ML_CLEAR_MS - 1) == D32_KEY_NONE);
    CHECK(d32_keyhold_tick(&k, 1000 + D32_ML_CLEAR_MS) == D32_KEY_CLEAR);
    CHECK(d32_keyhold_tick(&k, 1000 + 3 * D32_ML_CLEAR_MS) == D32_KEY_NONE);
    CHECK(d32_keyhold_release(&k, '7', 4000, &dig) == D32_KEY_NONE);
    /* Long hold with no tick in between: the release clears, no digit. */
    CHECK(d32_keyhold_press(&k, 'E', 5000, &dig) == D32_KEY_NONE);
    CHECK(d32_keyhold_release(&k, 'E', 5000 + D32_ML_CLEAR_MS, &dig) == D32_KEY_CLEAR);
    /* Rolled typing: pressing the next key types the one still down. */
    CHECK(d32_keyhold_press(&k, '1', 6000, &dig) == D32_KEY_NONE);
    dig = 0;
    CHECK(d32_keyhold_press(&k, '2', 6050, &dig) == D32_KEY_DIGIT && dig == '1');
    CHECK(d32_keyhold_release(&k, '1', 6080, &dig) == D32_KEY_NONE);
    CHECK(d32_keyhold_release(&k, '2', 6100, &dig) == D32_KEY_DIGIT && dig == '2');
    /* A cleared key does not count as rolled when the next one is pressed. */
    CHECK(d32_keyhold_press(&k, '3', 7000, &dig) == D32_KEY_NONE);
    CHECK(d32_keyhold_tick(&k, 7000 + D32_ML_CLEAR_MS) == D32_KEY_CLEAR);
    CHECK(d32_keyhold_press(&k, '4', 8000, &dig) == D32_KEY_NONE);
    CHECK(d32_keyhold_release(&k, '3', 8010, &dig) == D32_KEY_NONE);
    CHECK(d32_keyhold_release(&k, '4', 8020, &dig) == D32_KEY_DIGIT && dig == '4');
    /* Clock wrap. */
    CHECK(d32_keyhold_press(&k, 'A', 0xFFFFFF00u, &dig) == D32_KEY_NONE);
    CHECK(d32_keyhold_tick(&k, 0xFFFFFF00u + D32_ML_CLEAR_MS) == D32_KEY_CLEAR);
}

static void test_entry(void)
{
    d32_entry_t e;
    d32_entry_clear(&e);
    CHECK(d32_entry_check(&e, "12ABDE") == D32_ENTRY_PARTIAL);
    CHECK(!d32_entry_idle(&e, 999999)); /* empty never times out */
    CHECK(!d32_entry_add(&e, 'G', 0));
    CHECK(d32_entry_add(&e, '1', 100) && d32_entry_add(&e, '2', 200) && d32_entry_add(&e, 'a', 300));
    CHECK(d32_entry_check(&e, "12ABDE") == D32_ENTRY_PARTIAL);
    CHECK(!d32_entry_idle(&e, 300 + D32_ML_IDLE_MS - 1));
    CHECK(d32_entry_idle(&e, 300 + D32_ML_IDLE_MS));
    CHECK(d32_entry_add(&e, 'B', 400) && d32_entry_add(&e, 'd', 500) && d32_entry_add(&e, 'E', 600));
    CHECK(strcmp(e.buf, "12ABDE") == 0 && e.len == 6);
    CHECK(!d32_entry_add(&e, '0', 700));
    CHECK(d32_entry_check(&e, "12ABDE") == D32_ENTRY_SERVICE);
    CHECK(d32_entry_check(&e, NULL) == D32_ENTRY_SUBMIT);
    CHECK(d32_entry_check(&e, "12ABDF") == D32_ENTRY_SUBMIT);
    d32_entry_clear(&e);
    CHECK(e.len == 0 && e.buf[0] == '\0');
}

/* Keypad model: press/release every key of `code` (no hold), auto-submit on
 * the 6th. Returns what the 6th digit produced. */
static d32_entry_result_t type_code(const char *code, const char *pin, d32_entry_t *e, uint32_t *t)
{
    d32_keyhold_t k;
    memset(&k, 0, sizeof(k));
    d32_entry_result_t r = D32_ENTRY_PARTIAL;
    for (const char *p = code; *p; p++) {
        char dig = 0;
        CHECK(d32_keyhold_press(&k, *p, *t, &dig) == D32_KEY_NONE);
        *t += 60;
        CHECK(d32_keyhold_tick(&k, *t) == D32_KEY_NONE);
        if (d32_keyhold_release(&k, *p, *t, &dig) == D32_KEY_DIGIT && d32_entry_add(e, dig, *t)) {
            r = d32_entry_check(e, pin);
        }
        *t += 60;
    }
    return r;
}

static void test_keypad_disarms_round(void)
{
    d32_t d;
    setup(&d, NULL);
    CHECK(d32_arm(&d, SEED_A) == D32_ARM_OK);
    char codes[D32_SLOTS][7];
    const char *list[D32_SLOTS];
    for (int i = 0; i < D32_SLOTS; i++) {
        list[i] = d32_code_for(&d, i, codes[i]) ? codes[i] : NULL;
    }
    char pin[7];
    CHECK(d32_service_pin(SEED_A, list, D32_SLOTS, pin) >= 0);
    uint32_t t = 1000;
    /* The service PIN opens the menu and never reaches the engine. */
    d32_entry_t e;
    d32_entry_clear(&e);
    CHECK(type_code(pin, pin, &e, &t) == D32_ENTRY_SERVICE);
    CHECK(d32_strikes(&d) == 0);
    for (int i = 0; i < D32_SLOTS; i++) {
        d32_entry_clear(&e);
        CHECK(type_code(codes[i], pin, &e, &t) == D32_ENTRY_SUBMIT);
        CHECK(strcmp(e.buf, codes[i]) == 0);
        CHECK(d32_submit_code(&d, e.buf, NULL) == D32_CODE_DISARMED);
    }
    CHECK(d32_phase(&d) == D32_FINAL);
    CHECK(d32_strikes(&d) == 0);
}

void run_modlogic_tests(void)
{
    RUN(test_morse_symbols);
    RUN(test_morse_timeline);
    RUN(test_patch_pattern);
    RUN(test_patch_match_and_hint);
    RUN(test_touch_sequence);
    RUN(test_service_pin);
    RUN(test_service_pin_collision);
    RUN(test_base64);
    RUN(test_debounce);
    RUN(test_keyhold);
    RUN(test_entry);
    RUN(test_keypad_disarms_round);
}
