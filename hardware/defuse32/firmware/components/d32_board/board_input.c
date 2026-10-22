#include "board.h"

#include "esp_rom_sys.h"
#include "sdkconfig.h"

/* Rev 1b strobe lines (16-bit MCP pin masks, low byte = GPA, high = GPB).
 * Keypad on U2: rows GPA0-3 (inputs), columns COL1-3 = GPA4-6, COL4 = GPB6.
 * Wires on U3: WA1-5 = GPA0-4, WA6 = GPB6 (strobes); WB1-6 = GPB0-5 (inputs).
 * None of the strobes is an output-only pin (GPA7/GPB7). */
#define KP_ROW_MASK     0x000Fu
#define KP_STROBE_MASK  0x4070u
#define WA_STROBE_MASK  0x401Fu
#define WB_SHIFT        8
#define WB_MASK         0x3Fu   /* port B bits 0-5 */

#define KP_DEBOUNCE     3

static const char s_keymap[BOARD_KEYPAD_KEYS] = {
    '1', '2', '3', 'A',
    '4', '5', '6', 'B',
    '7', '8', '9', 'C',
    '0', 'F', 'E', 'D',
};

static const uint8_t s_kp_col_pin[4] = {
    BOARD_U2_KP_COL1, BOARD_U2_KP_COL2, BOARD_U2_KP_COL3, BOARD_U2_KP_COL4,
};
static const uint8_t s_wa_pin[BOARD_WIRE_POSTS] = {
    BOARD_U3_WA1, BOARD_U3_WA2, BOARD_U3_WA3, BOARD_U3_WA4, BOARD_U3_WA5, BOARD_U3_WA6,
};

/* Open-drain strobe emulation: drive strobe `pin` low and switch every other
 * strobe in `strobe_mask` to input (high impedance), so only one line is
 * driven at a time. pin < 0: idle, every strobe an output driven low (all at
 * the same level, so a pressed key pair or a lead cannot short two drivers). */
static esp_err_t strobe(board_mcp_t m, uint16_t strobe_mask, int pin)
{
    uint16_t iodir = 0;
    if (pin >= 0) {
        iodir = (uint16_t)(strobe_mask & ~(1u << pin));
    }
    return board_mcp_port(m, strobe_mask, iodir, 0);
}

char board_keypad_char(int index)
{
    return (index >= 0 && index < BOARD_KEYPAD_KEYS) ? s_keymap[index] : '?';
}

esp_err_t board_keypad_scan(uint16_t *pressed)
{
    if (!board_mcp_present(BOARD_MCP_U2)) {
        return ESP_ERR_INVALID_STATE;
    }
    uint16_t keys = 0;
    esp_err_t err = ESP_OK;
    board_mcp_lock();
    for (int col = 0; col < 4 && err == ESP_OK; col++) {
        err = strobe(BOARD_MCP_U2, KP_STROBE_MASK, s_kp_col_pin[col]);
        uint16_t v = 0;
        if (err == ESP_OK) {
            err = board_mcp_read(BOARD_MCP_U2, &v);
        }
        uint8_t rows = (uint8_t)(~v & KP_ROW_MASK);
        for (int row = 0; row < 4; row++) {
            if (rows & (1u << row)) {
                keys |= (uint16_t)(1u << (row * 4 + col));
            }
        }
    }
    esp_err_t idle = strobe(BOARD_MCP_U2, KP_STROBE_MASK, -1);
    board_mcp_unlock();
    if (err == ESP_OK) {
        err = idle;
    }
    if (err == ESP_OK) {
        *pressed = keys;
    }
    return err;
}

char board_keypad_poll(void)
{
    static uint16_t s_last, s_stable;
    static uint8_t s_count;
    uint16_t raw;
    if (board_keypad_scan(&raw) != ESP_OK) {
        return 0;
    }
    if (raw != s_last) {
        s_last = raw;
        s_count = 0;
        return 0;
    }
    if (s_count >= KP_DEBOUNCE) {
        return 0;
    }
    if (++s_count < KP_DEBOUNCE) {
        return 0;
    }
    uint16_t newly = (uint16_t)(raw & ~s_stable);
    s_stable = raw;
    for (int i = 0; i < BOARD_KEYPAD_KEYS; i++) {
        if (newly & (1u << i)) {
            return s_keymap[i];
        }
    }
    return 0;
}

esp_err_t board_wires_scan(uint8_t conn[BOARD_WIRE_POSTS])
{
    if (!board_mcp_present(BOARD_MCP_U3)) {
        return ESP_ERR_INVALID_STATE;
    }
    esp_err_t err = ESP_OK;
    board_mcp_lock();
    for (int a = 0; a < BOARD_WIRE_POSTS && err == ESP_OK; a++) {
        err = strobe(BOARD_MCP_U3, WA_STROBE_MASK, s_wa_pin[a]);
        uint16_t v = 0;
        if (err == ESP_OK) {
            esp_rom_delay_us(20); /* let the long banana leads settle */
            err = board_mcp_read(BOARD_MCP_U3, &v);
        }
        conn[a] = (uint8_t)(~(v >> WB_SHIFT) & WB_MASK);
    }
    esp_err_t idle = strobe(BOARD_MCP_U3, WA_STROBE_MASK, -1);
    board_mcp_unlock();
    return err == ESP_OK ? idle : err;
}

int board_wires_b_for_a(const uint8_t conn[BOARD_WIRE_POSTS], int a)
{
    if (a < 0 || a >= BOARD_WIRE_POSTS || conn[a] == 0) {
        return -1;
    }
    uint8_t m = conn[a];
    if (m & (m - 1)) {
        return -2;
    }
    int b = 0;
    while (!(m & 1)) {
        m >>= 1;
        b++;
    }
    return b;
}

esp_err_t board_encoder_switch_init(void)
{
    /* GPIO39: input-only, external 10k pull-up to 3V3P (rev 1b). */
    gpio_config_t io = {
        .pin_bit_mask = 1ULL << BOARD_PIN_ENC_SW,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    return gpio_config(&io);
}

bool board_encoder_switch_down(void)
{
    /* The pull-up sits on 3V3P: with the rail off (I2C bus reported down)
     * the pin floats low, which must not read as a press. */
    return board_i2c_ready() && gpio_get_level(BOARD_PIN_ENC_SW) == 0;
}

esp_err_t board_encoder_poll(board_encoder_t *enc)
{
    /* Quadrature transition table indexed by (prev << 2) | cur, state = A<<1|B. */
    static const int8_t s_qdec[16] = { 0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0 };
    static uint8_t s_prev = 0xFF;
    bool down = board_encoder_switch_down();
    enc->clicked = down && !enc->pressed;
    enc->pressed = down;
    uint16_t v;
    esp_err_t err = board_mcp_read(BOARD_MCP_U3, &v);
    if (err != ESP_OK) {
        return err;
    }
    uint8_t a = (v >> BOARD_U3_ENC_A) & 1;
    uint8_t b = (v >> BOARD_U3_ENC_B) & 1;
    uint8_t cur = (uint8_t)((a << 1) | b);
    if (s_prev != 0xFF) {
        enc->steps += s_qdec[(s_prev << 2) | cur];
    }
    s_prev = cur;
    return ESP_OK;
}

esp_err_t board_simon_read(uint8_t *mask)
{
    uint16_t v;
    esp_err_t err = board_mcp_read(BOARD_MCP_U2, &v);
    if (err == ESP_OK) {
        *mask = (uint8_t)(~(v >> BOARD_U2_SIM1) & 0x0F);
    }
    return err;
}

esp_err_t board_keyswitch_armed(bool *armed)
{
    uint16_t v;
    esp_err_t err = board_mcp_read(BOARD_MCP_U2, &v);
    if (err == ESP_OK) {
        bool high = (v >> BOARD_U2_KEYSW) & 1;
#if CONFIG_D32_KEYSW_ARMED_LOW
        *armed = !high;
#else
        *armed = high;
#endif
    }
    return err;
}

esp_err_t board_sd_card_detected(bool *present)
{
    uint16_t v;
    esp_err_t err = board_mcp_read(BOARD_MCP_U2, &v);
    if (err == ESP_OK) {
        bool high = (v >> BOARD_U2_SD_DET) & 1;
#if CONFIG_D32_SD_DET_ACTIVE_HIGH
        *present = high;
#else
        *present = !high;
#endif
    }
    return err;
}
