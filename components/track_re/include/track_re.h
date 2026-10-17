#pragma once
/* track_re: firmware reversing track RE-01..04 (see docs/SPEC.md).
 * Provisions the notes partition, NVS "vault" and /storage/blob.bin (mounts
 * SPIFFS `storage` if nobody has yet), and registers `unlock`. */
#ifdef __cplusplus
extern "C" {
#endif

/* Called from app_main after ctf_platform_init(), before ctf_console_start().
 * May register console commands and start tasks. */
void track_re_start(void);

#ifdef __cplusplus
}
#endif
