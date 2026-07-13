import { AbsoluteFill, useVideoConfig } from "remotion";
import { DEFAULT_TOKENS, EXIT_SECS, type Tokens } from "../tokens";
import { useIO, useLand } from "../useIO";

export type CollapseProps = {
  text?: string;
  mode: "drop" | "scatter";
  duration: number;
  payoffAt?: number;
  tokens?: Tokens;
};

export const Collapse: React.FC<CollapseProps> = ({
  text = "",
  mode,
  duration,
  payoffAt = duration * 0.45,
  tokens = DEFAULT_TOKENS,
}) => {
  const { width, height } = useVideoConfig();
  const { alive, i } = useIO(0, Math.max(0, duration - EXIT_SECS));
  const destroy = useLand(payoffAt);
  const pieces = text.trim() ? text.trim().split(/\s+/) : ["", "", ""];

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "transparent",
        fontFamily: tokens.font,
        justifyContent: "center",
        alignItems: "center",
        overflow: "hidden",
        opacity: alive,
      }}
    >
      <div
        style={{
          width: Math.min(width - 160, 900),
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: 18,
          transform: `scale(${0.88 + i * 0.12})`,
        }}
      >
        {pieces.map((piece, index) => {
          const direction = index % 2 === 0 ? -1 : 1;
          const x =
            mode === "scatter"
              ? destroy * width * direction * (0.8 + index * 0.12)
              : destroy * direction * 30;
          const y =
            mode === "drop"
              ? destroy * destroy * height * (0.9 + index * 0.08)
              : destroy * height * (index % 3 === 0 ? -0.65 : 0.72);
          const rotate = destroy * direction * (18 + index * 7);
          return (
            <div
              key={`${piece}-${index}`}
              style={{
                minWidth: piece ? undefined : 170,
                minHeight: piece ? undefined : 96,
                padding: piece ? "24px 30px" : 0,
                borderRadius: tokens.radius,
                background: tokens.paper,
                borderBottom: `6px solid ${tokens.accent}`,
                color: tokens.ink,
                boxShadow: "0 18px 50px rgba(0,0,0,.45)",
                fontSize: 68,
                fontWeight: 850,
                letterSpacing: "-0.035em",
                transform: `translate(${x}px, ${y}px) rotate(${rotate}deg)`,
              }}
            >
              {piece}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
