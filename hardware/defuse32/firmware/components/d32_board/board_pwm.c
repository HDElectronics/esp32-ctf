#include "board.h"

#include "driver/ledc.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "sdkconfig.h"

static const char *TAG = "board_pwm";

#define PWM_MODE            LEDC_LOW_SPEED_MODE
#define BUZZ_TIMER          LEDC_TIMER_0
#define BUZZ_CHANNEL        LEDC_CHANNEL_0
#define BUZZ_RES            LEDC_TIMER_10_BIT
#define BUZZ_DUTY_ON        512             /* 50 % */
#define SERVO_TIMER         LEDC_TIMER_1
#define SERVO_CHANNEL       LEDC_CHANNEL_1
#define SERVO_RES           LEDC_TIMER_14_BIT
#define SERVO_HZ            50
#define SERVO_MIN_US        500
#define SERVO_MAX_US        2500

static bool s_buzz_ready;
static volatile bool s_buzz_busy;
static esp_timer_handle_t s_buzz_timer;
static bool s_servo_ready;

/* ---- buzzer ------------------------------------------------------------- */

static void buzz_off(void)
{
    ledc_set_duty(PWM_MODE, BUZZ_CHANNEL, 0);
    ledc_update_duty(PWM_MODE, BUZZ_CHANNEL);
    s_buzz_busy = false;
}

static void buzz_timer_cb(void *arg)
{
    (void)arg;
    buzz_off();
}

esp_err_t board_buzzer_init(void)
{
    if (s_buzz_ready) {
        return ESP_OK;
    }
    ledc_timer_config_t t = {
        .speed_mode = PWM_MODE,
        .duty_resolution = BUZZ_RES,
        .timer_num = BUZZ_TIMER,
        .freq_hz = 2000,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    esp_err_t err = ledc_timer_config(&t);
    if (err == ESP_OK) {
        ledc_channel_config_t c = {
            .gpio_num = BOARD_PIN_BUZZER,
            .speed_mode = PWM_MODE,
            .channel = BUZZ_CHANNEL,
            .timer_sel = BUZZ_TIMER,
            .duty = 0,      /* Q1 off */
            .hpoint = 0,
        };
        err = ledc_channel_config(&c);
    }
    if (err == ESP_OK && !s_buzz_timer) {
        const esp_timer_create_args_t ta = { .callback = buzz_timer_cb, .name = "buzz" };
        err = esp_timer_create(&ta, &s_buzz_timer);
    }
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "buzzer init failed: %s", esp_err_to_name(err));
        return err;
    }
    s_buzz_ready = true;
    return ESP_OK;
}

void board_buzzer_deinit(void)
{
    if (!s_buzz_ready) {
        return;
    }
    esp_timer_stop(s_buzz_timer);
    buzz_off();
    ledc_stop(PWM_MODE, BUZZ_CHANNEL, 0);
    esp_timer_delete(s_buzz_timer);
    s_buzz_timer = NULL;
    s_buzz_ready = false;
}

esp_err_t board_buzzer_tone(uint32_t hz, uint32_t ms)
{
    if (!s_buzz_ready) {
        return ESP_ERR_INVALID_STATE;
    }
    if (hz < 50 || hz > 10000) {
        return ESP_ERR_INVALID_ARG;
    }
    esp_timer_stop(s_buzz_timer);   /* ESP_ERR_INVALID_STATE if not running: fine */
    esp_err_t err = ledc_set_freq(PWM_MODE, BUZZ_TIMER, hz);
    if (err == ESP_OK) {
        err = ledc_set_duty(PWM_MODE, BUZZ_CHANNEL, BUZZ_DUTY_ON);
    }
    if (err == ESP_OK) {
        err = ledc_update_duty(PWM_MODE, BUZZ_CHANNEL);
    }
    if (err != ESP_OK) {
        buzz_off();
        return err;
    }
    s_buzz_busy = true;
    if (ms > 0) {
        esp_timer_start_once(s_buzz_timer, (uint64_t)ms * 1000);
    }
    return ESP_OK;
}

esp_err_t board_buzzer_stop(void)
{
    if (!s_buzz_ready) {
        return ESP_ERR_INVALID_STATE;
    }
    esp_timer_stop(s_buzz_timer);
    buzz_off();
    return ESP_OK;
}

bool board_buzzer_busy(void)
{
    return s_buzz_busy;
}

/* ---- servo -------------------------------------------------------------- */

esp_err_t board_servo_init(void)
{
    if (s_servo_ready) {
        return ESP_OK;
    }
    ledc_timer_config_t t = {
        .speed_mode = PWM_MODE,
        .duty_resolution = SERVO_RES,
        .timer_num = SERVO_TIMER,
        .freq_hz = SERVO_HZ,
        .clk_cfg = LEDC_AUTO_CLK,
    };
    esp_err_t err = ledc_timer_config(&t);
    if (err == ESP_OK) {
        ledc_channel_config_t c = {
            .gpio_num = BOARD_PIN_SERVO,
            .speed_mode = PWM_MODE,
            .channel = SERVO_CHANNEL,
            .timer_sel = SERVO_TIMER,
            .duty = 0,      /* no pulses until the first angle */
            .hpoint = 0,
        };
        err = ledc_channel_config(&c);
    }
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "servo init failed: %s", esp_err_to_name(err));
        return err;
    }
    s_servo_ready = true;
    return ESP_OK;
}

void board_servo_deinit(void)
{
    if (s_servo_ready) {
        ledc_stop(PWM_MODE, SERVO_CHANNEL, 0);
        s_servo_ready = false;
    }
}

esp_err_t board_servo_angle(int degrees)
{
    if (!s_servo_ready) {
        return ESP_ERR_INVALID_STATE;
    }
    if (degrees < 0 || degrees > 180) {
        return ESP_ERR_INVALID_ARG;
    }
    uint32_t us = SERVO_MIN_US + (uint32_t)degrees * (SERVO_MAX_US - SERVO_MIN_US) / 180;
    uint32_t period_us = 1000000 / SERVO_HZ;
    uint32_t duty = us * ((1u << SERVO_RES) - 1) / period_us;
    esp_err_t err = ledc_set_duty(PWM_MODE, SERVO_CHANNEL, duty);
    if (err == ESP_OK) {
        err = ledc_update_duty(PWM_MODE, SERVO_CHANNEL);
    }
    return err;
}

esp_err_t board_servo_open(void)
{
    return board_servo_angle(CONFIG_D32_SERVO_OPEN_DEG);
}

esp_err_t board_servo_close(void)
{
    return board_servo_angle(CONFIG_D32_SERVO_CLOSED_DEG);
}

esp_err_t board_servo_release(void)
{
    if (!s_servo_ready) {
        return ESP_ERR_INVALID_STATE;
    }
    esp_err_t err = ledc_set_duty(PWM_MODE, SERVO_CHANNEL, 0);
    if (err == ESP_OK) {
        err = ledc_update_duty(PWM_MODE, SERVO_CHANNEL);
    }
    return err;
}
