# WEB track (Wi-Fi and web)

9 challenges, 1500 points. Net mode.

## Reaching the track

1. On the serial console: `mode net`. The board reboots with Bluetooth off and
   starts its own Wi-Fi access point. (`mode radio` brings Bluetooth back;
   progress is kept.)
2. Finding and joining that access point is the first challenge, WEB-01. You
   need a laptop with Wi-Fi on the 2.4 GHz band; the board's network is
   isolated and has no internet.
3. Once you are on the board's network, the board is the gateway (normally
   `192.168.4.1`) and serves HTTP on port 80.

While you are on the board's network your laptop is off its usual Wi-Fi. A
second adapter, or a phone hotspot over USB for your other traffic, helps.

### Submitting on the web

- `/score`: current score
- `/submit`: form that accepts any challenge's flag

## Challenges

### WEB-01 Hidden SSID (100)
The board runs its own access point. You won't find it in your network list.
Tools: `nmtui`, `nmcli`

### WEB-02 View source (100)
What a browser shows you is not everything the server sent.
Tools: `curl`, `posting`

### WEB-03 Cookie admin (100)
There is an admin area. You are not an admin. Yet.
Tools: `curl`, `mitmproxy`

### WEB-04 Header check (100)
An API that is picky about who it talks to.
Tools: `xh` / `httpie`, `posting`

### WEB-05 Weak JWT (200)
You can log in as a guest. The session token decides what you are.
Tools: `jwt-cli`, `hashcat`

### WEB-06 Ping tool (200)
A diagnostics page for reading log files. Only log files, surely.
Tools: `curl`, `mitmproxy`

### WEB-07 WebSocket chatter (200)
A chatty WebSocket. Most of it is noise.
Tools: `websocat`, Python `websockets`

### WEB-08 mDNS discovery (200)
Not every service on the board is linked from its web pages.
Tools: `avahi-browse`, `curl`

### WEB-09 UDP knock (300)
A door that is closed until you knock the right way. The console has something to say about it.
Tools: `knock` / `ncat`, `nmap` (the board's IP only)
