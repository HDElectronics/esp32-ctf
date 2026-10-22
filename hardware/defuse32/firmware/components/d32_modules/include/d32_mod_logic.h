#pragma once
/* d32_mod_logic: the pure logic behind the v0 module adapters (Morse timing,
 * seed-derived patterns and sequences, keypad entry). Portable C11: no
 * IDF/FreeRTOS headers, built by test/host.
 *
 * Seed-derived values use ctf_derive() on labels that cannot collide with the
 * engine's own labels ("D32:<SEED>:<Mn>:<variant>", ":wire", ":frag"), so
 * ctf_init() must have been called first:
 *   patch pattern   "D32:<SEED>:patch"
 *   touch sequence  "D32:<SEED>:touch"
 *   service PIN     "D32:<SEED>:menu", then "D32:<SEED>:menu:<n>" (n = 1, 2,
 *                   ...) while it collides with a module code of the round
 * <SEED> is the round seed as 8 uppercase hex digits. Shuffles are
 * Fisher-Yates driven by the derived bytes (byte % (i + 1); the small modulo
 * bias does not matter for a training game). */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define D32_ML_POSTS      6     /* wire posts per side (WA1-6, WB1-6) */
#define D32_ML_PADS       4     /* touch pads T0, T4, T6, T3 */
#define D32_ML_ENTRY_LEN  6     /* code length on the keypad */
#define D32_ML_PIN_LEN    6     /* keypad service PIN length (typed like a code) */
#define D32_ML_CLEAR_MS   800u  /* hold any key this long to clear the entry */
#define D32_ML_IDLE_MS    10000u /* the entry clears itself after this long without a key */

/* ---- Morse ---- */

/* International Morse for a hex digit ('0'-'9', 'A'-'F', any case), as a
 * string of '.' and '-'; NULL for any other char. */
const char *d32_morse_symbol(char c);

typedef struct {
    bool on;        /* tone on (element) or off (gap) */
    uint8_t units;  /* duration in Morse units */
} d32_morse_step_t;

/* Timeline for `text` (hex digits only): dot = 1 unit on, dash = 3 on, 1 off
 * between elements, 3 off between characters, and `tail_units` off after the
 * last character (the gap before the text repeats; at least 1 is used).
 * Returns the number of steps written, or -1 for an empty text, a non-hex
 * char or when `max` is too small. 6 hex chars need at most 60 steps. */
int d32_morse_timeline(const char *text, unsigned tail_units, d32_morse_step_t *steps, int max);

/* ---- M4 wires: patch pattern ---- */

/* b_for_a[a] = B post (0-5) that A post a (0-5) must be patched to: a
 * permutation of 0..5 derived from the seed. */
void d32_patch_pattern(uint32_t seed, uint8_t b_for_a[D32_ML_POSTS]);
/* conn[a] = bitmask of B posts connected to A post a (board_wires_scan()).
 * True when every A post is connected to exactly its pattern B post. */
bool d32_patch_matches(const uint8_t conn[D32_ML_POSTS], const uint8_t b_for_a[D32_ML_POSTS]);
/* "A1-B4 A2-B1 A3-B6 A4-B2 A5-B5 A6-B3" (1-based post names). Returns the
 * length, or -1 if cap is too small (out is then ""). Needs cap >= 36. */
int d32_patch_hint(const uint8_t b_for_a[D32_ML_POSTS], char *out, size_t cap);

/* ---- M6 sensors: touch sequence ---- */

/* seq = permutation of the pads 0..3 (0 = T0, 1 = T4, 2 = T6, 3 = T3). */
void d32_touch_sequence(uint32_t seed, uint8_t seq[D32_ML_PADS]);

typedef enum {
    D32_SEQ_PROGRESS, /* correct next pad */
    D32_SEQ_DONE,     /* sequence complete (matcher restarts) */
    D32_SEQ_WRONG,    /* wrong pad: progress restarts (counts as step 1 if it is seq[0]) */
} d32_seq_result_t;

typedef struct {
    uint8_t seq[D32_ML_PADS];
    uint8_t pos;      /* pads matched so far */
} d32_seqm_t;

void d32_seqm_init(d32_seqm_t *m, const uint8_t seq[D32_ML_PADS]);
d32_seq_result_t d32_seqm_feed(d32_seqm_t *m, uint8_t pad);

/* ---- M3 keypad ---- */

/* Service PIN: 6 uppercase hex chars, the first 3 bytes of
 * ctf_derive("D32:<SEED>:menu") (counter 0) or "D32:<SEED>:menu:<n>"
 * (counter n >= 1), taking the first counter whose PIN differs from every
 * entry of codes[0..ncodes-1] (the round's module codes; NULL entries and
 * "" are skipped). Returns the counter used, or -1 if 256 counters all
 * collided (out is then the last one tried; cannot happen with <= 6 codes in
 * practice). */
int d32_service_pin(uint32_t seed, const char *const *codes, int ncodes,
                    char out[D32_ML_PIN_LEN + 1]);

/* Base64 (RFC 4648, '=' padding) of len bytes. Returns the length written,
 * or -1 if cap is too small (out is then ""). 6 bytes -> 8 chars. */
int d32_base64(const uint8_t *in, size_t len, char *out, size_t cap);

/* Debouncer for the raw 16-key scan mask: a new mask is accepted after it
 * was read `need` times in a row. */
typedef struct {
    uint16_t last;    /* last raw sample */
    uint16_t stable;  /* accepted mask */
    uint8_t count;
} d32_debounce_t;

/* Feeds one raw sample; returns the accepted mask. *pressed / *released (may
 * be NULL) get the bits that changed on acceptance. */
uint16_t d32_debounce_feed(d32_debounce_t *db, uint16_t raw, uint8_t need,
                           uint16_t *pressed, uint16_t *released);

/* Keys on the 0-F overlay: all 16 keys are hex digits. A digit is typed when
 * its key is released before D32_ML_CLEAR_MS, or when another key is pressed
 * while it is still down (rolled typing). Holding a key for D32_ML_CLEAR_MS
 * clears the entry instead, and that key types nothing. */
typedef enum {
    D32_KEY_NONE,
    D32_KEY_DIGIT,  /* *digit = the typed digit (uppercase) */
    D32_KEY_CLEAR,  /* clear the entry */
} d32_key_action_t;

typedef struct {
    char held;        /* key being tracked, 0 if none */
    bool fired;       /* the hold already cleared the entry */
    uint32_t since;
} d32_keyhold_t;

/* Press / release edges (key chars, any case) and a periodic tick. */
d32_key_action_t d32_keyhold_press(d32_keyhold_t *k, char c, uint32_t now_ms, char *digit);
d32_key_action_t d32_keyhold_release(d32_keyhold_t *k, char c, uint32_t now_ms, char *digit);
d32_key_action_t d32_keyhold_tick(d32_keyhold_t *k, uint32_t now_ms);

/* Code entry buffer; it submits itself when the 6th digit is typed. */
typedef struct {
    char buf[D32_ML_ENTRY_LEN + 1];
    uint8_t len;
    uint32_t last_key_ms;  /* time of the last typed digit */
} d32_entry_t;

typedef enum {
    D32_ENTRY_PARTIAL, /* fewer than 6 digits */
    D32_ENTRY_SERVICE, /* 6 digits equal to the service PIN: open the menu, never a strike */
    D32_ENTRY_SUBMIT,  /* 6 digits: submit buf as a code */
} d32_entry_result_t;

void d32_entry_clear(d32_entry_t *e);
/* Appends an uppercase hex digit (false when full or not hex) and records the
 * time. */
bool d32_entry_add(d32_entry_t *e, char c, uint32_t now_ms);
/* What the buffer is now: PARTIAL, or (when full) SERVICE if it equals pin
 * (pin may be NULL: no service menu), else SUBMIT. Leaves the buffer as is. */
d32_entry_result_t d32_entry_check(const d32_entry_t *e, const char *pin);
/* True when a partial entry has had no key for D32_ML_IDLE_MS. */
bool d32_entry_idle(const d32_entry_t *e, uint32_t now_ms);

#ifdef __cplusplus
}
#endif
