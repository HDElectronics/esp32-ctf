/* UART2 on the probe plate header (TX GPIO17, RX GPIO16), 8N1. */
#pragma once

#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Install the driver (or change the baud rate if already installed). */
esp_err_t board_uart2_init(uint32_t baud);
void board_uart2_deinit(void);
/* Returns bytes written, or -1. */
int board_uart2_write(const void *data, size_t len);
/* Returns bytes read (0 on timeout), or -1. */
int board_uart2_read(void *buf, size_t len, uint32_t timeout_ms);

#ifdef __cplusplus
}
#endif
