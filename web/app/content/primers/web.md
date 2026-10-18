# Wi-Fi and web in three minutes

Websites, phone apps and smart TVs rest on the same building blocks: a Wi-Fi network to join, an address to reach, and HTTP to ask for pages. In net mode the board runs its own small Wi-Fi network and web server, with no internet behind it. Run `mode net` on the console to get there; the board reboots with Bluetooth off.

## How it works

An **access point** announces its network in short broadcasts that carry the network's name, the **SSID**. Your network list is built from those. A hidden network leaves its name out, so you have to know the name to join.

While your laptop is on the board's network, it is off your usual Wi-Fi and has no internet. A second Wi-Fi adapter or a phone sharing its connection over USB keeps you online; or join the board's network from a phone instead.

On the network, every service lives at an **IP address** and a **port**. The board is the gateway, normally `192.168.4.1`, with its web server on port 80. **TCP** ports carry a connection: both sides say hello, then exchange a reliable stream. **UDP** ports take single packets with no connection and no guarantee.

**HTTP** is requests and responses. A request has a method (`GET` to fetch, `POST` to send a form), a path such as `/index.html`, and **headers**: `Name: value` lines that describe it. The server answers with a status code (`200` OK, `403` forbidden, `404` not found), its own headers and a body. A browser shows you the rendered result; the raw response can hold more.

HTTP forgets you between requests, so sites keep state in **cookies**: small values your browser sends back every time. Others hand you a signed **token**, often a **JWT**: three dot-separated parts, a header, a payload of claims such as your user name, and a signature. The first two are only base64-encoded, so anyone can read them; the signature is what the server checks.

A **WebSocket** starts as an HTTP request, then stays open so both sides can send messages at any time. **mDNS** lets devices announce names ending in `.local`, and the services they run, without a DNS server.

## Words you'll meet

**SSID**: the name of a Wi-Fi network.

**Port**: a number that picks one service on a host.

**Header**: a `Name: value` line sent with an HTTP request or response.

**Cookie**: a value your browser stores and sends back on every request.

**JWT**: a JSON web token, three base64 parts joined by dots, signed by the server.

**WebSocket**: a long-lived two-way message channel.

**mDNS**: name and service announcements on the local network.

## Get set up

**nmcli / nmtui** (join networks): `sudo apt install network-manager`. Look around with `nmcli device wifi list`; `nmtui` has a menu for joining a network by name.

**curl** (see the raw HTTP): `sudo apt install curl`. Once on the board's network:

```sh
curl -i http://192.168.4.1/
```

`-i` prints the response headers; `-v` also shows what you sent.

**posting** (a terminal app for building HTTP requests): `pipx install posting`, then run `posting`.

## Where to start

Start with **WEB-01 Hidden SSID**. It won't show up in your network list, so first find out what joining a hidden network takes.
