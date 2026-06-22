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
