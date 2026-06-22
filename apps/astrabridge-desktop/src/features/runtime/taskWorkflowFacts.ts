import type { ProjectTask, ShellThread } from "../../types";
import type { CodingEventInspectorSummary } from "./codingEventInspector";

export type TaskWorkflowFacts = {
  laneCount: number;
  handoffCount: number;
  checkpointCount: number;
  commandCount: number;
  diagnosticCount: number;
  backend: "app_server" | "native_kernel";
};

export function summarizeTaskWorkflowFacts(
  task: ProjectTask | null | undefined,
  executionThread: Pick<ShellThread, "shellSettings"> | null | undefined,
  eventSummary?: Pick<CodingEventInspectorSummary, "checkpointRefs" | "commandRefs" | "diagnosticRefs"> | null,
): TaskWorkflowFacts {
  const handoffCountFromTask = task?.handoff_events?.length ?? 0;
  const handoffCountFromEvents = (eventSummary?.diagnosticRefs ?? []).filter((item) => item.kind === "provider_handoff").length;
  return {
    laneCount: task?.provider_threads?.length ?? 0,
    handoffCount: Math.max(handoffCountFromTask, handoffCountFromEvents),
    checkpointCount: Math.max(task?.checkpoint_refs?.length ?? 0, eventSummary?.checkpointRefs?.length ?? 0),
    commandCount: eventSummary?.commandRefs?.length ?? 0,
    diagnosticCount: eventSummary?.diagnosticRefs?.length ?? 0,
    backend: executionThread?.shellSettings?.execution_backend === "native_kernel" ? "native_kernel" : "app_server",
  };
}
