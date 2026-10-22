/* Carrier I2C bus (GPIO21/22, I2C_NUM_0, new i2c_master driver). */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"
#include "driver/i2c_master.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Checks that SDA/SCL idle high (3V3P rail powered, nothing holding the bus)
 * and creates the bus. ESP_ERR_INVALID_STATE if the lines are low. */
esp_err_t board_i2c_init(void);
void board_i2c_deinit(void);
bool board_i2c_ready(void);
i2c_master_bus_handle_t board_i2c_bus(void);

/* Address-only probe; ESP_OK if a device acknowledged. */
esp_err_t board_i2c_probe(uint8_t addr);
/* Probe 0x08..0x77; writes up to `max` found addresses, returns the count
 * (or -1 when the bus is down). */
int board_i2c_scan(uint8_t *found, int max);

/* Add a device at the bus speed (CONFIG_D32_I2C_FREQ_HZ). */
esp_err_t board_i2c_add(uint8_t addr, i2c_master_dev_handle_t *out);
void board_i2c_remove(i2c_master_dev_handle_t dev);

/* Register helpers (8-bit register address, BOARD_I2C_TIMEOUT_MS). */
esp_err_t board_i2c_write_reg(i2c_master_dev_handle_t dev, uint8_t reg, const uint8_t *data, size_t len);
esp_err_t board_i2c_read_reg(i2c_master_dev_handle_t dev, uint8_t reg, uint8_t *data, size_t len);

#ifdef __cplusplus
}
#endif
