import { AbsoluteFill } from "remotion";
import { DEFAULT_TOKENS, EXIT_SECS, type Tokens } from "../tokens";
import { Card, useIO, useLand } from "../useIO";

export type LowerThirdProps = {
  title: string;
  sub?: string;
  duration: number;
  payoffAt?: number;
  tokens?: Tokens;
};

export const LowerThird: React.FC<LowerThirdProps> = ({
  title,
  sub,
  duration,
  payoffAt = duration * 0.48,
  tokens = DEFAULT_TOKENS,
}) => {
  const { t, alive, i } = useIO(0, Math.max(0, duration - EXIT_SECS));
  const land = useLand(payoffAt);
  const bounce = land * 0.08 * Math.exp(-Math.max(0, t - payoffAt) * 6);

  return (
    <AbsoluteFill
      style={{ backgroundColor: "transparent", fontFamily: tokens.font }}
    >
      <Card alive={alive} i={i} tokens={tokens}>
        <div
          style={{
            color: tokens.ink,
            fontSize: 42,
            fontWeight: 820,
            transform: `scale(${1 + bounce})`,
            transformOrigin: "left center",
          }}
        >
          {title}
        </div>
        {sub ? (
          <div
            style={{
              marginTop: 6,
              color: tokens.accent,
              fontSize: 25,
              fontWeight: 680,
              letterSpacing: "0.05em",
            }}
          >
            {sub}
          </div>
        ) : null}
      </Card>
    </AbsoluteFill>
  );
};
