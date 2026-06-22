import type { ProjectTask, ShellThread } from "../../types";

export type TaskWorkflowFacts = {
  laneCount: number;
  handoffCount: number;
  checkpointCount: number;
  backend: "app_server" | "native_kernel";
};

export function summarizeTaskWorkflowFacts(
  task: ProjectTask | null | undefined,
  executionThread: Pick<ShellThread, "shellSettings"> | null | undefined,
): TaskWorkflowFacts {
  return {
    laneCount: task?.provider_threads?.length ?? 0,
    handoffCount: task?.handoff_events?.length ?? 0,
    checkpointCount: task?.checkpoint_refs?.length ?? 0,
    backend: executionThread?.shellSettings?.execution_backend === "native_kernel" ? "native_kernel" : "app_server",
  };
}

