# Director Layer Implementation Plan — storyboard + motion graphics

> **For Claude:** REQUIRED SUB-SKILL: Use `executing-plans` skill to implement this plan task-by-task.
> **Executor:** Codex CLI (`gpt-5.5`, xhigh). Work on branch `director-layer`. Commit after every task. **NEVER `git push`.**

**Goal:** Give clip-for-creators a director's brain and hands — a `/direct` skill that turns a transcript into an approved *graphics beat sheet*, and a reusable Remotion motion library that renders those beats as ProRes 4444 alpha overlays which the existing `clip.py --overlay/--sfx` flags composite. Style target: Dan Koe-grade minimal motion graphics — flat shapes, kinetic type, 1–2 accent colors, spring-eased movement, every payoff frame landing on the spoken syllable.

**Architecture:** Three pieces. (1) `skills/direct/SKILL.md` — the editorial doctrine + workflow (text supplied verbatim below). (2) `motion/` — a self-contained Remotion workspace: one dynamic `Beat` composition that renders any of 8 primitive comps from a `beats.json` manifest, plus a validator that mechanically enforces the doctrine (words must exist in the transcript, sync bounds, density lint). (3) A `render-beats` CLI that turns an approved manifest into `.mov` overlays and prints the exact `clip.py` flags. The manifest is the contract; beats are timed in OUTPUT time (post-`--tighten`, via the EDL) because source-time graphics drift — same lesson as `/longform` chapters.

**Why Remotion, not Hyperframes:** the style-proven code (springs, easing, beat grammar) already exists as React in `~/Building/AI-content/juliana-remotion/src/` — extraction, not invention. Its render command (ProRes 4444, `yuva444p10le`) is exactly what `clip.py --overlay` validates for. Hyperframes remains the alt lane for whole-video packaging; not built here.

**Tech Stack:** TypeScript, Remotion 4.0.448 (pin — the version proven today in juliana-remotion), Node ≥18, `node:test` for tests, ffmpeg/ffprobe for verification. No other deps.

---

## Required reading before Task 1 (the taste reference)

Read these fully — they carry the tuned animation values and the editorial voice the library must preserve:

- `~/Building/AI-content/juliana-remotion/src/Director.tsx` (the `useIO` spring hook, `Card`, word-sync doctrine in comments)
- `~/Building/AI-content/juliana-remotion/src/Beats.tsx` (beat grammar: HOOK/BUILD/TURN/END, FeedStack pattern, collapse move)
- `~/Building/AI-content/juliana-remotion/src/Graphics.tsx` (diagram/feed vocabulary)
- `skills/clip/SKILL.md` in this repo (approval gate, overlay/sfx contracts, "animate the idea, never decorate the face")
- `skills/clip/scripts/clip.py` — `apply_overlay` (alpha check) and `apply_sfx` (normalize=0)

Style spec (from the creator brief, distilled): flat minimalist shapes (lines, circles, boxes, arrows) on transparent background; modern sans-serif with clear hierarchy and negative space; monochrome + at most 2 accent colors; ALL movement spring-eased with slight overshoot ("pop", never linear); diagrams draw on with stroke reveals; elements enter exactly when the idea is spoken and exit when it's done; calm and premium, never busy.

---

## Task 1: Scaffold `motion/` workspace

**Files:**
- Create: `motion/package.json`

```json
{
  "name": "clip-motion",
  "private": true,
  "scripts": {
    "studio": "remotion studio",
    "check": "tsc --noEmit && node --test tests/",
    "golden": "node scripts/golden-render.mjs"
  },
  "dependencies": {
    "@remotion/cli": "4.0.448",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "remotion": "4.0.448"
  },
  "devDependencies": {
    "@types/react": "18.3.12",
    "typescript": "5.6.3"
  }
}
```

- Create: `motion/tsconfig.json` (Remotion default: jsx react-jsx, strict, moduleResolution bundler, target ES2022)
- Create: `motion/remotion.config.ts`:

```ts
import { Config } from "@remotion/cli/config";
Config.setVideoImageFormat("png"); // alpha survives only via png frames
```

- Create: `motion/src/tokens.ts` — the single style-token file:

```ts
// One place to restyle the whole library per creator. Values below are the
// tuned ones from the juliana job — calm spring, hard land, Inter stack.
export type Tokens = {
  font: string;
  accent: string;      // ONE accent. A second is the ceiling, not the norm.
  ink: string;         // primary text/shape color on dark footage
  paper: string;       // card background
  radius: number;
};
export const DEFAULT_TOKENS: Tokens = {
  font: "Inter, -apple-system, Helvetica, sans-serif",
  accent: "#FFD24A",
  ink: "#FFFFFF",
  paper: "rgba(18,18,20,0.92)",
  radius: 22,
};
// Motion constants — the house easing language. Do not add easings per-comp.
export const SPRING_CALM = { damping: 15, stiffness: 165 };   // enters, moves
export const SPRING_LAND = { damping: 8, stiffness: 260 };    // payoff hits
export const EXIT_SECS = 0.55;                                 // fade-out tail
```

- Create: `motion/src/useIO.ts` — port `useIO` + `Card` from `Director.tsx` verbatim (adapt imports, take tokens as props for Card styling).
- Create: `motion/src/Root.tsx` — registers ONE composition `Beat` (dynamic):

```tsx
import { Composition } from "remotion";
import { Beat, beatSchema, calcBeatMetadata } from "./Beat";
// Single dynamic comp: which primitive renders is a prop, so render-beats
// invokes `remotion render Beat --props=<beat json>` once per beat.
export const RemotionRoot: React.FC = () => (
  <Composition id="Beat" component={Beat} schema={beatSchema}
    calculateMetadata={calcBeatMetadata}
    durationInFrames={90} fps={30} width={1080} height={1920}
    defaultProps={{ /* a valid sample KineticQuote beat */ }} />
);
```

`calcBeatMetadata` sets `durationInFrames = round(beat.duration * 30)` and width/height from `canvas` ("vertical" → 1080×1920, "horizontal" → 1920×1080). fps stays 30 — `clip.py apply_overlay` already normalizes overlay fps to the output.

- Create: `motion/src/index.ts` (`registerRoot`).

**Step: verify** — `cd motion && npm install && npx tsc --noEmit` passes. `npx remotion compositions src/index.ts` lists `Beat`.

**Step: commit** — `feat(motion): scaffold Remotion workspace with dynamic Beat composition`

## Task 2: Beat manifest schema + doctrine validator (TDD)

The manifest is the contract between the director (LLM) and the renderer. The validator turns editorial rules into hard errors/warnings so a careless director can't ship a rule-break.

**Files:**
- Create: `motion/src/manifest.ts`:

```ts
export type Role = "HOOK" | "BUILD" | "TURN" | "END" | "CALLBACK" | "THROUGHLINE";
export type Comp = "KineticQuote" | "CountUp" | "DiagramReveal" | "Checklist"
  | "LowerThird" | "ChapterCard" | "FeedStack" | "Collapse";
export type SfxCue = { at: number; gain: number; sound: string }; // path resolved by render-beats
export type BeatSpec = {
  id: string;                 // filename-safe
  comp: Comp;
  role: Role;
  start: number;              // OUTPUT time (seconds) on the finished clip
  duration: number;
  payoffAt?: number;          // the syllable the graphic lands on (output time)
  words: string;              // the transcript words this beat serves — MUST exist in transcript
  props: Record<string, unknown>;   // primitive-specific
  sfx?: SfxCue[];
};
export type Manifest = {
  version: 1;
  canvas: "vertical" | "horizontal";
  tokens?: Partial<import("./tokens").Tokens>;
  clipDuration: number;       // duration of the finished clip being decorated
  beats: BeatSpec[];
};
```

- Create: `motion/src/validate.ts` — `validate(manifest, transcriptText): {errors: string[], warnings: string[]}`.

Rules (errors kill the render; warnings print):
- ERROR `invented-words`: normalize (lowercase, strip punctuation, collapse whitespace) — `beat.words` must appear as a substring of the normalized transcript. This is "never put words in the creator's mouth" enforced mechanically.
- ERROR `sync-bounds`: `0 ≤ start`, `duration > 0`, `start + duration ≤ clipDuration + 0.25`, and if `payoffAt` present: `start ≤ payoffAt ≤ start + duration`.
- ERROR `bad-id`: id not `[a-z0-9-]+`, or duplicate ids.
- WARNING `title-card-in-disguise`: any beat with `start < 1.2` whose role is not `HOOK` ("show them FIRST").
- WARNING `density-vertical`: canvas vertical and any gap > 8s between consecutive beats (a short goes beat-every-4-6s).
- WARNING `density-horizontal`: canvas horizontal and beats average denser than one per 15s (long-form graphics are sparse; the meandering is the product).
- WARNING `slide-not-punctuation`: `KineticQuote`/`Collapse`/`CountUp` beats longer than 3.5s (punctuation, not slides). `ChapterCard`, `Checklist`, `FeedStack`, `DiagramReveal` exempt.
- WARNING `turn-without-collapse`: a `TURN` beat whose comp isn't `Collapse` (the payoff usually destroys what was built).

- Test: `motion/tests/validate.test.mjs` (`node --test`, run against compiled or via tsx — simplest: make validate.ts logic importable by writing `motion/src/validate.ts` with no remotion imports and compiling with `npx tsc` to `motion/dist` in the test script, OR write the validator as plain `.mjs` with JSDoc types imported by both — pick the simplest that keeps ONE source of truth; do not duplicate the rules).

Write the failing tests first, one per rule: an invented-words beat rejected; payoffAt outside window rejected; early non-HOOK beat warns; sparse vertical warns; dense horizontal warns; a clean manifest returns zero errors/warnings. Run, watch them fail, implement, watch them pass.

**Step: commit** — `feat(motion): beat manifest schema + doctrine validator with tests`

## Task 3: The 8 primitives + golden renders

**Files:** Create `motion/src/Beat.tsx` (switch on `comp`) and `motion/src/comps/*.tsx`, one file per primitive. ALL primitives: transparent `AbsoluteFill` (no background paint), enter with `SPRING_CALM`, exit by fading over `EXIT_SECS` before the beat's end, land payoffs with `SPRING_LAND` at `payoffAt`. Tokens via props with `DEFAULT_TOKENS` fallback.

Primitive specs (generalized from the juliana comps — keep their feel):

1. **KineticQuote** — props `{ text, sub? }`. The creator's own words, large, centered or lower-third (`placement` prop). Scale 88%→100% with calm spring + fade in (the `make_card` animation at Remotion quality). If `payoffAt` set, the final word pops with the land spring.
2. **CountUp** — props `{ to, label, prefix?, suffix? }`. Number winds up with quartic ease-out and LANDS exactly at `payoffAt` (LikesCounter pattern: compute the wind-up window so the land frame = payoffAt). Label small-caps above, number huge.
3. **DiagramReveal** — props `{ nodes: string[], arrows: [from,to][], layout: "row"|"loop"|"funnel" }`. Boxes pop in sequence (staggered calm springs), connector lines draw on via SVG `strokeDashoffset` animation (the trim-path feel). This is the frameworks device — loops, ladders, funnels.
4. **Checklist** — props `{ title, items: string[], done: number }`. The THROUGHLINE device: plan card with items; first `done` items ticked (tick = land spring on a stroke-drawn check). Re-rendered later in a video with higher `done` to pay the plan off.
5. **LowerThird** — props `{ title, sub? }`. The `Card` from Director.tsx, bottom-left, in and out. Calm, no gimmick.
6. **ChapterCard** — props `{ kicker?, title }`. Long-form chapter break: full-width lower band (not full-screen — the footage stays visible), title slides up with calm spring. 1.5–2.5s.
7. **FeedStack** — props `{ items: string[], accelerate?: boolean }`. The speed-is-the-argument device: stacked pills enter one by one, cadence tightening if `accelerate` (Beats.tsx FEED pattern).
8. **Collapse** — props `{ text?, mode: "drop"|"scatter" }`. The TURN move: whatever text/shape is shown gets destroyed — pieces drop/scatter with gravity-ish interpolation, screen left EMPTY. Emptiness is the beat.

- Create: `motion/scripts/golden-render.mjs` — for each primitive, builds a minimal valid beat, runs:

```
npx remotion render src/index.ts Beat out/golden/<comp>.mov \
  --codec=prores --prores-profile=4444 --pixel-format=yuva444p10le \
  --image-format=png --props=<json>
```

then verifies with ffprobe: `pix_fmt` starts with `yuva` (the exact check `clip.py apply_overlay` performs — an opaque render is the known catastrophic failure), duration within 0.1s of the beat, file > 0 bytes. Also extracts a mid-beat frame to `out/golden/<comp>.png` (`ffmpeg -i mov -frames:v 1`) for human review. Script exits nonzero on any failure and prints a PASS table.

**Step: verify** — `npm run golden` passes 8/8. Keep the `out/golden/*.png` frames — the reviewer will look at them.

**Step: commit** — `feat(motion): 8 style primitives + golden alpha-render harness`

## Task 4: `render-beats` CLI — manifest → overlays → clip.py flags

**Files:**
- Create: `motion/scripts/render-beats.mjs`:

Usage: `node scripts/render-beats.mjs <beats.json> --transcript <workdir>/transcript.json [--check]`
1. Load manifest + transcript (concatenate segment texts for validation).
2. Run validator. Errors → print and exit 1. `--check` stops here (the director runs this BEFORE asking for approval).
3. Per beat: render `out/beats/<id>.mov` with the exact golden-render command (duration/canvas from the beat/manifest; pass tokens through).
4. ffprobe-verify each output has alpha (`yuva*`) — fail loudly otherwise.
5. Print the composite command for the human/agent to run:

```
python3 skills/clip/scripts/clip.py cut <workdir> --clips ... \
  --overlay "12.40:3.00:motion/out/beats/hook-count.mov" \
  --overlay "31.20:2.20:motion/out/beats/turn-collapse.mov" \
  --sfx "13.10:0.5:<sound-path>"        # only for beats that declared sfx
```

(overlay start = beat.start — beats are already in OUTPUT time; print a loud reminder that beat times must come from the EDL when `--tighten` was used.)

- Test: `motion/tests/render-beats.test.mjs` — e2e smoke, guarded: skip with a clear message if `ffmpeg` missing. Build a 6s test clip (`ffmpeg -f lavfi -i color=c=gray:s=1080x1920:d=6 -f lavfi -i sine=f=220:d=6 ...`), a 2-beat manifest (KineticQuote + CountUp) with a stub transcript containing their words, run the CLI, assert two `.mov` files exist with `yuva` pix_fmt, then run the printed overlay composite against the test clip and assert output duration ≈ 6s.

**Step: commit** — `feat(motion): render-beats CLI (validate -> render -> clip.py flags)`

## Task 5: The `/direct` skill + wiring into `/clip` and `/longform`

**Files:**
- Create: `skills/direct/SKILL.md` with EXACTLY this content:

```markdown
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
2. Draft the beat sheet as `beats.json` (schema: `motion/src/manifest.ts`) —
   for each beat: the words it serves, the primitive, role, start/payoffAt in
   OUTPUT time, and one sentence of WHY.
3. `node motion/scripts/render-beats.mjs beats.json --transcript <workdir>/transcript.json --check`
   — fix every error and take every warning seriously.
4. **Propose the beat sheet to the creator — words, timing, why — and WAIT for
   approval. Nothing renders until they say yes** (same law as `/clip`).
5. Drop `--check`, render, then composite with the printed `clip.py` flags.
6. LOOK at the result (preview frame + scrub the seams). Sync errors of 200ms
   read as broken — fix the beat, re-render; never ship "close".

## Style contract

Flat minimal shapes, transparent background, `motion/src/tokens.ts` is the
only place style lives. Spring-eased everything (calm enter, hard land).
1–2 accent colors max. Negative space is a feature. If a beat needs a third
color or a fourth simultaneous element, it's two beats or zero.
```

- Modify: `skills/clip/SKILL.md` — in the "Where this sits" section, replace the sentence positioning Remotion/Hyperframes as "a different, heavier tool" with a pointer: richer motion graphics are the `/direct` skill (this repo, `motion/` library) which renders ProRes 4444 overlays consumed by `--overlay`; Hyperframes remains an alternative packaging lane. Keep the "don't reach for a paid/generative tool" line.
- Modify: `skills/longform/SKILL.md` — after the Chapters section, add 3 lines: chapter cards and the throughline tracker can be rendered via `/direct` (ChapterCard/Checklist primitives), timed from the EDL, sparse by doctrine.
- Modify: `README.md` — add `/direct` one-paragraph mention under "Using it" (same plain voice as the rest: "ask it to add motion graphics; it proposes a beat sheet first; nothing renders until you approve").

**Step: verify** — `npm run check` green; re-read both modified SKILL.mds end-to-end for contradiction with the new text.

**Step: commit** — `feat(direct): director skill + wire motion library into clip/longform`

## Task 6: Repo hygiene

- Add `motion/node_modules/`, `motion/out/` to `.gitignore` (keep `out/golden/*.png` OUT of git too).
- `motion/README.md` — 20 lines: what it is, `npm install`, `npm run golden`, render-beats usage, tokens.
- Final: `npm run check && npm run golden` both green. `git log --oneline` shows one commit per task. **Do not push.**

---

## Checkpoint addenda — Fable review after Tasks 1–3 (2026-07-12, do these in Tasks 4–6)

**A. Branch hygiene FIRST.** Commits `80eac9a` + `8716ff0` belong to this feature, not main. While on `director-layer` (it points at `8716ff0`): `git checkout director-layer`, then `git branch -f main 31b44df`. Then commit the currently-uncommitted Task 1–3 work as the plan's per-task commits on `director-layer`. Nothing is pushed; origin/main is untouched.

**B. Adopt the REVIEW's thesis upgrade** (from `docs/plans/2026-07-12-director-layer-REVIEW.md`) into schema + validator + tests:
- `Manifest.thesis: string` — required. The creator's argument in ONE sentence, in their own logic.
- `BeatSpec.serves: string` — required. One sentence: how this beat serves the thesis, or the structural job it does ("hook", "chapter mark", "plan payoff").
- ERROR `no-thesis`: thesis missing/empty/whitespace.
- WARNING `thesis-unserved`: manifest has >3 beats and none carries role `THROUGHLINE` or `CALLBACK` — moments got graphics, the argument got none.
- WARNING `plan-unpaid`: a `Checklist` beat exists but no later `Checklist` beat reaches `done === items.length` — a plan announced and never paid off.
- Update existing tests' fixtures; add one test per new rule. Also add the missing tests for `sync-bounds` and `bad-id`.

**C. `/direct` SKILL.md:** include the REVIEW's "STEP 0 — read for the ARGUMENT" section verbatim ABOVE "What a director looks for", and add `thesis`/`serves` to the workflow (draft the thesis first; every proposed beat states what it serves in the approval message).

**D. Polish (small, real):**
- `DiagramReveal`: inset arrowheads so they stop at the node border instead of overlapping the node text.
- `golden-render.mjs`: capture the preview PNG at 25% of the beat for `Collapse` (mid-frame lands after the destruction and proves nothing).

## Verification summary (what "done" means)

1. `cd motion && npm run check` — typecheck + all `node --test` suites pass.
2. `npm run golden` — 8/8 primitives render `.mov` with `yuva*` pix_fmt; PNG frames exist for human review.
3. e2e smoke test composites 2 beats over a generated test clip via the real `clip.py` path.
4. `skills/direct/SKILL.md` exists with the doctrine above; clip/longform/README updated without contradicting their existing rules.
5. Branch `director-layer`, one commit per task, nothing pushed.
