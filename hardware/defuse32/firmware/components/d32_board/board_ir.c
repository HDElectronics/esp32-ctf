#include "board.h"

#include <stdlib.h>
#include "driver/rmt_rx.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

static const char *TAG = "board_ir";

#define IR_RESOLUTION_HZ    1000000     /* 1 tick = 1 us */
#define IR_SYMBOLS          64
#define NEC_LEAD_LOW        9000
#define NEC_LEAD_HIGH       4500
#define NEC_REPEAT_HIGH     2250
#define NEC_BIT_LOW         560
#define NEC_ZERO_HIGH       560
#define NEC_ONE_HIGH        1690

static rmt_channel_handle_t s_rx;
static QueueHandle_t s_done_q;      /* rmt_rx_done_event_data_t from the ISR */
static QueueHandle_t s_code_q;      /* board_ir_code_t */
static TaskHandle_t s_task;
static volatile bool s_stop;
static rmt_symbol_word_t s_buf[IR_SYMBOLS];
static board_ir_code_t s_last;

static bool IRAM_ATTR ir_rx_done(rmt_channel_handle_t ch, const rmt_rx_done_event_data_t *ed, void *ctx)
{
    (void)ch;
    BaseType_t woken = pdFALSE;
    xQueueSendFromISR((QueueHandle_t)ctx, ed, &woken);
    return woken == pdTRUE;
}

static inline bool ir_near(uint32_t v, uint32_t target)
{
    uint32_t tol = target / 4 + 100;    /* 25 % + 100 us */
    return v + tol >= target && v <= target + tol;
}

/* The receiver output is active low: level0 = 0 is the carrier burst. */
static bool nec_decode(const rmt_symbol_word_t *s, size_t n, board_ir_code_t *out)
{
    if (n < 2 || !ir_near(s[0].duration0, NEC_LEAD_LOW)) {
        return false;
    }
    if (n <= 3 && ir_near(s[0].duration1, NEC_REPEAT_HIGH)) {
        *out = s_last;
        out->repeat = true;
        return true;
    }
    if (n < 33 || !ir_near(s[0].duration1, NEC_LEAD_HIGH)) {
        return false;
    }
    uint32_t raw = 0;
    for (int i = 0; i < 32; i++) {
        const rmt_symbol_word_t *b = &s[1 + i];
        if (!ir_near(b->duration0, NEC_BIT_LOW)) {
            return false;
        }
        if (ir_near(b->duration1, NEC_ONE_HIGH)) {
            raw |= 1u << i;
        } else if (!ir_near(b->duration1, NEC_ZERO_HIGH)) {
            return false;
        }
    }
    uint8_t a = raw & 0xFF, an = (raw >> 8) & 0xFF, c = (raw >> 16) & 0xFF, cn = (raw >> 24) & 0xFF;
    if ((uint8_t)(c ^ cn) != 0xFF) {
        return false;
    }
    out->raw = raw;
    out->command = c;
    out->address = ((uint8_t)(a ^ an) == 0xFF) ? a : (uint16_t)(raw & 0xFFFF);
    out->repeat = false;
    s_last = *out;
    return true;
}

static void ir_task(void *arg)
{
    (void)arg;
    const rmt_receive_config_t rc = {
        .signal_range_min_ns = 1250,            /* glitch filter */
        .signal_range_max_ns = 12 * 1000 * 1000, /* > 9 ms lead: end of frame */
    };
    while (!s_stop) {
        if (rmt_receive(s_rx, s_buf, sizeof(s_buf), &rc) != ESP_OK) {
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }
        rmt_rx_done_event_data_t ed;
        while (!s_stop && xQueueReceive(s_done_q, &ed, pdMS_TO_TICKS(200)) != pdTRUE) {
        }
        if (s_stop) {
            break;
        }
        board_ir_code_t code;
        if (nec_decode(ed.received_symbols, ed.num_symbols, &code)) {
            xQueueSend(s_code_q, &code, 0);
        }
    }
    s_task = NULL;
    vTaskDelete(NULL);
}

esp_err_t board_ir_init(void)
{
    if (s_rx) {
        return ESP_OK;
    }
    rmt_rx_channel_config_t cc = {
        .gpio_num = BOARD_PIN_IR,
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = IR_RESOLUTION_HZ,
        .mem_block_symbols = IR_SYMBOLS,
    };
    esp_err_t err = rmt_new_rx_channel(&cc, &s_rx);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "RMT RX channel: %s", esp_err_to_name(err));
        s_rx = NULL;
        return err;
    }
    s_done_q = xQueueCreate(1, sizeof(rmt_rx_done_event_data_t));
    s_code_q = xQueueCreate(8, sizeof(board_ir_code_t));
    rmt_rx_event_callbacks_t cbs = { .on_recv_done = ir_rx_done };
    err = (s_done_q && s_code_q) ? ESP_OK : ESP_ERR_NO_MEM;
    if (err == ESP_OK) err = rmt_rx_register_event_callbacks(s_rx, &cbs, s_done_q);
    if (err == ESP_OK) err = rmt_enable(s_rx);
    if (err == ESP_OK) {
        s_stop = false;
        if (xTaskCreate(ir_task, "board_ir", 3072, NULL, 5, &s_task) != pdPASS) {
            err = ESP_ERR_NO_MEM;
        }
    }
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "init failed: %s", esp_err_to_name(err));
        board_ir_deinit();
    }
    return err;
}

void board_ir_deinit(void)
{
    s_stop = true;
    for (int i = 0; i < 50 && s_task; i++) {
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    if (s_rx) {
        rmt_disable(s_rx);
        rmt_del_channel(s_rx);
        s_rx = NULL;
    }
    if (s_done_q) {
        vQueueDelete(s_done_q);
        s_done_q = NULL;
    }
    if (s_code_q) {
        vQueueDelete(s_code_q);
        s_code_q = NULL;
    }
}

bool board_ir_ready(void)
{
    return s_rx != NULL && s_task != NULL;
}

bool board_ir_get(board_ir_code_t *out, uint32_t timeout_ms)
{
    if (!s_code_q) {
        return false;
    }
    return xQueueReceive(s_code_q, out, pdMS_TO_TICKS(timeout_ms)) == pdTRUE;
}

void board_ir_flush(void)
{
    if (s_code_q) {
        xQueueReset(s_code_q);
    }
}
