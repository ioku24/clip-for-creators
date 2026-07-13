import React from "react";
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  DEFAULT_TOKENS,
  SPRING_CALM,
  SPRING_LAND,
  type Tokens,
} from "./tokens";

const clamp = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
} as const;

export const useIO = (inAt: number, outAt: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const i = Math.min(
    spring({
      frame: frame - inAt * fps,
      fps,
      config: SPRING_CALM,
    }),
    1,
  );
  const o = interpolate(t, [outAt, outAt + 0.55], [1, 0], clamp);
  return { t, frame, fps, alive: i * o, i };
};

export const useLand = (payoffAt: number) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return Math.min(
    spring({
      frame: frame - payoffAt * fps,
      fps,
      config: SPRING_LAND,
    }),
    1,
  );
};

export const Card: React.FC<{
  children: React.ReactNode;
  alive: number;
  i: number;
  tokens?: Tokens;
  style?: React.CSSProperties;
}> = ({ children, alive, i, tokens = DEFAULT_TOKENS, style }) =>
  React.createElement(
    "div",
    {
      style: {
      position: "absolute",
      left: 90,
      bottom: 110,
      padding: "26px 38px",
      borderRadius: tokens.radius,
      background: tokens.paper,
      boxShadow: "0 24px 60px rgba(0,0,0,.55)",
      color: tokens.ink,
      opacity: alive,
      transform: `translateY(${(1 - i) * 40}px)`,
      ...style,
      },
    },
    children,
  );
