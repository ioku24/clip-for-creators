import { z } from "zod";
import type { CalculateMetadataFunction } from "remotion";
import { ChapterCard, type ChapterCardProps } from "./comps/ChapterCard";
import { Checklist, type ChecklistProps } from "./comps/Checklist";
import { Collapse, type CollapseProps } from "./comps/Collapse";
import { CountUp, type CountUpProps } from "./comps/CountUp";
import {
  DiagramReveal,
  type DiagramRevealProps,
} from "./comps/DiagramReveal";
import { FeedStack, type FeedStackProps } from "./comps/FeedStack";
import {
  KineticQuote,
  type KineticQuoteProps,
} from "./comps/KineticQuote";
import { LowerThird, type LowerThirdProps } from "./comps/LowerThird";
import { DEFAULT_TOKENS } from "./tokens";

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
  serves: z.string(),
  props: z.record(z.string(), z.unknown()),
  sfx: z
    .array(
      z.object({
        at: z.number(),
        gain: z.number(),
        sound: z.string(),
      }),
    )
    .optional(),
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

export const Beat: React.FC<BeatProps> = ({
  comp,
  start,
  duration,
  payoffAt,
  props,
  tokens,
}) => {
  const shared = {
    ...props,
    duration,
    payoffAt: payoffAt === undefined ? undefined : payoffAt - start,
    tokens: { ...DEFAULT_TOKENS, ...tokens },
  };

  switch (comp) {
    case "KineticQuote":
      return <KineticQuote {...(shared as KineticQuoteProps)} />;
    case "CountUp":
      return <CountUp {...(shared as CountUpProps)} />;
    case "DiagramReveal":
      return <DiagramReveal {...(shared as DiagramRevealProps)} />;
    case "Checklist":
      return <Checklist {...(shared as ChecklistProps)} />;
    case "LowerThird":
      return <LowerThird {...(shared as LowerThirdProps)} />;
    case "ChapterCard":
      return <ChapterCard {...(shared as ChapterCardProps)} />;
    case "FeedStack":
      return <FeedStack {...(shared as FeedStackProps)} />;
    case "Collapse":
      return <Collapse {...(shared as CollapseProps)} />;
  }
};
