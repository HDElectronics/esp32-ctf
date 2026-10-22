#include "board.h"

#include "driver/touch_sens.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

static const char *TAG = "board_touch";

#define TOUCH_CAL_SAMPLES   8
#define TOUCH_MIN_BASELINE  100     /* below this the pad looks shorted/broken */

static const int s_chan[BOARD_TOUCH_COUNT] = {
    BOARD_TOUCH_CH_T0, BOARD_TOUCH_CH_T4, BOARD_TOUCH_CH_T6, BOARD_TOUCH_CH_T3,
};

static touch_sensor_handle_t s_sens;
static touch_channel_handle_t s_ch[BOARD_TOUCH_COUNT];
static uint32_t s_base[BOARD_TOUCH_COUNT];
static bool s_running;

int board_touch_channel(board_touch_pad_t pad)
{
    return pad < BOARD_TOUCH_COUNT ? s_chan[pad] : -1;
}

static void touch_cleanup(void)
{
    if (s_running) {
        touch_sensor_stop_continuous_scanning(s_sens);
        touch_sensor_disable(s_sens);
        s_running = false;
    }
    for (int i = 0; i < BOARD_TOUCH_COUNT; i++) {
        if (s_ch[i]) {
            touch_sensor_del_channel(s_ch[i]);
            s_ch[i] = NULL;
        }
    }
    if (s_sens) {
        touch_sensor_del_controller(s_sens);
        s_sens = NULL;
    }
}

esp_err_t board_touch_init(void)
{
    if (s_sens) {
        return ESP_OK;
    }
    touch_sensor_sample_config_t sample[TOUCH_SAMPLE_CFG_NUM] = {
        TOUCH_SENSOR_V1_DEFAULT_SAMPLE_CONFIG(5.0, TOUCH_VOLT_LIM_L_0V5, TOUCH_VOLT_LIM_H_1V7),
    };
    touch_sensor_config_t sc = TOUCH_SENSOR_DEFAULT_BASIC_CONFIG(1, sample);
    esp_err_t err = touch_sensor_new_controller(&sc, &s_sens);
    if (err != ESP_OK) {
        s_sens = NULL;
        ESP_LOGW(TAG, "controller: %s", esp_err_to_name(err));
        return err;
    }
    touch_channel_config_t cc = {
        .abs_active_thresh = { 0 },     /* not used: we threshold in software */
        .charge_speed = TOUCH_CHARGE_SPEED_7,
        .init_charge_volt = TOUCH_INIT_CHARGE_VOLT_DEFAULT,
        .group = TOUCH_CHAN_TRIG_GROUP_BOTH,
    };
    for (int i = 0; i < BOARD_TOUCH_COUNT && err == ESP_OK; i++) {
        err = touch_sensor_new_channel(s_sens, s_chan[i], &cc, &s_ch[i]);
    }
    if (err == ESP_OK) {
        touch_sensor_filter_config_t fc = TOUCH_SENSOR_DEFAULT_FILTER_CONFIG();
        err = touch_sensor_config_filter(s_sens, &fc);
    }
    if (err == ESP_OK) {
        err = touch_sensor_enable(s_sens);
    }
    if (err == ESP_OK) {
        err = touch_sensor_start_continuous_scanning(s_sens);
        s_running = (err == ESP_OK);
    }
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "init failed: %s", esp_err_to_name(err));
        touch_cleanup();
        return err;
    }
    return board_touch_calibrate();
}

void board_touch_deinit(void)
{
    touch_cleanup();
}

bool board_touch_ready(void)
{
    return s_running;
}

esp_err_t board_touch_read(board_touch_pad_t pad, uint32_t *value)
{
    if (!s_running) {
        return ESP_ERR_INVALID_STATE;
    }
    if (pad >= BOARD_TOUCH_COUNT) {
        return ESP_ERR_INVALID_ARG;
    }
    return touch_channel_read_data(s_ch[pad], TOUCH_CHAN_DATA_TYPE_SMOOTH, value);
}

esp_err_t board_touch_calibrate(void)
{
    if (!s_running) {
        return ESP_ERR_INVALID_STATE;
    }
    uint64_t sum[BOARD_TOUCH_COUNT] = { 0 };
    vTaskDelay(pdMS_TO_TICKS(100)); /* let the software filter settle */
    for (int n = 0; n < TOUCH_CAL_SAMPLES; n++) {
        for (int i = 0; i < BOARD_TOUCH_COUNT; i++) {
            uint32_t v = 0;
            touch_channel_read_data(s_ch[i], TOUCH_CHAN_DATA_TYPE_SMOOTH, &v);
            sum[i] += v;
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
    esp_err_t ret = ESP_OK;
    for (int i = 0; i < BOARD_TOUCH_COUNT; i++) {
        s_base[i] = (uint32_t)(sum[i] / TOUCH_CAL_SAMPLES);
        if (s_base[i] < TOUCH_MIN_BASELINE) {
            ESP_LOGW(TAG, "T%d baseline %lu looks wrong (pad shorted or touched during calibration?)",
                     s_chan[i], (unsigned long)s_base[i]);
            ret = ESP_ERR_INVALID_RESPONSE;
        }
    }
    return ret;
}

uint32_t board_touch_baseline(board_touch_pad_t pad)
{
    return pad < BOARD_TOUCH_COUNT ? s_base[pad] : 0;
}

bool board_touch_touched(board_touch_pad_t pad)
{
    uint32_t v;
    if (board_touch_read(pad, &v) != ESP_OK || s_base[pad] < TOUCH_MIN_BASELINE) {
        return false;
    }
    uint32_t thresh = s_base[pad] - s_base[pad] * CONFIG_D32_TOUCH_THRESH_PCT / 100;
    return v < thresh;
}

uint8_t board_touch_mask(void)
{
    uint8_t m = 0;
    for (int i = 0; i < BOARD_TOUCH_COUNT; i++) {
        if (board_touch_touched((board_touch_pad_t)i)) {
            m |= (uint8_t)(1u << i);
        }
    }
    return m;
}
