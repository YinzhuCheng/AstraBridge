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
  };
}
