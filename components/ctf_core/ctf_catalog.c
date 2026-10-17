/* Static challenge catalogue (SPEC "Challenge catalogue", SPEC order).
 * Array index = progress bit index: append only, never reorder. */
#include <string.h>

#include "ctf_core.h"

#define KIT_USB_UART "USB-UART adapter"
#define KIT_JUMPER   "jumper wire"
#define KIT_LA       "logic analyzer"

static const ctf_challenge_t CATALOG[] = {
    /* BLE (radio mode) */
    {"BLE-01", "BLE", "Read the flag", CTF_EASY, NULL,
     "Connect with a BLE explorer (nRF Connect, bleak, gatttool) and read every characteristic in the board's custom service."},
    {"BLE-02", "BLE", "Hex and friends", CTF_EASY, NULL,
     "The value is wrapped in layers. Peel them in reverse order: one layer only shuffles the byte order, the others are two everyday text encodings."},
    {"BLE-03", "BLE", "Notify me", CTF_EASY, NULL,
     "Some characteristics never answer a read. Enable notifications through the Client Characteristic Configuration descriptor and wait."},
    {"BLE-04", "BLE", "Indicate and ack", CTF_MEDIUM, NULL,
     "This one uses indications, not notifications: the next fragment only comes once your client confirms the previous one. Subscribe for indications and collect every piece."},
    {"BLE-05", "BLE", "Write to unlock", CTF_EASY, NULL,
     "Characteristics can carry a human-readable User Description descriptor. Read it, do what it says, then look at the service again."},
    {"BLE-06", "BLE", "Descriptor hunt", CTF_MEDIUM, NULL,
     "Not every secret lives in a characteristic value. List all descriptors of each characteristic, especially ones with unfamiliar UUIDs."},
    {"BLE-07", "BLE", "Advertising payload", CTF_MEDIUM, NULL,
     "No connection needed: watch the manufacturer-specific data in the board's advertisements for several seconds. It changes, and each version holds a piece."},
    {"BLE-08", "BLE", "Big MTU", CTF_MEDIUM, NULL,
     "With the default ATT MTU you only see the start of a long value. Negotiate a bigger MTU or use a long (offset) read to get the end."},
    {"BLE-09", "BLE", "Passkey pairing", CTF_MEDIUM, NULL,
     "This characteristic needs an encrypted, authenticated link. Pair using passkey entry; the board tells you its passkey on the serial console at boot."},
    {"BLE-10", "BLE", "Rate-limited PIN", CTF_HARD, NULL,
     "Four digits is only 10,000 guesses. Script them and work with the lockout: pause after each batch of wrong tries instead of hammering."},
    {"BLE-11", "BLE", "Write-without-response sequence", CTF_HARD, NULL,
     "Both order and timing matter: send each value of the sequence as a write-without-response, less than half a second after the previous one. Script it."},

    /* BT Classic (radio mode) */
    {"BTC-01", "BTC", "SPP console", CTF_EASY, NULL,
     "This is Bluetooth Classic, not BLE. Pair with the board and open its Serial Port Profile (RFCOMM) channel in a terminal."},
    {"BTC-02", "BTC", "Hidden menu", CTF_MEDIUM, NULL,
     "The SPP shell's help does not list everything. Re-read the banner carefully for a command that help forgets to mention."},
    {"BTC-03", "BTC", "Device class clue", CTF_MEDIUM, NULL,
     "Run a Classic inquiry and inspect everything the board announces: its name, its Class of Device bits and its extended inquiry response data."},

    /* Web (net mode) */
    {"WEB-01", "WEB", "Hidden SSID", CTF_EASY, NULL,
     "A hidden network still exists, you just need its name. A serial console command tells you, in an encoding you will have to decode."},
    {"WEB-02", "WEB", "View source", CTF_EASY, NULL,
     "Read the page source, not just the rendered page. Then check what the site asks search engines to stay away from."},
    {"WEB-03", "WEB", "Cookie admin", CTF_EASY, NULL,
     "Look at the cookies the site sets. The server trusts whatever you send back."},
    {"WEB-04", "WEB", "Header check", CTF_EASY, NULL,
     "The API cares about who is asking. Work out which request headers it wants; the value it expects is shown somewhere on the site."},
    {"WEB-05", "WEB", "Weak JWT", CTF_MEDIUM, NULL,
     "Decode your session token. An HS256 secret picked from a short public wordlist can be brute-forced offline, and then you can sign your own claims."},
    {"WEB-06", "WEB", "Ping tool", CTF_MEDIUM, NULL,
     "The diagnostics form takes a filename. What happens when that filename climbs up out of its folder?"},
    {"WEB-07", "WEB", "WebSocket chatter", CTF_MEDIUM, NULL,
     "Connect to the WebSocket with a client that shows binary frames, and be patient: most of what arrives is noise."},
    {"WEB-08", "WEB", "mDNS discovery", CTF_MEDIUM, NULL,
     "Some services are only announced over multicast DNS. Browse the service types on the board's network and follow the port that is advertised."},
    {"WEB-09", "WEB", "UDP knock", CTF_HARD, NULL,
     "A closed port can open if you knock the right way. The console hints at which UDP ports to hit; order matters and the door does not stay open long."},

    /* Serial (always) */
    {"SER-01", "SER", "Boot log", CTF_EASY, NULL,
     "Everything printed at boot scrolls past fast. Capture the full serial log from a reset and search it."},
    {"SER-02", "SER", "Wrong baud", CTF_MEDIUM, KIT_USB_UART,
     "The board also talks on a second UART at an unusual baud rate. Wire a USB-UART adapter to that pin (with shared GND) and try non-standard speeds."},
    {"SER-03", "SER", "Debug login", CTF_HARD, NULL,
     "The login check takes longer the more of the password you get right. Time each guess and recover it one character at a time."},
    {"SER-04", "SER", "Escape sequence", CTF_MEDIUM, NULL,
     "The console reacts to a control-key escape followed by a short debugging word, all typed within a second. Use a terminal that can send raw control characters."},

    /* Hardware (always) */
    {"HW-01", "HW", "Jumper it", CTF_EASY, KIT_JUMPER,
     "At boot the board checks whether two of its pins are connected. Bridge them with a jumper wire (see the pin map) and press reset."},
    {"HW-02", "HW", "Blinky Morse", CTF_EASY, NULL,
     "Watch the onboard LED: short and long blinks. Film it or point a light sensor at it, then decode the Morse."},
    {"HW-03", "HW", "PWM frequency", CTF_MEDIUM, KIT_LA,
     "Probe the PWM pin with a logic analyzer and measure the frequency, then give it to the answer command."},
    {"HW-04", "HW", "I2C chatter", CTF_MEDIUM, KIT_LA,
     "Hook a logic analyzer to SDA and SCL and use an I2C decoder. Nobody acknowledges, but the bytes are still on the wire."},
    {"HW-05", "HW", "SPI dump", CTF_MEDIUM, KIT_LA,
     "Capture SCK, MOSI and CS with a logic analyzer and decode as SPI mode 0. The transfer repeats every few seconds."},
    {"HW-06", "HW", "Touch pad code", CTF_MEDIUM, NULL,
     "The touch pads form a keypad. The console gives a clue to the sequence; touch the pads in that order without long pauses."},

    /* Firmware reversing (always) */
    {"RE-01", "RE", "Strings in flash", CTF_EASY, NULL,
     "Dump the flash with esptool and look for readable text. Not every partition holds code."},
    {"RE-02", "RE", "NVS secrets", CTF_MEDIUM, NULL,
     "Dump the NVS partition and parse its entries (ESP-IDF ships tools for that). The value you want is hidden behind a single repeating byte."},
    {"RE-03", "RE", "Crackme", CTF_HARD, NULL,
     "Dump the factory app partition and load it in Ghidra with Xtensa support. Find the unlock command handler and invert its key check."},
    {"RE-04", "RE", "XOR'd asset", CTF_HARD, NULL,
     "The blob in the filesystem is XORed with a keystream. Find the simple generator in the firmware; its seed is something you can read from your own board."},

    /* Crypto (always, console) */
    {"CRY-01", "CRY", "Classic cipher", CTF_EASY, NULL,
     "It is a classic polyalphabetic cipher. Pieces of the key word are hidden in other tracks' banners."},
    {"CRY-02", "CRY", "ECB penguin", CTF_HARD, NULL,
     "ECB encrypts identical blocks identically. Pad your input so one unknown byte at a time lands at the end of a block, then match it against your own guesses."},
    {"CRY-03", "CRY", "Reused nonce", CTF_MEDIUM, NULL,
     "Reusing a CTR nonce means both messages share one keystream. XOR the ciphertexts together and use the plaintext you already know."},
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
