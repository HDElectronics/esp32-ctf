/* d32_engine: Defuse32 game engine. Portable C11, no IDF/FreeRTOS headers, no heap.
 * Rules: hardware/defuse32/FIRMWARE.md "Game rules the engine implements". */
#include "d32_engine.h"

#include <stdio.h>
#include <string.h>

#include "ctf_core.h"

#define PPM_ONE      1000000u
#define RATE_PPM_CAP 1000000000u /* 1000x: keeps dt * rate inside 64 bits */

static const char *const SLOT_ID[D32_SLOTS] = {"M1", "M2", "M3", "M4", "M5", "M6"};
static const char *const SLOT_NAME[D32_SLOTS] = {"radio", "timer", "keypad",
                                                 "wires", "probe", "sensors"};
static const char *const WIRE_COLOUR[D32_WIRES] = {"RED",   "BLUE",  "YELLOW",
                                                   "GREEN", "WHITE", "BLACK"};
static const char *const PHASE_NAME[] = {"idle", "armed", "final", "won", "lost"};

/* ---- helpers ---- */

static bool running(const d32_t *d)
{
    return d->phase == D32_ARMED || d->phase == D32_FINAL;
}

static bool slot_ok(int slot)
{
    return slot >= 0 && slot < D32_SLOTS;
}

static uint32_t ceil_seconds(uint32_t ms)
{
    return ms / 1000u + (ms % 1000u ? 1u : 0u);
}

static void push(d32_t *d, const d32_event_t *ev)
{
    if (d->ev_count == D32_EVQ_LEN) {
        d->ev_head = (uint8_t)((d->ev_head + 1u) % D32_EVQ_LEN);
        d->ev_count--;
        d->ev_dropped++;
    }
    d->evq[(d->ev_head + d->ev_count) % D32_EVQ_LEN] = *ev;
    d->ev_count++;
}

static d32_event_t new_event(const d32_t *d, d32_event_type_t type)
{
    d32_event_t ev;
    memset(&ev, 0, sizeof(ev));
    ev.type = type;
    ev.phase = d->phase;
    ev.strikes = d->strikes;
    ev.rate_permille = d32_rate_permille(d);
    ev.time_left_ms = d->time_left_ms;
    ev.seconds = ceil_seconds(d->time_left_ms);
    return ev;
}

static void set_phase(d32_t *d, d32_phase_t p)
{
    d->phase = p;
    d32_event_t ev = new_event(d, D32_EV_PHASE);
    push(d, &ev);
}

static void end_round(d32_t *d, d32_end_t why)
{
    d->end = why;
    set_phase(d, why == D32_END_WON ? D32_WON : D32_LOST);
    d32_event_t ev = new_event(d, D32_EV_RESULT);
    ev.reason = (uint8_t)why;
    push(d, &ev);
}

static void clear_round(d32_t *d)
{
    d->phase = D32_IDLE;
    d->end = D32_END_NONE;
    d->seed = 0;
    d->time_left_ms = (uint32_t)d->cfg.minutes * 60000u;
    d->frac_ppm = 0;
    d->rate_ppm = PPM_ONE;
    d->last_seconds = ceil_seconds(d->time_left_ms);
    d->strikes = 0;
    d->tilt_seen = false;
    d->last_tilt_ms = 0;
    d->target_wire = 0;
    d->colour_len = 0;
    for (int i = 0; i < D32_SLOTS; i++) {
        d->slot_state[i] = d->cfg.slot[i].enabled ? D32_SLOT_IDLE : D32_SLOT_DISABLED;
    }
    memset(d->codes, 0, sizeof(d->codes));
    memset(d->nfrags, 0, sizeof(d->nfrags));
    memset(d->frags, 0, sizeof(d->frags));
    d->ev_head = 0;
    d->ev_count = 0;
    d->ev_dropped = 0;
}

/* ---- config ---- */

void d32_config_default(d32_config_t *cfg)
{
    memset(cfg, 0, sizeof(*cfg));
    cfg->minutes = D32_DEF_MINUTES;
    cfg->max_strikes = D32_DEF_MAX_STRIKES;
    cfg->strike_rate_permille = D32_DEF_RATE;
    cfg->training = false;
    for (int i = 0; i < D32_SLOTS; i++) {
        cfg->slot[i].enabled = true;
    }
}

unsigned d32_config_sanitize(d32_config_t *cfg)
{
    unsigned fixed = 0;
    if (cfg->minutes < 1 || cfg->minutes > D32_MAX_MINUTES) {
        cfg->minutes = D32_DEF_MINUTES;
        fixed++;
    }
    if (cfg->max_strikes < 1 || cfg->max_strikes > D32_MAX_MAX_STRIKES) {
        cfg->max_strikes = D32_DEF_MAX_STRIKES;
        fixed++;
    }
    if (cfg->strike_rate_permille < D32_MIN_RATE || cfg->strike_rate_permille > D32_MAX_RATE) {
        cfg->strike_rate_permille = D32_DEF_RATE;
        fixed++;
    }
    for (int i = 0; i < D32_SLOTS; i++) {
        if (memchr(cfg->slot[i].variant, '\0', D32_VARIANT_MAX) == NULL) {
            cfg->slot[i].variant[D32_VARIANT_MAX - 1] = '\0';
            fixed++;
        }
    }
    return fixed;
}

void d32_init(d32_t *d, const d32_config_t *cfg)
{
    memset(d, 0, sizeof(*d));
    if (cfg) {
        d->cfg = *cfg;
        d32_config_sanitize(&d->cfg);
    } else {
        d32_config_default(&d->cfg);
    }
    clear_round(d);
}

bool d32_set_config(d32_t *d, const d32_config_t *cfg)
{
    if (d->phase != D32_IDLE || cfg == NULL) {
        return false;
    }
    d->cfg = *cfg;
    d32_config_sanitize(&d->cfg);
    /* Keep the (IDLE) event queue; refresh slot states and the shown time. */
    d->time_left_ms = (uint32_t)d->cfg.minutes * 60000u;
    d->last_seconds = ceil_seconds(d->time_left_ms);
    for (int i = 0; i < D32_SLOTS; i++) {
        d->slot_state[i] = d->cfg.slot[i].enabled ? D32_SLOT_IDLE : D32_SLOT_DISABLED;
    }
    return true;
}

const d32_config_t *d32_config(const d32_t *d)
{
    return &d->cfg;
}

/* ---- derivation ---- */

static void derive_code(uint32_t seed, int slot, const char *variant, char out[D32_CODE_LEN + 1])
{
    char label[64];
    uint8_t b[3];
    snprintf(label, sizeof(label), "D32:%08X:%s:%s", (unsigned)seed, SLOT_ID[slot], variant);
    ctf_derive(label, b, sizeof(b));
    snprintf(out, D32_CODE_LEN + 1, "%02X%02X%02X", b[0], b[1], b[2]);
}

/* Spread the colour's letters over the enabled slots: shuffle the letter
 * positions and the enabled slots with bytes of ctf_derive("D32:<seed>:frag"),
 * then deal letter k to slot k mod n. Every letter lands on exactly one slot;
 * each slot carries floor(len/n) or ceil(len/n) letters (0, 1 or 2 when n >= 3). */
static void deal_fragments(d32_t *d, const char *colour)
{
    char label[32];
    uint8_t rnd[16];
    int k = 0;
    snprintf(label, sizeof(label), "D32:%08X:frag", (unsigned)d->seed);
    ctf_derive(label, rnd, sizeof(rnd));

    int len = (int)strlen(colour);
    uint8_t pos[D32_COLOUR_MAX];
    for (int i = 0; i < len; i++) {
        pos[i] = (uint8_t)i;
    }
    for (int i = len - 1; i > 0; i--) {
        int j = rnd[k++] % (i + 1);
        uint8_t t = pos[i];
        pos[i] = pos[j];
        pos[j] = t;
    }

    int slots[D32_SLOTS];
    int n = 0;
    for (int i = 0; i < D32_SLOTS; i++) {
        if (d->cfg.slot[i].enabled) {
            slots[n++] = i;
        }
    }
    for (int i = n - 1; i > 0; i--) {
        int j = rnd[k++] % (i + 1);
        int t = slots[i];
        slots[i] = slots[j];
        slots[j] = t;
    }

    for (int i = 0; i < len; i++) {
        int s = slots[i % n];
        d32_frag_t f = {(uint8_t)(pos[i] + 1), colour[pos[i]]};
        /* insert sorted by position */
        int m = d->nfrags[s];
        while (m > 0 && d->frags[s][m - 1].pos > f.pos) {
            d->frags[s][m] = d->frags[s][m - 1];
            m--;
        }
        d->frags[s][m] = f;
        d->nfrags[s]++;
    }
}

/* ---- round control ---- */

void d32_reset(d32_t *d)
{
    bool changed = d->phase != D32_IDLE;
    clear_round(d);
    if (changed) {
        d32_event_t ev = new_event(d, D32_EV_PHASE);
        push(d, &ev);
    }
}

d32_arm_result_t d32_arm(d32_t *d, uint32_t seed)
{
    if (d->phase != D32_IDLE) {
        return D32_ARM_BUSY;
    }
    if (d32_enabled_count(d) == 0) {
        return D32_ARM_NO_MODULES;
    }
    /* IDLE state is already clean (init, reset and set_config leave it so);
     * queued IDLE events such as PHASE(IDLE) from a reset are kept. */
    d->seed = seed;
    for (int i = 0; i < D32_SLOTS; i++) {
        if (d->cfg.slot[i].enabled) {
            derive_code(seed, i, d->cfg.slot[i].variant, d->codes[i]);
            d->slot_state[i] = D32_SLOT_ARMED;
        }
    }
    char label[32];
    snprintf(label, sizeof(label), "D32:%08X:wire", (unsigned)seed);
    d->target_wire = (uint8_t)(ctf_derive_u32(label) % D32_WIRES);
    const char *colour = WIRE_COLOUR[d->target_wire];
    d->colour_len = (uint8_t)strlen(colour);
    deal_fragments(d, colour);

    set_phase(d, D32_ARMED);
    return D32_ARM_OK;
}

void d32_tick(d32_t *d, uint32_t dt_ms)
{
    if (!running(d) || d->cfg.training || dt_ms == 0) {
        return;
    }
    uint64_t acc = (uint64_t)dt_ms * d->rate_ppm + d->frac_ppm;
    uint64_t elapsed = acc / PPM_ONE;
    d->frac_ppm = (uint32_t)(acc % PPM_ONE);
    d->time_left_ms = elapsed >= d->time_left_ms ? 0u : d->time_left_ms - (uint32_t)elapsed;

    uint32_t secs = ceil_seconds(d->time_left_ms);
    if (secs != d->last_seconds) {
        d->last_seconds = secs;
        d32_event_t ev = new_event(d, D32_EV_TICK);
        push(d, &ev);
    }
    if (d->time_left_ms == 0) {
        end_round(d, D32_END_TIME);
    }
}

bool d32_strike(d32_t *d, d32_strike_reason_t reason)
{
    if (!running(d) || d->cfg.training) {
        return false;
    }
    d->strikes++;
    uint64_t r = ((uint64_t)d->rate_ppm * d->cfg.strike_rate_permille + 500u) / 1000u;
    d->rate_ppm = r > RATE_PPM_CAP ? RATE_PPM_CAP : (uint32_t)r;
    d32_event_t ev = new_event(d, D32_EV_STRIKE);
    ev.reason = (uint8_t)reason;
    push(d, &ev);
    if (d->strikes >= d->cfg.max_strikes) {
        end_round(d, D32_END_STRIKES);
    }
    return true;
}

static void disarm(d32_t *d, int slot)
{
    d->slot_state[slot] = D32_SLOT_DISARMED;
    d32_event_t ev = new_event(d, D32_EV_DISARMED);
    ev.slot = (uint8_t)slot;
    ev.nfrags = d->nfrags[slot];
    memcpy(ev.frags, d->frags[slot], sizeof(ev.frags));
    push(d, &ev);
    if (d->phase == D32_ARMED && d32_disarmed_count(d) == d32_enabled_count(d)) {
        set_phase(d, D32_FINAL);
    }
}

d32_code_result_t d32_submit_code(d32_t *d, const char *text, int *slot_out)
{
    if (!running(d)) {
        return D32_CODE_NOT_ARMED;
    }
    char code[D32_CODE_LEN + 1];
    int n = 0;
    for (const char *p = text ? text : ""; *p; p++) {
        char c = *p;
        if (c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' || c == '\f') {
            continue;
        }
        if (c >= 'a' && c <= 'f') {
            c = (char)(c - 'a' + 'A');
        }
        if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'F')) || n == D32_CODE_LEN) {
            return D32_CODE_INVALID;
        }
        code[n++] = c;
    }
    if (n != D32_CODE_LEN) {
        return D32_CODE_INVALID;
    }
    code[n] = '\0';

    for (int i = 0; i < D32_SLOTS; i++) {
        if (d->slot_state[i] == D32_SLOT_ARMED && strcmp(d->codes[i], code) == 0) {
            if (slot_out) {
                *slot_out = i;
            }
            disarm(d, i);
            return D32_CODE_DISARMED;
        }
    }
    for (int i = 0; i < D32_SLOTS; i++) {
        if (d->slot_state[i] == D32_SLOT_DISARMED && strcmp(d->codes[i], code) == 0) {
            if (slot_out) {
                *slot_out = i;
            }
            return D32_CODE_ALREADY;
        }
    }
    d32_event_t ev = new_event(d, D32_EV_REJECTED);
    push(d, &ev);
    d32_strike(d, D32_STRIKE_CODE);
    return D32_CODE_REJECTED;
}

d32_wire_result_t d32_wire_pulled(d32_t *d, int index)
{
    if (!running(d)) {
        return D32_WIRE_NOT_ARMED;
    }
    if (index < 0 || index >= D32_WIRES) {
        return D32_WIRE_INVALID;
    }
    if (d->phase == D32_ARMED) {
        d32_strike(d, D32_STRIKE_WIRE);
        return D32_WIRE_EARLY;
    }
    if (index == d->target_wire) {
        end_round(d, D32_END_WON);
        return D32_WIRE_WON;
    }
    end_round(d, D32_END_WIRE);
    return D32_WIRE_LOST;
}

bool d32_tilt(d32_t *d, uint32_t now_ms)
{
    if (!running(d) || d->cfg.training) {
        return false;
    }
    if (d->tilt_seen && (uint32_t)(now_ms - d->last_tilt_ms) < D32_TILT_GAP_MS) {
        return false;
    }
    d->tilt_seen = true;
    d->last_tilt_ms = now_ms;
    return d32_strike(d, D32_STRIKE_TILT);
}

/* ---- state ---- */

d32_phase_t d32_phase(const d32_t *d)
{
    return d->phase;
}

d32_end_t d32_end_reason(const d32_t *d)
{
    return d->end;
}

uint32_t d32_time_left_ms(const d32_t *d)
{
    return d->time_left_ms;
}

char *d32_time_str(const d32_t *d, char out[6])
{
    uint32_t secs = ceil_seconds(d->time_left_ms);
    uint32_t mm = secs / 60u, ss = secs % 60u;
    if (mm > 99u) {
        mm = 99u;
        ss = 59u;
    }
    out[0] = (char)('0' + mm / 10u);
    out[1] = (char)('0' + mm % 10u);
    out[2] = ':';
    out[3] = (char)('0' + ss / 10u);
    out[4] = (char)('0' + ss % 10u);
    out[5] = '\0';
    return out;
}

uint8_t d32_strikes(const d32_t *d)
{
    return d->strikes;
}

uint32_t d32_rate_ppm(const d32_t *d)
{
    return d->rate_ppm;
}

uint32_t d32_rate_permille(const d32_t *d)
{
    return (d->rate_ppm + 500u) / 1000u;
}

d32_slot_state_t d32_slot_state(const d32_t *d, int slot)
{
    return slot_ok(slot) ? d->slot_state[slot] : D32_SLOT_DISABLED;
}

int d32_enabled_count(const d32_t *d)
{
    int n = 0;
    for (int i = 0; i < D32_SLOTS; i++) {
        n += d->cfg.slot[i].enabled ? 1 : 0;
    }
    return n;
}

int d32_disarmed_count(const d32_t *d)
{
    int n = 0;
    for (int i = 0; i < D32_SLOTS; i++) {
        n += d->slot_state[i] == D32_SLOT_DISARMED ? 1 : 0;
    }
    return n;
}

bool d32_score(const d32_t *d, uint32_t *time_left_ms, uint8_t *strikes)
{
    if (d->phase != D32_WON) {
        return false;
    }
    if (time_left_ms) {
        *time_left_ms = d->time_left_ms;
    }
    if (strikes) {
        *strikes = d->strikes;
    }
    return true;
}

int d32_slot_frags(const d32_t *d, int slot, d32_frag_t *out, int max)
{
    if (!slot_ok(slot)) {
        return 0;
    }
    int n = d->nfrags[slot];
    for (int i = 0; i < n && i < max && out; i++) {
        out[i] = d->frags[slot][i];
    }
    return n;
}

uint8_t d32_revealed_mask(const d32_t *d)
{
    uint8_t mask = 0;
    for (int s = 0; s < D32_SLOTS; s++) {
        if (d->slot_state[s] != D32_SLOT_DISARMED) {
            continue;
        }
        for (int i = 0; i < d->nfrags[s]; i++) {
            mask |= (uint8_t)(1u << (d->frags[s][i].pos - 1u));
        }
    }
    return mask;
}

char *d32_revealed_word(const d32_t *d, char out[D32_COLOUR_MAX + 1])
{
    int len = d->phase == D32_IDLE ? 0 : d->colour_len;
    uint8_t mask = d32_revealed_mask(d);
    const char *colour = WIRE_COLOUR[d->target_wire];
    for (int i = 0; i < len; i++) {
        out[i] = (mask & (1u << i)) ? colour[i] : '_';
    }
    out[len] = '\0';
    return out;
}

int d32_colour_len(const d32_t *d)
{
    return d->phase == D32_IDLE ? 0 : d->colour_len;
}

char *d32_frag_str(d32_frag_t f, char out[4])
{
    out[0] = (char)('0' + f.pos % 10u);
    out[1] = ':';
    out[2] = f.letter;
    out[3] = '\0';
    return out;
}

/* ---- game master debug ---- */

int d32_target_wire(const d32_t *d)
{
    return d->phase == D32_IDLE ? -1 : (int)d->target_wire;
}

bool d32_code_for(const d32_t *d, int slot, char out[D32_CODE_LEN + 1])
{
    if (d->phase == D32_IDLE || !slot_ok(slot) || !d->cfg.slot[slot].enabled) {
        return false;
    }
    memcpy(out, d->codes[slot], D32_CODE_LEN + 1);
    return true;
}

/* ---- static names ---- */

const char *d32_slot_id(int slot)
{
    return slot_ok(slot) ? SLOT_ID[slot] : NULL;
}

const char *d32_slot_name(int slot)
{
    return slot_ok(slot) ? SLOT_NAME[slot] : NULL;
}

const char *d32_wire_colour(int wire)
{
    return (wire >= 0 && wire < D32_WIRES) ? WIRE_COLOUR[wire] : NULL;
}

const char *d32_phase_name(d32_phase_t p)
{
    return ((unsigned)p < sizeof(PHASE_NAME) / sizeof(PHASE_NAME[0])) ? PHASE_NAME[p] : "?";
}

/* ---- events ---- */

bool d32_poll_event(d32_t *d, d32_event_t *ev)
{
    if (d->ev_count == 0) {
        return false;
    }
    if (ev) {
        *ev = d->evq[d->ev_head];
    }
    d->ev_head = (uint8_t)((d->ev_head + 1u) % D32_EVQ_LEN);
    d->ev_count--;
    return true;
}

int d32_event_count(const d32_t *d)
{
    return d->ev_count;
}

uint32_t d32_events_dropped(const d32_t *d)
{
    return d->ev_dropped;
}
