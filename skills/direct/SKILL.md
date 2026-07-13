---
name: direct
description: Design motion graphics that tell the story of a clip — read the transcript like a director, produce a graphics BEAT SHEET (what to show, on which spoken word, why), get it approved, then render Dan Koe-style minimal overlays (kinetic type, count-ups, diagrams, checklists) via the motion library and composite them with clip.py --overlay. Use when asked to "add motion graphics", "animate this clip", "make this feel edited/produced", "Dan Koe style", "add graphics that tell the story", "storyboard this", "/direct <workdir>".
user_invocable: true
---

# /direct — the director's pass

`/clip` decides WHAT footage survives. `/direct` decides what the viewer SEES
while the words play. You are doing the job of a motion designer sitting next
to an editor: read the transcript, find the beats that deserve a graphic, and
time every payoff to the syllable.

Requires a prepped workdir from `clip.py prep` (and the rendered clip you're
decorating). The motion library lives in `motion/` at the repo root.

## The law: sync to the WORD, not to a rule

A graphic lands ON the syllable of its payoff or it reads as broken. The
number lands when she says "three", not at a round timestamp. Timing rules
("hook in the first 3 seconds") tell you WHERE TO LOOK; the word timings tell
you WHEN TO LAND. When `--tighten` reshaped time, convert source→output
timestamps through `<out>.edl.json` — beats are authored in OUTPUT time.

## STEP 0 — read for the ARGUMENT, not for moments. Do this before anything.

1. **State the thesis in one sentence, in THEIR logic.** If you cannot state it,
   you cannot direct it — you can only decorate it.
2. **Grep the transcript for a repeated phrase.** Creators state their thesis
   three or four times without noticing. That phrase is the spine.
3. **Map SETUP → PAYOFF arcs.** A line that pays something off gets edited as a
   payoff, not as a quote.
4. **Then, of every beat: does this serve the ARGUMENT, or just the moment?**
   A well-made beat that serves no argument is decoration with good manners.

Do NOT visualise the metaphor while ignoring the lesson it introduces.

## What a director looks for (in priority order)

- **A THROUGHLINE** — a promise announced early ("the plan: 5k, gym, cold
  plunge") that graphics can tick off as it completes. The viewer always knows
  where they are. Biggest retention device there is. (`Checklist`, re-rendered
  with `done` increasing.)
- **A CALLBACK** — a planted line that pays off later. Plant it visually, pay
  it off visually. (`LowerThird` / `KineticQuote` reprise.)
- **LEGIBILITY** — the hardest-to-follow moment (a tangent, a framework, a
  comparison) is the one that earns a diagram. (`DiagramReveal`.)
- **THE NUMBER** — a hard number spoken out loud almost always earns a
  `CountUp` landing on the word.
- **THE TURN** — when the thesis inverts, DESTROY what the graphics built
  (`Collapse`). Building and never paying off is decoration.

## Beat grammar (shorts)

HOOK (0–5s, one beat) → BUILD (a beat every 4–6s, each adding to one visual
argument) → TURN (the payoff line — collapse or land) → END (often nothing:
emptiness after a collapse IS the beat). One graphic idea per clip, developed —
eight disconnected gags are worse than one built and destroyed.

Long-form is the opposite density: SPARSE. A beat only where a concrete noun,
number, plan, or framework is spoken. The meandering is the product; graphics
mark structure (chapters, the throughline), they don't wallpaper it.

## Hard rules (the validator enforces the first two)

- **Their words only.** Every text prop comes from the transcript. You are
  emphasising what they said, never speaking for them.
- **Payoff inside the beat.** `payoffAt` within [start, start+duration].
- **Show them first.** No graphic before ~1.2s unless it IS the hook beat.
- **Never restate the caption.** Captions already show the words; a graphic
  that repeats them is decoration. Graphics add the thing the words can't:
  the count, the diagram, the tick, the destruction.
- **Animate the idea; never decorate the face.** One accent color. Punctuation
  (1–3s), not slides. When in doubt, cut the beat.

## Workflow

1. Read the transcript AND the clip list (or the finished clip's EDL).
2. Draft the manifest's `thesis` first: the creator's argument in one sentence,
   in their own logic.
3. Draft the beat sheet as `beats.json` (schema: `motion/src/manifest.ts`) —
   for each beat: the words it serves, its `serves` sentence, the primitive,
   role, start/payoffAt in OUTPUT time, and one sentence of WHY.
4. `node motion/scripts/render-beats.mjs beats.json --transcript <workdir>/transcript.json --check`
   — fix every error and take every warning seriously.
5. **Propose the beat sheet to the creator — words, timing, why, and every beat's
   `serves` line — and WAIT for approval. Nothing renders until they say yes**
   (same law as `/clip`).
6. Drop `--check`, render, then composite with the printed `clip.py` flags.
7. LOOK at the result (preview frame + scrub the seams). Sync errors of 200ms
   read as broken — fix the beat, re-render; never ship "close".

## Style contract

Flat minimal shapes, transparent background, `motion/src/tokens.ts` is the
only place style lives. Spring-eased everything (calm enter, hard land).
1–2 accent colors max. Negative space is a feature. If a beat needs a third
color or a fourth simultaneous element, it's two beats or zero.
