const SMOKE_TASK_PREFIX_PATTERN = /^Step\s+\d+\s+(?:source|target)\s+for\s+/i;

function trimText(value: string | null | undefined) {
  return String(value || "").trim();
}

export function visibleTaskTitle(value: string | null | undefined) {
  const trimmed = trimText(value);
  if (!trimmed) return "";
  return trimmed.replace(SMOKE_TASK_PREFIX_PATTERN, "");
}

export function visibleThreadTitle(value: string | null | undefined) {
  return visibleTaskTitle(value);
}
