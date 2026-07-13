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
  serves: "Hooks the thesis in the creator's own words.",
  props: { text: "make your future self proud" },
  ...overrides,
});

const manifest = (overrides = {}) => ({
  version: 1,
  thesis: "Showing up today is how you make your future self proud.",
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

test("rejects a beat that extends beyond the clip bounds", () => {
  const result = validate(
    manifest({ beats: [beat({ start: 28, duration: 3, payoffAt: 29 })] }),
    "Make your future self proud.",
  );

  assert.equal(hasCode(result.errors, "sync-bounds"), true);
});

test("rejects an invalid beat id", () => {
  const result = validate(
    manifest({ beats: [beat({ id: "Bad ID" })] }),
    "Make your future self proud.",
  );

  assert.equal(hasCode(result.errors, "bad-id"), true);
});

test("rejects a missing or blank thesis", () => {
  const result = validate(
    manifest({ thesis: "   " }),
    "Make your future self proud.",
  );

  assert.equal(hasCode(result.errors, "no-thesis"), true);
});

test("warns when more than three beats do not serve a thesis arc", () => {
  const result = validate(
    manifest({
      beats: [
        beat({ id: "hook", role: "HOOK", start: 1.2 }),
        beat({ id: "build-one", role: "BUILD", start: 5 }),
        beat({ id: "build-two", role: "BUILD", start: 9 }),
        beat({ id: "end", role: "END", start: 13 }),
      ],
    }),
    "Make your future self proud.",
  );

  assert.equal(hasCode(result.warnings, "thesis-unserved"), true);
});

test("warns when a checklist plan is never paid off", () => {
  const checklistProps = {
    title: "The plan",
    items: ["make", "your", "future"],
    done: 1,
  };
  const result = validate(
    manifest({
      beats: [
        beat({
          id: "plan-start",
          comp: "Checklist",
          role: "THROUGHLINE",
          start: 2,
          props: checklistProps,
        }),
        beat({
          id: "plan-progress",
          comp: "Checklist",
          role: "THROUGHLINE",
          start: 8,
          props: { ...checklistProps, done: 2 },
        }),
      ],
    }),
    "Make your future self proud.",
  );

  assert.equal(hasCode(result.warnings, "plan-unpaid"), true);
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
