import type { RuntimeFailureAction, RuntimeFailureNotice } from "../../types";

export type RuntimeErrorNotice = RuntimeFailureNotice | null | undefined;
export type RuntimeErrorAction = RuntimeFailureAction;

export function runtimeErrorNoticeActions(runtimeError: RuntimeErrorNotice): RuntimeErrorAction[] {
  if (!runtimeError?.recommended_actions?.length) {
    return [];
  }
  const seen = new Set<string>();
  const actions: RuntimeErrorAction[] = [];
  for (const item of runtimeError.recommended_actions) {
    const label = item.label?.trim();
    if (!label) {
      continue;
    }
    const key = `${item.action}:${item.target ?? ""}:${label}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    actions.push(item);
    if (actions.length >= 3) {
      break;
    }
  }
  return actions;
}

export function runtimeErrorNoticeText(runtimeError: RuntimeErrorNotice): string {
  if (!runtimeError?.summary) {
    return "";
  }
  const parts = [runtimeError.summary.trim()];
  if (runtimeError.actionable_hint?.trim()) {
    parts.push(runtimeError.actionable_hint.trim());
  }
  const suggested = runtimeErrorNoticeActions(runtimeError).map((item: RuntimeErrorAction) => item.label.trim());
  if (suggested.length > 0) {
    parts.push(`Suggested: ${suggested.join(", ")}.`);
  }
  return parts.join(" ").trim();
}

export function runtimeErrorNoticeInline(runtimeError: RuntimeErrorNotice): string {
  if (!runtimeError?.summary) {
    return "";
  }
  return runtimeError.actionable_hint?.trim() ? `${runtimeError.summary.trim()} ${runtimeError.actionable_hint.trim()}`.trim() : runtimeError.summary.trim();
}

/**
 * Composer failures are surfaced in the compact conversation status strip. A
 * persisted runtime diagnostic is more actionable, so it takes precedence.
 */
export function composerFailureNoticeText(sendFailure: string | null | undefined, runtimeError: RuntimeErrorNotice): string {
  const failure = sendFailure?.trim();
  if (!failure || runtimeError?.summary?.trim()) {
    return "";
  }
  return failure.replace(/^(?:模型运行失败：|Model run failed:)\s*/i, "").trim();
}

export function latestCompletedTurnSuppressesRuntimeError(
  thread: { turns?: Array<{ status?: string | null; error?: unknown }> } | null | undefined,
) {
  const turns = Array.isArray(thread?.turns) ? thread.turns : [];
  const latest = turns.length > 0 ? turns[turns.length - 1] : undefined;
  if (!latest || String(latest.status ?? "").toLowerCase() !== "completed") {
    return false;
  }
  const error = latest.error;
  return error == null || error === "" || (typeof error === "object" && !Array.isArray(error) && Object.keys(error as object).length === 0);
}
