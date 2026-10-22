/* Fragment distribution: every letter of the target colour on exactly one
 * enabled module, for every set of enabled modules and every colour. */
#include <string.h>

#include "test_util.h"

static int popcount6(unsigned m)
{
    int n = 0;
    for (int i = 0; i < 6; i++) {
        n += (m >> i) & 1u;
    }
    return n;
}

/* Checks the distribution of the current round; returns the colour index. */
static int check_distribution(d32_t *d, unsigned mask)
{
    int n = popcount6(mask);
    int t = d32_target_wire(d);
    const char *colour = d32_wire_colour(t);
    int len = (int)strlen(colour);
    int cap = (len + n - 1) / n;
    int cover[D32_COLOUR_MAX] = {0};

    CHECK(d32_colour_len(d) == len);
    for (int s = 0; s < D32_SLOTS; s++) {
        d32_frag_t f[D32_MAX_FRAGS];
        int k = d32_slot_frags(d, s, f, D32_MAX_FRAGS);
        if (!((mask >> s) & 1u)) {
            CHECK(k == 0);
            continue;
        }
        CHECK(k <= cap);
        CHECK(k >= len / n); /* even spread: floor or ceil */
        if (n >= 3) {
            CHECK(k <= 2);
        }
        for (int i = 0; i < k; i++) {
            CHECK(f[i].pos >= 1 && f[i].pos <= len);
            if (f[i].pos < 1 || f[i].pos > len) {
                continue;
            }
            CHECK(f[i].letter == colour[f[i].pos - 1]);
            cover[f[i].pos - 1]++;
            if (i > 0) {
                CHECK(f[i - 1].pos < f[i].pos); /* sorted */
            }
        }
    }
    for (int i = 0; i < len; i++) {
        CHECK(cover[i] == 1);
    }
    return t;
}

static void test_coverage_all_combinations(void)
{
    d32_t d;
    int combos = 0;
    for (unsigned mask = 1; mask < 64; mask++) {
        d32_config_t c = cfg_slots(mask);
        setup(&d, &c);
        unsigned seen = 0;
        for (uint32_t seed = 0; seed < 400 && seen != 0x3F; seed++) {
            d32_reset(&d);
            CHECK(d32_arm(&d, seed * 2654435761u) == D32_ARM_OK);
            int t = check_distribution(&d, mask);
            if (!(seen & (1u << t))) {
                seen |= 1u << t;
                combos++;
                /* disarming every module reveals the whole colour */
                char w[D32_COLOUR_MAX + 1];
                CHECK(d32_revealed_mask(&d) == 0);
                disarm_all(&d);
                CHECK(strcmp(d32_revealed_word(&d, w), d32_wire_colour(t)) == 0);
            }
        }
        CHECK(seen == 0x3F);
    }
    CHECK(combos == 63 * 6);
}

static void test_reveal_progressive(void)
{
    d32_t d;
    setup(&d, NULL);
    d32_arm(&d, SEED_A);
    const char *colour = d32_wire_colour(d32_target_wire(&d));
    char w[D32_COLOUR_MAX + 1], code[7];
    char blank[D32_COLOUR_MAX + 1];
    memset(blank, '_', strlen(colour));
    blank[strlen(colour)] = '\0';
    CHECK(strcmp(d32_revealed_word(&d, w), blank) == 0);

    uint8_t mask = 0;
    for (int s = 0; s < D32_SLOTS; s++) {
        d32_frag_t f[D32_MAX_FRAGS];
        int k = d32_slot_frags(&d, s, f, D32_MAX_FRAGS);
        d32_code_for(&d, s, code);
        d32_submit_code(&d, code, NULL);
        for (int i = 0; i < k; i++) {
            mask |= (uint8_t)(1u << (f[i].pos - 1));
        }
        CHECK(d32_revealed_mask(&d) == mask);
        d32_revealed_word(&d, w);
        for (size_t i = 0; i < strlen(colour); i++) {
            CHECK(w[i] == ((mask >> i) & 1u ? colour[i] : '_'));
        }
    }
    CHECK(strcmp(w, colour) == 0);
}

static void test_deterministic(void)
{
    d32_t a, b;
    setup(&a, NULL);
    setup(&b, NULL);
    d32_arm(&a, SEED_B);
    d32_arm(&b, SEED_B);
    for (int s = 0; s < D32_SLOTS; s++) {
        d32_frag_t fa[D32_MAX_FRAGS], fb[D32_MAX_FRAGS];
        int ka = d32_slot_frags(&a, s, fa, D32_MAX_FRAGS);
        int kb = d32_slot_frags(&b, s, fb, D32_MAX_FRAGS);
        CHECK(ka == kb);
        for (int i = 0; i < ka && i < kb; i++) {
            CHECK(fa[i].pos == fb[i].pos && fa[i].letter == fb[i].letter);
        }
    }
    /* frag_str format */
    char s[4];
    d32_frag_t f = {3, 'L'};
    CHECK(strcmp(d32_frag_str(f, s), "3:L") == 0);
    /* slot_frags with a small buffer reports the full count */
    for (int i = 0; i < D32_SLOTS; i++) {
        d32_frag_t one[1];
        CHECK(d32_slot_frags(&a, i, one, 1) == d32_slot_frags(&a, i, NULL, 0));
    }
    CHECK(d32_slot_frags(&a, 7, NULL, 0) == 0);
}

void run_frag_tests(void)
{
    RUN(test_coverage_all_combinations);
    RUN(test_reveal_progressive);
    RUN(test_deterministic);
}
