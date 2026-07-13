import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
  unlinkSync,
} from "node:fs";
import { homedir, tmpdir } from "node:os";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const motionDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoDir = resolve(motionDir, "..");
const outDir = resolve(motionDir, "out/beats");

const fail = (message) => {
  throw new Error(message);
};

const run = (command, args, options = {}) => {
  const result = spawnSync(command, args, {
    cwd: motionDir,
    encoding: "utf8",
    maxBuffer: 20 * 1024 * 1024,
    ...options,
  });
  if (result.status !== 0) {
    fail(
      result.stderr?.trim() ||
        result.stdout?.trim() ||
        `${command} exited with status ${result.status}`,
    );
  }
  return result.stdout.trim();
};

const loadValidator = () => {
  const compiledDir = mkdtempSync(join(tmpdir(), "clip-motion-validator-"));
  try {
    run(process.execPath, [
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
    ]);
    const require = createRequire(import.meta.url);
    return require(join(compiledDir, "validate.js")).validate;
  } finally {
    rmSync(compiledDir, { recursive: true, force: true });
  }
};

const readJson = (path, label) => {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    fail(`Could not read ${label} at ${path}: ${error.message}`);
  }
};

const probePixelFormat = (path) =>
  run("ffprobe", [
    "-v",
    "error",
    "-select_streams",
    "v:0",
    "-show_entries",
    "stream=pix_fmt",
    "-of",
    "default=nw=1:nk=1",
    path,
  ]).split("\n")[0];

const resolveAsset = (asset, manifestDir) => {
  if (asset.startsWith("~/")) return resolve(homedir(), asset.slice(2));
  return isAbsolute(asset) ? asset : resolve(manifestDir, asset);
};

const quoted = (value) => `"${String(value).replaceAll('"', '\\"')}"`;

const usage = () => {
  console.error(
    "Usage: node scripts/render-beats.mjs <beats.json> --transcript <workdir>/transcript.json [--check]",
  );
  process.exit(1);
};

const main = () => {
  const args = process.argv.slice(2);
  const manifestArg = args[0];
  const transcriptIndex = args.indexOf("--transcript");
  if (
    !manifestArg ||
    manifestArg.startsWith("--") ||
    transcriptIndex === -1 ||
    !args[transcriptIndex + 1]
  ) {
    usage();
  }

  const manifestPath = resolve(process.cwd(), manifestArg);
  const transcriptPath = resolve(process.cwd(), args[transcriptIndex + 1]);
  const checkOnly = args.includes("--check");
  const manifest = readJson(manifestPath, "beat manifest");
  const transcriptData = readJson(transcriptPath, "transcript");
  if (!Array.isArray(transcriptData.segments)) {
    fail(`Transcript at ${transcriptPath} has no segments array`);
  }
  const transcriptText = transcriptData.segments
    .map((segment) => (typeof segment.text === "string" ? segment.text : ""))
    .join(" ");

  const validate = loadValidator();
  const result = validate(manifest, transcriptText);
  for (const warning of result.warnings) console.warn(`WARNING ${warning}`);
  if (result.errors.length > 0) {
    for (const error of result.errors) console.error(`ERROR ${error}`);
    process.exit(1);
  }
  console.log(
    `Validation PASS — ${manifest.beats.length} beat${manifest.beats.length === 1 ? "" : "s"}, ${result.warnings.length} warning${result.warnings.length === 1 ? "" : "s"}`,
  );
  if (checkOnly) return;

  mkdirSync(outDir, { recursive: true });
  const overlays = [];
  const sfx = [];
  for (const beat of manifest.beats) {
    const mov = resolve(outDir, `${beat.id}.mov`);
    if (existsSync(mov)) unlinkSync(mov);
    const props = {
      ...beat,
      canvas: manifest.canvas,
      tokens: manifest.tokens,
    };
    console.log(`Rendering ${beat.id} (${beat.comp})...`);
    run("npx", [
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
      `--props=${JSON.stringify(props)}`,
    ]);

    if (!existsSync(mov) || statSync(mov).size === 0) {
      fail(`Render output is missing or empty: ${mov}`);
    }
    const pixelFormat = probePixelFormat(mov);
    if (!pixelFormat.startsWith("yuva")) {
      fail(
        `Rendered beat "${beat.id}" has no alpha channel (pix_fmt=${pixelFormat})`,
      );
    }
    console.log(`PASS ${beat.id}: ${pixelFormat}`);
    overlays.push(
      `--overlay ${quoted(
        `${beat.start.toFixed(2)}:${beat.duration.toFixed(2)}:${relative(repoDir, mov)}`,
      )}`,
    );

    for (const cue of beat.sfx ?? []) {
      const sound = resolveAsset(cue.sound, dirname(manifestPath));
      sfx.push(
        `--sfx ${quoted(`${cue.at.toFixed(2)}:${cue.gain}:${sound}`)}`,
      );
    }
  }

  const workDir = dirname(transcriptPath);
  const command = [
    `python3 skills/clip/scripts/clip.py cut ${quoted(workDir)} --clips ...`,
    ...overlays,
    ...sfx,
  ];
  console.log("\nComposite command:");
  console.log(command.join(" \\\n  "));
  console.log(
    "\nIMPORTANT: Beat times are OUTPUT time. If --tighten was used, derive every beat time from the finished clip's .edl.json.",
  );
};

try {
  main();
} catch (error) {
  console.error(`render-beats: ${error.message}`);
  process.exit(1);
}
