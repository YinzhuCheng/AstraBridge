import { useEffect, useMemo, useState } from "react";

import type { LocaleCode, McpRuntimeStatus, McpStatusResponse } from "../../types";

type McpToolCallPayload = {
  profile_id?: string;
  thread_id: string;
  server: string;
  tool: string;
  arguments?: Record<string, unknown>;
};

type McpToolDiagnosticsPanelProps = {
  locale: LocaleCode;
  status?: McpStatusResponse | null;
  isLoading?: boolean;
  error?: unknown;
  profileId?: string;
  onCallTool: (payload: McpToolCallPayload) => Promise<unknown>;
};

const RESULT_PREVIEW_LIMIT = 2800;

const COPY = {
  en: {
    title: "MCP tool diagnostics",
    summary: "Inspect discovered runtime tools, replay one deterministic call, and keep arguments/results redacted for review.",
    discovered: "Discovered",
    server: "Server",
    tool: "Tool",
    arguments: "Arguments JSON",
    call: "Call tool",
    calling: "Calling...",
    noTools: "No runtime MCP tools are visible.",
    noToolsHint: "Reload MCP, install a preset, or check provider/runtime health before expecting tool calls here.",
    loading: "Checking runtime MCP tools...",
    statusError: "MCP status is unavailable.",
    schemaError: "Arguments must be a JSON object.",
    missingTool: "Select a visible MCP server and tool before calling.",
    missingThread: "MCP status thread is not ready. Refresh status or reload MCP, then retry.",
    callFailed: "Tool call failed",
    envelope: "Replay envelope",
    result: "Result preview",
    redacted: "Sensitive keys are redacted.",
    truncated: "Large result truncated for UI display.",
    auth: "auth",
    resources: "resources",
  },
  "zh-CN": {
    title: "MCP 工具诊断",
    summary: "检查运行时已发现的工具，复放一次确定性调用，并对参数和结果做脱敏展示。",
    discovered: "已发现",
    server: "服务器",
    tool: "工具",
    arguments: "参数 JSON",
    call: "调用工具",
    calling: "调用中...",
    noTools: "当前没有可见的运行时 MCP 工具。",
    noToolsHint: "请先重新加载 MCP、安装预设，或检查 provider/runtime 健康状态，再期待工具调用。",
    loading: "正在检查运行时 MCP 工具...",
    statusError: "MCP 状态暂不可用。",
    schemaError: "参数必须是 JSON 对象。",
    missingTool: "请先选择一个可见的 MCP 服务器和工具。",
    missingThread: "MCP 状态线程尚未就绪。请刷新状态或重新加载 MCP 后重试。",
    callFailed: "工具调用失败",
    envelope: "复放调用包",
    result: "结果预览",
    redacted: "敏感键已脱敏。",
    truncated: "大结果已在 UI 中截断。",
    auth: "认证",
    resources: "资源",
  },
} as const satisfies Record<string, Record<string, string>>;

export function McpToolDiagnosticsPanel({
  locale,
  status,
  isLoading = false,
  error,
  profileId,
  onCallTool,
}: McpToolDiagnosticsPanelProps) {
  const copy = COPY[locale] ?? COPY.en;
  const toolEntries = useMemo(() => flattenMcpTools(status), [status]);
  const [selectedServer, setSelectedServer] = useState("");
  const [selectedTool, setSelectedTool] = useState("");
  const [argumentsText, setArgumentsText] = useState("{}");
  const [pending, setPending] = useState(false);
  const [callError, setCallError] = useState("");
  const [lastCall, setLastCall] = useState<{
    envelope: ReturnType<typeof formatJsonForUi>;
    result: ReturnType<typeof formatJsonForUi>;
  } | null>(null);

  useEffect(() => {
    if (toolEntries.some((entry) => entry.server === selectedServer && entry.tool === selectedTool)) return;
    const first = toolEntries[0];
    setSelectedServer(first?.server ?? "");
    setSelectedTool(first?.tool ?? "");
  }, [selectedServer, selectedTool, toolEntries]);

  const servers = useMemo(() => {
    const unique = new Map<string, McpRuntimeStatus>();
    for (const server of status?.servers ?? []) unique.set(server.name, server);
    return [...unique.values()];
  }, [status]);
  const selectedServerStatus = servers.find((server) => server.name === selectedServer) ?? null;
  const visibleTools = toolEntries.filter((entry) => entry.server === selectedServer);
  const toolCount = toolEntries.length;
  const statusError = error ? `${copy.statusError} ${String((error as Error)?.message ?? error)}` : "";

  async function handleCall() {
    setCallError("");
    setLastCall(null);
    if (!selectedServer || !selectedTool) {
      setCallError(copy.missingTool);
      return;
    }
    const parsed = parseArgumentsObject(argumentsText);
    if (!parsed.ok) {
      setCallError(copy.schemaError);
      return;
    }
    const threadId = String(status?.thread_id ?? "").trim();
    if (!threadId) {
      setCallError(copy.missingThread);
      return;
    }
    const envelope = {
      profile_id: profileId || undefined,
      thread_id: threadId,
      server: selectedServer,
      tool: selectedTool,
      arguments: parsed.value,
    };
    setPending(true);
    try {
      const result = await onCallTool(envelope);
      setLastCall({
        envelope: formatJsonForUi(redactSensitive(envelope), RESULT_PREVIEW_LIMIT),
        result: formatJsonForUi(redactSensitive(result), RESULT_PREVIEW_LIMIT),
      });
    } catch (toolError) {
      setCallError(`${copy.callFailed}: ${String((toolError as Error)?.message ?? toolError)}`);
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="metadata-section mcp-diagnostics-panel" data-testid="mcp-tool-diagnostics-panel">
      <div className="mcp-diagnostics-header">
        <div>
          <h4>{copy.title}</h4>
          <p className="muted">{copy.summary}</p>
        </div>
        <span className={`status-tag ${toolCount > 0 ? "capability-ok" : "capability-warn"}`}>
          {copy.discovered}: {toolCount}
        </span>
      </div>

      {isLoading ? <p className="muted">{copy.loading}</p> : null}
      {statusError ? <p className="error-text">{statusError}</p> : null}
      {!isLoading && toolCount === 0 ? (
        <div className="mcp-diagnostics-empty" role="status">
          <strong>{copy.noTools}</strong>
          <span>{copy.noToolsHint}</span>
        </div>
      ) : null}

      {toolCount > 0 ? (
        <>
          <div className="mcp-tool-picker">
            <label className="field">
              <span>{copy.server}</span>
              <select value={selectedServer} onChange={(event) => setSelectedServer(event.target.value)} aria-label={copy.server}>
                {servers.map((server) => (
                  <option key={server.name} value={server.name}>
                    {server.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>{copy.tool}</span>
              <select value={selectedTool} onChange={(event) => setSelectedTool(event.target.value)} aria-label={copy.tool}>
                {visibleTools.map((entry) => (
                  <option key={`${entry.server}:${entry.tool}`} value={entry.tool}>
                    {entry.tool}
                  </option>
                ))}
              </select>
            </label>
            <div className="mcp-diagnostics-server-summary">
              <span>
                {copy.auth}: {formatInlineValue(selectedServerStatus?.authStatus)}
              </span>
              <span>
                {copy.resources}: {(selectedServerStatus?.resources ?? []).length}
              </span>
            </div>
          </div>
          <label className="field">
            <span>{copy.arguments}</span>
            <textarea
              rows={4}
              value={argumentsText}
              onChange={(event) => setArgumentsText(event.target.value)}
              aria-label={copy.arguments}
              spellCheck={false}
            />
          </label>
          <div className="mcp-diagnostics-actions">
            <button type="button" className="primary-button compact-button" onClick={() => void handleCall()} disabled={pending}>
              {pending ? copy.calling : copy.call}
            </button>
            <span className="muted">{copy.redacted}</span>
          </div>
        </>
      ) : null}

      {callError ? (
        <p className="error-text" role="alert">
          {callError}
        </p>
      ) : null}

      {lastCall ? (
        <div className="mcp-diagnostics-result" data-testid="mcp-tool-call-result">
          <div>
            <strong>{copy.envelope}</strong>
            {lastCall.envelope.truncated ? <span>{copy.truncated} ({lastCall.envelope.originalLength})</span> : null}
            <pre>{lastCall.envelope.text}</pre>
          </div>
          <div>
            <strong>{copy.result}</strong>
            {lastCall.result.truncated ? <span>{copy.truncated} ({lastCall.result.originalLength})</span> : null}
            <pre>{lastCall.result.text}</pre>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export function flattenMcpTools(status?: McpStatusResponse | null) {
  return (status?.servers ?? []).flatMap((server) =>
    Object.keys(server.tools ?? {})
      .sort((a, b) => a.localeCompare(b))
      .map((tool) => ({ server: server.name, tool, metadata: server.tools[tool] ?? {} })),
  );
}

export function parseArgumentsObject(text: string): { ok: true; value: Record<string, unknown> } | { ok: false } {
  try {
    const parsed = JSON.parse(text || "{}");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return { ok: false };
    return { ok: true, value: parsed as Record<string, unknown> };
  } catch {
    return { ok: false };
  }
}

export function redactSensitive(value: unknown, seen = new WeakSet<object>()): unknown {
  if (!value || typeof value !== "object") return value;
  if (seen.has(value)) return "[circular]";
  seen.add(value);
  if (Array.isArray(value)) return value.map((item) => redactSensitive(item, seen));
  const output: Record<string, unknown> = {};
  for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
    output[key] = /api[_-]?key|authorization|bearer|cookie|password|secret|token/i.test(key)
      ? "[redacted]"
      : redactSensitive(child, seen);
  }
  return output;
}

export function formatJsonForUi(value: unknown, limit = RESULT_PREVIEW_LIMIT) {
  const raw = JSON.stringify(value, null, 2) ?? "null";
  if (raw.length <= limit) {
    return { text: raw, truncated: false, originalLength: raw.length };
  }
  return {
    text: `${raw.slice(0, limit).trimEnd()}\n...`,
    truncated: true,
    originalLength: raw.length,
  };
}

function formatInlineValue(value: unknown) {
  if (typeof value === "string") return value || "-";
  if (value == null) return "-";
  return JSON.stringify(redactSensitive(value));
}
