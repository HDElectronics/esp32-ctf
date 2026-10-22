#pragma once
/* d32_engine: portable game engine for the Defuse32 training case
 * (hardware/defuse32/FIRMWARE.md "Game rules the engine implements").
 *
 * Portable C11: no IDF/FreeRTOS headers, no heap, no hidden globals. All state
 * lives in one d32_t that the caller owns and passes to every call. Not thread
 * safe: the caller serialises access (one game task, or a mutex around calls).
 *
 * Codes and the target wire are derived with ctf_derive / ctf_derive_u32, so
 * ctf_init() must have been called (with the board MAC) before d32_arm().
 *
 * Time is integer milliseconds. The clock rate is fixed point: internally in
 * ppm (1000000 = 1x), reported in permille. Each strike multiplies the rate by
 * strike_rate_permille / 1000, rounded half up to the nearest ppm; tick() keeps
 * the sub-millisecond remainder, so splitting a tick never changes the result.
 * The rate is capped at 1000x (1e9 ppm). */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define D32_SLOTS        6   /* module slots M1..M6 */
#define D32_WIRES        6   /* final wires, index 0..5 */
#define D32_CODE_LEN     6   /* 6 uppercase hex chars */
#define D32_VARIANT_MAX  24  /* variant string incl. NUL (longer is truncated) */
#define D32_MAX_FRAGS    6   /* letters one slot can carry (1 enabled module, 6-letter colour) */
#define D32_COLOUR_MAX   6   /* longest colour name ("YELLOW") */
#define D32_EVQ_LEN      32  /* event ring capacity */
#define D32_TILT_GAP_MS  5000u

/* Defaults and accepted ranges (out-of-range values fall back to the default). */
#define D32_DEF_MINUTES      45
#define D32_MAX_MINUTES      99   /* keeps MM:SS two-digit */
#define D32_DEF_MAX_STRIKES  3
#define D32_MAX_MAX_STRIKES  9
#define D32_DEF_RATE         1250 /* permille: 1.25x per strike */
#define D32_MIN_RATE         1000
#define D32_MAX_RATE         4000

typedef enum {
    D32_IDLE,
    D32_ARMED,  /* timer running, at least one enabled module armed */
    D32_FINAL,  /* all enabled modules disarmed, timer still running */
    D32_WON,
    D32_LOST,
} d32_phase_t;

typedef enum {
    D32_SLOT_DISABLED, /* not enabled in the config */
    D32_SLOT_IDLE,     /* enabled, no round yet */
    D32_SLOT_ARMED,
    D32_SLOT_DISARMED,
} d32_slot_state_t;

typedef enum {
    D32_STRIKE_CODE,   /* wrong code */
    D32_STRIKE_WIRE,   /* wire pulled before FINAL */
    D32_STRIKE_TILT,   /* tilt event (rate limited) */
    D32_STRIKE_MANUAL, /* game master / console */
} d32_strike_reason_t;

typedef enum {
    D32_END_NONE,
    D32_END_WON,     /* target wire pulled in FINAL */
    D32_END_TIME,    /* timer reached zero */
    D32_END_STRIKES, /* max_strikes reached */
    D32_END_WIRE,    /* wrong wire pulled in FINAL */
} d32_end_t;

typedef enum {
    D32_CODE_DISARMED,  /* matched an armed module: now disarmed */
    D32_CODE_ALREADY,   /* matched a module that was already disarmed: no strike */
    D32_CODE_REJECTED,  /* well formed but no match: strike (none in training) */
    D32_CODE_INVALID,   /* not 6 hex chars after removing whitespace: no strike */
    D32_CODE_NOT_ARMED, /* phase is not ARMED or FINAL */
} d32_code_result_t;

typedef enum {
    D32_WIRE_EARLY,     /* pulled before FINAL: strike (none in training) */
    D32_WIRE_WON,       /* target wire in FINAL */
    D32_WIRE_LOST,      /* other wire in FINAL */
    D32_WIRE_INVALID,   /* index outside 0..5 */
    D32_WIRE_NOT_ARMED, /* phase is not ARMED or FINAL */
} d32_wire_result_t;

typedef enum {
    D32_ARM_OK,
    D32_ARM_BUSY,       /* not IDLE: reset first */
    D32_ARM_NO_MODULES, /* no enabled module (no fragments to carry the colour) */
} d32_arm_result_t;

typedef struct {
    bool enabled;
    char variant[D32_VARIANT_MAX];
} d32_slot_cfg_t;

typedef struct {
    uint16_t minutes;              /* 1..99, default 45 */
    uint8_t max_strikes;           /* 1..9, default 3 */
    uint16_t strike_rate_permille; /* 1000..4000, default 1250 */
    bool training;                 /* no timer, no strikes */
    d32_slot_cfg_t slot[D32_SLOTS];
} d32_config_t;

/* One letter of the target colour name: shown to players as "<pos>:<letter>". */
typedef struct {
    uint8_t pos; /* 1-based position in the colour name */
    char letter; /* uppercase */
} d32_frag_t;

typedef enum {
    D32_EV_PHASE,    /* phase changed: .phase */
    D32_EV_DISARMED, /* .slot disarmed; .nfrags fragments in .frags */
    D32_EV_STRIKE,   /* .reason (d32_strike_reason_t), .strikes, .rate_permille */
    D32_EV_REJECTED, /* code rejected (also queued in training, without a strike) */
    D32_EV_TICK,     /* displayed second changed: .seconds = ceil(time left / 1000) */
    D32_EV_RESULT,   /* round over: .reason (d32_end_t), .time_left_ms, .strikes */
} d32_event_type_t;

typedef struct {
    d32_event_type_t type;
    d32_phase_t phase;
    uint8_t slot;
    uint8_t reason;
    uint8_t strikes;
    uint8_t nfrags;
    uint32_t rate_permille;
    uint32_t seconds;
    uint32_t time_left_ms;
    d32_frag_t frags[D32_MAX_FRAGS];
} d32_event_t;

/* Engine context. Treat the fields as private; use the functions below. */
typedef struct {
    d32_config_t cfg;
    d32_phase_t phase;
    d32_end_t end;
    uint32_t seed;
    uint32_t time_left_ms;
    uint32_t frac_ppm;      /* sub-millisecond remainder of game time, in ppm-ms */
    uint32_t rate_ppm;      /* 1000000 = 1x */
    uint32_t last_seconds;  /* last value sent in a TICK event */
    uint8_t strikes;
    bool tilt_seen;
    uint32_t last_tilt_ms;
    uint8_t target_wire;
    uint8_t colour_len;
    d32_slot_state_t slot_state[D32_SLOTS];
    char codes[D32_SLOTS][D32_CODE_LEN + 1];
    uint8_t nfrags[D32_SLOTS];
    d32_frag_t frags[D32_SLOTS][D32_MAX_FRAGS];
    d32_event_t evq[D32_EVQ_LEN];
    uint8_t ev_head;        /* index of the oldest event */
    uint8_t ev_count;
    uint32_t ev_dropped;
} d32_t;

/* ---- config ---- */

/* Defaults: 45 min, 3 strikes, 1250 permille, not training, all slots enabled
 * with an empty variant. */
void d32_config_default(d32_config_t *cfg);
/* Replaces out-of-range values with their defaults and NUL-terminates the
 * variants. Returns the number of fields it changed (for a pack warning). */
unsigned d32_config_sanitize(d32_config_t *cfg);

/* Sanitised copy of *cfg (NULL = defaults); clears all state to IDLE. */
void d32_init(d32_t *d, const d32_config_t *cfg);
/* Replaces the config; only in IDLE (returns false otherwise). */
bool d32_set_config(d32_t *d, const d32_config_t *cfg);
const d32_config_t *d32_config(const d32_t *d);

/* ---- round control ---- */

/* Back to IDLE from any phase. Clears codes, strikes, fragments and the event
 * queue, then queues PHASE(IDLE) if the phase changed. Config is kept. */
void d32_reset(d32_t *d);
/* IDLE -> ARMED: derives codes, target wire and fragments from seed, starts the
 * timer at minutes * 60000 ms with rate 1x, queues PHASE(ARMED). */
d32_arm_result_t d32_arm(d32_t *d, uint32_t seed);
/* Advances the clock by dt_ms of real time (ARMED/FINAL, not training). Queues
 * TICK when the displayed second changes; at zero the round is LOST (TIME). */
void d32_tick(d32_t *d, uint32_t dt_ms);
/* Code entry. On DISARMED, *slot_out (if non-NULL) is the slot; on ALREADY,
 * the slot whose code matched. Disarming the last enabled module -> FINAL. */
d32_code_result_t d32_submit_code(d32_t *d, const char *text, int *slot_out);
d32_wire_result_t d32_wire_pulled(d32_t *d, int index);
/* Tilt from the motion sensor at time now_ms (any monotonic ms clock). Strikes
 * at most once per D32_TILT_GAP_MS; returns true if it struck. */
bool d32_tilt(d32_t *d, uint32_t now_ms);
/* Adds a strike (ARMED/FINAL, not training): rate *= strike_rate, queues
 * STRIKE; at max_strikes the round is LOST (STRIKES). Returns true if applied. */
bool d32_strike(d32_t *d, d32_strike_reason_t reason);

/* ---- state ---- */

d32_phase_t d32_phase(const d32_t *d);
d32_end_t d32_end_reason(const d32_t *d);
uint32_t d32_time_left_ms(const d32_t *d);
/* "MM:SS" of ceil(time left / 1000) seconds; returns out. */
char *d32_time_str(const d32_t *d, char out[6]);
uint8_t d32_strikes(const d32_t *d);
uint32_t d32_rate_permille(const d32_t *d); /* rounded half up from ppm */
uint32_t d32_rate_ppm(const d32_t *d);
d32_slot_state_t d32_slot_state(const d32_t *d, int slot); /* DISABLED if out of range */
int d32_enabled_count(const d32_t *d);
int d32_disarmed_count(const d32_t *d);
/* Score at WON (false otherwise): time left in ms and strikes used. */
bool d32_score(const d32_t *d, uint32_t *time_left_ms, uint8_t *strikes);

/* Fragments carried by a slot (whether revealed or not, 0 when IDLE). Copies
 * up to max into out and returns the count. Game master / adapters only. */
int d32_slot_frags(const d32_t *d, int slot, d32_frag_t *out, int max);
/* Bit (pos - 1) set for every letter revealed by a disarmed module. */
uint8_t d32_revealed_mask(const d32_t *d);
/* Colour name with unrevealed letters as '_' (e.g. "B__E"); "" when IDLE. */
char *d32_revealed_word(const d32_t *d, char out[D32_COLOUR_MAX + 1]);
/* Length of the target colour name (0 when IDLE). */
int d32_colour_len(const d32_t *d);
/* "<pos>:<letter>" + NUL. */
char *d32_frag_str(d32_frag_t f, char out[4]);

/* ---- game master debug (console `round codes`) ---- */

/* Target wire index 0..5, or -1 when IDLE. */
int d32_target_wire(const d32_t *d);
/* Current code of slot (6 uppercase hex + NUL); false when IDLE, slot out of
 * range or disabled. */
bool d32_code_for(const d32_t *d, int slot, char out[D32_CODE_LEN + 1]);

/* ---- static names ---- */

const char *d32_slot_id(int slot);     /* "M1".."M6", NULL if out of range */
const char *d32_slot_name(int slot);   /* "radio" "timer" "keypad" "wires" "probe" "sensors" */
const char *d32_wire_colour(int wire); /* "RED" "BLUE" "YELLOW" "GREEN" "WHITE" "BLACK" */
const char *d32_phase_name(d32_phase_t p); /* "idle" "armed" "final" "won" "lost" */

/* ---- events ---- */

/* Pops the oldest event into *ev; false when the queue is empty. When the
 * ring is full, a new event overwrites the oldest one and ev_dropped grows. */
bool d32_poll_event(d32_t *d, d32_event_t *ev);
int d32_event_count(const d32_t *d);
uint32_t d32_events_dropped(const d32_t *d);

#ifdef __cplusplus
}
#endif
