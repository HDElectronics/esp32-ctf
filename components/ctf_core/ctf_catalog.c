/* Static challenge catalogue (SPEC "Challenge catalogue", SPEC order) + hint tiers.
 * Array index = progress bit index: append only, never reorder. */
#include <string.h>

#include "ctf_core.h"

#define KIT_USB_UART "USB-UART adapter"
#define KIT_JUMPER   "jumper wire"
#define KIT_LA       "logic analyzer"

/* Hint tiers (SPEC "v0.2.0"): {1 nudge, 2 hint, 3 walkthrough}. Tier 1 names
 * no tool or technique, tier 2 names the technique, tier 3 walks through the
 * solve and stops before the flag. No tier holds a flag or per-board value.
 * Tiers 1 and 3 are placeholders until the hint-content task writes them. */
#define NUDGE(id)       "Tier 1 nudge for " id " (to be written)."
#define WALKTHROUGH(id) "Tier 3 walkthrough for " id " (to be written)."

static const ctf_challenge_t CATALOG[] = {
    /* BLE (radio mode) */
    {"BLE-01", "BLE", "Read the flag", CTF_EASY, NULL,
     {NUDGE("BLE-01"),
      "Connect with a BLE explorer (nRF Connect, bleak, gatttool) and read every characteristic in the board's custom service.",
      WALKTHROUGH("BLE-01")}},
    {"BLE-02", "BLE", "Hex and friends", CTF_EASY, NULL,
     {NUDGE("BLE-02"),
      "The value is wrapped in layers. Peel them in reverse order: one layer only shuffles the byte order, the others are two everyday text encodings.",
      WALKTHROUGH("BLE-02")}},
    {"BLE-03", "BLE", "Notify me", CTF_EASY, NULL,
     {NUDGE("BLE-03"),
      "Some characteristics never answer a read. Enable notifications through the Client Characteristic Configuration descriptor and wait.",
      WALKTHROUGH("BLE-03")}},
    {"BLE-04", "BLE", "Indicate and ack", CTF_MEDIUM, NULL,
     {NUDGE("BLE-04"),
      "This one uses indications, not notifications: the next fragment only comes once your client confirms the previous one. Subscribe for indications and collect every piece.",
      WALKTHROUGH("BLE-04")}},
    {"BLE-05", "BLE", "Write to unlock", CTF_EASY, NULL,
     {NUDGE("BLE-05"),
      "Characteristics can carry a human-readable User Description descriptor. Read it, do what it says, then look at the service again.",
      WALKTHROUGH("BLE-05")}},
    {"BLE-06", "BLE", "Descriptor hunt", CTF_MEDIUM, NULL,
     {NUDGE("BLE-06"),
      "Not every secret lives in a characteristic value. List all descriptors of each characteristic, especially ones with unfamiliar UUIDs.",
      WALKTHROUGH("BLE-06")}},
    {"BLE-07", "BLE", "Advertising payload", CTF_MEDIUM, NULL,
     {NUDGE("BLE-07"),
      "No connection needed: watch the manufacturer-specific data in the board's advertisements for several seconds. It changes, and each version holds a piece.",
      WALKTHROUGH("BLE-07")}},
    {"BLE-08", "BLE", "Big MTU", CTF_MEDIUM, NULL,
     {NUDGE("BLE-08"),
      "With the default ATT MTU you only see the start of a long value. Negotiate a bigger MTU or use a long (offset) read to get the end.",
      WALKTHROUGH("BLE-08")}},
    {"BLE-09", "BLE", "Passkey pairing", CTF_MEDIUM, NULL,
     {NUDGE("BLE-09"),
      "This characteristic needs an encrypted, authenticated link. Pair using passkey entry; the board tells you its passkey on the serial console at boot.",
      WALKTHROUGH("BLE-09")}},
    {"BLE-10", "BLE", "Rate-limited PIN", CTF_HARD, NULL,
     {NUDGE("BLE-10"),
      "Four digits is only 10,000 guesses. Script them and work with the lockout: pause after each batch of wrong tries instead of hammering.",
      WALKTHROUGH("BLE-10")}},
    {"BLE-11", "BLE", "Write-without-response sequence", CTF_HARD, NULL,
     {NUDGE("BLE-11"),
      "Both order and timing matter: send each value of the sequence as a write-without-response, less than half a second after the previous one. Script it.",
      WALKTHROUGH("BLE-11")}},

    /* BT Classic (radio mode) */
    {"BTC-01", "BTC", "SPP console", CTF_EASY, NULL,
     {NUDGE("BTC-01"),
      "This is Bluetooth Classic, not BLE. Pair with the board and open its Serial Port Profile (RFCOMM) channel in a terminal.",
      WALKTHROUGH("BTC-01")}},
    {"BTC-02", "BTC", "Hidden menu", CTF_MEDIUM, NULL,
     {NUDGE("BTC-02"),
      "The SPP shell's help does not list everything. Re-read the banner carefully for a command that help forgets to mention.",
      WALKTHROUGH("BTC-02")}},
    {"BTC-03", "BTC", "Device class clue", CTF_MEDIUM, NULL,
     {NUDGE("BTC-03"),
      "Run a Classic inquiry and inspect everything the board announces: its name, its Class of Device bits and its extended inquiry response data.",
      WALKTHROUGH("BTC-03")}},

    /* Web (net mode) */
    {"WEB-01", "WEB", "Hidden SSID", CTF_EASY, NULL,
     {NUDGE("WEB-01"),
      "A hidden network still exists, you just need its name. A serial console command tells you, in an encoding you will have to decode.",
      WALKTHROUGH("WEB-01")}},
    {"WEB-02", "WEB", "View source", CTF_EASY, NULL,
     {NUDGE("WEB-02"),
      "Read the page source, not just the rendered page. Then check what the site asks search engines to stay away from.",
      WALKTHROUGH("WEB-02")}},
    {"WEB-03", "WEB", "Cookie admin", CTF_EASY, NULL,
     {NUDGE("WEB-03"),
      "Look at the cookies the site sets. The server trusts whatever you send back.",
      WALKTHROUGH("WEB-03")}},
    {"WEB-04", "WEB", "Header check", CTF_EASY, NULL,
     {NUDGE("WEB-04"),
      "The API cares about who is asking. Work out which request headers it wants; the value it expects is shown somewhere on the site.",
      WALKTHROUGH("WEB-04")}},
    {"WEB-05", "WEB", "Weak JWT", CTF_MEDIUM, NULL,
     {NUDGE("WEB-05"),
      "Decode your session token. An HS256 secret picked from a short public wordlist can be brute-forced offline, and then you can sign your own claims.",
      WALKTHROUGH("WEB-05")}},
    {"WEB-06", "WEB", "Ping tool", CTF_MEDIUM, NULL,
     {NUDGE("WEB-06"),
      "The diagnostics form takes a filename. What happens when that filename climbs up out of its folder?",
      WALKTHROUGH("WEB-06")}},
    {"WEB-07", "WEB", "WebSocket chatter", CTF_MEDIUM, NULL,
     {NUDGE("WEB-07"),
      "Connect to the WebSocket with a client that shows binary frames, and be patient: most of what arrives is noise.",
      WALKTHROUGH("WEB-07")}},
    {"WEB-08", "WEB", "mDNS discovery", CTF_MEDIUM, NULL,
     {NUDGE("WEB-08"),
      "Some services are only announced over multicast DNS. Browse the service types on the board's network and follow the port that is advertised.",
      WALKTHROUGH("WEB-08")}},
    {"WEB-09", "WEB", "UDP knock", CTF_HARD, NULL,
     {NUDGE("WEB-09"),
      "A closed port can open if you knock the right way. The console hints at which UDP ports to hit; order matters and the door does not stay open long.",
      WALKTHROUGH("WEB-09")}},

    /* Serial (always) */
    {"SER-01", "SER", "Boot log", CTF_EASY, NULL,
     {NUDGE("SER-01"),
      "Everything printed at boot scrolls past fast. Capture the full serial log from a reset and search it.",
      WALKTHROUGH("SER-01")}},
    {"SER-02", "SER", "Wrong baud", CTF_MEDIUM, KIT_USB_UART,
     {NUDGE("SER-02"),
      "The board also talks on a second UART at an unusual baud rate. Wire a USB-UART adapter to that pin (with shared GND) and try non-standard speeds.",
      WALKTHROUGH("SER-02")}},
    {"SER-03", "SER", "Debug login", CTF_HARD, NULL,
     {NUDGE("SER-03"),
      "The login check takes longer the more of the password you get right. Time each guess and recover it one character at a time.",
      WALKTHROUGH("SER-03")}},
    {"SER-04", "SER", "Escape sequence", CTF_MEDIUM, NULL,
     {NUDGE("SER-04"),
      "The console reacts to a control-key escape followed by a short debugging word, all typed within a second. Use a terminal that can send raw control characters.",
      WALKTHROUGH("SER-04")}},

    /* Hardware (always) */
    {"HW-01", "HW", "Jumper it", CTF_EASY, KIT_JUMPER,
     {NUDGE("HW-01"),
      "At boot the board checks whether two of its pins are connected. Bridge them with a jumper wire (see the pin map) and press reset.",
      WALKTHROUGH("HW-01")}},
    {"HW-02", "HW", "Blinky Morse", CTF_EASY, NULL,
     {NUDGE("HW-02"),
      "Watch the onboard LED: short and long blinks. Film it or point a light sensor at it, then decode the Morse.",
      WALKTHROUGH("HW-02")}},
    {"HW-03", "HW", "PWM frequency", CTF_MEDIUM, KIT_LA,
     {NUDGE("HW-03"),
      "Probe the PWM pin with a logic analyzer and measure the frequency, then give it to the answer command.",
      WALKTHROUGH("HW-03")}},
    {"HW-04", "HW", "I2C chatter", CTF_MEDIUM, KIT_LA,
     {NUDGE("HW-04"),
      "Hook a logic analyzer to SDA and SCL and use an I2C decoder. Nobody acknowledges, but the bytes are still on the wire.",
      WALKTHROUGH("HW-04")}},
    {"HW-05", "HW", "SPI dump", CTF_MEDIUM, KIT_LA,
     {NUDGE("HW-05"),
      "Capture SCK, MOSI and CS with a logic analyzer and decode as SPI mode 0. The transfer repeats every few seconds.",
      WALKTHROUGH("HW-05")}},
    {"HW-06", "HW", "Touch pad code", CTF_MEDIUM, NULL,
     {NUDGE("HW-06"),
      "The touch pads form a keypad. The console gives a clue to the sequence; touch the pads in that order without long pauses.",
      WALKTHROUGH("HW-06")}},

    /* Firmware reversing (always) */
    {"RE-01", "RE", "Strings in flash", CTF_EASY, NULL,
     {NUDGE("RE-01"),
      "Dump the flash with esptool and look for readable text. Not every partition holds code.",
      WALKTHROUGH("RE-01")}},
    {"RE-02", "RE", "NVS secrets", CTF_MEDIUM, NULL,
     {NUDGE("RE-02"),
      "Dump the NVS partition and parse its entries (ESP-IDF ships tools for that). The value you want is hidden behind a single repeating byte.",
      WALKTHROUGH("RE-02")}},
    {"RE-03", "RE", "Crackme", CTF_HARD, NULL,
     {NUDGE("RE-03"),
      "Dump the factory app partition and load it in Ghidra with Xtensa support. Find the unlock command handler and invert its key check.",
      WALKTHROUGH("RE-03")}},
    {"RE-04", "RE", "XOR'd asset", CTF_HARD, NULL,
     {NUDGE("RE-04"),
      "The blob in the filesystem is XORed with a keystream. Find the simple generator in the firmware; its seed is something you can read from your own board.",
      WALKTHROUGH("RE-04")}},

    /* Crypto (always, console) */
    {"CRY-01", "CRY", "Classic cipher", CTF_EASY, NULL,
     {NUDGE("CRY-01"),
      "It is a classic polyalphabetic cipher. Pieces of the key word are hidden in other tracks' banners.",
      WALKTHROUGH("CRY-01")}},
    {"CRY-02", "CRY", "ECB penguin", CTF_HARD, NULL,
     {NUDGE("CRY-02"),
      "ECB encrypts identical blocks identically. Pad your input so one unknown byte at a time lands at the end of a block, then match it against your own guesses.",
      WALKTHROUGH("CRY-02")}},
    {"CRY-03", "CRY", "Reused nonce", CTF_MEDIUM, NULL,
     {NUDGE("CRY-03"),
      "Reusing a CTR nonce means both messages share one keystream. XOR the ciphertexts together and use the plaintext you already know.",
      WALKTHROUGH("CRY-03")}},
};

#define CATALOG_LEN (sizeof(CATALOG) / sizeof(CATALOG[0]))

_Static_assert(CATALOG_LEN == 40, "SPEC catalogue has 40 challenges");
_Static_assert(CATALOG_LEN <= CTF_MAX_CHALLENGES, "progress bitmap is 64-bit");

size_t ctf_count(void)
{
    return CATALOG_LEN;
}

const ctf_challenge_t *ctf_get(size_t i)
{
    return i < CATALOG_LEN ? &CATALOG[i] : NULL;
}

const ctf_challenge_t *ctf_find(const char *id)
{
    if (!id) {
        return NULL;
    }
    for (size_t i = 0; i < CATALOG_LEN; i++) {
        if (strcmp(CATALOG[i].id, id) == 0) {
            return &CATALOG[i];
        }
    }
    return NULL;
}
