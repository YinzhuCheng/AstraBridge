import type { ProjectFileTreeItem, ProjectReviewFile, ProjectTask, ShellThread } from "../../types";
import { summarizeCodingEventInspector, type CodingEventInspectorSummary } from "./codingEventInspector";

type FileAccumulator = {
  status: string;
  detail: string[];
  kind: string;
  order: number;
};

function pushUnique(lines: string[], value: string) {
  const text = value.trim();
  if (!text || lines.includes(text)) return;
  lines.push(text);
}

function nonEmptyText(value: unknown): string | undefined {
  const text = String(value ?? "").trim();
  return text || undefined;
}

function rememberFile(
  files: Map<string, FileAccumulator>,
  orderRef: { current: number },
  path: string,
  status: string,
  detailLine: string,
  kind = "text",
) {
  const cleanPath = path.trim();
  if (!cleanPath) return;
  const current = files.get(cleanPath) ?? { status, detail: [], kind, order: orderRef.current++ };
  current.status = current.status || status;
  current.kind = current.kind || kind;
  pushUnique(current.detail, detailLine);
  files.set(cleanPath, current);
}

function checkpointDescription(ref: Record<string, unknown>): string {
  return nonEmptyText(ref.description) ?? nonEmptyText(ref.save_id) ?? "checkpoint";
}

function buildBaseFileMaps(base: CodingEventInspectorSummary) {
  const files = new Map<string, FileAccumulator>();
  const orderRef = { current: 0 };
  for (const file of base.recentFiles) {
    const path = String(file.path ?? "").trim();
    if (!path) continue;
    files.set(path, {
      status: base.reviewFiles.find((item) => item.path === path)?.status ?? "event",
      detail: base.detailByPath[path] ? [base.detailByPath[path]] : [],
      kind: file.kind || "text",
      order: orderRef.current++,
    });
  }
  return { files, orderRef };
}

function mergeVerificationRefs(
  files: Map<string, FileAccumulator>,
  orderRef: { current: number },
  checkpoints: Map<string, CodingEventInspectorSummary["checkpointRefs"][number]>,
  task: ProjectTask | null | undefined,
) {
  for (const item of task?.verification_refs ?? []) {
    if (!item || typeof item !== "object") continue;
    const record = item as Record<string, unknown>;
    const kind = nonEmptyText(record.kind) ?? "verification";
    const tool = nonEmptyText(record.tool) ?? kind;
    const path = nonEmptyText(record.path);
    const status = kind === "edit_operation" ? "changed" : kind === "file_read" ? "read" : "verified";
    const detail = kind === "edit_operation"
      ? "Persisted task edit evidence."
      : kind === "file_read"
        ? "Persisted task file-read evidence."
        : `Persisted task evidence from ${tool}.`;
    if (path) {
      rememberFile(files, orderRef, path, status, detail, "text");
    }
    for (const rawPath of [...(Array.isArray(record.files) ? record.files : []), ...(Array.isArray(record.paths) ? record.paths : [])]) {
      const nextPath = nonEmptyText(rawPath);
      if (!nextPath) continue;
      rememberFile(files, orderRef, nextPath, "verified", `Persisted task evidence from ${tool}.`, "text");
    }
    const reviewDiffPath = nonEmptyText(record.review_diff_path);
    if (path && reviewDiffPath) {
      rememberFile(files, orderRef, path, status, `Review diff artifact: ${reviewDiffPath}`, "text");
    }
    const checkpointSaveId = nonEmptyText(record.checkpoint_save_id);
    if (checkpointSaveId && !checkpoints.has(checkpointSaveId)) {
      checkpoints.set(checkpointSaveId, {
        save_id: checkpointSaveId,
        description: `Checkpoint referenced by ${tool}`,
        provider_id: nonEmptyText(record.provider_id),
        model_id: nonEmptyText(record.model),
      });
    }
    for (const rawSaveId of Array.isArray(record.save_ids) ? record.save_ids : []) {
      const saveId = nonEmptyText(rawSaveId);
      if (!saveId || checkpoints.has(saveId)) continue;
      checkpoints.set(saveId, {
        save_id: saveId,
        description: `Checkpoint listed by ${tool}`,
        provider_id: nonEmptyText(record.provider_id),
        model_id: nonEmptyText(record.model),
      });
    }
  }
}

function mergeTaskCheckpointRefs(
  checkpoints: Map<string, CodingEventInspectorSummary["checkpointRefs"][number]>,
  task: ProjectTask | null | undefined,
) {
  for (const item of task?.checkpoint_refs ?? []) {
    if (!item || typeof item !== "object") continue;
    const record = item as Record<string, unknown>;
    const saveId = nonEmptyText(record.save_id);
    if (!saveId || checkpoints.has(saveId)) continue;
    checkpoints.set(saveId, {
      save_id: saveId,
      description: checkpointDescription(record),
      provider_id: nonEmptyText(record.provider_id),
      model_id: nonEmptyText(record.model ?? record.model_id),
    });
  }
}

function mergeTaskCommandAndDiagnostics(
  commands: Map<string, CodingEventInspectorSummary["commandRefs"][number]>,
  diagnostics: Map<string, CodingEventInspectorSummary["diagnosticRefs"][number]>,
  task: ProjectTask | null | undefined,
) {
  for (const item of task?.diagnostic_refs ?? []) {
    if (!item || typeof item !== "object") continue;
    const record = item as Record<string, unknown>;
    const kind = nonEmptyText(record.kind);
    const providerId = nonEmptyText(record.provider_id);
    const modelId = nonEmptyText(record.model ?? record.model_id);
    if (kind === "command_execution") {
      const command = nonEmptyText(record.command);
      if (command) {
        const status = nonEmptyText(record.status);
        const exitCode = typeof record.exit_code === "number" ? record.exit_code : null;
        const key = `${command}:${status ?? ""}:${exitCode ?? ""}`;
        if (!commands.has(key)) {
          commands.set(key, {
            command,
            status,
            exit_code: exitCode,
            provider_id: providerId,
            model_id: modelId,
          });
        }
      }
    }
    const summary = kind === "provider_handoff"
      ? [`Handoff to ${nonEmptyText(record.provider_id) ?? "provider"}`, nonEmptyText(record.model)].filter(Boolean).join(" ")
      : kind === "runtime_transition"
        ? (nonEmptyText(record.transition) ? `Runtime transition: ${nonEmptyText(record.transition)}` : "Runtime transition")
        : kind === "command_execution"
          ? [nonEmptyText(record.command), nonEmptyText(record.status) ? `(${nonEmptyText(record.status)})` : ""].filter(Boolean).join(" ")
          : nonEmptyText(record.tool) ?? nonEmptyText(record.command) ?? nonEmptyText(record.transition);
    if (!kind || !summary) continue;
    const toThreadId = nonEmptyText(record.to_thread_id);
    const key = `${kind}:${summary}:${toThreadId ?? ""}`;
    if (!diagnostics.has(key)) {
      diagnostics.set(key, {
        kind,
        summary,
        provider_id: providerId,
        model_id: modelId,
        to_thread_id: toThreadId,
      });
    }
  }
}

function toSummary(
  files: Map<string, FileAccumulator>,
  checkpoints: Map<string, CodingEventInspectorSummary["checkpointRefs"][number]>,
  commands: Map<string, CodingEventInspectorSummary["commandRefs"][number]>,
  diagnostics: Map<string, CodingEventInspectorSummary["diagnosticRefs"][number]>,
): CodingEventInspectorSummary {
  const sortedFiles = Array.from(files.entries()).sort((left, right) => left[1].order - right[1].order);
  return {
    reviewFiles: sortedFiles.map(([path, entry]): ProjectReviewFile => ({ path, status: entry.status })),
    recentFiles: sortedFiles.map(([path, entry], index): ProjectFileTreeItem => ({
      path,
      name: path.split(/[\\/]/).pop() ?? path,
      kind: entry.kind || "text",
      size: 0,
      updated_at: index,
    })),
    detailByPath: Object.fromEntries(sortedFiles.map(([path, entry]) => [path, entry.detail.join("\n")])),
    checkpointRefs: Array.from(checkpoints.values()),
    commandRefs: Array.from(commands.values()),
    diagnosticRefs: Array.from(diagnostics.values()),
  };
}

export function summarizeTaskInspectorEvidence(
  task: ProjectTask | null | undefined,
  thread?: Pick<ShellThread, "turns"> | null,
): CodingEventInspectorSummary {
  const base = summarizeCodingEventInspector(thread);
  const { files, orderRef } = buildBaseFileMaps(base);
  const checkpoints = new Map(base.checkpointRefs.map((item) => [item.save_id, item] as const));
  const commands = new Map(
    base.commandRefs.map((item) => [`${item.command}:${item.status ?? ""}:${item.exit_code ?? ""}`, item] as const),
  );
  const diagnostics = new Map(
    base.diagnosticRefs.map((item) => [`${item.kind}:${item.summary}:${item.to_thread_id ?? ""}`, item] as const),
  );

  mergeVerificationRefs(files, orderRef, checkpoints, task);
  mergeTaskCheckpointRefs(checkpoints, task);
  mergeTaskCommandAndDiagnostics(commands, diagnostics, task);

  return toSummary(files, checkpoints, commands, diagnostics);
}
