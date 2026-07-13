import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const motionDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoDir = resolve(motionDir, "..");
const cliPath = resolve(motionDir, "scripts/render-beats.mjs");
const clipPath = resolve(repoDir, "skills/clip/scripts/clip.py");

const hasTool = (tool) =>
  spawnSync(tool, ["-version"], { stdio: "ignore" }).status === 0;
const missingMediaTool = ["ffmpeg", "ffprobe"].find(
  (tool) => !hasTool(tool),
);

test(
  "renders two alpha beats and composites the printed overlays via clip.py",
  {
    skip: missingMediaTool
      ? `${missingMediaTool} is not installed; skipping render-beats smoke test`
      : false,
    timeout: 180_000,
  },
  () => {
    const tempDir = mkdtempSync(joinTemp("clip-motion-render-beats-"));
    const workDir = resolve(tempDir, "work");
    const manifestPath = resolve(tempDir, "beats.json");
    const transcriptPath = resolve(workDir, "transcript.json");
    const quoteMov = resolve(motionDir, "out/beats/smoke-quote.mov");
    const countMov = resolve(motionDir, "out/beats/smoke-count.mov");

    try {
      mkdirSync(workDir, { recursive: true });
      execFileSync(
        "ffmpeg",
        [
          "-v",
          "error",
          "-y",
          "-f",
          "lavfi",
          "-i",
          "color=c=gray:s=1080x1920:r=30:d=6",
          "-f",
          "lavfi",
          "-i",
          "sine=frequency=220:sample_rate=48000:duration=6",
          "-shortest",
          "-c:v",
          "libx264",
          "-pix_fmt",
          "yuv420p",
          "-c:a",
          "aac",
          resolve(workDir, "source.mp4"),
        ],
        { stdio: "pipe" },
      );

      writeFileSync(
        transcriptPath,
        JSON.stringify({
          video: "source.mp4",
          duration: 6,
          method: "stub",
          segments: [
            {
              start: 0,
              end: 6,
              text: "Make your future self proud with three likes.",
            },
          ],
        }),
      );
      writeFileSync(
        manifestPath,
        JSON.stringify({
          version: 1,
          thesis: "Showing up now makes your future self proud.",
          canvas: "vertical",
          clipDuration: 6,
          beats: [
            {
              id: "smoke-quote",
              comp: "KineticQuote",
              role: "HOOK",
              start: 1.2,
              duration: 1.5,
              payoffAt: 1.8,
              words: "make your future self proud",
              serves: "States the thesis as the hook.",
              props: { text: "make your future self proud" },
            },
            {
              id: "smoke-count",
              comp: "CountUp",
              role: "BUILD",
              start: 3.5,
              duration: 1.5,
              payoffAt: 4.3,
              words: "three likes",
              serves: "Makes the spoken number legible.",
              props: { to: 3, label: "likes" },
            },
          ],
        }),
      );

      const stdout = execFileSync(
        process.execPath,
        [cliPath, manifestPath, "--transcript", transcriptPath],
        { cwd: motionDir, encoding: "utf8", timeout: 120_000 },
      );

      for (const mov of [quoteMov, countMov]) {
        assert.equal(existsSync(mov), true, `${mov} should exist`);
        const pixFmt = execFileSync(
          "ffprobe",
          [
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=pix_fmt",
            "-of",
            "default=nw=1:nk=1",
            mov,
          ],
          { encoding: "utf8" },
        ).trim();
        assert.match(pixFmt, /^yuva/);
      }

      const overlaySpecs = [...stdout.matchAll(/--overlay "([^"]+)"/g)].map(
        (match) => match[1],
      );
      assert.equal(overlaySpecs.length, 2, stdout);

      execFileSync(
        "python3",
        [
          clipPath,
          "cut",
          workDir,
          "--clips",
          "0:6",
          "--out",
          "composited",
          "--vertical",
          "--no-loudnorm",
          ...overlaySpecs.flatMap((spec) => ["--overlay", spec]),
        ],
        { cwd: repoDir, stdio: "pipe", timeout: 120_000 },
      );

      const output = resolve(workDir, "composited.mp4");
      assert.equal(existsSync(output), true);
      const duration = Number(
        execFileSync(
          "ffprobe",
          [
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            output,
          ],
          { encoding: "utf8" },
        ).trim(),
      );
      assert.ok(Math.abs(duration - 6) < 0.2, `duration was ${duration}s`);
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
      rmSync(quoteMov, { force: true });
      rmSync(countMov, { force: true });
    }
  },
);

function joinTemp(prefix) {
  return resolve(tmpdir(), prefix);
}
