/* track_btc: BT Classic track BTC-01..03 and CRY-01 shard 3 (SPEC "BT Classic",
 * "Cross-track rules"). Runs on top of track_ble's BTDM controller + Bluedroid.
 *
 * - GAP: connectable + general discoverable, SSP Just Works (IO cap none).
 * - BTC-03: the BR/EDR name, Class of Device and EIR together carry the flag
 *   body (12 hex chars b0..b11):
 *     name      "ESP32-CTF-XXXX:" + b0..b5  (XXXX = last 2 MAC bytes, as BLE)
 *     CoD       major Uncategorized, service Information, minor = nibble b6
 *     EIR       manufacturer data, company 0xFFFF, 3 bytes = 0x0 b7 b8 b9 b10 b11
 *               (leading zero nibble: the CoD nibble's slot)
 *   The BLE advertised name stays "ESP32-CTF-XXXX" (Bluedroid keeps BLE and
 *   BR/EDR names separate), so BLE solvers' prefix match is unaffected.
 * - BTC-01: SPP server "CTF Console" (callback mode); the connect banner holds
 *   the flag, the BTC-02 clue and CRY-01 shard 3, then a `spp> ` prompt.
 * - BTC-02: small line shell; `diag` (not in help) prints the flag. */
#include "track_btc.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "esp_bt_device.h"
#include "esp_gap_bt_api.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_spp_api.h"
#include "esp_timer.h"

#include "ctf_core.h"
#include "ctf_platform.h"
#include "track_ble.h"

static const char *TAG = "track_btc";

#define SPP_NAME   "CTF Console"
#define EIR_COMPANY 0xFFFF /* SIG "reserved for internal use"; BLE uses 0x02E5 */
#define PROMPT     "spp> "
#define LINE_MAX   64
#define TX_BUF     1024
#define TX_CHUNK   256

static char s_name[32];          /* ESP32-CTF-XXXX:hhhhhh */
static uint8_t s_cod_minor;      /* BTC-03 nibble b6 */
static uint8_t s_eir_mfr[5];     /* company LE + 3 bytes */

static uint32_t s_handle;        /* open SPP connection, 0 if none */
static char s_line[LINE_MAX];
static size_t s_line_len;
static bool s_last_cr;

static char s_tx[TX_BUF];        /* pending output */
static size_t s_tx_len;
static bool s_tx_busy;           /* write in flight or congested */
static bool s_closing;           /* `exit`: disconnect once output is sent */

/* ---- output (callback mode: one esp_spp_write in flight) --------------- */

static void tx_pump(void)
{
    if (!s_handle || s_tx_busy) {
        return;
    }
    if (s_tx_len == 0) {
        if (s_closing) {
            s_closing = false;
            esp_spp_disconnect(s_handle);
        }
        return;
    }
    size_t n = s_tx_len > TX_CHUNK ? TX_CHUNK : s_tx_len;
    /* Bluedroid copies the data before esp_spp_write returns. */
    if (esp_spp_write(s_handle, (int)n, (uint8_t *)s_tx) != ESP_OK) {
        return;
    }
    s_tx_busy = true;
    memmove(s_tx, s_tx + n, s_tx_len - n);
    s_tx_len -= n;
}

static void out(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static void out(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(s_tx + s_tx_len, sizeof(s_tx) - s_tx_len, fmt, ap);
    va_end(ap);
    if (n > 0) {
        s_tx_len += (size_t)n < sizeof(s_tx) - s_tx_len ? (size_t)n : sizeof(s_tx) - 1 - s_tx_len;
    }
    tx_pump();
}

/* ---- shell ------------------------------------------------------------- */

static void banner(void)
{
    char flag[18];
    uint8_t sh[2];
    ctf_flag("BTC-01", flag);
    ctf_derive("CRY-01:shard3", sh, sizeof(sh));
    out("\r\n"
        "== ESP32-CTF field service console ==\r\n"
        "link token: %s\r\n"
        "note: help lists the user verbs; maintenance crews still use the old\r\n"
        "      `diag` verb, it was never removed.\r\n"
        "cipher shard 3/4: %c%c\r\n"
        "\r\n" PROMPT,
        flag, 'A' + sh[0] % 26, 'A' + sh[1] % 26);
}

static void run_line(char *line)
{
    while (*line == ' ' || *line == '\t') {
        line++;
    }
    size_t n = strlen(line);
    while (n && (line[n - 1] == ' ' || line[n - 1] == '\t')) {
        line[--n] = '\0';
    }

    if (n == 0) {
        /* nothing */
    } else if (!strcmp(line, "help")) {
        out("commands:\r\n"
            "  help    this list\r\n"
            "  status  link and service state\r\n"
            "  uptime  time since boot\r\n"
            "  whoami  current session\r\n"
            "  exit    close the session\r\n");
    } else if (!strcmp(line, "status")) {
        out("service: field console, rfcomm up\r\n"
            "mode: %s\r\n"
            "free heap: %u bytes\r\n",
            ctf_platform_mode_name(ctf_platform_mode()),
            (unsigned)heap_caps_get_free_size(MALLOC_CAP_8BIT));
    } else if (!strcmp(line, "uptime")) {
        int64_t s = esp_timer_get_time() / 1000000;
        out("up %lld s\r\n", (long long)s);
    } else if (!strcmp(line, "whoami")) {
        out("guest (paired, unprivileged)\r\n");
    } else if (!strcmp(line, "exit")) {
        s_closing = true;
        out("bye\r\n");
        return;
    } else if (!strcmp(line, "diag")) {
        char flag[18];
        ctf_flag("BTC-02", flag);
        out("diag: radio ok, rfcomm ok, nvs ok\r\n"
            "diag: service token %s\r\n",
            flag);
    } else {
        out("%s: unknown command (try help)\r\n", line);
    }
    out(PROMPT);
}

static void rx_bytes(const uint8_t *d, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        uint8_t c = d[i];
        if (c == '\r' || c == '\n') {
            bool skip = (c == '\n' && s_last_cr);
            s_last_cr = (c == '\r');
            if (skip) {
                continue;
            }
            out("\r\n");
            s_line[s_line_len] = '\0';
            s_line_len = 0;
            run_line(s_line);
            if (s_closing) {
                return; /* ignore anything typed after `exit` */
            }
            continue;
        }
        s_last_cr = false;
        if (c == 0x7f || c == 0x08) {
            if (s_line_len) {
                s_line_len--;
                out("\b \b");
            }
        } else if (c >= 0x20 && c < 0x7f && s_line_len < LINE_MAX - 1) {
            s_line[s_line_len++] = (char)c;
            out("%c", c); /* echo, for plain terminals */
        }
    }
}

/* ---- callbacks --------------------------------------------------------- */

static void set_cod(void)
{
    esp_bt_cod_t cod = {
        .minor = s_cod_minor,
        .major = ESP_BT_COD_MAJOR_DEV_UNCATEGORIZED,
        .service = ESP_BT_COD_SRVC_INFORMATION,
    };
    esp_bt_gap_set_cod(cod, ESP_BT_SET_COD_ALL);
}

static void spp_cb(esp_spp_cb_event_t event, esp_spp_cb_param_t *p)
{
    switch (event) {
    case ESP_SPP_INIT_EVT:
        if (p->init.status != ESP_SPP_SUCCESS) {
            ESP_LOGE(TAG, "SPP init failed: %d", p->init.status);
            break;
        }
        set_cod(); /* after SPP init: its JV enable resets major/minor to unclassified */
        esp_spp_start_srv(ESP_SPP_SEC_AUTHENTICATE, ESP_SPP_ROLE_SLAVE, 0, SPP_NAME);
        break;
    case ESP_SPP_START_EVT:
        if (p->start.status == ESP_SPP_SUCCESS) {
            ESP_LOGI(TAG, "SPP server \"%s\" on RFCOMM channel %u; free heap: %u bytes", SPP_NAME,
                     p->start.scn, (unsigned)heap_caps_get_free_size(MALLOC_CAP_8BIT));
        } else {
            ESP_LOGE(TAG, "SPP server start failed: %d", p->start.status);
        }
        break;
    case ESP_SPP_SRV_OPEN_EVT:
        if (p->srv_open.status != ESP_SPP_SUCCESS) {
            break;
        }
        if (s_handle) { /* one session at a time */
            esp_spp_disconnect(p->srv_open.handle);
            break;
        }
        s_handle = p->srv_open.handle;
        s_tx_len = 0;
        s_tx_busy = false;
        s_line_len = 0;
        s_last_cr = false;
        s_closing = false;
        ESP_LOGI(TAG, "SPP session open");
        banner();
        break;
    case ESP_SPP_CLOSE_EVT:
        if (p->close.handle == s_handle) {
            s_handle = 0;
            s_tx_len = 0;
            s_tx_busy = false;
            ESP_LOGI(TAG, "SPP session closed");
        }
        break;
    case ESP_SPP_DATA_IND_EVT:
        if (p->data_ind.handle == s_handle && !s_closing) {
            rx_bytes(p->data_ind.data, p->data_ind.len);
        }
        break;
    case ESP_SPP_WRITE_EVT:
        if (p->write.handle == s_handle) {
            s_tx_busy = p->write.cong;
            tx_pump();
        }
        break;
    case ESP_SPP_CONG_EVT:
        if (p->cong.handle == s_handle) {
            s_tx_busy = p->cong.cong;
            tx_pump();
        }
        break;
    default:
        break;
    }
}

static void gap_cb(esp_bt_gap_cb_event_t event, esp_bt_gap_cb_param_t *p)
{
    switch (event) {
    case ESP_BT_GAP_CFM_REQ_EVT: /* Just Works / numeric comparison: accept */
        esp_bt_gap_ssp_confirm_reply(p->cfm_req.bda, true);
        break;
    case ESP_BT_GAP_AUTH_CMPL_EVT:
        if (p->auth_cmpl.stat == ESP_BT_STATUS_SUCCESS) {
            ESP_LOGI(TAG, "Classic pairing complete");
        } else {
            ESP_LOGW(TAG, "Classic pairing failed: %d", p->auth_cmpl.stat);
        }
        break;
    case ESP_BT_GAP_PIN_REQ_EVT: { /* legacy peers only */
        esp_bt_pin_code_t pin = {'0', '0', '0', '0'};
        esp_bt_gap_pin_reply(p->pin_req.bda, true, 4, pin);
        break;
    }
    default:
        break;
    }
}

/* ---- init -------------------------------------------------------------- */

static void derive_values(void)
{
    uint8_t mac[6];
    char body[13];
    ctf_platform_mac(mac);
    ctf_flag_body("BTC-03", body);

    snprintf(s_name, sizeof(s_name), "ESP32-CTF-%02X%02X:%.6s", mac[4], mac[5], body);

    unsigned v = 0;
    sscanf(body + 6, "%1x", &v);
    s_cod_minor = (uint8_t)v;
    unsigned tail = 0;
    sscanf(body + 7, "%5x", &tail);
    s_eir_mfr[0] = EIR_COMPANY & 0xff;
    s_eir_mfr[1] = EIR_COMPANY >> 8;
    s_eir_mfr[2] = (uint8_t)(tail >> 16);
    s_eir_mfr[3] = (uint8_t)(tail >> 8);
    s_eir_mfr[4] = (uint8_t)tail;
}

void track_btc_start(void)
{
    if (!track_ble_bt_ready()) {
        ESP_LOGW(TAG, "Bluetooth not up, BT Classic track disabled");
        return;
    }
    derive_values();

    esp_err_t err;
    if ((err = esp_bt_gap_register_callback(gap_cb)) != ESP_OK ||
        (err = esp_spp_register_callback(spp_cb)) != ESP_OK) {
        ESP_LOGE(TAG, "callback register failed: %s", esp_err_to_name(err));
        return;
    }

    esp_bt_gap_set_device_name(s_name);

    esp_bt_eir_data_t eir = {
        .fec_required = true,
        .include_txpower = false,
        .include_uuid = true,
        .include_name = true,
        .flag = ESP_BT_EIR_FLAG_GEN_DISC,
        .manufacturer_len = sizeof(s_eir_mfr),
        .p_manufacturer_data = s_eir_mfr,
    };
    esp_bt_gap_config_eir_data(&eir);

    esp_bt_io_cap_t iocap = ESP_BT_IO_CAP_NONE; /* SSP Just Works */
    esp_bt_gap_set_security_param(ESP_BT_SP_IOCAP_MODE, &iocap, sizeof(iocap));

    esp_spp_cfg_t cfg = {
        .mode = ESP_SPP_MODE_CB,
        .enable_l2cap_ertm = true,
        .tx_buffer_size = 0,
    };
    if ((err = esp_spp_enhanced_init(&cfg)) != ESP_OK) {
        ESP_LOGE(TAG, "SPP init failed: %s", esp_err_to_name(err));
        return;
    }

    esp_bt_gap_set_scan_mode(ESP_BT_CONNECTABLE, ESP_BT_GENERAL_DISCOVERABLE);

    ESP_LOGI(TAG, "BT Classic up (SPP \"%s\"); free heap with BLE + Classic: %u bytes "
             "(largest block %u)", SPP_NAME,
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_8BIT),
             (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_8BIT));
}
