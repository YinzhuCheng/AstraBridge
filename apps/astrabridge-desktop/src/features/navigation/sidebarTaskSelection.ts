import type { ProjectFile, ProjectTask, SidebarProjectNode, SidebarTaskNode } from "../../types";

type CurrentProjectLike = Pick<ProjectFile, "project_file" | "project_id"> | null | undefined;
type CurrentTaskLike = Pick<ProjectTask, "task_id"> | null | undefined;
type SidebarProjectLike = Pick<SidebarProjectNode, "is_current" | "project_file" | "project_id">;
type SidebarTaskLike = Pick<SidebarTaskNode, "task_id">;

function normalizedKey(value: string | null | undefined) {
  return String(value || "").trim();
}

export function isSidebarTaskAlreadySelected(args: {
  currentProject: CurrentProjectLike;
  currentTask: CurrentTaskLike;
  projectNode: SidebarProjectLike;
  taskNode: SidebarTaskLike;
}) {
  const { currentProject, currentTask, projectNode, taskNode } = args;
  if (!currentTask?.task_id || currentTask.task_id !== taskNode.task_id) return false;
  if (projectNode.is_current) return true;
  const currentProjectFile = normalizedKey(currentProject?.project_file);
  const currentProjectId = normalizedKey(currentProject?.project_id);
  const projectNodeFile = normalizedKey(projectNode.project_file);
  const projectNodeId = normalizedKey(projectNode.project_id);
  if (currentProjectFile && projectNodeFile) return currentProjectFile === projectNodeFile;
  if (currentProjectId && projectNodeId) return currentProjectId === projectNodeId;
  return false;
}
