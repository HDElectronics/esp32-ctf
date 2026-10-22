/* Pure logic for the v0 module adapters. Portable C11 (no IDF headers):
 * also built by test/host. */
#include "d32_mod_logic.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>

#include "ctf_core.h"

/* ---- Morse ---- */

static const char *const s_morse_hex[16] = {
    "-----", ".----", "..---", "...--", "....-", /* 0-4 */
    ".....", "-....", "--...", "---..", "----.", /* 5-9 */
    ".-", "-...", "-.-.", "-..", ".", "..-.",    /* A-F */
};

const char *d32_morse_symbol(char c)
{
    if (c >= '0' && c <= '9') {
        return s_morse_hex[c - '0'];
    }
    c = (char)toupper((unsigned char)c);
    if (c >= 'A' && c <= 'F') {
        return s_morse_hex[10 + (c - 'A')];
    }
    return NULL;
}

static bool push(d32_morse_step_t *steps, int max, int *n, bool on, unsigned units)
{
    if (*n >= max) {
        return false;
    }
    steps[*n].on = on;
    steps[*n].units = (uint8_t)(units > 255 ? 255 : units);
    (*n)++;
    return true;
}

int d32_morse_timeline(const char *text, unsigned tail_units, d32_morse_step_t *steps, int max)
{
    if (!text || !*text || !steps || max <= 0) {
        return -1;
    }
    int n = 0;
    for (size_t i = 0; text[i]; i++) {
        const char *sym = d32_morse_symbol(text[i]);
        if (!sym) {
            return -1;
        }
        if (i > 0 && !push(steps, max, &n, false, 3)) {
            return -1;
        }
        for (size_t k = 0; sym[k]; k++) {
            if (k > 0 && !push(steps, max, &n, false, 1)) {
                return -1;
            }
            if (!push(steps, max, &n, true, sym[k] == '-' ? 3 : 1)) {
                return -1;
            }
        }
    }
    if (!push(steps, max, &n, false, tail_units ? tail_units : 1)) {
        return -1;
    }
    return n;
}

/* ---- seed-derived values ---- */

static void derive(uint32_t seed, const char *what, uint8_t *out, size_t len)
{
    char label[32];
    snprintf(label, sizeof(label), "D32:%08X:%s", (unsigned)seed, what);
    ctf_derive(label, out, len);
}

static void shuffle(uint8_t *v, int n, const uint8_t *rnd)
{
    for (int i = 0; i < n; i++) {
        v[i] = (uint8_t)i;
    }
    for (int i = n - 1; i > 0; i--) {
        int j = rnd[i] % (i + 1);
        uint8_t t = v[i];
        v[i] = v[j];
        v[j] = t;
    }
}

void d32_patch_pattern(uint32_t seed, uint8_t b_for_a[D32_ML_POSTS])
{
    uint8_t rnd[D32_ML_POSTS];
    derive(seed, "patch", rnd, sizeof(rnd));
    shuffle(b_for_a, D32_ML_POSTS, rnd);
}

bool d32_patch_matches(const uint8_t conn[D32_ML_POSTS], const uint8_t b_for_a[D32_ML_POSTS])
{
    for (int a = 0; a < D32_ML_POSTS; a++) {
        if (b_for_a[a] >= D32_ML_POSTS || conn[a] != (uint8_t)(1u << b_for_a[a])) {
            return false;
        }
    }
    return true;
}

int d32_patch_hint(const uint8_t b_for_a[D32_ML_POSTS], char *out, size_t cap)
{
    if (!out || cap == 0) {
        return -1;
    }
    size_t n = 0;
    for (int a = 0; a < D32_ML_POSTS; a++) {
        int w = snprintf(out + n, cap - n, "%sA%d-B%d", a ? " " : "", a + 1, b_for_a[a] + 1);
        if (w < 0 || (size_t)w >= cap - n) {
            out[0] = '\0';
            return -1;
        }
        n += (size_t)w;
    }
    return (int)n;
}

void d32_touch_sequence(uint32_t seed, uint8_t seq[D32_ML_PADS])
{
    uint8_t rnd[D32_ML_PADS];
    derive(seed, "touch", rnd, sizeof(rnd));
    shuffle(seq, D32_ML_PADS, rnd);
}

void d32_seqm_init(d32_seqm_t *m, const uint8_t seq[D32_ML_PADS])
{
    memcpy(m->seq, seq, sizeof(m->seq));
    m->pos = 0;
}

d32_seq_result_t d32_seqm_feed(d32_seqm_t *m, uint8_t pad)
{
    if (m->pos < D32_ML_PADS && pad == m->seq[m->pos]) {
        if (++m->pos == D32_ML_PADS) {
            m->pos = 0;
            return D32_SEQ_DONE;
        }
        return D32_SEQ_PROGRESS;
    }
    m->pos = (pad == m->seq[0]) ? 1 : 0;
    return D32_SEQ_WRONG;
}

static bool pin_collides(const char *pin, const char *const *codes, int ncodes)
{
    for (int i = 0; codes && i < ncodes; i++) {
        if (codes[i] && codes[i][0] && strcmp(codes[i], pin) == 0) {
            return true;
        }
    }
    return false;
}

int d32_service_pin(uint32_t seed, const char *const *codes, int ncodes,
                    char out[D32_ML_PIN_LEN + 1])
{
    for (unsigned n = 0; n < 256; n++) {
        char what[16];
        uint8_t b[3];
        if (n == 0) {
            snprintf(what, sizeof(what), "menu");
        } else {
            snprintf(what, sizeof(what), "menu:%u", n);
        }
        derive(seed, what, b, sizeof(b));
        snprintf(out, D32_ML_PIN_LEN + 1, "%02X%02X%02X", b[0], b[1], b[2]);
        if (!pin_collides(out, codes, ncodes)) {
            return (int)n;
        }
    }
    return -1;
}

int d32_base64(const uint8_t *in, size_t len, char *out, size_t cap)
{
    static const char tbl[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    size_t need = 4 * ((len + 2) / 3);
    if (!out || cap <= need) {
        if (out && cap) {
            out[0] = '\0';
        }
        return -1;
    }
    size_t o = 0;
    for (size_t i = 0; i < len; i += 3) {
        uint32_t v = (uint32_t)in[i] << 16;
        if (i + 1 < len) v |= (uint32_t)in[i + 1] << 8;
        if (i + 2 < len) v |= in[i + 2];
        out[o++] = tbl[(v >> 18) & 63];
        out[o++] = tbl[(v >> 12) & 63];
        out[o++] = i + 1 < len ? tbl[(v >> 6) & 63] : '=';
        out[o++] = i + 2 < len ? tbl[v & 63] : '=';
    }
    out[o] = '\0';
    return (int)o;
}

/* ---- keypad ---- */

uint16_t d32_debounce_feed(d32_debounce_t *db, uint16_t raw, uint8_t need,
                           uint16_t *pressed, uint16_t *released)
{
    uint16_t on = 0, off = 0;
    if (raw != db->last) {
        db->last = raw;
        db->count = 1;
    } else if (db->count < 255) {
        db->count++;
    }
    if (db->count >= (need ? need : 1) && raw != db->stable) {
        on = (uint16_t)(raw & ~db->stable);
        off = (uint16_t)(db->stable & ~raw);
        db->stable = raw;
    }
    if (pressed) {
        *pressed = on;
    }
    if (released) {
        *released = off;
    }
    return db->stable;
}

d32_key_action_t d32_keyhold_press(d32_keyhold_t *k, char c, uint32_t now_ms, char *digit)
{
    c = (char)toupper((unsigned char)c);
    if (!isxdigit((unsigned char)c)) {
        return D32_KEY_NONE;
    }
    d32_key_action_t a = D32_KEY_NONE;
    if (k->held && !k->fired) {
        /* Rolled typing: the key still down counts as typed now. */
        if (digit) {
            *digit = k->held;
        }
        a = D32_KEY_DIGIT;
    }
    k->held = c;
    k->fired = false;
    k->since = now_ms;
    return a;
}

d32_key_action_t d32_keyhold_release(d32_keyhold_t *k, char c, uint32_t now_ms, char *digit)
{
    c = (char)toupper((unsigned char)c);
    if (!k->held || c != k->held) {
        return D32_KEY_NONE; /* not tracked (already typed by a rolled press) */
    }
    bool fired = k->fired;
    bool long_hold = (uint32_t)(now_ms - k->since) >= D32_ML_CLEAR_MS;
    k->held = 0;
    k->fired = false;
    if (fired) {
        return D32_KEY_NONE;
    }
    if (long_hold) {
        return D32_KEY_CLEAR; /* no tick saw it: still a clear, never a digit */
    }
    if (digit) {
        *digit = c;
    }
    return D32_KEY_DIGIT;
}

d32_key_action_t d32_keyhold_tick(d32_keyhold_t *k, uint32_t now_ms)
{
    if (!k->held || k->fired || (uint32_t)(now_ms - k->since) < D32_ML_CLEAR_MS) {
        return D32_KEY_NONE;
    }
    k->fired = true;
    return D32_KEY_CLEAR;
}

void d32_entry_clear(d32_entry_t *e)
{
    memset(e, 0, sizeof(*e));
}

bool d32_entry_add(d32_entry_t *e, char c, uint32_t now_ms)
{
    c = (char)toupper((unsigned char)c);
    if (e->len >= D32_ML_ENTRY_LEN || !isxdigit((unsigned char)c)) {
        return false;
    }
    e->buf[e->len++] = c;
    e->buf[e->len] = '\0';
    e->last_key_ms = now_ms;
    return true;
}

d32_entry_result_t d32_entry_check(const d32_entry_t *e, const char *pin)
{
    if (e->len < D32_ML_ENTRY_LEN) {
        return D32_ENTRY_PARTIAL;
    }
    if (pin && strcmp(e->buf, pin) == 0) {
        return D32_ENTRY_SERVICE;
    }
    return D32_ENTRY_SUBMIT;
}

bool d32_entry_idle(const d32_entry_t *e, uint32_t now_ms)
{
    return e->len > 0 && (uint32_t)(now_ms - e->last_key_ms) >= D32_ML_IDLE_MS;
}
