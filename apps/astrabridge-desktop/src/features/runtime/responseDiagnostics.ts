import type { ResponseDiagnostics, ResponseDiagnosticsWarning } from "../../types";

function asObject(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function text(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function warningLabel(warning: ResponseDiagnosticsWarning) {
  const code = text(warning.code);
  const severity = text(warning.severity);
  if (code && severity) return `[${severity}/${code}]`;
  if (code) return `[${code}]`;
  if (severity) return `[${severity}]`;
  return "";
}

export function coerceResponseDiagnostics(value: unknown): ResponseDiagnostics | null {
  const entry = asObject(value);
  if (!entry) return null;
  const warnings: ResponseDiagnosticsWarning[] = [];
  if (Array.isArray(entry.warnings)) {
    for (const warning of entry.warnings) {
      const item = asObject(warning);
      if (!item) continue;
      warnings.push({
        code: text(item.code) || undefined,
        severity: text(item.severity) || undefined,
        message: text(item.message) || undefined,
      });
    }
  }
  const toolCalls: Array<{ id?: string; name?: string }> = [];
  if (Array.isArray(entry.tool_calls)) {
    for (const call of entry.tool_calls) {
      const item = asObject(call);
      if (!item) continue;
      const id = text(item.id);
      const name = text(item.name);
      if (!id && !name) continue;
      toolCalls.push({ id: id || undefined, name: name || undefined });
    }
  }
  const reasoningState = asObject(entry.reasoning_state);
  const rawRef = asObject(entry.raw_ref);
  return {
    text_excerpt: text(entry.text_excerpt) || null,
    reasoning_summary: text(entry.reasoning_summary) || null,
    finish_reason: text(entry.finish_reason) || null,
    warnings,
    provider_data_keys: Array.isArray(entry.provider_data_keys) ? entry.provider_data_keys.map((item) => text(item)).filter(Boolean) : [],
    tool_calls: toolCalls,
    usage: asObject(entry.usage) ?? undefined,
    reasoning_state: reasoningState
      ? {
          provider_id: text(reasoningState.provider_id) || undefined,
          model_id: text(reasoningState.model_id) || undefined,
          replayable: Boolean(reasoningState.replayable),
          visible_summary: text(reasoningState.visible_summary) || null,
          opaque_artifact_count: typeof reasoningState.opaque_artifact_count === "number" ? reasoningState.opaque_artifact_count : undefined,
        }
      : undefined,
    raw_ref: rawRef
      ? {
          kind: text(rawRef.kind) || undefined,
          locator: text(rawRef.locator) || undefined,
          redaction_status: text(rawRef.redaction_status) || undefined,
          summary: text(rawRef.summary) || null,
        }
      : undefined,
  };
}

export function formatResponseDiagnostics(value: unknown): string | null {
  const diagnostics = coerceResponseDiagnostics(value);
  if (!diagnostics) return null;
  const lines: string[] = [];
  if (diagnostics.text_excerpt) lines.push(`Excerpt: ${diagnostics.text_excerpt}`);
  if (diagnostics.reasoning_summary) lines.push(`Reasoning: ${diagnostics.reasoning_summary}`);
  for (const warning of diagnostics.warnings ?? []) {
    const label = warningLabel(warning);
    const message = text(warning.message);
    if (!label && !message) continue;
    lines.push(`Warning: ${[label, message].filter(Boolean).join(" ")}`.trim());
  }
  if ((diagnostics.provider_data_keys ?? []).length) {
    lines.push(`Provider data keys: ${(diagnostics.provider_data_keys ?? []).join(", ")}`);
  }
  if (diagnostics.raw_ref?.kind || diagnostics.raw_ref?.redaction_status) {
    lines.push(
      `Raw artifact: ${[text(diagnostics.raw_ref?.kind), text(diagnostics.raw_ref?.redaction_status)].filter(Boolean).join(" / ")}`.trim(),
    );
  }
  return lines.length ? lines.join("\n") : null;
}

export function summarizeResponseDiagnosticsInline(value: unknown): string | null {
  const diagnostics = coerceResponseDiagnostics(value);
  if (!diagnostics) return null;
  const warning = (diagnostics.warnings ?? []).find((item) => text(item.message) || text(item.code));
  if (warning) {
    return [warningLabel(warning), text(warning.message)].filter(Boolean).join(" ").trim();
  }
  if (diagnostics.reasoning_summary) return diagnostics.reasoning_summary;
  if (diagnostics.raw_ref?.kind || diagnostics.raw_ref?.redaction_status) {
    return `artifact ${[text(diagnostics.raw_ref.kind), text(diagnostics.raw_ref.redaction_status)].filter(Boolean).join(" / ")}`.trim();
  }
  if (diagnostics.finish_reason) return `finish ${diagnostics.finish_reason}`;
  return diagnostics.text_excerpt || null;
}
