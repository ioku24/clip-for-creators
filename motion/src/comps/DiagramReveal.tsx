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

export type DiagramRevealProps = {
  nodes: string[];
  arrows: [number, number][];
  layout: "row" | "loop" | "funnel";
  duration: number;
  payoffAt?: number;
  tokens?: Tokens;
};

type Point = { x: number; y: number };

const positionsFor = (
  count: number,
  layout: DiagramRevealProps["layout"],
  width: number,
  height: number,
): Point[] => {
  if (count === 0) return [];
  if (layout === "loop") {
    return Array.from({ length: count }, (_, index) => {
      const angle = -Math.PI / 2 + (index / count) * Math.PI * 2;
      return {
        x: width * 0.5 + Math.cos(angle) * width * 0.3,
        y: height * 0.42 + Math.sin(angle) * height * 0.2,
      };
    });
  }
  if (layout === "funnel") {
    return Array.from({ length: count }, (_, index) => {
      const progress = count === 1 ? 0.5 : index / (count - 1);
      const direction = index % 2 === 0 ? -1 : 1;
      return {
        x: width * (0.5 + direction * 0.24 * (1 - progress)),
        y: height * (0.22 + progress * 0.44),
      };
    });
  }
  return Array.from({ length: count }, (_, index) => ({
    x: width * (count === 1 ? 0.5 : 0.15 + (index / (count - 1)) * 0.7),
    y: height * 0.43,
  }));
};

export const DiagramReveal: React.FC<DiagramRevealProps> = ({
  nodes,
  arrows,
  layout,
  duration,
  payoffAt = duration * 0.62,
  tokens = DEFAULT_TOKENS,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const { alive } = useIO(0, Math.max(0, duration - EXIT_SECS));
  const points = positionsFor(nodes.length, layout, width, height);

  return (
    <AbsoluteFill
      style={{ backgroundColor: "transparent", fontFamily: tokens.font }}
    >
      <svg
        width={width}
        height={height}
        style={{ position: "absolute", inset: 0, opacity: alive }}
      >
        <defs>
          <marker
            id="diagram-arrow"
            markerWidth="10"
            markerHeight="10"
            refX="8"
            refY="5"
            orient="auto"
          >
            <path d="M0,0 L10,5 L0,10 z" fill={tokens.accent} />
          </marker>
        </defs>
        {arrows.map(([from, to], index) => {
          const a = points[from];
          const b = points[to];
          if (!a || !b) return null;
          const isPayoff = index === arrows.length - 1;
          const start = isPayoff ? payoffAt : Math.min(payoffAt, 0.45 + index * 0.22);
          const draw = Math.min(
            spring({
              frame: frame - start * fps,
              fps,
              config: isPayoff ? SPRING_LAND : SPRING_CALM,
            }),
            1,
          );
          const length = Math.hypot(b.x - a.x, b.y - a.y);
          return (
            <line
              key={`${from}-${to}-${index}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={tokens.accent}
              strokeWidth={7}
              strokeLinecap="round"
              strokeDasharray={length}
              strokeDashoffset={length * (1 - draw)}
              markerEnd="url(#diagram-arrow)"
            />
          );
        })}
      </svg>
      {nodes.map((label, index) => {
        const point = points[index];
        const nodeAt =
          index === nodes.length - 1 ? payoffAt : 0.15 + index * 0.22;
        const nodeIn = Math.min(
          spring({
            frame: frame - nodeAt * fps,
            fps,
            config: index === nodes.length - 1 ? SPRING_LAND : SPRING_CALM,
          }),
          1,
        );
        return (
          <div
            key={`${label}-${index}`}
            style={{
              position: "absolute",
              left: point.x,
              top: point.y,
              width: 250,
              minHeight: 92,
              padding: "22px 26px",
              borderRadius: tokens.radius,
              border: `4px solid ${tokens.accent}`,
              background: tokens.paper,
              color: tokens.ink,
              boxSizing: "border-box",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              textAlign: "center",
              fontSize: 30,
              fontWeight: 800,
              lineHeight: 1.05,
              opacity: alive * nodeIn,
              transform: `translate(-50%, -50%) scale(${0.88 + nodeIn * 0.12})`,
              boxShadow: "0 18px 50px rgba(0,0,0,.38)",
            }}
          >
            {label}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
