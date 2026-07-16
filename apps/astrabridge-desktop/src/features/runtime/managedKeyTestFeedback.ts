import type { RouterTestResult } from "../../types";

export type ManagedKeyTestFeedback = {
  tone: "success" | "danger";
  title: string;
  provider: string;
  model: string;
  status: number | null;
  diagnostic: string;
  nextAction: string;
};

function compactDiagnostic(value: string | null | undefined, fallback: string): string {
  const normalized = value?.replace(/\s+/g, " ").trim() || fallback;
  return normalized.length <= 220 ? normalized : `${normalized.slice(0, 217).trimEnd()}...`;
}

export function summarizeManagedKeyTest(
  result: RouterTestResult,
  diagnostic: string | null,
): ManagedKeyTestFeedback {
  const passed = result.ok && result.status >= 200 && result.status < 300;
  return {
    tone: passed ? "success" : "danger",
    title: passed ? "Provider test passed" : "Provider test needs attention",
    provider: result.provider || "unknown provider",
    model: result.model || "default model",
    status: result.status,
    diagnostic: passed
      ? "The provider returned a terminal response."
      : compactDiagnostic(diagnostic, "The provider did not return a usable terminal response."),
    nextAction: passed
      ? "You can continue with a bounded task on this route."
      : "Review the diagnostic before starting a budgeted task.",
  };
}

export function summarizeManagedKeyTestError(
  provider: string | undefined,
  diagnostic: string,
): ManagedKeyTestFeedback {
  return {
    tone: "danger",
    title: "Provider test could not complete",
    provider: provider || "unknown provider",
    model: "not confirmed",
    status: null,
    diagnostic: compactDiagnostic(diagnostic, "The app did not receive a usable health-test result."),
    nextAction: "Resolve the connection or key issue, then test again before starting a budgeted task.",
  };
}
