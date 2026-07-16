import { useState, type Dispatch, type SetStateAction } from "react";

import { t } from "../i18n/catalog";
import type {
  CapabilityManagementEntry,
  CapabilityArtifactEntry,
  CapabilityMcpPresetStatus,
  CapabilityRouteCandidate,
  CapabilityRouteEntry,
  CapabilitySmokeResult,
  CodexPluginRegistryRecord,
  CodexPluginSkillRegistrySnapshot,
  CodexSkillRegistryRecord,
  LocaleCode,
} from "../../types";

export type CapabilityRouteDraft = {
  mode: "auto" | "pinned";
  provider_id?: string | null;
  model?: string | null;
};

export type CapabilityProviderCredentialStatus = {
  provider_id: string;
  label: string;
  enabled: boolean;
  auth_mode: string;
  env_key?: string | null;
  status: "configured" | "missing" | "check_environment" | "session_required" | "disabled";
};

type CapabilityRuntimeToolingGuide =
  | {
      kind: "plugin";
      plugin_id: string;
      fallback_label: string;
      summary_key: string;
    }
  | {
      kind: "skill";
      skill_name: string;
      fallback_label: string;
      summary_key: string;
    };

type ResolvedCapabilityRuntimeTooling =
  | {
      kind: "plugin";
      reference: string;
      label: string;
      summary_key: string;
      state: "available" | "disabled" | "missing";
      detail: string | null;
    }
  | {
      kind: "skill";
      reference: string;
      label: string;
      summary_key: string;
      state: "enabled" | "disabled" | "missing";
      detail: string | null;
    };

const CAPABILITY_RUNTIME_TOOLING_GUIDANCE: Record<string, CapabilityRuntimeToolingGuide[]> = {
  "vision.analyze": [
    {
      kind: "plugin",
      plugin_id: "browser",
      fallback_label: "Browser",
      summary_key: "manager_capability_plugin_browser_summary",
    },
  ],
  "image.generate": [
    {
      kind: "skill",
      skill_name: "imagegen",
      fallback_label: "imagegen",
      summary_key: "manager_capability_skill_imagegen_summary",
    },
  ],
  "speech.transcribe": [
    {
      kind: "plugin",
      plugin_id: "openai-primary-runtime",
      fallback_label: "OpenAI Primary Runtime",
      summary_key: "manager_capability_plugin_primary_runtime_summary",
    },
  ],
  "speech.synthesize": [
    {
      kind: "plugin",
      plugin_id: "openai-primary-runtime",
      fallback_label: "OpenAI Primary Runtime",
      summary_key: "manager_capability_plugin_primary_runtime_audio_summary",
    },
  ],
};

const CAPABILITY_DISPLAY_NAME_KEYS: Record<string, string> = {
  "image.generate": "manager_capability_name_image_generate",
  "speech.synthesize": "manager_capability_name_speech_synthesize",
  "speech.transcribe": "manager_capability_name_speech_transcribe",
  "vision.analyze": "manager_capability_name_vision_analyze",
  "web.search": "manager_capability_name_web_search",
};

const CAPABILITY_LANE_KEYS: Record<string, string> = {
  model_backed: "manager_capability_lane_model_backed",
  web_standalone: "manager_capability_lane_web_standalone",
};

const CAPABILITY_TRANSPORT_KEYS: Record<string, string> = {
  request_response: "manager_capability_transport_request_response",
  stream_sse: "manager_capability_transport_stream_sse",
  realtime_ws: "manager_capability_transport_realtime_ws",
};

const CAPABILITY_STATUS_KEYS: Record<string, string> = {
  ok: "manager_capability_status_ok",
  standalone: "manager_capability_status_standalone",
  unknown: "manager_capability_status_unknown",
  untested: "manager_capability_status_untested",
  pass: "manager_capability_status_pass",
  warn: "manager_capability_status_warn",
  fail: "manager_capability_status_fail",
  provider_not_run: "manager_capability_status_provider_not_run",
  skipped: "manager_capability_status_skipped",
  no_capability_candidate: "manager_capability_status_no_candidate",
  missing: "manager_capability_status_missing",
  session_required: "manager_capability_status_session_required",
  disabled: "manager_capability_status_disabled",
};

const CAPABILITY_SMOKE_MODE_KEYS: Record<string, string> = {
  dry_run: "manager_capability_smoke_mode_dry_run",
  provider: "manager_capability_smoke_mode_provider",
};

type CapabilitySurfaceStatus = "verified" | "partial" | "failed" | "unverified" | "unsupported" | "standalone";

const CAPABILITY_SURFACE_STATUS_KEYS: Record<CapabilitySurfaceStatus, string> = {
  verified: "manager_capability_surface_verified",
  partial: "manager_capability_surface_partial",
  failed: "manager_capability_surface_failed",
  unverified: "manager_capability_surface_unverified",
  unsupported: "manager_capability_surface_unsupported",
  standalone: "manager_capability_status_standalone",
};

function smokeProviderError(result: CapabilitySmokeResult | undefined): string {
  const value = result?.sanitized_response?.provider_error;
  return typeof value === "string" ? value.trim() : "";
}

function smokeElapsedMs(result: CapabilitySmokeResult | undefined): number | null {
  const value = result?.sanitized_response?.elapsed_ms;
  return typeof value === "number" && Number.isFinite(value) ? Math.max(0, Math.round(value)) : null;
}

function smokeSummary(locale: LocaleCode, result: CapabilitySmokeResult | null): string {
  if (!result) {
    return t(locale, "manager_capability_not_run");
  }
  const mode = localizedEnum(locale, result.mode, CAPABILITY_SMOKE_MODE_KEYS);
  const status = localizedEnum(locale, result.status, CAPABILITY_STATUS_KEYS);
  const elapsed = smokeElapsedMs(result);
  const providerState = result.provider_invoked ? t(locale, "manager_capability_provider_invoked_yes") : t(locale, "manager_capability_provider_invoked_no");
  const parts = [`${mode} · ${status}`, result.case_id, providerState];
  if (elapsed !== null) {
    parts.push(`${t(locale, "manager_capability_elapsed")} ${elapsed} ms`);
  }
  return parts.join(" / ");
}

const CAPABILITY_ARTIFACT_POLICY_KEYS: Record<string, string> = {
  none: "manager_capability_artifact_policy_none",
  unknown: "manager_capability_artifact_policy_unknown",
  no_local_artifacts: "manager_capability_artifact_policy_none",
  persist_research_record: "manager_capability_artifact_policy_research_record",
  persist_generated_assets: "manager_capability_artifact_policy_generated_assets",
  persist_optional_visual_artifacts: "manager_capability_artifact_policy_visual_artifacts",
  persist_audio_request_and_transcript: "manager_capability_artifact_policy_audio_request",
  persist_audio_output_and_text_sidecar: "manager_capability_artifact_policy_audio_output",
  persist_optional_audio_artifacts: "manager_capability_artifact_policy_audio_output",
};

const CAPABILITY_MODALITY_KEYS: Record<string, string> = {
  text: "manager_capability_modality_text",
  image: "manager_capability_modality_image",
  audio: "manager_capability_modality_audio",
  video: "manager_capability_modality_video",
};

type CapabilityDiagnosticTone = "ok" | "warning" | "info";

type CapabilityDiagnostic = {
  key: string;
  label: string;
  tone: CapabilityDiagnosticTone;
};

type CapabilityRoutesPanelProps = {
  locale: LocaleCode;
  routes: CapabilityRouteEntry[];
  managementEntries: CapabilityManagementEntry[];
  mcpPreset: CapabilityMcpPresetStatus | null;
  pluginSkillRegistry: CodexPluginSkillRegistrySnapshot | null;
  pluginSkillRegistryLoading: boolean;
  pluginSkillRegistryError: boolean;
  drafts: Record<string, CapabilityRouteDraft>;
  setDrafts: Dispatch<SetStateAction<Record<string, CapabilityRouteDraft>>>;
  isLoading: boolean;
  isError: boolean;
  isSaving: boolean;
  smokeResults: Record<string, CapabilitySmokeResult>;
  smokePendingCapabilityId: string | null;
  isSmokePending: boolean;
  artifacts: CapabilityArtifactEntry[];
  artifactsLoading: boolean;
  artifactsError: boolean;
  providerCredentials: Record<string, CapabilityProviderCredentialStatus>;
  mcpRuntimeVisible: boolean | null;
  mcpRuntimeToolCount: number;
  mcpVisibilityLoading: boolean;
  mcpVisibilityError: boolean;
  isInstallingMcpPreset: boolean;
  toMediaSrc: (path: string) => string;
  onInstallMcpPreset: () => void;
  onSave: (route: CapabilityRouteEntry, draft: CapabilityRouteDraft) => void;
  onRunSmoke: (capabilityId: string) => void;
  onRunProviderSmoke: (capabilityId: string) => void;
};

function localizedCapabilityName(locale: LocaleCode, route: Pick<CapabilityRouteEntry, "capability_id" | "display_name">) {
  const key = CAPABILITY_DISPLAY_NAME_KEYS[route.capability_id];
  return key ? t(locale, key) : route.display_name;
}

function localizedEnum(locale: LocaleCode, value: string | null | undefined, keys: Record<string, string>) {
  const normalized = value || "unknown";
  const key = keys[normalized];
  return key ? t(locale, key) : normalized;
}

function providerSmokeSkipReason(
  locale: LocaleCode,
  route: CapabilityRouteEntry,
  credential: CapabilityProviderCredentialStatus | null,
  authorized: boolean,
): string {
  if (!route.resolved_candidate?.provider_id) {
    return t(locale, "manager_capability_provider_smoke_skip_no_route");
  }
  if (!credential) {
    return t(locale, "manager_capability_provider_smoke_skip_no_credential");
  }
  if (!credential.enabled || credential.status === "disabled") {
    return t(locale, "manager_capability_provider_smoke_skip_disabled");
  }
  if (credential.status === "missing") {
    return t(locale, "manager_capability_provider_smoke_skip_missing");
  }
  if (credential.status === "session_required") {
    return t(locale, "manager_capability_provider_smoke_skip_session");
  }
  if (!authorized) {
    return t(locale, "manager_capability_provider_smoke_skip_unauthorized");
  }
  return "";
}

function localizedModalities(locale: LocaleCode, modalities: string[] | null | undefined) {
  const values = modalities && modalities.length > 0 ? modalities : ["text"];
  return values.map((value) => localizedEnum(locale, value, CAPABILITY_MODALITY_KEYS)).join(", ");
}

function effectiveSmokeStatus(management: CapabilityManagementEntry | undefined, smokeResult: CapabilitySmokeResult | null): string {
  return smokeResult?.status ?? management?.smoke.status ?? "unknown";
}

function sameCandidate(
  left: Pick<CapabilityRouteCandidate, "provider_id" | "model" | "adapter_id"> | null | undefined,
  right: Pick<CapabilityRouteCandidate, "provider_id" | "model" | "adapter_id"> | null | undefined,
) {
  return (
    Boolean(left && right) &&
    (left?.provider_id ?? null) === (right?.provider_id ?? null) &&
    (left?.model ?? null) === (right?.model ?? null) &&
    (left?.adapter_id ?? null) === (right?.adapter_id ?? null)
  );
}

function routeSurfaceStatus(
  route: CapabilityRouteEntry,
  management: CapabilityManagementEntry | undefined,
  smokeResult: CapabilitySmokeResult | null,
): CapabilitySurfaceStatus {
  if (route.lane_type === "web_standalone") {
    return "standalone";
  }
  if (!route.resolved_candidate || route.resolution_status === "no_capability_candidate") {
    return "unsupported";
  }
  const smokeStatus = effectiveSmokeStatus(management, smokeResult);
  if (smokeStatus === "pass") {
    return "verified";
  }
  if (smokeStatus === "warn") {
    return "partial";
  }
  if (smokeStatus === "fail") {
    return "failed";
  }
  return "unverified";
}

function candidateSurfaceStatus(
  candidate: CapabilityRouteCandidate,
  route: CapabilityRouteEntry,
  management: CapabilityManagementEntry | undefined,
  smokeResult: CapabilitySmokeResult | null,
): CapabilitySurfaceStatus {
  if (!candidate.provider_id || !candidate.model) {
    return "unsupported";
  }
  if (sameCandidate(candidate, route.resolved_candidate ?? null)) {
    return routeSurfaceStatus(route, management, smokeResult);
  }
  return "unverified";
}

function capabilitySurfaceToneClass(status: CapabilitySurfaceStatus) {
  if (status === "verified" || status === "standalone") {
    return "capability-ok";
  }
  if (status === "partial") {
    return "status-tag-warning";
  }
  return "capability-warn";
}

function candidateStatusNote(
  locale: LocaleCode,
  candidate: CapabilityRouteCandidate,
  status: CapabilitySurfaceStatus,
): string {
  if (status === "verified") {
    return t(locale, "manager_capability_candidate_note_verified");
  }
  if (status === "partial") {
    return t(locale, "manager_capability_candidate_note_partial");
  }
  if (status === "failed") {
    return t(locale, "manager_capability_candidate_note_failed");
  }
  if (candidate.catalog_present === false) {
    return t(locale, "manager_capability_candidate_note_catalog_missing");
  }
  return t(locale, "manager_capability_candidate_note_unverified");
}

function routeDiagnostics(
  locale: LocaleCode,
  route: CapabilityRouteEntry,
  management: CapabilityManagementEntry | undefined,
  smokeResult: CapabilitySmokeResult | null,
  credential: CapabilityProviderCredentialStatus | null,
): CapabilityDiagnostic[] {
  const diagnostics: CapabilityDiagnostic[] = [];
  const isStandalone = route.lane_type === "web_standalone";
  const smokeStatus = effectiveSmokeStatus(management, smokeResult);

  if (isStandalone) {
    diagnostics.push({
      key: "web-standalone",
      label: t(locale, "manager_capability_diagnostic_web_standalone"),
      tone: "info",
    });
    return diagnostics;
  }

  if (!route.resolved_candidate?.provider_id) {
    diagnostics.push({
      key: "no-route",
      label: t(locale, "manager_capability_diagnostic_no_route"),
      tone: "warning",
    });
  }

  if (
    !credential ||
    !credential.enabled ||
    credential.status === "missing" ||
    credential.status === "session_required" ||
    credential.status === "disabled"
  ) {
    diagnostics.push({
      key: "credential",
      label: t(locale, "manager_capability_diagnostic_credential"),
      tone: "warning",
    });
  }

  if (smokeStatus === "fail") {
    diagnostics.push({
      key: "smoke-fail",
      label: t(locale, "manager_capability_diagnostic_smoke_failed"),
      tone: "warning",
    });
  } else if (smokeStatus === "warn") {
    diagnostics.push({
      key: "smoke-partial",
      label: t(locale, "manager_capability_diagnostic_smoke_partial"),
      tone: "warning",
    });
  } else if (smokeStatus !== "pass") {
    diagnostics.push({
      key: "smoke-untested",
      label: t(locale, "manager_capability_diagnostic_smoke_not_verified"),
      tone: "warning",
    });
  }

  if (route.resolved_candidate && route.resolved_candidate.catalog_present === false) {
    diagnostics.push({
      key: "catalog-missing",
      label: t(locale, "manager_capability_diagnostic_catalog_missing"),
      tone: "info",
    });
  }

  if (diagnostics.length === 0) {
    diagnostics.push({
      key: "ok",
      label: t(locale, "manager_capability_diagnostic_no_warnings"),
      tone: "ok",
    });
  }

  return diagnostics;
}

export function CapabilityRoutesPanel({
  locale,
  routes,
  managementEntries,
  mcpPreset,
  pluginSkillRegistry,
  pluginSkillRegistryLoading,
  pluginSkillRegistryError,
  drafts,
  setDrafts,
  isLoading,
  isError,
  isSaving,
  smokeResults,
  smokePendingCapabilityId,
  isSmokePending,
  artifacts,
  artifactsLoading,
  artifactsError,
  providerCredentials,
  mcpRuntimeVisible,
  mcpRuntimeToolCount,
  mcpVisibilityLoading,
  mcpVisibilityError,
  isInstallingMcpPreset,
  toMediaSrc,
  onInstallMcpPreset,
  onSave,
  onRunSmoke,
  onRunProviderSmoke,
}: CapabilityRoutesPanelProps) {
  const [providerSmokeAuthorizations, setProviderSmokeAuthorizations] = useState<Record<string, boolean>>({});
  const managementById = new Map(managementEntries.map((entry) => [entry.capability_id, entry]));
  const pluginRegistryById = new Map(pluginSkillRegistry?.plugins.map((item) => [item.plugin_id, item]) ?? []);
  const skillRegistryByName = new Map(pluginSkillRegistry?.skills.map((item) => [item.skill_name, item]) ?? []);
  const showPluginSkillLoading = pluginSkillRegistryLoading && !pluginSkillRegistry;
  const showPluginSkillError = pluginSkillRegistryError && !pluginSkillRegistry;
  const configuredToolCount = mcpPreset?.configured_tool_count ?? mcpPreset?.tool_names.length ?? 0;
  const expectedToolCount = mcpPreset?.expected_tool_names?.length ?? configuredToolCount;
  const missingToolCount = mcpPreset?.missing_tool_names?.length ?? 0;
  const mcpHealthLabel =
    !mcpPreset?.configured
      ? t(locale, "manager_capability_missing")
      : !mcpPreset.enabled
        ? t(locale, "manager_capability_mcp_disabled")
        : mcpPreset.health_status === "partial" || missingToolCount > 0
          ? t(locale, "manager_capability_mcp_partial")
          : t(locale, "manager_capability_configured");
  const runtimeLabel = mcpVisibilityLoading
    ? t(locale, "manager_capability_mcp_runtime_checking")
    : mcpVisibilityError
      ? mcpPreset?.configured && configuredToolCount > 0
        ? t(locale, "manager_capability_mcp_runtime_pending")
        : t(locale, "manager_capability_mcp_runtime_error")
      : mcpRuntimeVisible === true
        ? t(locale, "manager_capability_mcp_runtime_visible")
        : mcpRuntimeVisible === false
          ? t(locale, "manager_capability_mcp_runtime_hidden")
          : t(locale, "manager_capability_mcp_runtime_unchecked");
  const artifactsByCapability = new Map<string, CapabilityArtifactEntry[]>();
  for (const artifact of artifacts) {
    const current = artifactsByCapability.get(artifact.capability_id) ?? [];
    current.push(artifact);
    artifactsByCapability.set(artifact.capability_id, current);
  }
  const diagnosticsByCapability = new Map<string, CapabilityDiagnostic[]>();
  let resolvedRouteCount = 0;
  let verifiedModelSmokeCount = 0;
  let modelBackedRouteCount = 0;
  let warningDiagnosticCount = 0;
  let standaloneWebReady = false;
  for (const route of routes) {
    const management = managementById.get(route.capability_id);
    const smokeResult = smokeResults[route.capability_id] ?? null;
    const resolvedCredential = route.resolved_candidate?.provider_id
      ? providerCredentials[route.resolved_candidate.provider_id] ?? null
      : null;
    const diagnostics = routeDiagnostics(locale, route, management, smokeResult, resolvedCredential);
    diagnosticsByCapability.set(route.capability_id, diagnostics);
    if (route.resolved_candidate) {
      resolvedRouteCount += 1;
    }
    if (route.lane_type === "web_standalone" && route.resolution_status === "standalone") {
      standaloneWebReady = true;
    }
    if (route.lane_type !== "web_standalone") {
      modelBackedRouteCount += 1;
      if (routeSurfaceStatus(route, management, smokeResult) === "verified") {
        verifiedModelSmokeCount += 1;
      }
    }
    warningDiagnosticCount += diagnostics.filter((item) => item.tone === "warning").length;
  }
  return (
    <div className="manager-section">
      <div className="metadata-actions metadata-actions-compact">
        <div>
          <h4>{t(locale, "manager_capabilities_title")}</h4>
          <p className="muted compact-copy">{t(locale, "manager_capabilities_summary")}</p>
        </div>
        <div className="capability-status-strip" aria-label={t(locale, "manager_capability_status_summary")}>
          <span className={`session-badge ${mcpPreset?.configured ? "capability-ok" : "capability-warn"}`}>
            {t(locale, "manager_capability_mcp_preset")}: {mcpHealthLabel}
          </span>
          <span className={`session-badge ${mcpRuntimeVisible ? "capability-ok" : mcpRuntimeVisible === false || mcpVisibilityError ? "capability-warn" : ""}`}>
            {t(locale, "manager_capability_mcp_runtime")}: {runtimeLabel}
          </span>
          <span className={`session-badge ${missingToolCount === 0 && configuredToolCount > 0 ? "capability-ok" : "capability-warn"}`}>
            {t(locale, "manager_capability_mcp_tools")}: {configuredToolCount}/{expectedToolCount}
            {mcpRuntimeVisible ? ` (${mcpRuntimeToolCount} ${t(locale, "manager_capability_mcp_runtime_tools")})` : ""}
          </span>
          <span className="session-badge">
            {t(locale, "manager_capability_routes_count")}: {routes.length}
          </span>
          <button type="button" className="ghost-button compact-button" disabled={isInstallingMcpPreset} onClick={onInstallMcpPreset}>
            {isInstallingMcpPreset ? t(locale, "manager_capability_mcp_installing") : t(locale, "manager_capability_mcp_install")}
          </button>
        </div>
      </div>
      {missingToolCount > 0 ? (
        <p className="muted compact-copy capability-mcp-warning">
          {t(locale, "manager_capability_mcp_missing_tools")}: {(mcpPreset?.missing_tool_names ?? []).join(", ")}
        </p>
      ) : null}
      <div className="capability-observability-panel" aria-label={t(locale, "manager_capability_observability_title")}>
        <div>
          <strong>{t(locale, "manager_capability_observability_title")}</strong>
          <p className="muted compact-copy">{t(locale, "manager_capability_observability_summary")}</p>
        </div>
        <div className="capability-observability-grid">
          <span className="capability-observability-metric">
            <strong>{resolvedRouteCount}/{routes.length}</strong>
            <small>{t(locale, "manager_capability_observability_routes_ready")}</small>
          </span>
          <span className="capability-observability-metric">
            <strong>{verifiedModelSmokeCount}/{modelBackedRouteCount}</strong>
            <small>{t(locale, "manager_capability_observability_smoke_verified")}</small>
          </span>
          <span className={`capability-observability-metric ${warningDiagnosticCount === 0 ? "capability-ok" : "capability-warn"}`}>
            <strong>{warningDiagnosticCount}</strong>
            <small>{t(locale, "manager_capability_observability_warnings")}</small>
          </span>
          <span className={`capability-observability-metric ${standaloneWebReady ? "capability-ok" : "capability-warn"}`}>
            <strong>{standaloneWebReady ? t(locale, "manager_capability_status_ok") : t(locale, "manager_capability_status_unknown")}</strong>
            <small>{t(locale, "manager_capability_observability_web_lane")}</small>
          </span>
        </div>
      </div>
      {isLoading ? <p className="muted compact-copy">{t(locale, "manager_capability_loading")}</p> : null}
      {isError ? <p className="error-text">{t(locale, "manager_capability_load_error")}</p> : null}
      {routes.length === 0 && !isLoading ? (
        <div className="manager-empty-state">{t(locale, "manager_capability_empty")}</div>
      ) : (
        <div className="manager-list manager-list-tall capability-route-list">
          {routes.map((route) => {
            const management = managementById.get(route.capability_id);
            const draft = drafts[route.capability_id] ?? {
              mode: route.route_record.mode,
              provider_id: route.route_record.provider_id ?? null,
              model: route.route_record.model ?? null,
            };
            const selectableCandidates = route.candidates.filter((candidate) => candidate.provider_id && candidate.model);
            const selectedCandidateValue = draft.provider_id ? `${draft.provider_id}/${draft.model ?? ""}` : "";
            const isStandalone = route.lane_type === "web_standalone";
            const isDirty =
              draft.mode !== route.route_record.mode ||
              (draft.provider_id ?? null) !== (route.route_record.provider_id ?? null) ||
              (draft.model ?? null) !== (route.route_record.model ?? null);
            const smokeResult = smokeResults[route.capability_id] ?? null;
            const routeStatus = routeSurfaceStatus(route, management, smokeResult);
            const routeStatusLabel = localizedEnum(locale, routeStatus, CAPABILITY_SURFACE_STATUS_KEYS);
            const resolvedLabel = route.resolved_candidate?.provider_id
              ? `${route.resolved_candidate.provider_id}/${route.resolved_candidate.model ?? ""}`
              : localizedEnum(locale, route.resolution_status, CAPABILITY_STATUS_KEYS);
            const routeDisplayName = localizedCapabilityName(locale, route);
            const laneLabel = localizedEnum(locale, route.lane_type, CAPABILITY_LANE_KEYS);
            const transportLabel = localizedEnum(locale, route.transport_mode, CAPABILITY_TRANSPORT_KEYS);
            const smokeStatusLabel = localizedEnum(locale, management?.smoke.status ?? "unknown", CAPABILITY_STATUS_KEYS);
            const artifactPolicyLabel = localizedEnum(locale, management?.artifacts.policy ?? "unknown", CAPABILITY_ARTIFACT_POLICY_KEYS);
            const visibleCandidates = route.candidates.slice(0, 4);
            const providerError = smokeProviderError(smokeResult ?? undefined);
            const diagnostics = diagnosticsByCapability.get(route.capability_id) ?? [];
            const smokePending = isSmokePending && smokePendingCapabilityId === route.capability_id;
            const recentArtifacts = artifactsByCapability.get(route.capability_id) ?? [];
            const selectedProviderCredential = draft.provider_id ? providerCredentials[draft.provider_id] : null;
            const resolvedProviderCredential = route.resolved_candidate?.provider_id
              ? providerCredentials[route.resolved_candidate.provider_id]
              : null;
            const providerSmokeAuthorized = Boolean(providerSmokeAuthorizations[route.capability_id]);
            const providerSmokeDisabled = Boolean(
              smokePending ||
                !providerSmokeAuthorized ||
                !route.resolved_candidate?.provider_id ||
                !resolvedProviderCredential ||
                !resolvedProviderCredential.enabled ||
                resolvedProviderCredential.status === "missing" ||
                resolvedProviderCredential.status === "session_required" ||
                resolvedProviderCredential.status === "disabled",
            );
            const providerSmokeSkipText =
              !smokePending && providerSmokeDisabled && !isStandalone
                ? providerSmokeSkipReason(locale, route, resolvedProviderCredential, providerSmokeAuthorized)
                : "";
            const toolingGuides = CAPABILITY_RUNTIME_TOOLING_GUIDANCE[route.capability_id] ?? [];
            const resolvedToolingGuides = toolingGuides.map((guide) =>
              resolveCapabilityRuntimeToolingGuide(guide, pluginRegistryById, skillRegistryByName),
            );
            const selectedCredentialBlocksSave =
              draft.mode === "pinned" &&
              Boolean(
                selectedProviderCredential &&
                  (!selectedProviderCredential.enabled ||
                    selectedProviderCredential.status === "missing" ||
                    selectedProviderCredential.status === "session_required" ||
                    selectedProviderCredential.status === "disabled"),
              );
            const providerCredentialSummaries = Array.from(
              new Map(
                route.candidates
                  .filter((candidate) => candidate.provider_id)
                  .map((candidate) => [candidate.provider_id, providerCredentials[candidate.provider_id ?? ""]]),
              ).values(),
            ).filter(Boolean) as CapabilityProviderCredentialStatus[];
            const hasPaidProviderRisk = !isStandalone && route.candidates.some((candidate) => candidate.provider_id);
            const hasLargeArtifactRisk =
              !isStandalone &&
              ["generated_assets", "audio", "visual"].some((token) => String(management?.artifacts.policy ?? route.capability_id).includes(token));
            return (
              <section className="manager-row capability-route-row" key={route.capability_id} aria-labelledby={`capability-${route.capability_id}`}>
                <div className="capability-route-header">
                  <div>
                    <strong id={`capability-${route.capability_id}`}>{routeDisplayName}</strong>
                    <div className="muted compact-copy">{route.capability_id} / {laneLabel} / {transportLabel}</div>
                  </div>
                  <div className="capability-route-badges">
                    <span
                      className={`session-badge ${capabilitySurfaceToneClass(routeStatus)}`}
                      data-testid={`capability-route-status-${route.capability_id}`}
                    >
                      {routeStatusLabel}
                    </span>
                    <span className="session-badge">{resolvedLabel}</span>
                  </div>
                </div>

                <div className="capability-route-meta">
                  <span>{t(locale, "manager_capability_candidates")}: {management?.availability.candidate_count ?? route.candidates.length}</span>
                  <span>{t(locale, "manager_capability_adapters")}: {management?.adapters.length ?? 0}</span>
                  <span>{t(locale, "manager_capability_smoke")}: {smokeStatusLabel}</span>
                  <span>{t(locale, "manager_capability_artifacts")}: {artifactPolicyLabel}</span>
                </div>

                <details className="manager-disclosure capability-route-disclosure">
                  <summary>{t(locale, "manager_capability_route_details")}</summary>
                  <div className="manager-disclosure-content">
                <div className="capability-diagnostic-strip" aria-label={`${routeDisplayName} ${t(locale, "manager_capability_diagnostics")}`}>
                  {diagnostics.map((diagnostic) => {
                    const toneClass =
                      diagnostic.tone === "ok"
                        ? "capability-ok"
                        : diagnostic.tone === "warning"
                          ? "status-tag-warning"
                          : "";
                    return (
                      <span className={`status-tag ${toneClass}`} key={`${route.capability_id}-${diagnostic.key}`}>
                        {diagnostic.label}
                      </span>
                    );
                  })}
                </div>

                <div className="capability-safety-panel" aria-label={`${routeDisplayName} ${t(locale, "manager_capability_safety_panel")}`}>
                  {hasPaidProviderRisk ? <span className="status-tag status-tag-warning">{t(locale, "manager_capability_paid_warning")}</span> : null}
                  {hasLargeArtifactRisk ? <span className="status-tag status-tag-warning">{t(locale, "manager_capability_large_artifact_warning")}</span> : null}
                  {route.resolution_status !== "ok" && !isStandalone ? <span className="status-tag status-tag-warning">{t(locale, "manager_capability_provider_error")}: {route.resolution_status}</span> : null}
                  {providerCredentialSummaries.length === 0 && !isStandalone ? (
                    <span className="status-tag status-tag-warning">{t(locale, "manager_capability_credential_missing")}</span>
                  ) : null}
                  {providerCredentialSummaries.map((credential) => {
                    const tone = credential.status === "configured" || credential.status === "check_environment" ? "capability-ok" : "capability-warn";
                    const label =
                      credential.status === "configured"
                        ? t(locale, "manager_capability_credential_configured")
                        : credential.status === "check_environment"
                          ? `${t(locale, "manager_capability_credential_env_ref")} ${credential.env_key ?? ""}`.trim()
                          : credential.status === "session_required"
                            ? t(locale, "manager_capability_credential_session_required")
                            : credential.status === "disabled"
                              ? t(locale, "manager_capability_provider_disabled")
                              : t(locale, "manager_capability_credential_missing");
                    return (
                      <span className={`session-badge ${tone}`} key={credential.provider_id}>
                        {credential.provider_id}: {label}
                      </span>
                    );
                  })}
                </div>

                {toolingGuides.length > 0 || isStandalone ? (
                  <div className="capability-runtime-guidance-panel" aria-label={`${routeDisplayName} ${t(locale, "manager_capability_plugin_skill_panel")}`}>
                    <div>
                      <strong>{t(locale, "manager_capability_plugin_skill_title")}</strong>
                      <p className="muted compact-copy">{t(locale, "manager_capability_plugin_skill_summary")}</p>
                    </div>
                    {isStandalone ? (
                      <div className="capability-runtime-guidance-list">
                        <article className="capability-runtime-guidance-item">
                          <div className="capability-runtime-guidance-copy">
                            <strong>{t(locale, "manager_capability_standalone_web_label")}</strong>
                            <p className="muted compact-copy">{t(locale, "manager_capability_standalone_web_preserved")}</p>
                          </div>
                          <div className="capability-route-badges">
                            <span className="session-badge capability-ok">{t(locale, "manager_capability_standalone_note")}</span>
                          </div>
                        </article>
                      </div>
                    ) : showPluginSkillLoading ? (
                      <p className="muted compact-copy">{t(locale, "manager_capability_plugin_skill_loading")}</p>
                    ) : showPluginSkillError ? (
                      <p className="error-text">{t(locale, "manager_capability_plugin_skill_error")}</p>
                    ) : (
                      <div className="capability-runtime-guidance-list">
                        {resolvedToolingGuides.map((guide) => {
                          const tone =
                            guide.kind === "plugin"
                              ? guide.state === "available"
                                ? "capability-ok"
                                : "capability-warn"
                              : guide.state === "enabled"
                                ? "capability-ok"
                                : "capability-warn";
                          const stateLabel =
                            guide.kind === "plugin"
                              ? guide.state === "available"
                                ? t(locale, "manager_capability_plugin_available")
                                : guide.state === "disabled"
                                  ? t(locale, "manager_capability_plugin_disabled")
                                  : t(locale, "manager_capability_plugin_missing")
                              : guide.state === "enabled"
                                ? t(locale, "manager_capability_skill_enabled")
                                : guide.state === "disabled"
                                  ? t(locale, "manager_capability_skill_disabled")
                                  : t(locale, "manager_capability_skill_missing");
                          return (
                            <article className="capability-runtime-guidance-item" key={`${route.capability_id}-${guide.kind}-${guide.reference}`}>
                              <div className="capability-runtime-guidance-copy">
                                <strong>{guide.label}</strong>
                                <p className="muted compact-copy">{t(locale, guide.summary_key)}</p>
                              </div>
                              <div className="capability-route-badges">
                                <span className={`session-badge ${tone}`}>{stateLabel}</span>
                                <span className="session-badge">{guide.reference}</span>
                                {guide.detail ? <span className="session-badge">{guide.detail}</span> : null}
                              </div>
                            </article>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ) : null}

                  </div>
                </details>

                <div className="form-grid capability-route-controls">
                  <label className="field">
                    <span>{t(locale, "manager_capability_mode")}</span>
                    <select
                      value={draft.mode}
                      disabled={isStandalone}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [route.capability_id]: {
                            ...draft,
                            mode: event.target.value as "auto" | "pinned",
                          },
                        }))
                      }
                    >
                      <option value="auto">{t(locale, "manager_capability_auto")}</option>
                      <option value="pinned">{t(locale, "manager_capability_pinned")}</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>{t(locale, "manager_capability_candidate")}</span>
                    <select
                      value={selectedCandidateValue}
                      disabled={draft.mode !== "pinned" || isStandalone}
                      onChange={(event) => {
                        const [provider_id, model] = event.target.value.split("/", 2);
                        setDrafts((current) => ({
                          ...current,
                          [route.capability_id]: {
                            ...draft,
                            provider_id: provider_id || null,
                            model: model || null,
                          },
                        }));
                      }}
                    >
                      <option value="">{t(locale, "manager_capability_unavailable")}</option>
                      {selectableCandidates.map((candidate) => {
                        const status = candidateSurfaceStatus(candidate, route, management, smokeResult);
                        const statusLabel = localizedEnum(locale, status, CAPABILITY_SURFACE_STATUS_KEYS);
                        return (
                          <option key={`${candidate.provider_id}/${candidate.model}`} value={`${candidate.provider_id}/${candidate.model}`}>
                            {candidate.provider_id}/{candidate.model} - {statusLabel}
                          </option>
                        );
                      })}
                    </select>
                  </label>
                </div>

                <div className="capability-candidate-list" aria-label={t(locale, "manager_capability_candidate_details")}>
                  {visibleCandidates.length === 0 ? (
                    <span className="muted compact-copy">{t(locale, "manager_capability_no_candidate_detail")}</span>
                  ) : (
                    visibleCandidates.map((candidate) => {
                      const candidateStatus = candidateSurfaceStatus(candidate, route, management, smokeResult);
                      const candidateStatusLabel = localizedEnum(locale, candidateStatus, CAPABILITY_SURFACE_STATUS_KEYS);
                      const isResolvedCandidate = sameCandidate(candidate, route.resolved_candidate ?? null);
                      return (
                        <article
                          className="capability-candidate-pill"
                          key={`${candidate.adapter_id}-${candidate.provider_id ?? "standalone"}-${candidate.model ?? "none"}`}
                        >
                          <div className="capability-candidate-pill-header">
                            <strong>{candidate.provider_id ? `${candidate.provider_id}/${candidate.model ?? ""}` : candidate.source}</strong>
                            <div className="capability-candidate-badges">
                              <span
                                className={`session-badge ${capabilitySurfaceToneClass(candidateStatus)}`}
                                data-testid={`capability-candidate-status-${route.capability_id}-${candidate.provider_id ?? "standalone"}-${candidate.model ?? "none"}`}
                              >
                                {candidateStatusLabel}
                              </span>
                              {isResolvedCandidate ? <span className="session-badge">{t(locale, "manager_capability_candidate_resolved")}</span> : null}
                              {candidate.recommended ? <span className="session-badge">{t(locale, "manager_capability_candidate_recommended")}</span> : null}
                              {candidate.default_for_provider ? <span className="session-badge">{t(locale, "manager_capability_candidate_default")}</span> : null}
                              {candidate.catalog_present === false ? (
                                <span className="session-badge capability-warn">{t(locale, "manager_capability_candidate_catalog_missing")}</span>
                              ) : null}
                            </div>
                          </div>
                          <small>{candidate.adapter_id} / {localizedModalities(locale, candidate.input_modalities)}</small>
                          <small>{candidateStatusNote(locale, candidate, candidateStatus)}</small>
                        </article>
                      );
                    })
                  )}
                </div>

                {!isStandalone ? (
                  <div className="capability-smoke-panel" aria-label={`${routeDisplayName} ${t(locale, "manager_capability_smoke_panel")}`}>
                    <div>
                      <strong>{t(locale, "manager_capability_dry_run_smoke")}</strong>
                      <p className="muted compact-copy">{t(locale, "manager_capability_dry_run_summary")}</p>
                    </div>
                    <div className="capability-smoke-result">
                      <span>{t(locale, "manager_capability_fixture_cases")}: {(management?.smoke.case_ids ?? []).join(", ") || "dry_run"}</span>
                      <span>
                        {t(locale, "manager_capability_last_smoke")}: {smokeSummary(locale, smokeResult)}
                      </span>
                      {smokeResult?.route.error ? <span className="error-text">{smokeResult.route.error}</span> : null}
                      {providerError ? <span className="error-text">{providerError}</span> : null}
                    </div>
                    {providerSmokeSkipText ? (
                      <div className="capability-smoke-skip" data-testid={`capability-provider-smoke-skip-${route.capability_id}`}>
                        <strong>{t(locale, "manager_capability_provider_smoke_skipped")}</strong>
                        <span>{providerSmokeSkipText}</span>
                      </div>
                    ) : null}
                    <label className="capability-provider-smoke-authorization">
                      <input
                        type="checkbox"
                        checked={providerSmokeAuthorized}
                        onChange={(event) =>
                          setProviderSmokeAuthorizations((current) => ({
                            ...current,
                            [route.capability_id]: event.target.checked,
                          }))
                        }
                      />
                      <span>{t(locale, "manager_capability_provider_smoke_authorize")}</span>
                    </label>
                    <div className="capability-smoke-actions">
                      <button
                        type="button"
                        className="ghost-button"
                        data-testid={`capability-dry-smoke-${route.capability_id}`}
                        disabled={smokePending}
                        onClick={() => onRunSmoke(route.capability_id)}
                      >
                        {smokePending ? t(locale, "manager_capability_smoke_running") : t(locale, "manager_capability_run_dry_smoke")}
                      </button>
                      <button
                        type="button"
                        className="ghost-button"
                        data-testid={`capability-provider-smoke-${route.capability_id}`}
                        disabled={providerSmokeDisabled}
                        onClick={() => onRunProviderSmoke(route.capability_id)}
                        title={providerSmokeDisabled ? t(locale, "manager_capability_provider_smoke_disabled") : t(locale, "manager_capability_provider_smoke_warning")}
                      >
                        {smokePending ? t(locale, "manager_capability_smoke_running") : t(locale, "manager_capability_run_provider_smoke")}
                      </button>
                    </div>
                  </div>
                ) : null}

                <div className="capability-artifacts-panel" aria-label={`${routeDisplayName} ${t(locale, "manager_capability_artifact_panel")}`}>
                  <div className="capability-artifacts-header">
                    <div>
                      <strong>{t(locale, "manager_capability_recent_artifacts")}</strong>
                      <p className="muted compact-copy">
                        {artifactsLoading
                          ? t(locale, "manager_capability_artifacts_loading")
                          : artifactsError
                            ? t(locale, "manager_capability_artifacts_error")
                            : `${recentArtifacts.length} ${t(locale, "manager_capability_artifacts_found")}`}
                      </p>
                    </div>
                  </div>
                  {recentArtifacts.length === 0 ? (
                    <div className="muted compact-copy">{t(locale, "manager_capability_artifacts_empty")}</div>
                  ) : (
                    <div className="capability-artifact-list">
                      {recentArtifacts.slice(0, 2).map((artifact) => {
                        const imageSrc = artifact.preview.image_path ? toMediaSrc(artifact.preview.image_path) : "";
                        const audioSrc = artifact.preview.audio_path ? toMediaSrc(artifact.preview.audio_path) : "";
                        const hasMediaPreview = Boolean(imageSrc || audioSrc);
                        return (
                          <article className="capability-artifact-item" key={`${artifact.capability_id}-${artifact.artifact_id}`}>
                            <div className="capability-artifact-preview">
                              {artifact.preview.kind === "image" && imageSrc ? <img src={imageSrc} alt="" /> : null}
                              {artifact.preview.kind === "audio" && audioSrc ? <audio controls src={audioSrc} /> : null}
                              {!hasMediaPreview && artifact.preview.text ? <p>{artifact.preview.text}</p> : null}
                              {!hasMediaPreview && !artifact.preview.text ? <span>{artifact.preview.kind}</span> : null}
                            </div>
                            <div className="capability-artifact-meta">
                              <strong>{artifact.artifact_id}</strong>
                              <span>{artifact.provider_id || "provider"} / {artifact.model || "model"}</span>
                              <span>{artifact.saved_at || t(locale, "manager_capability_unknown_time")}</span>
                              <span>{artifact.relative_summary_path}</span>
                              <span>{artifact.artifact_refs.length} {t(locale, "manager_capability_artifact_refs")}</span>
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div className="field-row capability-route-actions">
                  <button
                    type="button"
                    className="ghost-button"
                    disabled={!isDirty || isSaving}
                    onClick={() =>
                      setDrafts((current) => ({
                        ...current,
                        [route.capability_id]: {
                          mode: route.route_record.mode,
                          provider_id: route.route_record.provider_id ?? null,
                          model: route.route_record.model ?? null,
                        },
                      }))
                    }
                  >
                    {t(locale, "manager_capability_reset")}
                  </button>
                  <button
                    type="button"
                    className="primary-button"
                    disabled={!isDirty || isSaving || isStandalone || (draft.mode === "pinned" && !draft.provider_id) || selectedCredentialBlocksSave}
                    onClick={() => onSave(route, draft)}
                  >
                    {t(locale, "manager_capability_save")}
                  </button>
                  {selectedCredentialBlocksSave ? <small className="error-text">{t(locale, "manager_capability_credential_blocks_save")}</small> : null}
                  {isStandalone ? <small className="muted compact-copy">{t(locale, "manager_capability_standalone_note")}</small> : null}
                  {route.error ? <small className="error-text">{route.error}</small> : null}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

function resolveCapabilityRuntimeToolingGuide(
  guide: CapabilityRuntimeToolingGuide,
  pluginRegistryById: Map<string, CodexPluginRegistryRecord>,
  skillRegistryByName: Map<string, CodexSkillRegistryRecord>,
): ResolvedCapabilityRuntimeTooling {
  if (guide.kind === "plugin") {
    const plugin = pluginRegistryById.get(guide.plugin_id);
    const state = resolvePluginGuideState(plugin);
    return {
      kind: "plugin",
      reference: guide.plugin_id,
      label: plugin?.display_name || guide.fallback_label,
      summary_key: guide.summary_key,
      state,
      detail: null,
    };
  }
  const skill = skillRegistryByName.get(guide.skill_name);
  const state = resolveSkillGuideState(skill);
  return {
    kind: "skill",
    reference: guide.skill_name,
    label: skill?.display_name || guide.fallback_label,
    summary_key: guide.summary_key,
    state,
    detail: null,
  };
}

function resolvePluginGuideState(plugin?: CodexPluginRegistryRecord): "available" | "disabled" | "missing" {
  if (!plugin || plugin.install_status !== "installed") {
    return "missing";
  }
  if (plugin.enablement_status !== "enabled" || plugin.compatibility_status === "incompatible") {
    return "disabled";
  }
  return "available";
}

function resolveSkillGuideState(skill?: CodexSkillRegistryRecord): "enabled" | "disabled" | "missing" {
  if (!skill || skill.install_status !== "installed") {
    return "missing";
  }
  const effectiveStatus = skill.effective_enablement_status || skill.enablement_status;
  if (effectiveStatus !== "enabled" || skill.compatibility_status === "incompatible") {
    return "disabled";
  }
  return "enabled";
}
