/* Flag derivation, derived values, submission normalisation, answer gates. */
#include <string.h>

#include "test_util.h"

static bool is_upper_hex(const char *s, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        char c = s[i];
        if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'F'))) {
            return false;
        }
    }
    return true;
}

static void test_flag_format(void)
{
    ctf_init(TEST_MAC_A, NULL);
    for (size_t i = 0; i < ctf_count(); i++) {
        const char *id = ctf_get(i)->id;
        char flag[18], body[13];
        memset(flag, 'x', sizeof(flag));
        memset(body, 'x', sizeof(body));
        ctf_flag(id, flag);
        ctf_flag_body(id, body);
        CHECK(strlen(flag) == 17);
        CHECK(strncmp(flag, "ESP{", 4) == 0);
        CHECK(flag[16] == '}');
        CHECK(is_upper_hex(flag + 4, 12));
        CHECK(strlen(body) == 12);
        CHECK(memcmp(flag + 4, body, 12) == 0);

        /* Body is the upper hex of the first 6 derived bytes for the id. */
        uint8_t d[6];
        char hx[13];
        ctf_derive(id, d, sizeof(d));
        for (int j = 0; j < 6; j++) {
            snprintf(hx + 2 * j, 3, "%02X", d[j]);
        }
        CHECK(strcmp(hx, body) == 0);
    }
}

static void test_flag_determinism_and_mac(void)
{
    char a1[18], a2[18], b1[18];
    char all_a[40][13];
    ctf_init(TEST_MAC_A, NULL);
    ctf_flag("BLE-01", a1);
    for (size_t i = 0; i < ctf_count(); i++) {
        ctf_flag_body(ctf_get(i)->id, all_a[i]);
    }
    ctf_init(TEST_MAC_B, NULL);
    ctf_flag("BLE-01", b1);
    bool all_differ = true;
    for (size_t i = 0; i < ctf_count(); i++) {
        char b[13];
        ctf_flag_body(ctf_get(i)->id, b);
        if (strcmp(b, all_a[i]) == 0) {
            all_differ = false;
        }
    }
    ctf_init(TEST_MAC_A, NULL);
    ctf_flag("BLE-01", a2);

    CHECK(strcmp(a1, a2) == 0); /* same board, same flag after re-init */
    CHECK(strcmp(a1, b1) != 0); /* one MAC bit changes the flag */
    CHECK(all_differ);

    /* All 40 flags on one board are distinct. */
    bool distinct = true;
    for (size_t i = 0; i < ctf_count(); i++) {
        for (size_t j = i + 1; j < ctf_count(); j++) {
            if (strcmp(all_a[i], all_a[j]) == 0) {
                distinct = false;
            }
        }
    }
    CHECK(distinct);
}

static void test_derive(void)
{
    ctf_init(TEST_MAC_A, NULL);
    uint8_t s32[32], s80[80], again[80], other[32];
    ctf_derive("BLE-10:pin", s32, sizeof(s32));
    ctf_derive("BLE-10:pin", s80, sizeof(s80));
    ctf_derive("BLE-10:pin", again, sizeof(again));
    ctf_derive("BLE-09:passkey", other, sizeof(other));
    CHECK(memcmp(s32, s80, 32) == 0);           /* expansion keeps block 0 */
    CHECK(memcmp(s80, again, sizeof(s80)) == 0); /* deterministic */
    CHECK(memcmp(s80, s80 + 32, 32) != 0);       /* counter blocks differ */
    CHECK(memcmp(s80 + 32, s80 + 64, 16) != 0);
    CHECK(memcmp(s32, other, 32) != 0);          /* label sensitive */

    uint32_t u = ctf_derive_u32("BLE-10:pin");
    CHECK(u == (((uint32_t)s32[0] << 24) | ((uint32_t)s32[1] << 16) |
                ((uint32_t)s32[2] << 8) | s32[3]));

    ctf_init(TEST_MAC_B, NULL);
    CHECK(ctf_derive_u32("BLE-10:pin") != u); /* MAC sensitive */
}

static void test_submit_forms(void)
{
    mem_store_t st;
    char other_board[18];
    ctf_init(TEST_MAC_B, NULL);
    ctf_flag("WEB-03", other_board);

    mem_store_clear(&st);
    ctf_backend_t be = mem_backend(&st);
    ctf_init(TEST_MAC_A, &be);

    const ctf_challenge_t *m = (const ctf_challenge_t *)1;
    char flag[18], buf[64];

    /* Wrapped. */
    ctf_flag("BLE-01", flag);
    CHECK(ctf_submit(flag, &m) == CTF_SUBMIT_NEW);
    CHECK(m == ctf_find("BLE-01"));
    CHECK(ctf_is_solved("BLE-01"));
    CHECK(ctf_submit(flag, &m) == CTF_SUBMIT_ALREADY);
    CHECK(m == ctf_find("BLE-01"));

    /* Bare body. */
    ctf_flag_body("BLE-02", buf);
    CHECK(ctf_submit(buf, &m) == CTF_SUBMIT_NEW && m == ctf_find("BLE-02"));

    /* Lowercase body and lowercase / mixed-case prefix. */
    ctf_flag("BLE-03", flag);
    for (char *p = flag; *p; p++) {
        if (*p >= 'A' && *p <= 'Z') {
            *p = (char)(*p - 'A' + 'a');
        }
    }
    CHECK(strncmp(flag, "esp{", 4) == 0);
    CHECK(ctf_submit(flag, &m) == CTF_SUBMIT_NEW && m == ctf_find("BLE-03"));
    ctf_flag("BLE-04", flag);
    flag[0] = 'e';
    flag[2] = 'p';
    CHECK(ctf_submit(flag, NULL) == CTF_SUBMIT_NEW);

    /* Surrounding whitespace. */
    ctf_flag("BLE-05", flag);
    snprintf(buf, sizeof(buf), " \t\r\n%s \r\n", flag);
    CHECK(ctf_submit(buf, &m) == CTF_SUBMIT_NEW && m == ctf_find("BLE-05"));
    ctf_flag_body("BLE-06", flag);
    snprintf(buf, sizeof(buf), "  %s\n", flag);
    CHECK(ctf_submit(buf, &m) == CTF_SUBMIT_NEW && m == ctf_find("BLE-06"));

    int solved_score = ctf_points();

    /* Rejections: 11 / 13 chars, non-hex, other board's flag, junk. */
    char body[13];
    ctf_flag_body("BLE-07", body);
    snprintf(buf, sizeof(buf), "%.11s", body);
    CHECK(ctf_submit(buf, &m) == CTF_SUBMIT_WRONG && m == NULL);
    snprintf(buf, sizeof(buf), "%s0", body);
    CHECK(ctf_submit(buf, &m) == CTF_SUBMIT_WRONG && m == NULL);
    snprintf(buf, sizeof(buf), "ESP{%.11s}", body);
    CHECK(ctf_submit(buf, NULL) == CTF_SUBMIT_WRONG);
    snprintf(buf, sizeof(buf), "ESP{%s0}", body);
    CHECK(ctf_submit(buf, NULL) == CTF_SUBMIT_WRONG);
    snprintf(buf, sizeof(buf), "ESP{%.11sG}", body);
    CHECK(ctf_submit(buf, NULL) == CTF_SUBMIT_WRONG);
    snprintf(buf, sizeof(buf), "%.11sZ", body);
    CHECK(ctf_submit(buf, NULL) == CTF_SUBMIT_WRONG);
    snprintf(buf, sizeof(buf), "ESP{ %.11s}", body);
    CHECK(ctf_submit(buf, NULL) == CTF_SUBMIT_WRONG);
    snprintf(buf, sizeof(buf), "XSP{%s}", body);
    CHECK(ctf_submit(buf, NULL) == CTF_SUBMIT_WRONG);
    snprintf(buf, sizeof(buf), "ESP(%s)", body);
    CHECK(ctf_submit(buf, NULL) == CTF_SUBMIT_WRONG);
    snprintf(buf, sizeof(buf), "ESP{%s", body);
    CHECK(ctf_submit(buf, NULL) == CTF_SUBMIT_WRONG);
    CHECK(ctf_submit(other_board, &m) == CTF_SUBMIT_WRONG && m == NULL);
    CHECK(ctf_submit(other_board + 4, NULL) == CTF_SUBMIT_WRONG);
    CHECK(ctf_submit("000000000000", NULL) == CTF_SUBMIT_WRONG);
    CHECK(ctf_submit("", NULL) == CTF_SUBMIT_WRONG);
    CHECK(ctf_submit("   ", NULL) == CTF_SUBMIT_WRONG);
    CHECK(ctf_submit(NULL, &m) == CTF_SUBMIT_WRONG && m == NULL);
    CHECK(!ctf_is_solved("BLE-07"));
    CHECK(!ctf_is_solved("WEB-03"));
    CHECK(ctf_points() == solved_score);

    /* NEW persisted: re-init from the same store keeps it solved. */
    ctf_init(TEST_MAC_A, &be);
    CHECK(ctf_is_solved("BLE-01") && ctf_is_solved("BLE-06"));
    ctf_flag("BLE-01", flag);
    CHECK(ctf_submit(flag, NULL) == CTF_SUBMIT_ALREADY);
}

typedef struct {
    const char *expect;
    int calls;
    uint32_t derived;
} gate_ctx_t;

static bool gate_fn(const char *value, void *ctx)
{
    gate_ctx_t *g = ctx;
    g->calls++;
    /* Validators may call ctf_derive*: the engine lock must not be held. */
    g->derived = ctf_derive_u32("HW-03:hz");
    return strcmp(value, g->expect) == 0;
}

static void test_answer_gate(void)
{
    mem_store_t st;
    mem_store_clear(&st);
    ctf_backend_t be = mem_backend(&st);
    ctf_init(TEST_MAC_A, &be);

    gate_ctx_t g = {"4242", 0, 0};
    char out[18], want[18];
    memset(out, 'x', sizeof(out));

    CHECK(!ctf_answer("HW-03", "4242", out)); /* no validator yet */
    CHECK(!ctf_set_answer("HW-99", gate_fn, &g));
    CHECK(ctf_set_answer("HW-03", gate_fn, &g));
    CHECK(!ctf_answer("HW-03", "4241", out));
    CHECK(out[0] == 'x'); /* untouched on failure */
    CHECK(g.calls == 1);
    CHECK(!ctf_answer("HW-99", "4242", out));
    CHECK(!ctf_answer("HW-04", "4242", out)); /* gate is per challenge */
    CHECK(ctf_answer("HW-03", "4242", out));
    ctf_flag("HW-03", want);
    CHECK(strcmp(out, want) == 0);
    CHECK(g.derived == ctf_derive_u32("HW-03:hz"));
    CHECK(ctf_answer("HW-03", "4242", NULL));
    CHECK(!ctf_is_solved("HW-03")); /* player still submits the flag */
    CHECK(ctf_submit(out, NULL) == CTF_SUBMIT_NEW);
    CHECK(st.depth == 0 && st.max_depth == 1);

    CHECK(ctf_set_answer("HW-03", NULL, NULL));
    CHECK(!ctf_answer("HW-03", "4242", out));
}

void run_flag_tests(void)
{
    RUN(test_flag_format);
    RUN(test_flag_determinism_and_mac);
    RUN(test_derive);
    RUN(test_submit_forms);
    RUN(test_answer_gate);
}
