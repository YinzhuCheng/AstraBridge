import { useEffect, useId, useMemo, useState } from "react";

export type StarbridgeWaitingPhase = "thinking" | "tools" | "web" | "files" | "automation" | "approval";
export type StarbridgeWaitingVariant = "inline" | "panel";

type StarbridgeWaitingConstellationProps = {
  variant?: StarbridgeWaitingVariant;
  phase?: StarbridgeWaitingPhase;
  label?: string;
  title?: string;
  detail?: string;
  className?: string;
};

type ConstellationNode = {
  id: string;
  x: number;
  y: number;
  tone: "anchor" | "relay" | "hub" | "beacon";
};

type ConstellationPath = {
  id: string;
  d: string;
  delay: string;
  strokeWidth?: number;
};

type TravelerRoute = {
  id: string;
  duration: string;
  delay: string;
  cxValues: string;
  cyValues: string;
  opacityValues: string;
};

type ConstellationGeometry = {
  viewBox: string;
  nodes: ConstellationNode[];
  paths: ConstellationPath[];
  travelers: TravelerRoute[];
};

const INLINE_GEOMETRY: ConstellationGeometry = {
  viewBox: "0 0 204 56",
  nodes: [
    { id: "entry", x: 18, y: 31, tone: "anchor" },
    { id: "left", x: 56, y: 22, tone: "relay" },
    { id: "mid-left", x: 94, y: 33, tone: "hub" },
    { id: "mid-right", x: 132, y: 21, tone: "relay" },
    { id: "right", x: 168, y: 32, tone: "hub" },
    { id: "beacon", x: 188, y: 18, tone: "beacon" },
  ],
  paths: [
    { id: "entry-left", d: "M18 31 L56 22", delay: "0s" },
    { id: "left-mid-left", d: "M56 22 L94 33", delay: "-0.8s" },
    { id: "mid-left-mid-right", d: "M94 33 L132 21", delay: "-1.4s" },
    { id: "mid-right-right", d: "M132 21 L168 32", delay: "-2s" },
    { id: "right-beacon", d: "M168 32 L188 18", delay: "-2.7s", strokeWidth: 1.9 },
  ],
  travelers: [
    {
      id: "inline-main",
      duration: "7.8s",
      delay: "-1.2s",
      opacityValues: "0;0.8;1;1;0.56;0",
      cxValues: "18;56;94;132;168;188",
      cyValues: "31;22;33;21;32;18",
    },
  ],
};

const PANEL_GEOMETRY: ConstellationGeometry = {
  viewBox: "0 0 236 164",
  nodes: [
    { id: "left-shoulder", x: 42, y: 34, tone: "hub" },
    { id: "right-shoulder", x: 128, y: 44, tone: "anchor" },
    { id: "belt-left", x: 78, y: 82, tone: "hub" },
    { id: "belt-mid", x: 112, y: 78, tone: "hub" },
    { id: "belt-right", x: 150, y: 76, tone: "hub" },
    { id: "left-foot", x: 68, y: 142, tone: "anchor" },
    { id: "right-foot", x: 178, y: 136, tone: "beacon" },
    { id: "sword-upper", x: 122, y: 106, tone: "relay" },
    { id: "sword-lower", x: 132, y: 132, tone: "relay" },
  ],
  paths: [
    { id: "shoulders", d: "M42 34 L128 44", delay: "0s" },
    { id: "left-shoulder-belt", d: "M42 34 L78 82", delay: "-0.7s" },
    { id: "right-shoulder-belt", d: "M128 44 L150 76", delay: "-1.4s" },
    { id: "belt-left", d: "M78 82 L112 78", delay: "-2.1s", strokeWidth: 1.9 },
    { id: "belt-right", d: "M112 78 L150 76", delay: "-2.8s", strokeWidth: 1.9 },
    { id: "left-leg", d: "M78 82 L68 142", delay: "-3.5s" },
    { id: "right-leg", d: "M150 76 L178 136", delay: "-4.2s" },
    { id: "base", d: "M68 142 L178 136", delay: "-4.9s", strokeWidth: 2.1 },
    { id: "sword-upper", d: "M112 78 L122 106", delay: "-5.6s" },
    { id: "sword-lower", d: "M122 106 L132 132", delay: "-6.1s" },
  ],
  travelers: [
    {
      id: "belt",
      duration: "8.6s",
      delay: "-0.4s",
      opacityValues: "0;0.74;1;1;0.56;0",
      cxValues: "78;112;150;112;78",
      cyValues: "82;78;76;78;82",
    },
    {
      id: "frame",
      duration: "12.2s",
      delay: "-2.8s",
      opacityValues: "0;0.56;0.86;0.92;0.52;0",
      cxValues: "42;78;112;150;178;68;78;42",
      cyValues: "34;82;78;76;136;142;82;34",
    },
  ],
};

const DEFAULT_COPY: Record<StarbridgeWaitingPhase, { title: string; detail: string }> = {
  thinking: {
    title: "Thinking through the next step",
    detail: "Keeping the execution lane warm while the next action is prepared.",
  },
  tools: {
    title: "Calling local tools",
    detail: "Syncing commands, arguments, and results through the runtime lane.",
  },
  web: {
    title: "Collecting web evidence",
    detail: "Pulling fresh sources before the result is written back into the task.",
  },
  files: {
    title: "Editing project files",
    detail: "Applying changes and tracking diffs before the conversation moves on.",
  },
  automation: {
    title: "Advancing automation",
    detail: "Polling the executor and recovery signals without dropping task context.",
  },
  approval: {
    title: "Waiting for approval",
    detail: "The action stays paused until you explicitly confirm the next move.",
  },
};

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

function toTranslateValues(cxValues: string, cyValues: string) {
  const xs = cxValues.split(";").map((value) => value.trim());
  const ys = cyValues.split(";").map((value) => value.trim());
  return xs.map((x, index) => `${x} ${ys[index] ?? ys[ys.length - 1] ?? "0"}`).join(";");
}

export function StarbridgeWaitingConstellation({
  variant = "inline",
  phase = "thinking",
  label,
  title,
  detail,
  className,
}: StarbridgeWaitingConstellationProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const motionMode = prefersReducedMotion ? "reduced" : "animated";
  const uniqueId = useId().replace(/:/g, "");
  const geometry = variant === "panel" ? PANEL_GEOMETRY : INLINE_GEOMETRY;
  const pathGradientId = `starbridge-waiting-path-${uniqueId}`;
  const flowGradientId = `starbridge-waiting-flow-${uniqueId}`;
  const glowGradientId = `starbridge-waiting-glow-${uniqueId}`;
  const travelerGradientId = `starbridge-waiting-traveler-${uniqueId}`;
  const glowFilterId = `starbridge-waiting-glow-filter-${uniqueId}`;
  const dustFilterId = `starbridge-waiting-dust-filter-${uniqueId}`;
  const starSymbolId = `starbridge-waiting-star-${uniqueId}`;
  const resolvedTitle = title ?? DEFAULT_COPY[phase].title;
  const resolvedDetail = detail ?? DEFAULT_COPY[phase].detail;
  const travelerTransforms = useMemo(
    () =>
      geometry.travelers.map((route) => ({
        ...route,
        translateValues: toTranslateValues(route.cxValues, route.cyValues),
      })),
    [geometry.travelers],
  );

  return (
    <div
      className={className ? `starbridge-waiting starbridge-waiting-${variant} ${className}` : `starbridge-waiting starbridge-waiting-${variant}`}
      data-motion={motionMode}
      data-phase={phase}
      data-variant={variant}
      data-testid="starbridge-waiting"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="starbridge-waiting-visual" aria-hidden="true">
        <svg className="starbridge-waiting-svg" viewBox={geometry.viewBox} preserveAspectRatio="xMidYMid meet" role="presentation" focusable="false">
          <defs>
            <linearGradient id={pathGradientId} x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="var(--starbridge-waiting-line-soft)" />
              <stop offset="36%" stopColor="var(--starbridge-waiting-line-core)" />
              <stop offset="62%" stopColor="var(--starbridge-waiting-line-bright)" />
              <stop offset="100%" stopColor="var(--starbridge-waiting-line-soft)" />
            </linearGradient>
            <linearGradient id={flowGradientId} x1="0%" y1="100%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="var(--starbridge-waiting-flow-soft)" />
              <stop offset="42%" stopColor="var(--starbridge-waiting-flow-bright)" />
              <stop offset="56%" stopColor="var(--starbridge-waiting-flow-core)" />
              <stop offset="100%" stopColor="var(--starbridge-waiting-flow-soft)" />
            </linearGradient>
            <radialGradient id={glowGradientId} cx="50%" cy="50%" r="62%">
              <stop offset="0%" stopColor="var(--starbridge-waiting-node-glow-core)" />
              <stop offset="58%" stopColor="var(--starbridge-waiting-node-glow-soft)" />
              <stop offset="100%" stopColor="transparent" />
            </radialGradient>
            <radialGradient id={travelerGradientId} cx="50%" cy="50%" r="62%">
              <stop offset="0%" stopColor="var(--starbridge-waiting-traveler-core)" />
              <stop offset="60%" stopColor="var(--starbridge-waiting-traveler-glow)" />
              <stop offset="100%" stopColor="transparent" />
            </radialGradient>
            <filter id={glowFilterId} x="-80%" y="-80%" width="260%" height="260%">
              <feGaussianBlur stdDeviation="2.8" />
            </filter>
            <filter id={dustFilterId} x="-80%" y="-80%" width="260%" height="260%">
              <feGaussianBlur stdDeviation="1.4" />
            </filter>
            <symbol id={starSymbolId} viewBox="-10 -10 20 20">
              <path fill="currentColor" d="M0 -7.6 L1.8 -1.8 L7.6 0 L1.8 1.8 L0 7.6 L-1.8 1.8 L-7.6 0 L-1.8 -1.8 Z" />
              <path fill="currentColor" opacity="0.78" d="M0 -4.7 L0.88 -0.88 L4.7 0 L0.88 0.88 L0 4.7 L-0.88 0.88 L-4.7 0 L-0.88 -0.88 Z" />
              <circle cx="0" cy="0" r="0.72" fill="#ffffff" opacity="0.94" />
            </symbol>
          </defs>

          <g className="starbridge-waiting-paths">
            {geometry.paths.map((path) => (
              <g key={path.id}>
                <path
                  d={path.d}
                  className="starbridge-waiting-path-under"
                  stroke={`url(#${pathGradientId})`}
                  style={path.strokeWidth ? { strokeWidth: `${path.strokeWidth + 2.2}px` } : undefined}
                />
                <path
                  d={path.d}
                  className="starbridge-waiting-path-main"
                  stroke={`url(#${pathGradientId})`}
                  style={path.strokeWidth ? { strokeWidth: `${path.strokeWidth}px` } : undefined}
                />
              </g>
            ))}
            {!prefersReducedMotion
              ? geometry.paths.map((path) => (
                  <path
                    key={`${path.id}-flow`}
                    d={path.d}
                    pathLength={100}
                    className="starbridge-waiting-path-flow"
                    stroke={`url(#${flowGradientId})`}
                    style={path.strokeWidth ? { animationDelay: path.delay, strokeWidth: `${path.strokeWidth + 0.8}px` } : { animationDelay: path.delay }}
                  />
                ))
              : null}
          </g>

          <g className="starbridge-waiting-nodes">
            {geometry.nodes.map((node, index) => {
              const haloRadius = node.tone === "beacon" ? 10.8 : node.tone === "hub" ? 9.1 : node.tone === "anchor" ? 8.3 : 7.2;
              const coreRadius = node.tone === "beacon" ? 2.3 : node.tone === "hub" ? 2 : 1.7;
              const starSize = node.tone === "beacon" ? 9.6 : node.tone === "hub" ? 8.4 : 7.2;
              return (
                <g key={node.id} className={`starbridge-waiting-node starbridge-waiting-node-${node.tone}`} transform={`translate(${node.x} ${node.y})`}>
                  <circle className="starbridge-waiting-node-halo" r={haloRadius} fill={`url(#${glowGradientId})`} filter={`url(#${glowFilterId})`} />
                  <circle className="starbridge-waiting-node-core" r={coreRadius} />
                  <use
                    href={`#${starSymbolId}`}
                    className="starbridge-waiting-node-star"
                    width={starSize}
                    height={starSize}
                    x={-(starSize / 2)}
                    y={-(starSize / 2)}
                    style={!prefersReducedMotion ? { animationDelay: `${index * 0.34}s` } : undefined}
                  />
                </g>
              );
            })}
          </g>

          {!prefersReducedMotion ? (
            <g className="starbridge-waiting-travelers">
              {travelerTransforms.map((route, index) => (
                <g key={route.id} className="starbridge-waiting-traveler" data-testid={`starbridge-waiting-traveler-${index}`}>
                  <g className="starbridge-waiting-traveler-motion">
                    <animateTransform attributeName="transform" type="translate" dur={route.duration} begin={route.delay} values={route.translateValues} repeatCount="indefinite" />
                    <animate attributeName="opacity" dur={route.duration} begin={route.delay} values={route.opacityValues} repeatCount="indefinite" />
                    <circle className="starbridge-waiting-traveler-halo" r={7.3} filter={`url(#${glowFilterId})`} fill={`url(#${travelerGradientId})`} />
                    <use href={`#${starSymbolId}`} className="starbridge-waiting-traveler-star" width={10.4} height={10.4} x={-5.2} y={-5.2} />
                    <circle className="starbridge-waiting-traveler-core" r={1.6} />
                  </g>
                  {[0.34, 0.7, 1.06].map((shift, dustIndex) => (
                    <g key={`${route.id}-dust-${dustIndex}`} className="starbridge-waiting-dust-motion">
                      <animateTransform attributeName="transform" type="translate" dur={route.duration} begin={shiftBegin(route.delay, shift)} values={route.translateValues} repeatCount="indefinite" />
                      <animate attributeName="opacity" dur={route.duration} begin={shiftBegin(route.delay, shift)} values="0;0.46;0.22;0.06;0" repeatCount="indefinite" />
                      <circle className="starbridge-waiting-dust" r={dustIndex === 0 ? 1.42 : dustIndex === 1 ? 1.18 : 0.94} filter={`url(#${dustFilterId})`} />
                    </g>
                  ))}
                </g>
              ))}
            </g>
          ) : null}
        </svg>
      </div>

      <div className="starbridge-waiting-copy">
        {label ? <span className="starbridge-waiting-label">{label}</span> : null}
        <strong className="starbridge-waiting-title">{resolvedTitle}</strong>
        {resolvedDetail ? <p className="starbridge-waiting-detail">{resolvedDetail}</p> : null}
      </div>
    </div>
  );
}
