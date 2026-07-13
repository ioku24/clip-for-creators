import { z } from "zod";
import type { CalculateMetadataFunction } from "remotion";
import { AbsoluteFill } from "remotion";
import { DEFAULT_TOKENS, EXIT_SECS } from "./tokens";
import { Card, useIO } from "./useIO";

const tokenSchema = z.object({
  font: z.string().optional(),
  accent: z.string().optional(),
  ink: z.string().optional(),
  paper: z.string().optional(),
  radius: z.number().optional(),
});

export const beatSchema = z.object({
  id: z.string(),
  comp: z.enum([
    "KineticQuote",
    "CountUp",
    "DiagramReveal",
    "Checklist",
    "LowerThird",
    "ChapterCard",
    "FeedStack",
    "Collapse",
  ]),
  role: z.enum(["HOOK", "BUILD", "TURN", "END", "CALLBACK", "THROUGHLINE"]),
  start: z.number(),
  duration: z.number().positive(),
  payoffAt: z.number().optional(),
  words: z.string(),
  props: z.record(z.string(), z.unknown()),
  canvas: z.enum(["vertical", "horizontal"]),
  tokens: tokenSchema.optional(),
});

export type BeatProps = z.infer<typeof beatSchema>;

export const calcBeatMetadata: CalculateMetadataFunction<BeatProps> = ({
  props,
}) => ({
  durationInFrames: Math.round(props.duration * 30),
  width: props.canvas === "vertical" ? 1080 : 1920,
  height: props.canvas === "vertical" ? 1920 : 1080,
  fps: 30,
});

export const Beat: React.FC<BeatProps> = ({ duration, props, tokens }) => {
  const resolved = { ...DEFAULT_TOKENS, ...tokens };
  const { alive, i } = useIO(0, Math.max(0, duration - EXIT_SECS));
  const text = typeof props.text === "string" ? props.text : "Their own words";

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "transparent",
        fontFamily: resolved.font,
      }}
    >
      <Card alive={alive} i={i} tokens={resolved}>
        <div style={{ fontSize: 54, fontWeight: 800 }}>{text}</div>
      </Card>
    </AbsoluteFill>
  );
};
