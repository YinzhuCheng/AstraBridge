import type { CodexKernelProbeSnapshot, LocaleCode } from "../../types";

const LABELS = {
  en: {
    title: "Codex kernel compatibility",
    loading: "Loading kernel compatibility snapshot...",
    unavailable: "Kernel snapshot is unavailable.",
    summaryFallback: "No compatibility summary was reported.",
    binary: "Binary",
    version: "Version",
    isolatedHome: "Isolated home",
    host: "Host",
    transport: "Transport",
    launchMode: "Launch mode",
    compatibility: "Compatibility",
    appServer: "App-server",
    mcp: "MCP",
    plugins: "Plugins",
    skills: "Skills",
    warnings: "Warnings",
    none: "none",
    notDetected: "not detected",
    noWarnings: "No probe warnings.",
  },
  "zh-CN": {
    title: "Codex kernel compatibility",
    loading: "Loading kernel compatibility snapshot...",
    unavailable: "Kernel snapshot is unavailable.",
    summaryFallback: "No compatibility summary was reported.",
    binary: "Binary",
    version: "Version",
    isolatedHome: "Isolated home",
    host: "Host",
    transport: "Transport",
    launchMode: "Launch mode",
    compatibility: "Compatibility",
    appServer: "App-server",
    mcp: "MCP",
    plugins: "Plugins",
    skills: "Skills",
    warnings: "Warnings",
    none: "none",
    notDetected: "not detected",
    noWarnings: "No probe warnings.",
  },
} as const;

export function RuntimeKernelStatusPanel({
  locale,
  snapshot,
  isLoading,
  error,
}: {
  locale: LocaleCode;
  snapshot?: CodexKernelProbeSnapshot | null;
  isLoading: boolean;
  error?: unknown;
}) {
  const copy = LABELS[locale] ?? LABELS.en;
  if (isLoading && !snapshot) {
    return (
      <section className="metadata-section" data-testid="runtime-kernel-status-panel">
        <div className="section-header">
          <h4>{copy.title}</h4>
        </div>
        <p className="muted">{copy.loading}</p>
      </section>
    );
  }

  if (!snapshot) {
    return (
      <section className="metadata-section" data-testid="runtime-kernel-status-panel">
        <div className="section-header">
          <h4>{copy.title}</h4>
        </div>
        {error ? <p className="error-text">{String((error as Error)?.message ?? error)}</p> : null}
        <p className="muted">{copy.unavailable}</p>
      </section>
    );
  }

  const compatibilityStatus = _formatStatus(snapshot.inferred.compatibility_status);
  const appServerStatus = _formatStatus(snapshot.observed.app_server.initialize_status);
  const mcpStatus = _formatStatus(snapshot.observed.mcp_features.server_status_list_status || snapshot.observed.mcp_features.config_render_status);
  const pluginStatus = _formatPluginStatus(snapshot);
  const skillStatus = _formatStatus(snapshot.observed.skill_features.list_status);
  const statusClass = _statusClass(snapshot.inferred.compatibility_status);
  const binaryPath = snapshot.observed.binary.path || copy.notDetected;
  const versionText = snapshot.observed.binary.version_semver || snapshot.observed.binary.version_text || copy.notDetected;
  const isolatedHome = snapshot.observed.runtime_roots.isolated_codex_home || copy.notDetected;
  const warnings = (snapshot.known_warnings || []).filter((item) => String(item || "").trim());

  return (
    <section className="metadata-section" data-testid="runtime-kernel-status-panel">
      <div className="section-header">
        <h4>{copy.title}</h4>
        <span className={`status-tag ${statusClass}`}>{compatibilityStatus}</span>
      </div>
      <p className="muted">{snapshot.inferred.compatibility_summary || copy.summaryFallback}</p>
      {error ? <p className="error-text">{String((error as Error)?.message ?? error)}</p> : null}
      <div className="mcp-health-row">
        <span>{copy.compatibility}: {compatibilityStatus}</span>
        <span>{copy.appServer}: {appServerStatus}</span>
        <span>{copy.mcp}: {mcpStatus}</span>
        <span>{copy.plugins}: {pluginStatus}</span>
        <span>{copy.skills}: {skillStatus}</span>
      </div>
      <div className="env-list">
        <div><span>{copy.binary}</span><strong>{binaryPath}</strong></div>
        <div><span>{copy.version}</span><strong>{versionText}</strong></div>
        <div><span>{copy.isolatedHome}</span><strong>{isolatedHome}</strong></div>
        <div><span>{copy.host}</span><strong>{snapshot.observed.platform.execution_host || copy.none}</strong></div>
        <div><span>{copy.transport}</span><strong>{snapshot.observed.app_server.transport || copy.none}</strong></div>
        <div><span>{copy.launchMode}</span><strong>{snapshot.observed.app_server.launch_mode || copy.none}</strong></div>
      </div>
      <div className="capability-warning-list">
        <p><strong>{copy.warnings}:</strong></p>
        {warnings.length ? warnings.slice(0, 8).map((warning) => <p key={warning}>{warning}</p>) : <p>{copy.noWarnings}</p>}
      </div>
    </section>
  );
}

function _formatStatus(value: string | null | undefined) {
  const text = String(value || "unknown").trim() || "unknown";
  return text.replace(/[\/_]+/g, " ");
}

function _formatPluginStatus(snapshot: CodexKernelProbeSnapshot) {
  const featureState = String(snapshot.observed.plugin_features.config_feature_state || "").trim();
  if (featureState === "disabled_by_app") {
    return _formatStatus(featureState);
  }
  return _formatStatus(snapshot.observed.plugin_features.list_status);
}

function _statusClass(value: string | null | undefined) {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "verified") {
    return "capability-ok";
  }
  if (normalized === "probed" || normalized === "partial" || normalized === "blocked") {
    return "capability-warn";
  }
  return "";
}
