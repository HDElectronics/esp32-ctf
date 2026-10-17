/* SHA-256 (FIPS 180-4 examples) and HMAC-SHA256 (RFC 4231 cases 1-4, 6, 7). */
#include <string.h>

#include "ctf_sha256.h"
#include "test_util.h"

static void to_hex(const uint8_t *d, size_t n, char *out)
{
    static const char hex[] = "0123456789abcdef";
    for (size_t i = 0; i < n; i++) {
        out[2 * i] = hex[d[i] >> 4];
        out[2 * i + 1] = hex[d[i] & 0x0f];
    }
    out[2 * n] = '\0';
}

static bool sha_is(const void *data, size_t len, const char *want)
{
    uint8_t d[CTF_SHA256_LEN];
    char h[2 * CTF_SHA256_LEN + 1];
    ctf_sha256(data, len, d);
    to_hex(d, sizeof(d), h);
    return strcmp(h, want) == 0;
}

static bool hmac_is(const void *key, size_t klen, const void *data, size_t dlen, const char *want)
{
    uint8_t d[CTF_SHA256_LEN];
    char h[2 * CTF_SHA256_LEN + 1];
    ctf_hmac_sha256(key, klen, data, dlen, d);
    to_hex(d, sizeof(d), h);
    return strcmp(h, want) == 0;
}

static void test_sha256_vectors(void)
{
    CHECK(sha_is("", 0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"));
    CHECK(sha_is("abc", 3, "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"));
    const char *m2 = "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
    CHECK(sha_is(m2, strlen(m2), "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"));
}

static void test_sha256_streaming(void)
{
    /* One million 'a' fed in odd-sized chunks exercises buffering + padding. */
    static uint8_t chunk[997];
    memset(chunk, 'a', sizeof(chunk));
    ctf_sha256_ctx_t c;
    ctf_sha256_init(&c);
    size_t left = 1000000;
    while (left) {
        size_t n = left < sizeof(chunk) ? left : sizeof(chunk);
        ctf_sha256_update(&c, chunk, n);
        left -= n;
    }
    uint8_t d[CTF_SHA256_LEN];
    char h[2 * CTF_SHA256_LEN + 1];
    ctf_sha256_final(&c, d);
    to_hex(d, sizeof(d), h);
    CHECK(strcmp(h, "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0") == 0);

    /* Every length 0..130 split at every point matches one-shot. */
    uint8_t msg[130];
    for (size_t i = 0; i < sizeof(msg); i++) {
        msg[i] = (uint8_t)(i * 7 + 3);
    }
    bool ok = true;
    for (size_t len = 0; len <= sizeof(msg); len++) {
        uint8_t one[CTF_SHA256_LEN];
        ctf_sha256(msg, len, one);
        for (size_t cut = 0; cut <= len; cut++) {
            uint8_t two[CTF_SHA256_LEN];
            ctf_sha256_init(&c);
            ctf_sha256_update(&c, msg, cut);
            ctf_sha256_update(&c, msg + cut, len - cut);
            ctf_sha256_final(&c, two);
            ok = ok && memcmp(one, two, sizeof(one)) == 0;
        }
    }
    CHECK(ok);
}

static void test_hmac_rfc4231(void)
{
    uint8_t k[131];
    uint8_t d[50];

    /* Case 1 */
    memset(k, 0x0b, 20);
    CHECK(hmac_is(k, 20, "Hi There", 8,
                  "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"));
    /* Case 2 */
    CHECK(hmac_is("Jefe", 4, "what do ya want for nothing?", 28,
                  "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"));
    /* Case 3 */
    memset(k, 0xaa, 20);
    memset(d, 0xdd, 50);
    CHECK(hmac_is(k, 20, d, 50,
                  "773ea91e36800e46854db8ebd09181a72959098b3ef8c122d9635514ced565fe"));
    /* Case 4 */
    for (int i = 0; i < 25; i++) {
        k[i] = (uint8_t)(i + 1);
    }
    memset(d, 0xcd, 50);
    CHECK(hmac_is(k, 25, d, 50,
                  "82558a389a443c0ea4cc819899f2083a85f0faa3e578f8077a2e3ff46729665b"));
    /* Case 6 */
    memset(k, 0xaa, 131);
    const char *m6 = "Test Using Larger Than Block-Size Key - Hash Key First";
    CHECK(hmac_is(k, 131, m6, strlen(m6),
                  "60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54"));
    /* Case 7 */
    const char *m7 = "This is a test using a larger than block-size key and a larger than "
                     "block-size data. The key needs to be hashed before being used by the "
                     "HMAC algorithm.";
    CHECK(hmac_is(k, 131, m7, strlen(m7),
                  "9b09ffa71b942fcb27635fbcd5b0e944bfdc63644f0713938a7f51535c3a35e2"));

    /* Incremental HMAC matches one-shot. */
    ctf_hmac_ctx_t h;
    uint8_t a[CTF_SHA256_LEN], b[CTF_SHA256_LEN];
    ctf_hmac_init(&h, k, 131);
    ctf_hmac_update(&h, m7, 10);
    ctf_hmac_update(&h, m7 + 10, strlen(m7) - 10);
    ctf_hmac_final(&h, a);
    ctf_hmac_sha256(k, 131, m7, strlen(m7), b);
    CHECK(memcmp(a, b, sizeof(a)) == 0);
}

void run_crypto_tests(void)
{
    RUN(test_sha256_vectors);
    RUN(test_sha256_streaming);
    RUN(test_hmac_rfc4231);
}
