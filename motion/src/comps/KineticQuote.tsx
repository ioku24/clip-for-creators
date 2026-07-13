import { AbsoluteFill } from "remotion";
import { DEFAULT_TOKENS, EXIT_SECS, type Tokens } from "../tokens";
import { useIO, useLand } from "../useIO";

export type KineticQuoteProps = {
  text: string;
  sub?: string;
  placement?: "center" | "lower-third";
  duration: number;
  payoffAt?: number;
  tokens?: Tokens;
};

export const KineticQuote: React.FC<KineticQuoteProps> = ({
  text,
  sub,
  placement = "center",
  duration,
  payoffAt = duration * 0.55,
  tokens = DEFAULT_TOKENS,
}) => {
  const { t, alive, i } = useIO(0, Math.max(0, duration - EXIT_SECS));
  const land = useLand(payoffAt);
  const words = text.trim().split(/\s+/);
  const finalWord = words.pop() ?? "";
  const lead = words.join(" ");
  const bounce = land * 0.18 * Math.exp(-Math.max(0, t - payoffAt) * 6);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "transparent",
        fontFamily: tokens.font,
        justifyContent: placement === "center" ? "center" : "flex-end",
        alignItems: placement === "center" ? "center" : "flex-start",
        padding: placement === "center" ? 90 : "0 90px 230px",
        color: tokens.ink,
        opacity: alive,
      }}
    >
      <div
        style={{
          maxWidth: 900,
          fontSize: 104,
          fontWeight: 850,
          lineHeight: 0.98,
          letterSpacing: "-0.045em",
          textAlign: placement === "center" ? "center" : "left",
          transform: `scale(${0.88 + i * 0.12})`,
          transformOrigin: placement === "center" ? "center" : "left bottom",
          textShadow: "0 14px 42px rgba(0,0,0,.45)",
        }}
      >
        {lead ? `${lead} ` : ""}
        <span
          style={{
            color: tokens.accent,
            display: "inline-block",
            transform: `scale(${1 + bounce})`,
          }}
        >
          {finalWord}
        </span>
        {sub ? (
          <div
            style={{
              marginTop: 28,
              fontSize: 34,
              fontWeight: 650,
              letterSpacing: "0.02em",
              lineHeight: 1.2,
              opacity: 0.78,
            }}
          >
            {sub}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
