/* Core console commands (SPEC "Console commands", "v0.2.0" console changes):
 * status, list, submit, answer, hint, mode, reset. `help` is esp_console's built-in. */
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
    int earned = ctf_earned(), spent = ctf_spent();
    printf("Points: %d (started with %d, +%d solved, -%d hints)\n",
           CTF_START_POINTS + earned - spent, CTF_START_POINTS, earned, spent);
    printf("Challenges: %d points to earn (%d without optional kit)\n",
           ctf_max_score(true), ctf_max_score(false));
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
                printf(" %s", c->id);
            }
        }
        printf("\n");
    }
    printf("Hints bought:");
    int nh = 0;
    for (size_t i = 0; i < ctf_count(); i++) {
        const ctf_challenge_t *c = ctf_get(i);
        int t = ctf_hint_tier(c->id);
        if (t > 1) {
            printf("%s %s (%d)", nh ? "," : "", c->id, t);
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
        bool s = ctf_is_solved(c->id);
        int t = ctf_hint_tier(c->id);
        printf("%-7s %-26s %3d  %-6s %-7s", c->id, c->name, ctf_value(c->id),
               s ? "solved" : "-", t > 1 ? (t == 2 ? "hint 2" : "hint 3") : "");
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
        printf("Correct! %s %s +%d (points: %d)\n", c->id, c->name, ctf_value(c->id), ctf_points());
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

static const char *const TIER_NAME[CTF_HINT_TIERS] = {"Nudge", "Hint", "Walkthrough"};

static void print_tier_text(const ctf_challenge_t *c, int tier, const char *text)
{
    printf("%s tier %d (%s):\n%s\n", c->id, tier, TIER_NAME[tier - 1], text);
}

/* `hint <id>`: the three tiers with state and price. */
static void list_tiers(const ctf_challenge_t *c)
{
    int have = ctf_hint_tier(c->id);
    printf("%s %s (%d points). Hint tiers:\n", c->id, c->name, ctf_value(c->id));
    for (int t = 1; t <= CTF_HINT_TIERS; t++) {
        char price[16], state[40];
        int p = ctf_hint_price(c->id, t);
        if (p == 0) {
            snprintf(price, sizeof(price), "free");
        } else {
            snprintf(price, sizeof(price), "%d points", p);
        }
        if (t == 1) {
            snprintf(state, sizeof(state), "[show: hint %s 1]", c->id);
        } else if (t <= have) {
            snprintf(state, sizeof(state), "[owned: hint %s %d]", c->id, t);
        } else if (t == have + 1) {
            snprintf(state, sizeof(state), "[buy: hint %s %d]", c->id, t);
        } else {
            snprintf(state, sizeof(state), "[locked: buy tier %d first]", t - 1);
        }
        printf("  %d %-12s %-11s %s\n", t, TIER_NAME[t - 1], price, state);
    }
    printf("You have %d points.\n", ctf_points());
}

static int cmd_hint(int argc, char **argv)
{
    if (argc < 2) {
        printf("Usage: hint <id> [1|2|3] [yes]\n");
        return 1;
    }
    const ctf_challenge_t *c = find_id(argv[1]);
    if (!c) {
        printf("Unknown challenge '%s'.\n", argv[1]);
        return 1;
    }
    if (argc < 3) {
        list_tiers(c);
        return 0;
    }
    const char *a = argv[2];
    if (!(a[0] >= '1' && a[0] <= '0' + CTF_HINT_TIERS && a[1] == '\0')) {
        printf("Usage: hint %s [1|2|3] [yes]\n", c->id);
        return 1;
    }
    int tier = a[0] - '0';
    int have = ctf_hint_tier(c->id);
    int price = ctf_hint_price(c->id, tier);
    bool yes = argc >= 4 && strcasecmp(argv[3], "yes") == 0;
    const char *text = NULL;

    if (tier <= have || yes) {
        int before = ctf_points();
        switch (ctf_hint_buy(c->id, tier, &text)) {
        case CTF_HINT_OK:
            if (tier > have) {
                printf("Bought %s tier %d for %d points (%d left).\n", c->id, tier, price,
                       ctf_points());
            }
            print_tier_text(c, tier, text);
            return 0;
        case CTF_HINT_LOCKED:
            printf("Tier %d is locked: buy tier %d first (`hint %s %d`).\n", tier, tier - 1,
                   c->id, tier - 1);
            return 1;
        case CTF_HINT_POINTS:
            printf("Not enough points: tier %d costs %d, you have %d (need %d more).\n", tier,
                   price, before, price - before);
            return 1;
        default:
            printf("Usage: hint %s [1|2|3] [yes]\n", c->id);
            return 1;
        }
    }
    if (tier > have + 1) {
        printf("Tier %d is locked: buy tier %d first (`hint %s %d`).\n", tier, tier - 1, c->id,
               tier - 1);
        return 0;
    }
    int pts = ctf_points();
    printf("%s tier %d (%s) costs %d points. You have %d.\n", c->id, tier, TIER_NAME[tier - 1],
           price, pts);
    if (pts < price) {
        printf("Not enough points: you need %d more. Solve a challenge first.\n", price - pts);
        return 0;
    }
    printf("Type `hint %s %d yes` to buy it.\n", c->id, tier);
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
        printf("WARNING: this wipes all progress (solved challenges, bought hints, points).\n"
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
        { .command = "status", .help = "Points, max (with/without kit), mode, solved per track, hints bought",
          .func = cmd_status },
        { .command = "list", .help = "List challenges (optionally one track: BLE BTC WEB SER HW RE CRY)",
          .hint = "[track]", .func = cmd_list },
        { .command = "submit", .help = "Submit a flag: ESP{...} or the bare 12-hex body",
          .hint = "<flag>", .func = cmd_submit },
        { .command = "answer", .help = "Answer a value challenge; prints its flag when correct",
          .hint = "<id> <value>", .func = cmd_answer },
        { .command = "hint", .help = "List a challenge's 3 hint tiers; `hint <id> <n>` shows tier n, "
                                     "`hint <id> <n> yes` buys it",
          .hint = "<id> [1|2|3] [yes]", .func = cmd_hint },
        { .command = "mode", .help = "Show or switch mode (radio: BLE/BT Classic, net: Wi-Fi/web); reboots",
          .hint = "[radio|net]", .func = cmd_mode },
        { .command = "reset", .help = "Wipe all progress; requires `reset yes`; reboots",
          .hint = "[yes]", .func = cmd_reset },
    };
    for (size_t i = 0; i < sizeof(cmds) / sizeof(cmds[0]); i++) {
        ESP_ERROR_CHECK(esp_console_cmd_register(&cmds[i]));
    }
}
