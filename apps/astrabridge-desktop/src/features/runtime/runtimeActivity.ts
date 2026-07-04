import type { RuntimeActivityEntry, RuntimeActivityKind, RuntimeDiffSummary, ThreadRenderBlock } from "../../types";

const PATH_SEGMENT_LIMIT = 2;
const PREVIEW_LIMIT = 96;

function compactText(value: string | undefined | null, limit = PREVIEW_LIMIT) {
  const compact = String(value ?? "").replace(/\s+/g, " ").trim();
  if (compact.length <= limit) return compact;
  return `${compact.slice(0, limit).trimEnd()}...`;
}

export function shortenActivityPath(path: string, segments = PATH_SEGMENT_LIMIT) {
  const clean = String(path ?? "").trim();
  if (!clean) return "";
  const parts = clean.split(/[\\/]+/).filter(Boolean);
  if (parts.length <= segments) return clean;
  return parts.slice(-segments).join("/");
}

function canonicalKind(kind: RuntimeActivityKind): RuntimeActivityKind {
  if (kind === "web_search") return "web";
  if (kind === "file_change") return "file_edit";
  return kind;
}

function firstDetailLine(detail: string | undefined) {
  return String(detail ?? "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find(Boolean) ?? "";
}

function classifyTool(title: string, detail?: string): RuntimeActivityKind {
  const haystack = `${title}\n${detail ?? ""}`.toLowerCase();
  if (haystack.includes("yunwu_image_") || haystack.includes("image generation") || haystack.includes("asset:") || haystack.includes("images:")) {
    return "multimodal";
  }
  if (haystack.includes("browser") || haystack.includes("screenshot:") || haystack.includes("capture") || haystack.includes("smoke")) {
    return "browser";
  }
  if (haystack.includes("astrabridge_web_") || haystack.includes("web_search") || haystack.includes("research") || haystack.includes("sources:") || haystack.includes("url:")) {
    return "web";
  }
  return "tool";
}

function toolPreview(title: string, detail?: string) {
  const evidenceLine = String(detail ?? "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) =>
      /^sources:\s*\d+/i.test(line) ||
      /^images:\s*/i.test(line) ||
      /^browser smoke/i.test(line) ||
      /^asset:/i.test(line)
    );
  if (evidenceLine) return evidenceLine;
  return compactText(title);
}

export function runtimeActivityStatusLabel(entry: RuntimeActivityEntry, locale: "en" | "zh-CN") {
  const active = entry.status === "active" || entry.status === "pending" || entry.status === "inProgress";
  const failed = String(entry.status).toLowerCase() === "failed";
  if (locale !== "zh-CN") {
    if (entry.kind === "command") return failed ? "Command failed" : active ? "Running" : "Ran";
    if (entry.kind === "file_edit") return failed ? "Edit failed" : active ? "Editing" : "Edited";
    if (entry.kind === "web" || entry.kind === "browser") return failed ? "Web failed" : active ? "Using web" : "Fetched";
    if (entry.kind === "multimodal") return failed ? "Multimodal failed" : active ? "Using multimodal" : "Completed multimodal";
    if (entry.kind === "mcp") return failed ? "MCP failed" : active ? "Calling MCP" : "Called MCP";
    if (entry.kind === "tool") return failed ? "Tool failed" : active ? "Calling tool" : "Called tool";
    if (entry.kind === "compact") return active ? "Compacting" : "Compacted";
    if (entry.kind === "fork") return active ? "Creating branch task" : "Created branch task";
    if (entry.kind === "review") return active ? "Reviewing" : "Reviewed";
    if (entry.kind === "thinking") return "Thinking";
    return active ? "Working" : "Done";
  }
  if (entry.kind === "command") return failed ? "命令失败" : active ? "正在执行" : "已运行";
  if (entry.kind === "file_edit") return failed ? "编辑失败" : active ? "正在编辑" : "已编辑";
  if (entry.kind === "web" || entry.kind === "browser") return failed ? "联网失败" : active ? "正在联网" : "已获取";
  if (entry.kind === "multimodal") return failed ? "多模态失败" : active ? "正在处理多模态" : "已完成多模态";
  if (entry.kind === "mcp") return failed ? "MCP 调用失败" : active ? "正在调用 MCP 工具" : "已调用 MCP 工具";
  if (entry.kind === "tool") return failed ? "工具调用失败" : active ? "正在调用工具" : "已调用工具";
  if (entry.kind === "compact") return active ? "正在压缩上下文" : "上下文已压缩";
  if (entry.kind === "fork") return active ? "正在创建分支任务" : "已创建分支任务";
  if (entry.kind === "review") return active ? "正在审查" : "审查已更新";
  if (entry.kind === "thinking") return "正在思考";
  return active ? "正在处理" : "已完成";
}
export function normalizeRuntimeActivity(block: ThreadRenderBlock): RuntimeActivityEntry | null {
  const startedAt = block.startedAt ?? null;
  const completedAt = block.completedAt ?? null;
  if (block.role === "activity") {
    const kind = canonicalKind(block.activity.kind);
    const diff = block.diff;
    const files = diff?.file_paths ?? [];
    return {
      id: block.key,
      kind,
      status: block.activity.status,
      label: block.activity.label,
      preview: kind === "file_edit" && files.length > 0 ? files.map((file) => shortenActivityPath(file)).slice(0, 2).join(", ") : compactText(block.activity.preview || block.activity.label),
      detail: block.activity.detail,
      files,
      diff,
      startedAt,
      completedAt,
      toolName: kind === "mcp" || kind === "tool" ? block.activity.preview : undefined,
    };
  }
  if (block.role === "command") {
    return {
      id: block.key,
      kind: "command",
      status: block.status,
      label: "Command",
      preview: compactText(block.command),
      detail: [block.command, block.output].filter(Boolean).join("\n\n"),
      toolName: "shell_command",
      startedAt,
      completedAt,
    };
  }
  if (block.role === "file_change") {
    const diff: RuntimeDiffSummary = {
      files: block.files.length,
      added: block.added ?? 0,
      deleted: block.deleted ?? 0,
      file_paths: block.files,
      detail: block.detail,
    };
    return {
      id: block.key,
      kind: "file_edit",
      status: block.status,
      label: "File edit",
      preview: block.files.map((file) => shortenActivityPath(file)).slice(0, 2).join(", "),
      detail: block.detail,
      files: block.files,
      diff,
      startedAt,
      completedAt,
    };
  }
  if (block.role === "tool") {
    const kind = classifyTool(block.title, block.detail);
    return {
      id: block.key,
      kind,
      status: block.status,
      label: block.title,
      preview: toolPreview(block.title, block.detail),
      detail: block.detail,
      toolName: block.title,
      startedAt,
      completedAt,
    };
  }
  return null;
}
