/* track_web main HTTP server, port 80 (SPEC "Web"):
 *   /              WEB-01 flag, WEB-02 part 1 (HTML comment), CRY-01 shard 4, role cookie
 *   /robots.txt    disallows /staging/ (WEB-02 part 2)
 *   /admin         WEB-03 (cookie role=admin)
 *   /api/docs      WEB-04 key; /api/secret needs User-Agent + X-CTF-Key
 *   /login /vault  WEB-05 HS256 JWT; /wordlist.txt the secret's word list
 *   /diag          WEB-06 log viewer, ../ allowed but confined to /storage
 *   /ws            WEB-07 WebSocket: noise text every 1 s, flag binary every 30 s
 *   /score /submit scoreboard and flag submission (ctf_submit)
 * Handlers run in the single httpd task, so the static buffers are not shared
 * between concurrent requests. Page templates are embedded (EMBED_TXTFILES);
 * {{NAME}} placeholders are filled at runtime, no flag is stored in them. */
#include "web_priv.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include "ctf_core.h"
#include "ctf_sha256.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_random.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "web_http";

extern const char index_html[] asm("_binary_index_html_start");
extern const char page_html[] asm("_binary_page_html_start");
extern const char docs_html[] asm("_binary_docs_html_start");
extern const char login_html[] asm("_binary_login_html_start");
extern const char diag_html[] asm("_binary_diag_html_start");
extern const char submit_html[] asm("_binary_submit_html_start");
extern const char robots_txt[] asm("_binary_robots_txt_start");

#define MAX_SOCKETS 8

static httpd_handle_t s_srv;
static const char *s_title = "";  /* {{TITLE}} for the current response */
static char s_body[3072];         /* {{BODY}} for the current response */
static char s_cookie[400];        /* Set-Cookie value (must outlive the send) */

/* ---------------- small helpers ---------------- */

static void url_decode(char *s)
{
    char *o = s;
    for (const char *p = s; *p; p++) {
        if (*p == '+') {
            *o++ = ' ';
        } else if (*p == '%' && isxdigit((unsigned char)p[1]) && isxdigit((unsigned char)p[2])) {
            char hex[3] = {p[1], p[2], 0};
            *o++ = (char)strtol(hex, NULL, 16);
            p += 2;
        } else {
            *o++ = *p;
        }
    }
    *o = '\0';
}

/* Appends HTML-escaped src to dst (NUL-terminated, bounded). */
static void html_cat(char *dst, size_t cap, const char *src, size_t n)
{
    size_t o = strlen(dst);
    for (size_t i = 0; i < n && o + 7 < cap; i++) {
        const char *rep = NULL;
        switch (src[i]) {
        case '<': rep = "&lt;"; break;
        case '>': rep = "&gt;"; break;
        case '&': rep = "&amp;"; break;
        case '"': rep = "&quot;"; break;
        default: break;
        }
        if (rep) {
            size_t l = strlen(rep);
            memcpy(dst + o, rep, l);
            o += l;
        } else if (src[i] == '\n' || src[i] == '\t' || (unsigned char)src[i] >= 0x20) {
            dst[o++] = src[i];
        } else {
            dst[o++] = '.';
        }
    }
    dst[o] = '\0';
}

static const char *tpl_var(const char *name, size_t len, char *buf, size_t sz)
{
#define IS(lit) (len == sizeof(lit) - 1 && memcmp(name, lit, len) == 0)
    if (IS("TITLE")) {
        return s_title;
    }
    if (IS("BODY")) {
        return s_body;
    }
    if (IS("WEB01")) {
        ctf_flag("WEB-01", buf);
        return buf;
    }
    if (IS("PART1")) {
        char body[13];
        ctf_flag_body("WEB-02", body);
        snprintf(buf, sz, "%.6s", body);
        return buf;
    }
    if (IS("SHARD")) {
        return g_web.shard;
    }
    if (IS("APIKEY")) {
        return g_web.api_key;
    }
#undef IS
    return "";
}

/* Streams an embedded template, filling {{NAME}} placeholders. */
static esp_err_t send_tpl(httpd_req_t *req, const char *tpl)
{
    char vbuf[32];
    httpd_resp_set_type(req, "text/html; charset=utf-8");
    const char *p = tpl;
    while (*p) {
        const char *s = strstr(p, "{{");
        const char *e = s ? strstr(s + 2, "}}") : NULL;
        if (!s || !e) {
            if (httpd_resp_sendstr_chunk(req, p) != ESP_OK) {
                return ESP_FAIL;
            }
            break;
        }
        if (s > p && httpd_resp_send_chunk(req, p, s - p) != ESP_OK) {
            return ESP_FAIL;
        }
        const char *v = tpl_var(s + 2, (size_t)(e - s - 2), vbuf, sizeof vbuf);
        if (*v && httpd_resp_sendstr_chunk(req, v) != ESP_OK) {
            return ESP_FAIL;
        }
        p = e + 2;
    }
    return httpd_resp_send_chunk(req, NULL, 0);
}

static esp_err_t send_page(httpd_req_t *req, const char *status, const char *title)
{
    if (status) {
        httpd_resp_set_status(req, status);
    }
    s_title = title;
    return send_tpl(req, page_html);
}

static esp_err_t send_text(httpd_req_t *req, const char *status, const char *text)
{
    if (status) {
        httpd_resp_set_status(req, status);
    }
    httpd_resp_set_type(req, "text/plain; charset=utf-8");
    return httpd_resp_sendstr(req, text);
}

/* Reads a small urlencoded body into buf; false (and 413/400 sent) on error. */
static bool read_body(httpd_req_t *req, char *buf, size_t cap)
{
    if (req->content_len >= cap) {
        send_text(req, "413 Content Too Large", "request body too large\n");
        return false;
    }
    size_t got = 0;
    while (got < req->content_len) {
        int r = httpd_req_recv(req, buf + got, req->content_len - got);
        if (r == HTTPD_SOCK_ERR_TIMEOUT) {
            continue;
        }
        if (r <= 0) {
            return false;
        }
        got += (size_t)r;
    }
    buf[got] = '\0';
    return true;
}

static bool form_value(const char *form, const char *key, char *val, size_t cap)
{
    if (httpd_query_key_value(form, key, val, cap) != ESP_OK) {
        return false;
    }
    url_decode(val);
    return true;
}

/* ---------------- WEB-01/02/03 ---------------- */

static esp_err_t h_index(httpd_req_t *req)
{
    char role[16];
    size_t n = sizeof role;
    if (httpd_req_get_cookie_val(req, "role", role, &n) != ESP_OK) {
        httpd_resp_set_hdr(req, "Set-Cookie", "role=guest; Path=/");
    }
    return send_tpl(req, index_html);
}

static esp_err_t h_robots(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/plain");
    return httpd_resp_sendstr(req, robots_txt);
}

static esp_err_t h_staging(httpd_req_t *req)
{
    char body[13], text[160];
    ctf_flag_body("WEB-02", body);
    snprintf(text, sizeof text,
             "staging notes\n"
             "release token part 2/2 = %s\n"
             "flag = ESP{ part 1 (first 6 hex, see / source) followed by part 2 (last 6 hex) }\n",
             body + 6);
    return send_text(req, NULL, text);
}

static esp_err_t h_admin(httpd_req_t *req)
{
    char role[16];
    size_t n = sizeof role;
    if (httpd_req_get_cookie_val(req, "role", role, &n) != ESP_OK) {
        strcpy(role, "nobody");
    }
    if (strcmp(role, "admin") == 0) {
        char flag[18];
        ctf_flag("WEB-03", flag);
        snprintf(s_body, sizeof s_body, "<p>Welcome back, admin. WEB-03: <code>%s</code></p>", flag);
        return send_page(req, NULL, "Admin panel");
    }
    strcpy(s_body, "<p>Admins only. You are: <code>");
    html_cat(s_body, sizeof s_body, role, strlen(role));
    strncat(s_body, "</code></p>", sizeof s_body - strlen(s_body) - 1);
    return send_page(req, "403 Forbidden", "Admin panel");
}

/* ---------------- WEB-04 ---------------- */

static esp_err_t h_docs(httpd_req_t *req)
{
    return send_tpl(req, docs_html);
}

static esp_err_t h_secret(httpd_req_t *req)
{
    char ua[48] = "", key[40] = "";
    httpd_req_get_hdr_value_str(req, "User-Agent", ua, sizeof ua);
    httpd_req_get_hdr_value_str(req, "X-CTF-Key", key, sizeof key);
    if (strcmp(ua, "ESP32-CTF-Agent") != 0 || strcasecmp(key, g_web.api_key) != 0) {
        return send_text(req, "403 Forbidden", "403 Forbidden\n");
    }
    char flag[18], json[48];
    ctf_flag("WEB-04", flag);
    snprintf(json, sizeof json, "{\"flag\":\"%s\"}\n", flag);
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_sendstr(req, json);
}

/* ---------------- WEB-05: HS256 JWT ---------------- */

static const char B64U[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

static size_t b64url_enc(const uint8_t *in, size_t n, char *out, size_t cap)
{
    size_t o = 0;
    for (size_t i = 0; i < n; i += 3) {
        uint32_t v = (uint32_t)in[i] << 16;
        size_t k = n - i;
        if (k > 1) {
            v |= (uint32_t)in[i + 1] << 8;
        }
        if (k > 2) {
            v |= in[i + 2];
        }
        size_t chars = k >= 3 ? 4 : k + 1;
        for (size_t c = 0; c < chars && o + 1 < cap; c++) {
            out[o++] = B64U[(v >> (18 - 6 * c)) & 63];
        }
    }
    out[o] = '\0';
    return o;
}

/* Strict base64url decode (trailing '=' tolerated); returns length or -1. */
static int b64url_dec(const char *in, size_t n, uint8_t *out, size_t cap)
{
    while (n > 0 && in[n - 1] == '=') {
        n--;
    }
    if (n % 4 == 1) {
        return -1;
    }
    uint32_t acc = 0;
    int bits = 0;
    size_t o = 0;
    for (size_t i = 0; i < n; i++) {
        const char *p = memchr(B64U, in[i], 64);
        if (!p) {
            return -1;
        }
        acc = (acc << 6) | (uint32_t)(p - B64U);
        bits += 6;
        if (bits >= 8) {
            bits -= 8;
            if (o >= cap) {
                return -1;
            }
            out[o++] = (uint8_t)(acc >> bits);
        }
    }
    return (int)o;
}

/* Extracts the string value of "key" from a flat JSON object. */
static bool json_str(const char *json, const char *key, char *val, size_t cap)
{
    char pat[24];
    snprintf(pat, sizeof pat, "\"%s\"", key);
    const char *p = strstr(json, pat);
    if (!p) {
        return false;
    }
    p += strlen(pat);
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') {
        p++;
    }
    if (*p++ != ':') {
        return false;
    }
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r') {
        p++;
    }
    if (*p++ != '"') {
        return false;
    }
    size_t o = 0;
    while (*p && *p != '"') {
        if (o + 1 >= cap) {
            return false;
        }
        val[o++] = *p++;
    }
    if (*p != '"') {
        return false;
    }
    val[o] = '\0';
    return true;
}

static void jwt_sign(const char *signing_input, size_t n, uint8_t mac[CTF_SHA256_LEN])
{
    ctf_hmac_sha256(g_web.jwt_secret, strlen(g_web.jwt_secret), signing_input, n, mac);
}

static void jwt_issue(const char *payload, char *out, size_t cap)
{
    static const char HDR[] = "{\"alg\":\"HS256\",\"typ\":\"JWT\"}";
    size_t o = b64url_enc((const uint8_t *)HDR, sizeof HDR - 1, out, cap);
    out[o++] = '.';
    o += b64url_enc((const uint8_t *)payload, strlen(payload), out + o, cap - o);
    uint8_t mac[CTF_SHA256_LEN];
    jwt_sign(out, o, mac);
    out[o++] = '.';
    b64url_enc(mac, sizeof mac, out + o, cap - o);
}

typedef enum { JWT_OK, JWT_MALFORMED, JWT_BAD_ALG, JWT_BAD_SIG } jwt_res_t;

/* Verifies an HS256 token; on JWT_OK, role (may be "") is filled. */
static jwt_res_t jwt_verify(const char *tok, char *role, size_t role_cap)
{
    size_t n = strlen(tok);
    const char *d1 = memchr(tok, '.', n);
    const char *d2 = d1 ? memchr(d1 + 1, '.', n - (size_t)(d1 + 1 - tok)) : NULL;
    if (!d1 || !d2 || memchr(d2 + 1, '.', n - (size_t)(d2 + 1 - tok))) {
        return JWT_MALFORMED;
    }
    char json[257];
    int l = b64url_dec(tok, (size_t)(d1 - tok), (uint8_t *)json, sizeof json - 1);
    if (l < 0) {
        return JWT_MALFORMED;
    }
    json[l] = '\0';
    char alg[16];
    if (!json_str(json, "alg", alg, sizeof alg)) {
        return JWT_MALFORMED;
    }
    if (strcmp(alg, "HS256") != 0) { /* rejects "none" and everything else */
        return JWT_BAD_ALG;
    }
    uint8_t sig[CTF_SHA256_LEN + 4], mac[CTF_SHA256_LEN];
    l = b64url_dec(d2 + 1, n - (size_t)(d2 + 1 - tok), sig, sizeof sig);
    if (l != CTF_SHA256_LEN) {
        return JWT_BAD_SIG;
    }
    jwt_sign(tok, (size_t)(d2 - tok), mac);
    uint8_t diff = 0;
    for (int i = 0; i < CTF_SHA256_LEN; i++) {
        diff |= (uint8_t)(sig[i] ^ mac[i]);
    }
    if (diff) {
        return JWT_BAD_SIG;
    }
    l = b64url_dec(d1 + 1, (size_t)(d2 - d1 - 1), (uint8_t *)json, sizeof json - 1);
    if (l < 0) {
        return JWT_MALFORMED;
    }
    json[l] = '\0';
    if (!json_str(json, "role", role, role_cap)) {
        role[0] = '\0';
    }
    return JWT_OK;
}

static esp_err_t h_login_get(httpd_req_t *req)
{
    s_body[0] = '\0';
    return send_tpl(req, login_html);
}

static esp_err_t h_login_post(httpd_req_t *req)
{
    char form[256], user[32] = "";
    if (!read_body(req, form, sizeof form)) {
        return ESP_FAIL; /* 413 already sent, or the socket died */
    }
    form_value(form, "user", user, sizeof user);
    if (strcmp(user, "guest") != 0) {
        snprintf(s_body, sizeof s_body,
                 "<p><b>Login failed.</b> Only the guest account is open on this terminal.</p>");
        httpd_resp_set_status(req, "401 Unauthorized");
        return send_tpl(req, login_html);
    }
    char tok[256];
    jwt_issue("{\"sub\":\"guest\",\"role\":\"user\"}", tok, sizeof tok);
    snprintf(s_cookie, sizeof s_cookie, "session=%s; Path=/", tok);
    httpd_resp_set_hdr(req, "Set-Cookie", s_cookie);
    snprintf(s_body, sizeof s_body,
             "<p>Logged in as <b>guest</b> (role: user). Your session token:</p>"
             "<p><code style=\"word-break:break-all\">%s</code></p>", tok);
    return send_tpl(req, login_html);
}

static esp_err_t h_vault(httpd_req_t *req)
{
    char tok[400] = "";
    char auth[420];
    if (httpd_req_get_hdr_value_str(req, "Authorization", auth, sizeof auth) == ESP_OK &&
        strncasecmp(auth, "Bearer ", 7) == 0) {
        strlcpy(tok, auth + 7, sizeof tok);
    } else {
        size_t n = sizeof tok;
        if (httpd_req_get_cookie_val(req, "session", tok, &n) != ESP_OK) {
            tok[0] = '\0';
        }
    }
    if (!tok[0]) {
        strcpy(s_body, "<p>No session. <a href=\"/login\">Log in</a> first.</p>");
        return send_page(req, "401 Unauthorized", "Vault");
    }
    char role[24];
    switch (jwt_verify(tok, role, sizeof role)) {
    case JWT_MALFORMED:
        strcpy(s_body, "<p>Malformed token.</p>");
        return send_page(req, "401 Unauthorized", "Vault");
    case JWT_BAD_ALG:
        strcpy(s_body, "<p>Unsupported token algorithm.</p>");
        return send_page(req, "401 Unauthorized", "Vault");
    case JWT_BAD_SIG:
        strcpy(s_body, "<p>Invalid token signature.</p>");
        return send_page(req, "401 Unauthorized", "Vault");
    case JWT_OK:
        break;
    }
    if (strcmp(role, "admin") != 0) {
        strcpy(s_body, "<p>The vault is for role <code>admin</code>. Your role: <code>");
        html_cat(s_body, sizeof s_body, role, strlen(role));
        strncat(s_body, "</code></p>", sizeof s_body - strlen(s_body) - 1);
        return send_page(req, "403 Forbidden", "Vault");
    }
    char flag[18];
    ctf_flag("WEB-05", flag);
    snprintf(s_body, sizeof s_body, "<p>Vault open. WEB-05: <code>%s</code></p>", flag);
    return send_page(req, NULL, "Vault");
}

static esp_err_t h_wordlist(httpd_req_t *req)
{
    char chunk[512];
    size_t o = 0;
    httpd_resp_set_type(req, "text/plain");
    for (unsigned i = 0; i < WEB_WORDS; i++) {
        char w[WEB_WORD_MAX];
        web_word(i, w);
        o += (size_t)snprintf(chunk + o, sizeof chunk - o, "%s\n", w);
        if (o + WEB_WORD_MAX + 1 >= sizeof chunk || i + 1 == WEB_WORDS) {
            if (httpd_resp_send_chunk(req, chunk, o) != ESP_OK) {
                return ESP_FAIL;
            }
            o = 0;
        }
    }
    return httpd_resp_send_chunk(req, NULL, 0);
}

/* ---------------- WEB-06: confined path traversal ---------------- */

/* Normalises an absolute path ('.', '..', '//'); false if it climbs above '/'
 * or is not inside /storage/. */
static bool confine_storage(const char *in, char *out, size_t cap)
{
    const char *comp[16];
    size_t clen[16];
    int depth = 0;
    const char *p = in;
    while (*p) {
        while (*p == '/') {
            p++;
        }
        const char *s = p;
        while (*p && *p != '/') {
            p++;
        }
        size_t l = (size_t)(p - s);
        if (l == 0 || (l == 1 && s[0] == '.')) {
            continue;
        }
        if (l == 2 && s[0] == '.' && s[1] == '.') {
            if (depth == 0) {
                return false;
            }
            depth--;
            continue;
        }
        if (depth == 16) {
            return false;
        }
        comp[depth] = s;
        clen[depth] = l;
        depth++;
    }
    if (depth < 2 || clen[0] != 7 || memcmp(comp[0], "storage", 7) != 0) {
        return false;
    }
    size_t o = 0;
    for (int i = 0; i < depth; i++) {
        if (o + 1 + clen[i] + 1 > cap) {
            return false;
        }
        out[o++] = '/';
        memcpy(out + o, comp[i], clen[i]);
        o += clen[i];
    }
    out[o] = '\0';
    return true;
}

static esp_err_t h_diag(httpd_req_t *req)
{
    char q[192], file[128], path[160], norm[160];
    s_body[0] = '\0';
    if (httpd_req_get_url_query_str(req, q, sizeof q) != ESP_OK ||
        !form_value(q, "file", file, sizeof file) || !file[0]) {
        return send_tpl(req, diag_html);
    }
    snprintf(path, sizeof path, "/storage/diag/%s", file); /* naive on purpose */
    if (!confine_storage(path, norm, sizeof norm)) {
        strcpy(s_body, "<p><b>access denied:</b> outside the diagnostics storage</p>");
        httpd_resp_set_status(req, "403 Forbidden");
        return send_tpl(req, diag_html);
    }
    FILE *f = fopen(norm, "rb");
    if (!f) {
        strcpy(s_body, "<p><b>no such file:</b> <code>");
        html_cat(s_body, sizeof s_body, file, strlen(file));
        strncat(s_body, "</code></p>", sizeof s_body - strlen(s_body) - 1);
        httpd_resp_set_status(req, "404 Not Found");
        return send_tpl(req, diag_html);
    }
    char data[1536];
    size_t n = fread(data, 1, sizeof data, f);
    fclose(f);
    strcpy(s_body, "<h2>");
    html_cat(s_body, sizeof s_body, file, strlen(file));
    strncat(s_body, "</h2><pre>", sizeof s_body - strlen(s_body) - 1);
    html_cat(s_body, sizeof s_body - 8, data, n);
    strncat(s_body, "</pre>", sizeof s_body - strlen(s_body) - 1);
    return send_tpl(req, diag_html);
}

/* ---------------- WEB-07: WebSocket ---------------- */

static esp_err_t h_ws(httpd_req_t *req)
{
    if (req->method == HTTP_GET) {
        ESP_LOGI(TAG, "ws client connected (fd %d)", httpd_req_to_sockfd(req));
        return ESP_OK;
    }
    uint8_t buf[128];
    httpd_ws_frame_t f = {0};
    esp_err_t err = httpd_ws_recv_frame(req, &f, 0);
    if (err != ESP_OK) {
        return err;
    }
    if (f.len > sizeof buf) {
        return ESP_FAIL; /* closes the connection */
    }
    if (f.len) {
        f.payload = buf;
        err = httpd_ws_recv_frame(req, &f, f.len);
    }
    return err; /* client messages are ignored */
}

static void ws_broadcast(void *arg)
{
    static uint32_t seq;
    bool with_flag = (uintptr_t)arg != 0;
    size_t nfds = MAX_SOCKETS;
    int fds[MAX_SOCKETS];
    if (httpd_get_client_list(s_srv, &nfds, fds) != ESP_OK) {
        return;
    }
    char text[96];
    uint32_t r = esp_random();
    snprintf(text, sizeof text,
             "{\"seq\":%lu,\"sensor\":\"t%u\",\"value\":%u.%02u,\"pad\":\"%08lx\"}",
             (unsigned long)++seq, (unsigned)(r & 7), (unsigned)(18 + (r >> 8) % 12),
             (unsigned)((r >> 16) % 100), (unsigned long)esp_random());
    char flag[18];
    ctf_flag("WEB-07", flag);
    httpd_ws_frame_t noise = {.final = true, .type = HTTPD_WS_TYPE_TEXT,
                              .payload = (uint8_t *)text, .len = strlen(text)};
    httpd_ws_frame_t bin = {.final = true, .type = HTTPD_WS_TYPE_BINARY,
                            .payload = (uint8_t *)flag, .len = CTF_FLAG_LEN};
    for (size_t i = 0; i < nfds; i++) {
        if (httpd_ws_get_fd_info(s_srv, fds[i]) != HTTPD_WS_CLIENT_WEBSOCKET) {
            continue;
        }
        httpd_ws_send_frame_async(s_srv, fds[i], &noise);
        if (with_flag) {
            httpd_ws_send_frame_async(s_srv, fds[i], &bin);
        }
    }
}

static void ws_ticker(void *arg)
{
    (void)arg;
    for (uint32_t n = 1;; n++) {
        vTaskDelay(pdMS_TO_TICKS(1000));
        httpd_queue_work(s_srv, ws_broadcast, (void *)(uintptr_t)(n % 30 == 0));
    }
}

/* ---------------- /score, /submit ---------------- */

static esp_err_t h_score(httpd_req_t *req)
{
    static const char *const TRACKS[] = {"BLE", "BTC", "WEB", "SER", "HW", "RE", "CRY"};
    int solved[7] = {0}, total[7] = {0};
    for (size_t i = 0; i < ctf_count(); i++) {
        const ctf_challenge_t *c = ctf_get(i);
        for (int t = 0; t < 7; t++) {
            if (strcmp(c->track, TRACKS[t]) == 0) {
                total[t]++;
                solved[t] += ctf_is_solved(c->id) ? 1 : 0;
            }
        }
    }
    size_t o = (size_t)snprintf(s_body, sizeof s_body,
                                "<p>Score: <b>%d / %d</b> (%d without optional-kit challenges)</p>"
                                "<table><tr><th>Track</th><th>Solved</th></tr>",
                                ctf_score(), ctf_max_score(true), ctf_max_score(false));
    for (int t = 0; t < 7 && o < sizeof s_body; t++) {
        o += (size_t)snprintf(s_body + o, sizeof s_body - o,
                              "<tr><td>%s</td><td>%d / %d</td></tr>", TRACKS[t], solved[t], total[t]);
    }
    if (o < sizeof s_body) {
        snprintf(s_body + o, sizeof s_body - o, "</table><p><a href=\"/submit\">submit a flag</a></p>");
    }
    return send_page(req, NULL, "Scoreboard");
}

static esp_err_t h_submit_get(httpd_req_t *req)
{
    s_body[0] = '\0';
    return send_tpl(req, submit_html);
}

static esp_err_t h_submit_post(httpd_req_t *req)
{
    char form[192], flag[64] = "";
    if (!read_body(req, form, sizeof form)) {
        return ESP_FAIL; /* 413 already sent, or the socket died */
    }
    form_value(form, "flag", flag, sizeof flag);
    const ctf_challenge_t *c = NULL;
    switch (ctf_submit(flag, &c)) {
    case CTF_SUBMIT_NEW:
        snprintf(s_body, sizeof s_body, "<p class=\"result\">Correct! %s %s +%d</p>", c->id, c->name,
                 ctf_points(c->id) - (ctf_hint_used(c->id) ? ctf_points(c->id) / 4 : 0));
        break;
    case CTF_SUBMIT_ALREADY:
        snprintf(s_body, sizeof s_body, "<p class=\"result\">Already solved: %s %s</p>", c->id, c->name);
        break;
    default:
        snprintf(s_body, sizeof s_body, "<p class=\"result\">Wrong flag.</p>");
        break;
    }
    return send_tpl(req, submit_html);
}

static esp_err_t h_404(httpd_req_t *req, httpd_err_code_t err)
{
    (void)err;
    send_text(req, "404 Not Found", "404 Not Found\n");
    return ESP_OK;
}

bool web_http_start(void)
{
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.server_port = 80;
    cfg.ctrl_port = WEB_MAIN_CTRL;
    cfg.stack_size = 6144;
    cfg.max_open_sockets = MAX_SOCKETS;
    cfg.max_uri_handlers = 20;
    cfg.lru_purge_enable = true;
    cfg.uri_match_fn = httpd_uri_match_wildcard;
    esp_err_t err = httpd_start(&s_srv, &cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "httpd_start: %s", esp_err_to_name(err));
        return false;
    }
    static const httpd_uri_t uris[] = {
        {.uri = "/", .method = HTTP_GET, .handler = h_index},
        {.uri = "/robots.txt", .method = HTTP_GET, .handler = h_robots},
        {.uri = "/staging*", .method = HTTP_GET, .handler = h_staging},
        {.uri = "/admin", .method = HTTP_GET, .handler = h_admin},
        {.uri = "/api/docs", .method = HTTP_GET, .handler = h_docs},
        {.uri = "/api/secret", .method = HTTP_GET, .handler = h_secret},
        {.uri = "/login", .method = HTTP_GET, .handler = h_login_get},
        {.uri = "/login", .method = HTTP_POST, .handler = h_login_post},
        {.uri = "/vault", .method = HTTP_GET, .handler = h_vault},
        {.uri = "/wordlist.txt", .method = HTTP_GET, .handler = h_wordlist},
        {.uri = "/diag", .method = HTTP_GET, .handler = h_diag},
        {.uri = "/ws", .method = HTTP_GET, .handler = h_ws, .is_websocket = true},
        {.uri = "/score", .method = HTTP_GET, .handler = h_score},
        {.uri = "/submit", .method = HTTP_GET, .handler = h_submit_get},
        {.uri = "/submit", .method = HTTP_POST, .handler = h_submit_post},
    };
    for (size_t i = 0; i < sizeof uris / sizeof uris[0]; i++) {
        ESP_ERROR_CHECK(httpd_register_uri_handler(s_srv, &uris[i]));
    }
    httpd_register_err_handler(s_srv, HTTPD_404_NOT_FOUND, h_404);
    xTaskCreate(ws_ticker, "web_ws", 2560, NULL, 4, NULL);
    return true;
}
