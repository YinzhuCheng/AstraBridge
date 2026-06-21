import type { ProjectTask, ProjectTaskProviderThread } from "../../types";

export type TaskSummary = {
  subtitle: string;
  routeModel: string;
  routeEffort: string;
  stats: string[];
  tone: "default" | "warning";
};

function activeThreadForTask(task: ProjectTask): ProjectTaskProviderThread | undefined {
  return task.provider_threads.find((item) => item.thread_id === task.active_provider_thread_id) ?? task.provider_threads[0];
}

export function summarizeTaskCard(task: ProjectTask): TaskSummary {
  const activeThread = activeThreadForTask(task);
  const latestHandoff = task.handoff_events[task.handoff_events.length - 1];
  const forkCount = task.fork_threads?.length ?? 0;
  const checkpointCount = task.checkpoint_refs?.length ?? 0;
  const missingCount = task.provider_threads.filter((item) => Boolean((item as { missing_at?: string }).missing_at)).length;

  const subtitle = latestHandoff
    ? `已切换到 ${latestHandoff.profile_id ?? latestHandoff.provider_id ?? "默认通道"}${latestHandoff.model ? ` · ${latestHandoff.model}` : ""}`
    : `${task.provider_threads.length || 0} 条执行线程`;

  const stats: string[] = [];
  if (forkCount > 0) stats.push(`${forkCount} 个分支`);
  if (checkpointCount > 0) stats.push(`${checkpointCount} 个检查点`);
  if (missingCount > 0) stats.push(`${missingCount} 条异常线程`);

  return {
    subtitle,
    routeModel: activeThread?.model ?? "-",
    routeEffort: activeThread?.reasoning_effort ?? "-",
    stats,
    tone: missingCount > 0 ? "warning" : "default",
  };
}
