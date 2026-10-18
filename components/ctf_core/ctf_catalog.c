/* Static challenge catalogue (SPEC "Challenge catalogue", SPEC order) + hint tiers.
 * Array index = progress bit index: append only, never reorder. */
#include <string.h>

#include "ctf_core.h"

#define KIT_USB_UART "USB-UART adapter"
#define KIT_JUMPER   "jumper wire"
#define KIT_LA       "logic analyzer"

/* Hint tiers (SPEC "v0.2.0"): {1 nudge, 2 hint, 3 walkthrough}. Tier 1 names
 * no tool or technique; tier 2 names the technique and may name a tool
 * category; tier 3 walks through the solve with concrete steps and stops
 * before the flag. No tier holds a flag or a per-board value (PIN, passkey,
 * password, SSID, ports, frequency, keys, MAC-derived numbers). Plain ASCII
 * only; commands in backticks. */

static const ctf_challenge_t CATALOG[] = {
    /* BLE (radio mode) */
    {"BLE-01", "BLE", "Read the flag", CTF_EASY, NULL,
     {"The board's custom service puts several readings on display; one of them is exactly what you came for.",
      "Connect with a BLE explorer (nRF Connect, bleak, bluetoothctl) and read every characteristic in the board's custom service; one holds the flag in plain text.",
      "With `bluetoothctl`: `scan le`, `connect <addr>`, then `menu gatt`, `list-attributes` to see every characteristic in the challenge service, and `select-attribute` + `read` on each. The flag is the plaintext `ESP{...}` value; no decoding needed."}},
    {"BLE-02", "BLE", "Hex and friends", CTF_EASY, NULL,
     {"One characteristic's value looks like gibberish; it is your flag dressed up and worth undressing.",
      "The value is wrapped in layers. Peel them in reverse order: one layer only reverses the byte order, the others are two everyday text encodings (base64 and hex).",
      "Read the Scrambled Transmission characteristic's value. Work backwards: reverse the byte string, base64-decode the result, then hex-decode that to ASCII. CyberChef `Reverse` -> `From Base64` -> `From Hex`, or `bytes.fromhex(base64.b64decode(raw[::-1]).decode())` in Python, gives the flag."}},
    {"BLE-03", "BLE", "Notify me", CTF_EASY, NULL,
     {"One characteristic will not answer a plain read; it prefers to speak only once you agree to listen.",
      "Some characteristics never answer a read. Subscribe for notifications through the Client Characteristic Configuration descriptor and the flag arrives on its own.",
      "In `bluetoothctl` `menu gatt`, `select-attribute` the notify-only characteristic and run `notify on`. The board pushes the flag as a notification on subscribe and again every second. In `bleak`, `start_notify(uuid, cb)` and read it from the callback."}},
    {"BLE-04", "BLE", "Indicate and ack", CTF_MEDIUM, NULL,
     {"A talkative characteristic hands you the flag a piece at a time, and waits for a nod before sending the next piece.",
      "This one uses indications, not notifications: each fragment is only released after your client confirms the previous one. Subscribe for indications and collect every piece in order.",
      "Subscribe for indications on the Relay Station characteristic; BlueZ auto-confirms each one, which releases the next. Fragments arrive as `i/5:xxxx`, so concatenate the five payloads in index order. `bleak`'s `start_notify` handles indications transparently, so you just reassemble the pieces."}},
    {"BLE-05", "BLE", "Write to unlock", CTF_EASY, NULL,
     {"Two characteristics work as a pair: a panel with instructions, and a hatch that stays shut until you follow them.",
      "Characteristics can carry a human-readable User Description descriptor. Read the panel's description, write the value it names back to that characteristic, then read the neighbouring hatch characteristic.",
      "Read the User Description (`0x2901`) on the Airlock Panel characteristic: it names the exact token to write. Write that token to the panel (`write-value` in `bluetoothctl`, or `write_gatt_char`), then read the Airlock Hatch characteristic, which now returns the flag instead of `SEALED`."}},
    {"BLE-06", "BLE", "Descriptor hunt", CTF_MEDIUM, NULL,
     {"Not everything a characteristic knows is in the value you read; look at what hangs off it.",
      "Not every secret lives in a characteristic value. Enumerate the descriptors of each characteristic and read the one whose UUID is not a standard SIG descriptor.",
      "List the descriptors of every characteristic (`bleak`: iterate `char.descriptors`; `bluetoothctl`: `list-attributes`). The flag is in a descriptor with a custom UUID, not one of the standard `0000xxxx-0000-1000-8000-00805f9b34fb` ones, on an otherwise boring characteristic. `select-attribute` that descriptor and `read` it."}},
    {"BLE-07", "BLE", "Advertising payload", CTF_MEDIUM, NULL,
     {"You can learn something here without ever connecting; just keep watching what the board shouts to the room.",
      "No connection needed: scan passively and watch the manufacturer-specific advertising data over several seconds. It rotates through three parts, each labelled with its index.",
      "Scan without connecting and read the manufacturer data; the payload is `<n>:<part>` and rotates every two seconds. Collect parts 1, 2 and 3 and concatenate them in order. Controllers de-duplicate adverts, so restart short scans (or set BlueZ `DuplicateData`) to catch each rotation. `bleak`'s scanner callback exposes `adv.manufacturer_data`."}},
    {"BLE-08", "BLE", "Big MTU", CTF_MEDIUM, NULL,
     {"A long telemetry value scrolls off the end; make sure your client is really showing you all of it.",
      "With the default ATT MTU you only see the first chunk of a long value. Negotiate a larger MTU, or do a long/offset (Read Blob) read, to reach the end where the flag sits.",
      "Read the Telemetry characteristic: it is a couple of hundred bytes with the flag at the very end. A client that negotiates a big MTU (`bleak` does on connect) returns the whole value in one read; otherwise issue an offset read (ATT Read Blob) past byte 200. The flag is the `ESP{...}` at the tail."}},
    {"BLE-09", "BLE", "Passkey pairing", CTF_MEDIUM, NULL,
     {"One locker only opens over a properly secured connection, and the board tells you at startup what it needs to let you in.",
      "This characteristic needs an encrypted, authenticated link. Pair using passkey entry; the board prints its passkey on the serial console at boot.",
      "Read the passkey the board prints on its serial console at boot (the `ble passkey:` line). Then pair with passkey entry: in `bluetoothctl` register a `KeyboardDisplay` agent, `pair <addr>`, and type that passkey when prompted. Once bonded, read the Secure Locker characteristic, which now returns the flag over the encrypted link."}},
    {"BLE-10", "BLE", "Rate-limited PIN", CTF_HARD, NULL,
     {"A four-digit keypad guards this one; there are not many combinations, but it dislikes being rushed.",
      "Only 10,000 combinations, so script a brute force over the keypad's write characteristic, but respect the rate limit: pause after each batch of wrong tries instead of hammering.",
      "Write four ASCII digits to the Vault Keypad characteristic and read it back for status. After ten wrong tries it locks briefly and writes fail with ATT error 0x80, so sweep `0000`..`9999` in batches, sleeping about a second after every tenth try and retrying on that error. The correct PIN notifies the flag. Script it with `bleak`."}},
    {"BLE-11", "BLE", "Write-without-response sequence", CTF_HARD, NULL,
     {"A sequencer wants a short pattern played back to it, in the right order and without dawdling.",
      "Both order and timing matter: the input characteristic tells you the bytes; send each one as a write-without-response command, well under half a second apart, and watch the output characteristic. Script it.",
      "Read the Sequencer Input characteristic: it lists five one-byte values. Subscribe for notifications on the Sequencer Output, then send the five bytes to the input as write-WITHOUT-response commands under 500 ms apart (a write request is rejected and resets it). `bleak`: `write_gatt_char(uuid, bytes([b]), response=False)` in a loop. The flag is notified when the sequence completes."}},

    /* BT Classic (radio mode) */
    {"BTC-01", "BTC", "SPP console", CTF_EASY, NULL,
     {"This device speaks the older flavour of Bluetooth, and offers something that behaves like a serial terminal.",
      "This is Bluetooth Classic, not BLE. Pair with the board and open its Serial Port Profile (RFCOMM) channel in a terminal; the connect banner shows the flag.",
      "Run a BR/EDR inquiry (`bluetoothctl` `scan bredr`), pair (Just Works, no PIN), then open the SPP/RFCOMM channel. Bind it to a tty and open it in `tio`/`picocom`, or use Python `socket.AF_BLUETOOTH` (`BTPROTO_RFCOMM`) on the SDP-advertised channel. The flag is in the banner printed on connect, on the `link token:` line."}},
    {"BTC-02", "BTC", "Hidden menu", CTF_MEDIUM, NULL,
     {"The console lists its commands for you, but the welcome text hints that the list is not the whole story.",
      "The SPP shell's `help` does not list everything. Re-read the connect banner for a command it mentions but `help` omits, then run that command.",
      "Open the SPP console (see BTC-01) and run `help` to see the listed verbs. Compare that with the banner text, which refers to an old maintenance verb `help` never prints. Type that verb at the `spp>` prompt; it reports diagnostics and prints the flag on its service-token line."}},
    {"BTC-03", "BTC", "Device class clue", CTF_MEDIUM, NULL,
     {"The board gives away more about itself than its name before you ever connect; read everything an inquiry reveals.",
      "Run a Classic inquiry and inspect all of the board's advertised metadata: the full device name, its Class of Device field and its extended inquiry response (manufacturer) data. The flag body is split across them.",
      "Do a BR/EDR-only scan and read the device's properties (`bluetoothctl` `info <addr>`, or `btmon`). The name suffix after the colon, the Class of Device minor field, and the company `0xFFFF` manufacturer data each carry part of the twelve-hex flag body. Reassemble them in that order; the leading `0` nibble of the manufacturer data just marks the class slot."}},

    /* Web (net mode) */
    {"WEB-01", "WEB", "Hidden SSID", CTF_EASY, NULL,
     {"The board hosts a network you will not see in a scan list; the console knows its name, just not in plain letters.",
      "A hidden network still exists once you know its name. The serial console's `wifi` command prints the SSID in an encoding plus the password; decode the SSID, join the hidden network, then the landing page shows the flag.",
      "On the serial console run `wifi`: it prints the SSID in base32 and the WPA2 password. Decode the base32 to the real SSID (CyberChef `From Base32`, or `base32 -d`). Join the hidden network (`nmcli dev wifi connect <ssid> password <pw> hidden yes`, or `nmtui`), then browse to the board at `192.168.4.1`; the flag is on the landing page."}},
    {"WEB-02", "WEB", "View source", CTF_EASY, NULL,
     {"What the browser renders is not everything the server sent, and sites often ask crawlers to avoid their most interesting corners.",
      "Read the raw page source, not just the rendered page, for the first half; then check `/robots.txt` for a disallowed path and visit it for the second half.",
      "`curl http://192.168.4.1/` and read the HTML comment: it holds part 1 (first six hex) and says part 2 is where crawlers are told not to go. `curl .../robots.txt`, note the `Disallow:` path, and `curl` that path for part 2 (last six hex). The flag is `ESP{` + part 1 + part 2 + `}`."}},
    {"WEB-03", "WEB", "Cookie admin", CTF_EASY, NULL,
     {"There is an admin area you are not allowed into; the server decides who you are from something it handed you.",
      "Look at the cookie the site sets on you. The server trusts that cookie's value as your role, so send it back with a different value and request the admin area.",
      "Load `/`; it sets a `role=guest` cookie. Request `/admin` and you are refused. Re-send the request with the cookie changed to the admin role (`curl -b role=admin http://192.168.4.1/admin`, or edit it in `mitmproxy` or devtools). The admin page then returns the flag."}},
    {"WEB-04", "WEB", "Header check", CTF_EASY, NULL,
     {"An API is fussy about who is calling; it wants the request to introduce itself correctly, and the site tells you how.",
      "The restricted endpoint checks request headers: a specific User-Agent and a key header. Both expected values are shown on the API docs page; send them with your request.",
      "Read `/api/docs`: it names the exact User-Agent the client must use and prints the board key for the key header. Request `/api/secret` with both headers set (`xh GET http://192.168.4.1/api/secret User-Agent:<name> X-CTF-Key:<key>`, or `curl -H`). With both correct, the endpoint returns the flag; anything else gets 403."}},
    {"WEB-05", "WEB", "Weak JWT", CTF_MEDIUM, NULL,
     {"Your session token decides what you are; it is signed, but only as strongly as the secret behind it.",
      "The session is an HS256 JWT. Its signing secret is one word from the public list the site serves, so brute-force it offline, then re-sign a token claiming the admin role.",
      "Log in as guest (`POST /login user=guest`) to get the `session` JWT. Fetch `/wordlist.txt` and crack the HS256 secret offline against that token (`hashcat -m 16500`, or a short HMAC loop over the words). With the secret, forge a token whose payload sets the role to admin, sign it, and send it as `Authorization: Bearer <token>` to `/vault`."}},
    {"WEB-06", "WEB", "Ping tool", CTF_MEDIUM, NULL,
     {"A diagnostics page reads log files by name; it may not check carefully where that name points.",
      "The diagnostics form takes a filename and joins it onto a directory. Use a `../` path-traversal filename to climb out of the logs folder to the restricted file alongside it; it stays confined to the board's own filesystem.",
      "The form fetches `/diag?file=<name>` and builds a path under the logs directory. Read `boot.log` first; it mentions a restricted `secret/flag.txt`. Request `/diag?file=../secret/flag.txt` to climb one level into the secret folder: `curl 'http://192.168.4.1/diag?file=../secret/flag.txt'` returns the flag. Escaping the mount entirely (e.g. `../../etc/passwd`) is refused with 403."}},
    {"WEB-07", "WEB", "WebSocket chatter", CTF_MEDIUM, NULL,
     {"A chatty connection mostly sends noise; sit on it a while and watch for the message that does not look like the others.",
      "Connect to the `/ws` WebSocket with a client that distinguishes binary frames from text, and be patient: the flag arrives in a binary frame roughly every thirty seconds amid the text noise.",
      "Open the `/ws` endpoint with `websocat ws://192.168.4.1/ws` or Python `websockets`. Text frames (noise) arrive about once a second; keep the connection open up to about forty seconds for the binary frame, which carries the flag. Tell them apart by frame type (`isinstance(msg, bytes)` in `websockets`)."}},
    {"WEB-08", "WEB", "mDNS discovery", CTF_MEDIUM, NULL,
     {"Not every service on the board is linked from its web pages; some only announce themselves to the local network.",
      "Some services are advertised only over multicast DNS. Browse the mDNS service types on the board's network, find the one it does not link anywhere, and follow the host and port it advertises.",
      "Browse mDNS for the custom service: `avahi-browse -rt _ctf._tcp` (or Python `zeroconf`). It resolves to the board's address, a port and a TXT `path`. `curl http://192.168.4.1:<port><path>` using the advertised port and path returns the flag."}},
    {"WEB-09", "WEB", "UDP knock", CTF_HARD, NULL,
     {"A closed port can open if you approach it the right way; the console has something to say about how to knock.",
      "This is port knocking: send UDP packets to three specific ports in the right order, then connect to the TCP door it opens. The console's `wifi` command lists the ports; order matters and the window is short.",
      "Run `wifi` on the console for the three UDP knock ports (hex) and the door TCP port. Send a UDP packet to each knock port in order, each within five seconds of the last (`knock`, `ncat -u`, or a short socket loop), then connect to the door with `ncat <ip> <door>` within thirty seconds. A wrong port resets the sequence; the door serves only the IP that knocked and prints the flag."}},

    /* Serial (always) */
    {"SER-01", "SER", "Boot log", CTF_EASY, NULL,
     {"The board says a great deal the instant it powers on, and one line in that rush is what you are after.",
      "Everything printed at boot scrolls past quickly. Capture the full serial log from a reset and search it for the flag hidden among the log noise.",
      "Open the console at 115200 8N1 with a terminal that logs to a file (`tio -l out.log`, or `idf.py monitor`), press EN/RST to reboot, and capture the whole boot banner. Search the saved log for `ESP{` (`grep` the file); the flag is on a selftest line among the ordinary startup messages."}},
    {"SER-02", "SER", "Wrong baud", CTF_MEDIUM, KIT_USB_UART,
     {"The board has a second talking pin nobody wired up, and it speaks at an unusual pace.",
      "A second UART prints the flag periodically, but at a non-standard baud rate, so it looks like garbage until you match the speed. Wire a 3.3 V USB-UART adapter (or a logic analyzer) to that TX pin with shared ground.",
      "Connect an adapter's RX, or a logic analyzer probe, to the board's UART2 TX pin and share GND (see the pin map). The port emits a line every few seconds; at the wrong baud it is noise. Step a terminal through non-standard rates until the text is clean (`tio -b <rate>`), or capture and decode with `sigrok-cli -P uart:baudrate=<rate>`. The flag is on the `maint token` line."}},
    {"SER-03", "SER", "Debug login", CTF_HARD, NULL,
     {"A debug login guards a per-board password; the way it responds leaks how much of your guess is right.",
      "The `login` check compares the password character by character and takes slightly longer for each correct leading character. That is a timing side channel: measure each guess and recover the password one position at a time.",
      "Script the `login <guess>` command and time the delay from Enter to the reply. For each position, try every `[a-z0-9]` character keeping earlier ones fixed; the correct one replies measurably slower (about one extra short step). Fix it and move on until all eight are known, then `login` with the full password to print the flag. `pwntools` or `pyserial` make the timing loop easy."}},
    {"SER-04", "SER", "Escape sequence", CTF_MEDIUM, NULL,
     {"The console hides a back door that opens only for a particular key followed quickly by a short word.",
      "The console watches the raw byte stream for a control-key escape followed by a short debugging word, all within about a second. Use a terminal that can send raw control characters.",
      "Send the control character Ctrl-] (byte `0x1d`) and then the three-letter debug word immediately after, within one second, so the input watcher catches the whole sequence. `picocom` can send the control char, or script it (`write(b\"\\x1ddbg\")` with `pwntools` or `pyserial`). It opens a hidden debug monitor that prints the flag on its session-key line."}},

    /* Hardware (always) */
    {"HW-01", "HW", "Jumper it", CTF_EASY, KIT_JUMPER,
     {"At startup the board checks something physical about two of its pins; give it what it is checking for and reboot.",
      "At boot the board tests whether two specific GPIO pins are connected. Bridge them with a jumper wire (see the pin map) and press reset; the flag prints on the console.",
      "With the board powered, place a jumper wire between the two pins named for this challenge in the pin map (one is driven high, the other read as an input). Press EN/RST and watch the console: the pin check reports the bridge instead of `open` and prints the flag on the `HW-01 flag:` line. Remove the jumper afterwards."}},
    {"HW-02", "HW", "Blinky Morse", CTF_EASY, NULL,
     {"The onboard LED is not just a power light; its long and short blinks are spelling something out.",
      "The LED blinks the flag body in Morse code, on a loop. Record it (slow-motion video or a light sensor), measure the on/off durations, and decode the dots and dashes.",
      "Film the onboard LED for at least one full loop; slow motion helps. The unit is about 100 ms: dot is one unit on, dash is three. Note each on/off duration, convert to dots and dashes with the standard gap rules, and decode the Morse to the twelve-character flag body (CyberChef `From Morse Code`). A dev build's `hwdev morse` samples the pin for you."}},
    {"HW-03", "HW", "PWM frequency", CTF_MEDIUM, KIT_LA,
     {"A pin is toggling steadily at a rate unique to your board; the rate itself is the answer.",
      "Probe the PWM output pin with a logic analyzer, measure its frequency in hertz, and give that number to the `answer HW-03 <hz>` command (accepted within one percent).",
      "Hook a logic analyzer to the PWM pin and GND (see the pin map) and capture a short window. Measure the frequency in PulseView, or export samples and compute it: `sigrok-cli -d fx2lafw --config samplerate=1m --samples 1m -C D0 -O csv`, then count rising edges over the captured time. Submit with `answer HW-03 <hz>`; it accepts plus or minus one percent. A dev build's `hwdev` self-measures it."}},
    {"HW-04", "HW", "I2C chatter", CTF_MEDIUM, KIT_LA,
     {"The board is chattering to a bus device that is not actually there, and the conversation is still on the wire.",
      "A bit-banged I2C master writes the flag periodically and ignores the missing acknowledgement, so the bytes are on the bus with no slave present. Capture SDA and SCL with a logic analyzer and run an I2C decoder.",
      "Probe SDA and SCL plus GND (see the pin map) and capture at least six seconds at 500 kHz or more (the bus runs slowly, a burst every few seconds). Decode with `sigrok-cli -P i2c:scl=D0:sda=D1 -A i2c=data-write`, or PulseView's I2C decoder. Ignore that nobody ACKs; read the written data bytes as ASCII to recover the flag."}},
    {"HW-05", "HW", "SPI dump", CTF_MEDIUM, KIT_LA,
     {"Something is clocked out of a few pins every several seconds; capture it and read it back.",
      "A bit-banged SPI master (mode 0) sends the flag periodically. Capture the clock, the data-out line and chip-select with a logic analyzer and decode as SPI.",
      "Probe SCK, MOSI and CS (active low) plus GND per the pin map and capture at least eleven seconds at about 1 MHz (a burst every several seconds). Decode with `sigrok-cli -P spi:clk=D0:mosi=D1:cs=D2:cpol=0:cpha=0 -A spi=mosi-data`, or PulseView's SPI decoder (mode 0, MSB first). Read the MOSI bytes of one CS-framed transfer as ASCII for the flag."}},
    {"HW-06", "HW", "Touch pad code", CTF_MEDIUM, NULL,
     {"Four bare pins act as a keypad; the console gives you a clue to the code it wants, in order.",
      "The four touch pads form a keypad. The `keypad` console command gives a numeric clue that encodes the sequence; touch the pads in that order, without long pauses between touches.",
      "Run `keypad` on the console: it prints a combo number to read in base 4 as six digits, mapping 0 to 3 onto the four pads (listed in the pin map). Touch the bare pins in that order, lifting your finger between taps (a repeated digit needs two separate presses) and under about ten seconds apart. When the sequence matches, the console prints the flag. Do not touch the pads while the board boots."}},

    /* Firmware reversing (always) */
    {"RE-01", "RE", "Strings in flash", CTF_EASY, NULL,
     {"Not everything stored in the board's flash is program code; some of it is just text waiting to be read.",
      "Dump the board's flash over USB and look for human-readable strings. The flag is in plain text in a small raw data partition, not in the application image.",
      "Close your serial terminal, then dump flash with `esptool --chip esp32 -p <port> read-flash 0 0x400000 flash.bin` (or just the small `notes` data partition, whose offset comes from the partition table at `0x8000`). Run `strings` over it; the operator notes include the flag on the maintenance-token line. Reading flash is safe; do not write or erase."}},
    {"RE-02", "RE", "NVS secrets", CTF_MEDIUM, NULL,
     {"The firmware keeps a few values in its key-value store, and one of them is only lightly disguised.",
      "Dump the NVS partition and parse its entries with ESP-IDF's NVS tool. The value you want is a blob masked with a single repeating XOR byte; flags start with a known prefix, which gives you that byte.",
      "Dump the `nvs` partition (offset from the partition table at `0x8000`) and parse it with `nvs_tool.py -f json -d minimal nvs.bin`. In namespace `vault`, key `k` is a short blob. Because the plaintext starts with `ESP{`, XOR the first blob byte with `E` to recover the single mask byte, then XOR every byte with it to get the flag."}},
    {"RE-03", "RE", "Crackme", CTF_HARD, NULL,
     {"The console has an `unlock` command you do not have the key for; the check that validates the key can be run in reverse.",
      "Dump the factory app and load it in a disassembler with Xtensa support. Find the `unlock` command handler, understand the small byte routine it runs on your key, and invert it using the per-board target bytes stored in NVS.",
      "Dump the factory app partition (offsets from the table at `0x8000`) and load it into Ghidra 11+ as Xtensa, recreating the segment memory map from `esptool image-info`. Find the `unlock` handler via the `Usage: unlock <key>` string xref: it reads a blob from NVS `vault`, runs a short invertible byte routine on your input and compares. Read that blob with `nvs_tool.py`, invert the routine byte by byte to get the key, then run `unlock <key>` for the flag."}},
    {"RE-04", "RE", "XOR'd asset", CTF_HARD, NULL,
     {"There is a binary blob in the board's filesystem that is not readable as-is; the board itself holds what unlocks it.",
      "The filesystem blob is XORed with a keystream from a simple generator in the firmware. Reverse the generator in a disassembler; its seed comes from a value you can read off your own board.",
      "Dump the `storage` (SPIFFS) partition and find the `XBLOB1` magic; the bytes after it are the masked flag. In Ghidra, follow the xref to the `/storage/blob.bin` string to the writer: it builds a seed from the board MAC and clocks a shift-and-XOR generator (an LFSR), one keystream byte per flag byte. Re-implement that generator with your board's MAC (printed in the boot banner) and XOR it against the blob."}},

    /* Crypto (always, console) */
    {"CRY-01", "CRY", "Classic cipher", CTF_EASY, NULL,
     {"An old-school cipher hides the flag on the console, but its key is scattered in pieces across the other tracks.",
      "The `cipher` command shows a Vigenere-encrypted flag body. Its key is four two-letter shards; gather all four from the other tracks, then decrypt (letters shift back, digits pass straight through).",
      "Collect the four `cipher shard i/4: XY` pieces shown by the other tracks: shard 1 in the serial boot output, shard 2 on a readable BLE characteristic, shard 3 in the BT Classic SPP banner, shard 4 in the web landing page footer. Join them into the eight-letter key and Vigenere-decrypt the body from `cipher` (CyberChef `Vigenere Decode`, or a short script); digits are unchanged and do not advance the key."}},
    {"CRY-02", "CRY", "ECB penguin", CTF_HARD, NULL,
     {"An oracle will encrypt whatever you hand it, together with the secret you want; its block structure gives the secret away.",
      "ECB encrypts identical plaintext blocks identically. Use byte-at-a-time ECB decryption: align input so one unknown byte sits at a block's end, then match that block against ones you build from your own guesses. Script it.",
      "`oracle <hex>` returns AES-128-ECB of (your input || secret). Confirm 16-byte ECB by sending repeated blocks. Then pad input to `15 - (i mod 16)` bytes so the next unknown byte lands last in its block, and compare that block with ones built from `known + guess` over all candidate bytes. Recover the secret one byte at a time, extending `known`, until the whole flag appears. `pwntools` plus `pycryptodome` drive the loop."}},
    {"CRY-03", "CRY", "Reused nonce", CTF_MEDIUM, NULL,
     {"Two encrypted messages were produced carelessly in a way that lets one give up the other.",
      "Both AES-CTR messages reuse the same nonce, so they share one keystream. XOR the two ciphertexts together and combine with the plaintext you already know to recover the other message.",
      "`msgs` prints two AES-CTR ciphertexts that reuse a nonce, plus the known plaintext of message 1. Since `C1 xor P1` is the keystream, compute `P2 = C2 xor C1 xor P1` byte by byte over the overlapping length. The flag is in the recovered message 2; a few lines of Python, or XOR tooling, is enough."}},
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
