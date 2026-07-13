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
import { useIO } from "../useIO";

export type FeedStackProps = {
  items: string[];
  accelerate?: boolean;
  duration: number;
  payoffAt?: number;
  tokens?: Tokens;
};

export const FeedStack: React.FC<FeedStackProps> = ({
  items,
  accelerate = false,
  duration,
  payoffAt = duration * 0.68,
  tokens = DEFAULT_TOKENS,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const { alive } = useIO(0, Math.max(0, duration - EXIT_SECS));
  const firstAt = Math.min(0.25, payoffAt);
  const span = Math.max(0, payoffAt - firstAt);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "transparent",
        fontFamily: tokens.font,
        justifyContent: "center",
        alignItems: "center",
        overflow: "hidden",
      }}
    >
      <div style={{ width: 780, position: "relative" }}>
        {items.map((item, index) => {
          const progress = items.length === 1 ? 1 : index / (items.length - 1);
          const cadence = accelerate
            ? 1 - Math.pow(1 - progress, 2)
            : progress;
          const enterAt = firstAt + span * cadence;
          const isPayoff = index === items.length - 1;
          const itemIn = Math.min(
            spring({
              frame: frame - enterAt * fps,
              fps,
              config: isPayoff ? SPRING_LAND : SPRING_CALM,
            }),
            1,
          );
          return (
            <div
              key={`${item}-${index}`}
              style={{
                marginTop: index === 0 ? 0 : 18,
                marginLeft: index % 2 === 0 ? 0 : 100,
                width: 680,
                padding: "22px 30px",
                boxSizing: "border-box",
                borderRadius: tokens.radius,
                background: tokens.paper,
                borderLeft: `6px solid ${tokens.accent}`,
                boxShadow: "0 14px 42px rgba(0,0,0,.4)",
                color: tokens.ink,
                fontSize: 32,
                fontWeight: 740,
                opacity: alive * itemIn,
                transform: `translateY(${(1 - itemIn) * 54}px) scale(${0.92 + itemIn * 0.08})`,
              }}
            >
              {item}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
