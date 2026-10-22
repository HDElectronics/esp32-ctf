/* Game-master console commands: board checks (hw scan, led test, buzz, servo,
 * keys, wires, touch, ir, tilt), packs, and the round commands (status,
 * round start/reset/codes, code, wire, strike) that go through the game task
 * (game.h). The round commands need no plate hardware. */
#include "console_cmds.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "board.h"
#include "d32_pack.h"
#include "esp_console.h"
#include "esp_timer.h"
#include "game.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define WATCH_MS 10000  /* keys / ir watch duration */

static const char *addr_name(uint8_t a)
{
    switch (a) {
    case BOARD_I2C_ADDR_MCP_U2: return "MCP23017 U2";
    case BOARD_I2C_ADDR_MCP_U3: return "MCP23017 U3";
    case BOARD_I2C_ADDR_NFC: return "PN532 NFC";
    case BOARD_I2C_ADDR_OLED_M1: return "SSD1306 OLED (M1)";
    case BOARD_I2C_ADDR_OLED_M3: return "SH1106 OLED (M3)";
    case BOARD_I2C_ADDR_EEPROM: return "24C32 EEPROM (M5)";
    case BOARD_I2C_ADDR_LIS3DH: return "LIS3DH tilt";
    default: return "unknown";
    }
}

static bool parse_int(const char *s, long lo, long hi, long *out)
{
    char *end;
    long v = strtol(s, &end, 10);
    if (!*s || *end || v < lo || v > hi) {
        return false;
    }
    *out = v;
    return true;
}

static int64_t now_ms(void)
{
    return esp_timer_get_time() / 1000;
}

/* ---- hw ------------------------------------------------------------------ */

static int cmd_hw(int argc, char **argv)
{
    if (argc < 2 || strcmp(argv[1], "scan") != 0) {
        printf("usage: hw scan\n");
        return 1;
    }
    uint8_t found[32];
    int n = board_i2c_scan(found, 32);
    if (n < 0) {
        printf("I2C bus down (3V3P rail off? connect the 5 V input and reboot)\n");
    } else {
        printf("I2C: %d device(s)\n", n);
        for (int i = 0; i < n && i < 32; i++) {
            printf("  0x%02X  %s\n", found[i], addr_name(found[i]));
        }
    }
    board_print_presence();
    return 0;
}

/* ---- led test --------------------------------------------------------------- */

static const char *const s_led_names[BOARD_LED_COUNT] = {
    "radio link 1", "radio link 2", "radio status", "strike 1", "strike 2", "strike 3",
    "timer status", "keypad status", "wires status", "probe status",
    "simon 1", "simon 2", "simon 3", "simon 4", "sensor status",
};

static int cmd_led(int argc, char **argv)
{
    if (argc < 2 || strcmp(argv[1], "test") != 0) {
        printf("usage: led test\n");
        return 1;
    }
    if (!board_leds_ready()) {
        printf("LED driver not running\n");
        return 1;
    }
    for (int i = 0; i < BOARD_LED_COUNT; i++) {
        printf("  %2d %s\n", i, s_led_names[i]);
        static const uint8_t rgb[3][3] = { { 255, 0, 0 }, { 0, 255, 0 }, { 0, 0, 255 } };
        for (int c = 0; c < 3; c++) {
            board_leds_fill(0, 0, 0);
            board_leds_set((board_led_t)i, rgb[c][0], rgb[c][1], rgb[c][2]);
            board_leds_show();
            vTaskDelay(pdMS_TO_TICKS(120));
        }
    }
    board_leds_fill(255, 255, 255);
    board_leds_show();
    vTaskDelay(pdMS_TO_TICKS(500));
    board_leds_clear();
    printf("done\n");
    return 0;
}

/* ---- buzz / servo ------------------------------------------------------------ */

static int cmd_buzz(int argc, char **argv)
{
    long hz = 2000, ms = 200;
    if ((argc > 1 && !parse_int(argv[1], 50, 10000, &hz)) ||
        (argc > 2 && !parse_int(argv[2], 1, 10000, &ms))) {
        printf("usage: buzz [hz 50-10000] [ms 1-10000]\n");
        return 1;
    }
    esp_err_t err = board_buzzer_tone((uint32_t)hz, (uint32_t)ms);
    if (err != ESP_OK) {
        printf("buzzer: %s\n", esp_err_to_name(err));
        return 1;
    }
    printf("%ld Hz for %ld ms\n", hz, ms);
    return 0;
}

static int cmd_servo(int argc, char **argv)
{
    long deg;
    esp_err_t err;
    if (argc < 2) {
        printf("usage: servo open|close|<0-180>\n");
        return 1;
    }
    if (strcmp(argv[1], "open") == 0) {
        err = board_servo_open();
    } else if (strcmp(argv[1], "close") == 0) {
        err = board_servo_close();
    } else if (parse_int(argv[1], 0, 180, &deg)) {
        err = board_servo_angle((int)deg);
    } else {
        printf("usage: servo open|close|<0-180>\n");
        return 1;
    }
    if (err != ESP_OK) {
        printf("servo: %s\n", esp_err_to_name(err));
        return 1;
    }
    printf("ok\n");
    return 0;
}

/* ---- keys / wires / touch / ir / tilt ---------------------------------------- */

static int cmd_keys(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    if (!board_mcp_present(BOARD_MCP_U2)) {
        printf("U2 (0x20) missing: no keypad\n");
        return 1;
    }
    printf("press keys for %d s...\n", WATCH_MS / 1000);
    int64_t end = now_ms() + WATCH_MS;
    while (now_ms() < end) {
        char k = board_keypad_poll();
        if (k) {
            printf("  key %c\n", k);
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    printf("done\n");
    return 0;
}

static int cmd_wires(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    uint8_t conn[BOARD_WIRE_POSTS];
    esp_err_t err = board_wires_scan(conn);
    if (err != ESP_OK) {
        printf("wires: %s (U3 0x21 %s)\n", esp_err_to_name(err),
               board_mcp_present(BOARD_MCP_U3) ? "present" : "missing");
        return 1;
    }
    for (int a = 0; a < BOARD_WIRE_POSTS; a++) {
        printf("  WA%d ->", a + 1);
        if (!conn[a]) {
            printf(" -");
        }
        for (int b = 0; b < BOARD_WIRE_POSTS; b++) {
            if (conn[a] & (1u << b)) {
                printf(" WB%d", b + 1);
            }
        }
        printf("\n");
    }
    return 0;
}

static int cmd_touch(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    if (!board_touch_ready()) {
        printf("touch driver not running\n");
        return 1;
    }
    for (int i = 0; i < BOARD_TOUCH_COUNT; i++) {
        uint32_t v = 0;
        board_touch_read((board_touch_pad_t)i, &v);
        printf("  pad %d (T%d): value %5lu  baseline %5lu  %s\n", i + 1,
               board_touch_channel((board_touch_pad_t)i), (unsigned long)v,
               (unsigned long)board_touch_baseline((board_touch_pad_t)i),
               board_touch_touched((board_touch_pad_t)i) ? "TOUCHED" : "-");
    }
    return 0;
}

static int cmd_ir(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    if (!board_ir_ready()) {
        printf("IR driver not running\n");
        return 1;
    }
    board_ir_flush();
    printf("point an NEC remote at the receiver for %d s...\n", WATCH_MS / 1000);
    int64_t end = now_ms() + WATCH_MS;
    while (now_ms() < end) {
        board_ir_code_t c;
        if (board_ir_get(&c, 100)) {
            if (c.repeat) {
                printf("  repeat (addr 0x%04X cmd 0x%02X)\n", c.address, c.command);
            } else {
                printf("  addr 0x%04X cmd 0x%02X raw 0x%08lX\n", c.address, c.command, (unsigned long)c.raw);
            }
        }
    }
    printf("done\n");
    return 0;
}

static int cmd_tilt(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    float g[3], tilt, pitch, roll;
    esp_err_t err = board_lis3dh_accel(g);
    if (err == ESP_OK) {
        err = board_lis3dh_tilt(&tilt, &pitch, &roll);
    }
    if (err != ESP_OK) {
        printf("LIS3DH: %s\n", esp_err_to_name(err));
        return 1;
    }
    printf("  accel x %+.2f y %+.2f z %+.2f g\n", (double)g[0], (double)g[1], (double)g[2]);
    printf("  tilt %.1f deg from reference, pitch %+.1f, roll %+.1f\n", (double)tilt, (double)pitch, (double)roll);
    return 0;
}

/* ---- pack -------------------------------------------------------------------- */

static void pack_print(const d32_pack_t *p, const char *name)
{
    printf("  pack     %s (id \"%s\", \"%s\" %s, format %d)\n", name, p->id, p->title, p->version, p->format);
    printf("  round    %d min, max %d strikes, strike rate x%.2f%s\n", p->minutes, p->max_strikes,
           (double)p->strike_rate, p->training ? ", TRAINING" : "");
    for (int i = 0; i < D32_PACK_SLOTS; i++) {
        printf("  %s %-8s %-3s %s\n", d32_pack_slot_id(i), d32_pack_slot_name(i),
               p->slots[i].enabled ? "on" : "off", p->slots[i].variant);
    }
}

/* The card is unmounted during play (main.c). Mount it for one pack command
 * and unmount it again; refused while a round runs, so the shared SPI bus
 * stays quiet for the probe plate. */
static bool sd_open(bool *mounted_here)
{
    *mounted_here = false;
    if (board_sd_mounted()) {
        return true;
    }
    if (game_round_active()) {
        printf("round running: the microSD card stays unmounted during play\n");
        return false;
    }
    bool present = false;
    esp_err_t err = board_sd_card_detected(&present);
    if (err == ESP_OK && !present) {
        printf("no microSD card inserted\n");
        return false;
    }
    if (board_sd_mount() != ESP_OK) {
        printf("microSD mount failed\n");
        return false;
    }
    *mounted_here = true;
    return true;
}

static void sd_close(bool mounted_here)
{
    if (mounted_here) {
        board_sd_unmount();
    }
}

static int cmd_pack(int argc, char **argv)
{
    bool here = false;
    if (argc >= 2 && strcmp(argv[1], "list") == 0) {
        printf("  %s (compiled in)\n", D32_PACK_BUILTIN_NAME);
        if (!sd_open(&here)) {
            return 0;
        }
        static char names[32][D32_PACK_NAME_MAX];
        int n = d32_pack_list(D32_PACK_DIR, names, 32);
        sd_close(here);
        if (n < 0) {
            printf("  (%s not found)\n", D32_PACK_DIR);
            return 0;
        }
        for (int i = 0; i < n; i++) {
            printf("  %s\n", names[i]);
        }
        return 0;
    }
    if (argc >= 3 && strcmp(argv[1], "load") == 0) {
        static d32_pack_t p;
        bool builtin = strcmp(argv[2], D32_PACK_BUILTIN_NAME) == 0;
        if (!builtin && !sd_open(&here)) {
            return 1;
        }
        int rc = d32_pack_load(argv[2], &p);
        sd_close(here);
        if (rc != 0) {
            printf("load failed (see log); current pack unchanged\n");
            return 1;
        }
        d32_pack_select(&p, argv[2]);
        pack_print(&p, argv[2]);
        printf("  (used from the next round start)\n");
        return 0;
    }
    if (argc >= 2 && strcmp(argv[1], "show") == 0) {
        pack_print(d32_pack_current(), d32_pack_current_name());
        return 0;
    }
    printf("usage: pack list | pack load <name> | pack show\n");
    return 1;
}

/* ---- round commands (work without any plate hardware) ------------------------- */

static int cmd_status(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    game_print_status();
    return 0;
}

static int cmd_round(int argc, char **argv)
{
    if (argc >= 2 && strcmp(argv[1], "start") == 0) {
        long minutes = 0;
        if (argc > 2 && !parse_int(argv[2], 1, D32_MAX_MINUTES, &minutes)) {
            printf("usage: round start [minutes 1-%d]\n", D32_MAX_MINUTES);
            return 1;
        }
        d32_arm_result_t r = game_round_start((int)minutes);
        if (r == D32_ARM_BUSY) {
            printf("a round is running: round reset first\n");
            return 1;
        }
        if (r == D32_ARM_NO_MODULES) {
            printf("no module enabled in the pack\n");
            return 1;
        }
        printf("round armed\n");
        return 0;
    }
    if (argc >= 2 && strcmp(argv[1], "reset") == 0) {
        game_round_reset();
        printf("round reset (idle)\n");
        return 0;
    }
    if (argc >= 2 && strcmp(argv[1], "codes") == 0) {
        game_print_codes();
        return 0;
    }
    printf("usage: round start [minutes] | round reset | round codes\n");
    return 1;
}

static int cmd_code(int argc, char **argv)
{
    if (argc < 2) {
        printf("usage: code <6 hex chars>\n");
        return 1;
    }
    char text[32] = "";
    size_t n = 0;
    for (int i = 1; i < argc && n < sizeof(text) - 1; i++) { /* "3E 9D 01" works too */
        int w = snprintf(text + n, sizeof(text) - n, "%s", argv[i]);
        if (w < 0) {
            break;
        }
        n += (size_t)w;
    }
    int slot = -1;
    switch (game_submit_code(text, &slot)) {
    case D32_CODE_DISARMED:
        printf("%s %s disarmed\n", d32_slot_id(slot), d32_slot_name(slot));
        return 0;
    case D32_CODE_ALREADY:
        printf("%s already disarmed (no strike)\n", d32_slot_id(slot));
        return 0;
    case D32_CODE_REJECTED:
        printf("code rejected\n");
        return 1;
    case D32_CODE_INVALID:
        printf("invalid: 6 hex chars expected (no strike)\n");
        return 1;
    case D32_CODE_NOT_ARMED:
    default:
        printf("no round running\n");
        return 1;
    }
}

static int cmd_wire(int argc, char **argv)
{
    long w;
    if (argc < 2 || !parse_int(argv[1], 0, D32_WIRES - 1, &w)) {
        printf("usage: wire <0-5>  (0 RED, 1 BLUE, 2 YELLOW, 3 GREEN, 4 WHITE, 5 BLACK)\n");
        return 1;
    }
    switch (game_wire((int)w)) {
    case D32_WIRE_EARLY:
        printf("%s pulled before every module was disarmed\n", d32_wire_colour((int)w));
        return 1;
    case D32_WIRE_WON:
        printf("%s pulled: round won\n", d32_wire_colour((int)w));
        return 0;
    case D32_WIRE_LOST:
        printf("%s pulled: round lost\n", d32_wire_colour((int)w));
        return 0;
    case D32_WIRE_INVALID:
    case D32_WIRE_NOT_ARMED:
    default:
        printf("no round running\n");
        return 1;
    }
}

static int cmd_strike(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    if (!game_strike()) {
        printf("no strike applied (no round running, or training)\n");
        return 1;
    }
    printf("strike added\n");
    return 0;
}

/* ---- registration ------------------------------------------------------------ */

void console_cmds_register(void)
{
    const esp_console_cmd_t cmds[] = {
        { .command = "hw", .help = "hw scan: I2C scan + device presence table", .func = cmd_hw },
        { .command = "led", .help = "led test: walk R/G/B through the WS2812 chain", .func = cmd_led },
        { .command = "buzz", .help = "buzz [hz] [ms]: beep (default 2000 Hz, 200 ms)", .func = cmd_buzz },
        { .command = "servo", .help = "servo open|close|<deg>: move the prize hatch servo", .func = cmd_servo },
        { .command = "keys", .help = "keys: print keypad presses for 10 s", .func = cmd_keys },
        { .command = "wires", .help = "wires: print the wire patch matrix", .func = cmd_wires },
        { .command = "touch", .help = "touch: print touch pad readings", .func = cmd_touch },
        { .command = "ir", .help = "ir: print decoded NEC codes for 10 s", .func = cmd_ir },
        { .command = "tilt", .help = "tilt: print accelerometer and tilt angle", .func = cmd_tilt },
        { .command = "pack", .help = "pack list | pack load <name> | pack show", .func = cmd_pack },
        { .command = "status", .help = "status: round phase, time, strikes, modules, fragments", .func = cmd_status },
        { .command = "round", .help = "round start [minutes] | round reset | round codes (game master: shows the codes)", .func = cmd_round },
        { .command = "code", .help = "code <hex6>: submit a module code (as on the keypad)", .func = cmd_code },
        { .command = "wire", .help = "wire <0-5>: pull a wire (0 RED 1 BLUE 2 YELLOW 3 GREEN 4 WHITE 5 BLACK)", .func = cmd_wire },
        { .command = "strike", .help = "strike: add a strike (game master)", .func = cmd_strike },
    };
    for (size_t i = 0; i < sizeof(cmds) / sizeof(cmds[0]); i++) {
        ESP_ERROR_CHECK(esp_console_cmd_register(&cmds[i]));
    }
}
