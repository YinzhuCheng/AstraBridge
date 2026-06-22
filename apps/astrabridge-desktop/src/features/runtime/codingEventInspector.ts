import type { ProjectFileTreeItem, ProjectReviewFile, ShellThread } from "../../types";

type CodingEventRecord = {
  event_type?: string;
  provider_id?: string | null;
  model_id?: string | null;
  payload?: Record<string, unknown>;
};

type CodingEventTurn = {
  provider_id?: string;
  model?: string;
  coding_events?: CodingEventRecord[];
};

export type CodingEventInspectorSummary = {
  reviewFiles: ProjectReviewFile[];
  recentFiles: ProjectFileTreeItem[];
  detailByPath: Record<string, string>;
  checkpointRefs: Array<{
    save_id: string;
    description: string;
    provider_id?: string;
    model_id?: string;
  }>;
  commandRefs: Array<{
    command: string;
    status?: string;
    exit_code?: number | null;
    provider_id?: string;
    model_id?: string;
  }>;
  diagnosticRefs: Array<{
    kind: string;
    summary: string;
    provider_id?: string;
    model_id?: string;
    to_thread_id?: string;
  }>;
};

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

function eventPayload(event: CodingEventRecord) {
  return event.payload && typeof event.payload === "object" ? event.payload : {};
}

export function summarizeCodingEventInspector(thread?: Pick<ShellThread, "turns"> | null): CodingEventInspectorSummary {
  const files = new Map<string, FileAccumulator>();
  const checkpoints = new Map<string, { save_id: string; description: string; provider_id?: string; model_id?: string }>();
  const commands = new Map<string, { command: string; status?: string; exit_code?: number | null; provider_id?: string; model_id?: string }>();
  const diagnostics = new Map<string, { kind: string; summary: string; provider_id?: string; model_id?: string; to_thread_id?: string }>();
  let order = 0;

  const rememberFile = (path: string, status: string, detailLine: string, kind = "event") => {
    const cleanPath = path.trim();
    if (!cleanPath) return;
    const current = files.get(cleanPath) ?? { status, detail: [], kind, order: order++ };
    current.status = current.status || status;
    current.kind = current.kind || kind;
    pushUnique(current.detail, detailLine);
    files.set(cleanPath, current);
  };

  const rememberCheckpoint = (saveId: string, description: string, providerId?: string, modelId?: string) => {
    const cleanId = saveId.trim();
    if (!cleanId) return;
    if (checkpoints.has(cleanId)) return;
    checkpoints.set(cleanId, {
      save_id: cleanId,
      description: description.trim() || cleanId,
      provider_id: providerId,
      model_id: modelId,
    });
  };

  const rememberCommand = (command: string, status?: string, exitCode?: number | null, providerId?: string, modelId?: string) => {
    const cleanCommand = command.trim();
    if (!cleanCommand) return;
    const key = `${cleanCommand}:${status ?? ""}:${exitCode ?? ""}`;
    if (commands.has(key)) return;
    commands.set(key, {
      command: cleanCommand,
      status: status?.trim() || undefined,
      exit_code: typeof exitCode === "number" ? exitCode : null,
      provider_id: providerId,
      model_id: modelId,
    });
  };

  const rememberDiagnostic = (kind: string, summary: string, providerId?: string, modelId?: string, toThreadId?: string) => {
    const cleanKind = kind.trim();
    const cleanSummary = summary.trim();
    if (!cleanKind || !cleanSummary) return;
    const key = `${cleanKind}:${cleanSummary}:${toThreadId ?? ""}`;
    if (diagnostics.has(key)) return;
    diagnostics.set(key, {
      kind: cleanKind,
      summary: cleanSummary,
      provider_id: providerId,
      model_id: modelId,
      to_thread_id: toThreadId?.trim() || undefined,
    });
  };

  for (const turn of (thread?.turns ?? []) as CodingEventTurn[]) {
    const providerId = String(turn.provider_id ?? "").trim() || undefined;
    const modelId = String(turn.model ?? "").trim() || undefined;
    for (const event of turn.coding_events ?? []) {
      const eventType = String(event.event_type ?? "").trim();
      const payload = eventPayload(event);
      if (eventType === "file_change") {
        const paths = Array.isArray(payload.paths) ? payload.paths : [];
        for (const rawPath of paths) {
          const path = String(rawPath ?? "").trim();
          if (!path) continue;
          rememberFile(path, "changed", "Changed during this task.", "text");
        }
      } else if (eventType === "edit_operation") {
        const path = String(payload.path ?? "").trim();
        if (path) {
          const changed = payload.changed === true ? "changed" : "reviewed";
          const applied = payload.applied === true ? "Applied edit." : "Previewed edit strategy.";
          rememberFile(path, changed, applied, "text");
          const reviewDiffPath = String(payload.review_diff_path ?? "").trim();
          if (reviewDiffPath) {
            rememberFile(path, changed, `Review diff artifact: ${reviewDiffPath}`, "text");
          }
        }
        const checkpointSaveId = String(payload.checkpoint_save_id ?? "").trim();
        if (checkpointSaveId) {
          rememberCheckpoint(
            checkpointSaveId,
            path ? `Checkpoint before editing ${path}` : checkpointSaveId,
            providerId,
            modelId,
          );
        }
      } else if (eventType === "file_read") {
        const path = String(payload.path ?? "").trim();
        if (path) {
          const kind = String(payload.kind ?? "").trim() || "text";
          rememberFile(path, "read", "Read during this task.", kind);
        }
      } else if (eventType === "verification_result") {
        const tool = String(payload.tool ?? "").trim() || "verification";
        const filePaths = [
          ...(Array.isArray(payload.files) ? payload.files : []),
          ...(Array.isArray(payload.paths) ? payload.paths : []),
        ]
          .map((value) => String(value ?? "").trim())
          .filter(Boolean);
        for (const path of filePaths) {
          rememberFile(path, "verified", `Referenced by ${tool}.`, "text");
        }
        const saveIds = Array.isArray(payload.save_ids) ? payload.save_ids : [];
        for (const rawSaveId of saveIds) {
          const saveId = String(rawSaveId ?? "").trim();
          if (!saveId) continue;
          rememberCheckpoint(saveId, `Checkpoint listed by ${tool}`, providerId, modelId);
        }
      } else if (eventType === "command_execution") {
        rememberCommand(
          String(payload.command ?? ""),
          String(payload.status ?? "").trim() || undefined,
          typeof payload.exit_code === "number" ? payload.exit_code : null,
          providerId,
          modelId,
        );
      } else if (eventType === "provider_handoff" || eventType === "runtime_transition") {
        const transition = String(payload.transition ?? "").trim();
        const toThreadId = String(payload.to_thread_id ?? "").trim() || undefined;
        const summary = eventType === "provider_handoff"
          ? `Handoff to ${String(payload.provider_id ?? providerId ?? "").trim() || "provider"} ${String(payload.model ?? modelId ?? "").trim()}`.trim()
          : transition
            ? `Runtime transition: ${transition}`
            : "Runtime transition";
        rememberDiagnostic(eventType, summary, providerId, modelId, toThreadId);
      } else if (eventType === "checkpoint_created") {
        const saveId = String(payload.save_id ?? "").trim();
        if (!saveId) continue;
        rememberCheckpoint(
          saveId,
          String(payload.description ?? "").trim() || `Checkpoint ${saveId}`,
          providerId,
          modelId,
        );
      }
    }
  }

  const sortedFiles = Array.from(files.entries()).sort((left, right) => left[1].order - right[1].order);
  return {
    reviewFiles: sortedFiles.map(([path, entry]) => ({ path, status: entry.status })),
    recentFiles: sortedFiles.map(([path, entry], index) => ({
      path,
      name: path.split(/[\\/]/).pop() ?? path,
      kind: entry.kind || "event",
      size: 0,
      updated_at: index,
    })),
    detailByPath: Object.fromEntries(sortedFiles.map(([path, entry]) => [path, entry.detail.join("\n")])),
    checkpointRefs: Array.from(checkpoints.values()),
    commandRefs: Array.from(commands.values()),
    diagnosticRefs: Array.from(diagnostics.values()),
  };
}
