import type { ProjectTask, ShellThread } from "../../types";
import type { CodingEventInspectorSummary } from "./codingEventInspector";

export type TaskWorkflowRef = {
  key: string;
  kind?: string;
  summary: string;
  provider_id?: string;
  model_id?: string;
  to_thread_id?: string;
};

export type TaskWorkflowCheckpointRef = {
  save_id: string;
  description: string;
  provider_id?: string;
  model_id?: string;
};

export type TaskWorkflowFacts = {
  laneCount: number;
  handoffCount: number;
  checkpointCount: number;
  commandCount: number;
  diagnosticCount: number;
  failedCommandCount: number;
  recoveredCommandCount: number;
  backend: "app_server" | "native_kernel";
  checkpointRefs: TaskWorkflowCheckpointRef[];
  diagnosticRefs: TaskWorkflowRef[];
};

function nonEmptyText(value: unknown): string | undefined {
  const text = String(value ?? "").trim();
  return text || undefined;
}

function summarizeTaskDiagnosticRef(item: Record<string, unknown>): string | undefined {
  const kind = nonEmptyText(item.kind);
  if (kind === "provider_handoff") {
    const provider = nonEmptyText(item.provider_id) ?? "provider";
    const model = nonEmptyText(item.model);
    return [`Handoff to ${provider}`, model].filter(Boolean).join(" ");
  }
  if (kind === "runtime_transition") {
    const transition = nonEmptyText(item.transition);
    return transition ? `Runtime transition: ${transition}` : "Runtime transition";
  }
  if (kind === "command_execution") {
    const command = nonEmptyText(item.command);
    const status = nonEmptyText(item.status);
    if (!command) return undefined;
    return status ? `${command} (${status})` : command;
  }
  const tool = nonEmptyText(item.tool);
  const command = nonEmptyText(item.command);
  const transition = nonEmptyText(item.transition);
  return tool ?? command ?? transition;
}

function taskCheckpointRefs(task: ProjectTask | null | undefined): TaskWorkflowCheckpointRef[] {
  const seen = new Set<string>();
  const refs: TaskWorkflowCheckpointRef[] = [];
  for (const item of task?.checkpoint_refs ?? []) {
    if (!item || typeof item !== "object") continue;
    const saveId = nonEmptyText((item as Record<string, unknown>).save_id);
    if (!saveId || seen.has(saveId)) continue;
    seen.add(saveId);
    refs.push({
      save_id: saveId,
      description: nonEmptyText((item as Record<string, unknown>).description) ?? saveId,
      provider_id: nonEmptyText((item as Record<string, unknown>).provider_id),
      model_id: nonEmptyText((item as Record<string, unknown>).model ?? (item as Record<string, unknown>).model_id),
    });
  }
  return refs;
}

function taskDiagnosticRefs(task: ProjectTask | null | undefined): TaskWorkflowRef[] {
  const seen = new Set<string>();
  const refs: TaskWorkflowRef[] = [];
  for (const item of task?.diagnostic_refs ?? []) {
    if (!item || typeof item !== "object") continue;
    const record = item as Record<string, unknown>;
    const kind = nonEmptyText(record.kind);
    const summary = summarizeTaskDiagnosticRef(record);
    if (!kind || !summary) continue;
    const toThreadId = nonEmptyText(record.to_thread_id);
    const key = [kind, summary, toThreadId ?? ""].join(":");
    if (seen.has(key)) continue;
    seen.add(key);
    refs.push({
      key,
      kind,
      summary,
      provider_id: nonEmptyText(record.provider_id),
      model_id: nonEmptyText(record.model ?? record.model_id),
      to_thread_id: toThreadId,
    });
  }
  return refs;
}

function mergedCheckpointRefs(
  task: ProjectTask | null | undefined,
  eventSummary?: Pick<CodingEventInspectorSummary, "checkpointRefs"> | null,
): TaskWorkflowCheckpointRef[] {
  const merged = new Map<string, TaskWorkflowCheckpointRef>();
  for (const item of taskCheckpointRefs(task)) {
    merged.set(item.save_id, item);
  }
  for (const item of eventSummary?.checkpointRefs ?? []) {
    const saveId = nonEmptyText(item.save_id);
    if (!saveId) continue;
    merged.set(saveId, {
      save_id: saveId,
      description: nonEmptyText(item.description) ?? saveId,
      provider_id: nonEmptyText(item.provider_id),
      model_id: nonEmptyText(item.model_id),
    });
  }
  return Array.from(merged.values());
}

function mergedDiagnosticRefs(
  task: ProjectTask | null | undefined,
  eventSummary?: Pick<CodingEventInspectorSummary, "diagnosticRefs"> | null,
): TaskWorkflowRef[] {
  const merged = new Map<string, TaskWorkflowRef>();
  for (const item of taskDiagnosticRefs(task)) {
    merged.set(item.key, item);
  }
  for (const item of eventSummary?.diagnosticRefs ?? []) {
    const kind = nonEmptyText(item.kind);
    const summary = nonEmptyText(item.summary);
    if (!kind || !summary) continue;
    const toThreadId = nonEmptyText(item.to_thread_id);
    const key = [kind, summary, toThreadId ?? ""].join(":");
    merged.set(key, {
      key,
      kind,
      summary,
      provider_id: nonEmptyText(item.provider_id),
      model_id: nonEmptyText(item.model_id),
      to_thread_id: toThreadId,
    });
  }
  return Array.from(merged.values());
}

export function summarizeTaskWorkflowFacts(
  task: ProjectTask | null | undefined,
  executionThread: Pick<ShellThread, "shellSettings"> | null | undefined,
  eventSummary?: Pick<CodingEventInspectorSummary, "checkpointRefs" | "commandRefs" | "diagnosticRefs"> | null,
): TaskWorkflowFacts {
  const checkpointRefs = mergedCheckpointRefs(task, eventSummary);
  const diagnosticRefs = mergedDiagnosticRefs(task, eventSummary);
  const handoffCountFromTask = task?.handoff_events?.length ?? 0;
  const handoffCountFromDiagnostics = diagnosticRefs.filter((item) => item.kind === "provider_handoff").length;
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
    handoffCount: Math.max(handoffCountFromTask, handoffCountFromDiagnostics),
    checkpointCount: checkpointRefs.length,
    commandCount: commandRefs.length,
    diagnosticCount: diagnosticRefs.length,
    failedCommandCount: failedCommands.size,
    recoveredCommandCount: recoveredCommands.size,
    backend: executionThread?.shellSettings?.execution_backend === "native_kernel" ? "native_kernel" : "app_server",
    checkpointRefs,
    diagnosticRefs,
  };
}
