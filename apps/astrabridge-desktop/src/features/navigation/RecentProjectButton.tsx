import type { ProjectSummary } from "../../types";
import { recentProjectDisplayName, recentProjectTooltip } from "./recentProjectCards";

type RecentProjectButtonProps = {
  project: ProjectSummary;
  relativeTimeLabel: string;
  onOpen: (projectFile: string) => void;
  disabled?: boolean;
};

function visibleRecentProjectTitle(project: ProjectSummary): string {
  return recentProjectDisplayName(project)
    .split(/\r?\n/, 1)[0]
    ?.trim() || "AstraBridge Project";
}

export function RecentProjectButton({ project, relativeTimeLabel, onOpen, disabled = false }: RecentProjectButtonProps) {
  const displayName = visibleRecentProjectTitle(project);
  const tooltip = recentProjectTooltip(project);

  return (
    <button
      type="button"
      className="recent-project"
      title={tooltip}
      aria-label={displayName}
      disabled={disabled}
      onClick={() => onOpen(project.project_file)}
    >
      <span className="recent-project-head">
        <strong className="recent-project-title">{displayName}</strong>
        <time>{relativeTimeLabel}</time>
      </span>
    </button>
  );
}
