import { useEffect, useId, useState } from "react";

export type ComposerStarTrackState = "idle" | "sending" | "recording" | "error" | "drop";

type ComposerStarTrackProps = {
  state: ComposerStarTrackState;
  armed?: boolean;
};

type TrackNode = {
  id: string;
  x: number;
  y: number;
  tone: "anchor" | "relay" | "hub" | "beacon";
};

const TRACK_PATH = "M22 50 C 84 50 146 50 208 50 C 270 50 332 50 398 50";
const TRACK_TRANSLATE_VALUES = "22 50;84 50;146 50;208 50;270 50;332 50;398 50";
const TRACK_NODES: TrackNode[] = [
  { id: "entry", x: 22, y: 50, tone: "anchor" },
  { id: "left", x: 84, y: 50, tone: "relay" },
  { id: "mid-left", x: 146, y: 50, tone: "relay" },
  { id: "mid", x: 208, y: 50, tone: "hub" },
  { id: "mid-right", x: 270, y: 50, tone: "relay" },
  { id: "right", x: 332, y: 50, tone: "relay" },
  { id: "beacon", x: 398, y: 50, tone: "beacon" },
];

function usePrefersReducedMotion() {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return undefined;
    }
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setPrefersReducedMotion(media.matches);
    apply();
    media.addEventListener?.("change", apply);
    return () => media.removeEventListener?.("change", apply);
  }, []);

  return prefersReducedMotion;
}

function shiftBegin(delay: string, shiftSeconds: number) {
  const numericDelay = Number.parseFloat(delay.replace("s", ""));
  if (Number.isNaN(numericDelay)) {
    return `${-shiftSeconds}s`;
  }
  return `${numericDelay - shiftSeconds}s`;
}

export function ComposerStarTrack({ state, armed = false }: ComposerStarTrackProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const motionMode = prefersReducedMotion ? "reduced" : "animated";
  const uniqueId = useId().replace(/:/g, "");
  const railGradientId = `composer-track-rail-${uniqueId}`;
  const flowGradientId = `composer-track-flow-${uniqueId}`;
  const nodeGradientId = `composer-track-node-${uniqueId}`;
  const travelerGradientId = `composer-track-traveler-${uniqueId}`;
  const glowFilterId = `composer-track-glow-${uniqueId}`;
  const dustFilterId = `composer-track-dust-${uniqueId}`;
  const starSymbolId = `composer-track-star-${uniqueId}`;

  return (
    <div
      className="composer-star-track"
      data-state={state}
      data-armed={armed ? "true" : "false"}
      data-motion={motionMode}
      data-testid="composer-star-track"
      aria-hidden="true"
    >
      <svg className="composer-star-track-svg" viewBox="0 0 420 64" preserveAspectRatio="none" role="presentation" focusable="false">
        <defs>
          <linearGradient id={railGradientId} x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="var(--composer-track-line-soft)" />
            <stop offset="24%" stopColor="var(--composer-track-line-core)" />
            <stop offset="74%" stopColor="var(--composer-track-line-bright)" />
            <stop offset="100%" stopColor="var(--composer-track-line-soft)" />
          </linearGradient>
          <linearGradient id={flowGradientId} x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="var(--composer-track-flow-soft)" />
            <stop offset="42%" stopColor="var(--composer-track-flow-bright)" />
            <stop offset="58%" stopColor="var(--composer-track-flow-core)" />
            <stop offset="100%" stopColor="var(--composer-track-flow-soft)" />
          </linearGradient>
          <radialGradient id={nodeGradientId} cx="50%" cy="50%" r="60%">
            <stop offset="0%" stopColor="var(--composer-track-node-glow-core)" />
            <stop offset="58%" stopColor="var(--composer-track-node-glow-soft)" />
            <stop offset="100%" stopColor="transparent" />
          </radialGradient>
          <radialGradient id={travelerGradientId} cx="50%" cy="50%" r="60%">
            <stop offset="0%" stopColor="var(--composer-track-traveler-core)" />
            <stop offset="58%" stopColor="var(--composer-track-traveler-glow)" />
            <stop offset="100%" stopColor="transparent" />
          </radialGradient>
          <filter id={glowFilterId} x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="2.4" />
          </filter>
          <filter id={dustFilterId} x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="1.4" />
          </filter>
          <symbol id={starSymbolId} viewBox="-10 -10 20 20">
            <path fill="currentColor" d="M0 -7.6 L1.8 -1.8 L7.6 0 L1.8 1.8 L0 7.6 L-1.8 1.8 L-7.6 0 L-1.8 -1.8 Z" />
            <path fill="currentColor" opacity="0.72" d="M0 -4.6 L0.86 -0.86 L4.6 0 L0.86 0.86 L0 4.6 L-0.86 0.86 L-4.6 0 L-0.86 -0.86 Z" />
            <circle cx="0" cy="0" r="0.72" fill="white" opacity="0.94" />
          </symbol>
        </defs>

        <g className="composer-star-track-rails">
          <path d={TRACK_PATH} className="composer-star-track-rail composer-star-track-rail-under" />
          <path d={TRACK_PATH} className="composer-star-track-rail composer-star-track-rail-main" stroke={`url(#${railGradientId})`} />
          <path d={TRACK_PATH} pathLength={100} className="composer-star-track-rail composer-star-track-rail-flow" stroke={`url(#${flowGradientId})`} />
        </g>

        <g className="composer-star-track-nodes">
          {TRACK_NODES.map((node, index) => (
            <g key={node.id} className={`composer-star-track-node composer-star-track-node-${node.tone}`} transform={`translate(${node.x} ${node.y})`}>
              <circle
                className="composer-star-track-node-halo"
                r={node.tone === "beacon" ? 10.8 : node.tone === "hub" ? 8.4 : 6.6}
                fill={`url(#${nodeGradientId})`}
                filter={`url(#${glowFilterId})`}
              />
              <circle className="composer-star-track-node-core" r={node.tone === "beacon" ? 2.4 : node.tone === "hub" ? 2.1 : 1.7} />
              <use
                href={`#${starSymbolId}`}
                className="composer-star-track-node-star"
                width={node.tone === "beacon" ? 10.4 : node.tone === "hub" ? 8.8 : 7.2}
                height={node.tone === "beacon" ? 10.4 : node.tone === "hub" ? 8.8 : 7.2}
                x={node.tone === "beacon" ? -5.2 : node.tone === "hub" ? -4.4 : -3.6}
                y={node.tone === "beacon" ? -5.2 : node.tone === "hub" ? -4.4 : -3.6}
                style={!prefersReducedMotion ? { animationDelay: `${index * 0.42}s` } : undefined}
              />
            </g>
          ))}
        </g>

        {!prefersReducedMotion ? (
          <g className="composer-star-track-traveler" data-testid="composer-star-track-traveler">
            <g className="composer-star-track-traveler-motion">
              <animateTransform attributeName="transform" type="translate" dur="11s" begin="-2.2s" values={TRACK_TRANSLATE_VALUES} repeatCount="indefinite" />
              <circle className="composer-star-track-traveler-halo" r={7.8} fill={`url(#${travelerGradientId})`} filter={`url(#${glowFilterId})`} />
              <use href={`#${starSymbolId}`} className="composer-star-track-traveler-star" width={10.6} height={10.6} x={-5.3} y={-5.3} />
              <circle className="composer-star-track-traveler-core" r={1.6} />
            </g>
            {[0.34, 0.68, 1.02].map((shift, dustIndex) => (
              <g key={`dust-${dustIndex}`} className="composer-star-track-dust-motion">
                <animateTransform attributeName="transform" type="translate" dur="11s" begin={shiftBegin("-2.2s", shift)} values={TRACK_TRANSLATE_VALUES} repeatCount="indefinite" />
                <animate attributeName="opacity" dur="11s" begin={shiftBegin("-2.2s", shift)} values="0;0.44;0.22;0.05;0" repeatCount="indefinite" />
                <circle className="composer-star-track-dust" r={dustIndex === 0 ? 1.48 : dustIndex === 1 ? 1.18 : 0.96} filter={`url(#${dustFilterId})`} />
              </g>
            ))}
          </g>
        ) : null}
      </svg>
    </div>
  );
}
