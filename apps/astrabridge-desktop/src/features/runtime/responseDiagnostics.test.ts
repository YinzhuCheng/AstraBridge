import { describe, expect, it } from "vitest";

import { coerceResponseDiagnostics, formatResponseDiagnostics, summarizeResponseDiagnosticsInline } from "./responseDiagnostics";

describe("response diagnostics helpers", () => {
  it("coerces structured diagnostics and keeps only safe summary fields", () => {
    const diagnostics = coerceResponseDiagnostics({
      text_excerpt: "ok",
      reasoning_summary: "planned next step",
      warnings: [{ code: "tool_call_repair", severity: "warning", message: "Malformed JSON was repaired." }],
      provider_data_keys: ["output_types", "provider_response_id"],
      raw_ref: { kind: "responses_output", redaction_status: "redacted", locator: "resp_123" },
    });

    expect(diagnostics).toMatchObject({
      text_excerpt: "ok",
      reasoning_summary: "planned next step",
      provider_data_keys: ["output_types", "provider_response_id"],
      raw_ref: { kind: "responses_output", redaction_status: "redacted" },
    });
    expect(diagnostics?.warnings?.[0]).toMatchObject({
      code: "tool_call_repair",
      severity: "warning",
    });
  });

  it("formats diagnostics for key-test output", () => {
    const text = formatResponseDiagnostics({
      text_excerpt: "ok",
      warnings: [{ code: "tool_call_repair", severity: "warning", message: "Malformed JSON was repaired." }],
      provider_data_keys: ["output_types"],
      raw_ref: { kind: "responses_output", redaction_status: "redacted" },
    });

    expect(text).toContain("Excerpt: ok");
    expect(text).toContain("tool_call_repair");
    expect(text).toContain("Provider data keys: output_types");
    expect(text).toContain("responses_output / redacted");
  });

  it("prefers warning summaries for inline health rows", () => {
    const text = summarizeResponseDiagnosticsInline({
      warnings: [{ code: "tool_call_repair", severity: "warning", message: "Malformed JSON was repaired." }],
      raw_ref: { kind: "responses_output", redaction_status: "redacted" },
    });

    expect(text).toBe("[warning/tool_call_repair] Malformed JSON was repaired.");
  });
});
