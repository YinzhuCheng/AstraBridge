import type { RuntimeActivityState, RuntimeDiffSummary, ThreadMessageSource, ThreadRenderBlock } from "../../types";

type VerifiedEvidence = {
  tool?: string;
  server?: string;
  status?: string;
  verified?: boolean;
  label?: string;
  summary?: string[];
  paths?: string[];
  urls?: string[];
};

type CompletionQuality = {
  status?: string;
  reason?: string;
  tool_item_count?: number;
  agent_message_count?: number;
  max_agent_chars?: number;
  final_preview?: string;
  recommended_action?: string;
};

type DecoratedThreadItem = ThreadMessageSource & {
  verifiedEvidence?: VerifiedEvidence;
};

type DecoratedTurn = {
  id?: string;
  startedAt?: number | null;
  completedAt?: number | null;
  durationMs?: number | null;
  source_thread_id?: string;
  sourceThreadId?: string;
  profile_id?: string;
  profileId?: string;
  provider_id?: string;
  providerId?: string;
  model?: string;
  reasoning_effort?: string;
  reasoningEffort?: string;
  items?: ThreadMessageSource[];
  completionQuality?: CompletionQuality;
  coding_events?: DecoratedCodingEvent[];
};

type DecoratedCodingEvent = {
  event_id?: string;
  event_type?: string;
  task_id?: string;
  visible_thread_id?: string;
  execution_thread_id?: string | null;
  provider_id?: string | null;
  model_id?: string | null;
  timestamp?: string | null;
  payload?: Record<string, unknown>;
  redaction_status?: string;
  source?: string;
};

type FileChangeSummaryInput = {
  path?: string;
  newPath?: string;
  file?: string;
  diff?: string;
  kind?: {
    type?: string;
    move_path?: string | null;
  };
};

function safeJsonPreview(value: unknown, limit = 500) {
  try {
    return JSON.stringify(value ?? {}, null, 2).slice(0, limit);
  } catch {
    return String(value ?? "");
  }
}

function summarizeDiffText(diff: string) {
  let added = 0;
  let deleted = 0;
  for (const line of diff.split(/\r?\n/)) {
    if (line.startsWith("+++") || line.startsWith("---")) continue;
    if (line.startsWith("+")) added += 1;
    if (line.startsWith("-")) deleted += 1;
  }
  return { added, deleted };
}

function summarizeFileChanges(changes: FileChangeSummaryInput[]) {
  let added = 0;
  let deleted = 0;
  const detailLines: string[] = [];
  const files: string[] = [];

  for (const change of changes) {
    const path = String(change.path ?? change.newPath ?? change.file ?? "file");
    const diff = String(change.diff ?? "");
    const kind = String(change.kind?.type ?? "update");
    const movePath = String(change.kind?.move_path ?? "").trim();
    const counts = summarizeDiffText(diff);

    added += counts.added;
    deleted += counts.deleted;
    files.push(path);

    const changeLabel = kind === "add" ? "新增" : kind === "delete" ? "删除" : movePath ? `更新并移动到 ${movePath}` : "更新";
    detailLines.push(`${path} · ${changeLabel} · +${counts.added} -${counts.deleted}`);

    const excerpt = diff
      .split(/\r?\n/)
      .filter((line) => line && !line.startsWith("@@"))
      .slice(0, 6)
      .join("\n")
      .trim();
    if (excerpt) detailLines.push(excerpt);
  }

  return {
    files,
    added,
    deleted,
    detail: detailLines.join("\n\n"),
  };
}

function summarizeJsonLike(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (!value || typeof value !== "object") return "";
  const record = value as Record<string, unknown>;
  if (typeof record.text === "string" && record.text.trim()) return record.text.trim();
  if (Array.isArray(record.content)) {
    const joined = record.content
      .map((entry) => summarizeJsonLike(entry))
      .filter(Boolean)
      .join("\n");
    if (joined.trim()) return joined.trim();
  }
  return "";
}

function mcpResultDetail(result: unknown) {
  if (!result || typeof result !== "object") return "";
  const record = result as { content?: unknown[]; structuredContent?: unknown };
  const detailChunks: string[] = [];
  for (const entry of record.content ?? []) {
    const text = summarizeJsonLike(entry);
    if (text) detailChunks.push(text);
  }
  const structured = summarizeJsonLike(record.structuredContent);
  if (structured) detailChunks.push(structured);
  if (detailChunks.length > 0) return detailChunks.join("\n\n");
  return safeJsonPreview(result);
}

function dynamicToolResultDetail(item: Extract<DecoratedThreadItem, { type: "dynamicToolCall" }>) {
  const detailChunks: string[] = [];
  const textContent = (item.contentItems ?? [])
    .filter((entry): entry is Extract<NonNullable<typeof item.contentItems>[number], { type: "inputText" }> => entry.type === "inputText")
    .map((entry) => entry.text.trim())
    .filter(Boolean);
  if (textContent.length > 0) detailChunks.push(textContent.join("\n"));

  const imageCount = (item.contentItems ?? []).filter((entry) => entry.type === "inputImage").length;
  if (imageCount > 0) detailChunks.push(`${imageCount} image item${imageCount === 1 ? "" : "s"}`);

  if (detailChunks.length > 0) return detailChunks.join("\n\n");
  return safeJsonPreview(item.arguments);
}

function toolDetail(item: DecoratedThreadItem) {
  const detailChunks: string[] = [];
  const evidence = item.verifiedEvidence;
  if (evidence?.label) detailChunks.push(evidence.label);
  if (evidence?.summary?.length) detailChunks.push(...evidence.summary);
  if (evidence?.paths?.length) detailChunks.push(...evidence.paths.map((path) => `path: ${path}`));
  if (evidence?.urls?.length) detailChunks.push(...evidence.urls.map((url) => `url: ${url}`));
  if (detailChunks.length > 0) return detailChunks.join("\n");
  if (item.type === "mcpToolCall") {
    return item.error ? safeJsonPreview(item.error) : item.result ? mcpResultDetail(item.result) : safeJsonPreview(item.arguments);
  }
  if (item.type === "dynamicToolCall") {
    return dynamicToolResultDetail(item);
  }
  return "";
}

function commandDetail(item: Extract<DecoratedThreadItem, { type: "commandExecution" }>) {
  const detailChunks = [item.command];
  if (item.verifiedEvidence?.summary?.length) detailChunks.push(...item.verifiedEvidence.summary);
  if (item.aggregatedOutput) detailChunks.push(item.aggregatedOutput);
  return detailChunks.filter(Boolean).join("\n\n");
}

function collabToolPreview(item: Extract<ThreadMessageSource, { type: "collabAgentToolCall" }>) {
  const receivers = item.receiverThreadIds.length > 0 ? item.receiverThreadIds.join(", ") : "pending";
  const prompt = item.prompt?.trim() ? item.prompt.trim() : "";
  const detail = [
    `sender: ${item.senderThreadId}`,
    `receivers: ${receivers}`,
    item.model ? `model: ${item.model}` : "",
    item.reasoningEffort ? `effort: ${item.reasoningEffort}` : "",
    prompt ? `prompt: ${prompt}` : "",
  ]
    .filter(Boolean)
    .join("\n");
  return {
    title: item.tool === "spawnAgent" ? "Forked branch task" : `Collab tool: ${item.tool}`,
    detail,
  };
}

function liveCollabPreview(item: Record<string, unknown>) {
  const tool = String(item.tool ?? "collab");
  const receiverThreadIds = Array.isArray(item.receiverThreadIds) ? item.receiverThreadIds.map((value) => String(value)).filter(Boolean) : [];
  const prompt = String(item.prompt ?? "").trim();
  const model = String(item.model ?? "").trim();
  const effort = String(item.reasoningEffort ?? "").trim();
  const preview =
    receiverThreadIds.length > 0
      ? receiverThreadIds.slice(0, 2).join(", ")
      : prompt
          ? prompt.slice(0, 80)
          : tool === "spawnAgent"
            ? "Preparing branch task"
            : tool;
  const detail = [
    receiverThreadIds.length > 0 ? `receivers: ${receiverThreadIds.join(", ")}` : "",
    model ? `model: ${model}` : "",
    effort ? `effort: ${effort}` : "",
    prompt ? `prompt: ${prompt}` : "",
  ]
    .filter(Boolean)
    .join("\n");
  return { preview, detail };
}

function completionQualityBlock(turn: DecoratedTurn): ThreadRenderBlock | null {
  const quality = turn.completionQuality;
  if (!quality) return null;
  const preview = quality.final_preview || "The turn ended after tool activity, but the final assistant answer still looks incomplete.";
  const detail = [
    quality.reason ? `reason: ${quality.reason}` : "",
    quality.recommended_action ? `recommended action: ${quality.recommended_action}` : "",
    quality.tool_item_count !== undefined ? `verified activity items: ${quality.tool_item_count}` : "",
    quality.agent_message_count !== undefined ? `assistant messages: ${quality.agent_message_count}` : "",
    quality.max_agent_chars !== undefined ? `max assistant chars: ${quality.max_agent_chars}` : "",
    quality.final_preview ? `final preview: ${quality.final_preview}` : "",
  ]
    .filter(Boolean)
    .join("\n");
  return {
    key: `${turn.id ?? "turn"}:completion-quality`,
    role: "activity",
    activity: {
      kind: "waiting",
      label: "Final answer may need a follow-up",
      status: quality.status || "warning",
      preview,
      detail,
    },
  };
}

function codingEventPreview(payload: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }
  return "";
}

function codingEventList(payload: Record<string, unknown>, key: string) {
  const value = payload[key];
  if (!Array.isArray(value)) return [];
  return value.map((entry) => String(entry ?? "").trim()).filter(Boolean);
}

function renderBlocksForCodingEvent(event: DecoratedCodingEvent, fallbackKey: string): ThreadRenderBlock[] {
  const eventType = String(event.event_type ?? "").trim();
  const payload = event.payload && typeof event.payload === "object" ? event.payload : {};
  const key = String(event.event_id ?? "").trim() || fallbackKey;
  switch (eventType) {
    case "agent_message": {
      const text = codingEventPreview(payload, ["text", "message", "summary"]);
      if (!text) return [];
      return [{ key, role: payload.role === "user" ? "user" : "assistant", text }];
    }
    case "reasoning_summary": {
      const text = codingEventPreview(payload, ["text", "summary"]);
      if (!text) return [];
      return [{ key, role: "reasoning", text: [text], source: event.source || "coding_event" }];
    }
    case "plan_update": {
      const text = codingEventPreview(payload, ["text", "summary"]);
      if (!text) return [];
      return [{ key, role: "plan", text }];
    }
    case "command_execution": {
      const command = codingEventPreview(payload, ["command"]);
      const output = codingEventPreview(payload, ["output_excerpt"]);
      return [{ key, role: "command", command: command || "Command", output, status: String(payload.status ?? "completed") }];
    }
    case "file_change": {
      const files = codingEventList(payload, "paths");
      return [{
        key,
        role: "file_change",
        files,
        status: typeof payload.count === "number" ? `${payload.count} change${payload.count === 1 ? "" : "s"}` : "changed",
        detail: files.length > 0 ? files.join("\n") : undefined,
      }];
    }
    case "file_read": {
      const path = codingEventPreview(payload, ["path"]);
      const kind = codingEventPreview(payload, ["kind"]);
      const ok = payload.ok !== false;
      return [{
        key,
        role: "tool",
        title: "Read file",
        status: ok ? "completed" : "failed",
        detail: [path ? `path: ${path}` : "", kind ? `kind: ${kind}` : ""].filter(Boolean).join("\n"),
      }];
    }
    case "edit_operation": {
      const path = codingEventPreview(payload, ["path"]);
      const reviewDiffPath = codingEventPreview(payload, ["review_diff_path"]);
      const checkpointSaveId = codingEventPreview(payload, ["checkpoint_save_id"]);
      const detail = [
        path ? `path: ${path}` : "",
        payload.changed !== undefined ? `changed: ${Boolean(payload.changed)}` : "",
        payload.applied !== undefined ? `applied: ${Boolean(payload.applied)}` : "",
        reviewDiffPath ? `review diff: ${reviewDiffPath}` : "",
        checkpointSaveId ? `checkpoint: ${checkpointSaveId}` : "",
      ]
        .filter(Boolean)
        .join("\n");
      return [{ key, role: "tool", title: "Edit operation", status: payload.ok === false ? "failed" : "completed", detail }];
    }
    case "checkpoint_created": {
      const saveId = codingEventPreview(payload, ["save_id"]);
      const description = codingEventPreview(payload, ["description"]);
      return [{
        key,
        role: "tool",
        title: "Checkpoint created",
        status: payload.ok === false ? "failed" : "completed",
        detail: [saveId ? `save id: ${saveId}` : "", description ? `description: ${description}` : ""].filter(Boolean).join("\n"),
      }];
    }
    case "verification_result": {
      const tool = codingEventPreview(payload, ["tool"]);
      const path = codingEventPreview(payload, ["path"]);
      const files = codingEventList(payload, "files");
      const paths = codingEventList(payload, "paths");
      const saveIds = codingEventList(payload, "save_ids");
      const detail = [
        path ? `path: ${path}` : "",
        files.length > 0 ? `files: ${files.join(", ")}` : "",
        paths.length > 0 ? `paths: ${paths.join(", ")}` : "",
        saveIds.length > 0 ? `checkpoints: ${saveIds.join(", ")}` : "",
        payload.command_count !== undefined ? `commands: ${String(payload.command_count)}` : "",
        payload.item_count !== undefined ? `items: ${String(payload.item_count)}` : "",
      ]
        .filter(Boolean)
        .join("\n");
      return [{
        key,
        role: "tool",
        title: tool ? `Verification: ${tool}` : "Verification result",
        status: payload.ok === false ? "failed" : "completed",
        detail,
      }];
    }
    case "provider_handoff": {
      const toThreadId = codingEventPreview(payload, ["to_thread_id"]);
      const model = codingEventPreview(payload, ["model"]);
      const reused = payload.reused_existing === true;
      const transitionSummary = payload.transition_summary && typeof payload.transition_summary === "object"
        ? payload.transition_summary as Record<string, unknown>
        : {};
      const projectionMode = typeof transitionSummary.projection_mode === "string" ? transitionSummary.projection_mode.trim() : "";
      const projectionPreview = typeof transitionSummary.projection_preview === "string" ? transitionSummary.projection_preview.trim() : "";
      const droppedArtifacts = typeof transitionSummary.dropped_artifacts === "number" ? transitionSummary.dropped_artifacts : null;
      const repairedToolPairs = typeof transitionSummary.repaired_tool_pairs === "number" ? transitionSummary.repaired_tool_pairs : null;
      const replayableArtifactCount = typeof transitionSummary.replayable_artifact_count === "number"
        ? transitionSummary.replayable_artifact_count
        : null;
      const targetRuntime = transitionSummary.target_runtime && typeof transitionSummary.target_runtime === "object"
        ? transitionSummary.target_runtime as Record<string, unknown>
        : {};
      return [{
        key,
        role: "activity",
        activity: {
          kind: "fork",
          label: "模型通道已切换",
          status: "completed",
          preview: [event.provider_id ? `提供方 ${event.provider_id}` : "", model ? `模型 ${model}` : ""].filter(Boolean).join(" · ") || "Provider handoff",
          detail: [
            toThreadId ? `to execution lane: ${toThreadId}` : "",
            reused ? "reused existing lane" : "",
            projectionMode ? `projection: ${projectionMode}` : "",
            targetRuntime.protocol ? `protocol: ${String(targetRuntime.protocol)}` : "",
            targetRuntime.base_url ? `base url: ${String(targetRuntime.base_url)}` : "",
            droppedArtifacts ? `dropped artifacts: ${String(droppedArtifacts)}` : "",
            repairedToolPairs ? `repaired tool pairs: ${String(repairedToolPairs)}` : "",
            replayableArtifactCount ? `replayable artifacts: ${String(replayableArtifactCount)}` : "",
            projectionPreview ? `projection preview: ${projectionPreview}` : "",
          ].filter(Boolean).join("\n"),
        },
      }];
    }
    case "runtime_transition": {
      const transition = codingEventPreview(payload, ["transition"]);
      const review = codingEventPreview(payload, ["review"]);
      return [{
        key,
        role: "activity",
        activity: {
          kind: "review",
          label: "Runtime status updated",
          status: "completed",
          preview: transition || "runtime transition",
          detail: review,
        },
      }];
    }
    default:
      return [];
  }
}

export function itemActivityFromPayload(item: Record<string, unknown>, status = "active"): RuntimeActivityState | null {
  const itemType = String(item.type ?? "");
  const itemId = String(item.id ?? "");
  if (itemType === "reasoning") {
    return { kind: "thinking", label: "Thinking", status, item_id: itemId };
  }
  if (itemType === "commandExecution") {
    return {
      kind: "command",
      label: "正在执行命令",
      status,
      preview: String(item.command ?? ""),
      detail: String(item.command ?? ""),
      item_id: itemId,
    };
  }
  if (itemType === "fileChange") {
    return { kind: "file_change", label: "正在修改文件", status, item_id: itemId };
  }
  if (itemType === "webSearch") {
    return {
      kind: "web_search",
      label: "正在搜索",
      status,
      preview: String(item.query ?? ""),
      detail: safeJsonPreview(item.action),
      item_id: itemId,
    };
  }
  if (itemType === "mcpToolCall") {
    return {
      kind: "mcp",
      label: "正在调用 MCP 工具",
      status,
      preview: [item.server, item.tool].filter(Boolean).join("."),
      detail: safeJsonPreview(item.arguments),
      item_id: itemId,
    };
  }
  if (itemType === "dynamicToolCall") {
    return {
      kind: "tool",
      label: "正在调用工具",
      status,
      preview: [item.namespace, item.tool].filter(Boolean).join("."),
      detail: safeJsonPreview(item.arguments),
      item_id: itemId,
    };
  }
  if (itemType === "enteredReviewMode" || itemType === "exitedReviewMode") {
    return {
      kind: "review",
      label: itemType === "enteredReviewMode" ? "Entered review mode" : "Exited review mode",
      status,
      preview: String(item.review ?? ""),
      item_id: itemId,
    };
  }
  if (itemType === "collabAgentToolCall") {
    const collab = liveCollabPreview(item);
    return {
      kind: item.tool === "spawnAgent" ? "fork" : "tool",
      label: item.tool === "spawnAgent" ? "创建分支任务" : "正在调用协作工具",
      status,
      preview: collab.preview,
      detail: [collab.detail, safeJsonPreview(item.agentsStates)].filter(Boolean).join("\n\n"),
      item_id: itemId,
    };
  }
  if (itemType === "contextCompaction") {
    return {
      kind: "compact",
      label: status === "completed" ? "Context compacted" : "Compacting context",
      status,
      preview: "Context compaction",
      item_id: itemId,
    };
  }
  return null;
}

export function renderBlocksForItem(item: ThreadMessageSource): ThreadRenderBlock[] {
  const decoratedItem = item as DecoratedThreadItem;
  switch (item.type) {
    case "userMessage": {
      const text = item.content
        .filter((entry) => entry.type === "text")
        .map((entry) => entry.text)
        .join("\n");
      const attachments = item.content
        .filter((entry) => entry.type !== "text")
        .map((entry) => ("name" in entry ? entry.name : entry.type === "localImage" ? entry.path.split(/[\\/]/).pop() ?? entry.path : entry.url));
      return [{ key: item.id, role: "user", text, attachments }];
    }
    case "agentMessage":
      return [{ key: item.id, role: "assistant", text: item.text }];
    case "plan":
      return [{ key: item.id, role: "plan", text: item.text }];
    case "reasoning":
      return [{ key: item.id, role: "reasoning", text: item.summary.length > 0 ? item.summary : item.content }];
    case "commandExecution":
      return [
        {
          key: item.id,
          role: "command",
          command: item.command,
          output: commandDetail(decoratedItem as Extract<DecoratedThreadItem, { type: "commandExecution" }>),
          status: item.status,
        },
      ];
    case "fileChange": {
      const summary = summarizeFileChanges(item.changes as FileChangeSummaryInput[]);
      return [
        {
          key: item.id,
          role: "file_change",
          files: summary.files,
          status: item.status,
          added: summary.added,
          deleted: summary.deleted,
          detail: summary.detail,
        },
      ];
    }
    case "mcpToolCall":
      return [{
        key: item.id,
        role: "tool",
        title: `${item.server}.${item.tool}`,
        status: item.status,
        detail: toolDetail(decoratedItem),
      }];
    case "dynamicToolCall":
      return [{ key: item.id, role: "tool", title: `${item.namespace ?? "tool"}.${item.tool}`, status: item.status, detail: toolDetail(decoratedItem) }];
    case "collabAgentToolCall": {
      const collab = collabToolPreview(item);
      return [{ key: item.id, role: "tool", title: collab.title, status: item.status, detail: collab.detail }];
    }
    case "webSearch":
      return [{
        key: item.id,
        role: "activity",
        activity: {
          kind: "web_search",
          label: "网页搜索",
          status: "completed",
          preview: item.query,
          detail: safeJsonPreview(item.action),
          item_id: item.id,
        },
      }];
    case "imageView":
      return [{ key: item.id, role: "image", path: item.path }];
    case "imageGeneration":
      return [{
        key: item.id,
        role: "tool",
        title: "Image generation",
        status: item.status,
        detail: [item.revisedPrompt, item.savedPath, item.result].filter(Boolean).join("\n"),
      }];
    case "enteredReviewMode":
      return [{
        key: item.id,
        role: "activity",
        activity: {
          kind: "review",
          label: "进入审查模式",
          status: "completed",
          preview: item.review,
          item_id: item.id,
        },
      }];
    case "exitedReviewMode":
      return [{
        key: item.id,
        role: "activity",
        activity: {
          kind: "review",
          label: "Exited review mode",
          status: "completed",
          preview: item.review,
          item_id: item.id,
        },
      }];
    case "contextCompaction":
      return [{
        key: item.id,
        role: "activity",
        activity: {
          kind: "compact",
          label: "上下文已压缩",
          status: "completed",
          preview: "Context compaction completed",
          item_id: item.id,
        },
      }];
    default:
      return [];
  }
}

const RENDERABLE_ITEM_TYPES = [
  "agentMessage",
  "plan",
  "commandExecution",
  "fileChange",
  "mcpToolCall",
  "dynamicToolCall",
  "collabAgentToolCall",
  "webSearch",
  "imageView",
  "imageGeneration",
  "enteredReviewMode",
  "exitedReviewMode",
  "contextCompaction",
];

const RENDERABLE_CODING_EVENT_TYPES = [
  "agent_message",
  "plan_update",
  "reasoning_summary",
  "command_execution",
  "file_change",
  "file_read",
  "edit_operation",
  "checkpoint_created",
  "verification_result",
  "provider_handoff",
  "runtime_transition",
];

type RenderableTurn = {
  id?: string;
  status?: string;
  error?: unknown;
  completedAt?: number | null;
  items?: ThreadMessageSource[];
  coding_events?: DecoratedCodingEvent[];
};

type ConversationRenderThread = {
  id?: string;
  displayName?: string | null;
  status?: string | { type?: string; stale_error_type?: string; stale_error_normalized?: boolean; activeFlags?: unknown[] } | null;
  turns?: RenderableTurn[] | null;
};

export type ConversationRenderState =
  | { kind: "loading"; tone: "info"; title: string; detail: string }
  | { kind: "ready"; tone: "default"; title: string; detail?: string; staleErrorType?: string }
  | { kind: "empty"; tone: "default" | "info"; title: string; detail: string; emptyKind: "new_thread" | "terminal_empty" }
  | {
      kind: "diagnostic";
      tone: "info" | "warning" | "danger";
      title: string;
      detail: string;
      diagnosticKind:
        | "runtime_error"
        | "thread_not_loaded"
        | "turn_failed"
        | "turn_interrupted"
        | "turn_cancelled"
        | "render_mismatch"
        | "stale_runtime_error";
    };

function hasRenderableTurnContent(turn?: RenderableTurn | null) {
  const itemContent = (turn?.items ?? []).some((item) => RENDERABLE_ITEM_TYPES.includes(item.type));
  if (itemContent) return true;
  return (turn?.coding_events ?? []).some((event) => RENDERABLE_CODING_EVENT_TYPES.includes(String(event.event_type ?? "")));
}

export function hasPersistedRenderableTurnContent(turn?: RenderableTurn | null) {
  if (!turn?.completedAt) return false;
  return hasRenderableTurnContent(turn);
}

export function hasRenderableThreadContent(thread?: { turns?: RenderableTurn[] } | null) {
  return (thread?.turns ?? []).some((turn) => hasRenderableTurnContent(turn));
}

function threadStatusRecord(thread?: ConversationRenderThread | null) {
  const status = thread?.status;
  if (status && typeof status === "object") return status;
  if (typeof status === "string" && status.trim()) return { type: status.trim() };
  return {};
}

function threadStatusType(thread?: ConversationRenderThread | null) {
  return String(threadStatusRecord(thread).type ?? "").trim();
}

function latestTurn(thread?: ConversationRenderThread | null) {
  const turns = thread?.turns ?? [];
  return turns.length > 0 ? turns[turns.length - 1] : null;
}

function turnErrorMessage(error: unknown) {
  if (!error) return "";
  if (typeof error === "string") return error;
  if (typeof error === "object") {
    const record = error as { message?: unknown; additionalDetails?: unknown };
    return String(record.message ?? record.additionalDetails ?? "").trim();
  }
  return String(error);
}

function hasApiConversationPayload(thread?: ConversationRenderThread | null) {
  return (thread?.turns ?? []).some((turn) =>
    (turn.items ?? []).length > 0 ||
    (turn.coding_events ?? []).length > 0 ||
    Boolean((turn as { completionQuality?: unknown }).completionQuality),
  );
}

export function describeConversationRenderState({
  activeThread,
  selectedRuntimeThread,
  taskConversationThread,
  blocks,
  isLoading,
}: {
  activeThread?: ConversationRenderThread | null;
  selectedRuntimeThread?: ConversationRenderThread | null;
  taskConversationThread?: ConversationRenderThread | null;
  blocks?: ThreadRenderBlock[];
  isLoading?: boolean;
}): ConversationRenderState {
  if (isLoading) {
    return {
      kind: "loading",
      tone: "info",
      title: "Conversation is loading",
      detail: "AstraBridge is refreshing the task conversation and internal execution lane.",
    };
  }

  const renderedBlocks = blocks ?? [];
  const sourceThread = activeThread ?? taskConversationThread ?? selectedRuntimeThread ?? null;
  const statusSource = selectedRuntimeThread ?? activeThread ?? taskConversationThread ?? null;
  const status = threadStatusRecord(statusSource);
  const statusType = threadStatusType(statusSource);
  const staleErrorType = String(status.stale_error_type ?? "").trim();
  const staleErrorNormalized = Boolean(status.stale_error_normalized || staleErrorType);
  const latest = latestTurn(sourceThread) ?? latestTurn(selectedRuntimeThread) ?? latestTurn(taskConversationThread);
  const turnStatus = String(latest?.status ?? "").trim().toLowerCase();
  const hasPayload = hasApiConversationPayload(sourceThread) || hasApiConversationPayload(selectedRuntimeThread) || hasApiConversationPayload(taskConversationThread);

  if (statusType === "systemError") {
    return {
      kind: "diagnostic",
      tone: "danger",
      diagnosticKind: "runtime_error",
      title: "Task runtime error",
      detail: "The runtime reported a system error for this task's execution lane. Use the inspector recovery controls or retry after restart.",
    };
  }

  if (statusType === "notLoaded") {
    return {
      kind: "diagnostic",
      tone: "warning",
      diagnosticKind: "thread_not_loaded",
      title: "Execution lane is not loaded",
      detail: "The runtime has not loaded this task's execution lane yet. Refresh the task or switch back to the active provider lane.",
    };
  }

  if (turnStatus === "failed" || Boolean(latest?.error)) {
    const message = turnErrorMessage(latest?.error);
    return {
      kind: "diagnostic",
      tone: "danger",
      diagnosticKind: "turn_failed",
      title: "Last turn failed",
      detail: message || "The last turn ended with an error before a renderable assistant response was available.",
    };
  }

  if (turnStatus === "interrupted") {
    return {
      kind: "diagnostic",
      tone: "warning",
      diagnosticKind: "turn_interrupted",
      title: "Last turn was interrupted",
      detail: "The turn stopped before completion. Continue, retry, or fork from the current task if the context is still useful.",
    };
  }

  if (turnStatus === "cancelled" || turnStatus === "canceled") {
    return {
      kind: "diagnostic",
      tone: "warning",
      diagnosticKind: "turn_cancelled",
      title: "Last turn was cancelled",
      detail: "The turn was cancelled before a renderable assistant response was available.",
    };
  }

  if (renderedBlocks.length === 0 && hasPayload) {
    return {
      kind: "diagnostic",
      tone: "warning",
      diagnosticKind: "render_mismatch",
      title: "Conversation data needs review",
      detail: "The API returned turn data, but the chat renderer could not turn it into visible messages. Check the inspector for raw execution-lane and task-conversation evidence.",
    };
  }

  if (staleErrorNormalized) {
    return {
      kind: "diagnostic",
      tone: "info",
      diagnosticKind: "stale_runtime_error",
      title: "Recovered stale runtime status",
      detail: `The runtime previously reported ${staleErrorType || "an error"}, but the latest completed turn is clean. The raw status is retained in diagnostics.`,
    };
  }

  if (renderedBlocks.length > 0) {
    return { kind: "ready", tone: "default", title: "Conversation is renderable" };
  }

  if (turnStatus === "completed") {
    return {
      kind: "empty",
      tone: "info",
      emptyKind: "terminal_empty",
      title: "Turn completed without visible output",
      detail: "The latest turn completed, but it did not include assistant, tool, plan, artifact, or diagnostic content for the chat surface.",
    };
  }

  return {
    kind: "empty",
    tone: "default",
    emptyKind: "new_thread",
    title: "No turns yet",
    detail: "Start with a prompt or attachments.",
  };
}

export function summarizeTurnBlocks(
  thread?: { turns?: DecoratedTurn[] } | null,
  liveText?: string,
  liveReasoning?: { text: string; source: string; label: string },
  liveActivity?: RuntimeActivityState,
  liveDiff?: RuntimeDiffSummary,
  liveTurnId?: string,
): ThreadRenderBlock[] {
  if (!thread) {
    const liveBlocks: ThreadRenderBlock[] = [];
    if (liveActivity) liveBlocks.push({ key: "activity-live", role: "activity", activity: liveActivity, diff: liveDiff });
    if (liveReasoning?.text) liveBlocks.push({ key: "reasoning-live", role: "reasoning", text: [liveReasoning.text], source: liveReasoning.label || liveReasoning.source, live: true });
    if (liveText) liveBlocks.push({ key: "live", role: "assistant_live", text: liveText });
    return liveBlocks;
  }

  const turns = thread.turns ?? [];
  const blocks: ThreadRenderBlock[] = [];
  let renderedLiveTurn = false;
  for (const turn of turns) {
    const turnMeta = {
      turnId: turn.id,
      startedAt: turn.startedAt ?? null,
      completedAt: turn.completedAt ?? null,
      durationMs: turn.durationMs ?? null,
      sourceThreadId: turn.source_thread_id ?? turn.sourceThreadId,
      profileId: turn.profile_id ?? turn.profileId,
      providerId: turn.provider_id ?? turn.providerId,
      model: turn.model,
      reasoningEffort: turn.reasoning_effort ?? turn.reasoningEffort,
    };
    let renderedTurnContent = false;
    for (const item of turn.items ?? []) {
      const rendered = renderBlocksForItem(item).map((block) => ({ ...turnMeta, ...block }));
      if (rendered.length > 0) renderedTurnContent = true;
      blocks.push(...rendered);
    }
    if (!renderedTurnContent) {
      for (const [index, event] of (turn.coding_events ?? []).entries()) {
        const rendered = renderBlocksForCodingEvent(event, `${turn.id ?? "turn"}:event:${index}`).map((block) => ({
          ...turnMeta,
          providerId: block.providerId ?? turnMeta.providerId ?? event.provider_id ?? undefined,
          model: block.model ?? turnMeta.model ?? event.model_id ?? undefined,
          sourceThreadId: block.sourceThreadId ?? turnMeta.sourceThreadId ?? event.execution_thread_id ?? undefined,
          ...block,
        }));
        if (rendered.length > 0) renderedTurnContent = true;
        blocks.push(...rendered);
      }
    }
    const qualityBlock = completionQualityBlock(turn);
    if (qualityBlock) {
      blocks.push({ ...turnMeta, ...qualityBlock });
    }
    const isLatest = turn.id === (turns[turns.length - 1]?.id ?? "");
    if (liveTurnId && turn.id === liveTurnId) {
      renderedLiveTurn = true;
    }
    if (liveText && isLatest) {
      if (liveActivity) {
        blocks.push({ ...turnMeta, key: `activity-${turn.id}`, role: "activity", activity: liveActivity, diff: liveDiff, completedAt: null, durationMs: null });
      }
      if (liveReasoning?.text) {
        blocks.push({
          ...turnMeta,
          key: `reasoning-live-${turn.id}`,
          role: "reasoning",
          text: [liveReasoning.text],
          source: liveReasoning.label || liveReasoning.source,
          live: true,
          completedAt: null,
          durationMs: null,
        });
      }
      blocks.push({ ...turnMeta, key: `live-${turn.id}`, role: "assistant_live", text: liveText, completedAt: null, durationMs: null });
    } else if (!liveText && isLatest && (liveActivity || liveReasoning?.text)) {
      if (liveActivity) {
        blocks.push({ ...turnMeta, key: `activity-${turn.id}`, role: "activity", activity: liveActivity, diff: liveDiff, completedAt: null, durationMs: null });
      }
      if (liveReasoning?.text) {
        blocks.push({
          ...turnMeta,
          key: `reasoning-live-${turn.id}`,
          role: "reasoning",
          text: [liveReasoning.text],
          source: liveReasoning.label || liveReasoning.source,
          live: true,
          completedAt: null,
          durationMs: null,
        });
      }
    }
  }
  if ((liveText || liveActivity || liveReasoning?.text) && liveTurnId && !renderedLiveTurn) {
    const liveMeta = { key: `live-${liveTurnId}`, turnId: liveTurnId, startedAt: null, completedAt: null, durationMs: null };
    if (liveActivity) {
      blocks.push({ ...liveMeta, key: `activity-${liveTurnId}`, role: "activity", activity: liveActivity, diff: liveDiff });
    }
    if (liveReasoning?.text) {
      blocks.push({
        ...liveMeta,
        key: `reasoning-live-${liveTurnId}`,
        role: "reasoning",
        text: [liveReasoning.text],
        source: liveReasoning.label || liveReasoning.source,
        live: true,
      });
    }
    if (liveText) {
      blocks.push({ ...liveMeta, role: "assistant_live", text: liveText });
    }
  }
  return blocks;
}

