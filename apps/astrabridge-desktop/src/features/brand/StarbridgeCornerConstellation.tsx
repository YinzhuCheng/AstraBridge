import { useEffect, useId, useMemo, useState } from "react";

type StarbridgeCornerConstellationProps = {
  variant?: "settings" | "guard";
  className?: string;
};

type ConstellationPath = {
  id: string;
  d: string;
  delay: string;
};

type ConstellationNode = {
  id: string;
  x: number;
  y: number;
  tone: "anchor" | "relay" | "hub";
};

type TravelerRoute = {
  id: string;
  duration: string;
  delay: string;
  opacityValues: string;
  cxValues: string;
  cyValues: string;
};

const CONSTELLATION_PATHS: ConstellationPath[] = [
  { id: "shoulders", d: "M56 38 L148 54", delay: "0s" },
  { id: "left-arm-to-belt", d: "M56 38 L84 92", delay: "-0.8s" },
  { id: "right-arm-to-belt", d: "M148 54 L168 84", delay: "-1.5s" },
  { id: "belt-left", d: "M84 92 L120 88", delay: "-2.1s" },
  { id: "belt-right", d: "M120 88 L168 84", delay: "-2.9s" },
  { id: "left-leg", d: "M84 92 L76 160", delay: "-3.5s" },
  { id: "right-leg", d: "M168 84 L192 148", delay: "-4.1s" },
  { id: "base", d: "M76 160 L192 148", delay: "-4.8s" },
  { id: "sword-upper", d: "M120 88 L128 118", delay: "-5.3s" },
  { id: "sword-lower", d: "M128 118 L136 146", delay: "-5.9s" },
];

const CONSTELLATION_NODES: ConstellationNode[] = [
  { id: "betelgeuse", x: 56, y: 38, tone: "hub" },
  { id: "bellatrix", x: 148, y: 54, tone: "anchor" },
  { id: "alnitak", x: 84, y: 92, tone: "hub" },
  { id: "alnilam", x: 120, y: 88, tone: "hub" },
  { id: "mintaka", x: 168, y: 84, tone: "hub" },
  { id: "saiph", x: 76, y: 160, tone: "anchor" },
  { id: "rigel", x: 192, y: 148, tone: "hub" },
  { id: "sword-upper", x: 128, y: 118, tone: "relay" },
  { id: "sword-lower", x: 136, y: 146, tone: "relay" },
];

const TRAVELER_ROUTES: TravelerRoute[] = [
  {
    id: "belt",
    duration: "8.6s",
    delay: "0s",
    opacityValues: "0;0.78;1;1;0.58;0",
    cxValues: "84;120;168;120;84",
    cyValues: "92;88;84;88;92",
  },
  {
    id: "sword",
    duration: "7.8s",
    delay: "-1.8s",
    opacityValues: "0;0.68;0.96;1;0.64;0",
    cxValues: "120;128;136;128;120",
    cyValues: "88;118;146;118;88",
  },
  {
    id: "frame",
    duration: "12.4s",
    delay: "-3.6s",
    opacityValues: "0;0.52;0.86;0.94;0.56;0",
    cxValues: "56;84;120;168;192;76;84;56",
    cyValues: "38;92;88;84;148;160;92;38",
  },
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

function toTranslateValues(cxValues: string, cyValues: string) {
  const xs = cxValues.split(";").map((value) => value.trim());
  const ys = cyValues.split(";").map((value) => value.trim());
  return xs.map((x, index) => `${x} ${ys[index] ?? ys[ys.length - 1] ?? "0"}`).join(";");
}

export function StarbridgeCornerConstellation({ variant = "settings", className }: StarbridgeCornerConstellationProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const motionMode = prefersReducedMotion ? "reduced" : "animated";
  const uniqueId = useId().replace(/:/g, "");
  const baseGradientId = `starbridge-corner-base-${uniqueId}`;
  const sparkleGradientId = `starbridge-corner-sparkle-${uniqueId}`;
  const traceGradientId = `starbridge-corner-trace-${uniqueId}`;
  const traceHaloGradientId = `starbridge-corner-trace-halo-${uniqueId}`;
  const glowFilterId = `starbridge-corner-glow-${uniqueId}`;
  const dustFilterId = `starbridge-corner-dust-${uniqueId}`;
  const starSymbolId = `starbridge-corner-star-${uniqueId}`;
  const toneClass = variant === "guard" ? "starbridge-corner-accent starbridge-corner-accent-guard" : "starbridge-corner-accent starbridge-corner-accent-settings";
  const travelerTransforms = useMemo(
    () =>
      TRAVELER_ROUTES.map((route) => ({
        ...route,
        translateValues: toTranslateValues(route.cxValues, route.cyValues),
      })),
    [],
  );

  return (
    <div
      className={className ? `${toneClass} ${className}` : toneClass}
      data-motion={motionMode}
      data-testid="starbridge-corner-accent"
      aria-hidden="true"
    >
      <svg className="starbridge-corner-svg" viewBox="0 0 236 188" role="presentation" focusable="false">
        <defs>
          <linearGradient id={baseGradientId} x1="4%" y1="88%" x2="92%" y2="18%">
            <stop offset="0%" stopColor="#d7e1ee" stopOpacity="0.24" />
            <stop offset="30%" stopColor="#eef3fa" stopOpacity="0.48" />
            <stop offset="56%" stopColor="#f7fafe" stopOpacity="0.74" />
            <stop offset="100%" stopColor="#d6e0ee" stopOpacity="0.3" />
          </linearGradient>
          <radialGradient id={sparkleGradientId} cx="50%" cy="50%" r="60%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="1" />
            <stop offset="42%" stopColor="#f2f6fb" stopOpacity="0.9" />
            <stop offset="74%" stopColor="#d6e2f1" stopOpacity="0.3" />
            <stop offset="100%" stopColor="#b9cce7" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={traceGradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#eef3fa" stopOpacity="0" />
            <stop offset="24%" stopColor="#eef3fa" stopOpacity="0.16" />
            <stop offset="48%" stopColor="#ffffff" stopOpacity="1" />
            <stop offset="68%" stopColor="#d8e4f5" stopOpacity="0.88" />
            <stop offset="100%" stopColor="#c0d4ef" stopOpacity="0" />
          </linearGradient>
          <linearGradient id={traceHaloGradientId} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#e9f0fa" stopOpacity="0" />
            <stop offset="34%" stopColor="#d9e7fb" stopOpacity="0.4" />
            <stop offset="50%" stopColor="#fdfefe" stopOpacity="0.96" />
            <stop offset="66%" stopColor="#d5e4f8" stopOpacity="0.42" />
            <stop offset="100%" stopColor="#b8cde8" stopOpacity="0" />
          </linearGradient>
          <filter id={glowFilterId} x="-60%" y="-60%" width="220%" height="220%">
            <feGaussianBlur stdDeviation="3.4" />
          </filter>
          <filter id={dustFilterId} x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="1.8" />
          </filter>
          <symbol id={starSymbolId} viewBox="-12 -12 24 24">
            <path fill="currentColor" d="M0 -8.8 L2.1 -2.1 L8.8 0 L2.1 2.1 L0 8.8 L-2.1 2.1 L-8.8 0 L-2.1 -2.1 Z" />
            <path fill="currentColor" opacity="0.82" d="M0 -5.6 L1.05 -1.05 L5.6 0 L1.05 1.05 L0 5.6 L-1.05 1.05 L-5.6 0 L-1.05 -1.05 Z" />
            <circle cx="0" cy="0" r="0.9" fill="#ffffff" opacity="0.96" />
          </symbol>
        </defs>

        <g className="starbridge-corner-links">
          {CONSTELLATION_PATHS.map((path) => (
            <g key={path.id}>
              <path d={path.d} className={`starbridge-corner-link-under starbridge-corner-link-under-${path.id}`} stroke={`url(#${baseGradientId})`} />
              <path d={path.d} className={`starbridge-corner-link starbridge-corner-link-${path.id}`} stroke={`url(#${baseGradientId})`} />
            </g>
          ))}
          {!prefersReducedMotion
            ? CONSTELLATION_PATHS.map((path) => (
                <g key={`${path.id}-flow`}>
                  <path
                    d={path.d}
                    pathLength={100}
                    className="starbridge-corner-link-flow-halo"
                    style={{ animationDelay: path.delay, stroke: `url(#${traceHaloGradientId})` }}
                  />
                  <path
                    d={path.d}
                    pathLength={100}
                    className="starbridge-corner-link-flow"
                    style={{ animationDelay: path.delay, stroke: `url(#${traceGradientId})` }}
                  />
                </g>
              ))
            : null}
        </g>

        <g className="starbridge-corner-nodes">
          {CONSTELLATION_NODES.map((node, index) => (
            <g key={node.id} transform={`translate(${node.x} ${node.y})`} className={`starbridge-corner-node starbridge-corner-node-${node.tone}`}>
              <circle className="starbridge-corner-node-halo" r={node.tone === "hub" ? 13.8 : node.tone === "anchor" ? 12.4 : 10.8} fill={`url(#${sparkleGradientId})`} filter={`url(#${glowFilterId})`} />
              <circle className="starbridge-corner-node-core" r={node.tone === "hub" ? 3.15 : node.tone === "anchor" ? 2.7 : 2.35} />
              <use
                href={`#${starSymbolId}`}
                className="starbridge-corner-node-star"
                width={node.tone === "hub" ? 13.2 : node.tone === "anchor" ? 11.6 : 9.8}
                height={node.tone === "hub" ? 13.2 : node.tone === "anchor" ? 11.6 : 9.8}
                x={node.tone === "hub" ? -6.6 : node.tone === "anchor" ? -5.8 : -4.9}
                y={node.tone === "hub" ? -6.6 : node.tone === "anchor" ? -5.8 : -4.9}
                style={!prefersReducedMotion ? { animationDelay: `${index * 0.48}s` } : undefined}
              />
            </g>
          ))}
        </g>

        {!prefersReducedMotion ? (
          <g className="starbridge-corner-travelers">
            {travelerTransforms.map((route, index) => (
              <g key={route.id} className="starbridge-corner-traveler" data-testid={`starbridge-traveler-${index}`}>
                <g className="starbridge-corner-traveler-motion">
                  <animateTransform attributeName="transform" type="translate" dur={route.duration} begin={route.delay} values={route.translateValues} repeatCount="indefinite" />
                  <animate attributeName="opacity" dur={route.duration} begin={route.delay} values={route.opacityValues} repeatCount="indefinite" />
                  <circle className="starbridge-corner-traveler-halo" r={8.6} filter={`url(#${glowFilterId})`} />
                  <use href={`#${starSymbolId}`} className="starbridge-corner-traveler-star" width={12.4} height={12.4} x={-6.2} y={-6.2} />
                  <circle className="starbridge-corner-traveler-core" r={1.75} />
                </g>
                {[0.34, 0.68, 1.04, 1.38].map((shift, dustIndex) => (
                  <g key={`${route.id}-dust-${dustIndex}`} className="starbridge-corner-dust-motion">
                    <animateTransform attributeName="transform" type="translate" dur={route.duration} begin={shiftBegin(route.delay, shift)} values={route.translateValues} repeatCount="indefinite" />
                    <animate attributeName="opacity" dur={route.duration} begin={shiftBegin(route.delay, shift)} values="0;0.48;0.26;0.08;0" repeatCount="indefinite" />
                    <circle className="starbridge-corner-dust" r={dustIndex === 0 ? 1.9 : dustIndex === 1 ? 1.55 : 1.18} filter={`url(#${dustFilterId})`} />
                  </g>
                ))}
              </g>
            ))}
          </g>
        ) : null}
      </svg>
    </div>
  );
}
