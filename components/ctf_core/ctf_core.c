/* ctf_core engine: flag derivation, submission, answer gates, points wallet,
 * hint tiers, tagged progress record. Portable C11, no IDF/FreeRTOS headers, no heap. */
#include "ctf_core.h"

#include <string.h>

#include "ctf_sha256.h"

/* K = KEY_A ^ KEY_B (SPEC "Flags": XOR-split, recombined only at runtime). */
static const uint8_t KEY_A[32] = {
    0xde, 0x1f, 0x64, 0x70, 0xa2, 0x7f, 0x84, 0x49, 0xd8, 0x99, 0x21, 0xa5, 0x71, 0x5f, 0x2d, 0xd9,
    0xae, 0x31, 0x44, 0xef, 0x76, 0x3a, 0xef, 0x7f, 0xf7, 0x8a, 0xda, 0x9d, 0x55, 0x2e, 0x9a, 0x83,
};
static const uint8_t KEY_B[32] = {
    0x84, 0x6a, 0x88, 0xc1, 0x99, 0x72, 0x06, 0x1e, 0x8d, 0xc3, 0x8d, 0xc3, 0x31, 0x53, 0x9d, 0x8d,
    0x98, 0xb3, 0x9d, 0x97, 0xd6, 0x3c, 0x65, 0x54, 0x4d, 0x46, 0xec, 0x87, 0xff, 0xec, 0x60, 0x4c,
};

/* Progress record v2 (41 bytes):
 *   [0]      version = 2
 *   [1..8]   solved bitmap (u64 LE)
 *   [9..16]  tier-2 bitmap (u64 LE)
 *   [17..24] tier-3 bitmap (u64 LE)
 *   [25..40] tag = HMAC-SHA256(derive("progress"), bytes 0..24)[0:16]
 * Bit i = catalogue index i. Invariant: tier3 bit implies tier2 bit. */
#define REC_VERSION  2u
#define REC_BODY_LEN (1u + 8u + 8u + 8u)
#define REC_TAG_LEN  16u
#define REC_LEN      (REC_BODY_LEN + REC_TAG_LEN)

/* The only mutable global: engine state. */
static struct {
    uint8_t mac[6];
    ctf_backend_t be;
    uint64_t solved;
    uint64_t tier2;
    uint64_t tier3;
    struct {
        ctf_answer_fn fn;
        void *ctx;
    } gate[CTF_MAX_CHALLENGES];
} s;

static void wipe(void *p, size_t n)
{
    volatile uint8_t *v = (volatile uint8_t *)p;
    while (n--) {
        *v++ = 0;
    }
}

static void lock(void)
{
    if (s.be.lock) {
        s.be.lock(s.be.ctx);
    }
}

static void unlock(void)
{
    if (s.be.unlock) {
        s.be.unlock(s.be.ctx);
    }
}

static int points_of(ctf_level_t level)
{
    switch (level) {
    case CTF_EASY: return 100;
    case CTF_MEDIUM: return 200;
    case CTF_HARD: return 300;
    }
    return 0;
}

/* Catalogue index of id, or -1. */
static int index_of(const char *id)
{
    const ctf_challenge_t *c = ctf_find(id);
    return c ? (int)(c - ctf_get(0)) : -1;
}

static uint64_t valid_mask(void)
{
    size_t n = ctf_count();
    return n >= 64 ? ~(uint64_t)0 : (((uint64_t)1 << n) - 1u);
}

static void hmac_start_k(ctf_hmac_ctx_t *h)
{
    /* Volatile reads keep the compiler from folding A^B into one literal. */
    const volatile uint8_t *a = KEY_A;
    const volatile uint8_t *b = KEY_B;
    uint8_t k[32];
    for (size_t i = 0; i < sizeof(k); i++) {
        k[i] = (uint8_t)(a[i] ^ b[i]);
    }
    ctf_hmac_init(h, k, sizeof(k));
    wipe(k, sizeof(k));
}

/* Block i of the derivation stream for label (caller holds the lock). */
static void derive_block(const char *label, uint32_t i, uint8_t out[CTF_SHA256_LEN])
{
    ctf_hmac_ctx_t h;
    hmac_start_k(&h);
    ctf_hmac_update(&h, s.mac, sizeof(s.mac));
    if (label) {
        ctf_hmac_update(&h, label, strlen(label));
    }
    if (i) {
        uint8_t ctr[4] = {(uint8_t)(i >> 24), (uint8_t)(i >> 16), (uint8_t)(i >> 8), (uint8_t)i};
        ctf_hmac_update(&h, ctr, sizeof(ctr));
    }
    ctf_hmac_final(&h, out);
    wipe(&h, sizeof(h));
}

static void derive_locked(const char *label, uint8_t *out, size_t len)
{
    uint8_t blk[CTF_SHA256_LEN];
    uint32_t i = 0;
    while (len) {
        size_t n = len < sizeof(blk) ? len : sizeof(blk);
        derive_block(label, i++, blk);
        memcpy(out, blk, n);
        out += n;
        len -= n;
    }
    wipe(blk, sizeof(blk));
}

static void body_locked(const char *id, char out[CTF_FLAG_BODY_LEN + 1])
{
    static const char hex[] = "0123456789ABCDEF";
    uint8_t d[CTF_FLAG_BODY_LEN / 2];
    derive_locked(id, d, sizeof(d));
    for (size_t i = 0; i < sizeof(d); i++) {
        out[2 * i] = hex[d[i] >> 4];
        out[2 * i + 1] = hex[d[i] & 0x0f];
    }
    out[CTF_FLAG_BODY_LEN] = '\0';
    wipe(d, sizeof(d));
}

static void flag_locked(const char *id, char out[CTF_FLAG_LEN + 1])
{
    memcpy(out, "ESP{", 4);
    body_locked(id, out + 4);
    out[4 + CTF_FLAG_BODY_LEN] = '}';
    out[CTF_FLAG_LEN] = '\0';
}

/* ---- progress record ---- */

static void put_u64(uint8_t *p, uint64_t v)
{
    for (int i = 0; i < 8; i++) {
        p[i] = (uint8_t)(v >> (8 * i));
    }
}

static uint64_t get_u64(const uint8_t *p)
{
    uint64_t v = 0;
    for (int i = 7; i >= 0; i--) {
        v = (v << 8) | p[i];
    }
    return v;
}

static void record_tag(const uint8_t body[REC_BODY_LEN], uint8_t tag[REC_TAG_LEN])
{
    uint8_t kp[CTF_SHA256_LEN];
    uint8_t mac[CTF_SHA256_LEN];
    derive_locked("progress", kp, sizeof(kp));
    ctf_hmac_sha256(kp, sizeof(kp), body, REC_BODY_LEN, mac);
    memcpy(tag, mac, REC_TAG_LEN);
    wipe(kp, sizeof(kp));
    wipe(mac, sizeof(mac));
}

static void save_locked(void)
{
    if (!s.be.save) {
        return;
    }
    uint8_t rec[REC_LEN];
    rec[0] = REC_VERSION;
    put_u64(rec + 1, s.solved);
    put_u64(rec + 9, s.tier2);
    put_u64(rec + 17, s.tier3);
    record_tag(rec, rec + REC_BODY_LEN);
    (void)s.be.save(rec, sizeof(rec), s.be.ctx);
}

static bool load_locked(void)
{
    uint8_t rec[REC_LEN];
    uint8_t tag[REC_TAG_LEN];
    if (!s.be.load || !s.be.load(rec, sizeof(rec), s.be.ctx)) {
        return false;
    }
    if (rec[0] != REC_VERSION) {
        return false;
    }
    record_tag(rec, tag);
    uint8_t diff = 0;
    for (size_t i = 0; i < REC_TAG_LEN; i++) {
        diff |= (uint8_t)(tag[i] ^ rec[REC_BODY_LEN + i]);
    }
    if (diff) {
        return false;
    }
    s.solved = get_u64(rec + 1) & valid_mask();
    s.tier2 = get_u64(rec + 9) & valid_mask();
    s.tier3 = get_u64(rec + 17) & s.tier2; /* tier 3 only on top of tier 2 */
    return true;
}

/* ---- public API ---- */

void ctf_init(const uint8_t mac[6], const ctf_backend_t *be)
{
    ctf_backend_t nb;
    memset(&nb, 0, sizeof(nb));
    if (be) {
        nb = *be;
    }
    if (nb.lock) {
        nb.lock(nb.ctx);
    }
    s.be = nb;
    if (mac) {
        memcpy(s.mac, mac, sizeof(s.mac));
    } else {
        memset(s.mac, 0, sizeof(s.mac));
    }
    s.solved = 0;
    s.tier2 = 0;
    s.tier3 = 0;
    if (!load_locked()) {
        s.solved = 0;
        s.tier2 = 0;
        s.tier3 = 0;
        save_locked();
    }
    unlock();
}

void ctf_flag(const char *id, char out[18])
{
    lock();
    flag_locked(id, out);
    unlock();
}

void ctf_flag_body(const char *id, char out[13])
{
    lock();
    body_locked(id, out);
    unlock();
}

void ctf_derive(const char *label, uint8_t *out, size_t len)
{
    if (!out) {
        return;
    }
    lock();
    derive_locked(label, out, len);
    unlock();
}

uint32_t ctf_derive_u32(const char *label)
{
    uint8_t d[4];
    ctf_derive(label, d, sizeof(d));
    return ((uint32_t)d[0] << 24) | ((uint32_t)d[1] << 16) | ((uint32_t)d[2] << 8) | d[3];
}

static bool is_space(char c)
{
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' || c == '\f';
}

static char lower(char c)
{
    return (c >= 'A' && c <= 'Z') ? (char)(c - 'A' + 'a') : c;
}

/* Normalise a submission to an uppercase 12-hex body. */
static bool parse_submission(const char *in, char body[CTF_FLAG_BODY_LEN + 1])
{
    if (!in) {
        return false;
    }
    const char *b = in;
    while (*b && is_space(*b)) {
        b++;
    }
    const char *e = b + strlen(b);
    while (e > b && is_space(e[-1])) {
        e--;
    }
    size_t n = (size_t)(e - b);
    if (n == CTF_FLAG_LEN && lower(b[0]) == 'e' && lower(b[1]) == 's' && lower(b[2]) == 'p' &&
        b[3] == '{' && b[CTF_FLAG_LEN - 1] == '}') {
        b += 4;
        n = CTF_FLAG_BODY_LEN;
    }
    if (n != CTF_FLAG_BODY_LEN) {
        return false;
    }
    for (size_t i = 0; i < n; i++) {
        char c = b[i];
        if (c >= 'a' && c <= 'f') {
            c = (char)(c - 'a' + 'A');
        } else if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'F'))) {
            return false;
        }
        body[i] = c;
    }
    body[n] = '\0';
    return true;
}

ctf_submit_t ctf_submit(const char *input, const ctf_challenge_t **matched)
{
    char body[CTF_FLAG_BODY_LEN + 1];
    char want[CTF_FLAG_BODY_LEN + 1];
    ctf_submit_t res = CTF_SUBMIT_WRONG;
    const ctf_challenge_t *m = NULL;

    if (matched) {
        *matched = NULL;
    }
    if (!parse_submission(input, body)) {
        return CTF_SUBMIT_WRONG;
    }
    lock();
    for (size_t i = 0; i < ctf_count(); i++) {
        const ctf_challenge_t *c = ctf_get(i);
        body_locked(c->id, want);
        if (memcmp(body, want, CTF_FLAG_BODY_LEN) == 0) {
            uint64_t bit = (uint64_t)1 << i;
            m = c;
            if (s.solved & bit) {
                res = CTF_SUBMIT_ALREADY;
            } else {
                s.solved |= bit;
                save_locked();
                res = CTF_SUBMIT_NEW;
            }
            break;
        }
    }
    unlock();
    wipe(want, sizeof(want));
    if (matched) {
        *matched = m;
    }
    return res;
}

bool ctf_set_answer(const char *id, ctf_answer_fn fn, void *ctx)
{
    int i = index_of(id);
    if (i < 0) {
        return false;
    }
    lock();
    s.gate[i].fn = fn;
    s.gate[i].ctx = fn ? ctx : NULL;
    unlock();
    return true;
}

bool ctf_answer(const char *id, const char *value, char flag_out[18])
{
    int i = index_of(id);
    if (i < 0) {
        return false;
    }
    lock();
    ctf_answer_fn fn = s.gate[i].fn;
    void *ctx = s.gate[i].ctx;
    unlock();
    /* Validator runs unlocked so it may call ctf_derive*(). */
    if (!fn || !fn(value ? value : "", ctx)) {
        return false;
    }
    if (flag_out) {
        lock();
        flag_locked(ctf_get((size_t)i)->id, flag_out);
        unlock();
    }
    return true;
}

bool ctf_is_solved(const char *id)
{
    int i = index_of(id);
    if (i < 0) {
        return false;
    }
    lock();
    bool r = (s.solved >> i) & 1u;
    unlock();
    return r;
}

int ctf_value(const char *id)
{
    const ctf_challenge_t *c = ctf_find(id);
    return c ? points_of(c->level) : 0;
}

int ctf_max_score(bool include_kit)
{
    int total = 0;
    for (size_t i = 0; i < ctf_count(); i++) {
        const ctf_challenge_t *c = ctf_get(i);
        if (include_kit || !c->kit) {
            total += points_of(c->level);
        }
    }
    return total;
}

/* round(0.2 * v) and round(0.5 * v), half up, integer only. */
static int price_of(ctf_level_t level, int tier)
{
    int v = points_of(level);
    switch (tier) {
    case 2: return (2 * v + 5) / 10;
    case 3: return (v + 1) / 2;
    default: return 0;
    }
}

static int earned_locked(void)
{
    int total = 0;
    for (size_t i = 0; i < ctf_count(); i++) {
        if ((s.solved >> i) & 1u) {
            total += points_of(ctf_get(i)->level);
        }
    }
    return total;
}

static int spent_locked(void)
{
    int total = 0;
    for (size_t i = 0; i < ctf_count(); i++) {
        ctf_level_t lv = ctf_get(i)->level;
        if ((s.tier2 >> i) & 1u) {
            total += price_of(lv, 2);
        }
        if ((s.tier3 >> i) & 1u) {
            total += price_of(lv, 3);
        }
    }
    return total;
}

static int points_locked(void)
{
    return CTF_START_POINTS + earned_locked() - spent_locked();
}

/* Highest owned tier of catalogue index i (caller holds the lock). */
static int tier_locked(int i)
{
    if ((s.tier3 >> i) & 1u) {
        return 3;
    }
    return ((s.tier2 >> i) & 1u) ? 2 : 1;
}

int ctf_points(void)
{
    lock();
    int r = points_locked();
    unlock();
    return r;
}

int ctf_earned(void)
{
    lock();
    int r = earned_locked();
    unlock();
    return r;
}

int ctf_spent(void)
{
    lock();
    int r = spent_locked();
    unlock();
    return r;
}

int ctf_hint_price(const char *id, int tier)
{
    const ctf_challenge_t *c = ctf_find(id);
    if (!c || tier < 1 || tier > CTF_HINT_TIERS) {
        return -1;
    }
    return price_of(c->level, tier);
}

int ctf_hint_tier(const char *id)
{
    int i = index_of(id);
    if (i < 0) {
        return 0;
    }
    lock();
    int r = tier_locked(i);
    unlock();
    return r;
}

ctf_hint_result_t ctf_hint_buy(const char *id, int tier, const char **text_out)
{
    if (text_out) {
        *text_out = NULL;
    }
    int i = index_of(id);
    if (i < 0 || tier < 1 || tier > CTF_HINT_TIERS) {
        return CTF_HINT_BAD;
    }
    const ctf_challenge_t *c = ctf_get((size_t)i);
    uint64_t bit = (uint64_t)1 << i;
    ctf_hint_result_t res = CTF_HINT_OK;
    lock();
    int have = tier_locked(i);
    if (tier > have) {
        if (tier > have + 1) {
            res = CTF_HINT_LOCKED;
        } else if (points_locked() < price_of(c->level, tier)) {
            res = CTF_HINT_POINTS;
        } else {
            if (tier == 2) {
                s.tier2 |= bit;
            } else {
                s.tier3 |= bit;
            }
            save_locked();
        }
    }
    unlock();
    if (res == CTF_HINT_OK && text_out) {
        *text_out = c->hint[tier - 1];
    }
    return res;
}

void ctf_reset(void)
{
    lock();
    s.solved = 0;
    s.tier2 = 0;
    s.tier3 = 0;
    save_locked();
    unlock();
}
