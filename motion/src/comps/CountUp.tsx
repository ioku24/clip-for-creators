import { AbsoluteFill, interpolate } from "remotion";
import { DEFAULT_TOKENS, EXIT_SECS, type Tokens } from "../tokens";
import { Card, useIO, useLand } from "../useIO";

const clamp = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
} as const;

export type CountUpProps = {
  to: number;
  label: string;
  prefix?: string;
  suffix?: string;
  duration: number;
  payoffAt?: number;
  tokens?: Tokens;
};

export const CountUp: React.FC<CountUpProps> = ({
  to,
  label,
  prefix = "",
  suffix = "",
  duration,
  payoffAt = duration * 0.62,
  tokens = DEFAULT_TOKENS,
}) => {
  const { t, alive, i } = useIO(0, Math.max(0, duration - EXIT_SECS));
  const windStart = Math.max(0.2, payoffAt - 1.45);
  const wind = interpolate(t, [windStart, payoffAt], [0, to], {
    ...clamp,
    easing: (value) => 1 - Math.pow(1 - value, 4),
  });
  const land = useLand(payoffAt);
  const bounce = land * 0.18 * Math.exp(-Math.max(0, t - payoffAt) * 6);

  return (
    <AbsoluteFill
      style={{ backgroundColor: "transparent", fontFamily: tokens.font }}
    >
      <Card
        alive={alive}
        i={i}
        tokens={tokens}
        style={{ minWidth: 430, textAlign: "center", padding: "32px 48px" }}
      >
        <div
          style={{
            color: tokens.accent,
            fontSize: 22,
            fontWeight: 750,
            letterSpacing: "0.22em",
            textTransform: "uppercase",
          }}
        >
          {label}
        </div>
        <div
          style={{
            marginTop: 8,
            color: tokens.ink,
            fontSize: 112,
            fontWeight: 850,
            fontVariantNumeric: "tabular-nums",
            letterSpacing: "-0.05em",
            transform: `scale(${1 + bounce})`,
          }}
        >
          {prefix}
          {Math.round(wind).toLocaleString("en-US")}
          {suffix}
        </div>
      </Card>
    </AbsoluteFill>
  );
};
