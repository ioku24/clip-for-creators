#!/usr/bin/env python3
"""
clip.py — transcript-driven video clipping.

Two phases, with the model's judgment in between:

  prep  <url|file>                 acquire + transcribe -> timestamped transcript
  cut   <workdir> --clips ...      render the moments the model chose

The whole point: the transcript is the edit surface. `prep` produces text with
timestamps, the model reads it and decides what's worth keeping, `cut` applies
those decisions to the pixels. No timeline scrubbing anywhere.

Render order matters and is deliberate:
    trim+crop each span  ->  join  ->  push (zoom)  ->  burn captions  ->  loudness
Captions go on LAST, over the finished timeline. Burning them into each part
first (the obvious way) means crossfades dissolve caption pixels and --push
zooms the captions along with the picture. Both look amateur.
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

# How far a pad may encroach on a neighbouring word. 30ms is the tail of a
# consonant release — it protects a plosive's attack when two words butt up
# against each other with no silence between them, and is far too short to be
# heard as a word fragment.
ENCROACH = 0.03


def word_bounds(segs):
    return sorted((w["start"], w["end"]) for s in segs for w in s.get("words", []))


def pad_into_silence(raw_a, raw_b, wb, duration):
    """Pad a span for breathing room — but ONLY into silence.

    THE BUG THIS EXISTS TO KILL: padding used to expand by a flat PAD_HEAD /
    PAD_TAIL and walk straight into the neighbouring word. On a real vlog that
    put one boundary 50% through "know" and the next 72% through "editing", so
    the seam played:

        "...hundred meter sprints I kn-"  |  "-ing. You know, and maybe..."

    Two half-words back to back. That is what a viewer hears as CHOPPY, and no
    framing punch, crossfade or de-click repairs a severed syllable — the fix
    has to happen where the cut is chosen, not where it is rendered.

    A cut belongs in the gap between words. If there is no gap, we take 30ms and
    no more. If the caller's own timestamp lands mid-word we snap it out of that
    word first (keeping the word whole if we're past its midpoint, dropping it
    if we're not) — a fragment is never what anyone meant.
    """
    for s, e in wb:
        if s < raw_a < e:
            raw_a = s if raw_a < (s + e) / 2 else e
        if s < raw_b < e:
            raw_b = s if raw_b < (s + e) / 2 else e

    prev_end = max([e for _, e in wb if e <= raw_a] or [0.0])
    next_start = min([s for s, _ in wb if s >= raw_b] or [duration])

    a = max(0.0, prev_end - ENCROACH, raw_a - PAD_HEAD)
    b = min(duration, next_start + ENCROACH, raw_b + PAD_TAIL)
    return a, b

VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}

# Only unambiguous disfluencies. "like", "so", "you know" are NOT here on
# purpose — they carry real meaning often enough that cutting them mangles
# sentences, and a wrong cut is worse than an um left in.
FILLERS = {"um", "umm", "uh", "uhh", "uhm", "erm", "er", "hmm", "mhm", "ah"}

MAX_GAP = 0.70      # dead air longer than this gets cut. Sub-second silence is
                    # LONG in short-form; but see --keep-beats before dropping it.
MICRO_PAD = 0.10    # breathing room around each surviving sub-span
XFADE = 0.14        # only used with --xfade (opt-in; a dissolve between two face
                    # positions usually advertises the seam rather than hiding it)
CAPTION_WORDS = 4
HOOK_SECS = 2.5
PUSH_ZOOM = 1.07
HILITE = "&H0000D7FF"


def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if p.returncode != 0:
        sys.exit(f"command failed: {' '.join(map(str, cmd))}\n\n{p.stderr.strip()}")
    return p


def need(tool):
    if not shutil.which(tool):
        sys.exit(f"missing required tool: {tool}")


def find_video(work: Path):
    hits = sorted(p for p in work.glob("source.*") if p.suffix.lower() in VIDEO_EXT)
    return hits[0] if hits else None


def probe(path: Path, entries, stream=None):
    cmd = ["ffprobe", "-v", "error"]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "csv=p=0", str(path)]
    return run(cmd).stdout.strip()


def duration_of(path: Path) -> float:
    return float(probe(path, "format=duration").split(",")[0])


def source_fps(path: Path) -> int:
    """Preserve the source cadence. Hard-coding 30 throws away half the temporal
    resolution of 60fps footage — brutal on gestures and fast motion."""
    try:
        num, _, den = probe(path, "stream=r_frame_rate", "v:0").partition("/")
        fps = round(float(num) / float(den or 1))
        return fps if 20 <= fps <= 120 else 30
    except Exception:
        return 30


# ---------------------------------------------------------------- acquire


def acquire(source: str, work: Path) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    stamp = work / "source.txt"
    prior = stamp.read_text().strip() if stamp.exists() else None

    # A reused workdir holding a DIFFERENT source is how you get confidently
    # wrong cuts: stale source.mp4 + stale transcript, new timestamps.
    if prior and prior != source:
        sys.exit(f"workdir already holds a different source:\n  {prior}\n"
                 f"pass a fresh --work dir, or delete {work}")

    local = Path(source).expanduser()
    if local.exists():
        dest = work / f"source{local.suffix.lower()}"
        if not dest.exists():
            shutil.copy2(local, dest)
        stamp.write_text(source)
        return dest

    if not re.match(r"https?://", source):
        sys.exit(f"not a file or URL: {source}")

    need("yt-dlp")
    cached = find_video(work)
    if cached:
        stamp.write_text(source)
        return cached

    print(f"downloading {source} ...", flush=True)
    run([
        "yt-dlp",
        "-f", "bv*[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format", "mp4",
        "--write-auto-subs", "--write-subs", "--sub-lang", "en.*", "--sub-format", "vtt",
        "-o", str(work / "source.%(ext)s"),
        source,
    ])
    video = find_video(work)
    if not video:
        sys.exit("download produced no video file")
    stamp.write_text(source)
    return video


# ------------------------------------------------------------- transcribe


def parse_vtt(path: Path):
    """VTT -> [{start,end,text}].

    YouTube auto-captions "roll": each cue repeats the previous line and appends
    to it. We de-roll ONLY when the timings actually overlap, which is what makes
    a roll a roll. Matching on `text.startswith(previous)` alone silently eats
    real speech — the cue pair ("I", "I was wrong") becomes ("I", "was wrong").
    """
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
        text = re.sub(r"<[^>]+>", "", " ".join(buf))
        text = re.sub(r"\s+", " ", text).strip()
        if text and (not segs or text != segs[-1]["text"]):
            prev = segs[-1] if segs else None
            rolling = prev and start < prev["end"] and text.startswith(prev["text"])
            if rolling:
                text = text[len(prev["text"]):].strip()
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
        print(f"reusing existing whisper output ({raw.name})", flush=True)
    else:
        need("whisper")
        print(f"no usable subs — running whisper ({model}), word-level ...", flush=True)
        run([
            "whisper", str(video), "--model", model, "--output_format", "json",
            "--word_timestamps", "True", "--output_dir", str(work), "--verbose", "False",
        ])
    data = json.loads(raw.read_text())
    segs = []
    for s in data["segments"]:
        if not s["text"].strip():
            continue
        segs.append({
            "start": s["start"], "end": s["end"], "text": s["text"].strip(),
            "words": [
                {"w": w["word"].strip(), "start": w["start"], "end": w["end"]}
                for w in s.get("words", []) if w.get("word", "").strip()
            ],
        })
    return segs, f"whisper-{model}"


# ------------------------------------------------------------- tightening


def tighten(segs, a, b, max_gap):
    """Split [a,b] into sub-spans that EXCLUDE filler words and dead air.

    The subtle bug this replaces: dropping fillers from the word list, then
    spanning from the previous kept word to the next kept word, leaves the
    filler's audio sitting inside the span. It reported removals it never made.
    Here we keep an interval per surviving word and only bridge neighbours when
    they are genuinely adjacent — so a cut filler leaves a real hole.
    """
    words = [w for s in segs for w in s.get("words", [])
             if w["start"] >= a - 0.01 and w["end"] <= b + 0.01]
    if not words:
        return [(a, b)], 0, 0.0

    keep = [w for w in words if w["w"].strip(" .,?!—-\"'").lower() not in FILLERS]
    if not keep:
        return [(a, b)], 0, 0.0

    spans = []
    lo, hi = keep[0]["start"], keep[0]["end"]
    for w in keep[1:]:
        gap = w["start"] - hi
        dropped = any(hi <= f["start"] and f["end"] <= w["start"] for f in words if f not in keep)
        # Break the span on dead air OR on an excised filler. Bridging over a
        # filler is exactly what left the "um" in the audio before.
        if gap > max_gap or dropped:
            spans.append((lo, hi))
            lo = w["start"]
        hi = w["end"]
    spans.append((lo, hi))

    # Pad for breathing room, but never more than a third of the way into the
    # hole we just cut — otherwise the padding re-imports the filler we removed.
    # ...and never into a WORD. A third of the way into the hole can still land
    # on the filler we just excised, or on the neighbour's last syllable.
    wb = sorted((w["start"], w["end"]) for w in words)
    padded = []
    for i, (s, e) in enumerate(spans):
        head = MICRO_PAD if i == 0 else min(MICRO_PAD, (s - spans[i - 1][1]) / 3)
        tail = MICRO_PAD if i == len(spans) - 1 else min(MICRO_PAD, (spans[i + 1][0] - e) / 3)
        prev_end = max([we for _, we in wb if we <= s] or [a])
        next_start = min([ws for ws, _ in wb if ws >= e] or [b])
        padded.append((max(a, s - head, prev_end - ENCROACH),
                       min(b, e + tail, next_start + ENCROACH)))

    merged = [padded[0]]
    for s, e in padded[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))

    n_fill = len(words) - len(keep)
    removed = (b - a) - sum(e - s for s, e in merged)
    return merged, n_fill, removed


# --------------------------------------------------------------- captions


def ass_escape(t):
    t = t.replace("{", "(").replace("}", ")").replace("\n", " ")
    # ASS reads \N \n \h as control codes, so a transcript containing a literal
    # backslash could force line breaks. Neutralise the backslash itself.
    t = t.replace("\\", "/")
    t = re.sub(r"\s+([%,.!?;:])", r"\1", t)
    return t.strip()


def ts(sec):
    sec = max(0.0, sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def timeline_cues(segs, render, offsets, clip_len):
    """Caption cues in OUTPUT time, not source time.

    Each rendered span (a,b) lands at `offset` on the finished timeline, so a
    word spoken at source time t shows at (t - a + offset). Segments without
    word timings fall back per-segment — mixed transcripts must not silently
    lose their captions.
    """
    cues = []
    for (a, b), off in zip(render, offsets):
        for s in segs:
            if s["end"] <= a or s["start"] >= b:
                continue
            words = [w for w in s.get("words", []) if w["end"] > a and w["start"] < b]
            if words:
                chunk = []
                for w in words:
                    chunk.append(w)
                    if w["w"].rstrip().endswith((".", "?", "!", ",")) or len(chunk) >= CAPTION_WORDS:
                        cues.append((chunk[0]["start"] - a + off,
                                     chunk[-1]["end"] - a + off,
                                     " ".join(x["w"] for x in chunk)))
                        chunk = []
                if chunk:
                    cues.append((chunk[0]["start"] - a + off,
                                 chunk[-1]["end"] - a + off,
                                 " ".join(x["w"] for x in chunk)))
            else:
                cues.append((max(s["start"], a) - a + off,
                             min(s["end"], b) - a + off, s["text"]))
    return [(max(0.0, x), min(clip_len, y), t) for x, y, t in cues if y > x]


def write_ass(cues, path: Path, vertical, emphasize=(), hook=""):
    play_w, play_h = (1080, 1920) if vertical else (1920, 1080)
    size = 84 if vertical else 54
    margin_v = 300 if vertical else 90
    lines = [
        "[Script Info]", "ScriptType: v4.00+",
        f"PlayResX: {play_w}", f"PlayResY: {play_h}", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,"
        "Bold,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        # Heavy outline + shadow: short-form is watched on mute, so the caption
        # is load-bearing and must survive any background.
        f"Style: Cap,Helvetica,{size},&H00FFFFFF,&H00000000,&H80000000,"
        f"-1,1,6,3,2,80,80,{margin_v},1",
        f"Style: Hook,Helvetica,{size + 12},&H00FFFFFF,&H00000000,&HA0000000,"
        f"-1,1,7,4,8,70,70,160,1", "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    if hook:
        lines.append(f"Dialogue: 0,0:00:00.00,{ts(HOOK_SECS)},Hook,,0,0,0,,"
                     f"{ass_escape(hook).upper()}")
    for a, b, txt in cues:
        txt = ass_escape(txt).upper()
        if not txt or b - a < 0.05:
            continue
        if emphasize:
            out = []
            for word in txt.split():
                bare = word.strip(".,?!\"'—-%").lower()
                if any(k in bare for k in emphasize):
                    out.append(f"{{\\c{HILITE}&}}{word}{{\\c&H00FFFFFF&}}")
                else:
                    out.append(word)
            txt = " ".join(out)
        lines.append(f"Dialogue: 0,{ts(a)},{ts(b)},Cap,,0,0,0,,{txt}")
    path.write_text("\n".join(lines), encoding="utf-8")


# ----------------------------------------------------------------- render


JUMP_SSIM = 0.70     # above this, two seam frames are the SAME SHOT
PUNCH = 1.055        # framing change that declares a jump cut. Subtle on purpose.


def seam_ssim(video: Path, t_out: float, t_in: float, work: Path) -> float:
    """How similar are the frames either side of a seam?

    HIGH similarity means we cut from a shot back into the SAME shot seconds
    later — the speaker's head, hands and gaze teleport while the background
    insists nothing happened. That is the cut that reads as broken.
    LOW similarity means the scene changed, and the viewer accepts the cut.
    """
    a, b = work / "_sa.png", work / "_sb.png"
    for t, p in ((max(0.0, t_out - 0.08), a), (t_in + 0.08, b)):
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video),
             "-frames:v", "1", "-vf", "scale=160:90", str(p)])
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(a), "-i", str(b),
                        "-lavfi", "ssim=stats_file=-", "-f", "null", "-"],
                       capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if "All:" in line:
            try:
                return float(line.split("All:")[1].split()[0])
            except Exception:
                pass
    return 0.0


def declare_seams(video: Path, render, work: Path):
    """Give each span a scale so that every JUMP CUT changes the framing.

    A jump cut is not fixed by making it softer — a dissolve between two
    positions of the same face advertises the discontinuity. It's fixed by
    DECLARING it: the framing changes across the seam, so the eye reads "that
    was an edit" instead of "that was a glitch". Every vlog you've ever enjoyed
    does this.

    Scene changes are left alone. They don't need help.
    """
    scales = [1.0]
    print("  seams:", flush=True)
    for i in range(1, len(render)):
        s = seam_ssim(video, render[i - 1][1], render[i][0], work)
        jump = s >= JUMP_SSIM
        # alternate the framing ONLY across jump cuts; a scene change resets it
        scales.append(PUNCH if (jump and scales[-1] == 1.0) else 1.0)
        print(f"    {'JUMP  ' if jump else 'scene '} ssim={s:.2f}"
              f"{'  -> punch ' + str(round(scales[-1], 3)) if jump else ''}", flush=True)
    return scales


def crop_9x16(video: Path, crop_x=0.5) -> str:
    """9:16 crop. `crop_x` is where the keep-window sits horizontally: 0.0 = hard
    left, 0.5 = centre, 1.0 = hard right.

    There is no face detection here on purpose. The agent driving this tool can
    SEE — every render drops a preview frame, so it looks at the framing and
    shifts crop_x if the speaker is off-centre. That beats bolting OpenCV onto a
    non-technical user's machine to solve a problem a pair of eyes solves free.

    Numbers computed here, not in ffmpeg's expression language: an expression
    like min(iw,ih*9/16) contains a comma, which the filtergraph parser eats as a
    filter separator.
    """
    w, h = (int(x) for x in probe(video, "stream=width,height", "v:0").split(",")[:2])
    if w / h > 9 / 16:
        cw, ch = int(h * 9 / 16), h
    else:
        cw, ch = w, int(w * 16 / 9)
    cw -= cw % 2
    ch -= ch % 2
    x = int((w - cw) * min(max(crop_x, 0.0), 1.0))
    x -= x % 2
    return f"crop={cw}:{ch}:{x}:{(h - ch) // 2},scale=1080:1920"


def join(parts, out: Path, work: Path, fps, use_xfade):
    """Hard cut by default. A dissolve between two positions of the same face
    tends to advertise the discontinuity rather than hide it; short-form lives on
    hard cuts. --xfade exists for footage where a dissolve genuinely reads better."""
    if len(parts) == 1:
        shutil.copy2(parts[0], out)
        return

    durs = [duration_of(p) for p in parts]
    if not use_xfade or min(durs) <= XFADE * 2:
        # The concat FILTER, not the concat demuxer with -c copy.
        #
        # Each part is encoded to AAC independently, and AAC carries ~1024
        # samples of encoder priming. Stitching those with `-c copy` splices the
        # priming in too: a ~50ms DROPOUT at every seam. Measured -90dB holes at
        # all 20 cuts of a finished vlog — audible as the audio briefly falling
        # out. The demuxer is faster and it is quietly wrong.
        #
        # Decoding and re-encoding the audio as ONE continuous stream removes
        # every gap. Costs one video re-encode. Worth it.
        cmd = ["ffmpeg", "-v", "error", "-y"]
        for p in parts:
            cmd += ["-i", str(p)]
        streams = "".join(f"[{i}:v][{i}:a]" for i in range(len(parts)))
        cmd += ["-filter_complex", f"{streams}concat=n={len(parts)}:v=1:a=1[v][a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(fps),
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)]
        run(cmd)
        return

    offsets, acc = [], 0.0
    for i in range(1, len(parts)):
        acc += durs[i - 1]
        offsets.append(acc - i * XFADE)

    vf, af, v_prev, a_prev = [], [], "0:v", "0:a"
    for i in range(1, len(parts)):
        v_out, a_out = f"v{i}", f"a{i}"
        vf.append(f"[{v_prev}][{i}:v]xfade=transition=fade:duration={XFADE}"
                  f":offset={offsets[i - 1]:.3f}[{v_out}]")
        af.append(f"[{a_prev}][{i}:a]acrossfade=d={XFADE}[{a_out}]")
        v_prev, a_prev = v_out, a_out

    cmd = ["ffmpeg", "-v", "error", "-y"]
    for p in parts:
        cmd += ["-i", str(p)]
    cmd += ["-filter_complex", ";".join(vf + af),
            "-map", f"[{v_prev}]", "-map", f"[{a_prev}]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(out)]
    run(cmd)


def apply_broll(out: Path, brolls, work: Path, fps, vertical):
    """Cut away to other footage while HER AUDIO KEEPS RUNNING.

    This is the audio bridge, and it's the only honest way to add B-roll to a
    confessional: the voice never breaks, so the intimacy survives, but the eye
    gets something new. Never mute the speaker to show a stock clip — that's how
    you get a video that looks produced and says nothing.

    B-roll should be the CREATOR'S OWN footage, cued to a moment where they name
    something concrete ("I posted a video behind Zedd"). Generated/stock filler
    over a personal story is the slop we're trying to avoid.
    """
    w, h = (1080, 1920) if vertical else (1920, 1080)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(out.resolve())]
    filters, prev = [], "0:v"

    for i, (t, dur, path) in enumerate(brolls, start=1):
        src = Path(path).expanduser()
        if not src.exists():
            sys.exit(f"b-roll not found: {src}")
        cmd += ["-i", str(src.resolve())]
        filters.append(
            f"[{i}:v]trim=0:{dur},setpts=PTS-STARTPTS+{t}/TB,"
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},fps={fps}[b{i}]"
        )
        # enable= window, so the cutaway appears only for its span. Audio is
        # never touched — we map 0:a straight through below.
        filters.append(
            f"[{prev}][b{i}]overlay=0:0:enable='between(t,{t},{t + dur})'[v{i}]")
        prev = f"v{i}"
        print(f"  b-roll @ {t:.1f}s for {dur:.1f}s: {src.name}", flush=True)

    final = work / f"{out.stem}-broll.mp4"
    cmd += ["-filter_complex", ";".join(filters),
            "-map", f"[{prev}]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "copy", final.name]
    run(cmd, cwd=work)
    shutil.move(final, out)


def apply_overlay(out: Path, overlays, work: Path, fps, vertical):
    """Composite an ALPHA motion graphic OVER the footage — she stays visible
    underneath. This is different from --broll, which replaces the frame.

    Source must carry a real alpha channel. Render it from Remotion or
    Hyperframes as **ProRes 4444 (.mov)** — `--format webm` comes out yuv420p
    (opaque) and will paste a black box over her face. Check with:
        ffprobe -show_entries stream=pix_fmt   ->  want yuva*, not yuv420p
    """
    w, h = (1080, 1920) if vertical else (1920, 1080)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(out.resolve())]
    filters, prev = [], "0:v"

    for i, (t, dur, path) in enumerate(overlays, start=1):
        src = Path(path).expanduser()
        if not src.exists():
            sys.exit(f"overlay not found: {src}")
        pix = probe(src, "stream=pix_fmt", "v:0")
        if not pix.startswith("yuva") and "argb" not in pix and "rgba" not in pix:
            sys.exit(f"overlay '{src.name}' has no alpha channel (pix_fmt={pix}).\n"
                     f"Re-render it as ProRes 4444 .mov — an opaque overlay will "
                     f"paste a solid box over the speaker.")
        cmd += ["-i", str(src.resolve())]
        # format=yuva420p keeps alpha alive through the scale.
        filters.append(
            f"[{i}:v]trim=0:{dur},setpts=PTS-STARTPTS+{t}/TB,"
            f"scale={w}:{h},format=yuva420p,fps={fps}[g{i}]")
        filters.append(
            f"[{prev}][g{i}]overlay=0:0:enable='between(t,{t},{t + dur})'[v{i}]")
        prev = f"v{i}"
        print(f"  overlay @ {t:.1f}s for {dur:.1f}s: {src.name}  (alpha: {pix})", flush=True)

    final = work / f"{out.stem}-ov.mp4"
    cmd += ["-filter_complex", ";".join(filters),
            "-map", f"[{prev}]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "copy", final.name]
    run(cmd, cwd=work)
    shutil.move(final, out)


def apply_sfx(out: Path, sfx, work: Path):
    """Mix sound effects UNDER the speaker's voice at given timestamps.

    Motion graphics rendered from Remotion/HyperFrames come out SILENT — the
    overlay is a video track with no audio. A notification popping in with no
    sound reads as a bug, not a choice. The pops are half the effect.

    amix with normalize=0 is load-bearing: the default normalize=1 divides every
    input by N, so adding two blips would quietly duck her voice by ~10dB.
    """
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(out.resolve())]
    filters, labels = [], []

    for i, (t, gain, path) in enumerate(sfx, start=1):
        src = Path(path).expanduser()
        if not src.exists():
            sys.exit(f"sfx not found: {src}")
        cmd += ["-i", str(src.resolve())]
        filters.append(f"[{i}:a]adelay={int(t * 1000)}:all=1,volume={gain}[s{i}]")
        labels.append(f"[s{i}]")

    filters.append(
        f"[0:a]{''.join(labels)}amix=inputs={len(sfx) + 1}:duration=first"
        f":normalize=0[aout]")   # mix only. Loudness is normalised LAST, on the
                                 # FINAL mix — see finalize_audio().

    final = work / f"{out.stem}-sfx.mp4"
    cmd += ["-filter_complex", ";".join(filters),
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", final.name]
    run(cmd, cwd=work)
    shutil.move(final, out)
    print(f"  mixed {len(sfx)} sfx under the voice", flush=True)


def finalize_audio(out: Path, work: Path):
    """Normalise loudness LAST, on the FINAL mix.

    Running loudnorm before mixing the SFX is the classic ordering bug: you
    normalise to -14 LUFS, then ADD sound effects on top, and the finished file
    lands at -13.3 LUFS with true peak at -0.2 dBTP. Over -1.0 dBTP causes
    audible distortion on lossy playback (YouTube re-encodes everything).

    The last thing that touches the audio must be the thing that measures it.
    """
    TARGET_I, TARGET_TP, TARGET_LRA = -14.0, -2.5, 11.0

    # TWO PASSES. Single-pass loudnorm runs in DYNAMIC mode: it guesses as it
    # goes, overshoots, and lands wherever it lands. Measured -12.9 LUFS and
    # -0.0 dBTP on a file asked for -14/-1.5 — i.e. clipping. Pass 1 MEASURES the
    # file; pass 2 applies those measurements in LINEAR mode, which is exact.
    p = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(out.resolve()),
         "-af", f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
         "-f", "null", "-"], capture_output=True, text=True)
    blob = p.stdout + p.stderr
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", blob, re.S)
    if not m:
        print("  loudnorm: measurement pass produced no JSON — skipping", flush=True)
        return
    d = json.loads(m.group(0))

    af = (f"loudnorm=I={TARGET_I}:TP={TARGET_TP}:LRA={TARGET_LRA}"
          f":measured_I={d['input_i']}:measured_TP={d['input_tp']}"
          f":measured_LRA={d['input_lra']}:measured_thresh={d['input_thresh']}"
          f":offset={d['target_offset']}:linear=true:print_format=summary")

    final = work / f"{out.stem}-ln.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(out.resolve()),
         "-af", af,
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", final.name],
        cwd=work)
    shutil.move(final, out)
    print(f"  loudness: {d['input_i']} -> {TARGET_I} LUFS (2-pass, linear)", flush=True)


def make_card(clip: Path, t, dur, text, work: Path, fps, vertical) -> Path:
    """Generate an animated text card FROM THE CLIP'S OWN FRAMES — for creators
    who have no B-roll.

    The background is their own footage at that moment, blurred and darkened, so
    the card stays inside their world instead of dropping in a foreign template
    slide. The text scales and fades up. Audio bridges straight through it (the
    caller overlays this like B-roll), so their voice never breaks.

    The text should be THEIR OWN WORDS — the claim they are making right now.
    This is kinetic typography, not a title card: we are emphasising what they
    said, not speaking for them.
    """
    w, h = (1080, 1920) if vertical else (1920, 1080)
    card = work / f"card-{t:.0f}.mp4"
    ass = work / f"card-{t:.0f}.ass"

    body = ass_escape(text).upper()
    # Scale down for longer phrases so a sentence doesn't overflow the frame.
    n = len(body)
    size = (190 if n <= 6 else 140 if n <= 18 else 100) if vertical else 90
    # \fad = fade in/out. \t(...\fscx/\fscy) = scale up over the first 400ms, so
    # the words arrive with a push instead of just appearing.
    anim = r"{\fad(180,220)\fscx88\fscy88\t(0,400,\fscx100\fscy100)}"
    ass.write_text("\n".join([
        "[Script Info]", "ScriptType: v4.00+",
        f"PlayResX: {w}", f"PlayResY: {h}", "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,"
        "Bold,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: Card,Helvetica,{size},&H00FFFFFF,&H00000000,&H00000000,"
        f"-1,1,0,0,5,90,90,90,1", "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
        f"Dialogue: 0,0:00:00.00,{ts(dur)},Card,,0,0,0,,{anim}{body}",
    ]), encoding="utf-8")

    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-t", f"{dur:.3f}",
         "-i", str(clip.resolve()),
         # Blurred + dimmed, but she must still be READABLE underneath — that's
         # what keeps the card hers instead of a template slide dropped on top.
         "-vf", f"gblur=sigma=22,eq=brightness=-0.12:saturation=0.6,"
                f"subtitles={ass.name},fps={fps}",
         "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", card.name], cwd=work)
    print(f"  card @ {t:.1f}s for {dur:.1f}s: \"{text}\"", flush=True)
    return card


def cut(work: Path, spans, out_name, vertical, captions, do_tighten=False,
        emphasize=(), hook="", push=False, use_xfade=False, max_gap=MAX_GAP,
        loudnorm=True, crop_x=0.5, brolls=(), cards=(), overlays=(), sfx=(),
        declare=True):
    need("ffmpeg")
    meta = json.loads((work / "transcript.json").read_text())
    segs = meta["segments"]
    video = work / meta["video"]
    duration = float(meta["duration"])
    fps = source_fps(video)

    if do_tighten and not any(s.get("words") for s in segs):
        sys.exit("--tighten needs word-level timings; re-run `prep --whisper` "
                 f"(this transcript came from {meta.get('method')})")

    # Validate the RAW bounds. Doing it after padding means "5:5" silently
    # renders a half-second clip and "0:9999" silently clamps to the whole video.
    for i, (raw_a, raw_b) in enumerate(spans):
        if raw_b <= raw_a:
            sys.exit(f"clip {i}: end ({raw_b}) must be after start ({raw_a})")
        if raw_a < 0 or raw_b > duration + 0.5:
            sys.exit(f"clip {i}: {raw_a}–{raw_b}s is outside the source "
                     f"(0–{duration:.1f}s)")

    wb = word_bounds(segs)
    render = []
    for raw_a, raw_b in spans:
        a, b = pad_into_silence(raw_a, raw_b, wb, duration)
        if (a, b) != (max(0.0, raw_a - PAD_HEAD), min(duration, raw_b + PAD_TAIL)):
            print(f"  snap {raw_a:.2f}-{raw_b:.2f} -> {a:.2f}-{b:.2f} "
                  f"(a cut may not land inside a word)", flush=True)
        if do_tighten:
            subs, n_fill, secs = tighten(segs, a, b, max_gap)
            print(f"  tighten {a:.1f}-{b:.1f}s: -{n_fill} filler, "
                  f"-{secs:.1f}s dead air -> {len(subs)} sub-cut(s)", flush=True)
            render.extend(subs)
        else:
            render.append((a, b))

    parts_dir = work / "parts"
    if parts_dir.exists():
        shutil.rmtree(parts_dir)
    parts_dir.mkdir()

    # A jump cut is DECLARED with a framing change, not softened with a
    # dissolve. Detect which seams are same-shot and punch the framing across
    # them so the eye reads "edit", not "glitch".
    scales = declare_seams(video, render, work) if (declare and len(render) > 1) else [1.0] * len(render)

    crop = crop_9x16(video, crop_x) if vertical else None
    parts = []
    for i, (a, b) in enumerate(render):
        part = parts_dir / f"part{i:04d}.mp4"
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}",
               "-i", str(video.resolve())]
        vfx = []
        if crop:
            vfx.append(crop)
        if scales[i] != 1.0:
            ow, oh = (1080, 1920) if vertical else (
                tuple(int(x) for x in probe(video, "stream=width,height", "v:0").split(",")[:2]))
            ow -= ow % 2
            oh -= oh % 2
            z = scales[i]
            vfx.append(f"scale={int(ow * z) // 2 * 2}:{int(oh * z) // 2 * 2},crop={ow}:{oh}")
        # setsar=1 on EVERY part, always. The punch-in scale leaves a fractional
        # SAR (2276:2277) on punched parts while unpunched parts stay 1:1, and
        # the concat filter refuses to join streams whose parameters differ:
        # "Input link parameters do not match". Normalise it or the join dies.
        vfx.append("setsar=1")
        cmd += ["-vf", ",".join(vfx)]
        # Re-encode, not stream-copy: a copy snaps each cut to the nearest
        # keyframe and drifts it off the words we chose.
        # A CLICK at a cut is an amplitude discontinuity — the waveform jumps.
        # Measured 22dB and 20dB jumps on a finished vlog: audible pops.
        #
        # An acrossfade would fix it but OVERLAPS, shortening the audio by d at
        # every seam while the video concat does not — that desyncs. A 20ms fade
        # at each PART EDGE removes the discontinuity with zero length change.
        # Inaudible as a fade; the pop is gone.
        seg = max(0.06, b - a)
        cmd += ["-af", f"afade=t=in:st=0:d=0.02,"
                       f"afade=t=out:st={seg - 0.02:.3f}:d=0.02"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(fps),
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", part.name]
        run(cmd, cwd=parts_dir)
        parts.append(part)
        print(f"  render {i}: {a:.2f}–{b:.2f}s", flush=True)

    out = work / f"{out_name}.mp4"
    join(parts, out, parts_dir, fps, use_xfade)

    # Generated cards are just B-roll we made ourselves — same audio bridge, same
    # overlay path. Built from the assembled clip so they inherit its framing.
    inserts = list(brolls)
    for t, dur, text in cards:
        inserts.append((t, dur, str(make_card(out, t, dur, text, work, fps, vertical))))

    # Inserts go on BEFORE captions, so captions stay legible on top of the
    # cutaway. A cutaway that hides the words defeats the point of the words.
    if inserts:
        apply_broll(out, sorted(inserts), work, fps, vertical)

    # Alpha graphics composite OVER her (she stays visible), unlike b-roll which
    # replaces the frame. Still before captions, so captions read on top.
    if overlays:
        apply_overlay(out, sorted(overlays), work, fps, vertical)

    # Where each source span landed on the finished timeline — this is what lets
    # captions be burned last, over the assembled clip.
    offsets, acc = [], 0.0
    for i, (a, b) in enumerate(render):
        offsets.append(acc - (i * XFADE if use_xfade and len(parts) > 1 else 0))
        acc += b - a
    clip_len = duration_of(out)

    vf, af = [], []
    if push:
        rate = (PUSH_ZOOM - 1.0) / max(1, clip_len * fps)
        w, h = (1080, 1920) if vertical else (1920, 1080)
        vf.append(f"zoompan=z='min(1+{rate:.8f}*on,{PUSH_ZOOM})':d=1"
                  f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps}")
    if captions:
        ass = work / f"{out_name}.ass"
        write_ass(timeline_cues(segs, render, offsets, clip_len), ass,
                  vertical, emphasize, hook)
        # AFTER zoompan, so the captions are never zoomed with the picture.
        vf.append(f"subtitles={ass.name}")
    # NOTE: loudness is NOT normalised here. It happens LAST, after the SFX are
    # mixed — see finalize_audio(). Normalising a mix you are about to add to is
    # how a file ends up at -13.3 LUFS / -0.2 dBTP.

    if vf or af:
        final = work / f"{out_name}-final.mp4"
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(out.resolve())]
        if vf:
            cmd += ["-vf", ",".join(vf)]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(fps)]
        if af:
            cmd += ["-af", ",".join(af), "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        else:
            cmd += ["-c:a", "copy"]
        cmd += [final.name]
        run(cmd, cwd=work)
        shutil.move(final, out)

    if sfx:
        apply_sfx(out, sfx, work)

    if loudnorm:
        finalize_audio(out, work)

    # Edit map: where each SOURCE span ended up in the FINISHED video. Chapter
    # markers and YouTube timestamps must be in output time — --tighten removes
    # time, so a source timestamp is NOT where the viewer lands.
    edl = work / f"{out_name}.edl.json"
    edl.write_text(json.dumps({
        "output": out.name,
        "output_duration": duration_of(out),
        "spans": [
            {"source_start": round(a, 2), "source_end": round(b, 2),
             "output_start": round(o, 2), "output_end": round(o + (b - a), 2)}
            for (a, b), o in zip(render, offsets)
        ],
    }, indent=2))

    # Always drop a preview. This is how framing gets checked: the agent LOOKS.
    # A centre-crop silently decapitating an off-centre speaker is the worst
    # failure this tool has.
    #
    # THREE frames, not one. A single early frame is a useless sample of a
    # MOVING subject — it misread a wide shot of someone doing plyometrics as
    # correctly framed when she was jumping in and out of the crop window.
    # Start / middle / end, stacked into one contact sheet.
    preview = work / f"{out_name}-frame.jpg"
    d = duration_of(out)
    stamps = [d * 0.12, d * 0.5, d * 0.88]
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for s in stamps:
        cmd += ["-ss", f"{s:.2f}", "-i", str(out.resolve())]
    cmd += ["-filter_complex",
            "[0:v]scale=360:-1[a];[1:v]scale=360:-1[b];[2:v]scale=360:-1[c];[a][b][c]hstack=3",
            "-frames:v", "1", preview.name]
    run(cmd, cwd=work)

    print(f"\n{out}  ({duration_of(out):.1f}s, {fps}fps)")
    print(f"preview frame: {preview}   <- LOOK AT THIS. If the speaker is cropped "
          f"badly, re-run with --crop-x (0=left, 0.5=centre, 1=right).")
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

    c = sub.add_parser("cut", help="render the selected moments")
    c.add_argument("work", help="working dir from prep")
    c.add_argument("--clips", required=True,
                   help="comma-separated start:end in seconds, e.g. 12.4:31.0,88:104.5")
    c.add_argument("--out", default="clip", help="output basename")
    c.add_argument("--vertical", action="store_true", help="9:16 center-crop for Shorts/Reels")
    c.add_argument("--captions", action="store_true", help="burn in captions")
    c.add_argument("--tighten", action="store_true",
                   help="drop filler words + dead air INSIDE each clip (needs prep --whisper)")
    c.add_argument("--max-gap", type=float, default=MAX_GAP,
                   help=f"silence longer than this is dead air (default {MAX_GAP}s). "
                        "Raise it to protect emotional pauses.")
    c.add_argument("--emphasize", default="",
                   help="comma-separated words to amber in the captions (off by default)")
    c.add_argument("--hook", default="",
                   help="hook text over the first 2.5s. ONLY when the creator asks for it.")
    c.add_argument("--push", action="store_true", help="slow continuous zoom (subtle)")
    c.add_argument("--no-declare", action="store_true",
                   help="leave raw hard cuts. By default every JUMP CUT (a seam "
                        "back into the same shot) gets a small framing change, so "
                        "the eye reads 'edit' instead of 'glitch'.")
    c.add_argument("--xfade", action="store_true",
                   help="crossfade seams instead of hard-cutting them")
    c.add_argument("--no-loudnorm", action="store_true", help="skip loudness normalisation")
    c.add_argument("--crop-x", type=float, default=0.5,
                   help="horizontal crop position: 0=left, 0.5=centre, 1=right. "
                        "Check the preview frame and shift this if the speaker is cut off.")
    c.add_argument("--broll", default="",
                   help="cutaways, keeping her audio running: "
                        "'START:DURATION:/path/clip.mp4' — comma-separated for several")
    c.add_argument("--overlay", action="append", default=[],
                   help="alpha motion graphic composited OVER the speaker: "
                        "'START:DURATION:/path/graphic.mov'. Must be ProRes 4444 "
                        "(.mov) — webm/mp4 have no alpha. Repeatable.")
    c.add_argument("--sfx", action="append", default=[],
                   help="sound effect under the voice: 'TIME:GAIN:/path/sound.wav' "
                        "(gain 0.0-1.0). Motion graphics render silent — add the pops. "
                        "Repeatable.")
    c.add_argument("--card", action="append", default=[],
                   help="generated text cutaway for creators with no b-roll: "
                        "'START:DURATION:THEIR OWN WORDS'. Repeatable.")

    a = ap.parse_args()

    if a.cmd == "prep":
        work = Path(a.work) if a.work else Path("clip-work") / re.sub(
            r"[^a-zA-Z0-9]+", "-", Path(a.source).stem or "video")[:40].strip("-")
        work = work.expanduser().resolve()
        video = acquire(a.source, work)
        segs, method = transcribe(video, work, a.whisper)
        if not segs:
            sys.exit("no transcript produced — is there any speech in this video?")

        dur = duration_of(video)
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
        brolls = []
        for spec in filter(None, (s.strip() for s in a.broll.split(","))):
            t, _, rest = spec.partition(":")
            dur, _, path = rest.partition(":")   # path may itself contain ':'
            if not path:
                sys.exit(f"--broll needs START:DURATION:PATH, got: {spec}")
            brolls.append((float(t), float(dur), path))
        cards = []
        for spec in a.card:
            t, _, rest = spec.partition(":")
            dur, _, text = rest.partition(":")
            if not text:
                sys.exit(f"--card needs START:DURATION:TEXT, got: {spec}")
            cards.append((float(t), float(dur), text))
        overlays = []
        for spec in a.overlay:
            t, _, rest = spec.partition(":")
            dur, _, path = rest.partition(":")
            if not path:
                sys.exit(f"--overlay needs START:DURATION:PATH, got: {spec}")
            overlays.append((float(t), float(dur), path))
        sfx = []
        for spec in a.sfx:
            t, _, rest = spec.partition(":")
            gain, _, path = rest.partition(":")
            if not path:
                sys.exit(f"--sfx needs TIME:GAIN:PATH, got: {spec}")
            sfx.append((float(t), float(gain), path))
        cut(Path(a.work).expanduser().resolve(), spans, a.out,
            a.vertical, a.captions, a.tighten, emph, a.hook, a.push,
            a.xfade, a.max_gap, not a.no_loudnorm, a.crop_x, brolls, cards,
            overlays, sfx, not a.no_declare)


if __name__ == "__main__":
    main()
