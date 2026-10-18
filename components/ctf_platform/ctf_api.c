/* Machine channel for the player app (SPEC "v0.2.0" > "Machine channel").
 * The console task hands us a line that started with 0x01 (SOH); we answer
 * with exactly one frame "\x02<json>\x03\r\n".
 *
 * The frame is built in a heap buffer and sent with one write() on the
 * console fd: the UART VFS holds its write lock for a whole write() call, so
 * logs and printf from other tasks land before or after the frame, never
 * inside it (several printf calls would let them interleave mid-JSON). */
#include "ctf_platform.h"
#include "ctf_platform_priv.h"

#include <ctype.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <unistd.h>
#include "ctf_core.h"
#include "driver/uart.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

#define API_BUF_LEN 8192 /* `api list` is ~6.5 KB */

/* stdout turns "\n" into "\r\n" in CRLF mode; the frame must end "\x03\r\n". */
#if CONFIG_LIBC_STDOUT_LINE_ENDING_CRLF || CONFIG_NEWLIB_STDOUT_LINE_ENDING_CRLF
#define FRAME_END "\x03\n"
#else
#define FRAME_END "\x03\r\n"
#endif

/* ---- bounded JSON writer ---------------------------------------------- */

typedef struct {
    char *b;
    size_t n, cap;
    bool over;
} jw_t;

static void jw_raw(jw_t *w, const char *s)
{
    size_t l = strlen(s);
    if (w->n + l >= w->cap) {
        w->over = true;
        return;
    }
    memcpy(w->b + w->n, s, l);
    w->n += l;
    w->b[w->n] = '\0';
}

static void jw_fmt(jw_t *w, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
static void jw_fmt(jw_t *w, const char *fmt, ...)
{
    if (w->over) {
        return;
    }
    va_list ap;
    va_start(ap, fmt);
    int r = vsnprintf(w->b + w->n, w->cap - w->n, fmt, ap);
    va_end(ap);
    if (r < 0 || (size_t)r >= w->cap - w->n) {
        w->over = true;
        w->b[w->n] = '\0';
        return;
    }
    w->n += (size_t)r;
}

/* Quoted JSON string: escapes '"', '\\' and every control byte (< 0x20,
 * 0x7F); other bytes, UTF-8 included, pass through. NULL -> "". */
static void jw_str(jw_t *w, const char *s)
{
    static const char hex[] = "0123456789abcdef";
    jw_raw(w, "\"");
    for (const unsigned char *p = (const unsigned char *)(s ? s : ""); *p && !w->over; p++) {
        char e[7];
        unsigned char c = *p;
        if (c == '"' || c == '\\') {
            e[0] = '\\';
            e[1] = (char)c;
            e[2] = '\0';
        } else if (c == '\n') {
            strcpy(e, "\\n");
        } else if (c == '\r') {
            strcpy(e, "\\r");
        } else if (c == '\t') {
            strcpy(e, "\\t");
        } else if (c < 0x20 || c == 0x7F) {
            e[0] = '\\';
            e[1] = 'u';
            e[2] = '0';
            e[3] = '0';
            e[4] = hex[c >> 4];
            e[5] = hex[c & 0x0f];
            e[6] = '\0';
        } else {
            e[0] = (char)c;
            e[1] = '\0';
        }
        jw_raw(w, e);
    }
    jw_raw(w, "\"");
}

static void jw_error(jw_t *w, const char *reason)
{
    jw_raw(w, "{\"ok\":false,\"error\":");
    jw_str(w, reason);
    jw_raw(w, "}");
}

/* ---- helpers ------------------------------------------------------------ */

/* Next space-separated token (NUL-terminated in place), or NULL. */
static char *next_tok(char **p)
{
    char *s = *p;
    while (*s == ' ' || *s == '\t') {
        s++;
    }
    if (!*s) {
        *p = s;
        return NULL;
    }
    char *t = s;
    while (*s && *s != ' ' && *s != '\t') {
        s++;
    }
    if (*s) {
        *s++ = '\0';
    }
    *p = s;
    return t;
}

/* The rest of the line, leading and trailing blanks trimmed. */
static char *rest_of(char *p)
{
    while (*p == ' ' || *p == '\t') {
        p++;
    }
    size_t l = strlen(p);
    while (l && (p[l - 1] == ' ' || p[l - 1] == '\t')) {
        p[--l] = '\0';
    }
    return p;
}

static const ctf_challenge_t *find_id(const char *arg)
{
    char id[16];
    size_t i = 0;
    for (; arg && arg[i] && i + 1 < sizeof(id); i++) {
        id[i] = (char)toupper((unsigned char)arg[i]);
    }
    id[i] = '\0';
    return ctf_find(id);
}

static const char *mode_of(const ctf_challenge_t *c)
{
    if (strcmp(c->track, "BLE") == 0 || strcmp(c->track, "BTC") == 0) {
        return "radio";
    }
    return strcmp(c->track, "WEB") == 0 ? "net" : "any";
}

/* ---- commands ----------------------------------------------------------- */

static void api_info(jw_t *w)
{
    char board[CTF_BOARD_NAME_LEN];
    ctf_platform_board_name(board);
    int earned = ctf_earned(), spent = ctf_spent(), solved = 0;
    for (size_t i = 0; i < ctf_count(); i++) {
        solved += ctf_is_solved(ctf_get(i)->id) ? 1 : 0;
    }
    jw_raw(w, "{\"ok\":true,\"fw\":");
    jw_str(w, CTF_FW_VERSION);
    jw_raw(w, ",\"board\":");
    jw_str(w, board);
    jw_raw(w, ",\"mode\":");
    jw_str(w, ctf_platform_mode_name(ctf_platform_mode()));
    jw_fmt(w, ",\"points\":%d,\"start\":%d,\"earned\":%d,\"spent\":%d,\"solved\":%d,\"total\":%u}",
           CTF_START_POINTS + earned - spent, CTF_START_POINTS, earned, spent, solved,
           (unsigned)ctf_count());
}

static void api_list(jw_t *w)
{
    jw_raw(w, "{\"ok\":true,\"challenges\":[");
    for (size_t i = 0; i < ctf_count(); i++) {
        const ctf_challenge_t *c = ctf_get(i);
        jw_raw(w, i ? ",{\"id\":" : "{\"id\":");
        jw_str(w, c->id);
        jw_raw(w, ",\"track\":");
        jw_str(w, c->track);
        jw_raw(w, ",\"name\":");
        jw_str(w, c->name);
        jw_fmt(w, ",\"pts\":%d,\"kit\":", ctf_value(c->id));
        jw_str(w, c->kit);
        jw_raw(w, ",\"mode\":");
        jw_str(w, mode_of(c));
        jw_fmt(w, ",\"solved\":%s,\"answer\":%s,\"tier\":%d,\"prices\":[%d,%d,%d]}",
               ctf_is_solved(c->id) ? "true" : "false",
               ctf_has_answer(c->id) ? "true" : "false", ctf_hint_tier(c->id),
               ctf_hint_price(c->id, 1), ctf_hint_price(c->id, 2), ctf_hint_price(c->id, 3));
    }
    jw_raw(w, "]}");
}

static void api_submit(jw_t *w, char *arg)
{
    const ctf_challenge_t *c = NULL;
    const char *res;
    switch (ctf_submit(arg, &c)) {
    case CTF_SUBMIT_NEW: res = "new"; break;
    case CTF_SUBMIT_ALREADY: res = "already"; break;
    default: res = "wrong"; break;
    }
    jw_raw(w, "{\"ok\":true,\"result\":");
    jw_str(w, res);
    if (c) {
        jw_raw(w, ",\"id\":");
        jw_str(w, c->id);
        jw_fmt(w, ",\"pts\":%d", ctf_value(c->id));
    }
    jw_fmt(w, ",\"points\":%d}", ctf_points());
}

static void api_hint(jw_t *w, char *p)
{
    const char *ids = next_tok(&p);
    const char *ts = next_tok(&p);
    const ctf_challenge_t *c = ids ? find_id(ids) : NULL;
    if (!c) {
        jw_error(w, "unknown challenge");
        return;
    }
    if (!ts || !(ts[0] >= '1' && ts[0] <= '0' + CTF_HINT_TIERS && ts[1] == '\0')) {
        jw_error(w, "bad tier");
        return;
    }
    int tier = ts[0] - '0';
    const char *text = NULL;
    ctf_hint_result_t r = ctf_hint_buy(c->id, tier, &text);
    if (r == CTF_HINT_OK) {
        jw_raw(w, "{\"ok\":true,\"id\":");
        jw_str(w, c->id);
        jw_fmt(w, ",\"tier\":%d,\"text\":", tier);
        jw_str(w, text);
        jw_fmt(w, ",\"points\":%d}", ctf_points());
    } else if (r == CTF_HINT_LOCKED || r == CTF_HINT_POINTS) {
        jw_fmt(w, "{\"ok\":false,\"error\":\"%s\",\"need\":%d,\"points\":%d}",
               r == CTF_HINT_LOCKED ? "locked" : "points", ctf_hint_price(c->id, tier),
               ctf_points());
    } else {
        jw_error(w, "bad tier");
    }
}

static void api_answer(jw_t *w, char *p)
{
    const char *ids = next_tok(&p);
    const ctf_challenge_t *c = ids ? find_id(ids) : NULL;
    if (!c) {
        jw_error(w, "unknown challenge");
        return;
    }
    char flag[CTF_FLAG_LEN + 1];
    if (ctf_answer(c->id, rest_of(p), flag)) {
        jw_raw(w, "{\"ok\":true,\"correct\":true,\"flag\":");
        jw_str(w, flag);
        jw_raw(w, "}");
    } else {
        jw_raw(w, "{\"ok\":true,\"correct\":false}");
    }
    memset(flag, 0, sizeof(flag));
}

/* Returns true when the board must reboot into *mode after the reply. */
static bool api_mode(jw_t *w, char *p, ctf_mode_t *mode)
{
    const char *m = next_tok(&p);
    if (m && strcasecmp(m, "radio") == 0) {
        *mode = CTF_MODE_RADIO;
    } else if (m && strcasecmp(m, "net") == 0) {
        *mode = CTF_MODE_NET;
    } else {
        jw_error(w, "usage: api mode radio|net");
        return false;
    }
    jw_raw(w, "{\"ok\":true,\"mode\":");
    jw_str(w, ctf_platform_mode_name(*mode));
    jw_raw(w, ",\"rebooting\":true}");
    return true;
}

/* ---- entry -------------------------------------------------------------- */

static void send_frame(const char *json, size_t n)
{
    fflush(stdout); /* anything already buffered goes out before the frame */
    /* Frame = STX + json + FRAME_END in one write() (see top of file). */
    const char *p = json - 1;
    size_t len = n + 1 + strlen(FRAME_END);
    while (len) {
        ssize_t r = write(STDOUT_FILENO, p, len);
        if (r <= 0) {
            break;
        }
        p += r;
        len -= (size_t)r;
    }
}

void ctf_api_run(char *line)
{
    static const char oom[] = "\x02{\"ok\":false,\"error\":\"out of memory\"}" FRAME_END;
    char *buf = malloc(API_BUF_LEN);
    if (!buf) {
        fflush(stdout);
        (void)!write(STDOUT_FILENO, oom, sizeof(oom) - 1);
        return;
    }
    /* buf[0] = STX, JSON from buf + 1, FRAME_END appended after it. */
    size_t tail = strlen(FRAME_END);
    jw_t w = {.b = buf + 1, .n = 0, .cap = API_BUF_LEN - 1 - tail, .over = false};
    buf[0] = '\x02';
    w.b[0] = '\0';

    bool reboot = false;
    ctf_mode_t mode = CTF_MODE_RADIO;
    char *p = line;
    const char *api = next_tok(&p);
    const char *cmd = next_tok(&p);
    if (!api || strcmp(api, "api") != 0 || !cmd) {
        jw_error(&w, "unknown command");
    } else if (strcmp(cmd, "info") == 0) {
        api_info(&w);
    } else if (strcmp(cmd, "list") == 0) {
        api_list(&w);
    } else if (strcmp(cmd, "submit") == 0) {
        api_submit(&w, rest_of(p));
    } else if (strcmp(cmd, "hint") == 0) {
        api_hint(&w, p);
    } else if (strcmp(cmd, "answer") == 0) {
        api_answer(&w, p);
    } else if (strcmp(cmd, "mode") == 0) {
        reboot = api_mode(&w, p, &mode);
    } else {
        jw_error(&w, "unknown command");
    }
    if (w.over) {
        w.n = 0;
        w.over = false;
        w.b[0] = '\0';
        reboot = false;
        jw_error(&w, "reply too long");
    }
    memcpy(w.b + w.n, FRAME_END, tail + 1);
    send_frame(w.b, w.n);
    free(buf);

    if (reboot) {
        uart_wait_tx_done(UART_NUM_0, pdMS_TO_TICKS(200));
        ctf_platform_save_mode(mode);
        vTaskDelay(pdMS_TO_TICKS(100));
        esp_restart();
    }
}
