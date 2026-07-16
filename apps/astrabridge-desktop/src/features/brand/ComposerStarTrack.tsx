import { useEffect, useId, useState } from "react";

export type ComposerStarTrackState = "idle" | "sending" | "recording" | "error" | "drop";

type ComposerStarTrackProps = {
  state: ComposerStarTrackState;
  armed?: boolean;
};

const TRACK_PATH = "M22 50 C 84 50 146 50 208 50 C 270 50 332 50 398 50";

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

export function ComposerStarTrack({ state, armed = false }: ComposerStarTrackProps) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const motionMode = prefersReducedMotion ? "reduced" : "animated";
  const uniqueId = useId().replace(/:/g, "");
  const railGradientId = `composer-track-rail-${uniqueId}`;
  const flowGradientId = `composer-track-flow-${uniqueId}`;
  const glowFilterId = `composer-track-glow-${uniqueId}`;

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
          <filter id={glowFilterId} x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur stdDeviation="2.4" />
          </filter>
        </defs>

        <g className="composer-star-track-rails">
          <path d={TRACK_PATH} className="composer-star-track-rail composer-star-track-rail-under" />
          <path d={TRACK_PATH} className="composer-star-track-rail composer-star-track-rail-main" stroke={`url(#${railGradientId})`} />
          <path d={TRACK_PATH} pathLength={100} className="composer-star-track-rail composer-star-track-rail-flow" stroke={`url(#${flowGradientId})`} />
        </g>
        {!prefersReducedMotion ? (
          <path
            d={TRACK_PATH}
            pathLength={100}
            className="composer-star-track-rail composer-star-track-rail-glow"
            stroke={`url(#${flowGradientId})`}
            filter={`url(#${glowFilterId})`}
          />
        ) : null}
      </svg>
    </div>
  );
}
