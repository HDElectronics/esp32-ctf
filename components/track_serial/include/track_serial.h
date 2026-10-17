#pragma once
/* track_serial: challenge track (see docs/SPEC.md). SER-02..04 + CRY-01 shard 1. */
#ifdef __cplusplus
extern "C" {
#endif

/* Called from app_main after ctf_platform_init(), before ctf_console_start().
 * May register console commands and start tasks. */
void track_serial_start(void);

#ifdef __cplusplus
}
#endif
