import { ChevronDown, ChevronRight } from "lucide-react";
import { useState, type ReactNode } from "react";
import { StarbridgeProjectIcon, StarbridgeTaskIcon } from "../brand/StarbridgeIcons";
import type { LocaleCode, SidebarProjectNode, SidebarTaskNode } from "../../types";

export function sidebarProjectKey(project: Pick<SidebarProjectNode, "project_file" | "project_id">) {
  return project.project_file || project.project_id;
}

export function sidebarTaskKey(project: Pick<SidebarProjectNode, "project_file" | "project_id">, task: Pick<SidebarTaskNode, "task_id">) {
  return `${sidebarProjectKey(project)}:${task.task_id}`;
}

export type ProjectTaskTreeProps = {
  locale: LocaleCode;
  projects: SidebarProjectNode[];
  expandedProjects: Set<string>;
  formatTime: (value: string | number | null | undefined) => string;
  onToggleProject: (projectKey: string) => void;
  onSelectProject: (project: SidebarProjectNode) => void;
  onSelectTask: (project: SidebarProjectNode, task: SidebarTaskNode) => void;
  busy?: boolean;
};

export function ProjectTaskTree({
  locale,
  projects,
  expandedProjects,
  formatTime,
  onToggleProject,
  onSelectProject,
  onSelectTask,
  busy = false,
}: ProjectTaskTreeProps) {
  const labels = treeLabels(locale);
  if (projects.length === 0) {
    return <p className="muted project-tree-empty">{labels.empty}</p>;
  }
  return (
    <div className="project-task-tree" role="tree" aria-label={labels.tree}>
      {projects.map((project) => {
        const projectKey = sidebarProjectKey(project);
        const projectExpanded = expandedProjects.has(projectKey);
        const hasCurrentTask = project.tasks.some((task) => task.is_current);
        return (
          <div className="project-tree-group" role="none" key={projectKey}>
            <TreeItem
              level="project"
              title={project.name}
              timeLabel={formatTime(project.updated_at)}
              expanded={projectExpanded}
              expandable={project.tasks.length > 0}
              active={project.is_current && !hasCurrentTask}
              busy={busy}
              icon={<StarbridgeProjectIcon size={15} strokeWidth={1.9} />}
              labels={{ expand: labels.expandProject, collapse: labels.collapseProject, untitled: labels.untitled }}
              onToggle={() => onToggleProject(projectKey)}
              onSelect={() => onSelectProject(project)}
              hover={<SidebarInfoHoverCard locale={locale} kind="project" project={project} />}
            />
            {projectExpanded ? (
              <div className="project-tree-children" role="group">
                {project.tasks.map((task) => {
                  const taskKey = sidebarTaskKey(project, task);
                  return (
                    <div className="project-tree-group" role="none" key={taskKey}>
                      <TreeItem
                        level="task"
                        title={task.title}
                        timeLabel={formatTime(task.updated_at)}
                        expandable={false}
                        active={task.is_current}
                        busy={busy}
                        icon={<StarbridgeTaskIcon size={14} strokeWidth={1.9} />}
                        labels={{ expand: labels.expandTask, collapse: labels.collapseTask, untitled: labels.untitled }}
                        onToggle={() => undefined}
                        onSelect={() => onSelectTask(project, task)}
                        hover={<SidebarInfoHoverCard locale={locale} kind="task" project={project} task={task} />}
                      />
                    </div>
                  );
                })}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function TreeItem({
  level,
  title,
  timeLabel,
  expanded,
  expandable,
  active,
  busy,
  icon,
  labels,
  onToggle,
  onSelect,
  hover,
}: {
  level: "project" | "task";
  title: string;
  timeLabel: string;
  expanded?: boolean;
  expandable: boolean;
  active: boolean;
  busy: boolean;
  icon: ReactNode;
  labels: { expand: string; collapse: string; untitled: string };
  onToggle: () => void;
  onSelect: () => void;
  hover: ReactNode;
}) {
  const toggleLabel = expanded ? labels.collapse : labels.expand;
  const [previewOpen, setPreviewOpen] = useState(false);
  const itemClass = `project-tree-item project-tree-${level} ${active ? "project-tree-item-active" : ""} ${previewOpen ? "project-tree-item-preview" : ""}`;
  return (
    <div
      className={itemClass}
      role="treeitem"
      aria-expanded={expandable ? Boolean(expanded) : undefined}
      onMouseEnter={() => setPreviewOpen(true)}
      onMouseLeave={() => setPreviewOpen(false)}
      onFocusCapture={() => setPreviewOpen(true)}
      onBlurCapture={() => setPreviewOpen(false)}
    >
      {expandable ? (
        <button
          type="button"
          className="project-tree-expander"
          onClick={() => {
            setPreviewOpen(true);
            onToggle();
          }}
          title={toggleLabel}
          aria-label={toggleLabel}
          disabled={busy}
        >
          {expanded ? <ChevronDown size={13} strokeWidth={1.8} aria-hidden="true" /> : <ChevronRight size={13} strokeWidth={1.8} aria-hidden="true" />}
        </button>
      ) : (
        <span className="project-tree-expander project-tree-expander-placeholder" aria-hidden="true" />
      )}
      <button
        type="button"
        className="project-tree-row"
        onClick={() => {
          setPreviewOpen(true);
          onSelect();
        }}
        disabled={busy}
      >
        <span className="project-tree-icon" aria-hidden="true">{icon}</span>
        <strong>{title || labels.untitled}</strong>
        <time>{timeLabel}</time>
      </button>
      {hover}
    </div>
  );
}

function SidebarInfoHoverCard({
  locale,
  kind,
  project,
  task,
}: {
  locale: LocaleCode;
  kind: "project" | "task";
  project: SidebarProjectNode;
  task?: SidebarTaskNode;
}) {
  const labels = treeLabels(locale);
  const laneCount = task ? task.lane_count ?? task.thread_count ?? task.threads.length : 0;
  const activeLane = task
    ? task.active_lane_label || [task.provider_id, task.model, task.reasoning_effort].filter(Boolean).join(" / ") || "-"
    : "-";
  const rows: Array<[string, string]> =
    kind === "project"
      ? [
          [labels.workspace, project.workspace_root],
          [labels.projectFile, project.project_file],
          [labels.tasks, String(project.tasks.length)],
          [labels.updated, project.updated_at],
          ...(project.warnings?.length ? [[labels.warnings, project.warnings.join("; ")] as [string, string]] : []),
        ]
      : task
        ? [
            [labels.project, project.name],
            [labels.status, task.status || "-"],
            [labels.activeLane, activeLane],
            [labels.lanes, String(laneCount)],
            [labels.handoffs, String(task.handoff_count ?? 0)],
            [labels.checkpoints, String(task.checkpoint_count ?? 0)],
            [labels.missingLanes, String(task.missing_thread_count ?? 0)],
            ...(task.latest_lane_status ? [[labels.latestLaneStatus, task.latest_lane_status] as [string, string]] : []),
          ]
        : [];
  return (
    <aside className="sidebar-info-hover-card" role="tooltip">
      <strong>{kind === "project" ? project.name : task?.title}</strong>
      <dl>
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd title={value}>{value || "-"}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}

function treeLabels(locale: LocaleCode) {
  if (locale === "zh-CN") {
    return {
      tree: "项目与任务",
      empty: "还没有项目或任务。",
      expandProject: "展开项目",
      collapseProject: "收起项目",
      expandTask: "展开任务",
      collapseTask: "收起任务",
      workspace: "工作区",
      projectFile: "项目文件",
      project: "项目",
      task: "任务",
      tasks: "任务数",
      lanes: "执行线路",
      activeLane: "活动线路",
      latestLaneStatus: "线路状态",
      status: "状态",
      handoffs: "切换",
      checkpoints: "保存点",
      missingLanes: "异常线路",
      updated: "更新时间",
      warnings: "提示",
      untitled: "未命名",
    };
  }
  return {
    tree: "Projects and tasks",
    empty: "No projects or tasks yet.",
    expandProject: "Expand project",
    collapseProject: "Collapse project",
    expandTask: "Expand task",
    collapseTask: "Collapse task",
    workspace: "Workspace",
    projectFile: "Project file",
    project: "Project",
    task: "Task",
    tasks: "Tasks",
    lanes: "Execution lanes",
    activeLane: "Active lane",
    latestLaneStatus: "Lane status",
    status: "Status",
    handoffs: "Handoffs",
    checkpoints: "Checkpoints",
    missingLanes: "Missing lanes",
    updated: "Updated",
    warnings: "Warnings",
    untitled: "Untitled",
  };
}
