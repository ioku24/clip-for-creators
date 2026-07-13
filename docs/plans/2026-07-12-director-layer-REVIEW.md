# Review of `2026-07-12-director-layer.md`

Written after directing a real 15:45 vlog end-to-end (Juliana, day 23 marathon
training) and getting corrected four times by the creator's own footage. The plan
is strong — the manifest-as-contract, OUTPUT-time authoring via the EDL, the
mechanical `invented-words` validator, and the golden alpha-render harness are all
exactly right, and `pix_fmt` verification is the single highest-value check in it.

**Three gaps. The first one is the expensive one.**

---

## GAP 1 — `/direct` has no STEP 0. It will find moments and miss the argument.

The skill's "What a director looks for" list — throughline, callback, legibility,
the number, the turn — is a list of **moment-level devices**. Every one is a way
of decorating something *already found*. Nothing in the workflow asks **what the
creator is arguing.**

That is precisely the failure this library will otherwise institutionalise. On the
real job I found **twelve** great moments and built twelve well-made beats. The
creator said *"show up"* **three times** — at 1:57, 4:20, and in the closing line.
Beginning, middle, end. It was the spine of the entire video and it got **zero**
graphics, because I was hunting moments and **a thesis is not a moment.**

Two consequences fell straight out of it:

- **I animated the metaphor and dropped the lesson.** She said *"it flipped the
  switch"*; I built a cute toggle and ignored the framework she introduced with it
  (*"when you feel like you're not doing enough, go talk to yourself, reconnect
  with your purpose"*). Shipped the wrapper, binned the contents.
- **I broke an arc.** Her best aphorism (*"you can't enjoy something if you can't
  enjoy being a beginner"*, 3:52) **sets up** her best line five minutes later
  (*"it's never embarrassing to try"*). I called the payoff an isolated quote and
  left it bare. A line that pays something off must be **edited as a payoff.**

### Proposed fix — add to `skills/direct/SKILL.md`, ABOVE "What a director looks for"

```markdown
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
```

### And make it a checked contract, not a vibe

Add to `BeatSpec`:

```ts
serves: "thesis" | "stakes" | "throughline" | "turn" | "legibility" | "texture";
```

Add to `Manifest`:

```ts
thesis: string;   // one sentence, in the creator's logic. REQUIRED.
```

New validator rules:

- **ERROR `no-thesis`** — `manifest.thesis` missing or under ~20 chars. The
  director must state the argument before the renderer will run.
- **WARNING `thesis-unserved`** — zero beats with `serves: "thesis"`. On the real
  job this fired: twelve beats, none of them the spine.
- **WARNING `texture-heavy`** — more than ~30% of beats are `serves: "texture"`.
  That is a video decorated rather than directed.

---

## GAP 2 — the graphics budget belongs to the CREATOR, not to us.

The validator has density rules (`density-vertical`, `density-horizontal`) which
encode *our* taste. It has nothing that encodes *theirs*.

The creator said, on camera, in the footage being edited:

> *"I don't want to do all this fancy editing. I just want real footage of real
> moments."*

We had put **fifteen** motion graphics on her video. We were overriding a stated
aesthetic because we thought we knew better, and we would not have noticed.

### Proposed fix

Add to `Manifest`:

```ts
aesthetic?: "minimal" | "standard" | "produced";   // default "standard"
```

- **WARNING `aesthetic-override`** — `aesthetic: "minimal"` and more than ~6 beats.
- Add to the skill's hard rules:
  > **When a creator states an aesthetic, the budget is theirs.** Ship the cut
  > that honours it and offer the fuller one as an alternative. Never silently
  > override their taste because you think it will grow the channel.

---

## GAP 3 — `slide-not-punctuation` will fire falsely on the throughline.

`Checklist` is correctly exempted. But the real throughline device is the **same
checklist re-rendered with `done` increasing** (0 → 1 → 2 → 3), which on a
long-form vlog is four beats spread over eight minutes. `density-horizontal`
(“denser than one per 15s”) is fine, but a director will also want to know they
have **built a plan and never paid it off**.

### Proposed fix

- **WARNING `plan-unpaid`** — a `Checklist` beat with `done: 0` exists, and no
  later `Checklist` beat reaches `done === items.length`. Announcing a plan and
  never completing it on screen is the throughline equivalent of a TURN that
  never collapses — the rule the plan already gets right in
  `turn-without-collapse`.

---

## Small notes

- `LikesCounter` (the `CountUp` reference) is worth a caution in the skill: a
  count-up on a **vanity metric** can argue *against* the video it sits in. On the
  real job the creator's own thesis was *"it may not be now, it may be in five
  years"* — the counter made the video about views when she was arguing the
  opposite. **A number earns a CountUp only if the number serves the argument.**
- The `Collapse` primitive is the most valuable one in the list and the most
  likely to be skipped under time pressure. Consider making `turn-without-collapse`
  an ERROR rather than a WARNING.
- Everything the plan says about **word-sync** is correct and is the single rule I
  broke that read most obviously as *broken* to the creator: I fired a counter
  3.2s early because I obeyed "hook in the first 3-5s" instead of the word timing.
  Keep `payoffAt` mandatory for `CountUp`.

---

*Source components for extraction (Task 1's "required reading") are current and
proven on the real job: `~/Building/AI-content/juliana-remotion/src/` —
`Director.tsx` (useIO/Card/word-sync), `Thesis.tsx` (the beats that fixed GAP 1),
`Beats.tsx` (HOOK/BUILD/TURN/END + FeedStack + collapse), `Graphics.tsx`.*
