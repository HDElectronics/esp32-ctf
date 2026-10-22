/* M3 keypad adapter (variant "menu"), v0.
 *
 * The keypad is the code-entry device for every module, so this adapter runs
 * even when M3 is disabled in the pack. Keys (0-F overlay): all 16 keys are
 * hex digits, there is no enter or delete key.
 *   - the 6th digit submits the entry (d32_submit_code());
 *   - holding any key for 800 ms clears the entry (that key types nothing);
 *   - a partial entry clears itself after 10 s without a key.
 * The keypad OLED (SH1106) shows the round header, the entry line, two
 * message lines, the revealed fragments and a help line.
 *
 * v0 challenge for M3 itself: a hidden service menu. The service PIN is 6 hex
 * chars derived from the round seed (d32_service_pin(), never equal to a
 * module code of the round), typed like a code. The adapter checks it before
 * the engine sees the entry, so it is never a strike, and shows the M3 code.
 * Hint: the M5 UART2 banner carries the PIN in base64 ("svc: ..."). */
#include <stdio.h>
#include <string.h>

#include "board.h"
#include "d32_mod_internal.h"
#include "d32_mod_logic.h"
#include "esp_log.h"

static const char *TAG = "mod_keypad";

#define SCAN_MS        20     /* keypad scan period (13 I2C transfers per scan) */
#define DEBOUNCE       2      /* scans: 40 ms */
#define DRAW_MS        100    /* OLED refresh period (only changed lines are sent) */
#define KEY_HZ         2400
#define KEY_MS         25
#define CLEAR_HZ       400    /* short low beep when a long hold clears the entry */
#define CLEAR_MS       80

enum { L_HEAD = 0, L_ENTRY = 1, L_MSG1 = 3, L_MSG2 = 4, L_FRAG1 = 5, L_FRAG2 = 6, L_HELP = 7 };

static bool s_menu;         /* M3 enabled with variant "menu" */
static bool s_pin_valid;
static char s_pin[D32_ML_PIN_LEN + 1];
static d32_debounce_t s_db;
static d32_keyhold_t s_hold;
static d32_entry_t s_entry;
static uint32_t s_next_scan;
static uint32_t s_next_draw;
static char s_msg[2][BOARD_OLED_COLS + 1];
static char s_frag[2][BOARD_OLED_COLS + 1];
static char s_shown[BOARD_OLED_LINES][BOARD_OLED_COLS + 1];
static bool s_shown_valid;

static void set_line(char dst[BOARD_OLED_COLS + 1], const char *src)
{
    snprintf(dst, BOARD_OLED_COLS + 1, "%s", src ? src : "");
}

void d32_keypad_message(const char *line1, const char *line2)
{
    set_line(s_msg[0], line1);
    set_line(s_msg[1], line2);
    if ((line1 && *line1) || (line2 && *line2)) {
        ESP_LOGI(TAG, "oled: %s %s", s_msg[0], s_msg[1]);
    }
}

void d32_keypad_reveal(const d32_t *d, int slot)
{
    char code[D32_CODE_LEN + 1];
    char line[BOARD_OLED_COLS + 1];
    if (!d32_code_for(d, slot, code)) {
        return;
    }
    snprintf(line, sizeof(line), "%s CODE %s", d32_slot_id(slot), code);
    d32_keypad_message(line, "");
}

void d32_keypad_frags(const char *text)
{
    /* Up to 5 fragments ("1:B 2:L ...", 4 chars each) per line. */
    const size_t per_line = 5 * 4;
    size_t n = text ? strlen(text) : 0;
    if (n <= BOARD_OLED_COLS) {
        set_line(s_frag[0], text);
        s_frag[1][0] = '\0';
        return;
    }
    snprintf(s_frag[0], sizeof(s_frag[0]), "%.*s", (int)(per_line - 1), text);
    set_line(s_frag[1], text + per_line);
}

/* All fragments revealed so far, in slot order. */
static void update_frags(const d32_t *d)
{
    char text[64] = "";
    size_t n = 0;
    for (int s = 0; s < D32_SLOTS; s++) {
        if (d32_slot_state(d, s) != D32_SLOT_DISARMED) {
            continue;
        }
        d32_frag_t f[D32_MAX_FRAGS];
        int k = d32_slot_frags(d, s, f, D32_MAX_FRAGS);
        for (int i = 0; i < k && n + 5 < sizeof(text); i++) {
            char fs[4];
            n += (size_t)snprintf(text + n, sizeof(text) - n, "%s%s", n ? " " : "", d32_frag_str(f[i], fs));
        }
    }
    d32_keypad_frags(text);
}

static void draw(const d32_t *d)
{
    char lines[BOARD_OLED_LINES][BOARD_OLED_COLS + 1];
    memset(lines, 0, sizeof(lines));
    char phase[8];
    snprintf(phase, sizeof(phase), "%s", d32_phase_name(d32_phase(d)));
    for (char *p = phase; *p; p++) {
        if (*p >= 'a' && *p <= 'z') {
            *p = (char)(*p - 'a' + 'A');
        }
    }
    snprintf(lines[L_HEAD], sizeof(lines[0]), "%-6s S%u/%u D%d/%d", phase,
             (unsigned)d32_strikes(d), (unsigned)d32_config(d)->max_strikes,
             d32_disarmed_count(d), d32_enabled_count(d));
    char shown[D32_ML_ENTRY_LEN + 1];
    for (int i = 0; i < D32_ML_ENTRY_LEN; i++) {
        shown[i] = i < s_entry.len ? s_entry.buf[i] : '_';
    }
    shown[D32_ML_ENTRY_LEN] = '\0';
    snprintf(lines[L_ENTRY], sizeof(lines[0]), "CODE %s", shown);
    set_line(lines[L_MSG1], s_msg[0]);
    set_line(lines[L_MSG2], s_msg[1]);
    set_line(lines[L_FRAG1], s_frag[0]);
    set_line(lines[L_FRAG2], s_frag[1]);
    set_line(lines[L_HELP], "HOLD A KEY TO CLEAR");
    if (!board_oled_present(BOARD_OLED_M3)) {
        return;
    }
    bool changed = false;
    for (int l = 0; l < BOARD_OLED_LINES; l++) {
        if (!s_shown_valid || strcmp(lines[l], s_shown[l]) != 0) {
            board_oled_line(BOARD_OLED_M3, l, lines[l], l == L_HEAD);
            memcpy(s_shown[l], lines[l], sizeof(s_shown[l]));
            changed = true;
        }
    }
    s_shown_valid = true;
    if (changed) {
        board_oled_flush(BOARD_OLED_M3);
    }
}

bool d32_mod_keypad_pin(char out[D32_ML_PIN_LEN + 1])
{
    if (!s_menu || !s_pin_valid) {
        return false;
    }
    memcpy(out, s_pin, D32_ML_PIN_LEN + 1);
    return true;
}

/* The 6th digit was typed: service PIN or code submission. */
static void submit(d32_t *d)
{
    d32_entry_result_t r = d32_entry_check(&s_entry, s_pin_valid ? s_pin : NULL);
    if (r == D32_ENTRY_PARTIAL) {
        return;
    }
    if (r == D32_ENTRY_SERVICE) {
        ESP_LOGI(TAG, "service menu opened");
        char line[BOARD_OLED_COLS + 1];
        char code[D32_CODE_LEN + 1];
        if (d32_code_for(d, D32_M3, code)) {
            snprintf(line, sizeof(line), "M3 CODE %s", code);
        } else {
            snprintf(line, sizeof(line), "M3 CODE ------");
        }
        d32_keypad_message("SERVICE MENU", line);
        d32_entry_clear(&s_entry);
        return;
    }
    int slot = -1;
    d32_code_result_t cr = d32_submit_code(d, s_entry.buf, &slot);
    ESP_LOGI(TAG, "code %s entered on the keypad: result %d", s_entry.buf, (int)cr);
    d32_entry_clear(&s_entry);
    switch (cr) {
    case D32_CODE_ALREADY: {
        char line[BOARD_OLED_COLS + 1];
        snprintf(line, sizeof(line), "%s ALREADY DISARMED", d32_slot_id(slot));
        d32_keypad_message(line, "");
        break;
    }
    case D32_CODE_INVALID:
        d32_keypad_message("INVALID CODE", "");
        break;
    case D32_CODE_NOT_ARMED:
        d32_keypad_message("NO ROUND ARMED", "");
        break;
    case D32_CODE_DISARMED: /* messages come with the engine events */
    case D32_CODE_REJECTED:
    default:
        break;
    }
}

static void key_action(d32_t *d, d32_key_action_t a, char digit, uint32_t now_ms)
{
    switch (a) {
    case D32_KEY_DIGIT:
        if (d32_entry_add(&s_entry, digit, now_ms)) {
            submit(d);
        }
        break;
    case D32_KEY_CLEAR:
        d32_buzz(D32_BUZZ_CUE, CLEAR_HZ, CLEAR_MS, now_ms);
        d32_entry_clear(&s_entry);
        d32_keypad_message("CLEARED", "");
        break;
    case D32_KEY_NONE:
    default:
        break;
    }
}

static void scan(d32_t *d, uint32_t now_ms)
{
    uint16_t raw, pressed = 0, released = 0;
    if (board_keypad_scan(&raw) == ESP_OK) {
        d32_debounce_feed(&s_db, raw, DEBOUNCE, &pressed, &released);
    }
    /* Releases first, then presses, so a rolled key is typed before the next. */
    for (int i = 0; i < BOARD_KEYPAD_KEYS; i++) {
        char digit = 0;
        if (released & (1u << i)) {
            d32_key_action_t a = d32_keyhold_release(&s_hold, board_keypad_char(i), now_ms, &digit);
            key_action(d, a, digit, now_ms);
        }
    }
    for (int i = 0; i < BOARD_KEYPAD_KEYS; i++) {
        char c = board_keypad_char(i);
        char digit = 0;
        if (pressed & (1u << i)) {
            d32_buzz(D32_BUZZ_CUE, KEY_HZ, KEY_MS, now_ms);
            d32_key_action_t a = d32_keyhold_press(&s_hold, c, now_ms, &digit);
            key_action(d, a, digit, now_ms);
        }
    }
    key_action(d, d32_keyhold_tick(&s_hold, now_ms), 0, now_ms);
    if (d32_entry_idle(&s_entry, now_ms)) {
        d32_entry_clear(&s_entry);
        d32_keypad_message("ENTER CODE", "");
    }
}

static bool kp_configure(int slot, const char *variant)
{
    (void)slot;
    s_menu = variant && strcmp(variant, "menu") == 0;
    s_pin_valid = false;
    return s_menu;
}

static void kp_arm(d32_t *d, int slot, uint32_t seed)
{
    (void)slot;
    d32_entry_clear(&s_entry);
    s_pin_valid = false;
    if (s_menu) {
        /* The PIN must never equal a module code of this round. */
        char codes[D32_SLOTS][D32_CODE_LEN + 1];
        const char *list[D32_SLOTS];
        for (int i = 0; i < D32_SLOTS; i++) {
            list[i] = d32_code_for(d, i, codes[i]) ? codes[i] : NULL;
        }
        s_pin_valid = d32_service_pin(seed, list, D32_SLOTS, s_pin) >= 0;
    }
    d32_keypad_frags("");
}

static void kp_poll(d32_t *d, int slot, uint32_t now_ms)
{
    (void)slot;
    if ((int32_t)(now_ms - s_next_scan) >= 0) {
        s_next_scan = now_ms + SCAN_MS;
        scan(d, now_ms);
    }
    if ((int32_t)(now_ms - s_next_draw) >= 0) {
        s_next_draw = now_ms + DRAW_MS;
        draw(d);
    }
}

static const char *end_text(d32_end_t e)
{
    switch (e) {
    case D32_END_WON: return "CORRECT WIRE";
    case D32_END_TIME: return "TIME UP";
    case D32_END_STRIKES: return "TOO MANY STRIKES";
    case D32_END_WIRE: return "WRONG WIRE";
    default: return "";
    }
}

static void kp_event(d32_t *d, int slot, const d32_event_t *ev, uint32_t now_ms)
{
    (void)slot;
    (void)now_ms;
    char line[BOARD_OLED_COLS + 1];
    switch (ev->type) {
    case D32_EV_PHASE:
        if (ev->phase == D32_ARMED) {
            d32_keypad_message("ROUND ARMED", "");
        } else if (ev->phase == D32_FINAL) {
            d32_keypad_message("ALL DISARMED", "PULL ONE WIRE");
        } else if (ev->phase == D32_IDLE) {
            d32_keypad_message("", "");
            d32_keypad_frags("");
            d32_entry_clear(&s_entry);
        }
        break;
    case D32_EV_DISARMED:
        snprintf(line, sizeof(line), "%s DISARMED", d32_slot_id(ev->slot));
        d32_keypad_message(line, "");
        update_frags(d);
        break;
    case D32_EV_REJECTED: /* queued just before its STRIKE (none in training) */
        d32_keypad_message("CODE REJECTED", "");
        break;
    case D32_EV_STRIKE:
        if (ev->reason == D32_STRIKE_TILT) {
            set_line(s_msg[0], "TILT DETECTED");
        } else if (ev->reason == D32_STRIKE_WIRE) {
            set_line(s_msg[0], "WIRE PULLED EARLY");
        } else if (ev->reason == D32_STRIKE_MANUAL) {
            set_line(s_msg[0], "STRIKE (GAME MASTER)");
        }
        snprintf(line, sizeof(line), "STRIKE %u OF %u", (unsigned)ev->strikes,
                 (unsigned)d32_config(d)->max_strikes);
        set_line(s_msg[1], line);
        break;
    case D32_EV_RESULT: {
        uint32_t s = (ev->time_left_ms + 999) / 1000;
        if (ev->reason == D32_END_WON) {
            snprintf(line, sizeof(line), "TIME LEFT %02lu:%02lu", (unsigned long)(s / 60), (unsigned long)(s % 60));
            d32_keypad_message("ROUND WON", line);
        } else {
            d32_keypad_message("ROUND LOST", end_text((d32_end_t)ev->reason));
        }
        break;
    }
    case D32_EV_TICK:
    default:
        break;
    }
}

static void kp_reset(int slot)
{
    (void)slot;
    s_pin_valid = false;
    d32_entry_clear(&s_entry);
    memset(&s_hold, 0, sizeof(s_hold));
}

static void kp_gm_print(const d32_t *d, int slot)
{
    (void)slot;
    if (s_menu && s_pin_valid && d32_phase(d) != D32_IDLE) {
        printf("  M3 service PIN: type %s on the keypad (base64 hint on UART2)\n", s_pin);
    }
}

const d32_mod_ops_t d32_mod_keypad = {
    .name = "keypad",
    .configure = kp_configure,
    .arm = kp_arm,
    .poll = kp_poll,
    .event = kp_event,
    .reset = kp_reset,
    .gm_print = kp_gm_print,
};
