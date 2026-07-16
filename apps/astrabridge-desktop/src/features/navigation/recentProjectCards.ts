import type { ProjectSummary } from "../../types";

function firstNonEmptyLine(value: string): string {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find(Boolean) ?? "";
}

function compactWhitespace(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function looksLikePathFragment(value: string): boolean {
  return /^[a-z]:[\\/]/i.test(value)
    || value.startsWith("\\\\")
    || value.startsWith("/")
    || value.includes("\\")
    || /(?:^|[^\s])\/[^\s]/.test(value);
}

function stripPathSuffix(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";
  const pathIndex = trimmed.search(/(?:^|\s)(?:[a-z]:[\\/]|\\\\|\/[^/\s]+\/)/i);
  return pathIndex > 0 ? trimmed.slice(0, pathIndex).trim() : trimmed;
}

function sanitizeRecentProjectName(value: string): string {
  const lines = value
    .split(/\r?\n/)
    .map((line) => compactWhitespace(line))
    .filter(Boolean);
  for (const line of lines) {
    const compact = stripPathSuffix(line);
    if (compact && !looksLikePathFragment(compact)) return compact;
  }
  const singleLine = compactWhitespace(firstNonEmptyLine(value));
  if (!singleLine) return "";
  const compact = stripPathSuffix(singleLine);
  if (compact && !looksLikePathFragment(compact)) return compact;
  return "";
}

function fallbackRecentProjectName(project: ProjectSummary): string {
  const projectFile = String(project.project_file || "").trim();
  if (projectFile) {
    const normalized = projectFile.replace(/\\/g, "/");
    const fileName = normalized.split("/").pop() || "";
    return fileName.replace(/\.abproj$/i, "") || fileName;
  }
  const workspaceRoot = String(project.workspace_root || "").trim();
  if (!workspaceRoot) return "";
  const normalized = workspaceRoot.replace(/\\/g, "/");
  return normalized.split("/").pop() || normalized;
}

export function recentProjectDisplayName(project: ProjectSummary): string {
  const primary = sanitizeRecentProjectName(String(project.name || ""));
  return primary || fallbackRecentProjectName(project) || "AstraBridge Project";
}

export function recentProjectHoverDetail(project: ProjectSummary): string {
  return [project.workspace_root, project.project_file]
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .join("\n");
}

export function recentProjectTooltip(project: ProjectSummary): string {
  const displayName = recentProjectDisplayName(project);
  const hoverDetail = recentProjectHoverDetail(project);
  return hoverDetail ? `${displayName}\n${hoverDetail}` : displayName;
}

function compactPathTail(value: string, segmentCount = 2): string {
  const trimmed = String(value || "").trim();
  if (!trimmed) return "";
  const normalized = trimmed.replace(/\\/g, "/").replace(/\/+$/, "");
  const segments = normalized.split("/").filter(Boolean);
  if (segments.length === 0) return "";
  const tail = segments.slice(-Math.max(1, segmentCount));
  return tail.join("/");
}

export function recentProjectCompactLocation(project: ProjectSummary): string {
  const workspaceTail = compactPathTail(project.workspace_root || "", 2);
  if (workspaceTail) return workspaceTail;
  const projectFileTail = compactPathTail(project.project_file || "", 2);
  return projectFileTail;
}
