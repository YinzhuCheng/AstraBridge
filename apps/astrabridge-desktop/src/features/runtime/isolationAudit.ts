import type { IsolationAuditResponse, ProjectFile } from "../../types";

function normalizeWindowsPath(path: string) {
  return path.replace(/\//g, "\\");
}

function slugifyLabel(label: string) {
  const normalized = label.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return normalized || "browser-smoke";
}

export function projectCaptureRoot(project?: Pick<ProjectFile, "workspace_root"> | null) {
  const workspaceRoot = String(project?.workspace_root ?? "").trim();
  if (!workspaceRoot) return "";
  return normalizeWindowsPath(`${workspaceRoot}\\.astrabridge\\captures`);
}

export function suggestedDogfoodScreenshotPath(project?: Pick<ProjectFile, "workspace_root"> | null, label = "browser smoke") {
  const captureRoot = projectCaptureRoot(project);
  if (!captureRoot) return "";
  return `${captureRoot}\\${slugifyLabel(label)}.png`;
}

export function isolationAuditSummary(audit?: IsolationAuditResponse | null) {
  const checks = Array.isArray(audit?.checks) ? audit?.checks : [];
  const passed = checks.filter((item) => item?.ok).length;
  const failedChecks = checks.filter((item) => item && !item.ok);
  return {
    total: checks.length,
    passed,
    failed: failedChecks.length,
    failedChecks,
  };
}
