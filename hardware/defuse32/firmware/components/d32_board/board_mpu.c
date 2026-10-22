#include "board.h"

#include <math.h>
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "board_mpu";

#define MPU_REG_SMPLRT_DIV   0x19
#define MPU_REG_CONFIG       0x1A
#define MPU_REG_ACCEL_CONFIG 0x1C
#define MPU_REG_ACCEL_XOUT_H 0x3B
#define MPU_REG_PWR_MGMT_1   0x6B
#define MPU_REG_WHO_AM_I     0x75
#define MPU_LSB_PER_G        16384.0f   /* +-2 g */

static i2c_master_dev_handle_t s_dev;
static float s_ref[3] = { 0.0f, 0.0f, 1.0f };

esp_err_t board_mpu_init(void)
{
    if (s_dev) {
        return ESP_OK;
    }
    if (!board_i2c_ready() || board_i2c_probe(BOARD_I2C_ADDR_MPU) != ESP_OK) {
        ESP_LOGW(TAG, "MPU-6050 (0x%02X) not found", BOARD_I2C_ADDR_MPU);
        return ESP_ERR_NOT_FOUND;
    }
    esp_err_t err = board_i2c_add(BOARD_I2C_ADDR_MPU, &s_dev);
    if (err != ESP_OK) {
        s_dev = NULL;
        return err;
    }
    uint8_t who = 0;
    err = board_i2c_read_reg(s_dev, MPU_REG_WHO_AM_I, &who, 1);
    if (err == ESP_OK && (who & 0x7E) != 0x68) {
        /* 0x68 on genuine parts; some clones answer 0x70/0x72/0x98: accept
         * but say so. */
        ESP_LOGW(TAG, "WHO_AM_I = 0x%02X (expected 0x68), continuing", who);
    }
    const uint8_t wake = 0x01;          /* clock = PLL X gyro, sleep off */
    const uint8_t dlpf = 0x03;          /* ~44 Hz accel bandwidth */
    const uint8_t div = 9;              /* 100 Hz sample rate */
    const uint8_t range = 0x00;         /* +-2 g */
    if (err == ESP_OK) err = board_i2c_write_reg(s_dev, MPU_REG_PWR_MGMT_1, &wake, 1);
    if (err == ESP_OK) err = board_i2c_write_reg(s_dev, MPU_REG_CONFIG, &dlpf, 1);
    if (err == ESP_OK) err = board_i2c_write_reg(s_dev, MPU_REG_SMPLRT_DIV, &div, 1);
    if (err == ESP_OK) err = board_i2c_write_reg(s_dev, MPU_REG_ACCEL_CONFIG, &range, 1);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "init failed: %s", esp_err_to_name(err));
        board_i2c_remove(s_dev);
        s_dev = NULL;
        return err;
    }
    vTaskDelay(pdMS_TO_TICKS(30)); /* first samples after wake-up */
    board_mpu_set_reference();
    return ESP_OK;
}

void board_mpu_deinit(void)
{
    if (s_dev) {
        const uint8_t sleep = 0x40;
        board_i2c_write_reg(s_dev, MPU_REG_PWR_MGMT_1, &sleep, 1);
        board_i2c_remove(s_dev);
        s_dev = NULL;
    }
}

bool board_mpu_present(void)
{
    return s_dev != NULL;
}

esp_err_t board_mpu_accel(float g[3])
{
    if (!s_dev) {
        return ESP_ERR_INVALID_STATE;
    }
    uint8_t d[6];
    esp_err_t err = board_i2c_read_reg(s_dev, MPU_REG_ACCEL_XOUT_H, d, sizeof(d));
    if (err != ESP_OK) {
        return err;
    }
    for (int i = 0; i < 3; i++) {
        int16_t v = (int16_t)((d[2 * i] << 8) | d[2 * i + 1]);
        g[i] = (float)v / MPU_LSB_PER_G;
    }
    return ESP_OK;
}

esp_err_t board_mpu_set_reference(void)
{
    float g[3];
    esp_err_t err = board_mpu_accel(g);
    if (err != ESP_OK) {
        return err;
    }
    float n = sqrtf(g[0] * g[0] + g[1] * g[1] + g[2] * g[2]);
    if (n < 0.2f) {
        return ESP_ERR_INVALID_RESPONSE; /* free fall or garbage: keep the old one */
    }
    for (int i = 0; i < 3; i++) {
        s_ref[i] = g[i] / n;
    }
    return ESP_OK;
}

esp_err_t board_mpu_tilt(float *tilt_deg, float *pitch_deg, float *roll_deg)
{
    float g[3];
    esp_err_t err = board_mpu_accel(g);
    if (err != ESP_OK) {
        return err;
    }
    const float rad2deg = 57.2957795f;
    float n = sqrtf(g[0] * g[0] + g[1] * g[1] + g[2] * g[2]);
    if (tilt_deg) {
        float c = n > 0.0f ? (g[0] * s_ref[0] + g[1] * s_ref[1] + g[2] * s_ref[2]) / n : 1.0f;
        if (c > 1.0f) c = 1.0f;
        if (c < -1.0f) c = -1.0f;
        *tilt_deg = acosf(c) * rad2deg;
    }
    if (pitch_deg) {
        *pitch_deg = atan2f(-g[0], sqrtf(g[1] * g[1] + g[2] * g[2])) * rad2deg;
    }
    if (roll_deg) {
        *roll_deg = atan2f(g[1], g[2]) * rad2deg;
    }
    return ESP_OK;
}
