#!/usr/bin/env python3
"""Every word on screen must be a word she actually said.

WHY THIS EXISTS. Five times now, text has reached a render that the creator
never said:

    "THE ALGORITHM THINKS YOU ARE EVERYONE ELSE"   invented line
    "Day 22"                                        invented fact
    1,284  "TIMES YOU CHECKED"                      invented STATISTIC
    "HER EFFORT" / "HER ANXIETY"                    narrator talking ABOUT her,
                                                    in third person, on her own
                                                    channel

Every one was caught by a human eye, late, and only because someone happened to
look. Nothing in the pipeline could catch it, because the graphics live in React
and the truth lives in a transcript and the two never met.

This is the smallest thing that connects them: pull the strings that get RENDERED,
and ask the transcript whether she said them.

    python3 verify_text.py <transcript.json> <file.tsx> [file.tsx ...]

VERDICTS
  ok      the string appears in the transcript. She said it.
  PROP    marked `// prop` — deliberate UI chrome (an Instagram notification, a
          progress bar). Not a claim about her, so not held to the transcript.
  REVIEW  not in the transcript and not marked. Either quote her, mark it a prop,
          or cut it.
  NUMBER  not in the transcript AND contains a numeral. Loudest verdict on
          purpose: an invented number reads as a fact about her, and it is the
          exact shape of the worst bug this file exists to stop.

A REVIEW is not automatically wrong — "DECLINED" on a mock paywall is fine. It
means a human has to look. That is the whole point: make the invisible visible.
"""
import json
import re
import sys
from pathlib import Path

# Text nodes between JSX tags, plus string literals inside array/props that end
# up on screen. Deliberately over-collects: a false REVIEW costs five seconds, a
# missed fabrication costs the creator's credibility.
JSX_TEXT = re.compile(r">\s*([A-Za-z0-9][^<>{}\n]{2,}?)\s*<")
STR_LIT = re.compile(r'"([A-Za-z0-9][^"\n]{2,})"|\'([A-Za-z0-9][^\'\n]{2,})\'')

# Things that are code, not content.
#
# EVERY BRANCH IS FULL-ANCHORED, and that is not style. The first version left the
# numeric branch unanchored, so `re.match` succeeded on the leading "1" of
# "1 MILE WARM-UP" and threw the whole string away as a CSS length. It also ate
# "4 × 100m SPRINTS" and "3 new comments". The guard was silently blind to
# precisely the category it screams loudest about — anything starting with a digit,
# which is to say every invented statistic. It reported all-clear on a checklist
# that was on screen in the delivered cut.
#
# A filter that hides content is worse than no filter. Use fullmatch, anchor
# everything, and let a false REVIEW cost five seconds instead.
CODE = re.compile(
    r"px|rgba?|#[0-9a-f]{3,8}|[\d.]+(px|s|deg|%|fr|vh|vw|rem|em)?|"
    r"flex|grid|absolute|relative|center|column|row|none|auto|bold|nowrap|"
    r"tabular-nums|clamp|transparent|hidden|solid|round|butt|square|"
    r"extrapolateLeft|extrapolateRight|Inter|-apple-system|sans-serif|"
    r"currentColor|inherit|initial|unset|pointer|default|visible|scroll|"
    r"line-through|underline|uppercase|lowercase|capitalize|ellipsis|"
    r"contain|cover|fill-available|min-content|max-content|baseline|stretch|"
    r"[a-z]+[A-Z][a-zA-Z]*|"                        # camelCase identifiers
    r"[\w./-]+\.(tsx?|jsx?|mov|mp4|png|json|css)|"  # paths
    r"(https?|file|data):.*|"
    r"[\d.]+ [\d.]+ (auto|[\d.]+\w*)",   # flex shorthand
    re.I,
)


# A string sitting after `someProp:` is a STYLE VALUE, not something a viewer
# reads — `background: "linear-gradient(...)"`, `justifyContent: "space-between"`.
# Without this the two real fabrications ("HER ANXIETY", "TIMES YOU CHECKED") came
# back buried in ten lines of CSS. A check nobody reads is a check that does not
# exist, so the noise is not cosmetic — it is the difference between working and not.
# NOTE the denylist. The first cut of this skipped ANY string preceded by
# `identifier:` — which silently ate `text: "liked your post"` and `label: "..."`,
# the very content that has to be checked. A filter that hides real on-screen text
# is worse than no filter, because it reports all-clear. Name the CSS properties
# explicitly; anything not on this list is treated as content.
STYLE_PROPS = (
    "background|backgroundColor|color|font|fontFamily|fontWeight|fontSize|"
    "border|borderRadius|boxShadow|textShadow|display|position|transform|"
    "justifyContent|alignItems|alignSelf|flexDirection|whiteSpace|textAlign|"
    "letterSpacing|lineHeight|overflow|objectFit|pointerEvents|fontVariantNumeric|"
    "stroke|strokeLinecap|fill|filter|mixBlendMode|backdropFilter|cursor|visibility|"
    "textDecoration|textTransform|flexWrap|gridTemplateColumns|WebkitTextStroke"
)
STYLE_VALUE = re.compile(rf"\b({STYLE_PROPS})\s*:\s*$")
CSS_ISH = re.compile(
    r"(linear-gradient|radial-gradient|rgba?\(|sans-serif|-apple-system|"
    r"\d+px|\bem\b|cubic-bezier|space-(between|around|evenly)|flex-(start|end))",
    re.I,
)


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2

    tr = json.loads(Path(sys.argv[1]).read_text())
    words = [w["w"] for s in tr["segments"] for w in s.get("words", [])]
    said = squash(normalize(" ".join(words)))
    # digits also spelled out: she says "three", a graphic shows "3"
    NUM = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
           "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
           "10": "ten", "98": "98"}

    bad = 0
    for path in sys.argv[2:]:
        src = Path(path).read_text()
        lines = src.splitlines()

        # Comments are not on screen. Blank them out rather than skipping whole
        # lines: a /* */ block's continuation lines start with no marker at all, so
        # a line-prefix test leaks prose out of a comment and reports it as text a
        # viewer would read. Overwrite with spaces so every offset still lines up.
        def blank(m):
            return re.sub(r"[^\n]", " ", m.group(0))

        code = re.sub(r"/\*.*?\*/", blank, src, flags=re.S)
        code = re.sub(r"//[^\n]*", blank, code)

        found = []
        for m in list(JSX_TEXT.finditer(code)) + list(STR_LIT.finditer(code)):
            text = next(g for g in m.groups() if g) if m.re is STR_LIT else m.group(1)
            text = text.strip()
            if CODE.fullmatch(text) or CSS_ISH.search(text):
                continue
            line_start = code.rfind("\n", 0, m.start()) + 1
            if STYLE_VALUE.search(code[line_start: m.start()]):
                continue
            line_no = code[: m.start()].count("\n")
            found.append((line_no, text))

        # `// prop` marks the BLOCK it introduces, not just the next line. A
        # notification array has nine entries; a marker covering two of them tags
        # the first and leaves eight screaming, which trains you to ignore the
        # output. The block ends at a blank line or a closing bracket in column 0.
        # `// said <where>` is the other escape hatch, and it is NOT the same as
        # `// prop`. Some text IS her words but cannot be matched: she says
        # "we'll do four 100 meters" at 12:51 and the card reads "4 x 100m SPRINTS".
        # True, and no substring test will ever agree. Without a way to record that,
        # the file stays permanently red — and a check that is always red is a check
        # everyone learns to ignore, which is the same as having no check.
        # So: a human may clear a string, but only by leaving the receipt inline.
        prop_lines, said_lines = set(), set()
        in_prop = in_said = False
        for i, ln in enumerate(lines):
            if re.search(r"//\s*prop", ln, re.I):
                in_prop, in_said = True, False
            elif re.search(r"//\s*said\b", ln, re.I):
                in_said, in_prop = True, False
            elif (in_prop or in_said) and (not ln.strip() or re.match(r"[)\]}]", ln)):
                in_prop = in_said = False
            if in_prop:
                prop_lines.add(i)
            if in_said:
                said_lines.add(i)

        seen, rows = set(), []
        for line_no, text in found:
            if text in seen:
                continue
            seen.add(text)

            if line_no in prop_lines:
                rows.append(("PROP", text))
                continue
            if line_no in said_lines:
                rows.append(("SAID", text))
                continue

            n = squash(normalize(text))
            hit = n and n in said
            if not hit and n:  # try digit -> word
                alt = " ".join(NUM.get(t, t) for t in n.split())
                hit = alt in said
            if hit:
                rows.append(("ok", text))
            elif re.search(r"\d", text):
                rows.append(("NUMBER", text))
                bad += 1
            else:
                rows.append(("REVIEW", text))
                bad += 1

        print(f"\n{path}")
        for verdict, text in sorted(rows, key=lambda r: ("ok PROP SAID".find(r[0]), r[1])):
            mark = {"ok": "  ok    ", "PROP": "  prop  ", "SAID": "  said  ",
                    "REVIEW": "  REVIEW", "NUMBER": "  NUMBER"}[verdict]
            print(f"{mark}  {text[:72]}")

    print(f"\n{bad} string(s) need a human. "
          f"Quote her, mark it `// prop`, or cut it.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
