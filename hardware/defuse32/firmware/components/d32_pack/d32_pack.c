/* Pack loader: SD card listing/loading, logging, current selection. */
#include "d32_pack.h"

#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include "esp_log.h"

static const char *TAG = "d32_pack";

static d32_pack_t s_current;
static char s_current_name[D32_PACK_NAME_MAX] = D32_PACK_BUILTIN_NAME;
static bool s_current_set;

static void log_warn(void *ctx, const char *msg)
{
    ESP_LOGW(TAG, "%s: %s", (const char *)ctx, msg);
}

static int cmp_names(const void *a, const void *b)
{
    return strcmp((const char *)a, (const char *)b);
}

int d32_pack_list(const char *dir, char names[][D32_PACK_NAME_MAX], int max)
{
    DIR *d = opendir(dir);
    if (!d) {
        return -1;
    }
    int n = 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL && n < max) {
        size_t len = strlen(e->d_name);
        if (len <= 5 || strcasecmp(e->d_name + len - 5, ".json") != 0) {
            continue;
        }
        char base[D32_PACK_NAME_MAX];
        if (len - 5 >= sizeof(base)) {
            continue;
        }
        memcpy(base, e->d_name, len - 5);
        base[len - 5] = '\0';
        if (!d32_pack_name_valid(base)) {
            continue;
        }
        memcpy(names[n], base, sizeof(base));
        n++;
    }
    closedir(d);
    qsort(names, (size_t)n, D32_PACK_NAME_MAX, cmp_names);
    return n;
}

int d32_pack_load_from(const char *dir, const char *name, d32_pack_t *out)
{
    d32_pack_defaults(out);
    if (name && strcmp(name, D32_PACK_BUILTIN_NAME) == 0) {
        return 0;
    }
    if (!d32_pack_name_valid(name)) {
        ESP_LOGE(TAG, "invalid pack name \"%s\" (use [A-Za-z0-9_-], max %d chars)",
                 name ? name : "", D32_PACK_NAME_MAX - 1);
        return -1;
    }
    char path[128];
    snprintf(path, sizeof(path), "%s/%s.json", dir, name);
    FILE *f = fopen(path, "rb");
    if (!f) {
        ESP_LOGE(TAG, "cannot open %s", path);
        return -1;
    }
    char *buf = malloc(D32_PACK_FILE_MAX + 1);
    if (!buf) {
        fclose(f);
        return -1;
    }
    size_t n = fread(buf, 1, D32_PACK_FILE_MAX + 1, f);
    fclose(f);
    if (n > D32_PACK_FILE_MAX) {
        ESP_LOGE(TAG, "%s is larger than %d bytes", path, D32_PACK_FILE_MAX);
        free(buf);
        return -1;
    }
    int warnings = d32_pack_parse(buf, n, out, log_warn, (void *)name);
    free(buf);
    if (warnings < 0) {
        ESP_LOGE(TAG, "%s is not a valid pack", path);
        d32_pack_defaults(out);
        return -1;
    }
    ESP_LOGI(TAG, "loaded %s: \"%s\" %s (%d warning%s)", path, out->title, out->version,
             warnings, warnings == 1 ? "" : "s");
    return 0;
}

int d32_pack_load(const char *name, d32_pack_t *out)
{
    return d32_pack_load_from(D32_PACK_DIR, name, out);
}

const d32_pack_t *d32_pack_current(void)
{
    if (!s_current_set) {
        d32_pack_defaults(&s_current);
        s_current_set = true;
    }
    return &s_current;
}

const char *d32_pack_current_name(void)
{
    return s_current_name;
}

void d32_pack_select(const d32_pack_t *pack, const char *name)
{
    s_current = *pack;
    s_current_set = true;
    snprintf(s_current_name, sizeof(s_current_name), "%s", name ? name : "?");
}
