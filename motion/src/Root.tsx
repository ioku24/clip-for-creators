import { Composition } from "remotion";
import { Beat, beatSchema, calcBeatMetadata, type BeatProps } from "./Beat";

const sampleBeat = {
  id: "sample-quote",
  comp: "KineticQuote",
  role: "HOOK",
  start: 0,
  duration: 3,
  payoffAt: 1.8,
  words: "make your future self proud",
  serves: "States the thesis as the hook.",
  props: { text: "make your future self proud" },
  canvas: "vertical",
} satisfies BeatProps;

// Single dynamic comp: which primitive renders is a prop, so render-beats
// invokes `remotion render Beat --props=<beat json>` once per beat.
export const RemotionRoot: React.FC = () => (
  <Composition
    id="Beat"
    component={Beat}
    schema={beatSchema}
    calculateMetadata={calcBeatMetadata}
    durationInFrames={90}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={sampleBeat}
  />
);
