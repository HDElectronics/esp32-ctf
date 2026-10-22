/* 128x64 I2C OLED text driver: SSD1306 0.96" (radio plate, 0x3C) and SH1106
 * 1.3" (keypad plate, 0x3D, column offset CONFIG_D32_SH1106_COL_OFFSET).
 * 5x7 font in 6x8 cells: 8 lines of 21 characters. Drawing goes to a RAM
 * framebuffer; board_oled_flush() sends the changed pages. */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BOARD_OLED_M1 = 0,  /* radio plate, SSD1306, 0x3C */
    BOARD_OLED_M3 = 1,  /* keypad plate, SH1106, 0x3D */
    BOARD_OLED_COUNT
} board_oled_t;

#define BOARD_OLED_WIDTH    128
#define BOARD_OLED_HEIGHT   64
#define BOARD_OLED_LINES    8
#define BOARD_OLED_COLS     21

esp_err_t board_oled_init(void);
void board_oled_deinit(void);
bool board_oled_present(board_oled_t d);

/* Framebuffer operations (no I2C traffic). */
void board_oled_clear(board_oled_t d);
/* Replace a whole line (0-7); `inverse` draws light background. */
void board_oled_line(board_oled_t d, int line, const char *text, bool inverse);
void board_oled_printf(board_oled_t d, int line, const char *fmt, ...) __attribute__((format(printf, 3, 4)));
/* Text at pixel column x on a line, without clearing the rest. */
void board_oled_text_at(board_oled_t d, int x, int line, const char *text, bool inverse);

/* Send changed pages. */
esp_err_t board_oled_flush(board_oled_t d);
/* Whole-display hardware invert. */
esp_err_t board_oled_invert(board_oled_t d, bool on);
esp_err_t board_oled_contrast(board_oled_t d, uint8_t value);
esp_err_t board_oled_power(board_oled_t d, bool on);

#ifdef __cplusplus
}
#endif
