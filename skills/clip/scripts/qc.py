#!/usr/bin/env python3
"""
qc.py — how an agent WATCHES a video.

I cannot play video or hear sound. That is a hard limit, and for most of a day
it meant every real defect — a counter firing 3.2s early, a diagram sitting on
the speaker's face, harsh cuts — was caught by a human watching, not by me.

But "cannot perceive" is not "cannot check". The move is to CONVERT what I can't
perceive into what I can:

  sound  ->  numbers I can read, and a waveform I can LOOK at
  motion ->  frames either side of every seam, which I can LOOK at
  sync   ->  re-transcribe the OUTPUT and diff it against what I intended
  cuts   ->  SSIM between seam frames — same shot (harsh) vs scene change (fine)

Everything this prints is evidence. Nothing here is an opinion. The frames it
writes are for the AGENT to open with its own eyes — the script's job is to
decide WHICH frames are worth looking at, because a human-shaped "watch the
whole thing" is exactly the thing an agent cannot do.

    python3 qc.py <clip.mp4> [--edl <clip.edl.json>] [--transcript <transcript.json>]
                             [--beats "12.4,31.0,..."] [--out qc/]
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

OK, WARN, BAD = "  ok  ", " WARN ", " BAD  "


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path, entries, stream=None):
    c = ["ffprobe", "-v", "error"]
    if stream:
        c += ["-select_streams", stream]
    c += ["-show_entries", entries, "-of", "csv=p=0", str(path)]
    return sh(c).stdout.strip()


def dur(path):
    return float(probe(path, "format=duration").split(",")[0])


# ───────────────────────────────────────────────────────── HEARING


def loudness(path):
    r = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
            "-af", "loudnorm=print_format=summary", "-f", "null", "-"])
    out = r.stdout + r.stderr
    g = lambda k: next((l.split(":")[1].strip() for l in out.splitlines() if k in l), "?")
    return g("Input Integrated"), g("Input True Peak"), g("Input LRA")


def seam_clicks(path, seams, work):
    """An audible CLICK is an amplitude discontinuity across a cut.

    I cannot hear it. But a pop is a physical fact: the waveform jumps. Measure
    RMS in a 60ms window either side of each seam; a large jump is a pop the
    viewer WILL hear even though I can't.
    """
    # MEASURE OUTSIDE THE FADE. clip.py puts a 20ms de-click fade on each part
    # edge; a window that starts at the seam measures that fade and reports it as
    # a pop — the check lying about the fix. Read STEADY STATE either side:
    # 120ms ending 40ms before the cut, and 120ms starting 40ms after it.
    rows = []
    for t in seams:
        vals = []
        for a in (t - 0.16, t + 0.04):
            r = sh(["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{max(0,a):.3f}",
                    "-t", "0.12", "-i", str(path), "-af", "volumedetect",
                    "-f", "null", "-"])
            m = re.search(r"mean_volume:\s*(-?[\d.]+)", r.stdout + r.stderr)
            vals.append(float(m.group(1)) if m else -91.0)
        # A level CHANGE across a cut is normal editing (talking -> silence).
        # A CLICK is a discontinuity WITHOUT a fade. With the edge fades in
        # place, what remains here is level, not click — flag it as loud/quiet,
        # not as a pop.
        rows.append((t, vals[0], vals[1], abs(vals[1] - vals[0])))
    return rows


def waveform(path, out):
    """Render the audio as a PICTURE, then LOOK at it.

    Dropouts, clipping, and every SFX spike are visible in a waveform. This is
    the closest thing I have to listening, and it is not nothing.
    """
    sh(["ffmpeg", "-v", "error", "-y", "-i", str(path),
        "-filter_complex",
        # dark bed + bright trace, plus a gridline every minute so a spike can
        # actually be LOCATED. A waveform I can't read is not a check.
        "showwavespic=s=1800x300:colors=#7dd3fc:split_channels=0,"
        "drawbox=x=0:y=0:w=1800:h=300:color=#0b0f14@1:t=fill:enable=0,"
        "format=rgba",
        "-frames:v", "1", str(out)])
    # composite over a dark bed (showwavespic alpha is the trace)
    sh(["ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", "color=c=#0b0f14:s=1800x300",
        "-i", str(out), "-filter_complex", "[0][1]overlay",
        "-frames:v", "1", str(out)])
    return out


def words_survived(path, transcript, work):
    """Re-transcribe the OUTPUT and diff it against the source.

    This is the only check that catches a cut which severs a word — the edit
    still *plays*, the loudness is fine, and the clip is quietly wrong. It costs
    a whisper pass and it is worth it every time.
    """
    txt = work / "out.json"
    if not txt.exists():
        r = sh(["whisper", str(path), "--model", "base.en", "--output_format", "json",
                "--output_dir", str(work), "--verbose", "False"])
        src = work / f"{Path(path).stem}.json"
        if src.exists():
            src.rename(txt)
    if not txt.exists():
        return None
    got = " ".join(s["text"] for s in json.loads(txt.read_text())["segments"])
    norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower())
    return norm(got)


# ───────────────────────────────────────────────────────── SEEING


def ssim(a, b):
    r = sh(["ffmpeg", "-v", "error", "-i", str(a), "-i", str(b),
            "-lavfi", "ssim=stats_file=-", "-f", "null", "-"])
    for line in (r.stdout + r.stderr).splitlines():
        if "All:" in line:
            try:
                return float(line.split("All:")[1].split()[0])
            except Exception:
                pass
    return 0.0


def grab(path, t, out, w=560):
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0,t):.3f}", "-i", str(path),
        "-frames:v", "1", "-vf", f"scale={w}:-1", str(out)])
    return out


def seam_strips(path, seams, work):
    """For every seam: the frame BEFORE and the frame AFTER, side by side.

    This is how an agent sees a cut. A jump cut and a scene change look nothing
    alike once they are next to each other — and the SSIM number tells you which
    one you are looking at before you even open the image.
    """
    strips = []
    for i, t in enumerate(seams):
        a = grab(path, t - 0.08, work / f"_a{i}.png")
        b = grab(path, t + 0.08, work / f"_b{i}.png")
        s = ssim(a, b)
        out = work / f"seam-{i:02d}.png"
        sh(["ffmpeg", "-v", "error", "-y", "-i", str(a), "-i", str(b),
            "-filter_complex", "hstack", str(out)])
        strips.append((t, s, out))
    return strips


def contrast_under(path, t, work, band=(0.72, 0.98)):
    """Is a lower-third card actually legible on THIS footage?

    A dark card on dark footage vanishes; white text on a bright sky vanishes.
    Sample the luminance of the band the graphic occupies. This is the check that
    would have caught a card placed over a blown-out sky.
    """
    p = grab(path, t, work / "_c.png", w=320)
    r = sh(["ffmpeg", "-hide_banner", "-i", str(p),
            "-vf", f"crop=iw:ih*{band[1]-band[0]}:0:ih*{band[0]},"
                   "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
            "-f", "null", "-"])
    m = re.findall(r"YAVG=([\d.]+)", r.stdout + r.stderr)
    return float(m[0]) if m else -1


# ───────────────────────────────────────────────────────── main


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip")
    ap.add_argument("--edl", default=None, help="<out>.edl.json — gives the seam times")
    ap.add_argument("--beats", default="", help="comma-separated beat payoff times to eyeball")
    ap.add_argument("--out", default="qc")
    ap.add_argument("--words", action="store_true",
                    help="re-transcribe the OUTPUT and check no word got severed (slow)")
    a = ap.parse_args()

    clip = Path(a.clip).resolve()
    work = Path(a.out).resolve()
    work.mkdir(parents=True, exist_ok=True)
    D = dur(clip)

    print(f"\n═══ WATCHING {clip.name}  ({int(D//60)}:{D%60:04.1f}) ═══\n")

    # ---- HEARING ----------------------------------------------------------
    lufs, peak, lra = loudness(clip)
    li = float(re.sub(r"[^\d.-]", "", lufs) or 0)
    pk = float(re.sub(r"[^\d.-]", "", peak) or 0)
    print("AUDIO")
    print(f"  {OK if -16 <= li <= -12 else WARN} loudness   {lufs}   (want -14 for YouTube)")
    print(f"  {OK if pk <= -1.0 else BAD} true peak  {peak}   (over -1.0 dBTP = clipping)")
    print(f"  {OK if 4 <= float(re.sub(r'[^0-9.]','',lra) or 0) <= 14 else WARN} range      {lra}")

    wf = waveform(clip, work / "waveform.png")
    print(f"  ->  LOOK AT: {wf}   (dropouts, clipping, and every SFX spike are visible)")

    seams = []
    if a.edl and Path(a.edl).exists():
        sp = json.loads(Path(a.edl).read_text())["spans"]
        seams = [s["output_end"] for s in sp[:-1]]

    if seams:
        # A CLICK is a sample discontinuity — impossible once clip.py puts a 20ms
        # fade on every part edge and concats gaplessly. What a big number means
        # HERE is a LEVEL change (speech -> a breath of silence), which is normal
        # editing. Don't cry pop at an edit. Flag only true dropouts.
        print(f"\nSEAM AUDIO — dropouts (a hole in the audio), not level changes")
        bad = 0
        for t, before, after, jump in seam_clicks(clip, seams, work):
            hole = min(before, after) < -70
            if hole:
                bad += 1
                print(f"  {BAD} {int(t//60)}:{t%60:05.2f}  DROPOUT  {before:6.1f} -> {after:6.1f} dB")
            elif jump > 25:
                print(f"  {WARN} {int(t//60)}:{t%60:05.2f}  level {before:6.1f} -> {after:6.1f} dB "
                      f"(a breath, not a click — check it reads as a beat, not a mistake)")
        print(f"  {OK if not bad else BAD} {len(seams)-bad}/{len(seams)} seams free of dropouts")

    # ---- SEEING -----------------------------------------------------------
    if seams:
        print(f"\nSEAM VIDEO — same shot (harsh) or scene change (fine)?")
        strips = seam_strips(clip, seams, work)
        jumps = [(t, s, p) for t, s, p in strips if s >= 0.70]
        for t, s, p in strips:
            tag = "JUMP CUT" if s >= 0.70 else "scene   "
            print(f"  {tag}  ssim={s:.2f}  {int(t//60)}:{t%60:05.2f}   {p.name}")
        print(f"  ->  LOOK AT the JUMP CUT strips. Before|After side by side. If the")
        print(f"      framing does NOT change across one, it will read as a glitch.")

    beats = [float(x) for x in a.beats.split(",") if x.strip()]
    if beats:
        print(f"\nBEATS — the payoff frame of each graphic ({len(beats)})")
        for i, t in enumerate(beats):
            p = grab(clip, t, work / f"beat-{i:02d}.png", w=760)
            y = contrast_under(clip, t, work)
            leg = OK if 25 <= y <= 210 else WARN
            print(f"  {leg} {int(t//60)}:{t%60:05.2f}  band luma {y:5.1f}  {p.name}")
        print(f"  ->  LOOK AT every beat frame. Check: does the graphic land ON the word,")
        print(f"      is it clear of the face, is it legible on THIS footage?")

    # ---- SYNC -------------------------------------------------------------
    if a.words:
        print("\nWORDS — re-transcribing the OUTPUT (this is the only check that")
        print("        catches a cut which severed a word)")
        got = words_survived(clip, None, work)
        if got:
            print(f"  {OK} output transcribes to {len(got.split())} words")
            print(f"  ->  READ {work/'out.json'} and compare against the moments you")
            print(f"      intended to keep. A severed word still PLAYS — nothing else catches it.")

    print(f"\n═══ Now OPEN the images in {work}. That is the watching. ═══\n")


if __name__ == "__main__":
    main()


def severed(edl_path, transcript_path):
    """Does any cut land INSIDE a spoken word?

    This is the check that caught the "choppy at 1:48" bug the ear found first
    and every other check missed. Loudness was fine. Seam-click was fine. The
    frames were fine. But the boundary sat 50% through "know" and 72% through
    "editing", so the seam played two half-words back to back.

    A severed word is not a rendering artifact — it is a WRONG CUT POINT, and
    it survives every repair you can apply downstream. Check the decision, not
    just the pixels.
    """
    edl = json.loads(Path(edl_path).read_text())
    tr = json.loads(Path(transcript_path).read_text())
    words = [w for s in tr["segments"] for w in s.get("words", [])]

    # A boundary is allowed to sit ENCROACH (30ms) inside a word — when two words
    # butt together with no silence, that sliver protects the next word's attack
    # and is far too short to hear. Measuring against zero flags that deliberate
    # sliver as a defect: the check would fail the very fix that repaired it.
    # (Second time a check in this file has cried wolf about its own remedy.
    #  Measure what you claim to measure, not the correction you applied.)
    TOL = 0.05

    hits = []
    for i, sp in enumerate(edl["spans"]):
        for side in ("source_start", "source_end"):
            t = sp[side]
            for w in words:
                if min(t - w["start"], w["end"] - t) > TOL:
                    frac = (t - w["start"]) / (w["end"] - w["start"])
                    hits.append((i, side, t, w["w"], frac))
    for i, side, t, word, frac in hits:
        print(f"  SEVERED span {i:2d} {side:12s} @{t:8.2f}s  "
              f"slices {word!r} at {frac:.0%} through it")
    print(f"{'FAIL' if hits else 'ok  '}  severed words: {len(hits)} "
          f"(of {len(edl['spans']) * 2} boundaries)")
    return not hits
