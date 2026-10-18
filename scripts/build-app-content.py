#!/usr/bin/env python3
"""Build the player app's spoiler-free challenge content.

Parses docs/players/<track>.md challenge sections:

    ### BLE-03 Notify me (100)[ · Kit: ...]
    <brief, one or more lines>
    Tools: `bluetoothctl`, Python `bleak`

and writes web/app/content/challenges.json as {id: {"brief": str, "tools": [str]}}.
Names, points, kit, mode and solved state come from the board, not this file.

Usage: scripts/build-app-content.py [--check]
  --check  exit 1 if the committed JSON is out of date (writes nothing)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "players"
OUT = ROOT / "web" / "app" / "content" / "challenges.json"

HEAD = re.compile(r"^### ([A-Z]+-\d{2}) .+ \((\d+)\)(?: · Kit: .+)?$")
LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


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


def parse(path):
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
            sys.exit(f"error: {cid} appears twice ({path.name})")
        if not brief or not tools:
            sys.exit(f"error: {cid} in {path.name} has no brief or no Tools: line")
        out[cid] = {"brief": " ".join(brief), "tools": tools}
    return out


def main():
    data = {}
    for path in sorted(DOCS.glob("*.md")):
        for cid, entry in parse(path).items():
            if cid in data:
                sys.exit(f"error: {cid} appears in two guides")
            data[cid] = entry
    if len(data) != 40:
        sys.exit(f"error: expected 40 challenges, found {len(data)}")
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv[1:]:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            sys.exit(f"error: {OUT.relative_to(ROOT)} is out of date; run {Path(__file__).name}")
        print("challenges.json is up to date")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(data)} challenges)")


if __name__ == "__main__":
    main()
