#include "board.h"

#include "driver/uart.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"

static const char *TAG = "board_uart2";

#define U2_PORT     UART_NUM_2
#define U2_RX_BUF   1024
#define U2_TX_BUF   1024

static bool s_ready;

esp_err_t board_uart2_init(uint32_t baud)
{
    if (s_ready) {
        return uart_set_baudrate(U2_PORT, baud);
    }
    uart_config_t c = {
        .baud_rate = (int)baud,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };
    esp_err_t err = uart_driver_install(U2_PORT, U2_RX_BUF, U2_TX_BUF, 0, NULL, 0);
    if (err == ESP_OK) err = uart_param_config(U2_PORT, &c);
    if (err == ESP_OK) err = uart_set_pin(U2_PORT, BOARD_PIN_UART2_TX, BOARD_PIN_UART2_RX,
                                          UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "init failed: %s", esp_err_to_name(err));
        if (uart_is_driver_installed(U2_PORT)) {
            uart_driver_delete(U2_PORT);
        }
        return err;
    }
    s_ready = true;
    return ESP_OK;
}

void board_uart2_deinit(void)
{
    if (s_ready) {
        uart_driver_delete(U2_PORT);
        s_ready = false;
    }
}

int board_uart2_write(const void *data, size_t len)
{
    return s_ready ? uart_write_bytes(U2_PORT, data, len) : -1;
}

int board_uart2_read(void *buf, size_t len, uint32_t timeout_ms)
{
    return s_ready ? uart_read_bytes(U2_PORT, buf, len, pdMS_TO_TICKS(timeout_ms)) : -1;
}
