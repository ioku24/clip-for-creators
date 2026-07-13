import { AbsoluteFill } from "remotion";
import { DEFAULT_TOKENS, EXIT_SECS, type Tokens } from "../tokens";
import { useIO, useLand } from "../useIO";

export type ChapterCardProps = {
  kicker?: string;
  title: string;
  duration: number;
  payoffAt?: number;
  tokens?: Tokens;
};

export const ChapterCard: React.FC<ChapterCardProps> = ({
  kicker,
  title,
  duration,
  payoffAt = duration * 0.48,
  tokens = DEFAULT_TOKENS,
}) => {
  const { t, alive, i } = useIO(0, Math.max(0, duration - EXIT_SECS));
  const land = useLand(payoffAt);
  const bounce = land * 0.1 * Math.exp(-Math.max(0, t - payoffAt) * 6);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "transparent",
        fontFamily: tokens.font,
        justifyContent: "flex-end",
        opacity: alive,
      }}
    >
      <div
        style={{
          width: "100%",
          minHeight: 330,
          padding: "56px 90px 68px",
          boxSizing: "border-box",
          background: tokens.paper,
          borderTop: `5px solid ${tokens.accent}`,
          color: tokens.ink,
          transform: `translateY(${(1 - i) * 70}px)`,
          boxShadow: "0 -22px 70px rgba(0,0,0,.38)",
        }}
      >
        {kicker ? (
          <div
            style={{
              color: tokens.accent,
              fontSize: 23,
              fontWeight: 760,
              letterSpacing: "0.24em",
              textTransform: "uppercase",
            }}
          >
            {kicker}
          </div>
        ) : null}
        <div
          style={{
            marginTop: kicker ? 14 : 0,
            maxWidth: 1500,
            fontSize: 76,
            fontWeight: 840,
            lineHeight: 1,
            letterSpacing: "-0.035em",
            transform: `translateY(${(1 - i) * 30}px) scale(${1 + bounce})`,
            transformOrigin: "left center",
          }}
        >
          {title}
        </div>
      </div>
    </AbsoluteFill>
  );
};
