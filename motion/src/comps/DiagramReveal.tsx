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
  /**
   * Vertical band the diagram occupies. Defaults to "lower".
   *
   * WHY THIS EXISTS: a centred row diagram lands squarely across a centre-framed
   * speaker's face. Caught in production on a car-selfie vlog — "go and talk to
   * yourself" rendered directly over her eyes. Covering the face is the one rule
   * the whole doctrine is built on ("animate the idea, never decorate the face"),
   * and the primitive had no way to obey it. "lower" is the safe default; opt
   * into "center" only on footage with a genuinely empty middle.
   */
  placement?: "lower" | "center" | "upper";
  /**
   * When each node lands, in seconds from the beat's start — one entry per node.
   *
   * WITHOUT THIS the primitive staggers nodes at a fixed cadence and they drift
   * off the speech. On a real job she said the three steps at 4.2s / 10.0s /
   * 14.2s into the beat; the fixed stagger fired the first two inside 1.5s and
   * then left a 13-SECOND hole. Same class of bug as a count-up that lands early:
   * a graphic syncs to the WORD, not to a cadence.
   */
  nodeAt?: number[];
  tokens?: Tokens;
};

type Point = { x: number; y: number };

const NODE_WIDTH = 250;
const NODE_HEIGHT = 120;

const pointAtNodeBorder = (source: Point, target: Point): Point => {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  if (dx === 0 && dy === 0) return target;
  const scale = Math.min(
    dx === 0 ? Number.POSITIVE_INFINITY : NODE_WIDTH / 2 / Math.abs(dx),
    dy === 0 ? Number.POSITIVE_INFINITY : NODE_HEIGHT / 2 / Math.abs(dy),
  );
  return { x: target.x - dx * scale, y: target.y - dy * scale };
};

const BANDS = { upper: 0.2, center: 0.43, lower: 0.78 } as const;

const positionsFor = (
  count: number,
  layout: DiagramRevealProps["layout"],
  width: number,
  height: number,
  placement: NonNullable<DiagramRevealProps["placement"]> = "lower",
): Point[] => {
  if (count === 0) return [];
  const band = BANDS[placement];
  if (layout === "loop") {
    return Array.from({ length: count }, (_, index) => {
      const angle = -Math.PI / 2 + (index / count) * Math.PI * 2;
      return {
        x: width * 0.5 + Math.cos(angle) * width * 0.3,
        y: height * (band - 0.01) + Math.sin(angle) * height * 0.16,
      };
    });
  }
  if (layout === "funnel") {
    return Array.from({ length: count }, (_, index) => {
      const progress = count === 1 ? 0.5 : index / (count - 1);
      const direction = index % 2 === 0 ? -1 : 1;
      return {
        x: width * (0.5 + direction * 0.24 * (1 - progress)),
        y: height * (band - 0.21 + progress * 0.42),
      };
    });
  }
  return Array.from({ length: count }, (_, index) => ({
    x: width * (count === 1 ? 0.5 : 0.15 + (index / (count - 1)) * 0.7),
    y: height * band,
  }));
};

export const DiagramReveal: React.FC<DiagramRevealProps> = ({
  nodes,
  arrows,
  layout,
  duration,
  placement = "lower",
  nodeAt,
  payoffAt = duration * 0.62,
  tokens = DEFAULT_TOKENS,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const { alive } = useIO(0, Math.max(0, duration - EXIT_SECS));
  const points = positionsFor(nodes.length, layout, width, height, placement);

  /**
   * "row" is a FLOW, and a flow of real sentences is not a box diagram.
   *
   * The old row layout gave every node a hardcoded 250px box at fixed fractions
   * of the frame width. On real text that means: four-line wraps inside a tiny
   * box, and the last node pushed clean OFF the frame with its arrow pointing
   * into nothing. It looked like clip-art dropped on the footage.
   *
   * A flow renders as ONE card — steps inline, thin connectors, no per-node
   * boxes. It cannot overflow (flex + maxWidth), it cannot wrap badly, and it
   * reads as designed rather than assembled. Loop and funnel keep the SVG
   * treatment below; those genuinely are diagrams.
   */
  if (layout === "row") {
    const band =
      placement === "upper" ? 0.14 : placement === "center" ? 0.42 : 0.74;
    // Each step is its own pill, LEFT-ALIGNED so new pills append rightward
    // without reflowing the ones already on screen. A single shared card had to
    // reserve space for nodes that had not arrived yet — a dark bar extending
    // into nothing for as long as the speaker took to get there.
    const timing = (index: number) =>
      nodeAt?.[index] ??
      (index === nodes.length - 1 ? payoffAt : 0.25 + index * 0.85);

    return (
      <AbsoluteFill
        style={{ backgroundColor: "transparent", fontFamily: tokens.font }}
      >
        <div
          style={{
            position: "absolute",
            top: height * band,
            left: width * 0.05,
            right: width * 0.05,
            display: "flex",
            alignItems: "center",
            opacity: alive,
          }}
        >
          {nodes.map((label, index) => {
            const isLast = index === nodes.length - 1;
            const s0 = Math.min(
              spring({
                frame: frame - timing(index) * fps,
                fps,
                config: isLast ? SPRING_LAND : SPRING_CALM,
              }),
              1,
            );
            if (s0 <= 0.001) return null;
            const prev =
              index === 0
                ? 1
                : Math.min(
                    spring({
                      frame: frame - (timing(index) - 0.35) * fps,
                      fps,
                      config: SPRING_CALM,
                    }),
                    1,
                  );
            return (
              <div
                key={label}
                style={{ display: "flex", alignItems: "center", flex: "0 0 auto" }}
              >
                {index > 0 && (
                  <span
                    aria-hidden
                    style={{
                      margin: `0 ${height * 0.022}px`,
                      fontSize: height * 0.028,
                      fontWeight: 300,
                      color: "rgba(255,255,255,0.5)",
                      opacity: prev,
                    }}
                  >
                    →
                  </span>
                )}
                <div
                  style={{
                    padding: `${height * 0.018}px ${height * 0.026}px`,
                    borderRadius: tokens.radius,
                    background: tokens.paper,
                    boxShadow: "0 18px 46px rgba(0,0,0,.5)",
                    fontSize: height * 0.03,
                    fontWeight: isLast ? 800 : 600,
                    color: isLast ? tokens.ink : "rgba(255,255,255,0.82)",
                    whiteSpace: "nowrap",
                    opacity: s0,
                    transform: `translateY(${(1 - s0) * 14}px) scale(${0.94 + s0 * 0.06})`,
                  }}
                >
                  {label}
                </div>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    );
  }

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
            refX="10"
            refY="5"
            orient="auto"
            viewBox="0 0 10 10"
          >
            <path d="M0,0 L10,5 L0,10 z" fill={tokens.accent} />
          </marker>
        </defs>
        {arrows.map(([from, to], index) => {
          const a = points[from];
          const b = points[to];
          if (!a || !b) return null;
          const isPayoff = index === arrows.length - 1;
          const start = isPayoff
            ? payoffAt
            : Math.min(payoffAt, 0.45 + index * 0.22);
          const draw = Math.min(
            spring({
              frame: frame - start * fps,
              fps,
              config: isPayoff ? SPRING_LAND : SPRING_CALM,
            }),
            1,
          );
          const startPoint = pointAtNodeBorder(b, a);
          const endPoint = pointAtNodeBorder(a, b);
          const length = Math.hypot(
            endPoint.x - startPoint.x,
            endPoint.y - startPoint.y,
          );
          return (
            <line
              key={`${from}-${to}-${index}`}
              x1={startPoint.x}
              y1={startPoint.y}
              x2={endPoint.x}
              y2={endPoint.y}
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
              width: NODE_WIDTH,
              height: NODE_HEIGHT,
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
