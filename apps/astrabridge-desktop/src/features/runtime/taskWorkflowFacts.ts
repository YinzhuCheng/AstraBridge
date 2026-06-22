import type { ProjectTask, ShellThread } from "../../types";
import type { CodingEventInspectorSummary } from "./codingEventInspector";

export type TaskWorkflowFacts = {
  laneCount: number;
  handoffCount: number;
  checkpointCount: number;
  commandCount: number;
  diagnosticCount: number;
  failedCommandCount: number;
  recoveredCommandCount: number;
  backend: "app_server" | "native_kernel";
};

export function summarizeTaskWorkflowFacts(
  task: ProjectTask | null | undefined,
  executionThread: Pick<ShellThread, "shellSettings"> | null | undefined,
  eventSummary?: Pick<CodingEventInspectorSummary, "checkpointRefs" | "commandRefs" | "diagnosticRefs"> | null,
): TaskWorkflowFacts {
  const handoffCountFromTask = task?.handoff_events?.length ?? 0;
  const handoffCountFromEvents = (eventSummary?.diagnosticRefs ?? []).filter((item) => item.kind === "provider_handoff").length;
  const commandRefs = eventSummary?.commandRefs ?? [];
  const failedCommands = new Set<string>();
  const recoveredCommands = new Set<string>();
  for (const item of commandRefs) {
    const command = String(item.command ?? "").trim();
    const status = String(item.status ?? "").trim().toLowerCase();
    if (!command) continue;
    if (status === "failed") {
      failedCommands.add(command);
      continue;
    }
    if ((status === "completed" || status === "ok") && failedCommands.has(command)) {
      recoveredCommands.add(command);
    }
  }
  return {
    laneCount: task?.provider_threads?.length ?? 0,
    handoffCount: Math.max(handoffCountFromTask, handoffCountFromEvents),
    checkpointCount: Math.max(task?.checkpoint_refs?.length ?? 0, eventSummary?.checkpointRefs?.length ?? 0),
    commandCount: commandRefs.length,
    diagnosticCount: eventSummary?.diagnosticRefs?.length ?? 0,
    failedCommandCount: failedCommands.size,
    recoveredCommandCount: recoveredCommands.size,
    backend: executionThread?.shellSettings?.execution_backend === "native_kernel" ? "native_kernel" : "app_server",
  };
}
