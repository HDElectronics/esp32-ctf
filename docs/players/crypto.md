# CRY track (Crypto)

3 challenges, 600 points. Always on (both modes).

## Reaching the track

Everything happens on the serial console (see [serial.md](serial.md#connecting)).
`help` lists the crypto commands: `cipher`, `oracle` and `msgs`.
Flags in this track may come as the bare 12-character body; `submit`
accepts that.

## Challenges

### CRY-01 Classic cipher (100)
An old-school cipher, and a key that is scattered across the CTF. You will need to visit other tracks.
Tools: CyberChef, Python

### CRY-02 ECB penguin (300)
An encryption oracle that will happily encrypt whatever you give it, along with something you want. Needs scripting.
Tools: `pwntools`, Python `pycryptodome`

### CRY-03 Reused nonce (200)
Two encrypted messages. One of them you can already guess.
Tools: Python, `xortool`
