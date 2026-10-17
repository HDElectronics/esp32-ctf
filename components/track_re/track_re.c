/* track_re: firmware reversing track RE-01..04 (SPEC "Firmware reversing").
 *
 * Provisioning runs at every boot and is idempotent: each artefact is read
 * back and compared first, and only rewritten when missing or different
 * (fresh board, erased flash, `reset yes`, or a different MAC).
 *   RE-01  plaintext operator notes (with the flag) in the raw `notes` partition
 *   RE-02  NVS "vault"/"k" = flag XOR one per-board byte
 *   RE-03  NVS "vault"/"chk" = fold(per-board key); `unlock <key>` checks it
 *   RE-04  /storage/blob.bin = "XBLOB1" || flag XOR LFSR keystream (MAC seed)
 */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_console.h"
#include "esp_log.h"
#include "esp_partition.h"
#include "esp_spiffs.h"
#include "nvs.h"

#include "ctf_core.h"
#include "ctf_platform.h"
#include "track_re.h"

static const char *TAG = "track_re";

#define RE_NOTES_LABEL   "notes"
#define RE_NOTES_SUBTYPE 0x40
#define RE_VAULT_NS      "vault"
#define RE_KEY_LEN       12
#define RE_BLOB_PATH     "/storage/blob.bin"
#define RE_BLOB_MAGIC    "XBLOB1"
#define RE_BLOB_MAGIC_LEN 6

/* ---------------------------------------------------------------- RE-01 */

static const char *provision_notes(void)
{
    const esp_partition_t *p = esp_partition_find_first(
        ESP_PARTITION_TYPE_DATA, (esp_partition_subtype_t)RE_NOTES_SUBTYPE, RE_NOTES_LABEL);
    if (p == NULL) {
        ESP_LOGE(TAG, "notes partition missing");
        return "missing";
    }

    char flag[18];
    ctf_flag("RE-01", flag);

    char *text = malloc(512);
    char *old = malloc(512);
    if (text == NULL || old == NULL) {
        free(text);
        free(old);
        return "nomem";
    }
    int n = snprintf(text, 512,
                     "=== FIELD UNIT OPERATOR NOTES (rev 3) ===\n"
                     "- unit ships sealed; do not erase the vault namespace\n"
                     "- asset store lives on /storage, blobs are XBLOB1 framed\n"
                     "- factory unlock console: key is per unit, ask the bench\n"
                     "- maintenance token: %s\n"
                     "- rotate the token after every field visit\n"
                     "=== END OF NOTES ===\n",
                     flag);
    size_t len = (size_t)n + 1; /* keep the NUL so the old tail can't merge */

    const char *res = "ok";
    if (len > p->size || esp_partition_read(p, 0, old, len) != ESP_OK ||
        memcmp(old, text, len) != 0) {
        res = "written";
        if (esp_partition_erase_range(p, 0, p->size) != ESP_OK ||
            esp_partition_write(p, 0, text, len) != ESP_OK) {
            ESP_LOGE(TAG, "notes write failed");
            res = "error";
        }
    }
    free(text);
    free(old);
    return res;
}

/* ------------------------------------------------------------ RE-02/03 */

/* Writes key=data as a blob unless an identical value is already stored.
 * Returns true if a write happened (caller commits). */
static bool vault_put(nvs_handle_t h, const char *key, const uint8_t *data, size_t len,
                      bool *err)
{
    uint8_t cur[32];
    size_t sz = sizeof(cur);
    if (len <= sizeof(cur) && nvs_get_blob(h, key, cur, &sz) == ESP_OK && sz == len &&
        memcmp(cur, data, len) == 0) {
        return false;
    }
    if (nvs_set_blob(h, key, data, len) != ESP_OK) {
        *err = true;
    }
    return true;
}

/* Key check routine used by `unlock`: 12 bytes in, 12 bytes out.
 * Per byte: xor with a rolling value, rotate left by 1..4, add an index term;
 * the rolling value then absorbs the output byte. Invertible byte by byte. */
static void __attribute__((noinline)) re_fold(const uint8_t *in, uint8_t *out)
{
    uint8_t r = 0xA7;
    for (int i = 0; i < RE_KEY_LEN; i++) {
        uint8_t x = in[i] ^ r;
        unsigned s = (unsigned)(i & 3) + 1u;
        x = (uint8_t)((x << s) | (x >> (8u - s)));
        x = (uint8_t)(x + 0x33u + (unsigned)i * 0x1Du);
        out[i] = x;
        r = (uint8_t)(r * 5u + x);
    }
}

/* Per-board unlock key: 12 printable characters. */
static void make_key(uint8_t key[RE_KEY_LEN])
{
    static const char alphabet[] =
        "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
    uint8_t raw[RE_KEY_LEN];
    ctf_derive("RE-03:key", raw, sizeof(raw));
    for (int i = 0; i < RE_KEY_LEN; i++) {
        key[i] = (uint8_t)alphabet[raw[i] % (sizeof(alphabet) - 1)];
    }
    memset(raw, 0, sizeof(raw));
}

static const char *provision_vault(void)
{
    nvs_handle_t h;
    if (nvs_open(RE_VAULT_NS, NVS_READWRITE, &h) != ESP_OK) {
        ESP_LOGE(TAG, "vault open failed");
        return "error";
    }
    bool err = false;
    bool wrote = false;

    /* RE-02 */
    char flag[18];
    ctf_flag("RE-02", flag);
    uint8_t xb;
    ctf_derive("RE-02:xor", &xb, 1);
    if (xb == 0) {
        xb = 0xA5;
    }
    uint8_t enc[CTF_FLAG_LEN];
    for (int i = 0; i < CTF_FLAG_LEN; i++) {
        enc[i] = (uint8_t)flag[i] ^ xb;
    }
    wrote |= vault_put(h, "k", enc, sizeof(enc), &err);

    /* RE-03: only the folded key is stored, never the key itself. */
    uint8_t key[RE_KEY_LEN], chk[RE_KEY_LEN];
    make_key(key);
    re_fold(key, chk);
    memset(key, 0, sizeof(key));
    wrote |= vault_put(h, "chk", chk, sizeof(chk), &err);

    if (wrote && nvs_commit(h) != ESP_OK) {
        err = true;
    }
    nvs_close(h);
    return err ? "error" : (wrote ? "written" : "ok");
}

static int cmd_unlock(int argc, char **argv)
{
    if (argc != 2) {
        printf("Usage: unlock <key>\n");
        return 1;
    }
    uint8_t want[RE_KEY_LEN];
    size_t sz = sizeof(want);
    nvs_handle_t h;
    bool ok = nvs_open(RE_VAULT_NS, NVS_READONLY, &h) == ESP_OK;
    if (ok) {
        ok = nvs_get_blob(h, "chk", want, &sz) == ESP_OK && sz == sizeof(want);
        nvs_close(h);
    }
    if (!ok) {
        printf("unlock: vault unavailable\n");
        return 1;
    }
    const char *in = argv[1];
    if (strlen(in) != RE_KEY_LEN) {
        printf("Access denied.\n");
        return 0;
    }
    uint8_t got[RE_KEY_LEN];
    re_fold((const uint8_t *)in, got);
    uint8_t diff = 0;
    for (int i = 0; i < RE_KEY_LEN; i++) {
        diff |= (uint8_t)(got[i] ^ want[i]);
    }
    memset(got, 0, sizeof(got));
    if (diff != 0) {
        printf("Access denied.\n");
        return 0;
    }
    char flag[18];
    ctf_flag("RE-03", flag);
    printf("Access granted. Factory token: %s\n", flag);
    return 0;
}

/* ---------------------------------------------------------------- RE-04 */

/* 32-bit Galois LFSR, right shift, taps x^32 + x^22 + x^2 + x + 1. */
static uint32_t lfsr_step(uint32_t s)
{
    uint32_t lsb = s & 1u;
    s >>= 1;
    if (lsb) {
        s ^= 0x80200003u;
    }
    return s;
}

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

static const char *provision_blob(void)
{
    if (!mount_storage()) {
        return "error";
    }
    uint8_t mac[6];
    ctf_platform_mac(mac);
    uint32_t s = ((uint32_t)mac[2] << 24 | (uint32_t)mac[3] << 16 |
                  (uint32_t)mac[4] << 8 | (uint32_t)mac[5]) ^ 0x5A17C3E9u;
    if (s == 0) {
        s = 1;
    }

    char flag[18];
    ctf_flag("RE-04", flag);
    uint8_t blob[RE_BLOB_MAGIC_LEN + CTF_FLAG_LEN];
    memcpy(blob, RE_BLOB_MAGIC, RE_BLOB_MAGIC_LEN);
    for (int i = 0; i < CTF_FLAG_LEN; i++) {
        for (int k = 0; k < 8; k++) {
            s = lfsr_step(s);
        }
        blob[RE_BLOB_MAGIC_LEN + i] = (uint8_t)flag[i] ^ (uint8_t)s;
    }

    uint8_t cur[sizeof(blob) + 1];
    FILE *f = fopen(RE_BLOB_PATH, "rb");
    if (f != NULL) {
        size_t n = fread(cur, 1, sizeof(cur), f);
        fclose(f);
        if (n == sizeof(blob) && memcmp(cur, blob, sizeof(blob)) == 0) {
            return "ok";
        }
    }
    f = fopen(RE_BLOB_PATH, "wb");
    if (f == NULL) {
        ESP_LOGE(TAG, "cannot create %s", RE_BLOB_PATH);
        return "error";
    }
    bool good = fwrite(blob, 1, sizeof(blob), f) == sizeof(blob);
    good &= fclose(f) == 0;
    return good ? "written" : "error";
}

/* --------------------------------------------------------------- start */

void track_re_start(void)
{
    const char *notes = provision_notes();
    const char *vault = provision_vault();
    const char *blob = provision_blob();
    ESP_LOGI(TAG, "artefacts: notes %s, vault %s, blob %s", notes, vault, blob);

    const esp_console_cmd_t unlock = {
        .command = "unlock",
        .help = "Factory unlock: unlock <key>",
        .hint = "<key>",
        .func = cmd_unlock,
    };
    ESP_ERROR_CHECK(esp_console_cmd_register(&unlock));
}
