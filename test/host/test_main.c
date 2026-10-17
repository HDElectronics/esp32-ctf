/* Minimal host test runner for components/ctf_core (no external deps). */
#include <string.h>

#include "test_util.h"

int g_failures;
int g_checks;

const uint8_t TEST_MAC_A[6] = {0x24, 0x6f, 0x28, 0x12, 0x34, 0x56};
const uint8_t TEST_MAC_B[6] = {0x24, 0x6f, 0x28, 0x12, 0x34, 0x57};

static bool mem_load(void *buf, size_t len, void *ctx)
{
    mem_store_t *m = ctx;
    if (!m->has || m->len != len) {
        return false;
    }
    memcpy(buf, m->buf, len);
    return true;
}

static bool mem_save(const void *buf, size_t len, void *ctx)
{
    mem_store_t *m = ctx;
    if (len > sizeof(m->buf)) {
        return false;
    }
    memcpy(m->buf, buf, len);
    m->len = len;
    m->has = true;
    m->saves++;
    return true;
}

static void mem_lock(void *ctx)
{
    mem_store_t *m = ctx;
    m->locks++;
    if (++m->depth > m->max_depth) {
        m->max_depth = m->depth;
    }
}

static void mem_unlock(void *ctx)
{
    mem_store_t *m = ctx;
    m->depth--;
}

void mem_store_clear(mem_store_t *m)
{
    memset(m, 0, sizeof(*m));
}

ctf_backend_t mem_backend(mem_store_t *m)
{
    ctf_backend_t be = {mem_load, mem_save, mem_lock, mem_unlock, m};
    return be;
}

int main(void)
{
    run_crypto_tests();
    run_catalog_tests();
    run_flag_tests();
    run_progress_tests();
    printf("%d checks, %d failures\n", g_checks, g_failures);
    return g_failures ? 1 : 0;
}
