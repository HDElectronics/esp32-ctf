/* Scoring, hint cost, progress record persistence / tamper detection, reset, locking. */
#include <string.h>

#include "test_util.h"

static void solve(const char *id)
{
    char f[18];
    ctf_flag(id, f);
    CHECK(ctf_submit(f, NULL) == CTF_SUBMIT_NEW);
}

static void test_hint_and_score(void)
{
    mem_store_t st;
    mem_store_clear(&st);
    ctf_backend_t be = mem_backend(&st);
    ctf_init(TEST_MAC_A, &be);

    CHECK(ctf_score() == 0);
    CHECK(ctf_hint("NOPE-01") == NULL);
    CHECK(ctf_hint(NULL) == NULL);
    CHECK(!ctf_hint_used("NOPE-01"));
    CHECK(!ctf_is_solved("NOPE-01"));

    solve("BLE-01"); /* easy, no hint */
    CHECK(ctf_score() == 100);

    const char *h = ctf_hint("BLE-04"); /* medium, hint before solve */
    CHECK(h != NULL && h == ctf_find("BLE-04")->hint);
    CHECK(ctf_hint_used("BLE-04"));
    CHECK(ctf_score() == 100); /* hint alone costs nothing until solved */
    int saves = st.saves;
    CHECK(ctf_hint("BLE-04") == h); /* second request: no new state, no save */
    CHECK(st.saves == saves);
    solve("BLE-04");
    CHECK(ctf_score() == 100 + 150);

    ctf_hint("RE-03"); /* hard with hint */
    solve("RE-03");
    CHECK(ctf_score() == 100 + 150 + 225);

    solve("CRY-02"); /* hard, no hint */
    CHECK(ctf_score() == 100 + 150 + 225 + 300);

    ctf_hint("BLE-01"); /* hint after solving still costs 25% */
    CHECK(ctf_score() == 75 + 150 + 225 + 300);

    /* Hints persist across init. */
    ctf_init(TEST_MAC_A, &be);
    CHECK(ctf_hint_used("BLE-04") && ctf_hint_used("RE-03") && ctf_hint_used("BLE-01"));
    CHECK(!ctf_hint_used("CRY-02"));
    CHECK(ctf_score() == 75 + 150 + 225 + 300);

    /* Solving everything with no hints reaches the max score. */
    ctf_reset();
    for (size_t i = 0; i < ctf_count(); i++) {
        solve(ctf_get(i)->id);
    }
    CHECK(ctf_score() == ctf_max_score(true));
    CHECK(st.depth == 0 && st.max_depth == 1);
}

static void test_fresh_and_persist(void)
{
    mem_store_t st;
    mem_store_clear(&st);
    ctf_backend_t be = mem_backend(&st);

    ctf_init(TEST_MAC_A, &be); /* missing record -> fresh state, saved */
    CHECK(st.has && st.saves == 1);
    CHECK(ctf_score() == 0);

    solve("SER-01");
    CHECK(st.saves == 2);
    ctf_hint("SER-03");
    CHECK(st.saves == 3);

    ctf_init(TEST_MAC_A, &be);
    CHECK(st.saves == 3); /* valid record: loaded, not rewritten */
    CHECK(ctf_is_solved("SER-01") && ctf_hint_used("SER-03"));

    /* The tag is board specific: another MAC rejects this record. */
    mem_store_t copy = st;
    ctf_backend_t be2 = mem_backend(&copy);
    ctf_init(TEST_MAC_B, &be2);
    CHECK(!ctf_is_solved("SER-01") && !ctf_hint_used("SER-03"));
}

static void test_tampered_record(void)
{
    mem_store_t st;
    mem_store_clear(&st);
    ctf_backend_t be = mem_backend(&st);
    ctf_init(TEST_MAC_A, &be);
    solve("HW-02");
    ctf_hint("HW-06");
    mem_store_t good = st;
    CHECK(good.len > 0);

    bool all_rejected = true;
    bool all_rewritten = true;
    for (size_t i = 0; i < good.len; i++) {
        for (int bit = 0; bit < 8; bit++) {
            mem_store_t t = good;
            t.buf[i] ^= (uint8_t)(1u << bit);
            ctf_backend_t tb = mem_backend(&t);
            ctf_init(TEST_MAC_A, &tb);
            if (ctf_is_solved("HW-02") || ctf_hint_used("HW-06") || ctf_score() != 0) {
                all_rejected = false;
            }
            /* Fresh state was saved over the bad record. */
            if (t.saves != good.saves + 1 || memcmp(t.buf, good.buf, good.len) == 0) {
                all_rewritten = false;
            }
        }
    }
    CHECK(all_rejected);
    CHECK(all_rewritten);

    /* Wrong size -> fresh. */
    mem_store_t t = good;
    t.len = good.len - 1;
    ctf_backend_t tb = mem_backend(&t);
    ctf_init(TEST_MAC_A, &tb);
    CHECK(!ctf_is_solved("HW-02"));
    CHECK(t.len == good.len);

    /* The untouched record still loads. */
    mem_store_t ok = good;
    ctf_backend_t ob = mem_backend(&ok);
    ctf_init(TEST_MAC_A, &ob);
    CHECK(ctf_is_solved("HW-02") && ctf_hint_used("HW-06"));
}

static void test_reset(void)
{
    mem_store_t st;
    mem_store_clear(&st);
    ctf_backend_t be = mem_backend(&st);
    ctf_init(TEST_MAC_A, &be);
    solve("WEB-01");
    ctf_hint("WEB-09");
    int saves = st.saves;
    ctf_reset();
    CHECK(st.saves == saves + 1);
    CHECK(!ctf_is_solved("WEB-01") && !ctf_hint_used("WEB-09"));
    CHECK(ctf_score() == 0);
    ctf_init(TEST_MAC_A, &be);
    CHECK(!ctf_is_solved("WEB-01") && !ctf_hint_used("WEB-09"));
    solve("WEB-01"); /* solvable again after reset */
    CHECK(st.depth == 0 && st.max_depth == 1 && st.locks > 0);
}

static void test_no_backend(void)
{
    ctf_init(TEST_MAC_A, NULL); /* memory only */
    CHECK(ctf_score() == 0);
    solve("BTC-01");
    CHECK(ctf_score() == 100);
    ctf_backend_t partial = {NULL, NULL, NULL, NULL, NULL};
    ctf_init(TEST_MAC_A, &partial);
    CHECK(ctf_score() == 0);
}

void run_progress_tests(void)
{
    RUN(test_hint_and_score);
    RUN(test_fresh_and_persist);
    RUN(test_tampered_record);
    RUN(test_reset);
    RUN(test_no_backend);
}
