/* TM1637 4-digit 7-segment display (timer plate), bit-banged on GPIO32 (CLK)
 * and GPIO33 (DIO), open drain with the module's pull-ups. The colon is the
 * DP bit of digit 2 on the usual 0.56" clock modules. */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Probes the chip (ACK on a command). ESP_ERR_NOT_FOUND if no ACK. */
esp_err_t board_tm1637_init(void);
void board_tm1637_deinit(void);
bool board_tm1637_present(void);

/* Raw segments (bit0 = a ... bit6 = g, bit7 = DP/colon), digit 0 = left. */
esp_err_t board_tm1637_segments(const uint8_t seg[4]);
/* Characters: '0'-'9', 'A'-'F'/'a'-'f', '-', '_', ' ' (others blank). */
esp_err_t board_tm1637_text(const char *four, bool colon);
/* MM:SS (minutes clipped to 99). */
esp_err_t board_tm1637_time(int minutes, int seconds, bool colon);
/* Brightness 0-7; on = false blanks the display. */
esp_err_t board_tm1637_brightness(uint8_t level, bool on);
/* Segment pattern for one character. */
uint8_t board_tm1637_glyph(char c);

#ifdef __cplusplus
}
#endif
