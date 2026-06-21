import type { RuntimeSupervisorState } from "../../types";

type RuntimeErrorNotice = RuntimeSupervisorState["runtime_error"];
type RuntimeErrorAction = NonNullable<NonNullable<RuntimeErrorNotice>["recommended_actions"]>[number];

export function runtimeErrorNoticeText(runtimeError: RuntimeErrorNotice): string {
  if (!runtimeError?.summary) {
    return "";
  }
  const parts = [runtimeError.summary.trim()];
  if (runtimeError.actionable_hint?.trim()) {
    parts.push(runtimeError.actionable_hint.trim());
  }
  const suggested = Array.from(new Set((runtimeError.recommended_actions ?? []).map((item: RuntimeErrorAction) => item.label?.trim()).filter(Boolean))).slice(0, 3);
  if (suggested.length > 0) {
    parts.push(`Suggested: ${suggested.join(", ")}.`);
  }
  return parts.join(" ").trim();
}
