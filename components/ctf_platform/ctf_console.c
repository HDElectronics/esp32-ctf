/* Minimal UART0 line editor feeding esp_console_run().
 * Not linenoise: every raw byte goes through an optional hook first (SER-03
 * timing, SER-04 escape sequence), then a tiny editor (echo, backspace/DEL,
 * Enter; ANSI escape sequences such as arrow keys are swallowed).
 *
 * Machine channel (SPEC "v0.2.0"): a 0x01 (SOH) byte starts a machine line in
 * its own buffer: no echo, no prompt, and Enter hands it to ctf_api_run()
 * (one STX/ETX JSON frame). A half-typed human line is kept untouched, so the
 * player app can poll while someone is typing in its console pane. */
#include "ctf_platform.h"
#include "ctf_platform_priv.h"

#include <stdio.h>
#include <string.h>
#include "driver/uart.h"
#include "driver/uart_vfs.h"
#include "esp_console.h"
#include "esp_err.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define CONSOLE_UART   UART_NUM_0
#define CTF_LINE_MAX       256
#define PROMPT         "ctf> "

static const char *TAG = "ctf_console";
static volatile ctf_console_byte_hook_t s_hook;
static bool s_started;

void ctf_console_set_byte_hook(ctf_console_byte_hook_t hook)
{
    s_hook = hook;
}

static void out(const char *s, size_t n)
{
    fwrite(s, 1, n, stdout);
    fflush(stdout);
}

static void run_line(char *line)
{
    int ret = 0;
    esp_err_t err = esp_console_run(line, &ret);
    if (err == ESP_ERR_NOT_FOUND) {
        printf("Unknown command. Type `help`.\n");
    } else if (err == ESP_OK && ret != 0) {
        /* Commands print their own errors. */
    } else if (err != ESP_OK && err != ESP_ERR_INVALID_ARG) {
        printf("Error: %s\n", esp_err_to_name(err));
    }
}

static void console_task(void *arg)
{
    (void)arg;
    char line[CTF_LINE_MAX];
    size_t len = 0;
    char mline[CTF_LINE_MAX]; /* machine line (after SOH) */
    size_t mlen = 0;
    bool machine = false;
    int esc = 0;          /* 0 none, 1 after ESC, 2 inside CSI */
    bool last_cr = false; /* swallow LF right after CR */

    /* Let app_main return (and log) before the first prompt. */
    vTaskDelay(pdMS_TO_TICKS(100));
    out(PROMPT, sizeof(PROMPT) - 1);
    for (;;) {
        uint8_t b;
        if (uart_read_bytes(CONSOLE_UART, &b, 1, portMAX_DELAY) != 1) {
            continue;
        }
        int64_t t = esp_timer_get_time();
        ctf_console_byte_hook_t hook = s_hook;
        if (hook && hook(b, t)) {
            continue;
        }

        if (esc == 1) {
            esc = (b == '[' || b == 'O') ? 2 : 0;
            continue;
        }
        if (esc == 2) {
            if (b >= 0x40 && b <= 0x7E) {
                esc = 0;
            }
            continue;
        }

        if (b == '\n' && last_cr) {
            last_cr = false;
            continue;
        }
        last_cr = (b == '\r');

        if (b == 0x01) { /* SOH: start (or restart) a machine line */
            machine = true;
            mlen = 0;
            continue;
        }
        if (machine) {
            if (b == '\r' || b == '\n') {
                machine = false;
                mline[mlen] = '\0';
                ctf_api_run(mline);
            } else if (b == 0x08 || b == 0x7F) {
                mlen -= mlen > 0 ? 1 : 0;
            } else if (b == 0x1B) {
                esc = 1;
            } else if (b == 0x03) { /* Ctrl-C: drop the machine line silently */
                machine = false;
            } else if (b >= 0x20 && b < 0x7F && mlen < CTF_LINE_MAX - 1) {
                mline[mlen++] = (char)b;
            }
            continue;
        }

        if (b == '\r' || b == '\n') {
            out("\n", 1);
            line[len] = '\0';
            if (len > 0) {
                run_line(line);
            }
            len = 0;
            out(PROMPT, sizeof(PROMPT) - 1);
        } else if (b == 0x08 || b == 0x7F) {
            if (len > 0) {
                len--;
                out("\b \b", 3);
            }
        } else if (b == 0x1B) {
            esc = 1;
        } else if (b == 0x03) { /* Ctrl-C: drop the line */
            len = 0;
            out("^C\n" PROMPT, 3 + sizeof(PROMPT) - 1);
        } else if (b >= 0x20 && b < 0x7F) {
            if (len < CTF_LINE_MAX - 1) {
                line[len++] = (char)b;
                out((const char *)&b, 1);
            }
        }
        /* other control bytes ignored */
    }
}

void ctf_console_start(void)
{
    if (s_started) {
        return;
    }
    s_started = true;
    fflush(stdout);
    ESP_ERROR_CHECK(uart_driver_install(CONSOLE_UART, 512, 1024, 0, NULL, 0));
    /* stdout/stderr keep going to UART0, now through the driver (thread-safe
     * with our reads, TX buffered). */
    uart_vfs_dev_use_driver(CONSOLE_UART);
    if (xTaskCreate(console_task, "ctf_console", 6144, NULL, 5, NULL) != pdPASS) {
        ESP_LOGE(TAG, "failed to start console task");
    }
}
