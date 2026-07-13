---
name: longform
description: Fix a long-form video (vlog, podcast, webinar, stream) that is raw and unengaging — find a cold open buried in the footage, strip dead air across the whole file, and propose chapters. Uses the same transcript engine as /clip, pointed at a bigger canvas. Use when asked to "make this vlog watchable", "tighten this long video", "why is this boring", "add a cold open", "cut the dead parts", "chapter this up", "edit my YouTube video", "/longform <url>".
user_invocable: true
---

# /longform — make a raw long video watchable

Reuses the `clip` skill's engine (`clip.py` in the sibling `clip/` skill folder). Read that
skill first — the transcript is still the edit surface, and the approval rule
still applies: **nothing renders until the human says yes.**

## The diagnosis, before the tools

**A raw vlog is not boring because it's unpolished. It's boring because there is
no question the viewer needs answered.**

"Day 23 marathon training" promises nothing, so there's no reason to stay. The
same creator's best-performing title is "i failed" — because that one has a
question in it. Production value will not fix a video with no stakes. Say this
out loud to the user before you start editing; if the footage genuinely contains
no question, no admission, and no turning point, **the honest advice is that this
video can't be saved in the edit**, and a better one gets recorded.

Assuming there IS something in there, three fixes, in order of leverage.

## 1. The cold open (biggest lever)

Read the whole transcript and find the **single strongest 10–25 seconds anywhere
in the file** — the admission, the number, the moment it goes wrong. Move it to
the front.

The good part is almost always buried at minute nine. The viewer leaves at
minute one.

```bash
python3 $CLIP_SKILL_DIR/scripts/clip.py cut <workdir> \
  --clips "<cold-open>,<body-start>:<body-end>" --tighten
```

Spans concatenate in the order given, so the cold open is simply the first span.

**Yes, this reorders — and unlike a talking-head short, that's correct here.** A
cold open is an established grammar; the viewer *expects* a jump back in time.
It reads as an edit, not a glitch, because the scene changes. (The no-reordering
rule in `/clip` is about splicing two moments of the SAME locked-off shot.)

Cut back to the top of the video after it. Don't linger.

## 2. Pacing — silence is what makes raw footage feel raw

Run `--tighten` across the **entire** video, not a window:

```bash
--clips "0:<duration>" --tighten --max-gap 0.6
```

A 15-minute vlog is usually 8 minutes of content stretched over 15. This is the
single biggest engagement lift available and it's already built.

**But one threshold is not editing.** Raise `--max-gap` to protect a pause that
is doing work — the beat before a confession, the breath after bad news. Cutting
every silence produces something that feels machine-made. Scan the transcript for
emotional peaks and quote the timestamps you intend to protect.

## 3. Chapters

Propose the arc: where the tension is, where a segment genuinely ends, and what
each chapter promises. Then emit YouTube timestamps.

**Read them from `<out>.edl.json`, never from the source transcript.** `--tighten`
removes time, so a source timestamp is NOT where the viewer lands. The EDL maps
`source_start` → `output_start`; convert with that, or every chapter marker will
drift later and later through the video.

Chapter titles follow the same rule as clip titles: **they are the creator's
voice.** Draft them, propose them, never impose them.

Chapter cards and the throughline tracker can be rendered via `/direct`
(`ChapterCard` / `Checklist` primitives). Time them from the finished clip's
EDL, and keep long-form graphics sparse by doctrine.

## Workflow

1. `clip.py prep <url>` — run it in the background; a 15-min whisper pass takes
   a couple of minutes.
2. Read the transcript **in full**. Do not skim; the cold open is a needle.
3. **Propose**: the cold open (with the actual words and why), the pauses you'll
   protect, the chapter arc. Wait for approval.
4. Render. Then read the EDL and emit the timestamps.

## Gotchas

- **Don't cut the video down to a highlight reel.** A long-form vlog is a
  *hangout*; the meandering is the product. You are removing dead air and burying
  the lede, not compressing it into a Short. If the user wants a Short, that's
  `/clip`.
- **Chapter drift** is the silent failure — see above. Use the EDL.
- **A cold open you have to explain isn't a cold open.** It must land with zero
  setup.
