/* track_hw: hardware challenges HW-01..06 (SPEC "Hardware", "Pin map").
 *
 * HW-01 jumper GPIO26 -> GPIO33 checked once at boot.
 * HW-02 flag body in Morse on the GPIO2 LED (~12 WPM), low-priority task.
 * HW-03 LEDC PWM on GPIO25, 50% duty, per-board frequency; answer gate +-1%.
 * HW-04 bit-banged I2C write to 0x5A (SDA21/SCL22, ~50 kHz) every 5 s.
 * HW-05 bit-banged SPI mode 0 (SCK18/MOSI23/CS5, ~100 kHz) every 10 s.
 * HW-06 touch keypad A-D (T0/T4/T7/T9), per-board 6-touch code, `keypad` clue.
 *
 * Bit-bang bursts are a few ms of esp_rom_delay_us in a priority-1 task;
 * preemption only stretches the clock, which both decoders tolerate. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_rom_sys.h"
#include "esp_console.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "driver/touch_sens.h"
#include "sdkconfig.h"
#include "ctf_core.h"
#include "track_hw.h"
#if CONFIG_CTF_HW_DEV
#include "driver/pulse_cnt.h"
#endif

static const char *TAG = "track_hw";

/* Pin map (SPEC). */
#define PIN_JUMPER_OUT GPIO_NUM_26
#define PIN_JUMPER_IN  GPIO_NUM_33
#define PIN_LED        GPIO_NUM_2
#define PIN_PWM        GPIO_NUM_25
#define PIN_I2C_SDA    GPIO_NUM_21
#define PIN_I2C_SCL    GPIO_NUM_22
#define PIN_SPI_SCK    GPIO_NUM_18
#define PIN_SPI_MOSI   GPIO_NUM_23
#define PIN_SPI_CS     GPIO_NUM_5

#define TASK_PRIO 1

/* ------------------------------------------------------------------ HW-01 */

static bool jumper_follows(int level)
{
    /* High phase: input pulled down, so only a bridge can read 1.
     * Low phase: input pulled up, so only a bridge can read 0. */
    gpio_set_pull_mode(PIN_JUMPER_IN, level ? GPIO_PULLDOWN_ONLY : GPIO_PULLUP_ONLY);
    gpio_set_level(PIN_JUMPER_OUT, level);
    esp_rom_delay_us(200);
    return gpio_get_level(PIN_JUMPER_IN) == level;
}

static void hw01_check(void)
{
    gpio_config_t out = {
        .pin_bit_mask = 1ULL << PIN_JUMPER_OUT,
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config_t in = {
        .pin_bit_mask = 1ULL << PIN_JUMPER_IN,
        .mode = GPIO_MODE_INPUT,
        .pull_down_en = GPIO_PULLDOWN_ENABLE,
    };
    gpio_config(&out);
    gpio_config(&in);

    bool ok = true;
    for (int i = 0; i < 3 && ok; i++) {
        ok = jumper_follows(1) && jumper_follows(0);
    }

    gpio_reset_pin(PIN_JUMPER_OUT);
    gpio_reset_pin(PIN_JUMPER_IN);

    if (ok) {
        char flag[18];
        ctf_flag("HW-01", flag);
        printf("[hw] jumper GPIO26->GPIO33 detected. HW-01 flag: %s\n", flag);
    } else {
        ESP_LOGI(TAG, "pin check GPIO26->GPIO33: open");
    }
}

/* ------------------------------------------------------------------ HW-02 */

#define MORSE_UNIT_MS   100 /* 1200 / 12 WPM */
#define MORSE_PAUSE_MS  2000
#define MORSE_MAX_STEPS 160 /* 12 chars * (5 on + 5 off) = 120 */

typedef struct {
    uint8_t on;    /* LED level */
    uint8_t units; /* duration in Morse units */
} morse_step_t;

static morse_step_t s_morse[MORSE_MAX_STEPS];
static size_t s_morse_n;

static const char *morse_code(char c)
{
    static const char *const digits[10] = {
        "-----", ".----", "..---", "...--", "....-",
        ".....", "-....", "--...", "---..", "----.",
    };
    static const char *const letters[6] = {".-", "-...", "-.-.", "-..", ".", "..-."};
    if (c >= '0' && c <= '9') {
        return digits[c - '0'];
    }
    if (c >= 'A' && c <= 'F') {
        return letters[c - 'A'];
    }
    return "";
}

static void morse_build(void)
{
    char body[13];
    ctf_flag_body("HW-02", body);
    s_morse_n = 0;
    for (size_t i = 0; body[i]; i++) {
        const char *code = morse_code(body[i]);
        for (size_t j = 0; code[j]; j++) {
            s_morse[s_morse_n++] = (morse_step_t){1, code[j] == '-' ? 3 : 1};
            bool last_elem = code[j + 1] == '\0';
            bool last_char = body[i + 1] == '\0';
            uint8_t gap = !last_elem ? 1 : (!last_char ? 3 : 7);
            s_morse[s_morse_n++] = (morse_step_t){0, gap};
        }
    }
    memset(body, 0, sizeof(body));
}

static void morse_task(void *arg)
{
    (void)arg;
    TickType_t wake = xTaskGetTickCount();
    for (;;) {
        for (size_t i = 0; i < s_morse_n; i++) {
            gpio_set_level(PIN_LED, s_morse[i].on);
            xTaskDelayUntil(&wake, pdMS_TO_TICKS(s_morse[i].units * MORSE_UNIT_MS));
        }
        xTaskDelayUntil(&wake, pdMS_TO_TICKS(MORSE_PAUSE_MS));
    }
}

static void hw02_start(void)
{
    morse_build();
    /* Input enabled too so the level can be read back (dev self-test). */
    gpio_config_t led = {
        .pin_bit_mask = 1ULL << PIN_LED,
        .mode = GPIO_MODE_INPUT_OUTPUT,
    };
    gpio_config(&led);
    gpio_set_level(PIN_LED, 0);
    xTaskCreate(morse_task, "hw_morse", 2048, NULL, TASK_PRIO, NULL);
}

/* ------------------------------------------------------------------ HW-03 */

#define PWM_MODE    LEDC_LOW_SPEED_MODE
#define PWM_TIMER   LEDC_TIMER_3
#define PWM_CHANNEL LEDC_CHANNEL_7

static uint32_t pwm_freq(void)
{
    return 1000 + ctf_derive_u32("HW-03:freq") % 9000;
}

static bool hw03_answer(const char *value, void *ctx)
{
    (void)ctx;
    char *end = NULL;
    double v = strtod(value, &end);
    if (end == value) {
        return false;
    }
    while (*end == ' ') {
        end++;
    }
    if (*end != '\0' && strcasecmp(end, "hz") != 0) {
        return false;
    }
    double f = (double)pwm_freq();
    return fabs(v - f) <= f * 0.01;
}

static void hw03_start(void)
{
    ledc_timer_config_t tcfg = {
        .speed_mode = PWM_MODE,
        .duty_resolution = LEDC_TIMER_10_BIT,
        .timer_num = PWM_TIMER,
        .freq_hz = pwm_freq(),
        .clk_cfg = LEDC_AUTO_CLK,
    };
    ledc_channel_config_t ccfg = {
        .gpio_num = PIN_PWM,
        .speed_mode = PWM_MODE,
        .channel = PWM_CHANNEL,
        .timer_sel = PWM_TIMER,
        .duty = 512, /* 50% of 10 bits */
        .hpoint = 0,
    };
    if (ledc_timer_config(&tcfg) != ESP_OK || ledc_channel_config(&ccfg) != ESP_OK) {
        ESP_LOGE(TAG, "PWM setup failed");
    }
    ctf_set_answer("HW-03", hw03_answer, NULL);
}

/* ------------------------------------------------------------- HW-04/05 */

#define I2C_HALF_US 8 /* + gpio call overhead: ~20 us/bit, ~50 kHz */
#define I2C_ADDR    0x5A
#define SPI_HALF_US 4 /* + gpio call overhead: ~9.5 us/bit, ~105 kHz */

static void i2c_byte(uint8_t b)
{
    for (int bit = 7; bit >= 0; bit--) {
        gpio_set_level(PIN_I2C_SDA, (b >> bit) & 1);
        esp_rom_delay_us(I2C_HALF_US);
        gpio_set_level(PIN_I2C_SCL, 1);
        esp_rom_delay_us(I2C_HALF_US);
        gpio_set_level(PIN_I2C_SCL, 0);
    }
    /* ACK slot: release SDA and clock it; NACK is ignored. */
    gpio_set_level(PIN_I2C_SDA, 1);
    esp_rom_delay_us(I2C_HALF_US);
    gpio_set_level(PIN_I2C_SCL, 1);
    esp_rom_delay_us(I2C_HALF_US);
    gpio_set_level(PIN_I2C_SCL, 0);
}

static void hw04_send(const char *flag)
{
    /* START: SDA falls while SCL high. */
    gpio_set_level(PIN_I2C_SDA, 1);
    gpio_set_level(PIN_I2C_SCL, 1);
    esp_rom_delay_us(I2C_HALF_US);
    gpio_set_level(PIN_I2C_SDA, 0);
    esp_rom_delay_us(I2C_HALF_US);
    gpio_set_level(PIN_I2C_SCL, 0);

    i2c_byte((uint8_t)(I2C_ADDR << 1)); /* write */
    for (size_t i = 0; i < CTF_FLAG_LEN; i++) {
        i2c_byte((uint8_t)flag[i]);
    }

    /* STOP: SDA rises while SCL high. */
    gpio_set_level(PIN_I2C_SDA, 0);
    esp_rom_delay_us(I2C_HALF_US);
    gpio_set_level(PIN_I2C_SCL, 1);
    esp_rom_delay_us(I2C_HALF_US);
    gpio_set_level(PIN_I2C_SDA, 1);
    esp_rom_delay_us(I2C_HALF_US);
}

static void hw05_send(const char *flag)
{
    gpio_set_level(PIN_SPI_CS, 0);
    esp_rom_delay_us(SPI_HALF_US * 2);
    for (size_t i = 0; i < CTF_FLAG_LEN; i++) {
        uint8_t b = (uint8_t)flag[i];
        for (int bit = 7; bit >= 0; bit--) {
            gpio_set_level(PIN_SPI_MOSI, (b >> bit) & 1);
            esp_rom_delay_us(SPI_HALF_US);
            gpio_set_level(PIN_SPI_SCK, 1);
            esp_rom_delay_us(SPI_HALF_US);
            gpio_set_level(PIN_SPI_SCK, 0);
        }
    }
    gpio_set_level(PIN_SPI_MOSI, 0);
    esp_rom_delay_us(SPI_HALF_US * 2);
    gpio_set_level(PIN_SPI_CS, 1);
}

static uint32_t s_i2c_burst_us, s_spi_burst_us; /* last burst durations */

static void bus_task(void *arg)
{
    (void)arg;
    char flag[18];
    TickType_t wake = xTaskGetTickCount();
    for (unsigned n = 0;; n++) {
        xTaskDelayUntil(&wake, pdMS_TO_TICKS(5000));
        ctf_flag("HW-04", flag);
        int64_t t0 = esp_timer_get_time();
        hw04_send(flag);
        s_i2c_burst_us = (uint32_t)(esp_timer_get_time() - t0);
        if (n % 2 == 1) {
            ctf_flag("HW-05", flag);
            t0 = esp_timer_get_time();
            hw05_send(flag);
            s_spi_burst_us = (uint32_t)(esp_timer_get_time() - t0);
        }
        memset(flag, 0, sizeof(flag));
    }
}

static void hw0405_start(void)
{
    gpio_config_t od = {
        .pin_bit_mask = (1ULL << PIN_I2C_SDA) | (1ULL << PIN_I2C_SCL),
        .mode = GPIO_MODE_INPUT_OUTPUT_OD,
        .pull_up_en = GPIO_PULLUP_ENABLE,
    };
    gpio_config(&od);
    gpio_set_level(PIN_I2C_SDA, 1);
    gpio_set_level(PIN_I2C_SCL, 1);

    gpio_config_t pp = {
        .pin_bit_mask = (1ULL << PIN_SPI_SCK) | (1ULL << PIN_SPI_MOSI) | (1ULL << PIN_SPI_CS),
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&pp);
    gpio_set_level(PIN_SPI_CS, 1);
    gpio_set_level(PIN_SPI_SCK, 0);
    gpio_set_level(PIN_SPI_MOSI, 0);

    xTaskCreate(bus_task, "hw_bus", 2048, NULL, TASK_PRIO, NULL);
}

/* ------------------------------------------------------------------ HW-06 */

#define PAD_COUNT        4
#define CODE_LEN         6
#define TOUCH_GAP_US     (10 * 1000 * 1000)
#define TOUCH_THRESH_NUM 2 /* active below 2/3 of the untouched reading */
#define TOUCH_THRESH_DEN 3
#define TOUCH_RELEASE_US (250 * 1000) /* above release level this long = released */
#define TOUCH_POLL_MS    20

static const int s_pad_chan[PAD_COUNT] = {0, 4, 7, 9}; /* A..D = T0 T4 T7 T9 */
static touch_sensor_handle_t s_touch;
static touch_channel_handle_t s_pad[PAD_COUNT];
static uint32_t s_baseline[PAD_COUNT];
static uint32_t s_thresh[PAD_COUNT];
static QueueHandle_t s_touch_q;

typedef struct {
    uint8_t pad;
    int64_t t_us;
} touch_evt_t;

static uint32_t touch_code_value(void)
{
    return ctf_derive_u32("HW-06:code") % 4096; /* 4^6 */
}

static uint8_t touch_code_digit(uint32_t v, int i)
{
    return (uint8_t)((v >> (2 * (CODE_LEN - 1 - i))) & 3);
}

static bool touch_on_active(touch_sensor_handle_t sens, const touch_active_event_data_t *ev, void *ctx)
{
    (void)sens;
    (void)ctx;
    for (uint8_t p = 0; p < PAD_COUNT; p++) {
        if (s_pad_chan[p] == ev->chan_id) {
            touch_evt_t e = {p, esp_timer_get_time()};
            xQueueSend(s_touch_q, &e, 0); /* esp_timer task context */
        }
    }
    return false;
}

/* Debounce: a pad counts once when it first goes active; it is re-armed only
 * after its smooth reading stays above 90% of baseline for TOUCH_RELEASE_US. While
 * any pad is held, the task polls the readings every TOUCH_POLL_MS. */
static void touch_poll_release(bool held[PAD_COUNT], int64_t above_since[PAD_COUNT])
{
    int64_t now = esp_timer_get_time();
    for (int p = 0; p < PAD_COUNT; p++) {
        if (!held[p]) {
            continue;
        }
        uint32_t raw = 0;
        if (touch_channel_read_data(s_pad[p], TOUCH_CHAN_DATA_TYPE_SMOOTH, &raw) != ESP_OK ||
            raw < s_baseline[p] * 9 / 10) { /* hysteresis: release only near baseline */
            above_since[p] = 0; /* still touched (or chatter): restart release timer */
            continue;
        }
        if (above_since[p] == 0) {
            above_since[p] = now;
        } else if (now - above_since[p] >= TOUCH_RELEASE_US) {
            held[p] = false;
        }
    }
}

static void touch_task(void *arg)
{
    (void)arg;
    int progress = 0;
    int shown = 0; /* presses since the last 10 s pause, for the * feedback */
    int64_t last = 0;
    bool held[PAD_COUNT] = {false};
    int64_t above_since[PAD_COUNT] = {0};
    touch_evt_t e;
    for (;;) {
        bool any_held = false;
        for (int p = 0; p < PAD_COUNT; p++) {
            any_held |= held[p];
        }
        TickType_t wait = any_held ? pdMS_TO_TICKS(TOUCH_POLL_MS) : portMAX_DELAY;
        BaseType_t got = xQueueReceive(s_touch_q, &e, wait);
        touch_poll_release(held, above_since);
        if (got != pdTRUE) {
            continue;
        }
        if (held[e.pad]) {
            above_since[e.pad] = 0; /* re-fire during the same hold */
            continue;
        }
        held[e.pad] = true;
        above_since[e.pad] = 0;

        if (last != 0 && e.t_us - last > TOUCH_GAP_US) {
            progress = 0;
            shown = 0;
        }
        last = e.t_us;
        shown = shown % CODE_LEN + 1;
        printf("keypad: %.*s\n", shown, "******");
        uint32_t v = touch_code_value();
#if CONFIG_CTF_HW_DEV
        ESP_LOGI(TAG, "touch pad %c (progress %d)", 'A' + e.pad, progress);
#endif
        if (e.pad == touch_code_digit(v, progress)) {
            progress++;
        } else {
            progress = (e.pad == touch_code_digit(v, 0)) ? 1 : 0;
        }
        if (progress == CODE_LEN) {
            char flag[18];
            ctf_flag("HW-06", flag);
            printf("\n[hw] keypad code accepted. HW-06 flag: %s\n", flag);
            memset(flag, 0, sizeof(flag));
            progress = 0;
        }
    }
}

static esp_err_t touch_init(void)
{
    touch_sensor_sample_config_t sample[TOUCH_SAMPLE_CFG_NUM] = {
        TOUCH_SENSOR_V1_DEFAULT_SAMPLE_CONFIG(5.0, TOUCH_VOLT_LIM_L_0V5, TOUCH_VOLT_LIM_H_1V7),
    };
    touch_sensor_config_t scfg = TOUCH_SENSOR_DEFAULT_BASIC_CONFIG(1, sample);
    esp_err_t err = touch_sensor_new_controller(&scfg, &s_touch);
    if (err != ESP_OK) {
        return err;
    }
    touch_channel_config_t ccfg = {
        .abs_active_thresh = {0}, /* set after calibration */
        .charge_speed = TOUCH_CHARGE_SPEED_7,
        .init_charge_volt = TOUCH_INIT_CHARGE_VOLT_DEFAULT,
        .group = TOUCH_CHAN_TRIG_GROUP_BOTH,
    };
    for (int i = 0; i < PAD_COUNT; i++) {
        err = touch_sensor_new_channel(s_touch, s_pad_chan[i], &ccfg, &s_pad[i]);
        if (err != ESP_OK) {
            return err;
        }
    }
    touch_sensor_filter_config_t fcfg = TOUCH_SENSOR_DEFAULT_FILTER_CONFIG();
    if ((err = touch_sensor_config_filter(s_touch, &fcfg)) != ESP_OK) {
        return err;
    }

    /* Calibrate: a few one-shot scans, then threshold = 2/3 of the reading. */
    if ((err = touch_sensor_enable(s_touch)) != ESP_OK) {
        return err;
    }
    for (int i = 0; i < 3; i++) {
        if ((err = touch_sensor_trigger_oneshot_scanning(s_touch, 2000)) != ESP_OK) {
            return err;
        }
    }
    touch_sensor_disable(s_touch);
    for (int i = 0; i < PAD_COUNT; i++) {
        touch_channel_read_data(s_pad[i], TOUCH_CHAN_DATA_TYPE_SMOOTH, &s_baseline[i]);
        s_thresh[i] = s_baseline[i] * TOUCH_THRESH_NUM / TOUCH_THRESH_DEN;
        ccfg.abs_active_thresh[0] = s_thresh[i];
        if ((err = touch_sensor_reconfig_channel(s_pad[i], &ccfg)) != ESP_OK) {
            return err;
        }
    }

    touch_event_callbacks_t cbs = {.on_active = touch_on_active};
    if ((err = touch_sensor_register_callbacks(s_touch, &cbs, NULL)) != ESP_OK) {
        return err;
    }
    if ((err = touch_sensor_enable(s_touch)) != ESP_OK) {
        return err;
    }
    return touch_sensor_start_continuous_scanning(s_touch);
}

static int cmd_keypad(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    printf("Keypad pads: A=GPIO4 (T0)  B=GPIO13 (T4)  C=GPIO27 (T7)  D=GPIO32 (T9)\n"
           "Combo #%u. Read it in base 4 (6 digits), A=0 B=1 C=2 D=3.\n"
           "Touch the pads in that order, at most 10 s between touches.\n",
           (unsigned)touch_code_value());
    return 0;
}

static void hw06_start(void)
{
    s_touch_q = xQueueCreate(8, sizeof(touch_evt_t));
    esp_err_t err = touch_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "touch init failed: %s", esp_err_to_name(err));
    } else {
        xTaskCreate(touch_task, "hw_touch", 2560, NULL, TASK_PRIO, NULL);
    }
    const esp_console_cmd_t cmd = {
        .command = "keypad",
        .help = "Clue for the touch keypad (HW-06)",
        .func = cmd_keypad,
    };
    esp_console_cmd_register(&cmd);
}

/* --------------------------------------------------------------- dev mode */
#if CONFIG_CTF_HW_DEV

/* Counts rising edges on gpio for ms milliseconds; returns -1 on error. */
static int pcnt_count_edges(int gpio, int ms, int64_t *dt_us)
{
    pcnt_unit_config_t ucfg = {.low_limit = -1, .high_limit = 32767};
    pcnt_unit_handle_t unit = NULL;
    pcnt_channel_handle_t chan = NULL;
    pcnt_chan_config_t ccfg = {.edge_gpio_num = gpio, .level_gpio_num = -1};
    int count = -1;
    if (pcnt_new_unit(&ucfg, &unit) != ESP_OK) {
        return -1;
    }
    if (pcnt_new_channel(unit, &ccfg, &chan) == ESP_OK) {
        pcnt_channel_set_edge_action(chan, PCNT_CHANNEL_EDGE_ACTION_INCREASE,
                                     PCNT_CHANNEL_EDGE_ACTION_HOLD);
        pcnt_unit_enable(unit);
        pcnt_unit_clear_count(unit);
        int64_t t0 = esp_timer_get_time();
        pcnt_unit_start(unit);
        vTaskDelay(pdMS_TO_TICKS(ms));
        pcnt_unit_stop(unit);
        *dt_us = esp_timer_get_time() - t0;
        pcnt_unit_get_count(unit, &count);
        pcnt_unit_disable(unit);
        pcnt_del_channel(chan);
    }
    pcnt_del_unit(unit);
    return count;
}

static uint32_t pcnt_measure_hz(void)
{
    int64_t dt = 1;
    int count = pcnt_count_edges(PIN_PWM, 1000, &dt);
    return count < 0 ? 0 : (uint32_t)((int64_t)count * 1000000 / dt);
}

/* Counts SCL and SCK clock edges over ~10.5 s (one I2C frame = 163 SCL
 * rising edges, one SPI frame = 136 SCK rising edges). */
static void dev_bus_task(void *arg)
{
    (void)arg;
    int64_t dt = 0;
    int scl = pcnt_count_edges(PIN_I2C_SCL, 10500, &dt);
    int sck = pcnt_count_edges(PIN_SPI_SCK, 10500, &dt);
    printf("[hwdev] bus scl %d edges (%d frames, rem %d), sck %d edges (%d frames, rem %d), "
           "i2c burst %u us, spi burst %u us\n",
           scl, scl / 163, scl % 163, sck, sck / 136, sck % 136,
           (unsigned)s_i2c_burst_us, (unsigned)s_spi_burst_us);
    vTaskDelete(NULL);
}

static void dev_touch_task(void *arg)
{
    int secs = (int)(intptr_t)arg;
    for (int s = 0; s < secs; s++) {
        printf("[hwdev] touch raw/smooth/thresh:");
        for (int i = 0; i < PAD_COUNT; i++) {
            uint32_t raw = 0, smooth = 0;
            if (s_pad[i]) {
                touch_channel_read_data(s_pad[i], TOUCH_CHAN_DATA_TYPE_RAW, &raw);
                touch_channel_read_data(s_pad[i], TOUCH_CHAN_DATA_TYPE_SMOOTH, &smooth);
            }
            printf(" %c=%u/%u/%u", 'A' + i, (unsigned)raw, (unsigned)smooth,
                   (unsigned)(s_baseline[i] * TOUCH_THRESH_NUM / TOUCH_THRESH_DEN));
        }
        printf("\n");
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
    vTaskDelete(NULL);
}

/* Samples the LED pin every tick and prints each run as "<level> <ms>". */
static void dev_morse_task(void *arg)
{
    int secs = (int)(intptr_t)arg;
    int64_t end = esp_timer_get_time() + (int64_t)secs * 1000000;
    int level = gpio_get_level(PIN_LED);
    int64_t since = esp_timer_get_time();
    printf("[hwdev] morse sample start\n");
    while (esp_timer_get_time() < end) {
        vTaskDelay(1);
        int l = gpio_get_level(PIN_LED);
        if (l != level) {
            int64_t now = esp_timer_get_time();
            printf("[hwdev] m %d %d\n", level, (int)((now - since) / 1000));
            level = l;
            since = now;
        }
    }
    printf("[hwdev] morse sample end\n");
    vTaskDelete(NULL);
}

static int cmd_hwdev(int argc, char **argv)
{
    int secs = argc > 2 ? atoi(argv[2]) : 0;
    if (argc > 1 && strcmp(argv[1], "touch") == 0) {
        xTaskCreate(dev_touch_task, "hwdev_t", 2560, (void *)(intptr_t)(secs > 0 ? secs : 10),
                    TASK_PRIO, NULL);
        return 0;
    }
    if (argc > 1 && strcmp(argv[1], "bus") == 0) {
        xTaskCreate(dev_bus_task, "hwdev_b", 2560, NULL, TASK_PRIO, NULL);
        return 0;
    }
    if (argc > 1 && strcmp(argv[1], "morse") == 0) {
        xTaskCreate(dev_morse_task, "hwdev_m", 2560, (void *)(intptr_t)(secs > 0 ? secs : 65),
                    TASK_PRIO + 1, NULL);
        return 0;
    }
    uint32_t v = touch_code_value();
    char code[CODE_LEN + 1];
    for (int i = 0; i < CODE_LEN; i++) {
        code[i] = (char)('A' + touch_code_digit(v, i));
    }
    code[CODE_LEN] = '\0';
    printf("[hwdev] pwm derived %u Hz, ledc %u Hz, pcnt %u Hz\n", (unsigned)pwm_freq(),
           (unsigned)ledc_get_freq(PWM_MODE, PWM_TIMER), (unsigned)pcnt_measure_hz());
    printf("[hwdev] touch code %u = %s\n", (unsigned)v, code);
    printf("[hwdev] touch baseline A=%u B=%u C=%u D=%u\n", (unsigned)s_baseline[0],
           (unsigned)s_baseline[1], (unsigned)s_baseline[2], (unsigned)s_baseline[3]);
    unsigned units = 0;
    for (size_t i = 0; i < s_morse_n; i++) {
        units += s_morse[i].units;
    }
    printf("[hwdev] morse %u steps, %u units x %d ms + %d ms pause\n", (unsigned)s_morse_n, units,
           MORSE_UNIT_MS, MORSE_PAUSE_MS);
    return 0;
}

static void dev_register(void)
{
    const esp_console_cmd_t cmd = {
        .command = "hwdev",
        .help = "HW dev self-test: hwdev | hwdev touch [s] | hwdev morse [s] | hwdev bus",
        .func = cmd_hwdev,
    };
    esp_console_cmd_register(&cmd);
}
#endif /* CONFIG_CTF_HW_DEV */

/* ------------------------------------------------------------------ entry */

void track_hw_start(void)
{
    hw01_check();
    hw02_start();
    hw03_start();
    hw0405_start();
    hw06_start();
#if CONFIG_CTF_HW_DEV
    dev_register();
    ESP_LOGW(TAG, "CONFIG_CTF_HW_DEV is on: not for release");
#endif
}
