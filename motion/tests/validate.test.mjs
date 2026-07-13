import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const motionDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const compiledDir = mkdtempSync(join(tmpdir(), "clip-motion-validate-"));
execFileSync(
  process.execPath,
  [
    resolve(motionDir, "node_modules/typescript/bin/tsc"),
    "--target",
    "ES2022",
    "--module",
    "commonjs",
    "--moduleResolution",
    "node",
    "--skipLibCheck",
    "--outDir",
    compiledDir,
    resolve(motionDir, "src/validate.ts"),
  ],
  { cwd: motionDir, stdio: "pipe" },
);
const require = createRequire(import.meta.url);
const { validate } = require(join(compiledDir, "validate.js"));
rmSync(compiledDir, { recursive: true, force: true });

const beat = (overrides = {}) => ({
  id: "clean-beat",
  comp: "KineticQuote",
  role: "HOOK",
  start: 1.2,
  duration: 3,
  payoffAt: 2.5,
  words: "make your future self proud",
  props: { text: "make your future self proud" },
  ...overrides,
});

const manifest = (overrides = {}) => ({
  version: 1,
  canvas: "vertical",
  clipDuration: 30,
  beats: [beat()],
  ...overrides,
});

const hasCode = (messages, code) =>
  messages.some((message) => message.startsWith(`${code}:`));

test("rejects invented words that are absent from the transcript", () => {
  const result = validate(
    manifest({ beats: [beat({ words: "words she never said" })] }),
    "Make your future self proud.",
  );

  assert.equal(hasCode(result.errors, "invented-words"), true);
});

test("rejects payoffAt outside the beat window", () => {
  const result = validate(
    manifest({ beats: [beat({ start: 5, duration: 2, payoffAt: 7.1 })] }),
    "Make your future self proud.",
  );

  assert.equal(hasCode(result.errors, "sync-bounds"), true);
});

test("warns when an early beat is not the hook", () => {
  const result = validate(
    manifest({ beats: [beat({ start: 0.8, role: "BUILD" })] }),
    "Make your future self proud.",
  );

  assert.equal(hasCode(result.warnings, "title-card-in-disguise"), true);
});

test("warns when vertical beats leave a gap longer than eight seconds", () => {
  const result = validate(
    manifest({
      beats: [
        beat({ id: "first", start: 1.2, duration: 2 }),
        beat({ id: "second", start: 12, duration: 2 }),
      ],
    }),
    "Make your future self proud.",
  );

  assert.equal(hasCode(result.warnings, "density-vertical"), true);
});

test("warns when horizontal beats average denser than one per 15 seconds", () => {
  const result = validate(
    manifest({
      canvas: "horizontal",
      clipDuration: 20,
      beats: [
        beat({ id: "first", start: 2, duration: 2 }),
        beat({ id: "second", start: 10, duration: 2 }),
      ],
    }),
    "Make your future self proud.",
  );

  assert.equal(hasCode(result.warnings, "density-horizontal"), true);
});

test("returns zero errors and warnings for a clean manifest", () => {
  const result = validate(manifest(), "Make your future self proud.");

  assert.deepEqual(result, { errors: [], warnings: [] });
});
