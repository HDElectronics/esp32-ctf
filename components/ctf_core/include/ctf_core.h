#pragma once
/* ctf_core: portable flag / registry / scoring engine (SPEC "Flags",
 * "Scoring and hints", "Optional-kit challenges").
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

typedef enum { CTF_EASY, CTF_MEDIUM, CTF_HARD } ctf_level_t; /* 100/200/300 pts */

typedef struct {
    const char *id;    /* "BLE-01" */
    const char *track; /* "BLE","BTC","WEB","SER","HW","RE","CRY" */
    const char *name;  /* "Read the flag" */
    ctf_level_t level;
    const char *kit;   /* NULL, or short label e.g. "logic analyzer" */
    const char *hint;  /* hint text */
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

/* Copies mac and *be, loads progress; a missing/invalid/tampered record
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

/* Marks the hint used (persisted, once) and returns its text; NULL if unknown id. */
const char *ctf_hint(const char *id);
bool ctf_is_solved(const char *id);
bool ctf_hint_used(const char *id);
int ctf_points(const char *id);         /* base points; 0 if unknown id */
int ctf_score(void);                    /* sum(solved: points - (hint ? points/4 : 0)) */
int ctf_max_score(bool include_kit);    /* sum of base points, optionally skipping kit challenges */
void ctf_reset(void);                   /* clears solved + hint bitmaps, saves */

#ifdef __cplusplus
}
#endif
