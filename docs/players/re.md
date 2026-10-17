# RE track (Firmware reversing)

4 challenges, 900 points. Always on (both modes).

## Reaching the track

The material for this track is the board's own flash and firmware. You read
it over the same USB port as the console (close your serial terminal first,
the port can only be open once):

```sh
pipx install esptool
esptool --chip esp32 -p /dev/ttyUSB0 read-flash 0 0x400000 flash.bin   # full 4 MB dump
```

esptool puts the board into its ROM bootloader, reads, then resets it back
into the CTF. Reading is always safe. **Don't** `write-flash` or
`erase-flash` while playing: even re-flashing the release image wipes your
progress (this track's artefacts come back on the next boot, your score does
not).

The partition table lives at offset `0x8000`; the boot log prints it too.
ESP-IDF's `parttool.py` and `gen_esp32part.py` read it.

Ghidra 11+ supports the ESP32's Xtensa CPU natively. An ESP32 app image is not
an ELF: it is a header plus segments that load at fixed addresses
(`esptool --chip esp32 image-info <app.bin>` lists them), so plan to set up the
memory map yourself or convert the image first.

## Challenges

### RE-01 Strings in flash (100)
Not everything in flash is code.
Tools: `esptool read-flash`, `strings`

### RE-02 NVS secrets (200)
The firmware keeps a few things in its key-value store, and one of them is not quite in the clear.
Tools: `nvs_tool.py`, `xortool`

### RE-03 Crackme (300)
The console has an `unlock` command. You don't have the key.
Tools: Ghidra 11+, `radare2` / `rizin`

### RE-04 XOR'd asset (300)
There is a binary blob in the board's filesystem. It isn't readable as is.
Tools: Ghidra 11+, `hexyl`
