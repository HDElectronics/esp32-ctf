/* track_crypto: CRY-01..03 console commands (SPEC "Crypto", "Cross-track rules").
 * AES via the IDF hardware AES driver (mbedtls port, aes/esp_aes.h). */
#include "track_crypto.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>
#include "aes/esp_aes.h"
#include "ctf_core.h"
#include "esp_console.h"
#include "esp_log.h"
#include "sdkconfig.h"

static const char *TAG = "track_crypto";

static void print_hex(const uint8_t *b, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        printf("%02x", b[i]);
    }
    printf("\n");
}

/* ---- CRY-01: Vigenere over the flag body ------------------------------- */

#define CRY01_SHARDS 4

/* Same rule as every track: shard i = 'A' + b % 26 of ctf_derive("CRY-01:shard<i>", 2). */
static void cry01_key(char key[2 * CRY01_SHARDS + 1])
{
    for (int i = 0; i < CRY01_SHARDS; i++) {
        char label[20];
        uint8_t b[2];
        snprintf(label, sizeof(label), "CRY-01:shard%d", i + 1);
        ctf_derive(label, b, sizeof(b));
        key[2 * i] = (char)('A' + b[0] % 26);
        key[2 * i + 1] = (char)('A' + b[1] % 26);
    }
    key[2 * CRY01_SHARDS] = '\0';
}

static int cmd_cipher(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    char key[2 * CRY01_SHARDS + 1];
    char body[CTF_FLAG_BODY_LEN + 1];
    cry01_key(key);
    ctf_flag_body("CRY-01", body);
    size_t k = 0, klen = strlen(key);
    for (size_t i = 0; body[i]; i++) {
        char c = body[i];
        if (c >= 'A' && c <= 'Z') { /* digits pass through, key does not advance */
            body[i] = (char)('A' + (c - 'A' + key[k % klen] - 'A') % 26);
            k++;
        }
    }
    printf("Intercepted: %s\n", body);
    memset(key, 0, sizeof(key));
    return 0;
}

/* ---- CRY-02: AES-128-ECB oracle over input || flag --------------------- */

#define CRY02_MAX_IN 64
#define CRY02_MAX_PT (CRY02_MAX_IN + CTF_FLAG_LEN + 16)

static int hexval(int c)
{
    if (c >= '0' && c <= '9') {
        return c - '0';
    }
    c = tolower(c);
    if (c >= 'a' && c <= 'f') {
        return c - 'a' + 10;
    }
    return -1;
}

static int cmd_oracle(int argc, char **argv)
{
    const char *hex = argc >= 2 ? argv[1] : "";
    size_t hl = strlen(hex);
    if (hl % 2 != 0 || hl / 2 > CRY02_MAX_IN) {
        printf("Usage: oracle <hex> (even number of hex digits, at most %d bytes)\n", CRY02_MAX_IN);
        return 1;
    }
    uint8_t pt[CRY02_MAX_PT];
    size_t n = 0;
    for (size_t i = 0; i < hl; i += 2) {
        int hi = hexval((unsigned char)hex[i]), lo = hexval((unsigned char)hex[i + 1]);
        if (hi < 0 || lo < 0) {
            printf("Usage: oracle <hex> (even number of hex digits, at most %d bytes)\n", CRY02_MAX_IN);
            return 1;
        }
        pt[n++] = (uint8_t)(hi << 4 | lo);
    }
    char flag[18];
    ctf_flag("CRY-02", flag);
    memcpy(pt + n, flag, CTF_FLAG_LEN);
    n += CTF_FLAG_LEN;
    uint8_t pad = (uint8_t)(16 - n % 16); /* PKCS#7 */
    memset(pt + n, pad, pad);
    n += pad;

    uint8_t key[16];
    ctf_derive("CRY-02:key", key, sizeof(key));
    esp_aes_context ctx;
    esp_aes_init(&ctx);
    int rc = esp_aes_setkey(&ctx, key, 128);
    for (size_t i = 0; rc == 0 && i < n; i += 16) {
        rc = esp_aes_crypt_ecb(&ctx, ESP_AES_ENCRYPT, pt + i, pt + i);
    }
    esp_aes_free(&ctx);
    memset(key, 0, sizeof(key));
    if (rc != 0) {
        printf("oracle: cipher error\n");
        return 1;
    }
    print_hex(pt, n);
    return 0;
}

/* ---- CRY-03: two AES-128-CTR messages under one key + nonce ------------ */

static const char CRY03_P1[] =
    "OPS STATUS 0412: relay mast B online, uplink nominal, battery 87%, next sync 0300Z";

static int ctr_encrypt(const uint8_t key[16], const uint8_t nonce[8],
                       const uint8_t *in, uint8_t *out, size_t len)
{
    uint8_t ctrblk[16] = {0}, stream[16];
    size_t off = 0;
    memcpy(ctrblk, nonce, 8); /* nonce || 64-bit counter from 0 */
    esp_aes_context ctx;
    esp_aes_init(&ctx);
    int rc = esp_aes_setkey(&ctx, key, 128);
    if (rc == 0) {
        rc = esp_aes_crypt_ctr(&ctx, len, &off, ctrblk, stream, in, out);
    }
    esp_aes_free(&ctx);
    return rc;
}

static int cmd_msgs(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    uint8_t key[16], nonce[8];
    ctf_derive("CRY-03:key", key, sizeof(key));
    ctf_derive("CRY-03:nonce", nonce, sizeof(nonce));

    char p2[32];
    char flag[18];
    ctf_flag("CRY-03", flag);
    int p2len = snprintf(p2, sizeof(p2), "flag: %s", flag);

    uint8_t c1[sizeof(CRY03_P1)], c2[sizeof(p2)];
    size_t p1len = sizeof(CRY03_P1) - 1;
    int rc = ctr_encrypt(key, nonce, (const uint8_t *)CRY03_P1, c1, p1len);
    if (rc == 0) {
        rc = ctr_encrypt(key, nonce, (const uint8_t *)p2, c2, (size_t)p2len);
    }
    memset(key, 0, sizeof(key));
    memset(p2, 0, sizeof(p2));
    if (rc != 0) {
        printf("msgs: cipher error\n");
        return 1;
    }
    printf("Captured 2 messages (AES-128-CTR).\n");
    printf("msg 1 plaintext (recovered earlier): %s\n", CRY03_P1);
    printf("msg 1 ciphertext: ");
    print_hex(c1, p1len);
    printf("msg 2 ciphertext: ");
    print_hex(c2, (size_t)p2len);
    return 0;
}

/* ---- entry ------------------------------------------------------------- */

void track_crypto_start(void)
{
    static const esp_console_cmd_t cmds[] = {
        { .command = "cipher", .help = "Show an intercepted classic-cipher message",
          .func = cmd_cipher },
        { .command = "oracle", .help = "Encrypt your data with the vault's block cipher",
          .hint = "<hex>", .func = cmd_oracle },
        { .command = "msgs", .help = "Show captured encrypted operator messages",
          .func = cmd_msgs },
    };
    for (size_t i = 0; i < sizeof(cmds) / sizeof(cmds[0]); i++) {
        ESP_ERROR_CHECK(esp_console_cmd_register(&cmds[i]));
    }
#if CONFIG_CTF_CRYPTO_DEV
    char key[2 * CRY01_SHARDS + 1];
    cry01_key(key);
    ESP_LOGW(TAG, "DEV self-test: CRY-01 shards %.2s %.2s %.2s %.2s",
             key, key + 2, key + 4, key + 6);
#else
    (void)TAG;
#endif
}
