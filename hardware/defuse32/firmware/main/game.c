/* Game task (FIRMWARE.md "Firmware behaviour (v0)"): 10 ms tick into
 * d32_engine, adapter polling, key switch and tilt inputs, event-driven UI.
 *
 * Locking: s_lock guards the engine context and everything the adapters
 * touch. The game task holds it for one tick; console commands take it for
 * one call. The keypad OLED is drawn only from the game task. */
#include "game.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "board.h"
#include "ctf_core.h"
#include "d32_modules.h"
#include "d32_pack.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_random.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "freertos/task.h"
#include "sdkconfig.h"

static const char *TAG = "game";

#define TICK_MS        10
#define KEYSW_MS       50
#define TILT_MS        100
#define UI_MS          50
#define TASK_STACK     6144
#define TASK_PRIO      5

static SemaphoreHandle_t s_lock;
static SemaphoreHandle_t s_ctf_lock;
static d32_t s_d;
static bool s_hatch_open;

static void lock(void)
{
    xSemaphoreTake(s_lock, portMAX_DELAY);
}

static void unlock(void)
{
    xSemaphoreGive(s_lock);
}

/* ---- ctf_core backend -----------------------------------------------------
 * Defuse32 uses only ctf_core's key and derivation, not its challenge
 * catalogue or scoring, so the progress record lives in RAM: load reports
 * "nothing stored", save drops the record. */

static bool ctf_ram_load(void *buf, size_t len, void *ctx)
{
    (void)buf;
    (void)len;
    (void)ctx;
    return false;
}

static bool ctf_ram_save(const void *buf, size_t len, void *ctx)
{
    (void)buf;
    (void)len;
    (void)ctx;
    return true;
}

static void ctf_lock_fn(void *ctx)
{
    (void)ctx;
    xSemaphoreTake(s_ctf_lock, portMAX_DELAY);
}

static void ctf_unlock_fn(void *ctx)
{
    (void)ctx;
    xSemaphoreGive(s_ctf_lock);
}

/* ---- config ---------------------------------------------------------------- */

static void config_from_pack(const d32_pack_t *p, int minutes, d32_config_t *cfg)
{
    d32_config_default(cfg);
    int m = minutes > 0 ? minutes : p->minutes;
    if (m > D32_MAX_MINUTES) {
        ESP_LOGW(TAG, "round of %d min clipped to %d (MM:SS display)", m, D32_MAX_MINUTES);
        m = D32_MAX_MINUTES;
    }
    cfg->minutes = (uint16_t)m;
    cfg->max_strikes = (uint8_t)p->max_strikes;
    cfg->strike_rate_permille = (uint16_t)lroundf(p->strike_rate * 1000.0f);
    cfg->training = p->training;
    for (int i = 0; i < D32_SLOTS && i < D32_PACK_SLOTS; i++) {
        cfg->slot[i].enabled = p->slots[i].enabled;
        snprintf(cfg->slot[i].variant, sizeof(cfg->slot[i].variant), "%s", p->slots[i].variant);
    }
    unsigned fixed = d32_config_sanitize(cfg);
    if (fixed) {
        ESP_LOGW(TAG, "pack settings: %u value(s) replaced by engine defaults", fixed);
    }
}

/* ---- round control (lock held) ---------------------------------------------- */

static void reset_locked(void)
{
    d32_reset(&s_d);
    d32_modules_reset();
    if (s_hatch_open) {
        board_servo_close();
        s_hatch_open = false;
    }
}

static d32_arm_result_t arm_locked(int minutes)
{
    d32_phase_t ph = d32_phase(&s_d);
    if (ph == D32_ARMED || ph == D32_FINAL) {
        return D32_ARM_BUSY;
    }
    if (ph != D32_IDLE) {
        reset_locked();
    }
    d32_config_t cfg;
    config_from_pack(d32_pack_current(), minutes, &cfg);
    d32_set_config(&s_d, &cfg);
    d32_modules_configure(&cfg);
    uint32_t seed = esp_random();
    d32_arm_result_t r = d32_arm(&s_d, seed);
    if (r == D32_ARM_OK) {
        d32_modules_arm(&s_d, seed);
        board_lis3dh_set_reference(); /* "level" = the orientation at arming */
        ESP_LOGI(TAG, "round armed: %u min, %d module(s), pack %s", (unsigned)cfg.minutes,
                 d32_enabled_count(&s_d), d32_pack_current_name());
    }
    return r;
}

/* ---- UI ------------------------------------------------------------------------ */

static const board_led_t s_status_led[D32_SLOTS] = {
    BOARD_LED_RADIO_STATUS, BOARD_LED_TIMER_STATUS, BOARD_LED_KEYPAD_STATUS,
    BOARD_LED_WIRES_STATUS, BOARD_LED_PROBE_STATUS, BOARD_LED_SENSOR_STATUS,
};

static void ui_leds(void)
{
    if (!board_leds_ready()) {
        return;
    }
    d32_phase_t ph = d32_phase(&s_d);
    for (int i = 0; i < D32_SLOTS; i++) {
        uint8_t r = 0, g = 0, b = 0;
        d32_slot_state_t st = d32_slot_state(&s_d, i);
        if (st == D32_SLOT_DISABLED) {
            /* off */
        } else if (ph == D32_WON) {
            g = 255;
        } else if (ph == D32_LOST) {
            r = 255;
        } else if (st == D32_SLOT_ARMED) {
            r = 255;
        } else if (st == D32_SLOT_DISARMED) {
            g = 255;
        } else {
            r = g = b = 16; /* idle: dim */
        }
        board_leds_set(s_status_led[i], r, g, b);
    }
    unsigned strikes = d32_strikes(&s_d);
    for (unsigned i = 0; i < 3; i++) {
        board_leds_set((board_led_t)(BOARD_LED_STRIKE1 + i), i < strikes ? 255 : 0, 0, 0);
    }
    board_leds_set(BOARD_LED_RADIO_LINK1, 0, 0, 0);
    board_leds_set(BOARD_LED_RADIO_LINK2, 0, 0, 0);
    /* Simon LEDs belong to the M6 adapter. */
    board_leds_show();
}

static void ui_display(void)
{
    static char s_last[5];
    static int s_last_colon = -1;
    char text[5];
    d32_phase_t ph = d32_phase(&s_d);
    bool colon = true;
    if (ph == D32_IDLE) {
        snprintf(text, sizeof(text), "----");
        colon = false;
    } else {
        char t[6];
        d32_time_str(&s_d, t); /* "MM:SS" */
        text[0] = t[0];
        text[1] = t[1];
        text[2] = t[3];
        text[3] = t[4];
        text[4] = '\0';
        if ((ph == D32_ARMED || ph == D32_FINAL) && !d32_config(&s_d)->training) {
            colon = (d32_time_left_ms(&s_d) % 1000) >= 500; /* blink once per second */
        }
    }
    if (strcmp(text, s_last) == 0 && s_last_colon == (int)colon) {
        return;
    }
    if (board_tm1637_text(text, colon) == ESP_OK) {
        memcpy(s_last, text, sizeof(s_last));
        s_last_colon = colon;
    }
}

static void frag_text(const d32_event_t *ev, char *out, size_t cap)
{
    size_t n = 0;
    out[0] = '\0';
    for (int i = 0; i < ev->nfrags && n + 5 < cap; i++) {
        char fs[4];
        n += (size_t)snprintf(out + n, cap - n, "%s%s", i ? " " : "", d32_frag_str(ev->frags[i], fs));
    }
    if (!n) {
        snprintf(out, cap, "none");
    }
}

static const char *end_name(uint8_t reason)
{
    switch ((d32_end_t)reason) {
    case D32_END_WON: return "correct wire";
    case D32_END_TIME: return "time up";
    case D32_END_STRIKES: return "too many strikes";
    case D32_END_WIRE: return "wrong wire";
    default: return "-";
    }
}

static void ui_event(const d32_event_t *ev, uint32_t now)
{
    char buf[40];
    switch (ev->type) {
    case D32_EV_PHASE:
        ESP_LOGI(TAG, "phase: %s", d32_phase_name(ev->phase));
        if (ev->phase == D32_ARMED) {
            d32_buzz(D32_BUZZ_CUE, 1000, 150, now);
        } else if (ev->phase == D32_FINAL) {
            ESP_LOGI(TAG, "all modules disarmed: pull one wire");
            d32_buzz(D32_BUZZ_CUE, 1500, 300, now);
        }
        break;
    case D32_EV_DISARMED:
        frag_text(ev, buf, sizeof(buf));
        ESP_LOGI(TAG, "%s %s disarmed, fragments: %s", d32_slot_id(ev->slot),
                 d32_slot_name(ev->slot), buf);
        d32_buzz(D32_BUZZ_CUE, 1800, 150, now);
        break;
    case D32_EV_STRIKE:
        ESP_LOGI(TAG, "strike %u (reason %u), clock rate x%lu.%03lu", (unsigned)ev->strikes,
                 (unsigned)ev->reason, (unsigned long)(ev->rate_permille / 1000),
                 (unsigned long)(ev->rate_permille % 1000));
        d32_buzz(D32_BUZZ_CUE, 300, 400, now);
        break;
    case D32_EV_REJECTED:
        ESP_LOGI(TAG, "code rejected");
        break;
    case D32_EV_TICK:
        d32_buzz(D32_BUZZ_TICK, 3000, 15, now);
        break;
    case D32_EV_RESULT:
        if (ev->reason == D32_END_WON) {
            uint32_t s = (ev->time_left_ms + 999) / 1000;
            ESP_LOGI(TAG, "round WON: %02lu:%02lu left, %u strike(s)", (unsigned long)(s / 60),
                     (unsigned long)(s % 60), (unsigned)ev->strikes);
            d32_buzz(D32_BUZZ_CUE, 2000, 1000, now);
            if (board_servo_open() == ESP_OK) {
                s_hatch_open = true;
            }
        } else {
            ESP_LOGI(TAG, "round LOST: %s, %u strike(s)", end_name(ev->reason), (unsigned)ev->strikes);
            d32_buzz(D32_BUZZ_CUE, 200, 1500, now);
        }
        break;
    default:
        break;
    }
}

/* ---- inputs ----------------------------------------------------------------------- */

static void poll_keyswitch(void)
{
    static int s_prev = -1;   /* -1: unknown (first read sets it, no edge) */
    static int s_cand = -1;
    bool armed;
    if (board_keyswitch_armed(&armed) != ESP_OK) {
        return;
    }
    int v = armed ? 1 : 0;
    if (v != s_cand) {      /* two equal reads in a row (50 ms apart) */
        s_cand = v;
        return;
    }
    if (s_prev < 0) {
        s_prev = v;         /* key already turned at boot: wait for a real turn */
        return;
    }
    if (v == s_prev) {
        return;
    }
    s_prev = v;
    if (v) {
        d32_arm_result_t r = arm_locked(0);
        if (r != D32_ARM_OK) {
            ESP_LOGI(TAG, "key switch: round not started (%s)",
                     r == D32_ARM_BUSY ? "round running" : "no module enabled");
        }
    }
}

static void poll_tilt(uint32_t now)
{
    d32_phase_t ph = d32_phase(&s_d);
    if ((ph != D32_ARMED && ph != D32_FINAL) || !board_lis3dh_present()) {
        return;
    }
    float tilt;
    if (board_lis3dh_tilt(&tilt, NULL, NULL) == ESP_OK && tilt > (float)CONFIG_D32_TILT_DEG) {
        if (d32_tilt(&s_d, now)) {
            ESP_LOGI(TAG, "tilt %.0f deg (limit %d)", (double)tilt, CONFIG_D32_TILT_DEG);
        }
    }
}

/* ---- task ----------------------------------------------------------------------------- */

/* 10 ms = 1 tick at the default CONFIG_FREERTOS_HZ=100; never 0. */
static const TickType_t s_tick_ticks = pdMS_TO_TICKS(TICK_MS) > 0 ? pdMS_TO_TICKS(TICK_MS) : 1;

static void game_task(void *arg)
{
    (void)arg;
    TickType_t wake = xTaskGetTickCount();
    int64_t prev_us = esp_timer_get_time();
    uint32_t next_key = 0, next_tilt = 0, next_ui = 0;
    for (;;) {
        vTaskDelayUntil(&wake, s_tick_ticks);
        int64_t now_us = esp_timer_get_time();
        uint32_t dt = (uint32_t)((now_us - prev_us) / 1000);
        prev_us += (int64_t)dt * 1000; /* keep the sub-ms remainder */
        uint32_t now = (uint32_t)(now_us / 1000);

        lock();
        d32_tick(&s_d, dt);
        if ((int32_t)(now - next_key) >= 0) {
            next_key = now + KEYSW_MS;
            poll_keyswitch();
        }
        if ((int32_t)(now - next_tilt) >= 0) {
            next_tilt = now + TILT_MS;
            poll_tilt(now);
        }
        d32_modules_poll(&s_d, now);
        d32_event_t ev;
        while (d32_poll_event(&s_d, &ev)) {
            ui_event(&ev, now);
            d32_modules_event(&s_d, &ev, now);
        }
        if ((int32_t)(now - next_ui) >= 0) {
            next_ui = now + UI_MS;
            ui_leds();
            ui_display();
        }
        unlock();
    }
}

void game_init(void)
{
    s_lock = xSemaphoreCreateMutex();
    s_ctf_lock = xSemaphoreCreateMutex();
    configASSERT(s_lock && s_ctf_lock);

    uint8_t mac[6] = { 0 };
    esp_read_mac(mac, ESP_MAC_WIFI_STA); /* chip base MAC (eFuse) */
    static const ctf_backend_t be = {
        .load = ctf_ram_load,
        .save = ctf_ram_save,
        .lock = ctf_lock_fn,
        .unlock = ctf_unlock_fn,
        .ctx = NULL,
    };
    ctf_init(mac, &be);

    d32_config_t cfg;
    config_from_pack(d32_pack_current(), 0, &cfg);
    d32_init(&s_d, &cfg);
    d32_modules_configure(&cfg);
}

void game_start(void)
{
    BaseType_t ok = xTaskCreate(game_task, "game", TASK_STACK, NULL, TASK_PRIO, NULL);
    if (ok != pdPASS) {
        ESP_LOGE(TAG, "game task not started");
    }
}

/* ---- console API ------------------------------------------------------------------------ */

d32_arm_result_t game_round_start(int minutes)
{
    lock();
    d32_arm_result_t r = arm_locked(minutes);
    unlock();
    return r;
}

void game_round_reset(void)
{
    lock();
    reset_locked();
    unlock();
}

bool game_round_active(void)
{
    lock();
    d32_phase_t ph = d32_phase(&s_d);
    unlock();
    return ph == D32_ARMED || ph == D32_FINAL;
}

d32_code_result_t game_submit_code(const char *text, int *slot_out)
{
    lock();
    d32_code_result_t r = d32_submit_code(&s_d, text, slot_out);
    unlock();
    return r;
}

d32_wire_result_t game_wire(int index)
{
    lock();
    d32_wire_result_t r = d32_wire_pulled(&s_d, index);
    unlock();
    return r;
}

bool game_strike(void)
{
    lock();
    bool ok = d32_strike(&s_d, D32_STRIKE_MANUAL);
    unlock();
    return ok;
}

static const char *slot_state_name(d32_slot_state_t s)
{
    switch (s) {
    case D32_SLOT_DISABLED: return "off";
    case D32_SLOT_IDLE: return "idle";
    case D32_SLOT_ARMED: return "armed";
    case D32_SLOT_DISARMED: return "disarmed";
    default: return "?";
    }
}

void game_print_status(void)
{
    lock();
    const d32_config_t *c = d32_config(&s_d);
    d32_phase_t ph = d32_phase(&s_d);
    char t[6];
    d32_time_str(&s_d, t);
    uint32_t rate = d32_rate_permille(&s_d);
    printf("  round    %s", d32_phase_name(ph));
    if (ph != D32_IDLE) {
        printf(", %s left, clock x%lu.%03lu", t, (unsigned long)(rate / 1000), (unsigned long)(rate % 1000));
    }
    printf(", strikes %u/%u%s\n", (unsigned)d32_strikes(&s_d), (unsigned)c->max_strikes,
           c->training ? ", TRAINING" : "");
    if (ph == D32_WON || ph == D32_LOST) {
        printf("  result   %s\n", end_name((uint8_t)d32_end_reason(&s_d)));
    }
    uint32_t left;
    uint8_t used;
    if (d32_score(&s_d, &left, &used)) {
        printf("  score    %lu ms left, %u strike(s)\n", (unsigned long)left, (unsigned)used);
    }
    const d32_pack_t *p = d32_pack_current();
    printf("  pack     %s: %d min, %d strikes, rate x%.2f%s (used by the next round)\n",
           d32_pack_current_name(), p->minutes, p->max_strikes, (double)p->strike_rate,
           p->training ? ", training" : "");
    for (int i = 0; i < D32_SLOTS; i++) {
        bool known = d32_modules_variant_known(i);
        printf("  %s %-8s %-9s %-14s%s\n", d32_slot_id(i), d32_slot_name(i),
               slot_state_name(d32_slot_state(&s_d, i)), c->slot[i].variant,
               c->slot[i].enabled && !known ? " (v0 placeholder: console code)" : "");
    }
    if (ph != D32_IDLE) {
        printf("  modules  %d/%d disarmed\n", d32_disarmed_count(&s_d), d32_enabled_count(&s_d));
        printf("  fragments");
        int shown = 0;
        for (int i = 0; i < D32_SLOTS; i++) {
            if (d32_slot_state(&s_d, i) != D32_SLOT_DISARMED) {
                continue;
            }
            d32_frag_t f[D32_MAX_FRAGS];
            int n = d32_slot_frags(&s_d, i, f, D32_MAX_FRAGS);
            for (int k = 0; k < n; k++) {
                char fs[4];
                printf(" %s", d32_frag_str(f[k], fs));
                shown++;
            }
        }
        printf("%s\n", shown ? "" : " none yet");
        printf("  wires    0 RED, 1 BLUE, 2 YELLOW, 3 GREEN, 4 WHITE, 5 BLACK\n");
    }
    if (d32_events_dropped(&s_d)) {
        printf("  (%lu UI event(s) dropped)\n", (unsigned long)d32_events_dropped(&s_d));
    }
    unlock();
}

void game_print_codes(void)
{
    lock();
    if (d32_phase(&s_d) == D32_IDLE) {
        unlock();
        printf("no round armed (round start)\n");
        return;
    }
    printf("GAME MASTER ONLY: current round codes\n");
    for (int i = 0; i < D32_SLOTS; i++) {
        char code[D32_CODE_LEN + 1];
        if (d32_code_for(&s_d, i, code)) {
            printf("  %s %-8s %s  %s\n", d32_slot_id(i), d32_slot_name(i), code,
                   slot_state_name(d32_slot_state(&s_d, i)));
        }
    }
    int w = d32_target_wire(&s_d);
    printf("  target wire: %d (%s)\n", w, d32_wire_colour(w));
    d32_modules_gm_print(&s_d);
    unlock();
}
