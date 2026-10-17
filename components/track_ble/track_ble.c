/* BLE track (SPEC "BLE"): BLE-01..11, CTF control service (submit + score),
 * CRY-01 shard 2. Also brings up the shared BT controller (BTDM) + Bluedroid.
 *
 * Layout: one GATTS app, two attribute tables (challenge service, control
 * service), 128-bit UUIDs e532XXXX-c7f0-4e5b-9a1d-3c54460b1e00 (table in
 * solvers/ble/README.md). Single connection; advertising restarts on
 * disconnect. Per-connection state (BLE-05 hatch, BLE-10 unlock, BLE-11
 * progress, subscriptions) resets on disconnect; the BLE-10 lockout is global.
 *
 * Threading: GATTS/GAP callbacks run in the Bluedroid BTC task; a 1 s esp_timer
 * rotates the advert, pulses BLE-03 and refreshes the score. Shared state the
 * timer reads is a handful of word-sized flags; a stale read only causes one
 * dropped notification. */
#include "track_ble.h"

#include <ctype.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "ctf_core.h"
#include "ctf_platform.h"
#include "esp_bt.h"
#include "esp_bt_device.h"
#include "esp_bt_main.h"
#include "esp_console.h"
#include "esp_gap_ble_api.h"
#include "esp_gatt_common_api.h"
#include "esp_gatts_api.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"

static const char *TAG = "track_ble";

#define APP_ID           0x42
#define LOCAL_MTU        517
#define COMPANY_ID       0x02E5 /* Espressif */
#define PIN_TRIES        5      /* BLE-10: wrong tries before a lockout */
#define PIN_LOCKOUT_US   (3 * 1000 * 1000)
#define PIN_ERR_LOCKOUT  0x80   /* ATT application error: locked out */
#define PIN_ERR_FORMAT   0x81   /* ATT application error: not 4 ASCII digits */
#define SEQ_LEN          5      /* BLE-11 */
#define SEQ_GAP_US       (500 * 1000)
#define FRAG_CHARS       4      /* BLE-04 fragment size */

/* ---- UUIDs ------------------------------------------------------------- */

/* e532XXXX-c7f0-4e5b-9a1d-3c54460b1e00, little-endian as Bluedroid wants. */
#define UUID_SVC_CHAL  0x0100
#define UUID_BLE01     0x0101
#define UUID_BLE02     0x0102
#define UUID_BLE03     0x0103
#define UUID_BLE04     0x0104
#define UUID_BLE05_IN  0x0105
#define UUID_BLE05_OUT 0x0115
#define UUID_BLE06     0x0106
#define UUID_BLE06_DSC 0x0166
#define UUID_BLE08     0x0108
#define UUID_BLE09     0x0109
#define UUID_BLE10     0x010A
#define UUID_BLE11_IN  0x010B
#define UUID_BLE11_OUT 0x011B
#define UUID_SHARD     0x01C2
#define UUID_SVC_CTRL  0x0200
#define UUID_SUBMIT    0x0201
#define UUID_RESULT    0x0202
#define UUID_SCORE     0x0203

#define MAX_UUIDS 24
static uint8_t s_uuid[MAX_UUIDS][16];
static int s_nuuid;

static void uuid_fill(uint8_t u[16], uint16_t id)
{
    static const uint8_t base[16] = {0x00, 0x1e, 0x0b, 0x46, 0x54, 0x3c, 0x1d, 0x9a,
                                     0x5b, 0x4e, 0xf0, 0xc7, 0x00, 0x00, 0x32, 0xe5};
    memcpy(u, base, 16);
    u[12] = (uint8_t)(id & 0xff);
    u[13] = (uint8_t)(id >> 8);
}

static uint8_t *u128(uint16_t id)
{
    uint8_t *u = s_uuid[s_nuuid++];
    uuid_fill(u, id);
    return u;
}

static uint16_t s_uuid_primary = ESP_GATT_UUID_PRI_SERVICE;
static uint16_t s_uuid_decl = ESP_GATT_UUID_CHAR_DECLARE;
static uint16_t s_uuid_cccd = ESP_GATT_UUID_CHAR_CLIENT_CONFIG;
static uint16_t s_uuid_udesc = ESP_GATT_UUID_CHAR_DESCRIPTION;

static uint8_t s_prop_r = ESP_GATT_CHAR_PROP_BIT_READ;
static uint8_t s_prop_n = ESP_GATT_CHAR_PROP_BIT_NOTIFY;
static uint8_t s_prop_i = ESP_GATT_CHAR_PROP_BIT_INDICATE;
static uint8_t s_prop_w = ESP_GATT_CHAR_PROP_BIT_WRITE;
static uint8_t s_prop_ww = ESP_GATT_CHAR_PROP_BIT_WRITE | ESP_GATT_CHAR_PROP_BIT_WRITE_NR;
static uint8_t s_prop_rn = ESP_GATT_CHAR_PROP_BIT_READ | ESP_GATT_CHAR_PROP_BIT_NOTIFY;
static uint8_t s_prop_rwn = ESP_GATT_CHAR_PROP_BIT_READ | ESP_GATT_CHAR_PROP_BIT_WRITE |
                            ESP_GATT_CHAR_PROP_BIT_NOTIFY;
static uint8_t s_prop_rwnr = ESP_GATT_CHAR_PROP_BIT_READ | ESP_GATT_CHAR_PROP_BIT_WRITE_NR;
static uint8_t s_cccd_init[2];
static uint8_t s_empty[1];

/* ---- attribute tables -------------------------------------------------- */

enum {
    C_SVC,
    C01_DECL, C01_VAL, C01_DESC,
    C02_DECL, C02_VAL, C02_DESC,
    C03_DECL, C03_VAL, C03_CCC, C03_DESC,
    C04_DECL, C04_VAL, C04_CCC, C04_DESC,
    C05A_DECL, C05A_VAL, C05A_DESC,
    C05B_DECL, C05B_VAL, C05B_DESC,
    C08_DECL, C08_VAL, C08_DESC,
    C09_DECL, C09_VAL, C09_DESC,
    C10_DECL, C10_VAL, C10_CCC, C10_DESC,
    C11A_DECL, C11A_VAL, C11A_DESC,
    C11B_DECL, C11B_VAL, C11B_CCC, C11B_DESC,
    CSH_DECL, CSH_VAL, CSH_DESC,
    /* BLE-06 must stay last: create_attr_tab skips 128-bit descriptor rows, so
     * C06_SECRET is only a reserved handle; the descriptor is added with
     * esp_ble_gatts_add_char_descr() after the table, which appends it to the
     * last characteristic. */
    C06_DECL, C06_VAL, C06_DESC, C06_SECRET,
    C_NB
};

enum {
    K_SVC,
    K_SUB_DECL, K_SUB_VAL, K_SUB_DESC,
    K_RES_DECL, K_RES_VAL, K_RES_CCC, K_RES_DESC,
    K_SCO_DECL, K_SCO_VAL, K_SCO_CCC, K_SCO_DESC,
    K_NB
};

static esp_gatts_attr_db_t s_tab_c[C_NB];
static esp_gatts_attr_db_t s_tab_k[K_NB];
static uint16_t s_hc[C_NB];
static uint16_t s_hk[K_NB];
static int s_tabs_done;

static void a_set(esp_gatts_attr_db_t *e, uint8_t rsp, uint16_t uuid_len, const void *uuid,
                  uint16_t perm, uint16_t max, uint16_t len, const void *val)
{
    e->attr_control.auto_rsp = rsp;
    e->att_desc.uuid_length = uuid_len;
    e->att_desc.uuid_p = (uint8_t *)uuid;
    e->att_desc.perm = perm;
    e->att_desc.max_length = max;
    e->att_desc.length = len;
    e->att_desc.value = (uint8_t *)val;
}

static void a_svc(esp_gatts_attr_db_t *e, const uint8_t *svc_uuid)
{
    a_set(e, ESP_GATT_AUTO_RSP, ESP_UUID_LEN_16, &s_uuid_primary, ESP_GATT_PERM_READ, 16, 16,
          svc_uuid);
}

static void a_decl(esp_gatts_attr_db_t *e, const uint8_t *prop)
{
    a_set(e, ESP_GATT_AUTO_RSP, ESP_UUID_LEN_16, &s_uuid_decl, ESP_GATT_PERM_READ, 1, 1, prop);
}

static void a_cccd(esp_gatts_attr_db_t *e)
{
    a_set(e, ESP_GATT_AUTO_RSP, ESP_UUID_LEN_16, &s_uuid_cccd,
          ESP_GATT_PERM_READ | ESP_GATT_PERM_WRITE, 2, 2, s_cccd_init);
}

static void a_desc(esp_gatts_attr_db_t *e, const char *text)
{
    uint16_t n = (uint16_t)strlen(text);
    a_set(e, ESP_GATT_AUTO_RSP, ESP_UUID_LEN_16, &s_uuid_udesc, ESP_GATT_PERM_READ, n, n, text);
}

/* Value with a 128-bit UUID; text values use strlen. */
static void a_val(esp_gatts_attr_db_t *e, uint8_t rsp, uint16_t id, uint16_t perm,
                  uint16_t max, const char *text)
{
    uint16_t n = text ? (uint16_t)strlen(text) : 0;
    a_set(e, rsp, ESP_UUID_LEN_128, u128(id), perm, max > n ? max : n, n,
          text ? (const void *)text : (const void *)s_empty);
}

/* ---- per-board values -------------------------------------------------- */

static char s_name[20];             /* ESP32-CTF-XXXX */
static char s_flag01[18], s_flag03[18], s_flag04[18], s_flag05[18], s_flag06[18];
static char s_flag07[18], s_flag09[18], s_flag10[18], s_flag11[18];
static char s_val02[64];            /* reverse(base64(hex(flag))) */
static char s_val08[320];           /* long telemetry dump, flag at the end */
static char s_val11[112];           /* sequencer instructions */
static char s_shard[24];            /* "cipher shard 2/4: XY" */
static char s_unseal[24];           /* BLE-05 unlock word */
static char s_desc05[96];
static uint16_t s_pin;              /* BLE-10 */
static uint8_t s_seq[SEQ_LEN];      /* BLE-11 */
static uint32_t s_passkey;          /* BLE-09 */

static const char SEALED[] = "SEALED";
static const char WAITING[] = "";

static void hex_upper(const uint8_t *b, size_t n, char *out)
{
    static const char H[] = "0123456789ABCDEF";
    for (size_t i = 0; i < n; i++) {
        out[2 * i] = H[b[i] >> 4];
        out[2 * i + 1] = H[b[i] & 15];
    }
    out[2 * n] = '\0';
}

static size_t base64(const uint8_t *in, size_t n, char *out)
{
    static const char T[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    size_t o = 0;
    for (size_t i = 0; i < n; i += 3) {
        uint32_t v = (uint32_t)in[i] << 16;
        if (i + 1 < n) {
            v |= (uint32_t)in[i + 1] << 8;
        }
        if (i + 2 < n) {
            v |= in[i + 2];
        }
        out[o++] = T[(v >> 18) & 63];
        out[o++] = T[(v >> 12) & 63];
        out[o++] = (i + 1 < n) ? T[(v >> 6) & 63] : '=';
        out[o++] = (i + 2 < n) ? T[v & 63] : '=';
    }
    out[o] = '\0';
    return o;
}

static void derive_values(void)
{
    uint8_t mac[6];
    ctf_platform_mac(mac);
    snprintf(s_name, sizeof(s_name), "ESP32-CTF-%02X%02X", mac[4], mac[5]);

    ctf_flag("BLE-01", s_flag01);
    ctf_flag("BLE-03", s_flag03);
    ctf_flag("BLE-04", s_flag04);
    ctf_flag("BLE-05", s_flag05);
    ctf_flag("BLE-06", s_flag06);
    ctf_flag("BLE-07", s_flag07);
    ctf_flag("BLE-09", s_flag09);
    ctf_flag("BLE-10", s_flag10);
    ctf_flag("BLE-11", s_flag11);

    /* BLE-02: hex (lower) -> base64 -> bytes reversed. */
    char f[18], hx[40];
    ctf_flag("BLE-02", f);
    for (size_t i = 0; f[i]; i++) {
        snprintf(hx + 2 * i, 3, "%02x", (unsigned char)f[i]);
    }
    size_t n = base64((const uint8_t *)hx, strlen(hx), s_val02);
    for (size_t i = 0; i < n / 2; i++) {
        char t = s_val02[i];
        s_val02[i] = s_val02[n - 1 - i];
        s_val02[n - 1 - i] = t;
    }

    /* BLE-05 */
    uint8_t b[4];
    char h[9];
    ctf_derive("BLE-05:code", b, 4);
    hex_upper(b, 4, h);
    snprintf(s_unseal, sizeof(s_unseal), "UNSEAL-%s", h);
    snprintf(s_desc05, sizeof(s_desc05), "[BLE-05] Airlock Panel: write %s to open the hatch",
             s_unseal);

    /* BLE-08: > 200 bytes of sensor records, flag at the end. */
    uint8_t noise[24];
    ctf_derive("BLE-08:noise", noise, sizeof(noise));
    ctf_flag("BLE-08", f);
    size_t o = (size_t)snprintf(s_val08, sizeof(s_val08), "TELEMETRY v2 ");
    for (int i = 0; i < 24; i++) {
        o += (size_t)snprintf(s_val08 + o, sizeof(s_val08) - o, "s%02d=%02X; ", i, noise[i]);
    }
    snprintf(s_val08 + o, sizeof(s_val08) - o, "end of dump: %s", f);

    /* BLE-09: static 6-digit passkey. */
    s_passkey = ctf_derive_u32("BLE-09:passkey") % 1000000u;

    /* BLE-10: 4-digit PIN. */
    s_pin = (uint16_t)(ctf_derive_u32("BLE-10:pin") % 10000u);

    /* BLE-11: five 1-byte values. */
    ctf_derive("BLE-11:seq", s_seq, SEQ_LEN);
    snprintf(s_val11, sizeof(s_val11),
             "Sequencer: send %02X %02X %02X %02X %02X, one byte each, as write-without-response,"
             " < 500 ms apart",
             s_seq[0], s_seq[1], s_seq[2], s_seq[3], s_seq[4]);

    /* CRY-01 shard 2. */
    uint8_t sh[2];
    ctf_derive("CRY-01:shard2", sh, 2);
    snprintf(s_shard, sizeof(s_shard), "cipher shard 2/4: %c%c", 'A' + sh[0] % 26,
             'A' + sh[1] % 26);
}

static void build_tables(void)
{
    const uint16_t R = ESP_GATT_PERM_READ, W = ESP_GATT_PERM_WRITE;
    esp_gatts_attr_db_t *c = s_tab_c;
    s_nuuid = 0;

    a_svc(&c[C_SVC], u128(UUID_SVC_CHAL));

    a_decl(&c[C01_DECL], &s_prop_r);
    a_val(&c[C01_VAL], ESP_GATT_AUTO_RSP, UUID_BLE01, R, 0, s_flag01);
    a_desc(&c[C01_DESC], "[BLE-01] Welcome Note");

    a_decl(&c[C02_DECL], &s_prop_r);
    a_val(&c[C02_VAL], ESP_GATT_AUTO_RSP, UUID_BLE02, R, 0, s_val02);
    a_desc(&c[C02_DESC], "[BLE-02] Scrambled Transmission");

    a_decl(&c[C03_DECL], &s_prop_n);
    a_val(&c[C03_VAL], ESP_GATT_AUTO_RSP, UUID_BLE03, 0, 20, NULL);
    a_cccd(&c[C03_CCC]);
    a_desc(&c[C03_DESC], "[BLE-03] Beacon Pulse");

    a_decl(&c[C04_DECL], &s_prop_i);
    a_val(&c[C04_VAL], ESP_GATT_AUTO_RSP, UUID_BLE04, 0, 20, NULL);
    a_cccd(&c[C04_CCC]);
    a_desc(&c[C04_DESC], "[BLE-04] Relay Station");

    a_decl(&c[C05A_DECL], &s_prop_w);
    a_val(&c[C05A_VAL], ESP_GATT_AUTO_RSP, UUID_BLE05_IN, W, 32, NULL);
    a_desc(&c[C05A_DESC], s_desc05);

    a_decl(&c[C05B_DECL], &s_prop_r);
    a_val(&c[C05B_VAL], ESP_GATT_AUTO_RSP, UUID_BLE05_OUT, R, 24, SEALED);
    a_desc(&c[C05B_DESC], "[BLE-05] Airlock Hatch");

    a_decl(&c[C06_DECL], &s_prop_r);
    a_val(&c[C06_VAL], ESP_GATT_AUTO_RSP, UUID_BLE06, R, 0, "fw 1.0.3 (stable)");
    a_desc(&c[C06_DESC], "[BLE-06] Firmware Revision");
    a_set(&c[C06_SECRET], ESP_GATT_AUTO_RSP, ESP_UUID_LEN_128, u128(UUID_BLE06_DSC), R,
          (uint16_t)strlen(s_flag06), (uint16_t)strlen(s_flag06), s_flag06);

    a_decl(&c[C08_DECL], &s_prop_r);
    a_val(&c[C08_VAL], ESP_GATT_AUTO_RSP, UUID_BLE08, R, 0, s_val08);
    a_desc(&c[C08_DESC], "[BLE-08] Telemetry Dump");

    a_decl(&c[C09_DECL], &s_prop_r);
    a_val(&c[C09_VAL], ESP_GATT_AUTO_RSP, UUID_BLE09, ESP_GATT_PERM_READ_ENC_MITM, 0, s_flag09);
    a_desc(&c[C09_DESC], "[BLE-09] Secure Locker");

    a_decl(&c[C10_DECL], &s_prop_rwn);
    a_val(&c[C10_VAL], ESP_GATT_RSP_BY_APP, UUID_BLE10, R | W, 32, NULL);
    a_cccd(&c[C10_CCC]);
    a_desc(&c[C10_DESC], "[BLE-10] Vault Keypad: 4-digit PIN, 5 wrong tries lock it for 3 s");

    a_decl(&c[C11A_DECL], &s_prop_rwnr);
    a_val(&c[C11A_VAL], ESP_GATT_RSP_BY_APP, UUID_BLE11_IN, R | W, 32, NULL);
    a_desc(&c[C11A_DESC], "[BLE-11] Sequencer Input");

    a_decl(&c[C11B_DECL], &s_prop_n);
    a_val(&c[C11B_VAL], ESP_GATT_AUTO_RSP, UUID_BLE11_OUT, 0, 20, NULL);
    a_cccd(&c[C11B_CCC]);
    a_desc(&c[C11B_DESC], "[BLE-11] Sequencer Output");

    a_decl(&c[CSH_DECL], &s_prop_r);
    a_val(&c[CSH_VAL], ESP_GATT_AUTO_RSP, UUID_SHARD, R, 0, s_shard);
    a_desc(&c[CSH_DESC], "Cipher Shard");

    esp_gatts_attr_db_t *k = s_tab_k;
    a_svc(&k[K_SVC], u128(UUID_SVC_CTRL));

    a_decl(&k[K_SUB_DECL], &s_prop_ww);
    a_val(&k[K_SUB_VAL], ESP_GATT_AUTO_RSP, UUID_SUBMIT, W, 64, NULL);
    a_desc(&k[K_SUB_DESC], "CTF Submit Flag");

    a_decl(&k[K_RES_DECL], &s_prop_rn);
    a_val(&k[K_RES_VAL], ESP_GATT_AUTO_RSP, UUID_RESULT, R, 40, WAITING);
    a_cccd(&k[K_RES_CCC]);
    a_desc(&k[K_RES_DESC], "CTF Submit Result");

    a_decl(&k[K_SCO_DECL], &s_prop_rn);
    a_val(&k[K_SCO_VAL], ESP_GATT_AUTO_RSP, UUID_SCORE, R, 16, "0/0");
    a_cccd(&k[K_SCO_CCC]);
    a_desc(&k[K_SCO_DESC], "CTF Score");
}

/* ---- connection state -------------------------------------------------- */

static volatile bool s_bt_ready;
static esp_gatt_if_t s_gif = ESP_GATT_IF_NONE;
static volatile bool s_connected;
static volatile uint16_t s_conn_id;
static uint16_t s_mtu = 23;
static esp_bd_addr_t s_peer;

static volatile bool s_sub03, s_sub10, s_sub11, s_sub_res, s_sub_score;
static bool s_frag_active;
static int s_frag;
static bool s_pin_ok;
static int s_pin_wrong;          /* global: survives reconnects */
static int64_t s_lock_until;     /* global */
static int s_seq_step;
static int64_t s_seq_last;
static bool s_sub_prep;          /* a prepared (long) write to the submit char is pending */

static volatile int s_adv_part;
static int s_adv_cfg;            /* bit0 adv data set, bit1 scan rsp set */
static bool s_adv_started_once;
static char s_score_txt[16];

static void reset_conn_state(void)
{
    s_sub03 = s_sub10 = s_sub11 = s_sub_res = s_sub_score = false;
    s_frag_active = false;
    s_frag = 0;
    s_pin_ok = false;
    s_seq_step = 0;
    s_seq_last = 0;
    s_sub_prep = false;
    s_mtu = 23;
}

static void notify(uint16_t handle, const void *data, size_t len, bool confirm)
{
    if (!s_connected || s_gif == ESP_GATT_IF_NONE) {
        return;
    }
    esp_ble_gatts_send_indicate(s_gif, s_conn_id, handle, (uint16_t)len, (uint8_t *)data,
                                confirm);
}

/* ---- advertising ------------------------------------------------------- */

static esp_ble_adv_params_t s_adv_params = {
    .adv_int_min = 0x20, /* 20 ms */
    .adv_int_max = 0x40, /* 40 ms */
    .adv_type = ADV_TYPE_IND,
    .own_addr_type = BLE_ADDR_TYPE_PUBLIC,
    .channel_map = ADV_CHNL_ALL,
    .adv_filter_policy = ADV_FILTER_ALLOW_SCAN_ANY_CON_ANY,
};

/* Advert: flags + complete name + manufacturer data "<n>:<part n of 3>".
 * 3 + 16 + 12 = 31 bytes. The service UUID goes in the scan response. */
static void adv_update(void)
{
    static const uint8_t off[3] = {0, 6, 12}, len[3] = {6, 6, 5};
    uint8_t a[31];
    size_t n = 0, nl = strlen(s_name);
    int p = s_adv_part;
    a[n++] = 2;
    a[n++] = ESP_BLE_AD_TYPE_FLAG;
    a[n++] = ESP_BLE_ADV_FLAG_GEN_DISC | ESP_BLE_ADV_FLAG_BREDR_NOT_SPT;
    a[n++] = (uint8_t)(nl + 1);
    a[n++] = ESP_BLE_AD_TYPE_NAME_CMPL;
    memcpy(a + n, s_name, nl);
    n += nl;
    a[n++] = (uint8_t)(1 + 2 + 2 + len[p]);
    a[n++] = ESP_BLE_AD_MANUFACTURER_SPECIFIC_TYPE;
    a[n++] = COMPANY_ID & 0xff;
    a[n++] = COMPANY_ID >> 8;
    a[n++] = (uint8_t)('1' + p);
    a[n++] = ':';
    memcpy(a + n, s_flag07 + off[p], len[p]);
    n += len[p];
    esp_ble_gap_config_adv_data_raw(a, (uint32_t)n);
}

static void scan_rsp_config(void)
{
    uint8_t r[18];
    r[0] = 17;
    r[1] = ESP_BLE_AD_TYPE_128SRV_CMPL;
    uuid_fill(r + 2, UUID_SVC_CHAL);
    esp_ble_gap_config_scan_rsp_data_raw(r, sizeof(r));
}

static void adv_start(void)
{
    if (!s_connected) {
        esp_ble_gap_start_advertising(&s_adv_params);
    }
}

/* ---- score / tick ------------------------------------------------------ */

static void score_update(void)
{
    char t[16];
    snprintf(t, sizeof(t), "%d/%d", ctf_score(), ctf_max_score(true));
    if (strcmp(t, s_score_txt) == 0) {
        return;
    }
    strcpy(s_score_txt, t);
    if (s_hk[K_SCO_VAL]) {
        esp_ble_gatts_set_attr_value(s_hk[K_SCO_VAL], (uint16_t)strlen(t), (const uint8_t *)t);
        if (s_sub_score) {
            notify(s_hk[K_SCO_VAL], t, strlen(t), false);
        }
    }
}

static void tick_cb(void *arg)
{
    static unsigned tick;
    (void)arg;
    tick++;
    if (tick % 2 == 0) {
        s_adv_part = (s_adv_part + 1) % 3;
        adv_update();
    }
    if (s_connected && s_sub03) {
        notify(s_hc[C03_VAL], s_flag03, strlen(s_flag03), false);
    }
    score_update();
}

/* ---- challenge logic --------------------------------------------------- */

static void send_frag(void)
{
    size_t total = strlen(s_flag04);
    int nfrag = (int)((total + FRAG_CHARS - 1) / FRAG_CHARS);
    char t[20];
    size_t off = (size_t)s_frag * FRAG_CHARS;
    size_t n = total - off < FRAG_CHARS ? total - off : FRAG_CHARS;
    int len = snprintf(t, sizeof(t), "%d/%d:%.*s", s_frag + 1, nfrag, (int)n, s_flag04 + off);
    notify(s_hc[C04_VAL], t, (size_t)len, true);
}

static void on_frag_confirm(esp_gatt_status_t st)
{
    if (!s_frag_active) {
        return;
    }
    int nfrag = (int)((strlen(s_flag04) + FRAG_CHARS - 1) / FRAG_CHARS);
    if (st != ESP_GATT_OK || ++s_frag >= nfrag) {
        s_frag_active = false;
        return;
    }
    send_frag();
}

static esp_gatt_rsp_t s_rsp;

static void send_read(const struct gatts_read_evt_param *rd, const char *data)
{
    size_t len = strlen(data);
    memset(&s_rsp, 0, sizeof(s_rsp));
    s_rsp.attr_value.handle = rd->handle;
    s_rsp.attr_value.offset = rd->offset;
    if (rd->offset > len) {
        esp_ble_gatts_send_response(s_gif, rd->conn_id, rd->trans_id, ESP_GATT_INVALID_OFFSET,
                                    &s_rsp);
        return;
    }
    size_t n = len - rd->offset, max = (size_t)s_mtu - 1;
    if (n > max) {
        n = max;
    }
    memcpy(s_rsp.attr_value.value, data + rd->offset, n);
    s_rsp.attr_value.len = (uint16_t)n;
    esp_ble_gatts_send_response(s_gif, rd->conn_id, rd->trans_id, ESP_GATT_OK, &s_rsp);
}

static void pin_status(char *out, size_t n)
{
    int64_t now = esp_timer_get_time();
    if (s_pin_ok) {
        snprintf(out, n, "%s", s_flag10);
    } else if (now < s_lock_until) {
        snprintf(out, n, "LOCKOUT %u ms", (unsigned)((s_lock_until - now) / 1000));
    } else {
        snprintf(out, n, "LOCKED %d tries left", PIN_TRIES - s_pin_wrong);
    }
}

static void pin_write(const struct gatts_write_evt_param *w)
{
    esp_gatt_status_t st = ESP_GATT_OK;
    int64_t now = esp_timer_get_time();
    bool fresh_ok = false;
    if (w->is_prep) {
        st = ESP_GATT_REQ_NOT_SUPPORTED;
    } else if (now < s_lock_until) {
        st = PIN_ERR_LOCKOUT;
    } else if (w->len != 4 || !isdigit(w->value[0]) || !isdigit(w->value[1]) ||
               !isdigit(w->value[2]) || !isdigit(w->value[3])) {
        st = PIN_ERR_FORMAT;
    } else {
        int v = (w->value[0] - '0') * 1000 + (w->value[1] - '0') * 100 +
                (w->value[2] - '0') * 10 + (w->value[3] - '0');
        if (v == s_pin) {
            fresh_ok = !s_pin_ok;
            s_pin_ok = true;
            s_pin_wrong = 0;
        } else if (++s_pin_wrong >= PIN_TRIES) {
            s_pin_wrong = 0;
            s_lock_until = now + PIN_LOCKOUT_US;
        }
    }
    if (w->need_rsp) {
        esp_ble_gatts_send_response(s_gif, w->conn_id, w->trans_id, st, NULL);
    }
    if (s_pin_ok && st == ESP_GATT_OK && s_sub10) {
        notify(s_hc[C10_VAL], s_flag10, strlen(s_flag10), false);
    }
    if (fresh_ok) {
        ESP_LOGI(TAG, "BLE-10 vault opened");
    }
}

static void seq_write(const struct gatts_write_evt_param *w)
{
    if (w->need_rsp) {
        /* Write requests do not count: this panel only takes write commands. */
        esp_ble_gatts_send_response(s_gif, w->conn_id, w->trans_id, ESP_GATT_WRITE_NOT_PERMIT,
                                    NULL);
        s_seq_step = 0;
        return;
    }
    int64_t now = esp_timer_get_time();
    if (w->len != 1) {
        s_seq_step = 0;
        return;
    }
    if (s_seq_step > 0 && now - s_seq_last > SEQ_GAP_US) {
        s_seq_step = 0;
    }
    uint8_t v = w->value[0];
    if (v == s_seq[s_seq_step]) {
        s_seq_step++;
    } else {
        s_seq_step = (v == s_seq[0]) ? 1 : 0;
    }
    s_seq_last = now;
    if (s_seq_step == SEQ_LEN) {
        s_seq_step = 0;
        ESP_LOGI(TAG, "BLE-11 sequence accepted");
        if (s_sub11) {
            notify(s_hc[C11B_VAL], s_flag11, strlen(s_flag11), false);
        }
    }
}

static void submit_bytes(const uint8_t *v, size_t len)
{
    char buf[72], res[40];
    if (len > sizeof(buf) - 1) {
        len = sizeof(buf) - 1;
    }
    memcpy(buf, v, len);
    buf[len] = '\0';
    const ctf_challenge_t *c = NULL;
    switch (ctf_submit(buf, &c)) {
    case CTF_SUBMIT_NEW:
        snprintf(res, sizeof(res), "Correct! %s +%d", c->id,
                 ctf_points(c->id) - (ctf_hint_used(c->id) ? ctf_points(c->id) / 4 : 0));
        break;
    case CTF_SUBMIT_ALREADY:
        snprintf(res, sizeof(res), "Already solved");
        break;
    default:
        snprintf(res, sizeof(res), "Wrong flag");
        break;
    }
    ESP_LOGI(TAG, "BLE submit: %s", res);
    esp_ble_gatts_set_attr_value(s_hk[K_RES_VAL], (uint16_t)strlen(res), (const uint8_t *)res);
    if (s_sub_res) {
        notify(s_hk[K_RES_VAL], res, strlen(res), false);
    }
    score_update();
}

static bool trimmed_eq(const uint8_t *v, size_t len, const char *want)
{
    while (len && (v[len - 1] == '\n' || v[len - 1] == '\r' || v[len - 1] == ' ' ||
                   v[len - 1] == '\0')) {
        len--;
    }
    return len == strlen(want) && memcmp(v, want, len) == 0;
}

static void cccd_write(uint16_t h, uint16_t v)
{
    if (h == s_hc[C03_CCC]) {
        s_sub03 = v & 1;
        if (s_sub03) {
            notify(s_hc[C03_VAL], s_flag03, strlen(s_flag03), false);
        }
    } else if (h == s_hc[C04_CCC]) {
        if (v & 2) {
            s_frag = 0;
            s_frag_active = true;
            send_frag();
        } else {
            s_frag_active = false;
        }
    } else if (h == s_hc[C10_CCC]) {
        s_sub10 = v & 1;
    } else if (h == s_hc[C11B_CCC]) {
        s_sub11 = v & 1;
    } else if (h == s_hk[K_RES_CCC]) {
        s_sub_res = v & 1;
    } else if (h == s_hk[K_SCO_CCC]) {
        s_sub_score = v & 1;
    }
}

static void on_write(const struct gatts_write_evt_param *w)
{
    uint16_t h = w->handle;
    if (h == s_hc[C10_VAL]) {
        pin_write(w);
        return;
    }
    if (h == s_hc[C11A_VAL]) {
        seq_write(w);
        return;
    }
    /* Everything else is auto-response: the stack has already answered. */
    if (w->is_prep) {
        if (h == s_hk[K_SUB_VAL]) {
            s_sub_prep = true;
        }
        return;
    }
    if (w->len == 2 && (h == s_hc[C03_CCC] || h == s_hc[C04_CCC] || h == s_hc[C10_CCC] ||
                        h == s_hc[C11B_CCC] || h == s_hk[K_RES_CCC] || h == s_hk[K_SCO_CCC])) {
        cccd_write(h, (uint16_t)(w->value[0] | (w->value[1] << 8)));
    } else if (h == s_hc[C05A_VAL]) {
        if (trimmed_eq(w->value, w->len, s_unseal)) {
            esp_ble_gatts_set_attr_value(s_hc[C05B_VAL], (uint16_t)strlen(s_flag05),
                                         (const uint8_t *)s_flag05);
            ESP_LOGI(TAG, "BLE-05 hatch opened");
        }
    } else if (h == s_hk[K_SUB_VAL]) {
        submit_bytes(w->value, w->len);
    }
}

static void on_exec_write(const esp_ble_gatts_cb_param_t *p)
{
    esp_ble_gatts_send_response(s_gif, p->exec_write.conn_id, p->exec_write.trans_id,
                                ESP_GATT_OK, NULL);
    if (s_sub_prep && p->exec_write.exec_write_flag == ESP_GATT_PREP_WRITE_EXEC) {
        uint16_t len = 0;
        const uint8_t *v = NULL;
        if (esp_ble_gatts_get_attr_value(s_hk[K_SUB_VAL], &len, &v) == ESP_GATT_OK && v) {
            submit_bytes(v, len);
        }
    }
    s_sub_prep = false;
}

/* ---- callbacks --------------------------------------------------------- */

static void gap_cb(esp_gap_ble_cb_event_t event, esp_ble_gap_cb_param_t *param)
{
    switch (event) {
    case ESP_GAP_BLE_ADV_DATA_RAW_SET_COMPLETE_EVT:
    case ESP_GAP_BLE_SCAN_RSP_DATA_RAW_SET_COMPLETE_EVT:
        s_adv_cfg |= (event == ESP_GAP_BLE_ADV_DATA_RAW_SET_COMPLETE_EVT) ? 1 : 2;
        if (s_adv_cfg == 3 && !s_adv_started_once) {
            s_adv_started_once = true;
            adv_start();
        }
        break;
    case ESP_GAP_BLE_ADV_START_COMPLETE_EVT:
        if (param->adv_start_cmpl.status != ESP_BT_STATUS_SUCCESS) {
            ESP_LOGW(TAG, "advertising start failed: %d", param->adv_start_cmpl.status);
        }
        break;
    case ESP_GAP_BLE_SEC_REQ_EVT:
        esp_ble_gap_security_rsp(param->ble_security.ble_req.bd_addr, true);
        break;
    case ESP_GAP_BLE_PASSKEY_NOTIF_EVT:
        ESP_LOGI(TAG, "pairing: central must enter the passkey shown at boot");
        break;
    case ESP_GAP_BLE_NC_REQ_EVT:
        /* Not expected with display-only IO; reject numeric comparison. */
        esp_ble_confirm_reply(param->ble_security.ble_req.bd_addr, false);
        break;
    case ESP_GAP_BLE_AUTH_CMPL_EVT:
        if (param->ble_security.auth_cmpl.success) {
            ESP_LOGI(TAG, "pairing complete (auth mode 0x%02x)",
                     param->ble_security.auth_cmpl.auth_mode);
        } else {
            ESP_LOGW(TAG, "pairing failed, reason 0x%02x",
                     param->ble_security.auth_cmpl.fail_reason);
        }
        break;
    default:
        break;
    }
}

static void gatts_cb(esp_gatts_cb_event_t event, esp_gatt_if_t gatts_if,
                     esp_ble_gatts_cb_param_t *param)
{
    switch (event) {
    case ESP_GATTS_REG_EVT:
        if (param->reg.status != ESP_GATT_OK) {
            ESP_LOGE(TAG, "gatts app register failed: %d", param->reg.status);
            return;
        }
        s_gif = gatts_if;
        esp_ble_gap_set_device_name(s_name);
        adv_update();
        scan_rsp_config();
        esp_ble_gatts_create_attr_tab(s_tab_c, gatts_if, C_NB, 0);
        break;
    case ESP_GATTS_CREAT_ATTR_TAB_EVT: {
        bool chal = (s_tabs_done == 0);
        int nb = chal ? C_NB : K_NB;
        if (param->add_attr_tab.status != ESP_GATT_OK || param->add_attr_tab.num_handle != nb) {
            ESP_LOGE(TAG, "attr table %d failed: status %d, %d handles", s_tabs_done,
                     param->add_attr_tab.status, param->add_attr_tab.num_handle);
            return;
        }
        memcpy(chal ? s_hc : s_hk, param->add_attr_tab.handles, (size_t)nb * sizeof(uint16_t));
        s_tabs_done++;
        if (chal) {
            /* BLE-06 custom 128-bit descriptor (see the enum comment). */
            esp_bt_uuid_t du = {.len = ESP_UUID_LEN_128};
            uuid_fill(du.uuid.uuid128, UUID_BLE06_DSC);
            esp_attr_value_t dv = {
                .attr_max_len = (uint16_t)strlen(s_flag06),
                .attr_len = (uint16_t)strlen(s_flag06),
                .attr_value = (uint8_t *)s_flag06,
            };
            esp_attr_control_t ctl = {.auto_rsp = ESP_GATT_AUTO_RSP};
            esp_ble_gatts_add_char_descr(s_hc[C_SVC], &du, ESP_GATT_PERM_READ, &dv, &ctl);
        } else {
            esp_ble_gatts_start_service(s_hk[K_SVC]);
            s_score_txt[0] = '\0';
            score_update();
        }
        break;
    }
    case ESP_GATTS_ADD_CHAR_DESCR_EVT:
        if (param->add_char_descr.status != ESP_GATT_OK) {
            ESP_LOGE(TAG, "BLE-06 descriptor failed: %d", param->add_char_descr.status);
        }
        s_hc[C06_SECRET] = param->add_char_descr.attr_handle;
        esp_ble_gatts_start_service(s_hc[C_SVC]);
        break;
    case ESP_GATTS_START_EVT:
        /* Strictly serialise: a table creation must not overlap any other
         * pending GATTS operation (Bluedroid's create_attr_tab would take the
         * other completion as its own and assert in future_ready). */
        if (param->start.service_handle == s_hc[C_SVC] && s_tabs_done == 1) {
            esp_ble_gatts_create_attr_tab(s_tab_k, gatts_if, K_NB, 1);
        }
        break;
    case ESP_GATTS_CONNECT_EVT: {
        if (s_connected) {
            break;
        }
        reset_conn_state();
        s_conn_id = param->connect.conn_id;
        memcpy(s_peer, param->connect.remote_bda, sizeof(s_peer));
        s_connected = true;
        esp_ble_conn_update_params_t cp = {
            .min_int = 0x06, /* 7.5 ms */
            .max_int = 0x0C, /* 15 ms */
            .latency = 0,
            .timeout = 400,  /* 4 s */
        };
        memcpy(cp.bda, param->connect.remote_bda, sizeof(cp.bda));
        esp_ble_gap_update_conn_params(&cp);
        ESP_LOGI(TAG, "connected %02x:%02x:%02x:%02x:%02x:%02x", s_peer[0], s_peer[1],
                 s_peer[2], s_peer[3], s_peer[4], s_peer[5]);
        break;
    }
    case ESP_GATTS_DISCONNECT_EVT:
        if (param->disconnect.conn_id != s_conn_id) {
            break;
        }
        s_connected = false;
        reset_conn_state();
        esp_ble_gatts_set_attr_value(s_hc[C05B_VAL], (uint16_t)strlen(SEALED),
                                     (const uint8_t *)SEALED);
        ESP_LOGI(TAG, "disconnected (reason 0x%02x), advertising again",
                 param->disconnect.reason);
        adv_start();
        break;
    case ESP_GATTS_MTU_EVT:
        s_mtu = param->mtu.mtu;
        break;
    case ESP_GATTS_READ_EVT:
        if (!param->read.need_rsp) {
            break;
        }
        if (param->read.handle == s_hc[C10_VAL]) {
            char t[32];
            pin_status(t, sizeof(t));
            send_read(&param->read, t);
        } else if (param->read.handle == s_hc[C11A_VAL]) {
            send_read(&param->read, s_val11);
        } else {
            esp_ble_gatts_send_response(gatts_if, param->read.conn_id, param->read.trans_id,
                                        ESP_GATT_READ_NOT_PERMIT, NULL);
        }
        break;
    case ESP_GATTS_WRITE_EVT:
        on_write(&param->write);
        break;
    case ESP_GATTS_EXEC_WRITE_EVT:
        on_exec_write(param);
        break;
    case ESP_GATTS_CONF_EVT:
        if (param->conf.handle == s_hc[C04_VAL]) {
            on_frag_confirm(param->conf.status);
        }
        break;
    default:
        break;
    }
}

/* ---- console + init ---------------------------------------------------- */

static int cmd_ble(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    if (!s_bt_ready) {
        printf("Bluetooth is not running.\n");
        return 1;
    }
    const uint8_t *a = esp_bt_dev_get_address();
    printf("BLE name: %s\n", s_name);
    if (a) {
        printf("BLE address: %02X:%02X:%02X:%02X:%02X:%02X\n", a[0], a[1], a[2], a[3], a[4],
               a[5]);
    }
    printf("Connected: %s\n", s_connected ? "yes" : "no");
    return 0;
}

static bool bt_bringup(void)
{
    esp_err_t err;
    esp_bt_controller_config_t cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    if ((err = esp_bt_controller_init(&cfg)) != ESP_OK ||
        (err = esp_bt_controller_enable(ESP_BT_MODE_BTDM)) != ESP_OK) {
        ESP_LOGE(TAG, "BT controller init/enable failed: %s", esp_err_to_name(err));
        return false;
    }
    esp_bluedroid_config_t bcfg = BT_BLUEDROID_INIT_CONFIG_DEFAULT();
    if ((err = esp_bluedroid_init_with_cfg(&bcfg)) != ESP_OK ||
        (err = esp_bluedroid_enable()) != ESP_OK) {
        ESP_LOGE(TAG, "Bluedroid init/enable failed: %s", esp_err_to_name(err));
        return false;
    }
    return true;
}

static void security_config(void)
{
    esp_ble_auth_req_t auth = ESP_LE_AUTH_REQ_SC_MITM_BOND;
    esp_ble_io_cap_t iocap = ESP_IO_CAP_OUT; /* display only: the central types the passkey */
    uint8_t key_size = 16;
    uint8_t init_key = ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK;
    uint8_t rsp_key = ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK;
    uint8_t only_specified = ESP_BLE_ONLY_ACCEPT_SPECIFIED_AUTH_DISABLE;
    uint32_t passkey = s_passkey;
    esp_ble_gap_set_security_param(ESP_BLE_SM_SET_STATIC_PASSKEY, &passkey, sizeof(passkey));
    esp_ble_gap_set_security_param(ESP_BLE_SM_AUTHEN_REQ_MODE, &auth, sizeof(auth));
    esp_ble_gap_set_security_param(ESP_BLE_SM_IOCAP_MODE, &iocap, sizeof(iocap));
    esp_ble_gap_set_security_param(ESP_BLE_SM_MAX_KEY_SIZE, &key_size, sizeof(key_size));
    esp_ble_gap_set_security_param(ESP_BLE_SM_ONLY_ACCEPT_SPECIFIED_SEC_AUTH, &only_specified,
                                   sizeof(only_specified));
    esp_ble_gap_set_security_param(ESP_BLE_SM_SET_INIT_KEY, &init_key, sizeof(init_key));
    esp_ble_gap_set_security_param(ESP_BLE_SM_SET_RSP_KEY, &rsp_key, sizeof(rsp_key));
}

void track_ble_start(void)
{
    const esp_console_cmd_t cmd = {
        .command = "ble",
        .help = "Show the board's BLE name, address and connection state",
        .func = cmd_ble,
    };
    esp_console_cmd_register(&cmd);

    derive_values();
    build_tables();

    if (!bt_bringup()) {
        return;
    }
    s_bt_ready = true;

    esp_ble_gap_register_callback(gap_cb);
    esp_ble_gatts_register_callback(gatts_cb);
    security_config();
    esp_ble_gatt_set_local_mtu(LOCAL_MTU);
    esp_ble_gatts_app_register(APP_ID);

    const esp_timer_create_args_t targs = {.callback = tick_cb, .name = "ble_tick"};
    esp_timer_handle_t t;
    if (esp_timer_create(&targs, &t) == ESP_OK) {
        esp_timer_start_periodic(t, 1000 * 1000);
    }

    printf("ble passkey: %06" PRIu32 "\n", s_passkey);
    ESP_LOGI(TAG, "BLE up as %s; free heap after BT up: %u bytes (largest block %u)", s_name,
             (unsigned)heap_caps_get_free_size(MALLOC_CAP_8BIT),
             (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_8BIT));
}

bool track_ble_bt_ready(void)
{
    return s_bt_ready;
}
