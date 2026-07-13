import type { Manifest } from "./manifest";

export type ValidationResult = {
  errors: string[];
  warnings: string[];
};

const normalize = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, "")
    .replace(/\s+/g, " ")
    .trim();

const issue = (code: string, detail: string): string => `${code}: ${detail}`;

export const validate = (
  manifest: Manifest,
  transcriptText: string,
): ValidationResult => {
  const errors: string[] = [];
  const warnings: string[] = [];
  const transcript = normalize(transcriptText);
  const ids = new Set<string>();

  for (const beat of manifest.beats) {
    const words = normalize(beat.words);
    if (words.length === 0 || !transcript.includes(words)) {
      errors.push(
        issue(
          "invented-words",
          `beat "${beat.id}" words do not appear in the transcript`,
        ),
      );
    }

    const end = beat.start + beat.duration;
    if (
      beat.start < 0 ||
      beat.duration <= 0 ||
      end > manifest.clipDuration + 0.25 ||
      (beat.payoffAt !== undefined &&
        (beat.payoffAt < beat.start || beat.payoffAt > end))
    ) {
      errors.push(
        issue(
          "sync-bounds",
          `beat "${beat.id}" falls outside its beat or clip window`,
        ),
      );
    }

    if (!/^[a-z0-9-]+$/.test(beat.id) || ids.has(beat.id)) {
      errors.push(
        issue("bad-id", `beat id "${beat.id}" is invalid or duplicated`),
      );
    }
    ids.add(beat.id);

    if (beat.start < 1.2 && beat.role !== "HOOK") {
      warnings.push(
        issue(
          "title-card-in-disguise",
          `beat "${beat.id}" starts before 1.2s but is not the HOOK`,
        ),
      );
    }

    if (
      ["KineticQuote", "Collapse", "CountUp"].includes(beat.comp) &&
      beat.duration > 3.5
    ) {
      warnings.push(
        issue(
          "slide-not-punctuation",
          `beat "${beat.id}" runs ${beat.duration}s`,
        ),
      );
    }

    if (beat.role === "TURN" && beat.comp !== "Collapse") {
      warnings.push(
        issue(
          "turn-without-collapse",
          `TURN beat "${beat.id}" uses ${beat.comp}`,
        ),
      );
    }
  }

  if (manifest.canvas === "vertical") {
    const ordered = [...manifest.beats].sort((a, b) => a.start - b.start);
    for (let index = 1; index < ordered.length; index += 1) {
      const previous = ordered[index - 1];
      const current = ordered[index];
      const gap = current.start - (previous.start + previous.duration);
      if (gap > 8) {
        warnings.push(
          issue(
            "density-vertical",
            `${gap.toFixed(2)}s gap between "${previous.id}" and "${current.id}"`,
          ),
        );
      }
    }
  }

  if (
    manifest.canvas === "horizontal" &&
    manifest.beats.length > 0 &&
    manifest.clipDuration / manifest.beats.length < 15
  ) {
    warnings.push(
      issue(
        "density-horizontal",
        `${manifest.beats.length} beats in ${manifest.clipDuration}s averages denser than one per 15s`,
      ),
    );
  }

  return { errors, warnings };
};
