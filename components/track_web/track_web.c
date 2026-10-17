/* track_web: WEB-01..09 (SPEC "Web", net mode only).
 * This file: per-board derived values, SPIFFS files for WEB-06, the hidden
 * WPA2 SoftAP (WEB-01) with optional dev station (CONFIG_CTF_WEB_DEV_STA),
 * the `wifi` console clue, and start-up of the HTTP / mDNS / knock services
 * (web_http.c, web_net.c). Everything runs on the board's own network. */
#include "track_web.h"
#include "web_priv.h"

#include <stdio.h>
#include <string.h>
#include "ctf_core.h"
#include "esp_console.h"
#include "esp_event.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_netif.h"
#include "esp_spiffs.h"
#include "esp_wifi.h"
#include "sdkconfig.h"

static const char *TAG = "track_web";

web_secrets_t g_web;

#if CONFIG_CTF_WEB_DEV_STA
static esp_netif_t *s_sta_netif;
#endif

/* ---- WEB-05 wordlist: 1000 two-syllable words from a syllable table ---- */

static const char CONS[] = "bdfghjklmnprstvz"; /* 16 */
static const char VOWS[] = "aeiou";            /* 5  -> 80 CV syllables */
static const char *const ENDS[] = {"", "n", "r", "s", "l", "x", "", "m"};

void web_word(unsigned i, char out[WEB_WORD_MAX])
{
    /* 37 is coprime with 80*80, so i < 1000 picks distinct (a, b) pairs and
     * every word is unique (each syllable is exactly 2 letters). */
    unsigned j = (i * 37u + 11u) % 6400u;
    unsigned a = j / 80u, b = j % 80u;
    snprintf(out, WEB_WORD_MAX, "%c%c%c%c%s", CONS[a / 5], VOWS[a % 5], CONS[b / 5],
             VOWS[b % 5], ENDS[(j / 7u + i) % 8u]);
}

/* ---- per-board values ---- */

static void derive_secrets(void)
{
    uint8_t b[16];
    memset(&g_web, 0, sizeof g_web);

    ctf_derive("WEB-01:ssid", b, 6);
    memcpy(g_web.ssid, "ctf-", 4);
    for (int i = 0; i < 6; i++) {
        g_web.ssid[4 + i] = (char)('a' + b[i] % 26);
    }

    static const char PW[] = "abcdefghjkmnpqrstuvwxyz23456789"; /* no 0/o/1/l/i */
    ctf_derive("WEB-01:pass", b, 12);
    for (int i = 0; i < 12; i++) {
        g_web.pass[i] = PW[b[i] % (sizeof PW - 1)];
    }

    ctf_derive("WEB-04:key", b, 8);
    for (int i = 0; i < 8; i++) {
        snprintf(&g_web.api_key[2 * i], 3, "%02x", b[i]);
    }

    web_word(ctf_derive_u32("WEB-05:secret") % WEB_WORDS, g_web.jwt_secret);

    ctf_derive("CRY-01:shard4", b, 2);
    g_web.shard[0] = (char)('A' + b[0] % 26);
    g_web.shard[1] = (char)('A' + b[1] % 26);

    g_web.beacon_port = (uint16_t)(8000 + ctf_derive_u32("WEB-08:port") % 1000);

    ctf_derive("WEB-09:ports", b, 2 * WEB_KNOCK_N);
    for (int i = 0; i < WEB_KNOCK_N; i++) {
        unsigned v = ((unsigned)b[2 * i] << 8 | b[2 * i + 1]) % 20001u; /* 20000..40000 */
        for (;;) {
            unsigned p = 20000u + v;
            bool clash = p == WEB_DOOR_PORT || p == WEB_MAIN_CTRL || p == WEB_BEACON_CTRL;
            for (int k = 0; k < i; k++) {
                clash = clash || p == g_web.knock[k];
            }
            if (!clash) {
                g_web.knock[i] = (uint16_t)p;
                break;
            }
            v = (v + 1u) % 20001u;
        }
    }
}

/* ---- WEB-06 files on the shared SPIFFS mount (SPEC "Cross-track rules") ---- */

static bool mount_storage(void)
{
    if (esp_spiffs_mounted("storage")) {
        return true;
    }
    const esp_vfs_spiffs_conf_t conf = {
        .base_path = "/storage",
        .partition_label = "storage",
        .max_files = 8,
        .format_if_mount_failed = true,
    };
    esp_err_t err = esp_vfs_spiffs_register(&conf);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "SPIFFS mount failed: %s", esp_err_to_name(err));
        return false;
    }
    return true;
}

/* Writes path only when its content differs (saves flash wear across boots). */
static void write_if_changed(const char *path, const char *content)
{
    size_t n = strlen(content);
    char buf[512];
    FILE *f = fopen(path, "rb");
    if (f) {
        size_t got = fread(buf, 1, sizeof buf, f);
        fclose(f);
        if (got == n && memcmp(buf, content, n) == 0) {
            return;
        }
    }
    f = fopen(path, "wb");
    if (!f) {
        ESP_LOGE(TAG, "cannot write %s", path);
        return;
    }
    fwrite(content, 1, n, f);
    fclose(f);
}

static void provision_files(void)
{
    if (!mount_storage()) {
        return;
    }
    write_if_changed("/storage/diag/boot.log",
                     "[    0.412] fs: mounted /storage (spiffs)\n"
                     "[    0.418] fs: diag logs -> /storage/diag/\n"
                     "[    0.421] fs: secret/flag.txt provisioned (restricted, not listed)\n"
                     "[    0.503] wifi: softap up, ssid hidden, wpa2-psk\n"
                     "[    0.611] httpd: listening on :80\n"
                     "[    0.615] diag: viewer serves files from diag/ only\n");
    write_if_changed("/storage/diag/net.log",
                     "dhcps: pool 192.168.4.2 - 192.168.4.5, lease 120 min\n"
                     "dhcps: offer 192.168.4.2 -> 02:00:00:00:00:01\n"
                     "httpd: GET / 200\n"
                     "httpd: GET /favicon.ico 404\n");
    write_if_changed("/storage/diag/ping.log",
                     "PING 192.168.4.1 (192.168.4.1): 56 data bytes\n"
                     "64 bytes from 192.168.4.1: icmp_seq=0 ttl=255 time=1.9 ms\n"
                     "64 bytes from 192.168.4.1: icmp_seq=1 ttl=255 time=2.3 ms\n"
                     "64 bytes from 192.168.4.1: icmp_seq=2 ttl=255 time=2.0 ms\n"
                     "--- 192.168.4.1 ping statistics ---\n"
                     "3 packets transmitted, 3 received, 0% packet loss\n");
    /* WEB-06 target, written on purpose (SPEC "Web": traversal reads
     * /storage/secret/flag.txt). Rewritten if the board changes. */
    char flag[18], line[40];
    ctf_flag("WEB-06", flag);
    snprintf(line, sizeof line, "WEB-06 %s\n", flag);
    write_if_changed("/storage/secret/flag.txt", line);
}

/* ---- Wi-Fi (WEB-01) ---- */

static void wifi_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    (void)arg;
    if (base == WIFI_EVENT && id == WIFI_EVENT_AP_STACONNECTED) {
        const wifi_event_ap_staconnected_t *e = data;
        ESP_LOGI(TAG, "station joined: " MACSTR, MAC2STR(e->mac));
    }
#if CONFIG_CTF_WEB_DEV_STA
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        const ip_event_got_ip_t *e = data;
        printf("web dev sta ip: " IPSTR "\n", IP2STR(&e->ip_info.ip));
        ESP_LOGI(TAG, "free heap (8-bit) with STA up: %u bytes",
                 (unsigned)heap_caps_get_free_size(MALLOC_CAP_8BIT));
    }
#endif
}

static bool wifi_start(void)
{
    esp_err_t err = esp_netif_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_netif_init: %s", esp_err_to_name(err));
        return false;
    }
    err = esp_event_loop_create_default();
    if (err != ESP_OK && err != ESP_ERR_INVALID_STATE) {
        ESP_LOGE(TAG, "event loop: %s", esp_err_to_name(err));
        return false;
    }
    esp_netif_create_default_wifi_ap();
#if CONFIG_CTF_WEB_DEV_STA
    s_sta_netif = esp_netif_create_default_wifi_sta();
#endif

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    err = esp_wifi_init(&cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_wifi_init: %s", esp_err_to_name(err));
        return false;
    }
    esp_wifi_set_storage(WIFI_STORAGE_RAM);
    esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event, NULL);
#if CONFIG_CTF_WEB_DEV_STA
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event, NULL);
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_APSTA));
#else
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
#endif

    wifi_config_t ap = {0};
    memcpy(ap.ap.ssid, g_web.ssid, strlen(g_web.ssid));
    ap.ap.ssid_len = (uint8_t)strlen(g_web.ssid);
    memcpy(ap.ap.password, g_web.pass, strlen(g_web.pass));
    ap.ap.channel = 1;
    ap.ap.authmode = WIFI_AUTH_WPA2_PSK;
    ap.ap.ssid_hidden = 1;
    ap.ap.max_connection = 4;
    ap.ap.beacon_interval = 100;
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &ap));

#if CONFIG_CTF_WEB_DEV_STA
    wifi_config_t sta = {0};
    strncpy((char *)sta.sta.ssid, CONFIG_CTF_WEB_DEV_STA_SSID, sizeof sta.sta.ssid);
    strncpy((char *)sta.sta.password, CONFIG_CTF_WEB_DEV_STA_PASS, sizeof sta.sta.password);
    sta.sta.scan_method = WIFI_ALL_CHANNEL_SCAN;
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &sta));
    ESP_LOGW(TAG, "DEV STATION MODE: joining test network (APSTA); not for release");
#endif
    return true;
}

/* ---- console: `wifi` (WEB-01 clue + WEB-09 knock hint) ---- */

static void base32(const char *in, char *out, size_t outsz)
{
    static const char A[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
    size_t n = strlen(in), o = 0;
    uint32_t acc = 0;
    int bits = 0;
    for (size_t i = 0; i < n; i++) {
        acc = (acc << 8) | (uint8_t)in[i];
        bits += 8;
        while (bits >= 5 && o + 1 < outsz) {
            out[o++] = A[(acc >> (bits - 5)) & 31];
            bits -= 5;
        }
    }
    if (bits > 0 && o + 1 < outsz) {
        out[o++] = A[(acc << (5 - bits)) & 31];
    }
    while (o % 8 && o + 1 < outsz) {
        out[o++] = '=';
    }
    out[o] = '\0';
}

static int cmd_wifi(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    char b32[40];
    base32(g_web.ssid, b32, sizeof b32);
    printf("Board network: hidden SSID, WPA2-PSK, board at 192.168.4.1\n"
           "  ssid (base32): %s\n"
           "  password:      %s\n"
           "  knock, knock, knock: %04x . %04x . %04x  (base 16, udp, this order)"
           " -> door %04x\n",
           b32, g_web.pass, g_web.knock[0], g_web.knock[1], g_web.knock[2],
           WEB_DOOR_PORT);
#if CONFIG_CTF_WEB_DEV_STA
    wifi_config_t ap = {0};
    esp_netif_ip_info_t ip = {0};
    esp_wifi_get_config(WIFI_IF_AP, &ap);
    esp_netif_get_ip_info(s_sta_netif, &ip);
    printf("  (dev) active AP ssid: %.*s, sta ip: " IPSTR "\n", ap.ap.ssid_len,
           (const char *)ap.ap.ssid, IP2STR(&ip.ip));
#endif
    return 0;
}

void track_web_start(void)
{
    derive_secrets();
    provision_files();

    const esp_console_cmd_t cmd = {
        .command = "wifi",
        .help = "Show how to reach the board's hidden network (net mode)",
        .func = cmd_wifi,
    };
    ESP_ERROR_CHECK(esp_console_cmd_register(&cmd));

    if (!wifi_start()) {
        return;
    }
    web_mdns_start(); /* before esp_wifi_start so mDNS sees the netif events */
    ESP_ERROR_CHECK(esp_wifi_start());
#if CONFIG_CTF_WEB_DEV_STA
    esp_wifi_set_ps(WIFI_PS_NONE);
#endif
    web_http_start();
    web_knock_start();
    ESP_LOGI(TAG, "net mode up: SoftAP (hidden), HTTP :80, mDNS, knock listener");
    ESP_LOGI(TAG, "free heap (8-bit) after Wi-Fi + HTTP: %u bytes (min %u)",
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_8BIT),
             (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_8BIT));
}
