#include "board.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "esp_log.h"
#include "sdkconfig.h"

static const char *TAG = "board_oled";

extern const uint8_t board_font5x7[95][5];

#define OLED_CTRL_CMD   0x00
#define OLED_CTRL_DATA  0x40

typedef struct {
    uint8_t addr;
    const char *name;
    uint8_t col_offset;
    bool sh1106;
} oled_cfg_t;

static const oled_cfg_t s_cfg[BOARD_OLED_COUNT] = {
    [BOARD_OLED_M1] = { BOARD_I2C_ADDR_OLED_M1, "SSD1306", 0, false },
    [BOARD_OLED_M3] = { BOARD_I2C_ADDR_OLED_M3, "SH1106", CONFIG_D32_SH1106_COL_OFFSET, true },
};

/* Page addressing mode works on both controllers (the SH1106 has no other). */
static const uint8_t s_init_ssd1306[] = {
    0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0x00, 0x40, 0x8D, 0x14, 0x20, 0x02,
    0xA1, 0xC8, 0xDA, 0x12, 0x81, 0xCF, 0xD9, 0xF1, 0xDB, 0x40, 0xA4, 0xA6, 0xAF,
};
static const uint8_t s_init_sh1106[] = {
    0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0x00, 0x40, 0xAD, 0x8B, 0xA1, 0xC8,
    0xDA, 0x12, 0x81, 0x80, 0xD9, 0x1F, 0xDB, 0x40, 0x33, 0xA4, 0xA6, 0xAF,
};

static i2c_master_dev_handle_t s_dev[BOARD_OLED_COUNT];
static uint8_t s_fb[BOARD_OLED_COUNT][BOARD_OLED_LINES][BOARD_OLED_WIDTH];
static uint8_t s_dirty[BOARD_OLED_COUNT];

static esp_err_t oled_cmds(board_oled_t d, const uint8_t *cmds, size_t n)
{
    uint8_t buf[32];
    if (n + 1 > sizeof(buf)) {
        return ESP_ERR_INVALID_SIZE;
    }
    buf[0] = OLED_CTRL_CMD;
    memcpy(buf + 1, cmds, n);
    return i2c_master_transmit(s_dev[d], buf, n + 1, BOARD_I2C_TIMEOUT_MS);
}

esp_err_t board_oled_init(void)
{
    int found = 0;
    for (int d = 0; d < BOARD_OLED_COUNT; d++) {
        if (s_dev[d]) {
            found++;
            continue;
        }
        const oled_cfg_t *c = &s_cfg[d];
        if (!board_i2c_ready() || board_i2c_probe(c->addr) != ESP_OK) {
            ESP_LOGW(TAG, "%s (0x%02X) not found", c->name, c->addr);
            continue;
        }
        if (board_i2c_add(c->addr, &s_dev[d]) != ESP_OK) {
            s_dev[d] = NULL;
            continue;
        }
        const uint8_t *seq = c->sh1106 ? s_init_sh1106 : s_init_ssd1306;
        size_t len = c->sh1106 ? sizeof(s_init_sh1106) : sizeof(s_init_ssd1306);
        if (oled_cmds((board_oled_t)d, seq, len) != ESP_OK) {
            ESP_LOGW(TAG, "%s init failed", c->name);
            board_i2c_remove(s_dev[d]);
            s_dev[d] = NULL;
            continue;
        }
        board_oled_clear((board_oled_t)d);
        board_oled_flush((board_oled_t)d);
        found++;
    }
    return found == BOARD_OLED_COUNT ? ESP_OK : (found ? ESP_ERR_NOT_FINISHED : ESP_ERR_NOT_FOUND);
}

void board_oled_deinit(void)
{
    for (int d = 0; d < BOARD_OLED_COUNT; d++) {
        if (s_dev[d]) {
            board_oled_power((board_oled_t)d, false);
            board_i2c_remove(s_dev[d]);
            s_dev[d] = NULL;
        }
    }
}

bool board_oled_present(board_oled_t d)
{
    return d < BOARD_OLED_COUNT && s_dev[d] != NULL;
}

void board_oled_clear(board_oled_t d)
{
    if (d >= BOARD_OLED_COUNT) {
        return;
    }
    memset(s_fb[d], 0, sizeof(s_fb[d]));
    s_dirty[d] = 0xFF;
}

void board_oled_text_at(board_oled_t d, int x, int line, const char *text, bool inverse)
{
    if (d >= BOARD_OLED_COUNT || line < 0 || line >= BOARD_OLED_LINES || !text) {
        return;
    }
    uint8_t *row = s_fb[d][line];
    for (; *text && x < BOARD_OLED_WIDTH; text++) {
        unsigned char ch = (unsigned char)*text;
        const uint8_t *g = board_font5x7[(ch >= 0x20 && ch <= 0x7E) ? ch - 0x20 : '?' - 0x20];
        for (int i = 0; i < 6 && x < BOARD_OLED_WIDTH; i++, x++) {
            uint8_t col = i < 5 ? g[i] : 0x00;
            if (x >= 0) {
                row[x] = inverse ? (uint8_t)~col : col;
            }
        }
    }
    s_dirty[d] |= (uint8_t)(1u << line);
}

void board_oled_line(board_oled_t d, int line, const char *text, bool inverse)
{
    if (d >= BOARD_OLED_COUNT || line < 0 || line >= BOARD_OLED_LINES) {
        return;
    }
    memset(s_fb[d][line], inverse ? 0xFF : 0x00, BOARD_OLED_WIDTH);
    board_oled_text_at(d, 0, line, text ? text : "", inverse);
}

void board_oled_printf(board_oled_t d, int line, const char *fmt, ...)
{
    char buf[BOARD_OLED_COLS + 1];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    board_oled_line(d, line, buf, false);
}

esp_err_t board_oled_flush(board_oled_t d)
{
    if (!board_oled_present(d)) {
        return ESP_ERR_INVALID_STATE;
    }
    uint8_t col = s_cfg[d].col_offset;
    uint8_t buf[1 + BOARD_OLED_WIDTH];
    for (int p = 0; p < BOARD_OLED_LINES; p++) {
        if (!(s_dirty[d] & (1u << p))) {
            continue;
        }
        const uint8_t addr[3] = { (uint8_t)(0xB0 | p), (uint8_t)(0x00 | (col & 0x0F)), (uint8_t)(0x10 | (col >> 4)) };
        esp_err_t err = oled_cmds(d, addr, sizeof(addr));
        if (err == ESP_OK) {
            buf[0] = OLED_CTRL_DATA;
            memcpy(buf + 1, s_fb[d][p], BOARD_OLED_WIDTH);
            err = i2c_master_transmit(s_dev[d], buf, sizeof(buf), BOARD_I2C_TIMEOUT_MS * 4);
        }
        if (err != ESP_OK) {
            return err;
        }
        s_dirty[d] &= (uint8_t)~(1u << p);
    }
    return ESP_OK;
}

esp_err_t board_oled_invert(board_oled_t d, bool on)
{
    if (!board_oled_present(d)) {
        return ESP_ERR_INVALID_STATE;
    }
    uint8_t c = on ? 0xA7 : 0xA6;
    return oled_cmds(d, &c, 1);
}

esp_err_t board_oled_contrast(board_oled_t d, uint8_t value)
{
    if (!board_oled_present(d)) {
        return ESP_ERR_INVALID_STATE;
    }
    const uint8_t c[2] = { 0x81, value };
    return oled_cmds(d, c, 2);
}

esp_err_t board_oled_power(board_oled_t d, bool on)
{
    if (!board_oled_present(d)) {
        return ESP_ERR_INVALID_STATE;
    }
    uint8_t c = on ? 0xAF : 0xAE;
    return oled_cmds(d, &c, 1);
}
