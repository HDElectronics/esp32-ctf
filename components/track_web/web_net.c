/* track_web network extras (SPEC "Web"):
 *   WEB-08  mDNS hostname esp32-ctf, service _ctf._tcp -> beacon HTTP server on a
 *           per-board port (8000..8999) whose / shows the flag. Not linked anywhere.
 *   WEB-09  UDP knock on 3 per-board ports (20000..40000), in order, each within
 *           5 s of the previous; then TCP 31337 accepts connections from that
 *           client IP for 30 s, prints the flag and closes. Wrong port resets.
 * All sockets bind to INADDR_ANY, so both the SoftAP and the dev station work. */
#include "web_priv.h"

#include <stdio.h>
#include <string.h>
#include "ctf_core.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include "mdns.h"

static const char *TAG = "web_net";

/* ---------------- WEB-08 ---------------- */

static esp_err_t h_beacon(httpd_req_t *req)
{
    char flag[18], text[96];
    ctf_flag("WEB-08", flag);
    snprintf(text, sizeof text, "ctf beacon: you followed the announcement.\nWEB-08 %s\n", flag);
    httpd_resp_set_type(req, "text/plain");
    return httpd_resp_sendstr(req, text);
}

bool web_mdns_start(void)
{
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.server_port = g_web.beacon_port;
    cfg.ctrl_port = WEB_BEACON_CTRL;
    cfg.max_open_sockets = 2;
    cfg.max_uri_handlers = 1;
    cfg.lru_purge_enable = true;
    httpd_handle_t srv = NULL;
    esp_err_t err = httpd_start(&srv, &cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "beacon httpd: %s", esp_err_to_name(err));
        return false;
    }
    const httpd_uri_t root = {.uri = "/", .method = HTTP_GET, .handler = h_beacon};
    httpd_register_uri_handler(srv, &root);

    err = mdns_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "mdns_init: %s", esp_err_to_name(err));
        return false;
    }
    mdns_hostname_set("esp32-ctf");
    mdns_instance_name_set("ESP32 CTF");
    mdns_txt_item_t txt[] = {
        {"board", "esp32-ctf"},
        {"path", "/"},
        {"hint", "plain HTTP on the advertised port"},
    };
    err = mdns_service_add("CTF beacon", "_ctf", "_tcp", g_web.beacon_port, txt,
                           sizeof txt / sizeof txt[0]);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "mdns_service_add: %s", esp_err_to_name(err));
        return false;
    }
    return true;
}

/* ---------------- WEB-09 ---------------- */

#define KNOCK_GAP_US   (5 * 1000000LL)
#define DOOR_OPEN_US   (30 * 1000000LL)
#define SLOTS          4

typedef struct {
    uint32_t ip;      /* network order; 0 = free */
    int stage;        /* knocks matched so far */
    int64_t last_us;  /* time of the last matched knock */
} knocker_t;

typedef struct {
    uint32_t ip;
    int64_t until_us;
} window_t;

static knocker_t s_knock[SLOTS];
static window_t s_win[SLOTS];

static knocker_t *knocker_for(uint32_t ip)
{
    knocker_t *oldest = &s_knock[0];
    for (int i = 0; i < SLOTS; i++) {
        if (s_knock[i].ip == ip) {
            return &s_knock[i];
        }
        if (s_knock[i].last_us < oldest->last_us) {
            oldest = &s_knock[i];
        }
    }
    *oldest = (knocker_t){.ip = ip};
    return oldest;
}

static void knock(uint32_t ip, int port_idx, int64_t now)
{
    knocker_t *k = knocker_for(ip);
    if (k->stage > 0 && now - k->last_us > KNOCK_GAP_US) {
        k->stage = 0;
    }
    if (port_idx == k->stage) {
        k->stage++;
    } else {
        k->stage = port_idx == 0 ? 1 : 0; /* wrong order resets */
    }
    k->last_us = now;
    if (k->stage < WEB_KNOCK_N) {
        return;
    }
    k->stage = 0;
    window_t *w = &s_win[0];
    for (int i = 0; i < SLOTS; i++) {
        if (s_win[i].ip == ip || s_win[i].until_us < w->until_us) {
            w = &s_win[i];
            if (s_win[i].ip == ip) {
                break;
            }
        }
    }
    w->ip = ip;
    w->until_us = now + DOOR_OPEN_US;
    ESP_LOGI(TAG, "knock accepted, door open for 30 s");
}

static bool door_allowed(uint32_t ip, int64_t now)
{
    for (int i = 0; i < SLOTS; i++) {
        if (s_win[i].ip == ip && s_win[i].until_us > now) {
            return true;
        }
    }
    return false;
}

static bool any_window(int64_t now)
{
    for (int i = 0; i < SLOTS; i++) {
        if (s_win[i].ip && s_win[i].until_us > now) {
            return true;
        }
    }
    return false;
}

static int udp_bind(uint16_t port)
{
    int fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (fd < 0) {
        return -1;
    }
    struct sockaddr_in a = {.sin_family = AF_INET, .sin_port = htons(port),
                            .sin_addr.s_addr = htonl(INADDR_ANY)};
    if (bind(fd, (struct sockaddr *)&a, sizeof a) != 0) {
        close(fd);
        return -1;
    }
    return fd;
}

static int door_open(void)
{
    int fd = socket(AF_INET, SOCK_STREAM, IPPROTO_IP);
    if (fd < 0) {
        return -1;
    }
    int one = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    struct sockaddr_in a = {.sin_family = AF_INET, .sin_port = htons(WEB_DOOR_PORT),
                            .sin_addr.s_addr = htonl(INADDR_ANY)};
    if (bind(fd, (struct sockaddr *)&a, sizeof a) != 0 || listen(fd, 2) != 0) {
        ESP_LOGE(TAG, "door bind/listen failed: errno %d", errno);
        close(fd);
        return -1;
    }
    return fd;
}

static void door_serve(int lfd, int64_t now)
{
    struct sockaddr_in peer;
    socklen_t pl = sizeof peer;
    int c = accept(lfd, (struct sockaddr *)&peer, &pl);
    if (c < 0) {
        return;
    }
    if (door_allowed(peer.sin_addr.s_addr, now)) {
        struct timeval tv = {.tv_sec = 2};
        setsockopt(c, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof tv);
        char flag[18], text[80];
        ctf_flag("WEB-09", flag);
        int n = snprintf(text, sizeof text, "the door creaks open.\nWEB-09 %s\n", flag);
        send(c, text, (size_t)n, 0);
        shutdown(c, SHUT_WR);
    }
    close(c);
}

static void knock_task(void *arg)
{
    (void)arg;
    int udp[WEB_KNOCK_N];
    for (int i = 0; i < WEB_KNOCK_N; i++) {
        udp[i] = udp_bind(g_web.knock[i]);
        if (udp[i] < 0) {
            ESP_LOGE(TAG, "knock port bind failed");
        }
    }
    int door = -1;
    for (;;) {
        int64_t now = esp_timer_get_time();
        bool want_door = any_window(now);
        if (want_door && door < 0) {
            door = door_open();
        } else if (!want_door && door >= 0) {
            close(door);
            door = -1;
        }
        fd_set rd;
        FD_ZERO(&rd);
        int maxfd = -1;
        for (int i = 0; i < WEB_KNOCK_N; i++) {
            if (udp[i] >= 0) {
                FD_SET(udp[i], &rd);
                maxfd = udp[i] > maxfd ? udp[i] : maxfd;
            }
        }
        if (door >= 0) {
            FD_SET(door, &rd);
            maxfd = door > maxfd ? door : maxfd;
        }
        struct timeval tv = {.tv_sec = 0, .tv_usec = 500000};
        if (maxfd < 0) {
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }
        if (select(maxfd + 1, &rd, NULL, NULL, &tv) <= 0) {
            continue;
        }
        now = esp_timer_get_time();
        for (int i = 0; i < WEB_KNOCK_N; i++) {
            if (udp[i] >= 0 && FD_ISSET(udp[i], &rd)) {
                uint8_t junk[64];
                struct sockaddr_in src;
                socklen_t sl = sizeof src;
                if (recvfrom(udp[i], junk, sizeof junk, 0, (struct sockaddr *)&src, &sl) >= 0) {
                    knock(src.sin_addr.s_addr, i, now);
                }
            }
        }
        if (door >= 0 && FD_ISSET(door, &rd)) {
            door_serve(door, now);
        }
    }
}

bool web_knock_start(void)
{
    return xTaskCreate(knock_task, "web_knock", 3072, NULL, 4, NULL) == pdPASS;
}
