import type { RouterModelEntry } from "../../types";

export type ModelAuthorityState = {
  tier: "A" | "B" | "C" | "D" | "unknown";
  label: string;
  tone: "ok" | "warning" | "danger";
  sendBlocked: boolean;
  notices: string[];
};

function dedupe(values: string[]) {
  const seen = new Set<string>();
  const unique: string[] = [];
  for (const value of values) {
    const text = value.trim();
    if (!text || seen.has(text)) continue;
    seen.add(text);
    unique.push(text);
  }
  return unique;
}

export function modelAuthorityState(model: Pick<RouterModelEntry, "authority_tier" | "authority_reason" | "parallel_tool_call_status"> | null | undefined): ModelAuthorityState | null {
  if (!model) return null;
  const tier = String(model.authority_tier ?? "").trim().toUpperCase();
  const reason = String(model.authority_reason ?? "").trim();
  const parallelStatus = String(model.parallel_tool_call_status ?? "").trim().toLowerCase();

  if (tier === "A") {
    return {
      tier: "A",
      label: "Tier A agent",
      tone: "ok",
      sendBlocked: false,
      notices: dedupe([
        parallelStatus === "serial_only" ? "Parallel tool calls are disabled for this model unless a parallel smoke test passes." : "",
      ]),
    };
  }

  if (tier === "B") {
    return {
      tier: "B",
      label: "Tier B propose-first",
      tone: "warning",
      sendBlocked: false,
      notices: dedupe([
        reason || "This model should stay in propose-first mode for apply or execute actions.",
        parallelStatus === "serial_only" ? "Parallel tool calls are disabled for this model unless a parallel smoke test passes." : "",
      ]),
    };
  }

  if (tier === "C") {
    return {
      tier: "C",
      label: "Tier C review-only",
      tone: "warning",
      sendBlocked: false,
      notices: dedupe([
        reason || "This model should stay in review or explain mode because structured tool use is not verified.",
        parallelStatus === "serial_only" ? "Parallel tool calls are disabled for this model unless a parallel smoke test passes." : "",
      ]),
    };
  }

  if (tier === "D") {
    return {
      tier: "D",
      label: "Tier D agent disabled",
      tone: "danger",
      sendBlocked: true,
      notices: dedupe([
        reason || "This model is not eligible for AstraBridge agent mode.",
      ]),
    };
  }

  return {
    tier: "unknown",
    label: "Authority unknown",
    tone: "warning",
    sendBlocked: false,
    notices: dedupe([
      reason || "Model authority is unknown. Keep approvals and verification on until this model is classified.",
    ]),
  };
}
