#pragma once
/* ctf_platform: IDF glue for the CTF engine (SPEC "Architecture", "Modes").
 * - NVS-backed ctf_core backend (namespace "ctf", blob "progress"), board MAC.
 * - Mode (radio / net) stored in NVS "ctf"/"mode"; survives `reset`.
 * - UART0 console: small line editor feeding esp_console_run(), with an
 *   optional raw-byte hook for tracks (SER-03 timing, SER-04 escape sequence).
 * Tracks register their own commands with esp_console_cmd_register() after
 * ctf_platform_init() and before ctf_console_start(). */
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum { CTF_MODE_RADIO = 0, CTF_MODE_NET = 1 } ctf_mode_t;

/* NVS init, MAC read, engine init (ctf_init), esp_console_init and the core
 * commands. Call first in app_main. */
void ctf_platform_init(void);

/* Board base MAC (as passed to ctf_init). */
void ctf_platform_mac(uint8_t mac[6]);

ctf_mode_t ctf_platform_mode(void);
const char *ctf_platform_mode_name(ctf_mode_t mode); /* "radio" / "net" */
/* Saves mode to NVS and restarts; does not return. */
void ctf_platform_set_mode_and_reboot(ctf_mode_t mode);

/* Raw console byte hook: called for every byte read from UART0 before the line
 * editor sees it, with esp_timer time in microseconds. Return true to consume
 * the byte (the editor then ignores it). NULL removes the hook. */
typedef bool (*ctf_console_byte_hook_t)(uint8_t b, int64_t t_us);
void ctf_console_set_byte_hook(ctf_console_byte_hook_t hook);

/* Starts the console task (prompt "ctf> "). Call after all commands are registered. */
void ctf_console_start(void);

#ifdef __cplusplus
}
#endif
