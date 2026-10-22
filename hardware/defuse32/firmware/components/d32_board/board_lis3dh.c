#include "board.h"

#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "board_lis3dh";

#define LIS_REG_WHO_AM_I     0x0F
#define LIS_REG_CTRL_REG1    0x20
#define LIS_REG_CTRL_REG4    0x23
#define LIS_REG_OUT_X_L      0x28
#define LIS_AUTO_INC         0x80   /* sub-address MSB: auto-increment on multi-byte reads */
#define LIS_WHO_AM_I_VALUE   0x33
#define LIS_CTRL1_50HZ_XYZ   0x47   /* ODR 0100 = 50 Hz, LPen 0 (normal mode), Z/Y/X on */
#define LIS_CTRL1_POWERDOWN  0x00
#define LIS_CTRL4_BDU_2G     0x80   /* BDU on, FS +-2 g, HR off (normal mode) */

static i2c_master_dev_handle_t s_dev;
static float s_ref[3] = { 0.0f, 0.0f, 1.0f };

esp_err_t board_lis3dh_init(void)
{
    if (s_dev) {
        return ESP_OK;
    }
    if (!board_i2c_ready() || board_i2c_probe(BOARD_I2C_ADDR_LIS3DH) != ESP_OK) {
        ESP_LOGW(TAG, "LIS3DH (0x%02X) not found", BOARD_I2C_ADDR_LIS3DH);
        return ESP_ERR_NOT_FOUND;
    }
    esp_err_t err = board_i2c_add(BOARD_I2C_ADDR_LIS3DH, &s_dev);
    if (err != ESP_OK) {
        s_dev = NULL;
        return err;
    }
    uint8_t who = 0;
    err = board_i2c_read_reg(s_dev, LIS_REG_WHO_AM_I, &who, 1);
    if (err == ESP_OK && who != LIS_WHO_AM_I_VALUE) {
        ESP_LOGW(TAG, "WHO_AM_I = 0x%02X (expected 0x%02X): not a LIS3DH", who, LIS_WHO_AM_I_VALUE);
        err = ESP_ERR_NOT_FOUND;
    }
    const uint8_t ctrl4 = LIS_CTRL4_BDU_2G;
    const uint8_t ctrl1 = LIS_CTRL1_50HZ_XYZ;
    if (err == ESP_OK) err = board_i2c_write_reg(s_dev, LIS_REG_CTRL_REG4, &ctrl4, 1);
    if (err == ESP_OK) err = board_i2c_write_reg(s_dev, LIS_REG_CTRL_REG1, &ctrl1, 1);
    if (err != ESP_OK) {
        if (err != ESP_ERR_NOT_FOUND) {
            ESP_LOGW(TAG, "init failed: %s", esp_err_to_name(err));
        }
        board_i2c_remove(s_dev);
        s_dev = NULL;
        return err;
    }
    vTaskDelay(pdMS_TO_TICKS(50)); /* turn-on time 1/ODR + 1 ms: wait for a couple of samples */
    board_lis3dh_set_reference();
    return ESP_OK;
}

void board_lis3dh_deinit(void)
{
    if (s_dev) {
        const uint8_t off = LIS_CTRL1_POWERDOWN;
        board_i2c_write_reg(s_dev, LIS_REG_CTRL_REG1, &off, 1);
        board_i2c_remove(s_dev);
        s_dev = NULL;
    }
}

bool board_lis3dh_present(void)
{
    return s_dev != NULL;
}

esp_err_t board_lis3dh_accel(float g[3])
{
    if (!s_dev) {
        return ESP_ERR_INVALID_STATE;
    }
    uint8_t d[6];
    esp_err_t err = board_i2c_read_reg(s_dev, LIS_REG_OUT_X_L | LIS_AUTO_INC, d, sizeof(d));
    if (err != ESP_OK) {
        return err;
    }
    for (int i = 0; i < 3; i++) {
        int16_t v = (int16_t)(((uint16_t)d[2 * i + 1] << 8) | d[2 * i]); /* little endian */
        g[i] = board_tilt_lis3dh_raw_to_g(v);
    }
    return ESP_OK;
}

esp_err_t board_lis3dh_set_reference(void)
{
    float g[3];
    esp_err_t err = board_lis3dh_accel(g);
    if (err != ESP_OK) {
        return err;
    }
    /* free fall or garbage: keep the old reference */
    return board_tilt_set_ref(g, s_ref) ? ESP_OK : ESP_ERR_INVALID_RESPONSE;
}

esp_err_t board_lis3dh_tilt(float *tilt_deg, float *pitch_deg, float *roll_deg)
{
    float g[3];
    esp_err_t err = board_lis3dh_accel(g);
    if (err != ESP_OK) {
        return err;
    }
    if (tilt_deg) {
        *tilt_deg = board_tilt_angle(g, s_ref);
    }
    if (pitch_deg) {
        *pitch_deg = board_tilt_pitch(g);
    }
    if (roll_deg) {
        *roll_deg = board_tilt_roll(g);
    }
    return ESP_OK;
}
