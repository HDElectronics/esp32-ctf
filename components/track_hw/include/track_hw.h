#pragma once
/* track_hw: challenge track (see docs/SPEC.md). Stub until its task lands. */
#ifdef __cplusplus
extern "C" {
#endif

/* Called from app_main after ctf_platform_init(), before ctf_console_start().
 * May register console commands and start tasks. */
void track_hw_start(void);

#ifdef __cplusplus
}
#endif
