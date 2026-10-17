#pragma once
/* ctf_sha256: portable SHA-256 and HMAC-SHA256 (FIPS 180-4, RFC 2104).
 * Own implementation so host tests and the device produce identical output.
 * Must not include IDF/FreeRTOS headers. */
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CTF_SHA256_LEN   32
#define CTF_SHA256_BLOCK 64

typedef struct {
    uint32_t h[8];
    uint64_t total;               /* bytes hashed so far */
    uint8_t buf[CTF_SHA256_BLOCK];
    size_t used;                  /* bytes pending in buf */
} ctf_sha256_ctx_t;

void ctf_sha256_init(ctf_sha256_ctx_t *c);
void ctf_sha256_update(ctf_sha256_ctx_t *c, const void *data, size_t len);
void ctf_sha256_final(ctf_sha256_ctx_t *c, uint8_t out[CTF_SHA256_LEN]);
void ctf_sha256(const void *data, size_t len, uint8_t out[CTF_SHA256_LEN]);

typedef struct {
    ctf_sha256_ctx_t inner;
    ctf_sha256_ctx_t outer;
} ctf_hmac_ctx_t;

void ctf_hmac_init(ctf_hmac_ctx_t *c, const void *key, size_t key_len);
void ctf_hmac_update(ctf_hmac_ctx_t *c, const void *data, size_t len);
void ctf_hmac_final(ctf_hmac_ctx_t *c, uint8_t out[CTF_SHA256_LEN]);
void ctf_hmac_sha256(const void *key, size_t key_len, const void *data, size_t len,
                     uint8_t out[CTF_SHA256_LEN]);

#ifdef __cplusplus
}
#endif
