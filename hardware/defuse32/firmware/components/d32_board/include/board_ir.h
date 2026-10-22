/* VS1838B IR receiver on GPIO34 (active low), RMT RX + NEC decoder running
 * in a small background task. Decoded frames are queued (depth 8). */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint16_t address;   /* 8-bit address (if its inverse matched) or 16-bit extended address */
    uint8_t command;
    bool repeat;        /* NEC repeat code: address/command repeat the last frame */
    uint32_t raw;       /* 32 data bits as received, LSB first */
} board_ir_code_t;

esp_err_t board_ir_init(void);
void board_ir_deinit(void);
bool board_ir_ready(void);
/* Wait up to timeout_ms for a decoded frame. */
bool board_ir_get(board_ir_code_t *out, uint32_t timeout_ms);
/* Drop queued frames. */
void board_ir_flush(void);

#ifdef __cplusplus
}
#endif
