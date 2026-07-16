type BootstrapState = "loading" | "stalled" | "error" | "ready";

type BootstrapShellApi = {
  note?: (message: string) => void;
  stalled?: (message?: string) => void;
  ready?: (message?: string) => void;
  fail?: (message?: string) => void;
  state?: () => BootstrapState | null;
};

const READY_SURFACE_SELECTORS = [
  "[data-testid='app-shell']",
  ".launcher-shell",
  ".launch-isolation-shell",
];

declare global {
  interface Window {
    __AB_BOOTSTRAP__?: BootstrapShellApi;
  }
}

function bootstrapShellApi() {
  if (typeof window === "undefined") return null;
  return window.__AB_BOOTSTRAP__ ?? null;
}

export function bootstrapFailureMessage(
  error: unknown,
  fallback = "AstraBridge 前端入口未能完成启动。",
) {
  if (error instanceof Error) {
    const message = error.message.trim();
    return message ? `${fallback} ${message}` : fallback;
  }
  if (typeof error === "string" && error.trim()) {
    return `${fallback} ${error.trim()}`;
  }
  if (error != null) {
    try {
      const serialized = JSON.stringify(error);
      if (serialized && serialized !== "{}") return `${fallback} ${serialized}`;
    } catch {
      // Fall through to the generic fallback below.
    }
  }
  return fallback;
}

export function bootstrapNote(message: string) {
  bootstrapShellApi()?.note?.(message);
}

export function bootstrapReady(message?: string) {
  bootstrapShellApi()?.ready?.(message);
}

export function bootstrapStalled(message?: string) {
  bootstrapShellApi()?.stalled?.(message);
}

export function bootstrapFail(error: unknown, fallback?: string) {
  bootstrapShellApi()?.fail?.(bootstrapFailureMessage(error, fallback));
}

export function bootstrapState() {
  return bootstrapShellApi()?.state?.() ?? null;
}

export function scheduleBootstrapReady(message?: string) {
  if (typeof window === "undefined") return;
  const startedAt = Date.now();
  let stalledNotified = false;

  const tick = () => {
    if (READY_SURFACE_SELECTORS.some((selector) => document.querySelector(selector))) {
      bootstrapReady(message);
      return;
    }
    if (!stalledNotified && Date.now() - startedAt >= 3000) {
      stalledNotified = true;
      bootstrapStalled("前端入口已连通，但首屏仍在等待真实界面挂载。");
    }
    window.requestAnimationFrame(tick);
  };

  window.requestAnimationFrame(tick);
}
