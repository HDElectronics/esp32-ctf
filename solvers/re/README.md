# RE track solvers (RE-01..04) — spoilers

Reference solvers that recover each flag the way a player would, then submit it
on the console (`submit`) and expect `Correct!` or `Already solved`.

| Challenge | Solver | Player technique |
|-----------|--------|------------------|
| RE-01 Strings in flash | `re01_strings.py` | dump `notes` partition, `strings` |
| RE-02 NVS secrets | `re02_nvs.py` | dump `nvs`, `nvs_tool.py`, single-byte XOR (known `ESP{` prefix) |
| RE-03 Crackme | `re03_crackme.py` | Ghidra on the factory app, invert the key routine, `vault/chk` from NVS, `unlock <key>` |
| RE-04 XOR'd asset | `re04_blob.py` | dump `storage`, find `XBLOB1`, re-implement the LFSR from the firmware, MAC from the banner |

## Running

Use the ESP-IDF Python environment (it has `esptool`, `pyserial` and
`nvs_tool.py`):

```sh
. ~/esp/esp-idf/export.sh
python solvers/re/re01_strings.py --port /dev/ttyACM0
```

Each solver reads the partition table from flash offset `0x8000`, parses it,
and dumps only the partition it needs with `esptool read-flash` (RE-04 reads
the whole ~1.4 MB `storage` partition, about 20 s at 921600 baud). Options:

- `--image flash.bin` works from an existing full dump
  (`esptool read-flash 0 0x400000 flash.bin`); the board is still needed to submit.
- `--out DIR` keeps the partition dumps; `--baud` sets the read-flash baud rate.
- `re04_blob.py --mac aa:bb:cc:dd:ee:ff` skips reading the MAC from the banner.

In the dev setup the board is shared, so wrap each run in the board lock
(`flock <lockfile> python solvers/re/...`).

## Getting the app into Ghidra (RE-03, RE-04)

Ghidra 11+ ships an Xtensa processor module (`Xtensa:LE:32:default`). An ESP32
app image is not an ELF: it is a 24-byte header followed by segments, each
`{u32 load_addr, u32 length, data}`, which the ROM bootloader copies or maps to
fixed addresses. You have to recreate that memory layout in Ghidra.

### 1. Dump the app

```sh
esptool read-flash 0x8000 0xc00 pt.bin
python $IDF_PATH/components/partition_table/gen_esp32part.py pt.bin   # prints the table
esptool read-flash 0x10000 0x280000 factory.bin                       # factory offset/size from the table
```

### 2. List the segments

```sh
esptool --chip esp32 image-info factory.bin
```

Example output (addresses differ per build):

```
Segment   Length   Load addr   File offs  Memory types
      0  0x0e8d8  0x3f400020  0x00000018  DROM      <- flash-mapped rodata (strings, consts)
      1  0x01718  0x3ffbdb60  0x0000e8f8  DRAM      <- initialised .data
      2  0x1ef74  0x400d0020  0x00010018  IROM      <- flash-mapped code (most app code)
      3  0x0285c  0x3ffbf278  0x0002ef94  DRAM
      4  0x0cd20  0x40080000  0x000317f8  IRAM      <- code copied to internal RAM
      5  0x00028  0x50000000  0x0003e520  RTC_DATA
```

`File offs` is where the segment's 8-byte header (`load_addr`, `length`)
starts inside `factory.bin`; the segment's data starts at **`File offs` + 8**
(e.g. DROM data at `0x20`, IROM data at `0x10020`).

### 3a. Import manually (always works)

1. *File → Import File* → `factory.bin`, Format **Raw Binary**, Language
   **Xtensa:LE:32:default**. Do not auto-analyze yet.
2. *Window → Memory Map*: delete the default `ram` block that maps the whole
   file at 0.
3. For every segment, click **+** (Add Memory Block): name it (`drom0`,
   `iram0`, …), Start Addr = load address, Length = segment length, Block Type
   Default, **Initialized from File Bytes** `factory.bin`, File Offset = `File
   offs` + 8. Permissions: IROM/IRAM = R-X, DROM = R, DRAM/RTC = RW.
4. Optional: add an uninitialised RW block for the rest of DRAM
   (`0x3ffae000`–`0x3fffffff`) so pointers into BSS/heap resolve.
5. *Analysis → Auto Analyze* with defaults. Then go to the entry point
   (`Entry point:` from image-info, in IRAM) and press `D` if nothing was
   disassembled there.

Xtensa windowed-ABI functions start with `entry a1, N` (bytes `36 x1 00`).
If analysis misses code, *Search → Memory* for that pattern in IROM and
disassemble (`D`) / create functions (`F`) at the hits. Calls into the mask ROM
(`0x4000xxxx`) stay unresolved; that is fine for this challenge (the ROM ELFs in
`~/.espressif/tools/esp-rom-elfs/` can be imported as extra blocks if you want
names for them).

### 3b. Convert to ELF (optional shortcut)

`esp32_image_parser` (github.com/tenable/esp32_image_parser, community tool)
turns a **full flash dump** into an ELF with the segments already placed:

```sh
esptool read-flash 0 0x400000 flash.bin
python3 esp32_image_parser.py create_elf flash.bin -partition factory -output factory.elf
```

Import `factory.elf` (Ghidra detects Xtensa from the ELF header) and analyze.
The tool is not maintained by Espressif; if it chokes on a newer image, use 3a.

### 4. Finding the RE-03 key check

1. *Search → For Strings*, filter `unlock`. You get the command name
   `"unlock"`, its help text and `"Usage: unlock <key>"`.
2. *References → Show References to* `"Usage: unlock <key>"`: the only
   reference is inside the command handler. (The `"unlock"` name itself is
   referenced from the registration code, which also loads the handler's
   address from the same literal pool, `l32r`.)
3. In the decompiled handler: `nvs_open("vault", …)`, `nvs_get_blob(…,
   "chk", buf, &len)` with `len == 12`, `strlen(arg) == 12`, then a call to a
   small unnamed function `f(arg, out)`, then a loop OR-ing `out[i] ^ chk[i]`;
   zero prints the flag.
4. Open `f`: a 12-iteration loop with an 8-bit rolling value. Retype the
   parameters as `uint8_t *` and the locals as `uint8_t`; the rotate shows up as
   a `<<` and a `>>` of the same byte combined with `|` (on Xtensa `ssl`/`sll`,
   `ssr`/`srl`). Write each step down, then run them backwards per byte
   (subtract, rotate right, XOR). The rolling value is updated from the
   *output* byte, so the inverse can recompute it from `chk` alone.
5. Read `vault`/`chk` from the NVS dump (`nvs_tool.py -f json -d minimal
   nvs.bin`, blob data is base64), invert, run `unlock <key>`.

### RE-04 in the same project

Search strings for `/storage/blob.bin` and follow the reference to the code
that writes it. It reads the board MAC (the same one the boot banner prints),
builds a 32-bit seed from it, and clocks a shift-and-XOR loop (a Galois LFSR:
the XOR mask constant is applied when the bit shifted out is 1) to produce one
keystream byte per flag byte. The file starts with the 6-byte `XBLOB1` magic.
