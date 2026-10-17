#pragma once
/* track_btc: BT Classic track BTC-01..03 and CRY-01 shard 3 (SPEC "BT Classic",
 * "Cross-track rules"). Builds on track_ble's BTDM controller + Bluedroid. */
#ifdef __cplusplus
extern "C" {
#endif

/* Called from app_main in radio mode right after track_ble_start(), before
 * ctf_console_start(). Returns early if track_ble_bt_ready() is false.
 * Sets the BR/EDR name, CoD and EIR, enables SSP (Just Works), starts the
 * SPP server "CTF Console" and makes the board connectable + discoverable. */
void track_btc_start(void);

#ifdef __cplusplus
}
#endif
