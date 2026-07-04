import { useEffect, useRef, useState } from "react";

import type { CursorEnhancementPreference } from "../../types";

import { resolveCursorRenderQuality, type CursorRenderQuality } from "./cursorEnhancement";

type CursorMode = "default" | "hover" | "drag" | "text";

type CursorClassification = {
  passiveMode: CursorMode;
  canDrag: boolean;
};

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return undefined;
    }
    const media = window.matchMedia(query);
    const apply = () => setMatches(media.matches);
    apply();
    media.addEventListener?.("change", apply);
    return () => media.removeEventListener?.("change", apply);
  }, [query]);

  return matches;
}

function nearestElement(target: EventTarget | null) {
  return target instanceof Element ? target : null;
}

function classifyCursorTarget(target: EventTarget | null): CursorClassification {
  const element = nearestElement(target);
  if (!element) {
    return { passiveMode: "default", canDrag: false };
  }

  const editableTarget = element.closest(
    'textarea, input:not([type="button"]):not([type="checkbox"]):not([type="radio"]):not([type="range"]):not([type="submit"]), [contenteditable=""], [contenteditable="true"]',
  );
  if (editableTarget) {
    return { passiveMode: "text", canDrag: false };
  }

  const dragHandle = element.closest('.resize-handle, .composer-resize-grip, [role="separator"], [data-cursor-mode="drag"]');
  let resolvedCursor = "";
  try {
    resolvedCursor = window.getComputedStyle(element).cursor;
  } catch {
    resolvedCursor = "";
  }
  const dragCursor = /resize|grab/i.test(resolvedCursor);
  if (dragHandle || dragCursor) {
    return { passiveMode: "hover", canDrag: true };
  }

  if (/text/i.test(resolvedCursor)) {
    return { passiveMode: "text", canDrag: false };
  }

  const interactiveTarget = element.closest(
    'button, a[href], summary, select, option, label, [role="button"], [role="tab"], [role="menuitem"], [role="switch"], [role="checkbox"], [aria-haspopup="menu"], [data-cursor-mode="hover"]',
  );
  if (interactiveTarget || resolvedCursor === "pointer") {
    return { passiveMode: "hover", canDrag: false };
  }

  return { passiveMode: "default", canDrag: false };
}

type CursorPhysicsState = {
  visible: boolean;
  headX: number;
  headY: number;
  trailX: number;
  trailY: number;
  dustAX: number;
  dustAY: number;
  dustBX: number;
  dustBY: number;
  targetX: number;
  targetY: number;
};

type StarbridgeCursorOverlayProps = {
  preference?: CursorEnhancementPreference;
};

type NetworkConnectionLike = {
  saveData?: boolean;
  addEventListener?: (type: string, listener: EventListenerOrEventListenerObject) => void;
  removeEventListener?: (type: string, listener: EventListenerOrEventListenerObject) => void;
};

function readCursorPowerSignals() {
  if (typeof navigator === "undefined") {
    return { saveData: false, hardwareConcurrency: null as number | null, deviceMemory: null as number | null };
  }
  const navigatorWithHints = navigator as Navigator & {
    connection?: NetworkConnectionLike;
    deviceMemory?: number;
  };
  return {
    saveData: Boolean(navigatorWithHints.connection?.saveData),
    hardwareConcurrency: typeof navigator.hardwareConcurrency === "number" ? navigator.hardwareConcurrency : null,
    deviceMemory: typeof navigatorWithHints.deviceMemory === "number" ? navigatorWithHints.deviceMemory : null,
  };
}

export function StarbridgeCursorOverlay({ preference = "auto" }: StarbridgeCursorOverlayProps) {
  const prefersReducedMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const hasFinePointer = useMediaQuery("(pointer: fine)");
  const [powerSignals, setPowerSignals] = useState(() => readCursorPowerSignals());
  const [visible, setVisible] = useState(false);
  const [mode, setMode] = useState<CursorMode>("default");
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const headAnchorRef = useRef<HTMLDivElement | null>(null);
  const trailAnchorRef = useRef<HTMLDivElement | null>(null);
  const dustAAnchorRef = useRef<HTMLDivElement | null>(null);
  const dustBAnchorRef = useRef<HTMLDivElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const passiveModeRef = useRef<CursorMode>("default");
  const pressedDragRef = useRef(false);
  const physicsRef = useRef<CursorPhysicsState>({
    visible: false,
    headX: -40,
    headY: -40,
    trailX: -40,
    trailY: -40,
    dustAX: -40,
    dustAY: -40,
    dustBX: -40,
    dustBY: -40,
    targetX: -40,
    targetY: -40,
  });
  const quality: CursorRenderQuality = resolveCursorRenderQuality(preference, {
    hasFinePointer,
    prefersReducedMotion,
    saveData: powerSignals.saveData,
    hardwareConcurrency: powerSignals.hardwareConcurrency,
    deviceMemory: powerSignals.deviceMemory,
  });

  useEffect(() => {
    if (typeof navigator === "undefined") {
      return undefined;
    }
    const navigatorWithHints = navigator as Navigator & {
      connection?: NetworkConnectionLike;
      deviceMemory?: number;
    };
    const connection = navigatorWithHints.connection;
    const apply = () => setPowerSignals(readCursorPowerSignals());
    apply();
    connection?.addEventListener?.("change", apply);
    return () => connection?.removeEventListener?.("change", apply);
  }, []);

  useEffect(() => {
    if (quality === "hidden" || typeof window === "undefined") {
      return undefined;
    }

    const state = physicsRef.current;
    const settleThreshold = quality === "minimal" ? 0.18 : quality === "economy" ? 0.32 : 0.48;

    const applyTransforms = () => {
      const angle = Math.atan2(state.targetY - state.trailY, state.targetX - state.trailX) * (180 / Math.PI);
      overlayRef.current?.style.setProperty("--starbridge-cursor-angle", `${Number.isFinite(angle) ? angle : 18}deg`);

      if (headAnchorRef.current) {
        headAnchorRef.current.style.transform = `translate3d(${state.headX}px, ${state.headY}px, 0)`;
      }
      if (trailAnchorRef.current) {
        trailAnchorRef.current.style.transform = `translate3d(${state.trailX}px, ${state.trailY}px, 0)`;
      }
      if (dustAAnchorRef.current) {
        dustAAnchorRef.current.style.transform = `translate3d(${state.dustAX}px, ${state.dustAY}px, 0)`;
      }
      if (dustBAnchorRef.current) {
        dustBAnchorRef.current.style.transform = `translate3d(${state.dustBX}px, ${state.dustBY}px, 0)`;
      }
    };

    const queueFrame = () => {
      if (animationFrameRef.current != null) {
        return;
      }
      animationFrameRef.current = window.requestAnimationFrame(renderFrame);
    };

    const hideOverlay = () => {
      state.visible = false;
      pressedDragRef.current = false;
      passiveModeRef.current = "default";
      if (animationFrameRef.current != null) {
        window.cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      setVisible(false);
      setMode("default");
    };

    const updateSemanticMode = (target: EventTarget | null, _buttons: number) => {
      const classification = classifyCursorTarget(target);
      passiveModeRef.current = classification.passiveMode;
      const nextMode = pressedDragRef.current ? "drag" : classification.passiveMode;
      setMode((current) => (current === nextMode ? current : nextMode));
      return classification;
    };

    const onPointerMove = (event: PointerEvent) => {
      if (event.pointerType && event.pointerType !== "mouse" && event.pointerType !== "pen") {
        return;
      }
      if (!state.visible) {
        state.headX = event.clientX;
        state.headY = event.clientY;
        state.trailX = event.clientX;
        state.trailY = event.clientY;
        state.dustAX = event.clientX;
        state.dustAY = event.clientY;
        state.dustBX = event.clientX;
        state.dustBY = event.clientY;
      }
      state.visible = true;
      state.targetX = event.clientX;
      state.targetY = event.clientY;
      setVisible((current) => (current ? current : true));
      updateSemanticMode(event.target, event.buttons);
      queueFrame();
    };

    const onPointerDown = (event: PointerEvent) => {
      if (event.pointerType && event.pointerType !== "mouse" && event.pointerType !== "pen") {
        return;
      }
      const classification = classifyCursorTarget(event.target);
      passiveModeRef.current = classification.passiveMode;
      pressedDragRef.current = classification.canDrag;
      setMode((current) => {
        const nextMode = classification.canDrag ? "drag" : classification.passiveMode;
        return current === nextMode ? current : nextMode;
      });
    };

    const onPointerUp = (event: PointerEvent) => {
      if (event.pointerType && event.pointerType !== "mouse" && event.pointerType !== "pen") {
        return;
      }
      pressedDragRef.current = false;
      setMode((current) => (current === passiveModeRef.current ? current : passiveModeRef.current));
    };

    const onMouseOut = (event: MouseEvent) => {
      if (!event.relatedTarget) {
        hideOverlay();
      }
    };

    const renderFrame = () => {
      animationFrameRef.current = null;
      const minimal = quality === "minimal";
      const economy = quality === "economy";
      const leadEase = minimal ? 1 : economy ? (state.visible ? 0.62 : 0.28) : state.visible ? 0.48 : 0.18;
      const trailEase = minimal ? 1 : economy ? (state.visible ? 0.22 : 0.16) : state.visible ? 0.16 : 0.12;
      const dustEase = minimal || economy ? 1 : state.visible ? 0.12 : 0.08;

      state.headX += (state.targetX - state.headX) * leadEase;
      state.headY += (state.targetY - state.headY) * leadEase;
      state.trailX += (state.targetX - state.trailX) * trailEase;
      state.trailY += (state.targetY - state.trailY) * trailEase;
      state.dustAX += (state.targetX - state.dustAX) * dustEase;
      state.dustAY += (state.targetY - state.dustAY) * dustEase;
      state.dustBX += (state.trailX - state.dustBX) * 0.16;
      state.dustBY += (state.trailY - state.dustBY) * 0.16;

      applyTransforms();

      const maxDelta = Math.max(
        Math.abs(state.targetX - state.headX),
        Math.abs(state.targetY - state.headY),
        Math.abs(state.targetX - state.trailX),
        Math.abs(state.targetY - state.trailY),
        Math.abs(state.targetX - state.dustAX),
        Math.abs(state.targetY - state.dustAY),
        Math.abs(state.trailX - state.dustBX),
        Math.abs(state.trailY - state.dustBY),
      );

      if (state.visible && maxDelta > settleThreshold) {
        queueFrame();
      }
    };

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    window.addEventListener("pointerdown", onPointerDown, { passive: true });
    window.addEventListener("pointerup", onPointerUp, { passive: true });
    window.addEventListener("pointercancel", onPointerUp, { passive: true });
    window.addEventListener("mouseout", onMouseOut);
    window.addEventListener("blur", hideOverlay);

    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerUp);
      window.removeEventListener("mouseout", onMouseOut);
      window.removeEventListener("blur", hideOverlay);
      if (animationFrameRef.current != null) {
        window.cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [quality]);

  if (quality === "hidden") {
    return null;
  }

  return (
    <div
      ref={overlayRef}
      className="starbridge-cursor-overlay"
      data-mode={mode}
      data-motion={prefersReducedMotion ? "reduced" : quality === "economy" ? "economy" : "animated"}
      data-quality={quality}
      data-visible={visible ? "true" : "false"}
      data-testid="starbridge-cursor-overlay"
      aria-hidden="true"
    >
      {quality !== "minimal" ? (
        <div ref={trailAnchorRef} className="starbridge-cursor-anchor starbridge-cursor-anchor-trail">
          <span className="starbridge-cursor-trail-body" />
        </div>
      ) : null}
      {quality === "full" ? (
        <>
          <div ref={dustBAnchorRef} className="starbridge-cursor-anchor starbridge-cursor-anchor-dust starbridge-cursor-anchor-dust-secondary">
            <span className="starbridge-cursor-dust-body" />
          </div>
          <div ref={dustAAnchorRef} className="starbridge-cursor-anchor starbridge-cursor-anchor-dust">
            <span className="starbridge-cursor-dust-body" />
          </div>
        </>
      ) : null}
      <div ref={headAnchorRef} className="starbridge-cursor-anchor starbridge-cursor-anchor-head">
        <span className="starbridge-cursor-head-body">
          <span className="starbridge-cursor-ring" />
          <span className="starbridge-cursor-core" />
          <svg className="starbridge-cursor-star" viewBox="-10 -10 20 20" role="presentation" focusable="false">
            <path fill="currentColor" d="M0 -7.6 L1.8 -1.8 L7.6 0 L1.8 1.8 L0 7.6 L-1.8 1.8 L-7.6 0 L-1.8 -1.8 Z" />
            <path fill="currentColor" opacity="0.72" d="M0 -4.6 L0.86 -0.86 L4.6 0 L0.86 0.86 L0 4.6 L-0.86 0.86 L-4.6 0 L-0.86 -0.86 Z" />
            <circle cx="0" cy="0" r="0.72" fill="white" opacity="0.96" />
          </svg>
        </span>
      </div>
    </div>
  );
}
