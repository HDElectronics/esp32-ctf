/* Pack JSON parse core. Portable C11 + cJSON only: no IDF/FreeRTOS headers,
 * so test/host can build and test it. */
#include "d32_pack.h"

#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "cJSON.h"

static const char *const s_slot_id[D32_PACK_SLOTS] = { "M1", "M2", "M3", "M4", "M5", "M6" };
static const char *const s_slot_name[D32_PACK_SLOTS] = {
    "radio", "timer", "keypad", "wires", "probe", "sensors",
};
static const char *const s_default_variant[D32_PACK_SLOTS] = {
    "ble-read", "buzzer-morse", "menu", "patch-a", "uart-115200", "touch-4",
};

const char *d32_pack_slot_id(int slot)
{
    return (slot >= 0 && slot < D32_PACK_SLOTS) ? s_slot_id[slot] : NULL;
}

const char *d32_pack_slot_name(int slot)
{
    return (slot >= 0 && slot < D32_PACK_SLOTS) ? s_slot_name[slot] : NULL;
}

static void copy_str(char *dst, size_t cap, const char *src)
{
    size_t n = strlen(src);
    if (n >= cap) {
        n = cap - 1;
    }
    memcpy(dst, src, n);
    dst[n] = '\0';
}

void d32_pack_defaults(d32_pack_t *out)
{
    memset(out, 0, sizeof(*out));
    out->format = D32_PACK_FORMAT;
    copy_str(out->id, sizeof(out->id), D32_PACK_BUILTIN_NAME);
    copy_str(out->title, sizeof(out->title), "Built-in default");
    copy_str(out->version, sizeof(out->version), "0.1.0");
    out->minutes = D32_PACK_DEF_MINUTES;
    out->max_strikes = D32_PACK_DEF_STRIKES;
    out->strike_rate = D32_PACK_DEF_RATE;
    out->training = false;
    for (int i = 0; i < D32_PACK_SLOTS; i++) {
        out->slots[i].enabled = true;
        copy_str(out->slots[i].variant, sizeof(out->slots[i].variant), s_default_variant[i]);
    }
}

typedef struct {
    d32_pack_warn_fn fn;
    void *ctx;
    int count;
} warn_t;

static void warnf(warn_t *w, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
static void warnf(warn_t *w, const char *fmt, ...)
{
    w->count++;
    if (!w->fn) {
        return;
    }
    char msg[112];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(msg, sizeof(msg), fmt, ap);
    va_end(ap);
    w->fn(w->ctx, msg);
}

static bool name_char_ok(char c, bool upper_ok)
{
    return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-' || c == '_' ||
           (upper_ok && c >= 'A' && c <= 'Z');
}

static bool token_valid(const char *s, size_t cap, bool upper_ok)
{
    size_t n = strlen(s);
    if (n == 0 || n >= cap) {
        return false;
    }
    for (size_t i = 0; i < n; i++) {
        if (!name_char_ok(s[i], upper_ok)) {
            return false;
        }
    }
    return true;
}

bool d32_pack_name_valid(const char *name)
{
    return name && token_valid(name, D32_PACK_NAME_MAX, true);
}

/* Optional string field: keeps the default when missing/invalid. */
static void get_str(warn_t *w, const cJSON *obj, const char *key, char *dst, size_t cap)
{
    const cJSON *it = cJSON_GetObjectItemCaseSensitive(obj, key);
    if (!it) {
        warnf(w, "\"%s\" missing, using \"%s\"", key, dst);
        return;
    }
    if (!cJSON_IsString(it) || !it->valuestring || !it->valuestring[0]) {
        warnf(w, "\"%s\" is not a non-empty string, using \"%s\"", key, dst);
        return;
    }
    if (strlen(it->valuestring) >= cap) {
        warnf(w, "\"%s\" longer than %u chars, truncated", key, (unsigned)(cap - 1));
    }
    copy_str(dst, cap, it->valuestring);
}

static void get_int(warn_t *w, const cJSON *obj, const char *path, const char *key, int *dst, int lo, int hi)
{
    const cJSON *it = cJSON_GetObjectItemCaseSensitive(obj, key);
    if (!it) {
        warnf(w, "%s.%s missing, using %d", path, key, *dst);
        return;
    }
    double d = cJSON_IsNumber(it) ? it->valuedouble : NAN;
    if (!(d >= lo && d <= hi) || d != floor(d)) {
        warnf(w, "%s.%s must be an integer %d..%d, using %d", path, key, lo, hi, *dst);
        return;
    }
    *dst = (int)d;
}

static void get_bool(warn_t *w, const cJSON *obj, const char *path, const char *key, bool *dst)
{
    const cJSON *it = cJSON_GetObjectItemCaseSensitive(obj, key);
    if (!it) {
        warnf(w, "%s.%s missing, using %s", path, key, *dst ? "true" : "false");
        return;
    }
    if (!cJSON_IsBool(it)) {
        warnf(w, "%s.%s must be true/false, using %s", path, key, *dst ? "true" : "false");
        return;
    }
    *dst = cJSON_IsTrue(it);
}

static void parse_round(warn_t *w, const cJSON *root, d32_pack_t *p)
{
    const cJSON *r = cJSON_GetObjectItemCaseSensitive(root, "round");
    if (!cJSON_IsObject(r)) {
        warnf(w, "\"round\" %s, using default round settings", r ? "is not an object" : "missing");
        return;
    }
    get_int(w, r, "round", "minutes", &p->minutes, D32_PACK_MIN_MINUTES, D32_PACK_MAX_MINUTES);
    get_int(w, r, "round", "max_strikes", &p->max_strikes, D32_PACK_MIN_STRIKES, D32_PACK_MAX_STRIKES);
    const cJSON *it = cJSON_GetObjectItemCaseSensitive(r, "strike_rate");
    if (!it) {
        warnf(w, "round.strike_rate missing, using %.2f", (double)p->strike_rate);
    } else if (!cJSON_IsNumber(it) || !(it->valuedouble >= D32_PACK_MIN_RATE && it->valuedouble <= D32_PACK_MAX_RATE)) {
        warnf(w, "round.strike_rate must be a number %.1f..%.1f, using %.2f",
              (double)D32_PACK_MIN_RATE, (double)D32_PACK_MAX_RATE, (double)p->strike_rate);
    } else {
        p->strike_rate = (float)it->valuedouble;
    }
    get_bool(w, r, "round", "training", &p->training);
}

static void parse_modules(warn_t *w, const cJSON *root, d32_pack_t *p)
{
    const cJSON *m = cJSON_GetObjectItemCaseSensitive(root, "modules");
    if (!cJSON_IsObject(m)) {
        warnf(w, "\"modules\" %s, using default modules", m ? "is not an object" : "missing");
        return;
    }
    for (int i = 0; i < D32_PACK_SLOTS; i++) {
        const char *id = s_slot_id[i];
        d32_pack_slot_t *s = &p->slots[i];
        const cJSON *so = cJSON_GetObjectItemCaseSensitive(m, id);
        if (!cJSON_IsObject(so)) {
            warnf(w, "modules.%s %s, using default (enabled, \"%s\")", id,
                  so ? "is not an object" : "missing", s->variant);
            continue;
        }
        char path[16];
        snprintf(path, sizeof(path), "modules.%s", id);
        get_bool(w, so, path, "enabled", &s->enabled);
        const cJSON *v = cJSON_GetObjectItemCaseSensitive(so, "variant");
        if (!v) {
            warnf(w, "%s.variant missing, using \"%s\"", path, s->variant);
        } else if (!cJSON_IsString(v) || !v->valuestring ||
                   !token_valid(v->valuestring, sizeof(s->variant), false)) {
            warnf(w, "%s.variant must be 1..%u chars of [a-z0-9_-], using \"%s\"", path,
                  (unsigned)(sizeof(s->variant) - 1), s->variant);
        } else {
            copy_str(s->variant, sizeof(s->variant), v->valuestring);
        }
    }
}

int d32_pack_parse(const char *json, size_t len, d32_pack_t *out, d32_pack_warn_fn warn, void *ctx)
{
    warn_t w = { .fn = warn, .ctx = ctx, .count = 0 };
    d32_pack_defaults(out);
    if (!json) {
        warnf(&w, "no pack text");
        return -1;
    }
    cJSON *root = cJSON_ParseWithLength(json, len);
    if (!cJSON_IsObject(root)) {
        warnf(&w, "not a JSON object%s", root ? "" : " (syntax error)");
        cJSON_Delete(root);
        return -1;
    }

    const cJSON *fmt = cJSON_GetObjectItemCaseSensitive(root, "format");
    if (!fmt) {
        warnf(&w, "\"format\" missing, assuming %d", D32_PACK_FORMAT);
    } else if (!cJSON_IsNumber(fmt) || fmt->valuedouble != D32_PACK_FORMAT) {
        warnf(&w, "\"format\" is not %d, reading it as format %d", D32_PACK_FORMAT, D32_PACK_FORMAT);
    }
    /* A file pack is not the built-in one: start from neutral metadata. */
    copy_str(out->id, sizeof(out->id), "unnamed");
    copy_str(out->title, sizeof(out->title), "Untitled pack");
    copy_str(out->version, sizeof(out->version), "0.0.0");
    get_str(&w, root, "id", out->id, sizeof(out->id));
    get_str(&w, root, "title", out->title, sizeof(out->title));
    get_str(&w, root, "version", out->version, sizeof(out->version));
    parse_round(&w, root, out);
    parse_modules(&w, root, out);

    cJSON_Delete(root);
    return w.count;
}
