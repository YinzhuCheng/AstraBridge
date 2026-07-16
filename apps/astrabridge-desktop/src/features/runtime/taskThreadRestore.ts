import type { ProjectFile, ProjectTask, ProjectTasksResponse, ShellThread } from "../../types";

function normalizeId(value: string | null | undefined) {
  const text = String(value ?? "").trim();
  return text || null;
}

function providerThreads(task: Pick<ProjectTask, "provider_threads"> | null | undefined) {
  return Array.isArray(task?.provider_threads) ? task.provider_threads : [];
}

export function resolveCurrentProjectTask(
  project: Pick<ProjectFile, "current_task_id">,
  projectTasks: Pick<ProjectTasksResponse, "current_task" | "tasks"> | null | undefined,
): ProjectTask | null {
  const currentTaskId = normalizeId(project.current_task_id);
  const currentTask = projectTasks?.current_task ?? null;
  if (!currentTaskId) return currentTask;

  if (normalizeId(currentTask?.task_id) === currentTaskId) return currentTask;

  const matchingTask = projectTasks?.tasks?.find((task) => normalizeId(task.task_id) === currentTaskId) ?? null;
  if (matchingTask) return matchingTask;
  return null;
}

export function resolveVisibleCurrentProjectTask({
  pendingSidebarTask,
  taskSelectionGuard,
  resolvedCurrentTask,
}: {
  pendingSidebarTask: ProjectTask | null;
  taskSelectionGuard: ProjectTask | null;
  resolvedCurrentTask: ProjectTask | null;
}) {
  const optimisticTask = pendingSidebarTask ?? taskSelectionGuard;
  if (!optimisticTask) {
    return resolvedCurrentTask;
  }
  if (!resolvedCurrentTask) {
    return optimisticTask;
  }
  if (normalizeId(optimisticTask.task_id) === normalizeId(resolvedCurrentTask.task_id)) {
    return resolvedCurrentTask;
  }
  return optimisticTask;
}

export function resolveSelectedThreadProfileId({
  currentTask,
  selectedThreadId,
  threadSettingsProfileId,
  selectedThreadSummary,
  projectDefaultProfileId,
  listProfileId,
}: {
  currentTask: ProjectTask | null;
  selectedThreadId: string | null;
  threadSettingsProfileId?: string | null;
  selectedThreadSummary?: Pick<ShellThread, "shellSettings"> | null;
  projectDefaultProfileId?: string | null;
  listProfileId?: string | null;
}) {
  const normalizedThreadId = normalizeId(selectedThreadId);
  const providerThreadProfileId =
    normalizedThreadId
      ? normalizeId(providerThreads(currentTask).find((thread) => normalizeId(thread.thread_id) === normalizedThreadId)?.profile_id)
      : null;
  const draftProfileId = normalizeId(threadSettingsProfileId);
  const summaryProfileId = normalizeId(selectedThreadSummary?.shellSettings?.profile_id);
  const defaultProfileId = normalizeId(projectDefaultProfileId) ?? normalizeId(listProfileId);
  if (providerThreadProfileId) return providerThreadProfileId;
  if (draftProfileId) return draftProfileId;
  if (summaryProfileId) return summaryProfileId;
  if (normalizedThreadId) return defaultProfileId;
  return normalizeId(listProfileId);
}

export function resolveTaskSendTargetThreadId({
  currentTask,
  selectedThreadId,
}: {
  currentTask: ProjectTask | null;
  selectedThreadId: string | null;
}) {
  const normalizedSelectedThreadId = normalizeId(selectedThreadId);
  if (!currentTask) return normalizedSelectedThreadId;

  const activeProviderThreadId = normalizeId(currentTask.active_provider_thread_id);
  if (activeProviderThreadId) return activeProviderThreadId;

  const currentTaskProviderThreadIds = new Set(
    providerThreads(currentTask)
      .map((thread) => normalizeId(thread.thread_id))
      .filter((value): value is string => Boolean(value)),
  );
  if (normalizedSelectedThreadId && currentTaskProviderThreadIds.has(normalizedSelectedThreadId)) {
    return normalizedSelectedThreadId;
  }
  return null;
}

/**
 * New provider lanes belong to the task represented by the rendered
 * conversation, not a potentially stale project-level task pointer.
 */
export function resolveTaskIdForNewThread({
  selectedTaskId,
  conversationTaskId,
  currentTask,
}: {
  selectedTaskId?: string | null;
  conversationTaskId?: string | null;
  currentTask: Pick<ProjectTask, "task_id"> | null | undefined;
}) {
  return normalizeId(selectedTaskId) ?? normalizeId(conversationTaskId) ?? normalizeId(currentTask?.task_id) ?? undefined;
}

export function shouldUseSelectedRuntimeThread({
  currentTask,
  selectedThreadId,
}: {
  currentTask: ProjectTask | null;
  selectedThreadId: string | null;
}) {
  const normalizedSelectedThreadId = normalizeId(selectedThreadId);
  if (!normalizedSelectedThreadId) return false;
  if (!currentTask) return true;

  const activeProviderThreadId = normalizeId(currentTask.active_provider_thread_id);
  if (activeProviderThreadId) return activeProviderThreadId === normalizedSelectedThreadId;

  return providerThreads(currentTask).some((thread) => normalizeId(thread.thread_id) === normalizedSelectedThreadId);
}

export function fallbackThreadIdForEmptyTaskContext({
  currentTask,
  selectedThreadId,
  threads,
}: {
  currentTask: ProjectTask | null;
  selectedThreadId: string | null;
  threads: Array<Pick<ShellThread, "id">> | null | undefined;
}) {
  if (normalizeId(selectedThreadId)) return null;
  if (currentTask) return null;
  return normalizeId(threads?.[0]?.id);
}
