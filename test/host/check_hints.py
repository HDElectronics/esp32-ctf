#!/usr/bin/env python3
"""Lint the hint tiers in components/ctf_core/ctf_catalog.c (task 14b).

Parses the CATALOG entries and asserts, for every challenge:
  - exactly 40 entries, each with 3 non-empty hint tiers;
  - plain ASCII only (no smart quotes, em-dashes, Unicode);
  - per-tier length limits (tier 1 <= 140, tier 2 <= 240, tier 3 <= 520);
  - no literal flag (`ESP{` followed by hex) and no leftover placeholder text;
  - the three tiers of a challenge are distinct from one another.

Run: python3 test/host/check_hints.py
Exit status 0 on success, 1 on any failure.
"""
import os
import re
import sys

LIMITS = {1: 140, 2: 240, 3: 520}
HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, "..", "..", "components", "ctf_core", "ctf_catalog.c")

# A catalogue entry: {"ID", "TRACK", "name", LEVEL, kit, {t1, t2, t3}}
# We match the id and then the brace group holding the three tier strings.
ENTRY_RE = re.compile(
    r'\{\s*"([A-Z]+-\d+)"\s*,\s*"[A-Z]+"\s*,.*?\{\s*(".*?")\s*\}\s*\}',
    re.S,
)
FLAG_RE = re.compile(r"ESP\{[0-9A-Fa-f]")
PLACEHOLDER_RE = re.compile(r"to be written|NUDGE|WALKTHROUGH|TODO|FIXME")


def c_strings(blob):
    """Return the list of C string literals in `blob` (handles \\" and \\\\)."""
    out, i, n = [], 0, len(blob)
    while i < n:
        if blob[i] == '"':
            j, buf = i + 1, []
            while j < n and blob[j] != '"':
                if blob[j] == "\\":
                    esc = blob[j + 1]
                    buf.append({"n": "\n", "t": "\t", "r": "\r", '"': '"',
                                "\\": "\\", "0": "\0"}.get(esc, esc))
                    j += 2
                else:
                    buf.append(blob[j])
                    j += 1
            out.append("".join(buf))
            i = j + 1
        else:
            i += 1
    return out


def main():
    with open(CATALOG, "r", encoding="utf-8") as f:
        src = f.read()

    # Guard: the helper macros must be gone.
    if re.search(r"#define\s+(NUDGE|WALKTHROUGH)\b", src):
        print("FAIL: NUDGE/WALKTHROUGH macros still defined")
        return 1

    entries = ENTRY_RE.findall(src)
    errors = []
    if len(entries) != 40:
        errors.append("expected 40 entries, parsed %d" % len(entries))

    for cid, group in entries:
        tiers = c_strings(group)
        if len(tiers) != 3:
            errors.append("%s: parsed %d tiers, want 3" % (cid, len(tiers)))
            continue
        for t, text in enumerate(tiers, 1):
            if not text.strip():
                errors.append("%s tier %d: empty" % (cid, t))
            try:
                text.encode("ascii")
            except UnicodeEncodeError as e:
                errors.append("%s tier %d: non-ASCII (%s)" % (cid, t, e))
            if len(text) > LIMITS[t]:
                errors.append("%s tier %d: %d chars > %d" % (cid, t, len(text), LIMITS[t]))
            if FLAG_RE.search(text):
                errors.append("%s tier %d: contains a literal flag" % (cid, t))
            if PLACEHOLDER_RE.search(text):
                errors.append("%s tier %d: placeholder text left" % (cid, t))
        if len(set(tiers)) != 3:
            errors.append("%s: tier texts are not all distinct" % cid)

    if errors:
        print("FAIL (%d):" % len(errors))
        for e in errors:
            print("  " + e)
        return 1

    lens = [max(len(t) for _, g in [(c, g)] for t in c_strings(g))
            for c, g in entries]
    print("PASS: 40 entries x 3 tiers, ASCII, within limits, no flags/placeholders.")
    print("longest tier-3 text: %d chars (limit 520)" % max(lens))
    return 0


if __name__ == "__main__":
    sys.exit(main())
