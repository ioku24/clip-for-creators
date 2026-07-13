# clip — turn your long videos into shorts, by talking to your AI

You paste a YouTube link. Your AI reads what you actually *said*, tells you which
moments are the strongest and why, and — once you say yes — cuts them into
vertical, captioned clips.

No timeline. No scrubbing. No subscription. It runs on your own computer and it
costs nothing to use.

## The idea

Editing software makes you hunt through a timeline for the good parts. That's
backwards. **The good parts are in your words** — so this reads your transcript,
you pick the moments as *text*, and the computer does the cutting.

That means your AI can actually help. It can't watch your video, but it can read
what you said, and that turns out to be the whole game.

## Setup (once, about 5 minutes)

**1. Install the tools it needs.** Open Terminal and run:

```bash
bash setup.sh
```

That installs three free, open-source programs: `ffmpeg` (cuts video), `yt-dlp`
(downloads it), and `whisper` (transcribes it, from OpenAI). Nothing is sent
anywhere — the transcription happens on your machine.

**2. Add the skill to your AI.** In whatever coding-AI you use (Claude Code,
Cursor, Codex, Gemini CLI — they all support this), run:

```bash
npx skills add ioku24/clip-for-creators
```

That's it.

## Using it

Just talk to your AI normally:

> "Clip my last YouTube video"
> "Pull three shorts out of this: <link>"
> "Find the most viral moment in this and cut it vertical with captions"

It will:

1. Download the video and transcribe it.
2. **Read the transcript and tell you which moments it thinks are strongest —
   with timestamps, the actual words, and why each one earns its place.**
3. Wait for you to say yes. *It will not cut anything until you approve.*
4. Render the clips: 9:16 vertical, captions burned in, filler and dead air
   removed.

You can always overrule it. It's a second pair of eyes on your own words, not a
replacement for your taste.

Ask it to add motion graphics and `/direct` will read the clip's argument, then
propose a beat sheet with the words, timing, and reason for every graphic.
Nothing renders until you approve it.

## The things worth knowing

**Restructure before you decorate.** The single best thing you can do to a clip
costs nothing: **reorder it.** People bury their best line six seconds in — a
short can't afford that wait. Lead with the payoff, *then* the context that earns
it, *then* the release. Same footage, ten times the punch. Just ask for it:

> "Recut that but lead with the 98% line."

**Say the strong thing plainly.** This tool finds bold claims, real numbers,
honest admissions, and questions that make a viewer uncomfortable. It cannot
manufacture them. A clip is only as good as the sentence inside it.

**It needs you to be talking.** No speech, no transcript, nothing to cut on.
Silent screen recordings and music-only footage won't work.

**Animation isn't the answer.** A person talking straight to camera works
*because* it feels real. Graphics over your face break that spell. Use them only
when they carry information your face can't — a stat, a list, a before/after.

## Options, if you want them

Your AI knows all of these — you can just ask in plain English — but if you like
knowing what's under the hood:

| What you ask for | What it does |
|---|---|
| vertical | 9:16 crop for Shorts / Reels / TikTok |
| captions | Burned-in, 4-word bursts, readable on mute |
| tighten | Strips dead air *inside* the clip — the thing that makes raw footage feel raw |
| hook | A line of text over the first 2.5 seconds — the biggest retention lever there is |
| push | A slow, almost invisible zoom that keeps a locked-off shot alive |
| emphasize | Highlights the words that carry your claim, so the eye lands on them |

## Honest limits

- The vertical crop centers on the middle of the frame. If you're off to one
  side, check a frame before you trust a batch.
- Whisper's transcript is good, not perfect. It will occasionally botch a proper
  noun.
- It cuts what exists. It doesn't invent footage, and it can't make a boring
  take interesting.

---

Made with Claude Code. Everything runs locally — your footage never leaves your
machine.
