/* Defuse32 challenge packs (hardware/defuse32/FIRMWARE.md "Packs").
 *
 * A pack is a JSON file /sd/packs/<name>.json, or the compiled-in default.
 * Packs carry no flags or codes, only round settings and per-slot variants.
 *
 * Two layers:
 *   - parse core (d32_pack_parse.c): portable C + cJSON, no IDF headers, so
 *     test/host can build it;
 *   - loader (d32_pack.c): file listing/loading on the SD card, ESP logging,
 *     the currently selected pack. */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define D32_PACK_FORMAT         1
#define D32_PACK_SLOTS          6       /* M1..M6 */
#define D32_PACK_ID_MAX         32      /* incl. NUL */
#define D32_PACK_TITLE_MAX      48
#define D32_PACK_VERSION_MAX    16
#define D32_PACK_VARIANT_MAX    24
#define D32_PACK_NAME_MAX       32      /* file name without ".json" */
#define D32_PACK_FILE_MAX       8192    /* larger files are rejected */
#define D32_PACK_BUILTIN_NAME   "builtin"

/* Round defaults and accepted ranges. */
#define D32_PACK_DEF_MINUTES    45
#define D32_PACK_MIN_MINUTES    1
#define D32_PACK_MAX_MINUTES    180
#define D32_PACK_DEF_STRIKES    3
#define D32_PACK_MIN_STRIKES    1
#define D32_PACK_MAX_STRIKES    9
#define D32_PACK_DEF_RATE       1.25f
#define D32_PACK_MIN_RATE       1.0f
#define D32_PACK_MAX_RATE       4.0f

typedef struct {
    bool enabled;
    char variant[D32_PACK_VARIANT_MAX];     /* [a-z0-9_-], 1..23 chars */
} d32_pack_slot_t;

typedef struct {
    int format;
    char id[D32_PACK_ID_MAX];
    char title[D32_PACK_TITLE_MAX];
    char version[D32_PACK_VERSION_MAX];
    /* round */
    int minutes;
    int max_strikes;
    float strike_rate;
    bool training;
    /* modules, index 0..5 = M1..M6 */
    d32_pack_slot_t slots[D32_PACK_SLOTS];
} d32_pack_t;

/* Warning sink for the parser (may be NULL). */
typedef void (*d32_pack_warn_fn)(void *ctx, const char *msg);

/* ---- parse core (portable) ------------------------------------------------ */

/* Slot id "M1".."M6" and plate name ("radio", "timer", "keypad", "wires",
 * "probe", "sensors"); NULL for an out-of-range index. */
const char *d32_pack_slot_id(int slot);
const char *d32_pack_slot_name(int slot);

/* Fill *out with the built-in default pack. */
void d32_pack_defaults(d32_pack_t *out);

/* Parse pack JSON (len bytes; need not be NUL-terminated). Missing or invalid
 * values keep their defaults and produce one warning each; unknown keys are
 * ignored. Returns the number of warnings (>= 0), or -1 if the text is not a
 * JSON object (then *out holds the defaults). */
int d32_pack_parse(const char *json, size_t len, d32_pack_t *out, d32_pack_warn_fn warn, void *ctx);

/* True if `name` is a valid pack file name: [A-Za-z0-9_-], 1..31 chars. */
bool d32_pack_name_valid(const char *name);

/* ---- loader (ESP-IDF) ------------------------------------------------------ */

/* List pack names (file names without ".json", sorted) in `dir`, normally
 * "/sd/packs". Returns the count written (<= max), or -1 if the directory
 * cannot be opened. */
int d32_pack_list(const char *dir, char names[][D32_PACK_NAME_MAX], int max);

/* Load "/sd/packs/<name>.json"; name "builtin" gives the default pack.
 * 0 on success (warnings are logged), -1 on error (*out = defaults). */
int d32_pack_load(const char *name, d32_pack_t *out);

/* Same with an explicit directory. */
int d32_pack_load_from(const char *dir, const char *name, d32_pack_t *out);

/* Currently selected pack (the built-in default until one is selected) and
 * the name it was loaded from. */
const d32_pack_t *d32_pack_current(void);
const char *d32_pack_current_name(void);
void d32_pack_select(const d32_pack_t *pack, const char *name);

#define D32_PACK_DIR "/sd/packs"

#ifdef __cplusplus
}
#endif
