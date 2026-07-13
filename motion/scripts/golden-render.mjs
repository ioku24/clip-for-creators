import { existsSync, mkdirSync, statSync, unlinkSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const motionDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = resolve(motionDir, "out/golden");
mkdirSync(outDir, { recursive: true });

const beats = [
  {
    id: "golden-kinetic-quote",
    comp: "KineticQuote",
    role: "HOOK",
    start: 0,
    duration: 2.4,
    payoffAt: 1.35,
    words: "make your future self proud",
    serves: "States the thesis as the hook.",
    props: { text: "make your future self proud", sub: "every video" },
    canvas: "vertical",
  },
  {
    id: "golden-count-up",
    comp: "CountUp",
    role: "HOOK",
    start: 0,
    duration: 2.5,
    payoffAt: 1.5,
    words: "three likes",
    serves: "Makes the spoken number legible.",
    props: { to: 3, label: "likes", suffix: "" },
    canvas: "vertical",
  },
  {
    id: "golden-diagram-reveal",
    comp: "DiagramReveal",
    role: "BUILD",
    start: 0,
    duration: 3,
    payoffAt: 1.8,
    words: "feed choices future",
    serves: "Makes the framework legible.",
    props: {
      nodes: ["THE FEED", "YOUR CHOICES", "YOUR FUTURE"],
      arrows: [
        [0, 1],
        [1, 2],
      ],
      layout: "row",
    },
    canvas: "vertical",
  },
  {
    id: "golden-checklist",
    comp: "Checklist",
    role: "THROUGHLINE",
    start: 0,
    duration: 3,
    payoffAt: 1.7,
    words: "mile plyometrics sprints",
    serves: "Tracks progress through the plan.",
    props: {
      title: "TODAY",
      items: ["ONE MILE", "PLYOMETRICS", "SPRINTS"],
      done: 2,
    },
    canvas: "vertical",
  },
  {
    id: "golden-lower-third",
    comp: "LowerThird",
    role: "CALLBACK",
    start: 0,
    duration: 2.4,
    payoffAt: 1.2,
    words: "still no headphones",
    serves: "Pays off the planted callback.",
    props: { title: "still no headphones", sub: "CALLBACK" },
    canvas: "vertical",
  },
  {
    id: "golden-chapter-card",
    comp: "ChapterCard",
    role: "BUILD",
    start: 0,
    duration: 2.2,
    payoffAt: 1.05,
    words: "the turning point",
    serves: "Marks a structural chapter break.",
    props: { kicker: "CHAPTER 02", title: "The turning point" },
    canvas: "horizontal",
  },
  {
    id: "golden-feed-stack",
    comp: "FeedStack",
    role: "BUILD",
    start: 0,
    duration: 3,
    payoffAt: 2,
    words: "morning routine optimize behind becoming",
    serves: "Builds the visual argument through accumulation.",
    props: {
      items: [
        "5 AM MORNING ROUTINE",
        "OPTIMIZE YOUR LIFE",
        "SIGNS YOU'RE BEHIND",
        "DAY 1 OF BECOMING HER",
      ],
      accelerate: true,
    },
    canvas: "vertical",
  },
  {
    id: "golden-collapse",
    comp: "Collapse",
    role: "TURN",
    start: 0,
    duration: 2.7,
    payoffAt: 1.15,
    words: "is this really me",
    serves: "Destroys the built argument at the turn.",
    props: { text: "IS THIS REALLY ME", mode: "drop" },
    canvas: "vertical",
  },
];

const run = (command, args) =>
  spawnSync(command, args, {
    cwd: motionDir,
    encoding: "utf8",
    maxBuffer: 20 * 1024 * 1024,
  });

const probe = (path, entry, stream) => {
  const args = ["-v", "error"];
  if (stream) args.push("-select_streams", stream);
  args.push("-show_entries", entry, "-of", "default=nw=1:nk=1", path);
  const result = run("ffprobe", args);
  if (result.status !== 0) {
    throw new Error(result.stderr.trim() || `ffprobe failed for ${path}`);
  }
  return result.stdout.trim().split("\n")[0];
};

const rows = [];
const failures = [];

for (const beat of beats) {
  const mov = resolve(outDir, `${beat.comp}.mov`);
  const png = resolve(outDir, `${beat.comp}.png`);
  for (const path of [mov, png]) {
    if (existsSync(path)) unlinkSync(path);
  }

  const render = run("npx", [
    "--no-install",
    "remotion",
    "render",
    "src/index.ts",
    "Beat",
    mov,
    "--codec=prores",
    "--prores-profile=4444",
    "--pixel-format=yuva444p10le",
    "--image-format=png",
    `--props=${JSON.stringify(beat)}`,
  ]);

  if (render.status !== 0) {
    const detail = (render.stderr || render.stdout).trim();
    failures.push(`${beat.comp}: render failed\n${detail}`);
    rows.push({ primitive: beat.comp, status: "FAIL", pix: "-", duration: "-", png: "-" });
    continue;
  }

  try {
    if (!existsSync(mov) || statSync(mov).size === 0) {
      throw new Error("render output is missing or empty");
    }
    const pix = probe(mov, "stream=pix_fmt", "v:0");
    if (!pix.startsWith("yuva")) {
      throw new Error(`pix_fmt=${pix} does not contain alpha`);
    }
    const actualDuration = Number(probe(mov, "format=duration"));
    if (
      !Number.isFinite(actualDuration) ||
      Math.abs(actualDuration - beat.duration) > 0.1
    ) {
      throw new Error(
        `duration=${actualDuration} differs from ${beat.duration} by more than 0.1s`,
      );
    }

    const previewAt =
      beat.comp === "Collapse" ? beat.duration * 0.25 : beat.duration / 2;
    const frame = run("ffmpeg", [
      "-v",
      "error",
      "-y",
      "-ss",
      previewAt.toFixed(3),
      "-i",
      mov,
      "-frames:v",
      "1",
      "-update",
      "1",
      png,
    ]);
    if (frame.status !== 0 || !existsSync(png) || statSync(png).size === 0) {
      throw new Error(frame.stderr.trim() || "mid-beat PNG extraction failed");
    }

    rows.push({
      primitive: beat.comp,
      status: "PASS",
      pix,
      duration: actualDuration.toFixed(3),
      png: "PASS",
    });
  } catch (error) {
    failures.push(`${beat.comp}: ${error.message}`);
    rows.push({ primitive: beat.comp, status: "FAIL", pix: "-", duration: "-", png: "-" });
  }
}

console.log("Primitive       | Status | pix_fmt       | Duration | PNG");
console.log("----------------|--------|---------------|----------|-----");
for (const row of rows) {
  console.log(
    `${row.primitive.padEnd(15)} | ${row.status.padEnd(6)} | ${row.pix.padEnd(13)} | ${row.duration.padEnd(8)} | ${row.png}`,
  );
}

console.log("\nffprobe pix_fmt:");
for (const row of rows) {
  console.log(`${row.primitive}.mov: ${row.pix}`);
}

if (failures.length > 0) {
  console.error("\nFailures:");
  for (const failure of failures) console.error(failure);
  process.exit(1);
}

console.log(`\n8/8 PASS — ${outDir}`);
