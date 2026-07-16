import { useMemo, useState } from "react";

import { api as defaultApi } from "../../api";
import type {
  AgenticUpdateApplyMode,
  AgenticUpdateJobStatus,
  AgenticUpdateProposalResult,
  AgenticUpdateRunContract,
  AgenticUpdateScope,
  AgenticUpdateStartPayload,
  AgenticUpdateVersionPolicy,
  RouterProvider,
} from "../../types";

type AgenticUpdateReviewApi = {
  start: (payload: AgenticUpdateStartPayload) => Promise<AgenticUpdateJobStatus>;
  result: (jobId?: string | null) => Promise<AgenticUpdateProposalResult>;
};

type AgenticUpdateReviewPanelProps = {
  locale: "en" | "zh-CN";
  providers?: RouterProvider[];
  api?: AgenticUpdateReviewApi;
};

const SCOPE_OPTIONS: Array<{ value: AgenticUpdateScope; label: string; detail: string }> = [
  { value: "provider_metadata", label: "Provider metadata", detail: "Public model catalog, limits, and source status." },
  { value: "provider_adapter", label: "Provider adapter", detail: "Transport habits, request fields, and parser drift." },
  { value: "capability_routes", label: "Capability routes", detail: "Tool, vision, web, MCP, and route compatibility." },
  { value: "codex_kernel", label: "Codex kernel", detail: "Bundled runtime and kernel candidate discovery." },
  { value: "plugin_skill_surface", label: "Plugin and skill surface", detail: "Skill contracts and plugin discovery boundaries." },
  { value: "docs_only", label: "Docs only", detail: "Documentation and evidence refresh without code changes." },
];

const VERSION_POLICIES: Array<{ value: AgenticUpdateVersionPolicy; label: string }> = [
  { value: "stable", label: "Stable" },
  { value: "latest", label: "Latest" },
  { value: "pinned", label: "Pinned version" },
  { value: "deprecated_check", label: "Deprecation check" },
  { value: "security_fix_only", label: "Security fix only" },
];

const APPLY_MODES: Array<{ value: AgenticUpdateApplyMode; label: string; disabled?: boolean }> = [
  { value: "proposal_only", label: "Proposal only" },
  { value: "discover_only", label: "Discovery only" },
  { value: "isolated_apply", label: "Isolated apply", disabled: true },
  { value: "verify_candidate", label: "Verify candidate", disabled: true },
  { value: "promote_after_smoke", label: "Promote after smoke", disabled: true },
];

function stringValue(source: Record<string, unknown> | undefined | null, keys: string[], fallback = "") {
  if (!source) return fallback;
  for (const key of keys) {
    const value = source[key];
    if (typeof value === "string" && value.trim()) return value;
    if (typeof value === "number" || typeof value === "boolean") return String(value);
  }
  return fallback;
}

function displayText(value: unknown, fallback = "-") {
  if (value === null || value === undefined) return fallback;
  const raw = typeof value === "string" ? value : typeof value === "number" || typeof value === "boolean" ? String(value) : fallback;
  return redactDisplayText(raw);
}

function redactDisplayText(value: string) {
  const trimmed = value.replace(/\s+/g, " ").trim();
  const redacted = trimmed
    .replace(/authorization\s*:\s*[^,\s]+/gi, "authorization: [redacted]")
    .replace(/bearer\s+[a-z0-9._~+/=-]{10,}/gi, "bearer [redacted]")
    .replace(/(api[_-]?key\s*[:=]\s*)[^,\s&]+/gi, "$1[redacted]")
    .replace(/(token\s*[:=]\s*)[^,\s&]+/gi, "$1[redacted]")
    .replace(/sk-[a-z0-9]{12,}/gi, "sk-[redacted]");
  return redacted.length > 180 ? `${redacted.slice(0, 177)}...` : redacted;
}

function artifactHref(path: string) {
  const normalized = path.trim();
  if (/^[A-Za-z]:[\\/]/.test(normalized)) {
    return `file:///${normalized.replace(/\\/g, "/")}`;
  }
  if (normalized.startsWith("/")) {
    return `file://${normalized}`;
  }
  return "";
}

function sourceRows(result: AgenticUpdateProposalResult | null) {
  const sources =
    result?.proposal?.discovery_result?.sources ??
    result?.discovery?.sources ??
    [];
  return sources.slice(0, 6).map((source, index) => ({
    id: displayText(
      stringValue(source, ["source_id", "id", "provider_id", "url", "source_url"], `source-${index + 1}`),
    ),
    trust: displayText(stringValue(source, ["trust_label", "trust", "classification", "source_status"], "unclassified")),
    status: displayText(stringValue(source, ["status", "source_status", "http_status", "fetch_status"], "recorded")),
    location: displayText(stringValue(source, ["url", "source_url", "normalized_url", "domain"], "")),
    hash: displayText(stringValue(source, ["content_hash", "sha256", "hash"], "")),
  }));
}

function changeRows(result: AgenticUpdateProposalResult | null) {
  const changes = result?.proposal?.diff?.changes ?? result?.diff?.changes ?? [];
  return changes.slice(0, 8).map((change, index) => ({
    id: displayText(stringValue(change, ["change_id", "id", "target", "path"], `change-${index + 1}`)),
    action: displayText(stringValue(change, ["action", "kind", "operation"], "proposed")),
    summary: displayText(stringValue(change, ["summary", "description", "reason"], "Review proposed change.")),
    risk: displayText(stringValue(change, ["risk_class", "risk"], "")),
  }));
}

function validationRows(result: AgenticUpdateProposalResult | null) {
  const proposal = result?.proposal;
  const gates = proposal?.validation_result?.gates ?? [];
  if (gates.length > 0) {
    return gates.slice(0, 8).map((gate, index) => ({
      id: displayText(stringValue(gate, ["gate_id", "id", "name", "command"], `gate-${index + 1}`)),
      status: displayText(stringValue(gate, ["status", "result"], "required")),
    }));
  }
  const warnings = [
    ...(proposal?.validation_result?.warnings ?? []),
    ...(proposal?.apply_manifest?.warnings ?? []),
    ...(proposal?.rollback_manifest?.warnings ?? []),
  ];
  const uniqueWarnings = [...new Set(warnings.map((item) => displayText(item)).filter(Boolean))];
  const rows = uniqueWarnings.slice(0, 8).map((item, index) => ({ id: item, status: index === 0 ? "required" : "not run" }));
  return rows.length ? rows : [{ id: "Manual review required before apply.", status: "required" }];
}

function artifactRows(result: AgenticUpdateProposalResult | null) {
  const paths = {
    ...(result?.artifact_paths ?? {}),
    ...(result?.proposal?.diff?.artifact_paths ?? {}),
  };
  return Object.entries(paths)
    .filter((entry): entry is [string, string] => typeof entry[1] === "string" && Boolean(entry[1].trim()))
    .slice(0, 10)
    .map(([key, value]) => ({ key: displayText(key), path: displayText(value), href: artifactHref(value) }));
}

export function AgenticUpdateReviewPanel({
  locale,
  providers = [],
  api = {
    start: defaultApi.agenticUpdateStart,
    result: defaultApi.agenticUpdateResult,
  },
}: AgenticUpdateReviewPanelProps) {
  const [selectedScopes, setSelectedScopes] = useState<AgenticUpdateScope[]>(["provider_metadata"]);
  const [providerId, setProviderId] = useState("");
  const [versionPolicy, setVersionPolicy] = useState<AgenticUpdateVersionPolicy>("stable");
  const [targetVersion, setTargetVersion] = useState("");
  const [applyMode, setApplyMode] = useState<AgenticUpdateApplyMode>("proposal_only");
  const [allowNetwork, setAllowNetwork] = useState(true);
  const [jobStatus, setJobStatus] = useState<AgenticUpdateJobStatus | null>(null);
  const [result, setResult] = useState<AgenticUpdateProposalResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const selectedProviderLabel = useMemo(() => {
    if (!providerId) return "All configured providers";
    return providers.find((provider) => provider.id === providerId)?.display_name || providerId;
  }, [providerId, providers]);

  const canGenerate = selectedScopes.length > 0 && (versionPolicy !== "pinned" || Boolean(targetVersion.trim())) && !busy;
  const summary = result?.summary ?? {};
  const riskClass = displayText(summary.risk_class ?? result?.proposal?.diff?.risk_class ?? "unclassified");
  const changeCount = displayText(summary.change_count ?? changeRows(result).length);
  const proposalStatus = displayText(summary.proposal_status ?? result?.proposal?.diff?.status ?? jobStatus?.status ?? "idle");
  const sourceList = sourceRows(result);
  const changes = changeRows(result);
  const validations = validationRows(result);
  const artifacts = artifactRows(result);

  function toggleScope(scope: AgenticUpdateScope) {
    setSelectedScopes((current) =>
      current.includes(scope) ? current.filter((item) => item !== scope) : [...current, scope],
    );
  }

  function buildRunContract(): AgenticUpdateRunContract {
    return {
      scope: selectedScopes,
      providers: providerId ? [providerId] : [],
      models: [],
      version_policy: versionPolicy,
      target_version: versionPolicy === "pinned" ? targetVersion.trim() : null,
      apply_mode: applyMode,
      allow_network: allowNetwork,
      allow_provider_calls: false,
      allow_install: false,
      allow_code_changes: false,
      approval_policy: "manual_review_required",
    };
  }

  async function requestProposal() {
    if (!canGenerate) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const status = await api.start({ run_contract: buildRunContract() });
      setJobStatus(status);
      if (status.status === "failed") {
        setError(status.error || "Proposal request failed.");
        return;
      }
      const proposalResult = await api.result(status.job_id);
      setResult(proposalResult);
    } catch (requestError) {
      setError(`Proposal request failed: ${String((requestError as Error).message ?? requestError)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="manager-panel agentic-update-panel" data-testid="agentic-update-review-panel">
      <div className="manager-hero">
        <div>
          <span className="eyebrow">Agentic updates</span>
          <h3>{locale === "zh-CN" ? "自动更新提案审查" : "Update proposal review"}</h3>
          <p className="muted">
            Choose the update boundary, generate a proposal, and inspect trust, risk, validation, and artifacts before any apply step exists.
          </p>
        </div>
        <span className="session-badge">{proposalStatus}</span>
      </div>

      <div className="manager-grid agentic-update-grid">
        <section className="manager-section">
          <h4>Update scope</h4>
          <div className="agentic-update-scope-grid" role="group" aria-label="Update scope">
            {SCOPE_OPTIONS.map((scope) => (
              <label className="agentic-update-scope" key={scope.value}>
                <input
                  type="checkbox"
                  checked={selectedScopes.includes(scope.value)}
                  onChange={() => toggleScope(scope.value)}
                />
                <span>
                  <strong>{scope.label}</strong>
                  <small>{scope.detail}</small>
                </span>
              </label>
            ))}
          </div>
          {selectedScopes.length === 0 ? <p className="error-text">Select at least one update scope.</p> : null}
        </section>

        <section className="manager-section">
          <h4>Proposal boundary</h4>
          <label className="field">
            <span>Provider</span>
            {providers.length > 0 ? (
              <select data-testid="agentic-update-provider" value={providerId} onChange={(event) => setProviderId(event.target.value)}>
                <option value="">All configured providers</option>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>{provider.display_name || provider.id}</option>
                ))}
              </select>
            ) : (
              <input value={providerId} onChange={(event) => setProviderId(event.target.value)} placeholder="Provider id or blank for all" />
            )}
          </label>
          <label className="field">
            <span>Version policy</span>
            <select
              data-testid="agentic-update-version-policy"
              value={versionPolicy}
              onChange={(event) => setVersionPolicy(event.target.value as AgenticUpdateVersionPolicy)}
            >
              {VERSION_POLICIES.map((policy) => <option key={policy.value} value={policy.value}>{policy.label}</option>)}
            </select>
          </label>
          <label className="field">
            <span>Target version</span>
            <input
              data-testid="agentic-update-target-version"
              value={targetVersion}
              disabled={versionPolicy !== "pinned"}
              onChange={(event) => setTargetVersion(event.target.value)}
              placeholder={versionPolicy === "pinned" ? "Required for pinned updates" : "Only used with pinned policy"}
            />
          </label>
          <label className="field">
            <span>Apply mode</span>
            <select
              data-testid="agentic-update-apply-mode"
              value={applyMode}
              onChange={(event) => setApplyMode(event.target.value as AgenticUpdateApplyMode)}
            >
              {APPLY_MODES.map((mode) => <option key={mode.value} value={mode.value} disabled={mode.disabled}>{mode.label}</option>)}
            </select>
          </label>
          <label className="check-row agentic-update-network">
            <input type="checkbox" checked={allowNetwork} onChange={(event) => setAllowNetwork(event.target.checked)} />
            <span>Allow public documentation fetches</span>
          </label>
          <div className="field-row">
            <button type="button" className="primary-button" onClick={requestProposal} disabled={!canGenerate}>
              {busy ? "Generating..." : "Generate proposal"}
            </button>
            <button type="button" className="ghost-button" onClick={() => { setResult(null); setJobStatus(null); setError(""); }} disabled={busy}>
              Clear
            </button>
          </div>
          {versionPolicy === "pinned" && !targetVersion.trim() ? <p className="error-text">Pinned updates require a target version.</p> : null}
          {error ? <p className="error-text" role="alert">{error}</p> : null}
        </section>
      </div>

      <section className="metadata-actions metadata-actions-compact agentic-update-summary">
        <div>
          <span className="eyebrow">Proposal summary</span>
          <h3>{result?.run_id || jobStatus?.run_id || "No proposal generated"}</h3>
          <p className="muted">Scope: {selectedScopes.join(", ") || "none"} / Provider: {selectedProviderLabel}</p>
        </div>
        <div className="agentic-update-summary-strip" aria-label="Proposal summary">
          <span className="status-tag">{riskClass}</span>
          <span className="status-tag">{changeCount} changes</span>
          <span className="status-tag">{displayText(result?.run_contract.apply_mode ?? applyMode)}</span>
        </div>
      </section>

      {result ? (
        <div className="manager-grid agentic-update-grid">
          <section className="manager-section">
            <h4>Source trust</h4>
            <div className="manager-list">
              {sourceList.map((source) => (
                <div className="manager-row" key={`${source.id}-${source.hash}`}>
                  <span>
                    <strong>{source.id}</strong>
                    <small>{source.status} / {source.trust}</small>
                    {source.location ? <small>{source.location}</small> : null}
                  </span>
                  {source.hash ? <code>{source.hash}</code> : null}
                </div>
              ))}
              {sourceList.length === 0 ? <p className="muted">No source records were included in this proposal.</p> : null}
            </div>
          </section>

          <section className="manager-section">
            <h4>Risk and changes</h4>
            <div className="manager-list">
              {changes.map((change) => (
                <div className="manager-row" key={`${change.id}-${change.action}`}>
                  <span>
                    <strong>{change.id}</strong>
                    <small>{change.action}{change.risk ? ` / ${change.risk}` : ""}</small>
                  </span>
                  <code>{change.summary}</code>
                </div>
              ))}
              {changes.length === 0 ? <p className="muted">No concrete change rows were proposed.</p> : null}
            </div>
          </section>

          <section className="manager-section">
            <h4>Validation requirements</h4>
            <div className="manager-list">
              {validations.map((validation) => (
                <div className="manager-row" key={`${validation.id}-${validation.status}`}>
                  <span>
                    <strong>{validation.id}</strong>
                    <small>{validation.status}</small>
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="manager-section">
            <h4>Artifacts</h4>
            <div className="manager-list">
              {artifacts.map((artifact) => (
                <div className="manager-row" key={`${artifact.key}-${artifact.path}`}>
                  <span>
                    <strong>{artifact.key}</strong>
                    {artifact.href ? (
                      <a href={artifact.href} target="_blank" rel="noreferrer">{artifact.path}</a>
                    ) : (
                      <code>{artifact.path}</code>
                    )}
                  </span>
                </div>
              ))}
              {artifacts.length === 0 ? <p className="muted">No artifact paths are available yet.</p> : null}
            </div>
          </section>
        </div>
      ) : (
        <section className="manager-section agentic-update-empty">
          <h4>Review state</h4>
          <p className="muted">Generate a proposal to inspect source trust, risk, validation gates, and artifact paths.</p>
        </section>
      )}

      <section className="manager-section agentic-update-guardrail">
        <div className="metadata-detail-header">
          <div>
            <span className="eyebrow">Guardrails</span>
            <h3>Unsafe actions stay locked</h3>
            <p className="muted">Proposal review never sends provider smoke calls, installs candidates, or applies workspace changes.</p>
          </div>
        </div>
        <div className="field-row">
          <button type="button" className="ghost-button" data-testid="agentic-update-apply" disabled title="Apply requires a future isolated apply step and explicit approval.">Apply proposal</button>
          <button type="button" className="ghost-button" data-testid="agentic-update-provider-smoke" disabled title="Provider calls are disabled in proposal review.">Run provider smoke</button>
          <button type="button" className="ghost-button" data-testid="agentic-update-install" disabled title="Installs are disabled in proposal review.">Install candidate</button>
        </div>
      </section>
    </div>
  );
}
