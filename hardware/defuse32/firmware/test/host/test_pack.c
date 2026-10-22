/* d32_pack parse core (d32_pack_parse.c + cJSON). */
#include <string.h>

#include "d32_pack.h"
#include "test_util.h"

typedef struct {
    int count;
    char last[128];
    char all[1024];
} warns_t;

static void on_warn(void *ctx, const char *msg)
{
    warns_t *w = ctx;
    w->count++;
    snprintf(w->last, sizeof(w->last), "%s", msg);
    size_t n = strlen(w->all);
    snprintf(w->all + n, sizeof(w->all) - n, "%s\n", msg);
}

static int parse(const char *json, d32_pack_t *p, warns_t *w)
{
    memset(w, 0, sizeof(*w));
    return d32_pack_parse(json, json ? strlen(json) : 0, p, on_warn, w);
}

static const char *const FULL =
    "{ \"format\": 1, \"id\": \"base\", \"title\": \"Base pack\", \"version\": \"0.1.0\","
    "  \"round\": { \"minutes\": 30, \"max_strikes\": 5, \"strike_rate\": 1.5, \"training\": true },"
    "  \"modules\": {"
    "    \"M1\": { \"enabled\": false, \"variant\": \"ble-read\" },"
    "    \"M2\": { \"enabled\": true, \"variant\": \"buzzer-morse\" },"
    "    \"M3\": { \"enabled\": true, \"variant\": \"menu\" },"
    "    \"M4\": { \"enabled\": true, \"variant\": \"patch-a\" },"
    "    \"M5\": { \"enabled\": true, \"variant\": \"uart-9600\" },"
    "    \"M6\": { \"enabled\": false, \"variant\": \"touch-4\" } } }";

static void test_pack_valid(void)
{
    d32_pack_t p;
    warns_t w;
    CHECK(parse(FULL, &p, &w) == 0);
    CHECK(w.count == 0);
    CHECK(p.format == 1);
    CHECK(strcmp(p.id, "base") == 0);
    CHECK(strcmp(p.title, "Base pack") == 0);
    CHECK(strcmp(p.version, "0.1.0") == 0);
    CHECK(p.minutes == 30);
    CHECK(p.max_strikes == 5);
    CHECK(p.strike_rate > 1.499f && p.strike_rate < 1.501f);
    CHECK(p.training);
    CHECK(!p.slots[0].enabled && strcmp(p.slots[0].variant, "ble-read") == 0);
    CHECK(p.slots[1].enabled && strcmp(p.slots[1].variant, "buzzer-morse") == 0);
    CHECK(strcmp(p.slots[4].variant, "uart-9600") == 0);
    CHECK(!p.slots[5].enabled);
}

static void test_pack_defaults(void)
{
    d32_pack_t p;
    d32_pack_defaults(&p);
    CHECK(p.format == D32_PACK_FORMAT);
    CHECK(strcmp(p.id, "builtin") == 0);
    CHECK(p.minutes == 45 && p.max_strikes == 3 && !p.training);
    CHECK(p.strike_rate > 1.249f && p.strike_rate < 1.251f);
    static const char *const want[6] = { "ble-read", "buzzer-morse", "menu", "patch-a", "uart-115200", "touch-4" };
    for (int i = 0; i < D32_PACK_SLOTS; i++) {
        CHECK(p.slots[i].enabled);
        CHECK(strcmp(p.slots[i].variant, want[i]) == 0);
    }

    /* Empty object: every top-level field missing, defaults kept, neutral metadata. */
    warns_t w;
    CHECK(parse("{}", &p, &w) == 6);
    CHECK(w.count == 6);
    CHECK(strcmp(p.id, "unnamed") == 0);
    CHECK(strcmp(p.title, "Untitled pack") == 0);
    CHECK(p.minutes == 45 && p.max_strikes == 3);
    CHECK(strcmp(p.slots[3].variant, "patch-a") == 0 && p.slots[3].enabled);

    /* Missing fields inside round / a module. */
    CHECK(parse("{\"format\":1,\"id\":\"a\",\"title\":\"t\",\"version\":\"1\","
                "\"round\":{\"minutes\":10},"
                "\"modules\":{\"M1\":{},\"M2\":{\"enabled\":false}}}", &p, &w) > 0);
    CHECK(p.minutes == 10 && p.max_strikes == 3);
    CHECK(p.slots[0].enabled && strcmp(p.slots[0].variant, "ble-read") == 0);
    CHECK(!p.slots[1].enabled && strcmp(p.slots[1].variant, "buzzer-morse") == 0);
    /* round: 3 missing; M1: 2 missing; M2: variant missing; M3-M6 missing. */
    CHECK(w.count == 3 + 2 + 1 + 4);
}

static void test_pack_invalid_values(void)
{
    d32_pack_t p;
    warns_t w;
    const char *json =
        "{ \"format\": 2, \"id\": \"\", \"title\": 7, \"version\": \"0123456789abcdefXYZ\","
        "  \"round\": { \"minutes\": 0, \"max_strikes\": 10, \"strike_rate\": 0.5, \"training\": \"yes\" },"
        "  \"modules\": {"
        "    \"M1\": { \"enabled\": \"true\", \"variant\": \"BLE-READ\" },"
        "    \"M2\": { \"enabled\": 1, \"variant\": \"bad variant\" },"
        "    \"M3\": { \"enabled\": true, \"variant\": \"\" },"
        "    \"M4\": { \"enabled\": true, \"variant\": \"abcdefghijklmnopqrstuvwxyz\" },"
        "    \"M5\": { \"enabled\": true, \"variant\": 115200 },"
        "    \"M6\": [ 1, 2 ] } }";
    int n = parse(json, &p, &w);
    /* format, id, title, version (truncated), 4 round values,
     * M1 x2, M2 x2, M3 variant, M4 variant, M5 variant, M6 not an object. */
    CHECK(n == 4 + 4 + 2 + 2 + 1 + 1 + 1 + 1);
    CHECK(n == w.count);
    CHECK(strcmp(p.id, "unnamed") == 0);
    CHECK(strcmp(p.title, "Untitled pack") == 0);
    CHECK(strlen(p.version) == D32_PACK_VERSION_MAX - 1);
    CHECK(p.minutes == 45 && p.max_strikes == 3 && !p.training);
    CHECK(p.strike_rate > 1.249f && p.strike_rate < 1.251f);
    CHECK(p.slots[0].enabled && strcmp(p.slots[0].variant, "ble-read") == 0);
    CHECK(strcmp(p.slots[1].variant, "buzzer-morse") == 0);
    CHECK(strcmp(p.slots[2].variant, "menu") == 0);
    CHECK(strcmp(p.slots[3].variant, "patch-a") == 0);
    CHECK(strcmp(p.slots[4].variant, "uart-115200") == 0);
    CHECK(p.slots[5].enabled && strcmp(p.slots[5].variant, "touch-4") == 0);

    /* Range edges and non-integers. */
    const struct {
        const char *round;
        int minutes, strikes;
        int warns;
    } cases[] = {
        { "{\"minutes\":1,\"max_strikes\":1,\"strike_rate\":1.0,\"training\":false}", 1, 1, 0 },
        { "{\"minutes\":180,\"max_strikes\":9,\"strike_rate\":4.0,\"training\":false}", 180, 9, 0 },
        { "{\"minutes\":181,\"max_strikes\":0,\"strike_rate\":4.01,\"training\":false}", 45, 3, 3 },
        { "{\"minutes\":12.5,\"max_strikes\":\"3\",\"strike_rate\":\"1.5\",\"training\":0}", 45, 3, 4 },
        { "{\"minutes\":-5,\"max_strikes\":null,\"strike_rate\":null,\"training\":null}", 45, 3, 4 },
    };
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        char buf[512];
        snprintf(buf, sizeof(buf),
                 "{\"format\":1,\"id\":\"a\",\"title\":\"t\",\"version\":\"1\",\"round\":%s,"
                 "\"modules\":{\"M1\":{\"enabled\":true,\"variant\":\"a\"},\"M2\":{\"enabled\":true,\"variant\":\"b\"},"
                 "\"M3\":{\"enabled\":true,\"variant\":\"c\"},\"M4\":{\"enabled\":true,\"variant\":\"d\"},"
                 "\"M5\":{\"enabled\":true,\"variant\":\"e\"},\"M6\":{\"enabled\":true,\"variant\":\"f\"}}}",
                 cases[i].round);
        CHECK(parse(buf, &p, &w) == cases[i].warns);
        CHECK(p.minutes == cases[i].minutes);
        CHECK(p.max_strikes == cases[i].strikes);
    }
    /* "round" / "modules" of the wrong type. */
    CHECK(parse("{\"format\":1,\"id\":\"a\",\"title\":\"t\",\"version\":\"1\",\"round\":5,\"modules\":[]}", &p, &w) == 2);
    CHECK(p.minutes == 45 && strcmp(p.slots[0].variant, "ble-read") == 0);
}

static void test_pack_unknown_keys(void)
{
    /* FULL with extra keys everywhere: no warnings, same result. */
    const char *json =
        "{ \"format\": 1, \"id\": \"base\", \"title\": \"Base pack\", \"version\": \"0.1.0\","
        "  \"author\": \"someone\", \"extra\": { \"nested\": [1, 2, 3] },"
        "  \"round\": { \"minutes\": 30, \"max_strikes\": 5, \"strike_rate\": 1.5, \"training\": true,"
        "             \"music\": \"loud\" },"
        "  \"modules\": {"
        "    \"M0\": { \"enabled\": true, \"variant\": \"x\" },"
        "    \"M7\": { \"enabled\": true, \"variant\": \"x\" },"
        "    \"m1\": { \"enabled\": true, \"variant\": \"x\" },"
        "    \"M1\": { \"enabled\": false, \"variant\": \"ble-read\", \"colour\": \"red\" },"
        "    \"M2\": { \"enabled\": true, \"variant\": \"buzzer-morse\" },"
        "    \"M3\": { \"enabled\": true, \"variant\": \"menu\" },"
        "    \"M4\": { \"enabled\": true, \"variant\": \"patch-a\" },"
        "    \"M5\": { \"enabled\": true, \"variant\": \"uart-9600\" },"
        "    \"M6\": { \"enabled\": false, \"variant\": \"touch-4\" } } }";
    d32_pack_t a, b;
    warns_t w;
    CHECK(parse(json, &a, &w) == 0);
    CHECK(parse(FULL, &b, &w) == 0);
    CHECK(memcmp(&a, &b, sizeof(a)) == 0);
}

static void test_pack_broken_json(void)
{
    d32_pack_t p;
    warns_t w;
    const char *bad[] = {
        "",
        "{",
        "{ \"format\": 1, ",
        "{ \"format\": 1 \"id\": \"x\" }",
        "{ 'format': 1 }",
        "[ { \"format\": 1 } ]",
        "\"just a string\"",
        "42",
        "null",
    };
    for (size_t i = 0; i < sizeof(bad) / sizeof(bad[0]); i++) {
        CHECK(parse(bad[i], &p, &w) == -1);
        CHECK(w.count == 1);
        CHECK(strcmp(p.id, "builtin") == 0 && p.minutes == 45); /* defaults */
    }
    CHECK(d32_pack_parse(NULL, 0, &p, on_warn, &w) == -1);
    CHECK(d32_pack_parse("{}", 2, &p, NULL, NULL) == 6); /* no warning sink */

    /* Length-limited, not NUL-terminated input: only the first len bytes count. */
    char buf[64];
    memset(buf, 'x', sizeof(buf));
    memcpy(buf, "{\"format\":1}", 12);
    CHECK(d32_pack_parse(buf, 12, &p, on_warn, &w) >= 0);
    CHECK(d32_pack_parse(buf, 11, &p, NULL, NULL) == -1);
}

static void test_pack_names(void)
{
    CHECK(d32_pack_name_valid("default"));
    CHECK(d32_pack_name_valid("Pack_2-B"));
    CHECK(!d32_pack_name_valid(""));
    CHECK(!d32_pack_name_valid(NULL));
    CHECK(!d32_pack_name_valid("../etc"));
    CHECK(!d32_pack_name_valid("a.json"));
    CHECK(!d32_pack_name_valid("with space"));
    CHECK(d32_pack_name_valid("0123456789012345678901234567890"));   /* 31 */
    CHECK(!d32_pack_name_valid("01234567890123456789012345678901")); /* 32 */
    CHECK(strcmp(d32_pack_slot_id(0), "M1") == 0 && strcmp(d32_pack_slot_id(5), "M6") == 0);
    CHECK(strcmp(d32_pack_slot_name(3), "wires") == 0);
    CHECK(d32_pack_slot_id(6) == NULL && d32_pack_slot_name(-1) == NULL);
}

void run_pack_tests(void)
{
    RUN(test_pack_valid);
    RUN(test_pack_defaults);
    RUN(test_pack_invalid_values);
    RUN(test_pack_unknown_keys);
    RUN(test_pack_broken_json);
    RUN(test_pack_names);
}
