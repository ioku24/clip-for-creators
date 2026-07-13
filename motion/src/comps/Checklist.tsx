import {
  AbsoluteFill,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  DEFAULT_TOKENS,
  EXIT_SECS,
  SPRING_CALM,
  SPRING_LAND,
  type Tokens,
} from "../tokens";
import { Card, useIO } from "../useIO";

export type ChecklistProps = {
  title: string;
  items: string[];
  done: number;
  duration: number;
  payoffAt?: number;
  tokens?: Tokens;
};

export const Checklist: React.FC<ChecklistProps> = ({
  title,
  items,
  done,
  duration,
  payoffAt = duration * 0.58,
  tokens = DEFAULT_TOKENS,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { alive, i } = useIO(0, Math.max(0, duration - EXIT_SECS));

  return (
    <AbsoluteFill
      style={{ backgroundColor: "transparent", fontFamily: tokens.font }}
    >
      <Card
        alive={alive}
        i={i}
        tokens={tokens}
        style={{ minWidth: 620, padding: "32px 42px" }}
      >
        <div
          style={{
            color: tokens.accent,
            fontSize: 22,
            fontWeight: 750,
            letterSpacing: "0.22em",
            textTransform: "uppercase",
            marginBottom: 20,
          }}
        >
          {title}
        </div>
        {items.map((item, index) => {
          const row = Math.min(
            spring({
              frame: frame - (0.25 + index * 0.24) * fps,
              fps,
              config: SPRING_CALM,
            }),
            1,
          );
          const isDone = index < done;
          const tickAt = Math.max(
            0,
            payoffAt - Math.max(0, done - index - 1) * 0.14,
          );
          const tick = isDone
            ? Math.min(
                spring({
                  frame: frame - tickAt * fps,
                  fps,
                  config: SPRING_LAND,
                }),
                1,
              )
            : 0;
          return (
            <div
              key={`${item}-${index}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 20,
                marginTop: index === 0 ? 0 : 16,
                color: isDone ? "rgba(255,255,255,.48)" : tokens.ink,
                fontSize: 34,
                fontWeight: 720,
                opacity: row,
                transform: `translateX(${(1 - row) * -22}px)`,
                textDecoration: isDone ? "line-through" : "none",
              }}
            >
              <svg width="42" height="42" viewBox="0 0 42 42">
                <rect
                  x="2"
                  y="2"
                  width="38"
                  height="38"
                  rx="10"
                  fill={isDone ? tokens.accent : "transparent"}
                  stroke={isDone ? tokens.accent : "rgba(255,255,255,.3)"}
                  strokeWidth="3"
                />
                {isDone ? (
                  <path
                    d="M11 21 L18 28 L32 13"
                    fill="none"
                    stroke="#111"
                    strokeWidth="5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeDasharray="36"
                    strokeDashoffset={36 * (1 - tick)}
                  />
                ) : null}
              </svg>
              {item}
            </div>
          );
        })}
      </Card>
    </AbsoluteFill>
  );
};
