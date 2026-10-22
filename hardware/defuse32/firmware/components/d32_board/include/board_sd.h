/* microSD (rev 1) on the shared VSPI bus (SCK18/MOSI23/MISO19, CS GPIO2),
 * SDSPI + FATFS at /sd. Card detect is read through U2 GPB5 (board_input.h:
 * board_sd_card_detected()).
 *
 * While the card is mounted the ESP32 owns SCK/MOSI, which the probe plate's
 * SPI header shares: unmount before a challenge that lets players drive that
 * bus. */
#pragma once

#include <stdbool.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Mount at BOARD_SD_MOUNT_POINT (never formats). Initialises the SPI bus on
 * first use. */
esp_err_t board_sd_mount(void);
/* Unmount, free the SPI bus (SCK/MOSI released) and park CS high. */
esp_err_t board_sd_unmount(void);
/* Drive CS (GPIO2) high so an unmounted card stays deselected; board_init()
 * calls it, board_sd_unmount() too. */
void board_sd_park_cs(void);
bool board_sd_mounted(void);
/* Card name and size for logs ("-" if not mounted). */
void board_sd_info(char *buf, int len);

#ifdef __cplusplus
}
#endif
