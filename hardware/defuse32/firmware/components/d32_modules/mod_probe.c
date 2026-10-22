/* M5 probe adapter (variant "uart-<baud>", e.g. "uart-115200"), v0.
 *
 * Challenge: when a round is armed, a boot-style banner goes out on UART2
 * (probe plate header, TX GPIO17 / RX GPIO16, 8N1) at the variant's baud
 * rate. It carries the M5 code, the M4 patch hint and the M3 service PIN as
 * base64 ("svc: ..."). The banner is sent
 * again whenever a CR or LF arrives on RX, so a player who connects late
 * can ask for it. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "board.h"
#include "d32_mod_internal.h"
#include "esp_log.h"

static const char *TAG = "mod_probe";

#define RX_POLL_MS 50

static uint32_t s_baud;         /* 0: variant not understood */
static bool s_uart_ok;
static bool s_armed;
static uint32_t s_next_rx;

/* "uart-<baud>" with a baud rate 1200..921600. */
static uint32_t parse_baud(const char *variant)
{
    if (!variant || strncmp(variant, "uart-", 5) != 0) {
        return 0;
    }
    char *end;
    unsigned long b = strtoul(variant + 5, &end, 10);
    if (*end || b < 1200 || b > 921600) {
        return 0;
    }
    return (uint32_t)b;
}

static void send_banner(const d32_t *d, int slot)
{
    char code[D32_CODE_LEN + 1];
    char hint[48];
    char buf[256];
    if (!d32_code_for(d, slot, code)) {
        return;
    }
    int n = snprintf(buf, sizeof(buf),
                     "\r\n\r\nDefuse32 probe plate, boot\r\n"
                     "rst:0x1 (POWERON), uart2 %lu 8N1\r\n"
                     "M5 code: %s\r\n",
                     (unsigned long)s_baud, code);
    if (d32_mod_wires_hint(hint, sizeof(hint)) && n > 0 && (size_t)n < sizeof(buf)) {
        n += snprintf(buf + n, sizeof(buf) - (size_t)n, "M4 patch: %s\r\n", hint);
    }
    char pin[D32_ML_PIN_LEN + 1];
    char b64[16];
    if (d32_mod_keypad_pin(pin) && d32_base64((const uint8_t *)pin, D32_ML_PIN_LEN, b64, sizeof(b64)) > 0 &&
        n > 0 && (size_t)n < sizeof(buf)) {
        n += snprintf(buf + n, sizeof(buf) - (size_t)n, "svc: %s\r\n", b64);
    }
    if (n > 0 && (size_t)n < sizeof(buf)) {
        n += snprintf(buf + n, sizeof(buf) - (size_t)n, "(press Enter to repeat)\r\n");
    }
    if (n > 0) {
        board_uart2_write(buf, strnlen(buf, sizeof(buf)));
    }
}

static bool p_configure(int slot, const char *variant)
{
    (void)slot;
    s_baud = parse_baud(variant);
    s_armed = false;
    return s_baud != 0;
}

static void p_arm(d32_t *d, int slot, uint32_t seed)
{
    (void)seed;
    s_armed = false;
    if (!s_baud) {
        return;
    }
    s_uart_ok = board_uart2_init(s_baud) == ESP_OK;
    if (!s_uart_ok) {
        ESP_LOGW(TAG, "UART2 init failed: M5 banner not sent");
        return;
    }
    s_armed = true;
    send_banner(d, slot);
    ESP_LOGI(TAG, "banner sent on UART2 at %lu baud", (unsigned long)s_baud);
}

static void p_poll(d32_t *d, int slot, uint32_t now_ms)
{
    if (!s_armed || (int32_t)(now_ms - s_next_rx) < 0) {
        return;
    }
    s_next_rx = now_ms + RX_POLL_MS;
    d32_phase_t ph = d32_phase(d);
    uint8_t rx[16];
    int n = board_uart2_read(rx, sizeof(rx), 0);
    if (n <= 0 || (ph != D32_ARMED && ph != D32_FINAL)) {
        return;
    }
    for (int i = 0; i < n; i++) {
        if (rx[i] == '\r' || rx[i] == '\n') {
            send_banner(d, slot);
            break;
        }
    }
}

static void p_reset(int slot)
{
    (void)slot;
    s_armed = false;
}

const d32_mod_ops_t d32_mod_probe = {
    .name = "probe",
    .configure = p_configure,
    .arm = p_arm,
    .poll = p_poll,
    .reset = p_reset,
};
