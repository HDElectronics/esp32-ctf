#pragma once
/* Internal to ctf_platform. */
#include "ctf_platform.h"

void ctf_commands_register(void);

/* Saves mode to NVS (no output, no reboot). */
void ctf_platform_save_mode(ctf_mode_t mode);

/* Runs one machine-channel line (the text after the 0x01 byte, NUL-terminated,
 * may be modified) and prints exactly one `\x02<json>\x03\r\n` frame with a
 * single write, so other tasks' output cannot land inside it. */
void ctf_api_run(char *line);
