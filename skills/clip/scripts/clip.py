#!/usr/bin/env python3
"""
clip.py — transcript-driven video clipping.

Two phases, with Claude's judgment in between:

  prep  <url|file>                 acquire + transcribe -> timestamped transcript
  cut   <workdir> --clips ...      render the moments Claude chose

The whole point: the transcript is the edit surface. `prep` produces text with
timestamps, Claude reads it and decides what's worth keeping, `cut` applies
those decisions to the pixels. No timeline scrubbing anywhere.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Cuts land this much before/after the spoken words so we don't clip breaths
# or shave the last consonant. Tuned by ear, not theory — adjust freely.
PAD_HEAD = 0.20
PAD_TAIL = 0.35

# The workdir also holds source.*.vtt subtitle files, so "the video" can never be
# `glob('source.*')[0]` — that hands you a .vtt on the second run.
VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}


def find_video(work: Path):
    hits = sorted(p for p in work.glob("source.*") if p.suffix.lower() in VIDEO_EXT)
    return hits[0] if hits else None


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        sys.exit(f"command failed: {' '.join(map(str, cmd))}\n\n{p.stderr.strip()}")
    return p


def need(tool):
    if not shutil.which(tool):
        sys.exit(f"missing required tool: {tool}")


# ---------------------------------------------------------------- acquire


def acquire(source: str, work: Path) -> Path:
    """Return a local video path, downloading if source is a URL."""
    work.mkdir(parents=True, exist_ok=True)

    local = Path(source).expanduser()
    if local.exists():
        dest = work / f"source{local.suffix.lower()}"
        if not dest.exists():
            shutil.copy2(local, dest)
        return dest

    if not re.match(r"https?://", source):
        sys.exit(f"not a file or URL: {source}")

    need("yt-dlp")
    cached = find_video(work)
    if cached:
        return cached

    print(f"downloading {source} ...", flush=True)
    run([
        "yt-dlp",
        "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format", "mp4",
        # Grab subs opportunistically — free and instant when the uploader has
        # them. We fall back to whisper when they're absent.
        "--write-auto-subs", "--write-subs", "--sub-lang", "en.*", "--sub-format", "vtt",
        "-o", str(work / "source.%(ext)s"),
        source,
    ])
    video = find_video(work)
    if not video:
        sys.exit("download produced no video file")
    return video


# ------------------------------------------------------------- transcribe


def parse_vtt(path: Path):
    """VTT -> [{start,end,text}]. YouTube's auto-subs roll words, so we drop
    cues whose text is fully contained in the previous cue."""
    ts = r"(\d+):(\d{2}):(\d{2})\.(\d{3})"
    cue = re.compile(rf"{ts}\s*-->\s*{ts}")
    segs = []
    start = end = None
    buf = []

    def secs(h, m, s, ms):
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    def flush():
        nonlocal buf, start, end
        if start is None or not buf:
            buf = []
            return
        text = " ".join(buf).strip()
        text = re.sub(r"<[^>]+>", "", text)          # inline word timing tags
        text = re.sub(r"\s+", " ", text).strip()
        if text and (not segs or text != segs[-1]["text"]):
            # auto-subs repeat the prior line as a scroll buffer
            if segs and text.startswith(segs[-1]["text"]):
                text = text[len(segs[-1]["text"]):].strip()
            if text:
                segs.append({"start": start, "end": end, "text": text})
        buf = []

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = cue.match(line.strip())
        if m:
            flush()
            g = m.groups()
            start, end = secs(*g[:4]), secs(*g[4:])
        elif line.strip() and not line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            buf.append(line.strip())
    flush()
    return segs


def transcribe(video: Path, work: Path, force_whisper: bool):
    """Prefer the uploader's subs (instant); fall back to whisper (word-level)."""
    if not force_whisper:
        vtts = sorted(work.glob("source*.vtt"))
        if vtts:
            segs = parse_vtt(vtts[0])
            if segs:
                print(f"using yt-dlp subtitles ({len(segs)} segments)", flush=True)
                return segs, "yt-dlp-subs"

    model = "base.en"
    raw = work / f"{video.stem}.json"
    if raw.exists():
        # Whisper is the slow step; never pay for it twice on the same workdir.
        print(f"reusing existing whisper output ({raw.name})", flush=True)
    else:
        need("whisper")
        print(f"no usable subs — running whisper ({model}), word-level ...", flush=True)
        run([
            "whisper", str(video),
            "--model", model,
            "--output_format", "json",
            "--word_timestamps", "True",
            "--output_dir", str(work),
            "--verbose", "False",
        ])
    data = json.loads(raw.read_text())
    segs = []
    for s in data["segments"]:
        if not s["text"].strip():
            continue
        segs.append({
            "start": s["start"], "end": s["end"], "text": s["text"].strip(),
            # Word timings are what make --tighten possible. Uploader subs are
            # phrase-level and carry none, which is why --tighten needs whisper.
            "words": [
                {"w": w["word"].strip(), "start": w["start"], "end": w["end"]}
                for w in s.get("words", []) if w.get("word", "").strip()
            ],
        })
    return segs, f"whisper-{model}"


# ------------------------------------------------------------------- cut


CAPTION_WORDS = 4   # words on screen at once — short-form reads best in bursts
HOOK_SECS = 2.5     # how long the hook card stays up
PUSH_ZOOM = 1.07    # end scale of the slow push (subtle on purpose)
HILITE = "&H0000D7FF"  # ASS is &HAABBGGRR — this is amber


def ass_escape(t):
    return t.replace("{", "(").replace("}", ")").replace("\n", " ").strip()


def caption_cues(segs, clip_start, clip_end):
    """[(start, end, text)] for the clip. Built from WORDS when we have them:
    segment-level captions leak words spoken outside the cut and dump a wall of
    text on screen. Falls back to segments (clipped to the span) without them."""
    words = [w for s in segs for w in s.get("words", [])
             if w["end"] > clip_start and w["start"] < clip_end]
    if words:
        cues, chunk = [], []
        for w in words:
            chunk.append(w)
            # Flush on a sentence boundary, or once the line is full.
            if w["w"].rstrip().endswith((".", "?", "!", ",")) or len(chunk) >= CAPTION_WORDS:
                cues.append((chunk[0]["start"], chunk[-1]["end"],
                             " ".join(x["w"] for x in chunk)))
                chunk = []
        if chunk:
            cues.append((chunk[0]["start"], chunk[-1]["end"],
                         " ".join(x["w"] for x in chunk)))
        return cues

    return [(max(s["start"], clip_start), min(s["end"], clip_end), s["text"])
            for s in segs if s["end"] > clip_start and s["start"] < clip_end]


def build_ass(segs, clip_start, clip_end, offset, path: Path, vertical: bool, emphasize=()):
    """Burned-in captions for one clip, retimed to the clip's own clock."""
    play_w, play_h = (1080, 1920) if vertical else (1920, 1080)
    margin_v = 300 if vertical else 90
    size = 84 if vertical else 54

    def t(sec):
        sec = max(0.0, sec)
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{int(h)}:{int(m):02d}:{s:05.2f}"

    lines = [
        "[Script Info]", "ScriptType: v4.00+",
        f"PlayResX: {play_w}", f"PlayResY: {play_h}", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,"
        "Bold,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        # Heavy outline + drop shadow: captions must stay legible over any frame,
        # and short-form is watched muted, so this is the load-bearing layer.
        f"Style: Cap,Helvetica,{size},&H00FFFFFF,&H00000000,&H80000000,"
        f"-1,1,6,3,2,80,80,{margin_v},1", "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    for c_a, c_b, txt in caption_cues(segs, clip_start, clip_end):
        a = max(c_a, clip_start) - clip_start + offset
        b = min(c_b, clip_end) - clip_start + offset
        if b - a < 0.05:
            continue
        txt = ass_escape(txt).upper()
        if not txt:
            continue
        if emphasize:
            # Amber the words that carry the claim, so the eye lands on the
            # number and not on the filler around it.
            out = []
            for word in txt.split():
                bare = word.strip(".,?!\"'—-").lower()
                if any(k in bare for k in emphasize):
                    out.append(f"{{\\c{HILITE}&}}{word}{{\\c&H00FFFFFF&}}")
                else:
                    out.append(word)
            txt = " ".join(out)
        lines.append(f"Dialogue: 0,{t(a)},{t(b)},Cap,,0,0,0,,{txt}")
    path.write_text("\n".join(lines), encoding="utf-8")


def finish(out: Path, hook: str, push: bool, vertical: bool, work: Path):
    """Final pass over the assembled clip: hook card + slow push.

    Deliberately a SECOND pass rather than folded into the per-part renders —
    with --tighten a clip is several sub-cuts, and a per-part zoom would reset
    at every cut and strobe. One continuous pass over the finished clip is both
    simpler and the only way the push reads as one smooth move.
    """
    if not hook and not push:
        return out

    play_w, play_h = (1080, 1920) if vertical else (1920, 1080)
    vf = []
    if push:
        fps = 30
        secs = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(out)]).stdout.strip())
        rate = (PUSH_ZOOM - 1.0) / max(1, secs * fps)   # ramp to PUSH_ZOOM by the last frame
        vf.append(
            f"zoompan=z='min(1+{rate:.8f}*on,{PUSH_ZOOM})':d=1"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":s={play_w}x{play_h}:fps={fps}"
        )
    if hook:
        card = work / "hook.ass"
        size = 96 if vertical else 64
        card.write_text("\n".join([
            "[Script Info]", "ScriptType: v4.00+",
            f"PlayResX: {play_w}", f"PlayResY: {play_h}", "",
            "[V4+ Styles]",
            "Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,"
            "Bold,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
            # Alignment 8 = top-center: the hook sits above her face, captions below it.
            f"Style: Hook,Helvetica,{size},&H00FFFFFF,&H00000000,&HA0000000,"
            f"-1,1,7,4,8,70,70,160,1", "",
            "[Events]",
            "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
            f"Dialogue: 0,0:00:00.00,0:00:{HOOK_SECS:05.2f},Hook,,0,0,0,,"
            f"{ass_escape(hook).upper()}",
        ]), encoding="utf-8")
        vf.append(f"subtitles={card.name}")

    final = work / f"{out.stem}-final.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(out.resolve()),
         "-vf", ",".join(vf),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
         "-r", "30", "-c:a", "copy", final.name], cwd=work)
    shutil.move(final, out)
    return out


# Only unambiguous disfluencies. "like", "so", "you know" are NOT here on
# purpose — they carry real meaning often enough that cutting them mangles
# sentences, and a wrong cut is worse than an um left in.
FILLERS = {"um", "umm", "uh", "uhh", "uhm", "erm", "er", "hmm", "mhm", "ah"}
MAX_GAP = 0.55   # dead air longer than this inside a clip gets cut out
MICRO_PAD = 0.06  # breathing room around each surviving sub-span


def tighten(segs, a, b):
    """Split the outer span [a,b] into sub-spans with filler words and dead air
    removed. Returns [(a, b)] unchanged when there's no word-level data — that's
    the uploader-subs case, where we simply can't do this safely."""
    words = [w for s in segs for w in s.get("words", [])
             if w["start"] >= a - 0.01 and w["end"] <= b + 0.01]
    keep = [w for w in words if w["w"].strip(" .,?!—-").lower() not in FILLERS]
    if not keep:
        return [(a, b)], 0, 0.0

    spans = []
    lo, hi = keep[0]["start"], keep[0]["end"]
    for w in keep[1:]:
        if w["start"] - hi > MAX_GAP:     # dead air -> close this span, open a new one
            spans.append((lo, hi))
            lo = w["start"]
        hi = w["end"]
    spans.append((lo, hi))

    # Pad each span, then merge any that now touch, so we don't emit a cut
    # between two pieces that are effectively contiguous.
    padded = [(max(a, s - MICRO_PAD), min(b, e + MICRO_PAD)) for s, e in spans]
    merged = [padded[0]]
    for s, e in padded[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))

    removed = (b - a) - sum(e - s for s, e in merged)
    return merged, len(words) - len(keep), removed


def crop_9x16(video: Path) -> str:
    """Center-crop filter for 9:16. Numbers computed here, not in ffmpeg's
    expression language — an expression like min(iw,ih*9/16) contains a comma,
    which ffmpeg's filtergraph parser eats as a filter separator."""
    w, h = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=p=0",
                str(video)]).stdout.strip().split(",")[:2]
    w, h = int(w), int(h)
    if w / h > 9 / 16:               # wider than 9:16 -> trim the sides
        cw, ch = int(h * 9 / 16), h
    else:                            # taller -> trim top/bottom
        cw, ch = w, int(w * 16 / 9)
    cw -= cw % 2                     # h264 needs even dimensions
    ch -= ch % 2
    return f"crop={cw}:{ch}:{(w - cw) // 2}:{(h - ch) // 2},scale=1080:1920"


def cut(work: Path, spans, out_name, vertical, captions, do_tighten=False,
        emphasize=(), hook="", push=False):
    need("ffmpeg")
    meta = json.loads((work / "transcript.json").read_text())
    segs = meta["segments"]
    video = work / meta["video"]
    duration = float(meta["duration"])

    if do_tighten and not any(s.get("words") for s in segs):
        sys.exit("--tighten needs word-level timings; re-run `prep --whisper` "
                 f"(this transcript came from {meta.get('method')})")

    # Expand each chosen span into what actually gets rendered. Without --tighten
    # that's the span itself; with it, the span minus its fillers and dead air.
    render = []
    for i, (raw_a, raw_b) in enumerate(spans):
        a = max(0.0, raw_a - PAD_HEAD)
        b = min(duration, raw_b + PAD_TAIL)
        if b <= a:
            sys.exit(f"clip {i}: end ({raw_b}) must be after start ({raw_a})")
        if do_tighten:
            subs, n_fill, secs = tighten(segs, a, b)
            print(f"  tighten {a:.1f}-{b:.1f}s: -{n_fill} filler, "
                  f"-{secs:.1f}s dead air -> {len(subs)} sub-cut(s)", flush=True)
            render.extend(subs)
        else:
            render.append((a, b))

    parts_dir = work / "parts"
    if parts_dir.exists():
        shutil.rmtree(parts_dir)
    parts_dir.mkdir()

    crop_filter = crop_9x16(video) if vertical else None
    listing = []
    for i, (a, b) in enumerate(render):
        part = parts_dir / f"part{i:02d}.mp4"
        vf = []
        if vertical:
            # Center-crop. A face-tracking crop would frame better; this is the
            # honest 90% version. ponytail: swap in smart-crop if framing bites.
            vf.append(crop_filter)
        if captions:
            ass = parts_dir / f"part{i:02d}.ass"
            # offset 0: this part's own clock starts at `a`, so a word spoken at
            # t belongs at (t - a). Passing PAD_HEAD here dragged every caption
            # 200ms late.
            build_ass(segs, a, b, 0.0, ass, vertical, emphasize)
            # Bare filename + cwd=parts_dir: absolute paths inside a filtergraph
            # need their colons and backslashes escaped, and that's a losing game.
            vf.append(f"subtitles={ass.name}")

        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
               "-i", str(video.resolve())]
        if vf:
            cmd += ["-vf", ",".join(vf)]
        # Re-encode (not -c copy): copy would snap cuts to the nearest keyframe
        # and drift them off the words we actually chose.
        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-r", "30", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", part.name,
        ]
        run(cmd, cwd=parts_dir)
        listing.append(f"file '{part.name}'")
        print(f"  render {i}: {a:.2f}–{b:.2f}s", flush=True)

    out = work / f"{out_name}.mp4"
    if len(listing) == 1:
        shutil.copy2(parts_dir / "part00.mp4", out)
    else:
        lf = parts_dir / "list.txt"
        lf.write_text("\n".join(listing))
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", str(lf), "-c", "copy", str(out)])

    finish(out, hook, push, vertical, work)

    dur = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", str(out)]).stdout.strip()
    print(f"\n{out}  ({float(dur):.1f}s)")
    return out


# ------------------------------------------------------------------ main


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prep", help="acquire + transcribe")
    p.add_argument("source", help="YouTube/any yt-dlp URL, or a local video path")
    p.add_argument("--work", default=None, help="working dir (default: ./clip-work/<slug>)")
    p.add_argument("--whisper", action="store_true", help="force whisper, ignore uploader subs")

    c = sub.add_parser("cut", help="render Claude-selected moments")
    c.add_argument("work", help="working dir from prep")
    c.add_argument("--clips", required=True,
                   help="comma-separated start:end in seconds, e.g. 12.4:31.0,88:104.5")
    c.add_argument("--out", default="clip", help="output basename")
    c.add_argument("--vertical", action="store_true", help="9:16 center-crop for Shorts/Reels")
    c.add_argument("--captions", action="store_true", help="burn in captions")
    c.add_argument("--tighten", action="store_true",
                   help="drop filler words + dead air INSIDE each clip (needs prep --whisper)")
    c.add_argument("--emphasize", default="",
                   help="comma-separated words to amber in the captions, e.g. '98%%,anxiety'")
    c.add_argument("--hook", default="",
                   help=f"hook text over the first {HOOK_SECS}s (top of frame)")
    c.add_argument("--push", action="store_true",
                   help="slow continuous zoom across the clip (subtle; adds life)")

    a = ap.parse_args()

    if a.cmd == "prep":
        work = Path(a.work) if a.work else Path("clip-work") / re.sub(
            r"[^a-zA-Z0-9]+", "-", Path(a.source).stem or "video")[:40].strip("-")
        work = work.expanduser().resolve()
        video = acquire(a.source, work)
        segs, method = transcribe(video, work, a.whisper)
        if not segs:
            sys.exit("no transcript produced — is there any speech in this video?")

        dur = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "csv=p=0", str(video)]).stdout.strip())
        (work / "transcript.json").write_text(json.dumps({
            "source": a.source, "video": video.name, "duration": dur,
            "method": method, "segments": segs,
        }, indent=2))

        print(f"\n=== TRANSCRIPT  ({dur/60:.1f} min, {len(segs)} segments, via {method}) ===\n")
        for s in segs:
            print(f"[{s['start']:8.2f} - {s['end']:8.2f}]  {s['text']}")
        print(f"\n=== workdir: {work} ===")

    elif a.cmd == "cut":
        spans = []
        for chunk in a.clips.split(","):
            lo, _, hi = chunk.strip().partition(":")
            spans.append((float(lo), float(hi)))
        emph = tuple(w.strip().lower() for w in a.emphasize.split(",") if w.strip())
        cut(Path(a.work).expanduser().resolve(), spans, a.out,
            a.vertical, a.captions, a.tighten, emph, a.hook, a.push)


if __name__ == "__main__":
    main()
