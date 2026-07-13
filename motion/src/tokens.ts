// One place to restyle the whole library per creator. Values below are the
// tuned ones from the juliana job — calm spring, hard land, Inter stack.
export type Tokens = {
  font: string;
  accent: string; // ONE accent. A second is the ceiling, not the norm.
  ink: string; // primary text/shape color on dark footage
  paper: string; // card background
  radius: number;
};

export const DEFAULT_TOKENS: Tokens = {
  font: "Inter, -apple-system, Helvetica, sans-serif",
  // Monochrome by default — the amber text accent was rejected (Josh,
  // 2026-07-13). Payoffs land by scale, not color. A per-client brand accent
  // comes in via the manifest's tokens.accent override, never this default.
  accent: "#FFFFFF",
  ink: "#FFFFFF",
  paper: "rgba(18,18,20,0.92)",
  radius: 22,
};

// Motion constants — the house easing language. Do not add easings per-comp.
export const SPRING_CALM = { damping: 15, stiffness: 165 }; // enters, moves
export const SPRING_LAND = { damping: 8, stiffness: 260 }; // payoff hits
export const EXIT_SECS = 0.55; // fade-out tail
