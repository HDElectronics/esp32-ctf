/* Catalogue matches SPEC "Challenge catalogue": IDs, order, names, levels, kit labels. */
#include <string.h>

#include "test_util.h"

typedef struct {
    const char *id, *track, *name;
    ctf_level_t level;
    const char *kit;
} want_t;

#define E CTF_EASY
#define M CTF_MEDIUM
#define H CTF_HARD

static const want_t WANT[] = {
    {"BLE-01", "BLE", "Read the flag", E, NULL},
    {"BLE-02", "BLE", "Hex and friends", E, NULL},
    {"BLE-03", "BLE", "Notify me", E, NULL},
    {"BLE-04", "BLE", "Indicate and ack", M, NULL},
    {"BLE-05", "BLE", "Write to unlock", E, NULL},
    {"BLE-06", "BLE", "Descriptor hunt", M, NULL},
    {"BLE-07", "BLE", "Advertising payload", M, NULL},
    {"BLE-08", "BLE", "Big MTU", M, NULL},
    {"BLE-09", "BLE", "Passkey pairing", M, NULL},
    {"BLE-10", "BLE", "Rate-limited PIN", H, NULL},
    {"BLE-11", "BLE", "Write-without-response sequence", H, NULL},
    {"BTC-01", "BTC", "SPP console", E, NULL},
    {"BTC-02", "BTC", "Hidden menu", M, NULL},
    {"BTC-03", "BTC", "Device class clue", M, NULL},
    {"WEB-01", "WEB", "Hidden SSID", E, NULL},
    {"WEB-02", "WEB", "View source", E, NULL},
    {"WEB-03", "WEB", "Cookie admin", E, NULL},
    {"WEB-04", "WEB", "Header check", E, NULL},
    {"WEB-05", "WEB", "Weak JWT", M, NULL},
    {"WEB-06", "WEB", "Ping tool", M, NULL},
    {"WEB-07", "WEB", "WebSocket chatter", M, NULL},
    {"WEB-08", "WEB", "mDNS discovery", M, NULL},
    {"WEB-09", "WEB", "UDP knock", H, NULL},
    {"SER-01", "SER", "Boot log", E, NULL},
    {"SER-02", "SER", "Wrong baud", M, "USB-UART adapter"},
    {"SER-03", "SER", "Debug login", H, NULL},
    {"SER-04", "SER", "Escape sequence", M, NULL},
    {"HW-01", "HW", "Jumper it", E, "jumper wire"},
    {"HW-02", "HW", "Blinky Morse", E, NULL},
    {"HW-03", "HW", "PWM frequency", M, "logic analyzer"},
    {"HW-04", "HW", "I2C chatter", M, "logic analyzer"},
    {"HW-05", "HW", "SPI dump", M, "logic analyzer"},
    {"HW-06", "HW", "Touch pad code", M, NULL},
    {"RE-01", "RE", "Strings in flash", E, NULL},
    {"RE-02", "RE", "NVS secrets", M, NULL},
    {"RE-03", "RE", "Crackme", H, NULL},
    {"RE-04", "RE", "XOR'd asset", H, NULL},
    {"CRY-01", "CRY", "Classic cipher", E, NULL},
    {"CRY-02", "CRY", "ECB penguin", H, NULL},
    {"CRY-03", "CRY", "Reused nonce", M, NULL},
};

#define WANT_LEN (sizeof(WANT) / sizeof(WANT[0]))

static bool str_eq_or_null(const char *a, const char *b)
{
    if (!a || !b) {
        return a == b;
    }
    return strcmp(a, b) == 0;
}

static void test_catalog_matches_spec(void)
{
    CHECK(WANT_LEN == 40);
    CHECK(ctf_count() == WANT_LEN);
    for (size_t i = 0; i < WANT_LEN && i < ctf_count(); i++) {
        const ctf_challenge_t *c = ctf_get(i);
        CHECK(c != NULL);
        if (!c) {
            continue;
        }
        CHECK(strcmp(c->id, WANT[i].id) == 0);
        CHECK(strcmp(c->track, WANT[i].track) == 0);
        CHECK(strcmp(c->name, WANT[i].name) == 0);
        CHECK(c->level == WANT[i].level);
        CHECK(str_eq_or_null(c->kit, WANT[i].kit));
        CHECK(c->hint != NULL && strlen(c->hint) > 20);
        /* ID prefix is the track name. */
        size_t tl = strlen(c->track);
        CHECK(strncmp(c->id, c->track, tl) == 0 && c->id[tl] == '-');
        CHECK(ctf_find(c->id) == c);
    }
    CHECK(ctf_get(ctf_count()) == NULL);
    CHECK(ctf_find("BLE-12") == NULL);
    CHECK(ctf_find("ble-01") == NULL);
    CHECK(ctf_find(NULL) == NULL);
}

static void test_catalog_unique_ids(void)
{
    bool unique = true;
    for (size_t i = 0; i < ctf_count(); i++) {
        for (size_t j = i + 1; j < ctf_count(); j++) {
            if (strcmp(ctf_get(i)->id, ctf_get(j)->id) == 0) {
                unique = false;
            }
        }
    }
    CHECK(unique);
}

static void test_points_and_max_score(void)
{
    CHECK(ctf_points("BLE-01") == 100);
    CHECK(ctf_points("BLE-04") == 200);
    CHECK(ctf_points("BLE-10") == 300);
    CHECK(ctf_points("NOPE-1") == 0);
    CHECK(ctf_points(NULL) == 0);

    int all = 0, no_kit = 0;
    for (size_t i = 0; i < WANT_LEN; i++) {
        int p = WANT[i].level == E ? 100 : WANT[i].level == M ? 200 : 300;
        all += p;
        if (!WANT[i].kit) {
            no_kit += p;
        }
    }
    CHECK(ctf_max_score(true) == all);
    CHECK(ctf_max_score(false) == no_kit);
    /* SER-02 (200) + HW-01 (100) + HW-03/04/05 (3 x 200). */
    CHECK(all - no_kit == 900);
}

void run_catalog_tests(void)
{
    RUN(test_catalog_matches_spec);
    RUN(test_catalog_unique_ids);
    RUN(test_points_and_max_score);
}
