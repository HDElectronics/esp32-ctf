# Firmware reversing in three minutes

Firmware is the software baked into a device, from your router to the board in front of you. Reversing it means reading a device's memory and working out what the program does and keeps, without the source code. Everything in this track comes from the board's own flash chip, read over the same USB cable as the console. It works in both modes.

## How it works

The ESP32 stores everything in a 4 MB **flash** chip. Flash is not one big file; it is cut into regions at fixed offsets. The **bootloader** sits near the start, and the **partition table** at offset `0x8000` says where everything else lives: the main **app** (the program itself) and **data partitions** for settings, raw data or a small filesystem. The boot log prints the same table.

One data partition is usually **NVS** (non-volatile storage), a key-value store. Programs save small settings in it, such as a Wi-Fi password or a counter, as named keys grouped into **namespaces**. It is not a plain text file: entries sit in pages with headers, so a parser that knows the format makes it much easier to read.

Programs are full of text: messages, menu entries, format strings. It is stored as plain bytes, so you can find it by searching for runs of readable characters. That is what the `strings` tool does.

The code itself is machine instructions for the ESP32's CPU, an **Xtensa** core. A **disassembler** turns those bytes back into assembly; a **decompiler** goes further and shows C-like code with functions, loops and comparisons. An ESP32 app image is not an ELF file: it is a header plus segments that load at fixed addresses, so you set up that memory map in the tool, or convert the image first.

Reading flash is always safe. Writing is not: **don't** `write-flash` or `erase-flash` while playing, because even re-flashing the release image wipes your progress.

Only one program can hold the serial port at a time. Close your terminal or the player app before running esptool.

## Words you'll meet

**Flash**: the chip that keeps firmware and data when the power is off.

**Partition**: a named region of flash with a fixed offset and size.

**NVS**: the ESP32's key-value store for settings, kept in its own partition.

**Offset**: a position in flash, counted in bytes from the start, usually in hex.

**Disassembler**: a tool that turns machine code back into assembly instructions.

**Decompiler**: a tool that rebuilds C-like code from machine code.

**Xtensa**: the CPU architecture inside the classic ESP32.

## Get set up

**esptool** (reads the flash): `pipx install esptool`. A full 4 MB dump:

```sh
esptool --chip esp32 -p /dev/ttyUSB0 read-flash 0 0x400000 flash.bin
```

It puts the board into its bootloader, reads, then resets it back into the CTF. `esptool --chip esp32 image-info <app.bin>` lists an app image's segments.

**strings** and **hexyl** (look inside binaries): `sudo apt install binutils hexyl`. Try them on any program first, such as `strings /bin/ls | head` or `hexyl /bin/ls | head`.

**Ghidra 11+** (disassembler and decompiler, supports Xtensa): download from its GitHub releases page; it needs a JDK 21.

## Where to start

Start with **RE-01 Strings in flash**. Make a dump, then remember that not everything in flash is code.
