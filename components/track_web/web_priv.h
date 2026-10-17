#pragma once
/* track_web internals: per-board derived values shared by the Wi-Fi, HTTP and
 * network-extras parts (SPEC "Web"). All values come from ctf_derive at boot. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define WEB_WORDS        1000   /* WEB-05 wordlist size */
#define WEB_WORD_MAX     8      /* longest word + NUL */
#define WEB_KNOCK_N      3      /* WEB-09 knock ports */
#define WEB_DOOR_PORT    31337  /* WEB-09 TCP door */
#define WEB_MAIN_CTRL    32768  /* httpd control ports (UDP on 127.0.0.1) */
#define WEB_BEACON_CTRL  32769

typedef struct {
    char ssid[11];                 /* "ctf-" + 6 lowercase */
    char pass[13];                 /* 12 chars */
    char api_key[17];              /* WEB-04 X-CTF-Key, 16 lowercase hex */
    char jwt_secret[WEB_WORD_MAX]; /* WEB-05 HS256 secret, one wordlist entry */
    char shard[3];                 /* CRY-01 shard 4 */
    uint16_t knock[WEB_KNOCK_N];   /* WEB-09 UDP ports, in order */
    uint16_t beacon_port;          /* WEB-08 second HTTP server */
} web_secrets_t;

extern web_secrets_t g_web;

#define WEB_SECRET_FILE  "/storage/secret/flag.txt" /* WEB-06, stored masked */

/* WEB-06: XORs buf with the per-board mask of the secret file (mask/unmask). */
void web_secret_mask(uint8_t *buf, size_t n);

/* WEB-05 wordlist entry i (0..WEB_WORDS-1), same on every board. */
void web_word(unsigned i, char out[WEB_WORD_MAX]);

/* Main HTTP server on port 80 (WEB-01..07, /score, /submit) + WS ticker. */
bool web_http_start(void);
/* WEB-08: mDNS hostname + _ctf._tcp service + beacon HTTP server. */
bool web_mdns_start(void);
/* WEB-09: UDP knock listener task + TCP door. */
bool web_knock_start(void);
