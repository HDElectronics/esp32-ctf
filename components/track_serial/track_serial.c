/* track_serial: SER-02..04 and CRY-01 shard 1 (SPEC "Serial", "Cross-track rules").
 * SER-01 lives in main (boot banner). */
#include "track_serial.h"

#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include "ctf_core.h"
#include "ctf_platform.h"
#include "driver/uart.h"
#include "esp_console.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

/* ---- CRY-01 shard 1: one boot line ------------------------------------- */

static void print_shard1(void)
{
    uint8_t b[2];
    ctf_derive("CRY-01:shard1", b, sizeof(b));
    ESP_LOGI("locale", "cipher shard 1/4: %c%c", 'A' + b[0] % 26, 'A' + b[1] % 26);
}

/* ---- SER-02: UART2 at 28800 8N1, flag every 5 s ------------------------ */

#define SER02_UART     UART_NUM_2
#define SER02_TX_PIN   17
#define SER02_RX_PIN   16
#define SER02_BAUD     28800
#define SER02_PERIOD_MS 5000

static void ser02_task(void *arg)
{
    (void)arg;
    char flag[18];
    char line[64];
    unsigned seq = 0;
    for (;;) {
        ctf_flag("SER-02", flag);
        int n = snprintf(line, sizeof(line), "[aux] heartbeat %u, maint token %s\r\n", seq++, flag);
        uart_write_bytes(SER02_UART, line, (size_t)n);
        vTaskDelay(pdMS_TO_TICKS(SER02_PERIOD_MS));
    }
}

static void ser02_start(void)
{
    const uart_config_t cfg = {
        .baud_rate = SER02_BAUD,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    esp_err_t err = uart_driver_install(SER02_UART, 256, 0, 0, NULL, 0);
    if (err == ESP_OK) {
        err = uart_param_config(SER02_UART, &cfg);
    }
    if (err == ESP_OK) {
        err = uart_set_pin(SER02_UART, SER02_TX_PIN, SER02_RX_PIN,
                           UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    }
    if (err != ESP_OK) {
        ESP_LOGE("uart2", "init failed: %s", esp_err_to_name(err));
        return;
    }
    /* Low priority: just above idle. */
    if (xTaskCreate(ser02_task, "aux_uart", 2560, NULL, 1, NULL) != pdPASS) {
        ESP_LOGE("uart2", "task create failed");
    }
}

/* ---- SER-03: login with a timing side channel -------------------------- */

#define SER03_PW_LEN 8
#define SER03_STEP_MS 30

static void ser03_password(char pw[SER03_PW_LEN + 1])
{
    static const char alphabet[] = "abcdefghijklmnopqrstuvwxyz0123456789";
    uint8_t b[SER03_PW_LEN];
    ctf_derive("SER-03:pw", b, sizeof(b));
    for (int i = 0; i < SER03_PW_LEN; i++) {
        pw[i] = alphabet[b[i] % 36];
    }
    pw[SER03_PW_LEN] = '\0';
}

static int cmd_login(int argc, char **argv)
{
    if (argc < 2) {
        printf("Usage: login <password>\n");
        return 1;
    }
    char pw[SER03_PW_LEN + 1];
    ser03_password(pw);
    const char *in = argv[1];
    bool ok = true;
    /* Deliberately leaky: char by char, a pause after each correct one. */
    for (int i = 0; i < SER03_PW_LEN; i++) {
        if (in[i] != pw[i]) {
            ok = false;
            break;
        }
        vTaskDelay(pdMS_TO_TICKS(SER03_STEP_MS));
    }
    if (ok && in[SER03_PW_LEN] != '\0') {
        ok = false;
    }
    memset(pw, 0, sizeof(pw));
    if (!ok) {
        printf("Access denied.\n");
        return 1;
    }
    char flag[18];
    ctf_flag("SER-03", flag);
    printf("Access granted. Debug session token: %s\n", flag);
    return 0;
}

/* ---- SER-04: Ctrl-] then "dbg" within 1 s ------------------------------ */

#define SER04_START   0x1D
#define SER04_WINDOW_US 1000000

static int s_seq;        /* bytes of the sequence matched so far (0 = idle) */
static int64_t s_seq_t0; /* time of the Ctrl-] that started it */

static bool ser04_hook(uint8_t b, int64_t t_us)
{
    static const char word[] = "dbg";
    if (s_seq > 0 && t_us - s_seq_t0 > SER04_WINDOW_US) {
        s_seq = 0;
    }
    if (s_seq > 0) {
        if (b == (uint8_t)word[s_seq - 1]) {
            s_seq++;
            if (s_seq == (int)sizeof(word)) { /* 1 + strlen(word) bytes */
                s_seq = 0;
                char flag[18];
                ctf_flag("SER-04", flag);
                printf("\n"
                       "+--------------------------------------+\n"
                       "| hidden debug monitor (read-only)     |\n"
                       "+--------------------------------------+\n"
                       "dbg> session key: %s\n"
                       "dbg> exiting debug monitor\n"
                       "ctf> ",
                       flag);
                fflush(stdout);
            }
            return true;
        }
        s_seq = 0; /* mismatch: reset, and let the byte through */
    }
    if (b == SER04_START) {
        s_seq = 1;
        s_seq_t0 = t_us;
        return true;
    }
    return false;
}

/* ---- entry ------------------------------------------------------------- */

void track_serial_start(void)
{
    print_shard1();
    ser02_start();

    static const esp_console_cmd_t login_cmd = {
        .command = "login",
        .help = "Log in to the maintenance account",
        .hint = "<password>",
        .func = cmd_login,
    };
    ESP_ERROR_CHECK(esp_console_cmd_register(&login_cmd));
    ctf_console_set_byte_hook(ser04_hook);
}
