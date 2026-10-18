#pragma once
/* ctf_core: portable flag / registry / points-wallet engine (SPEC "Flags",
 * "Optional-kit challenges", "v0.2.0: points wallet, hint tiers").
 * Must not include IDF/FreeRTOS headers; built on device and in test/host.
 *
 * Thread safety: every function that touches engine state takes the backend's
 * lock hook (if provided) for its duration. The lock need not be recursive:
 * no public function calls another public function while holding it, and
 * answer validators run with the lock released (so they may call ctf_derive*). */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CTF_FLAG_LEN      17   /* "ESP{" + 12 hex + "}" */
#define CTF_FLAG_BODY_LEN 12
#define CTF_MAX_CHALLENGES 64  /* progress bitmaps are 64-bit */
#define CTF_START_POINTS  100  /* every board starts with this many points */
#define CTF_HINT_TIERS    3    /* 1 nudge (free), 2 hint, 3 walkthrough */

typedef enum { CTF_EASY, CTF_MEDIUM, CTF_HARD } ctf_level_t; /* 100/200/300 pts */

typedef struct {
    const char *id;    /* "BLE-01" */
    const char *track; /* "BLE","BTC","WEB","SER","HW","RE","CRY" */
    const char *name;  /* "Read the flag" */
    ctf_level_t level;
    const char *kit;   /* NULL, or short label e.g. "logic analyzer" */
    const char *hint[CTF_HINT_TIERS]; /* hint[t - 1] = text of tier t (1..3) */
} ctf_challenge_t;

/* Storage + optional lock hooks. load/save are required; lock/unlock may be NULL.
 * load must fill exactly `len` bytes and return true only if a stored record of
 * exactly `len` bytes exists; return false if missing or of a different size.
 * A NULL backend (or NULL load/save) runs memory-only. */
typedef struct {
    bool (*load)(void *buf, size_t len, void *ctx);
    bool (*save)(const void *buf, size_t len, void *ctx);
    void (*lock)(void *ctx);
    void (*unlock)(void *ctx);
    void *ctx;
} ctf_backend_t;

/* Copies mac and *be, loads progress; a missing/invalid/tampered/v1 record
 * starts fresh and is saved. Answer validators are kept across calls. */
void ctf_init(const uint8_t mac[6], const ctf_backend_t *be);

/* Catalogue (static, SPEC order). Index = progress bit index. */
size_t ctf_count(void);
const ctf_challenge_t *ctf_get(size_t i);        /* NULL if out of range */
const ctf_challenge_t *ctf_find(const char *id); /* exact, case-sensitive; NULL if unknown */

/* Flags: body = upper hex of first 6 bytes of HMAC-SHA256(K, mac6 || id). */
void ctf_flag(const char *id, char out[18]);      /* "ESP{XXXXXXXXXXXX}" + NUL */
void ctf_flag_body(const char *id, char out[13]); /* 12 uppercase hex + NUL */

/* Derived per-board values. Block 0 = HMAC-SHA256(K, mac6 || label);
 * for len > 32, block i >= 1 = HMAC-SHA256(K, mac6 || label || be32(i)),
 * concatenated and truncated to len. */
void ctf_derive(const char *label, uint8_t *out, size_t len);
uint32_t ctf_derive_u32(const char *label); /* first 4 derived bytes, big-endian */

typedef enum { CTF_SUBMIT_NEW, CTF_SUBMIT_ALREADY, CTF_SUBMIT_WRONG } ctf_submit_t;

/* Accepts "ESP{body}" (prefix any case) or bare body, body = 12 hex chars any
 * case, surrounding ASCII whitespace ignored. NEW marks solved and saves.
 * *matched (if matched != NULL) is the challenge, or NULL on WRONG. */
ctf_submit_t ctf_submit(const char *input, const ctf_challenge_t **matched);

/* Answer gates: tracks register a validator per challenge; fn NULL clears.
 * Returns false if id is unknown. */
typedef bool (*ctf_answer_fn)(const char *value, void *ctx);
bool ctf_set_answer(const char *id, ctf_answer_fn fn, void *ctx);
/* True (and flag in flag_out, if non-NULL) when a validator is registered for
 * id and accepts value. Does not mark the challenge solved: the player submits
 * the returned flag. */
bool ctf_answer(const char *id, const char *value, char flag_out[18]);
/* True when a validator is registered for id (false for an unknown id). */
bool ctf_has_answer(const char *id);

bool ctf_is_solved(const char *id);
int ctf_value(const char *id);          /* challenge value 100/200/300; 0 if unknown id */
int ctf_max_score(bool include_kit);    /* max earnable: sum of values, optionally skipping kit challenges */

/* Points wallet: points = CTF_START_POINTS + earned - spent (never negative). */
int ctf_points(void);
int ctf_earned(void);                   /* sum of solved challenges' values */
int ctf_spent(void);                    /* sum of the prices of bought hint tiers */

/* Hint tiers. Price: tier 1 = 0, tier 2 = round(0.2 * value), tier 3 =
 * round(0.5 * value) (100 -> 0/20/50, 200 -> 0/40/100, 300 -> 0/60/150).
 * Returns -1 for an unknown id or a tier outside 1..3. */
int ctf_hint_price(const char *id, int tier);
/* Highest owned tier: 1 (free) if none bought, 2 or 3; 0 if unknown id.
 * Tiers are owned in order, so tier t is owned iff t <= ctf_hint_tier(id). */
int ctf_hint_tier(const char *id);

typedef enum {
    CTF_HINT_OK,     /* tier is free, already owned, or just bought (and saved) */
    CTF_HINT_LOCKED, /* previous tier not owned yet */
    CTF_HINT_POINTS, /* not enough points for the price */
    CTF_HINT_BAD,    /* unknown id or tier outside 1..3 */
} ctf_hint_result_t;

/* Shows tier `tier` of id's hints, buying it if needed: tier 1 is always OK
 * and records nothing; an owned tier is OK without charge; otherwise the
 * previous tier must be owned (else LOCKED) and points >= price (else POINTS),
 * then the tier is recorded and the record saved. Buying after solving is
 * allowed. *text_out (if non-NULL) is the tier's text on OK, else NULL.
 * Check, charge and save happen under one lock (no double spend). */
ctf_hint_result_t ctf_hint_buy(const char *id, int tier, const char **text_out);

void ctf_reset(void);                   /* clears solved + hint-tier bitmaps, saves */

#ifdef __cplusplus
}
#endif
