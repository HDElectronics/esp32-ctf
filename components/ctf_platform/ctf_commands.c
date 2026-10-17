/* Core console commands (SPEC "Console commands"): status, list, submit,
 * answer, hint, mode, reset. `help` is esp_console's built-in. */
#include "ctf_platform.h"
#include "ctf_platform_priv.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include "ctf_core.h"
#include "esp_console.h"
#include "esp_err.h"
#include "esp_system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define MAX_TRACKS 8

/* Upper-cases src into dst (bounded). */
static void upcase(char *dst, size_t n, const char *src)
{
    size_t i = 0;
    for (; src[i] && i + 1 < n; i++) {
        dst[i] = (char)toupper((unsigned char)src[i]);
    }
    dst[i] = '\0';
}

static const ctf_challenge_t *find_id(const char *arg)
{
    char id[16];
    upcase(id, sizeof(id), arg);
    return ctf_find(id);
}

/* Track names in catalogue order. */
static size_t tracks(const char *out[MAX_TRACKS])
{
    size_t n = 0;
    for (size_t i = 0; i < ctf_count(); i++) {
        const char *t = ctf_get(i)->track;
        size_t j = 0;
        while (j < n && strcmp(out[j], t) != 0) {
            j++;
        }
        if (j == n && n < MAX_TRACKS) {
            out[n++] = t;
        }
    }
    return n;
}

static void print_kit(const ctf_challenge_t *c)
{
    if (c->kit) {
        printf("  [needs %s \xE2\x80\x94 skip if you don't have it]", c->kit);
    }
}

static int cmd_status(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    printf("Score: %d / %d (max without kit: %d)\n",
           ctf_score(), ctf_max_score(true), ctf_max_score(false));
    printf("Mode: %s\n", ctf_platform_mode_name(ctf_platform_mode()));
    const char *tr[MAX_TRACKS];
    size_t nt = tracks(tr);
    for (size_t k = 0; k < nt; k++) {
        int total = 0, solved = 0;
        for (size_t i = 0; i < ctf_count(); i++) {
            const ctf_challenge_t *c = ctf_get(i);
            if (strcmp(c->track, tr[k]) == 0) {
                total++;
                solved += ctf_is_solved(c->id) ? 1 : 0;
            }
        }
        printf("  %-4s %2d/%-2d", tr[k], solved, total);
        for (size_t i = 0; i < ctf_count(); i++) {
            const ctf_challenge_t *c = ctf_get(i);
            if (strcmp(c->track, tr[k]) == 0 && ctf_is_solved(c->id)) {
                printf(" %s%s", c->id, ctf_hint_used(c->id) ? "(h)" : "");
            }
        }
        printf("\n");
    }
    printf("Hints used:");
    int nh = 0;
    for (size_t i = 0; i < ctf_count(); i++) {
        const ctf_challenge_t *c = ctf_get(i);
        if (ctf_hint_used(c->id)) {
            printf(" %s", c->id);
            nh++;
        }
    }
    printf("%s\n", nh ? "" : " none");
    return 0;
}

static int cmd_list(int argc, char **argv)
{
    char filt[8] = "";
    if (argc >= 2) {
        upcase(filt, sizeof(filt), argv[1]);
    }
    bool any = false;
    for (size_t i = 0; i < ctf_count(); i++) {
        const ctf_challenge_t *c = ctf_get(i);
        if (filt[0] && strcmp(c->track, filt) != 0) {
            continue;
        }
        any = true;
        bool s = ctf_is_solved(c->id), h = ctf_hint_used(c->id);
        printf("%-7s %-26s %3d  %-6s %-4s", c->id, c->name, ctf_points(c->id),
               s ? "solved" : "-", h ? "hint" : "");
        print_kit(c);
        printf("\n");
    }
    if (!any) {
        const char *tr[MAX_TRACKS];
        size_t nt = tracks(tr);
        printf("Unknown track '%s'. Tracks:", argv[1]);
        for (size_t k = 0; k < nt; k++) {
            printf(" %s", tr[k]);
        }
        printf("\n");
        return 1;
    }
    return 0;
}

static int cmd_submit(int argc, char **argv)
{
    if (argc < 2) {
        printf("Usage: submit <flag>\n");
        return 1;
    }
    const ctf_challenge_t *c = NULL;
    switch (ctf_submit(argv[1], &c)) {
    case CTF_SUBMIT_NEW:
        printf("Correct! %s %s +%d\n", c->id, c->name,
               ctf_points(c->id) - (ctf_hint_used(c->id) ? ctf_points(c->id) / 4 : 0));
        return 0;
    case CTF_SUBMIT_ALREADY:
        printf("Already solved: %s %s\n", c->id, c->name);
        return 0;
    default:
        printf("Wrong flag.\n");
        return 1;
    }
}

static int cmd_answer(int argc, char **argv)
{
    if (argc < 3) {
        printf("Usage: answer <id> <value>\n");
        return 1;
    }
    const ctf_challenge_t *c = find_id(argv[1]);
    if (!c) {
        printf("Unknown challenge '%s'.\n", argv[1]);
        return 1;
    }
    char value[128];
    size_t n = 0;
    value[0] = '\0';
    for (int i = 2; i < argc; i++) {
        int w = snprintf(value + n, sizeof(value) - n, "%s%s", i > 2 ? " " : "", argv[i]);
        if (w < 0 || (size_t)w >= sizeof(value) - n) {
            break;
        }
        n += (size_t)w;
    }
    char flag[18];
    if (ctf_answer(c->id, value, flag)) {
        printf("Correct answer for %s. Flag: %s\nSubmit it with: submit %s\n", c->id, flag, flag);
        return 0;
    }
    printf("Wrong answer for %s.\n", c->id);
    return 1;
}

static int cmd_hint(int argc, char **argv)
{
    if (argc < 2) {
        printf("Usage: hint <id> [yes]\n");
        return 1;
    }
    const ctf_challenge_t *c = find_id(argv[1]);
    if (!c) {
        printf("Unknown challenge '%s'.\n", argv[1]);
        return 1;
    }
    int cost = ctf_points(c->id) / 4;
    if (ctf_hint_used(c->id)) {
        printf("Hint for %s (already paid): %s\n", c->id, ctf_hint(c->id));
        return 0;
    }
    bool yes = argc >= 3 && strcasecmp(argv[2], "yes") == 0;
    if (!yes) {
        printf("The hint for %s costs %d points (25%% of %d).\n", c->id, cost, ctf_points(c->id));
        if (ctf_is_solved(c->id)) {
            printf("You already solved %s: the hint still costs %d points.\n", c->id, cost);
        }
        printf("Type `hint %s yes` to reveal it.\n", c->id);
        return 0;
    }
    printf("Hint for %s (-%d points): %s\n", c->id, cost, ctf_hint(c->id));
    return 0;
}

static int cmd_mode(int argc, char **argv)
{
    if (argc < 2) {
        printf("Mode: %s. Usage: mode radio|net (saves and reboots)\n",
               ctf_platform_mode_name(ctf_platform_mode()));
        return 0;
    }
    if (strcasecmp(argv[1], "radio") == 0) {
        ctf_platform_set_mode_and_reboot(CTF_MODE_RADIO);
    } else if (strcasecmp(argv[1], "net") == 0) {
        ctf_platform_set_mode_and_reboot(CTF_MODE_NET);
    }
    printf("Usage: mode radio|net\n");
    return 1;
}

static int cmd_reset(int argc, char **argv)
{
    if (argc < 2 || strcasecmp(argv[1], "yes") != 0) {
        printf("WARNING: this wipes all progress (solved challenges and used hints).\n"
               "Type `reset yes` to confirm.\n");
        return 0;
    }
    ctf_reset();
    printf("Progress cleared. Rebooting...\n");
    fflush(stdout);
    vTaskDelay(pdMS_TO_TICKS(100));
    esp_restart();
    return 0;
}

void ctf_commands_register(void)
{
    static const esp_console_cmd_t cmds[] = {
        { .command = "status", .help = "Score, max score (with/without kit), solved per track, mode",
          .func = cmd_status },
        { .command = "list", .help = "List challenges (optionally one track: BLE BTC WEB SER HW RE CRY)",
          .hint = "[track]", .func = cmd_list },
        { .command = "submit", .help = "Submit a flag: ESP{...} or the bare 12-hex body",
          .hint = "<flag>", .func = cmd_submit },
        { .command = "answer", .help = "Answer a value challenge; prints its flag when correct",
          .hint = "<id> <value>", .func = cmd_answer },
        { .command = "hint", .help = "Show a hint's cost; `hint <id> yes` reveals it (-25% of its points)",
          .hint = "<id> [yes]", .func = cmd_hint },
        { .command = "mode", .help = "Show or switch mode (radio: BLE/BT Classic, net: Wi-Fi/web); reboots",
          .hint = "[radio|net]", .func = cmd_mode },
        { .command = "reset", .help = "Wipe all progress; requires `reset yes`; reboots",
          .hint = "[yes]", .func = cmd_reset },
    };
    for (size_t i = 0; i < sizeof(cmds) / sizeof(cmds[0]); i++) {
        ESP_ERROR_CHECK(esp_console_cmd_register(&cmds[i]));
    }
}
