/* Points wallet, hint tiers, progress record v2 persistence / tamper
 * detection / version handling, reset, locking. */
#include <string.h>

#include "ctf_sha256.h"
#include "test_util.h"

#define REC_LEN 41 /* v2: version + 3 x u64 + 16-byte tag */

static void solve(const char *id)
{
    char f[18];
    ctf_flag(id, f);
    CHECK(ctf_submit(f, NULL) == CTF_SUBMIT_NEW);
}

static int idx(const char *id)
{
    return (int)(ctf_find(id) - ctf_get(0));
}

static void put_u64(uint8_t *p, uint64_t v)
{
    for (int i = 0; i < 8; i++) {
        p[i] = (uint8_t)(v >> (8 * i));
    }
}

/* Builds a correctly tagged record for the board ctf_init last saw (the tag
 * key is derive("progress"), the public derivation). n_bitmaps = 2 gives the
 * v1 layout (33 bytes), 3 the v2 layout (41 bytes). Returns its length. */
static size_t forge(uint8_t *out, uint8_t version, int n_bitmaps, uint64_t a, uint64_t b,
                    uint64_t c)
{
    uint8_t kp[32], mac[32];
    size_t body = 1u + 8u * (size_t)n_bitmaps;
    out[0] = version;
    put_u64(out + 1, a);
    put_u64(out + 9, b);
    if (n_bitmaps == 3) {
        put_u64(out + 17, c);
    }
    ctf_derive("progress", kp, sizeof(kp));
    ctf_hmac_sha256(kp, sizeof(kp), out, body, mac);
    memcpy(out + body, mac, 16);
    return body + 16;
}

static void test_wallet_and_tiers(void)
{
    mem_store_t st;
    mem_store_clear(&st);
    ctf_backend_t be = mem_backend(&st);
    ctf_init(TEST_MAC_A, &be);
    const char *txt = NULL;

    CHECK(ctf_points() == 100 && ctf_earned() == 0 && ctf_spent() == 0);
    CHECK(ctf_hint_tier("BLE-01") == 1);
    CHECK(ctf_hint_tier("NOPE-01") == 0);
    CHECK(ctf_hint_tier(NULL) == 0);
    CHECK(!ctf_is_solved("NOPE-01"));
    CHECK(ctf_hint_buy("NOPE-01", 1, &txt) == CTF_HINT_BAD && txt == NULL);
    CHECK(ctf_hint_buy(NULL, 1, &txt) == CTF_HINT_BAD);
    CHECK(ctf_hint_buy("BLE-01", 0, &txt) == CTF_HINT_BAD && txt == NULL);
    CHECK(ctf_hint_buy("BLE-01", 4, &txt) == CTF_HINT_BAD && txt == NULL);

    /* Tier 1: free, always OK, records nothing (no save). */
    int saves = st.saves;
    CHECK(ctf_hint_buy("BLE-04", 1, &txt) == CTF_HINT_OK && txt == ctf_find("BLE-04")->hint[0]);
    CHECK(st.saves == saves && ctf_hint_tier("BLE-04") == 1 && ctf_points() == 100);

    /* Buy order: tier 3 before tier 2 is LOCKED, no state change. */
    CHECK(ctf_hint_buy("BLE-04", 3, &txt) == CTF_HINT_LOCKED && txt == NULL);
    CHECK(st.saves == saves && ctf_hint_tier("BLE-04") == 1 && ctf_points() == 100);

    /* Tier 2 of a medium costs 40. */
    CHECK(ctf_hint_buy("BLE-04", 2, &txt) == CTF_HINT_OK && txt == ctf_find("BLE-04")->hint[1]);
    CHECK(st.saves == saves + 1);
    CHECK(ctf_hint_tier("BLE-04") == 2 && ctf_points() == 60 && ctf_spent() == 40);

    /* Owned tier: free again, no save. Tier 1 still shows. */
    saves = st.saves;
    CHECK(ctf_hint_buy("BLE-04", 2, &txt) == CTF_HINT_OK && txt == ctf_find("BLE-04")->hint[1]);
    CHECK(ctf_hint_buy("BLE-04", 1, NULL) == CTF_HINT_OK);
    CHECK(st.saves == saves && ctf_points() == 60);

    /* Not enough points: tier 3 of BLE-04 costs 100 > 60 -> POINTS, no change. */
    CHECK(ctf_hint_buy("BLE-04", 3, &txt) == CTF_HINT_POINTS && txt == NULL);
    CHECK(st.saves == saves && ctf_hint_tier("BLE-04") == 2 && ctf_points() == 60);

    /* Solving adds the full value, even with hints bought. */
    solve("BLE-04");
    CHECK(ctf_earned() == 200 && ctf_points() == 260);
    CHECK(ctf_hint_buy("BLE-04", 3, &txt) == CTF_HINT_OK && txt == ctf_find("BLE-04")->hint[2]);
    CHECK(ctf_hint_tier("BLE-04") == 3 && ctf_spent() == 140 && ctf_points() == 160);
    /* Owned tier 3: free, and tier 2 stays owned. */
    saves = st.saves;
    CHECK(ctf_hint_buy("BLE-04", 3, NULL) == CTF_HINT_OK);
    CHECK(ctf_hint_buy("BLE-04", 2, NULL) == CTF_HINT_OK);
    CHECK(st.saves == saves && ctf_points() == 160);

    /* Spend down to 10 points. Hard tier 2 = 60, tier 3 = 150; easy 20 / 50. */
    CHECK(ctf_hint_buy("RE-03", 2, NULL) == CTF_HINT_OK && ctf_points() == 100);
    CHECK(ctf_hint_buy("RE-03", 3, NULL) == CTF_HINT_POINTS && ctf_points() == 100);
    CHECK(ctf_hint_buy("BLE-01", 2, NULL) == CTF_HINT_OK && ctf_points() == 80);
    CHECK(ctf_hint_buy("BLE-01", 3, NULL) == CTF_HINT_OK && ctf_points() == 30);
    CHECK(ctf_hint_buy("SER-03", 2, NULL) == CTF_HINT_POINTS); /* hard: 60 > 30 */
    CHECK(ctf_hint_buy("BLE-02", 2, NULL) == CTF_HINT_OK && ctf_points() == 10);
    CHECK(ctf_hint_buy("BLE-03", 2, NULL) == CTF_HINT_POINTS && ctf_points() == 10);
    CHECK(ctf_points() == 100 + 200 - (40 + 100 + 60 + 20 + 50 + 20));

    /* Buying after solving, then solving more. */
    solve("BLE-01");
    CHECK(ctf_points() == 110 && ctf_earned() == 300 && ctf_spent() == 290);
    solve("CRY-02");
    CHECK(ctf_points() == 410);

    /* Everything persists across init. */
    ctf_init(TEST_MAC_A, &be);
    CHECK(ctf_points() == 410 && ctf_earned() == 600 && ctf_spent() == 290);
    CHECK(ctf_hint_tier("BLE-04") == 3 && ctf_hint_tier("RE-03") == 2 &&
          ctf_hint_tier("BLE-01") == 3 && ctf_hint_tier("BLE-02") == 2 &&
          ctf_hint_tier("BLE-03") == 1 && ctf_hint_tier("CRY-02") == 1);

    /* Solving everything with no hints: 100 + max score = 7400. */
    ctf_reset();
    for (size_t i = 0; i < ctf_count(); i++) {
        solve(ctf_get(i)->id);
    }
    CHECK(ctf_earned() == ctf_max_score(true) && ctf_points() == 7400);
    CHECK(st.depth == 0 && st.max_depth == 1);
}

static void test_fresh_and_persist(void)
{
    mem_store_t st;
    mem_store_clear(&st);
    ctf_backend_t be = mem_backend(&st);

    ctf_init(TEST_MAC_A, &be); /* missing record -> fresh state, saved */
    CHECK(st.has && st.saves == 1 && st.len == REC_LEN && st.buf[0] == 2);
    CHECK(ctf_points() == 100);

    solve("SER-01");
    CHECK(st.saves == 2);
    CHECK(ctf_hint_buy("SER-03", 2, NULL) == CTF_HINT_OK);
    CHECK(st.saves == 3);
    CHECK(ctf_hint_buy("SER-01", 2, NULL) == CTF_HINT_OK);
    CHECK(ctf_hint_buy("SER-01", 3, NULL) == CTF_HINT_OK);
    CHECK(st.saves == 5);

    /* v2 layout on the wire. */
    uint8_t want[REC_LEN];
    uint64_t b1 = (uint64_t)1 << idx("SER-01"), b3 = (uint64_t)1 << idx("SER-03");
    CHECK(forge(want, 2, 3, b1, b1 | b3, b1) == REC_LEN);
    CHECK(memcmp(st.buf, want, REC_LEN) == 0);

    ctf_init(TEST_MAC_A, &be);
    CHECK(st.saves == 5); /* valid record: loaded, not rewritten */
    CHECK(ctf_is_solved("SER-01") && ctf_hint_tier("SER-03") == 2 && ctf_hint_tier("SER-01") == 3);
    CHECK(ctf_points() == 100 + 100 - 60 - 20 - 50);

    /* The tag is board specific: another MAC rejects this record. */
    mem_store_t copy = st;
    ctf_backend_t be2 = mem_backend(&copy);
    ctf_init(TEST_MAC_B, &be2);
    CHECK(!ctf_is_solved("SER-01") && ctf_hint_tier("SER-03") == 1 && ctf_points() == 100);
}

static void test_record_versions(void)
{
    mem_store_t st;
    mem_store_clear(&st);
    ctf_backend_t be = mem_backend(&st);
    ctf_init(TEST_MAC_A, &be);
    uint64_t sb = (uint64_t)1 << idx("HW-02"), hb = (uint64_t)1 << idx("HW-06");

    /* A correctly tagged v1 record (33 bytes) -> fresh start, rewritten as v2. */
    mem_store_t v1;
    mem_store_clear(&v1);
    v1.len = forge(v1.buf, 1, 2, sb, hb, 0);
    v1.has = true;
    CHECK(v1.len == 33);
    ctf_backend_t b1 = mem_backend(&v1);
    ctf_init(TEST_MAC_A, &b1);
    CHECK(!ctf_is_solved("HW-02") && ctf_hint_tier("HW-06") == 1 && ctf_points() == 100);
    CHECK(v1.saves == 1 && v1.len == REC_LEN && v1.buf[0] == 2);

    /* v2 length but version byte 1 (validly tagged) -> fresh. */
    mem_store_t vx;
    mem_store_clear(&vx);
    vx.len = forge(vx.buf, 1, 3, sb, hb, 0);
    vx.has = true;
    ctf_backend_t bx = mem_backend(&vx);
    ctf_init(TEST_MAC_A, &bx);
    CHECK(!ctf_is_solved("HW-02") && ctf_hint_tier("HW-06") == 1);
    CHECK(vx.saves == 1 && vx.buf[0] == 2);

    /* Validly tagged v2 with a tier-3 bit lacking its tier-2 bit: that tier-3
     * bit is dropped; a consistent pair survives. */
    uint64_t pb = (uint64_t)1 << idx("HW-05");
    mem_store_t v2;
    mem_store_clear(&v2);
    v2.len = forge(v2.buf, 2, 3, sb, pb, hb | pb);
    v2.has = true;
    ctf_backend_t b2 = mem_backend(&v2);
    ctf_init(TEST_MAC_A, &b2);
    CHECK(v2.saves == 0); /* valid tag: loaded as is */
    CHECK(ctf_is_solved("HW-02"));
    CHECK(ctf_hint_tier("HW-06") == 1); /* orphan tier 3 dropped */
    CHECK(ctf_hint_tier("HW-05") == 3);
    CHECK(ctf_spent() == 40 + 100);
    CHECK(ctf_hint_buy("HW-06", 3, NULL) == CTF_HINT_LOCKED);

    /* Bits beyond the catalogue are ignored. */
    mem_store_t hi;
    mem_store_clear(&hi);
    uint64_t junk = (uint64_t)1 << 63;
    hi.len = forge(hi.buf, 2, 3, sb | junk, junk, junk);
    hi.has = true;
    ctf_backend_t bh = mem_backend(&hi);
    ctf_init(TEST_MAC_A, &bh);
    CHECK(ctf_is_solved("HW-02") && ctf_earned() == 100 && ctf_spent() == 0);
}

static void test_tampered_record(void)
{
    mem_store_t st;
    mem_store_clear(&st);
    ctf_backend_t be = mem_backend(&st);
    ctf_init(TEST_MAC_A, &be);
    solve("HW-02");
    CHECK(ctf_hint_buy("HW-06", 2, NULL) == CTF_HINT_OK);
    CHECK(ctf_hint_buy("HW-06", 3, NULL) == CTF_HINT_OK);
    mem_store_t good = st;
    CHECK(good.len == REC_LEN);

    bool all_rejected = true;
    bool all_rewritten = true;
    for (size_t i = 0; i < good.len; i++) {
        for (int bit = 0; bit < 8; bit++) {
            mem_store_t t = good;
            t.buf[i] ^= (uint8_t)(1u << bit);
            ctf_backend_t tb = mem_backend(&t);
            ctf_init(TEST_MAC_A, &tb);
            if (ctf_is_solved("HW-02") || ctf_hint_tier("HW-06") != 1 || ctf_points() != 100) {
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
    CHECK(ctf_is_solved("HW-02") && ctf_hint_tier("HW-06") == 3);
}

static void test_reset(void)
{
    mem_store_t st;
    mem_store_clear(&st);
    ctf_backend_t be = mem_backend(&st);
    ctf_init(TEST_MAC_A, &be);
    solve("WEB-01");
    CHECK(ctf_hint_buy("WEB-09", 2, NULL) == CTF_HINT_OK);
    CHECK(ctf_hint_buy("WEB-01", 2, NULL) == CTF_HINT_OK);
    CHECK(ctf_hint_buy("WEB-01", 3, NULL) == CTF_HINT_OK);
    int saves = st.saves;
    ctf_reset();
    CHECK(st.saves == saves + 1);
    CHECK(!ctf_is_solved("WEB-01") && ctf_hint_tier("WEB-09") == 1 && ctf_hint_tier("WEB-01") == 1);
    CHECK(ctf_points() == 100 && ctf_earned() == 0 && ctf_spent() == 0);
    ctf_init(TEST_MAC_A, &be);
    CHECK(!ctf_is_solved("WEB-01") && ctf_hint_tier("WEB-09") == 1 && ctf_hint_tier("WEB-01") == 1);
    solve("WEB-01"); /* solvable again after reset */
    CHECK(ctf_hint_buy("WEB-01", 3, NULL) == CTF_HINT_LOCKED); /* tiers really cleared */
    CHECK(st.depth == 0 && st.max_depth == 1 && st.locks > 0);
}

static void test_no_backend(void)
{
    ctf_init(TEST_MAC_A, NULL); /* memory only */
    CHECK(ctf_points() == 100);
    solve("BTC-01");
    CHECK(ctf_points() == 200);
    CHECK(ctf_hint_buy("BTC-01", 2, NULL) == CTF_HINT_OK && ctf_points() == 180);
    ctf_backend_t partial = {NULL, NULL, NULL, NULL, NULL};
    ctf_init(TEST_MAC_A, &partial);
    CHECK(ctf_points() == 100 && ctf_hint_tier("BTC-01") == 1);
}

void run_progress_tests(void)
{
    RUN(test_wallet_and_tiers);
    RUN(test_fresh_and_persist);
    RUN(test_record_versions);
    RUN(test_tampered_record);
    RUN(test_reset);
    RUN(test_no_backend);
}
