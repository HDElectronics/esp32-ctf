#!/usr/bin/env python3
"""Build the player app's content (SPEC "Player app — offline guide and scoreboard").

Writes two generated files into web/app/content/ (do not edit them by hand):

challenges.json
    Spoiler-free briefs and tools, parsed from docs/players/<track>.md sections:

        ### BLE-03 Notify me (100)[ · Kit: ...]
        <brief, one or more lines>
        Tools: `bluetoothctl`, Python `bleak`

    as {id: {"brief": str, "tools": [str]}}.

board-data.json
    What the page needs to check flags and run the points wallet offline,
    taken from the firmware sources so the firmware stays the single source:
    - the flag key K = KEY_A ^ KEY_B (components/ctf_core/ctf_core.c),
    - start points (CTF_START_POINTS, ctf_core.h),
    - the catalogue in SPEC order: id, track, name, value, kit, board mode,
      hint prices and the three hint texts (components/ctf_core/ctf_catalog.c),
    - answer gates (HW-03 PWM frequency, components/track_hw/track_hw.c).

Usage: scripts/build-app-content.py [--check]
  --check  exit 1 if a committed JSON file is out of date (writes nothing)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "players"
CONTENT = ROOT / "web" / "app" / "content"
OUT_CHALLENGES = CONTENT / "challenges.json"
OUT_BOARD = CONTENT / "board-data.json"
CORE_C = ROOT / "components" / "ctf_core" / "ctf_core.c"
CORE_H = ROOT / "components" / "ctf_core" / "include" / "ctf_core.h"
CATALOG_C = ROOT / "components" / "ctf_core" / "ctf_catalog.c"
HW_C = ROOT / "components" / "track_hw" / "track_hw.c"

HEAD = re.compile(r"^### ([A-Z]+-\d{2}) .+ \((\d+)\)(?: · Kit: .+)?$")
LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def fail(msg):
    sys.exit(f"error: {msg}")


def rel(path):
    return path.relative_to(ROOT)


# ---------------------------------------------------------------- challenges.json

def plain(text):
    """Markdown inline -> plain text: links to their label, no backticks."""
    text = LINK.sub(r"\1", text)
    return text.replace("`", "").strip()


def brief_line(line):
    # Drop pointers into other guides ("(see hw.md)"): the app has no such page.
    line = re.sub(r"\s*\(see [^)]*\.md[^)]*\)", "", LINK.sub(r"\1", line))
    return plain(line)


def split_tools(raw):
    """Tools line -> list of short names, in the guide's order."""
    raw = re.sub(r"\bwith an analyzer:\s*", "", raw)
    tools = []
    for part in re.split(r";\s*|,\s*(?![^()]*\))", raw):
        for item in re.split(r"\s+or\s+(?![^()]*\))", part):
            item = item.strip()
            # "Python `bleak`" -> "bleak"; plain "Python" stays.
            item = re.sub(r"^Python\s+(?=`)", "", item)
            item = plain(item)
            if item:
                tools.append(item)
    return tools


def parse_guide(path):
    out = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        m = HEAD.match(lines[i].strip())
        if not m:
            i += 1
            continue
        cid = m.group(1)
        brief, tools = [], []
        i += 1
        while i < len(lines) and not lines[i].startswith("#"):
            line = lines[i].strip()
            i += 1
            if line.startswith("Tools:"):
                tools = split_tools(line[len("Tools:"):])
                break
            if line:
                brief.append(brief_line(line))
        if cid in out:
            fail(f"{cid} appears twice ({path.name})")
        if not brief or not tools:
            fail(f"{cid} in {path.name} has no brief or no Tools: line")
        out[cid] = {"brief": " ".join(brief), "tools": tools}
    return out


def build_challenges():
    data = {}
    for path in sorted(DOCS.glob("*.md")):
        for cid, entry in parse_guide(path).items():
            if cid in data:
                fail(f"{cid} appears in two guides")
            data[cid] = entry
    if len(data) != 40:
        fail(f"expected 40 challenges in docs/players, found {len(data)}")
    return data


# ---------------------------------------------------------------- C source parsing

def strip_comments(src):
    """Remove /* */ and // comments, leaving string literals intact."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == '"' or c == "'":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            out.append(src[i:j + 1])
            i = j + 1
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            if j < 0:
                fail("unterminated comment")
            out.append(" ")
            i = j + 2
        elif src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        else:
            out.append(c)
            i += 1
    return "".join(out)


SIMPLE_ESC = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'", "?": "?",
              "a": "\a", "b": "\b", "f": "\f", "v": "\v"}


def c_unescape(body, where):
    """Decode the escapes of one C string literal body (no surrounding quotes)."""
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        e = body[i + 1] if i + 1 < len(body) else ""
        if e in SIMPLE_ESC:
            out.append(SIMPLE_ESC[e])
            i += 2
        elif e == "x":
            m = re.match(r"[0-9a-fA-F]+", body[i + 2:])
            if not m:
                fail(f"bad \\x escape in {where}")
            out.append(chr(int(m.group(0), 16)))
            i += 2 + len(m.group(0))
        elif e in "01234567":
            m = re.match(r"[0-7]{1,3}", body[i + 1:])
            out.append(chr(int(m.group(0), 8)))
            i += 1 + len(m.group(0))
        else:
            fail(f"unsupported escape \\{e} in {where}")
    return "".join(out)


TOKEN = re.compile(r'\s*(?:("(?:[^"\\\n]|\\.)*")|([A-Za-z_]\w*)|(-?\d+)|([{},]))', re.S)


def tokenize(src, where):
    """C initializer -> tokens: ('str', text) with adjacent literals joined,
    ('id', name), ('num', int), ('p', '{'|'}'|',')."""
    toks, i = [], 0
    src = src.rstrip()
    while i < len(src):
        m = TOKEN.match(src, i)
        if not m or m.end() == i:
            fail(f"cannot parse {where} near: {src[i:i + 40]!r}")
        i = m.end()
        s, ident, num, punct = m.groups()
        if s is not None:
            text = c_unescape(s[1:-1], where)
            if toks and toks[-1][0] == "str":  # "a" "b" -> "ab"
                toks[-1] = ("str", toks[-1][1] + text)
            else:
                toks.append(("str", text))
        elif ident is not None:
            toks.append(("id", ident))
        elif num is not None:
            toks.append(("num", int(num)))
        else:
            toks.append(("p", punct))
    return toks


def parse_tree(toks, where):
    """Tokens of `{ ... }` -> nested Python lists (trailing commas allowed)."""
    pos = 0

    def value():
        nonlocal pos
        kind, v = toks[pos]
        if kind == "p" and v == "{":
            pos += 1
            items = []
            while True:
                if toks[pos] == ("p", "}"):
                    pos += 1
                    return items
                items.append(value())
                if toks[pos] == ("p", ","):
                    pos += 1
                elif toks[pos] != ("p", "}"):
                    fail(f"expected , or }} in {where}, got {toks[pos]}")
        pos += 1
        if kind == "p":
            fail(f"unexpected {v!r} in {where}")
        return (kind, v)

    tree = value()
    if pos != len(toks):
        fail(f"trailing tokens in {where}")
    return tree


def c_defines(src):
    """#define NAME "literal" or #define NAME number."""
    out = {}
    for m in re.finditer(r'^#define\s+(\w+)\s+("(?:[^"\\]|\\.)*"|\d+)(?=\s|$)', src, re.M):
        raw = m.group(2)
        out[m.group(1)] = ("str", c_unescape(raw[1:-1], m.group(1))) if raw.startswith('"') else ("num", int(raw))
    return out


def parse_key():
    src = strip_comments(CORE_C.read_text(encoding="utf-8"))
    parts = {}
    for name in ("KEY_A", "KEY_B"):
        m = re.search(rf"static const uint8_t {name}\[32\]\s*=\s*\{{([^}}]*)\}};", src)
        if not m:
            fail(f"{name}[32] not found in {rel(CORE_C)}")
        vals = [int(v, 16) for v in re.findall(r"0x([0-9a-fA-F]{2})\b", m.group(1))]
        if len(vals) != 32:
            fail(f"{name} in {rel(CORE_C)} has {len(vals)} bytes, expected 32")
        parts[name] = vals
    if not re.search(r"k\[i\]\s*=\s*\(uint8_t\)\(a\[i\]\s*\^\s*b\[i\]\)", src):
        fail(f"key recombination K = A ^ B not found in {rel(CORE_C)}")
    return bytes(a ^ b for a, b in zip(parts["KEY_A"], parts["KEY_B"]))


def parse_core_header():
    defs = c_defines(strip_comments(CORE_H.read_text(encoding="utf-8")))
    for name in ("CTF_START_POINTS", "CTF_HINT_TIERS"):
        if name not in defs or defs[name][0] != "num":
            fail(f"{name} not found in {rel(CORE_H)}")
    if defs["CTF_HINT_TIERS"][1] != 3:
        fail("the app expects 3 hint tiers")
    return defs["CTF_START_POINTS"][1]


LEVELS = {"CTF_EASY": 100, "CTF_MEDIUM": 200, "CTF_HARD": 300}


def mode_of(track):
    # Same rule as mode_of() in components/ctf_platform/ctf_api.c.
    return "radio" if track in ("BLE", "BTC") else "net" if track == "WEB" else "any"


def hint_prices(value):
    # Same integer rule as price_of() in ctf_core.c: round half up.
    return [0, (2 * value + 5) // 10, (value + 1) // 2]


def parse_catalog():
    raw = CATALOG_C.read_text(encoding="utf-8")
    src = strip_comments(raw)
    defs = c_defines(src)
    m = re.search(r"static const ctf_challenge_t CATALOG\[\]\s*=\s*(\{.*?\n\});", src, re.S)
    if not m:
        fail(f"CATALOG[] not found in {rel(CATALOG_C)}")
    tree = parse_tree(tokenize(m.group(1), rel(CATALOG_C)), rel(CATALOG_C))

    def scalar(tok, what, cid):
        kind, v = tok
        if kind == "id" and v in defs:
            kind, v = defs[v]
        if kind == "id" and v == "NULL":
            return None
        if kind != "str":
            fail(f"{cid}: {what} is not a string ({tok})")
        return v

    out = []
    for entry in tree:
        if not isinstance(entry, list) or len(entry) != 6 or not isinstance(entry[5], list):
            fail(f"catalogue entry has an unexpected shape: {entry!r:.80}")
        cid = scalar(entry[0], "id", "?")
        track = scalar(entry[1], "track", cid)
        name = scalar(entry[2], "name", cid)
        level = entry[3]
        if level[0] != "id" or level[1] not in LEVELS:
            fail(f"{cid}: unknown level {level}")
        kit = scalar(entry[4], "kit", cid)
        hints = [scalar(h, "hint", cid) for h in entry[5]]
        if len(hints) != 3 or not all(hints):
            fail(f"{cid}: expected 3 non-empty hint texts")
        if not re.fullmatch(r"[A-Z]+-\d{2}", cid or "") or not cid.startswith(track + "-"):
            fail(f"{cid}: bad id or track {track}")
        value = LEVELS[level[1]]
        out.append({
            "id": cid, "track": track, "name": name, "value": value, "kit": kit or "",
            "mode": mode_of(track), "prices": hint_prices(value), "hints": hints,
        })
    ids = [c["id"] for c in out]
    if len(set(ids)) != len(ids):
        fail("duplicate challenge id in the catalogue")
    if len(out) != 40:
        fail(f"expected 40 challenges in {rel(CATALOG_C)}, found {len(out)}")
    return out


def parse_answers():
    src = strip_comments(HW_C.read_text(encoding="utf-8"))
    m = re.search(r'return\s+(\d+)\s*\+\s*ctf_derive_u32\("(HW-03:freq)"\)\s*%\s*(\d+)\s*;', src)
    t = re.search(r"fabs\(v - f\)\s*<=\s*f\s*\*\s*([0-9.]+)\s*;", src)
    if not m or not t or 'ctf_set_answer("HW-03", hw03_answer' not in src:
        fail(f"HW-03 answer gate (frequency formula or tolerance) not found in {rel(HW_C)}")
    return {
        "HW-03": {
            "kind": "u32-range",
            "label": m.group(2),
            "base": int(m.group(1)),
            "mod": int(m.group(3)),
            "tolerance": float(t.group(1)),
            "unit": "Hz",
        }
    }


def build_board_data():
    catalog = parse_catalog()
    answers = parse_answers()
    for cid in answers:
        if cid not in {c["id"] for c in catalog}:
            fail(f"answer gate for unknown challenge {cid}")
    return {
        "_generated": "by scripts/build-app-content.py from ctf_core.c, ctf_core.h, ctf_catalog.c, track_hw.c; do not edit",
        "key": parse_key().hex(),
        "start": parse_core_header(),
        "priceRule": "tier 1 free, tier 2 round(0.2 x value), tier 3 round(0.5 x value), half up",
        "challenges": catalog,
        "answers": answers,
    }


# ---------------------------------------------------------------- main

def dump(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def main():
    outputs = [(OUT_CHALLENGES, dump(build_challenges())), (OUT_BOARD, dump(build_board_data()))]
    if "--check" in sys.argv[1:]:
        stale = [p for p, text in outputs if (p.read_text(encoding="utf-8") if p.exists() else "") != text]
        for p in stale:
            print(f"error: {rel(p)} is out of date; run {Path(__file__).name}", file=sys.stderr)
        if stale:
            sys.exit(1)
        print("app content is up to date")
        return
    CONTENT.mkdir(parents=True, exist_ok=True)
    for p, text in outputs:
        p.write_text(text, encoding="utf-8")
        print(f"wrote {rel(p)}")


if __name__ == "__main__":
    main()
