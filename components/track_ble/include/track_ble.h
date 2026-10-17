#pragma once
/* track_ble: BLE track BLE-01..11 + CTF control service (SPEC "BLE",
 * "Submission and scoreboard") and CRY-01 shard 2 (SPEC "Cross-track rules").
 * Also owns the shared Bluetooth bring-up: BT controller in BTDM (dual) mode
 * plus Bluedroid init + enable. Nothing Classic-related is released, so
 * track_btc can start its Classic profiles on top. */
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Called from app_main in radio mode, after ctf_platform_init() and before
 * track_btc_start() / ctf_console_start(). Brings Bluetooth up, starts the GATT
 * server and advertising, registers the `ble` console command. */
void track_ble_start(void);

/* True once the controller (BTDM) and Bluedroid are initialised and enabled. */
bool track_ble_bt_ready(void);

#ifdef __cplusplus
}
#endif
