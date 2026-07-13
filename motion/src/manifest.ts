export type Role =
  | "HOOK"
  | "BUILD"
  | "TURN"
  | "END"
  | "CALLBACK"
  | "THROUGHLINE";

export type Comp =
  | "KineticQuote"
  | "CountUp"
  | "DiagramReveal"
  | "Checklist"
  | "LowerThird"
  | "ChapterCard"
  | "FeedStack"
  | "Collapse";

export type SfxCue = {
  at: number;
  gain: number;
  sound: string;
};

export type BeatSpec = {
  id: string;
  comp: Comp;
  role: Role;
  start: number;
  duration: number;
  payoffAt?: number;
  words: string;
  serves: string;
  props: Record<string, unknown>;
  sfx?: SfxCue[];
};

export type Manifest = {
  version: 1;
  thesis: string;
  canvas: "vertical" | "horizontal";
  tokens?: Partial<import("./tokens").Tokens>;
  clipDuration: number;
  beats: BeatSpec[];
};
