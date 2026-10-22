/* PN532 V3 NFC module (sensor plate, I2C 0x24). Stub: presence probe only.
 * TODO: PN532 I2C framing (preamble/LEN/LCS/TFI/DCS, ready-status byte),
 * SAMConfiguration, InListPassiveTarget for ISO14443A UIDs. */
#pragma once

#include <stdbool.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t board_nfc_init(void);
void board_nfc_deinit(void);
/* True if 0x24 acknowledged at init. A sleeping PN532 may not ACK until
 * woken, so absent here is not conclusive. */
bool board_nfc_present(void);

#ifdef __cplusplus
}
#endif
