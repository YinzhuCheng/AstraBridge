import type { LocaleCode } from "../../types";

function rawErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return String(error.message || "").trim();
  }
  return String(error || "").trim();
}

export function launcherSidecarGateMessage(
  locale: LocaleCode,
  options: {
    error: unknown;
    pending: boolean;
  },
) {
  if (options.pending) {
    return locale === "zh-CN"
      ? "正在检查本地 sidecar 状态..."
      : "Checking local sidecar status...";
  }
  const message = rawErrorMessage(options.error);
  if (!message) return "";
  const normalized = message.toLowerCase();
  if (
    normalized.includes("failed to fetch") ||
    normalized.includes("did not respond in time") ||
    normalized.includes("/health")
  ) {
    return locale === "zh-CN"
      ? "当前本地 sidecar 不可用，已暂时禁用最近项目和打开/创建动作。请先在运行时面板恢复 sidecar。"
      : "The local sidecar is unavailable, so recent-project open and create/open actions are temporarily disabled. Restore the sidecar from Runtime first.";
  }
  return message;
}
