# Crypto in three minutes

Cryptography keeps messages secret and proves they weren't changed. It protects your banking app and every `https://` page you open. Strong ciphers almost never break; what breaks is how people use them. This track runs on the serial console in both modes: `help` lists its commands, and its flags may come as the bare 12-character body, which `submit` accepts.

## How it works

**Encoding is not encryption.** Hex and base64 only change how bytes are written down, and anyone can undo them without a key. Learn to recognise them: hex is pairs of `0-9a-f`, base64 is letters, digits, `+` and `/`, often ending in `=`.

**Classic ciphers** work on letters. A Caesar cipher shifts every letter by the same amount, so `A` becomes `D`. Others swap each letter for another from a scrambled alphabet, or change the shift from letter to letter following a keyword, as Vigenère does. They are fun to break by hand, and the key is often the whole puzzle.

**XOR** is the basic move of modern ciphers. It compares two bits and gives 1 when they differ. Its key property: XOR the same value twice and you are back where you started, `(a XOR k) XOR k = a`.

**Block ciphers** such as AES encrypt fixed-size blocks, 16 bytes for AES. Longer messages need a **mode** that says how the blocks are chained. The simplest, **ECB**, encrypts every block on its own with the same key. That leaks patterns: two identical plaintext blocks give two identical ciphertext blocks. Encrypt a picture of a penguin in ECB and you can still see the penguin.

**Stream ciphers** and AES in **CTR** mode work differently. They turn the key and a **nonce** (a number used once) into a long stream of pseudo-random bytes, the **keystream**, and XOR it with the message. This is safe only while every message gets a fresh nonce. Reuse one, and two messages share the same keystream: XOR the two ciphertexts together and the keystream cancels out, leaving the two plaintexts XORed with each other.

An **oracle** is any service that will encrypt or decrypt for you on request, with a key you never see.

## Words you'll meet

**Plaintext / ciphertext**: the message before and after encryption.

**Key**: the secret that controls a cipher.

**XOR**: bit-by-bit "differ" operation; doing it twice with the same value undoes it.

**Block**: the fixed chunk a block cipher works on, 16 bytes for AES.

**ECB**: a mode that encrypts each block independently.

**Nonce**: a value that must never be used twice with the same key.

**Keystream**: the pseudo-random bytes a stream cipher XORs with the message.

## Get set up

**CyberChef** (in the browser, no install): open gchq.github.io/CyberChef and drag in operations such as "From Hex", "From Base64" or "XOR".

**pycryptodome** (Python crypto library): `pip install pycryptodome` in a virtual environment. A first check:

```sh
python3 -c "from Crypto.Cipher import AES; print(AES.block_size)"
```

**pwntools** (talk to the console from a script): `pip install pwntools`. Close other serial programs first; only one can hold the port.

## Where to start

Start with **CRY-01 Classic cipher**. Run `cipher` on the console and read what it says; the key is scattered across the CTF, so collect its pieces as you play the other tracks.
