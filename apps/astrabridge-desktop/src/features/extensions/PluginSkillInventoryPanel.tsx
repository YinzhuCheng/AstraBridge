import { convertFileSrc, isTauri } from "@tauri-apps/api/core";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../api";
import type {
  CodexPluginInstallExecution,
  CodexPluginInstallPlan,
  CodexPluginInstallPlanFileEntry,
  CodexPluginRegistryRecord,
  CodexPluginSkillRegistrySnapshot,
  CodexRegistryCompatibilityWarning,
  CodexRegistryIconMetadata,
  CodexRegistrySourceCatalog,
  CodexSkillRegistryRecord,
  LocaleCode,
  ProjectFile,
} from "../../types";

type InventoryKind = "all" | "plugins" | "skills";
type InventoryStatusFilter = "all" | "installed" | "available" | "attention" | "disabled";

type InventoryItem =
  | {
      id: string;
      kind: "plugin";
      title: string;
      subtitle: string;
      description: string;
      searchText: string;
      source: CodexRegistrySourceCatalog | null;
      installStatus: string;
      enablementStatus: string;
      compatibilityStatus: string;
      warnings: CodexRegistryCompatibilityWarning[];
      notes: string[];
      attention: boolean;
      icon: CodexRegistryIconMetadata | null;
      plugin: CodexPluginRegistryRecord;
    }
  | {
      id: string;
      kind: "skill";
      title: string;
      subtitle: string;
      description: string;
      searchText: string;
      source: CodexRegistrySourceCatalog | null;
      installStatus: string;
      enablementStatus: string;
      compatibilityStatus: string;
      warnings: CodexRegistryCompatibilityWarning[];
      notes: string[];
      attention: boolean;
      icon: CodexRegistryIconMetadata | null;
      skill: CodexSkillRegistryRecord;
    };

const LABELS = {
  en: {
    title: "Extensions",
    loading: "Loading plugin and skill inventory...",
    unavailable: "Plugin and skill inventory is unavailable.",
    summary: "Inspect discovered Codex plugins and skills across AstraBridge-managed runtime roots. Plugin install stays explicit, and skill enablement can be managed globally or overridden per project.",
    pluginList: "Plugin list",
    skillList: "Skill list",
    pluginsCount: "Plugins",
    skillsCount: "Skills",
    sourcesCount: "Sources",
    generatedAt: "Generated",
    inventory: "Inventory",
    details: "Details",
    search: "Search inventory",
    type: "Type",
    status: "Status",
    all: "All",
    plugins: "Plugins",
    skills: "Skills",
    installed: "installed",
    available: "available",
    attention: "attention",
    disabled: "disabled",
    noMatches: "No plugins or skills match the current filters.",
    noSelection: "Select a plugin or skill to inspect its metadata.",
    unsupportedKernel: "Kernel does not expose plugin or skill inventory on this runtime yet.",
    unsupportedHint: "Upgrade or probe a runtime that supports plugin and skill listing before expecting inventory here.",
    source: "Source",
    sourceCatalog: "Source catalog",
    description: "Description",
    installStatus: "Install status",
    enablement: "Enablement",
    compatibility: "Compatibility",
    pluginId: "Plugin id",
    skillName: "Skill name",
    versions: "Versions",
    declaredMcp: "Declared MCP",
    declaredApps: "Declared apps",
    declaredHooks: "Declared hooks",
    owningPlugin: "Owning plugin",
    triggerHints: "Trigger hints",
    permissions: "Permissions",
    provenance: "Provenance",
    warnings: "Warnings",
    notes: "Notes",
    icon: "Icon",
    iconProvenance: "Icon provenance",
    iconValidated: "Icon validated",
    asset: "Asset",
    none: "none",
    manifestPath: "Manifest path",
    sourcePath: "Source path",
    sourceUrl: "Source URL",
    relativeRoot: "Relative root",
    checksum: "Checksum",
    writable: "Writable",
    yes: "yes",
    no: "no",
    plugin: "Plugin",
    skill: "Skill",
    noWarnings: "No compatibility warnings.",
    official: "official",
    bundledLocal: "bundled local",
    generatedFallback: "generated fallback",
    planTitle: "Install plan",
    planSummary: "Preview install or update scope before any file mutation happens.",
    planAction: "Action",
    planReason: "Reason",
    planSourceRoot: "Source root",
    planTargetRoot: "Target root",
    planRollback: "Rollback snapshot",
    planPreview: "Preview plan",
    planPreviewPending: "Preparing plan...",
    planNotLoaded: "No install or update plan has been prepared for this plugin yet.",
    currentVersion: "Current version",
    targetVersion: "Target version",
    sourceFiles: "Source files",
    targetFiles: "Existing target files",
    plannedWrites: "Planned writes",
    planErrors: "Plan errors",
    planWarnings: "Plan warnings",
    rollbackFiles: "Rollback capture",
    rollbackStatus: "Rollback status",
    apps: "Apps",
    applyAction: "Apply",
    applyPending: "Applying...",
    applyResult: "Execution result",
    executionStatus: "Execution status",
    reportPath: "Report path",
    projectPreset: "Project preset",
    activePreset: "Active preset",
    presetPlugins: "Preset plugins",
    presetSkills: "Preset skills",
    addToPreset: "Add to project preset",
    removeFromPreset: "Remove from project preset",
    resetPreset: "Reset preset",
    presetPending: "Saving preset...",
    presetSummary: "Project-local plugin and skill references are stored in the AstraBridge project file and stay out of official Codex state.",
    skillControls: "Skill controls",
    observedEnablement: "Observed runtime",
    effectiveEnablement: "Effective enablement",
    globalDefault: "Global default",
    projectOverride: "Project override",
    enablementSourceLabel: "Enablement source",
    enableGlobally: "Enable globally",
    disableGlobally: "Disable globally",
    enableForProject: "Enable for project",
    disableForProject: "Disable for project",
    useGlobalSetting: "Use global setting",
    globalStatePath: "Global state path",
    projectStatePath: "Project state path",
    skillUpdatePending: "Updating...",
  },
  "zh-CN": {
    title: "扩展",
    loading: "正在加载插件与技能清单...",
    unavailable: "插件与技能清单暂不可用。",
    summary: "查看 AstraBridge 托管运行时根目录中发现的 Codex 插件与技能。本阶段只读，不提供安装、更新或启用变更。",
    pluginList: "插件列表",
    skillList: "技能列表",
    pluginsCount: "插件",
    skillsCount: "技能",
    sourcesCount: "来源",
    generatedAt: "生成时间",
    inventory: "清单",
    details: "详情",
    search: "搜索清单",
    type: "类型",
    status: "状态",
    all: "全部",
    plugins: "插件",
    skills: "技能",
    installed: "已安装",
    available: "可用",
    attention: "需关注",
    disabled: "已禁用",
    noMatches: "当前筛选条件下没有匹配的插件或技能。",
    noSelection: "选择一个插件或技能以查看元数据。",
    unsupportedKernel: "当前运行时内核还不能暴露插件或技能清单。",
    unsupportedHint: "先升级或探测支持插件与技能列表能力的运行时，再在这里查看清单。",
    source: "来源",
    sourceCatalog: "来源目录",
    description: "描述",
    installStatus: "安装状态",
    enablement: "启用状态",
    compatibility: "兼容性",
    pluginId: "插件 ID",
    skillName: "技能名",
    versions: "版本",
    declaredMcp: "声明的 MCP",
    declaredApps: "声明的应用",
    declaredHooks: "声明的 Hook",
    owningPlugin: "所属插件",
    triggerHints: "触发提示",
    permissions: "权限提示",
    provenance: "来源追踪",
    warnings: "兼容性告警",
    notes: "备注",
    none: "无",
    manifestPath: "Manifest 路径",
    sourcePath: "来源路径",
    sourceUrl: "来源 URL",
    relativeRoot: "相对根",
    checksum: "校验",
    writable: "可写",
    yes: "是",
    no: "否",
    plugin: "插件",
    skill: "技能",
    noWarnings: "没有兼容性告警。",
  },
} as const;

export function PluginSkillInventoryPanel({
  locale,
  snapshot,
  isLoading,
  error,
  project,
  onProjectChanged,
  onRegistryChanged,
}: {
  locale: LocaleCode;
  snapshot?: CodexPluginSkillRegistrySnapshot | null;
  isLoading: boolean;
  error?: unknown;
  project?: ProjectFile | null;
  onProjectChanged?: (project: ProjectFile) => void;
  onRegistryChanged?: () => void | Promise<unknown>;
}) {
  const copy = { ...LABELS.en, ...(LABELS[locale] ?? LABELS.en) };
  const [search, setSearch] = useState("");
  const [kind, setKind] = useState<InventoryKind>("all");
  const [status, setStatus] = useState<InventoryStatusFilter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pluginPlans, setPluginPlans] = useState<Record<string, CodexPluginInstallPlan>>({});
  const [planErrors, setPlanErrors] = useState<Record<string, string>>({});
  const [planPendingRecordId, setPlanPendingRecordId] = useState<string | null>(null);
  const [applyResults, setApplyResults] = useState<Record<string, CodexPluginInstallExecution>>({});
  const [applyErrors, setApplyErrors] = useState<Record<string, string>>({});
  const [applyPendingRecordId, setApplyPendingRecordId] = useState<string | null>(null);
  const [presetPending, setPresetPending] = useState(false);
  const [presetError, setPresetError] = useState("");
  const [skillActionErrorRecordId, setSkillActionErrorRecordId] = useState<string | null>(null);
  const [skillActionError, setSkillActionError] = useState("");
  const [skillPendingActionKey, setSkillPendingActionKey] = useState<string | null>(null);

  const sourceCatalogById = useMemo(() => {
    return new Map((snapshot?.source_catalogs ?? []).map((entry) => [entry.source_catalog_id, entry]));
  }, [snapshot?.source_catalogs]);

  const items = useMemo(() => {
    const pluginItems = (snapshot?.plugins ?? []).map((plugin) => _pluginItem(plugin, sourceCatalogById.get(plugin.source_catalog_id) ?? null));
    const skillItems = (snapshot?.skills ?? []).map((skill) => _skillItem(skill, sourceCatalogById.get(skill.source_catalog_id) ?? null));
    return [...pluginItems, ...skillItems].sort((left, right) => left.title.localeCompare(right.title));
  }, [snapshot?.plugins, snapshot?.skills, sourceCatalogById]);

  const noteMap = useMemo(() => _noteMap(snapshot?.notes ?? []), [snapshot?.notes]);
  const pluginListStatus = noteMap.plugin_list_status ?? "unknown";
  const skillListStatus = noteMap.skill_list_status ?? "unknown";

  const filteredItems = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return items.filter((item) => {
      if (kind === "plugins" && item.kind !== "plugin") return false;
      if (kind === "skills" && item.kind !== "skill") return false;
      if (status === "installed" && item.installStatus !== "installed") return false;
      if (status === "available" && !["available", "update_available"].includes(item.installStatus)) return false;
      if (status === "attention" && !item.attention) return false;
      if (status === "disabled" && item.enablementStatus !== "disabled") return false;
      if (!normalizedSearch) return true;
      return item.searchText.includes(normalizedSearch);
    });
  }, [items, kind, search, status]);

  useEffect(() => {
    if (!filteredItems.length) {
      setSelectedId(null);
      return;
    }
    if (!selectedId || !filteredItems.some((item) => item.id === selectedId)) {
      setSelectedId(filteredItems[0].id);
    }
  }, [filteredItems, selectedId]);

  useEffect(() => {
    setPluginPlans({});
    setPlanErrors({});
    setPlanPendingRecordId(null);
    setApplyResults({});
    setApplyErrors({});
    setApplyPendingRecordId(null);
    setPresetPending(false);
    setPresetError("");
    setSkillActionErrorRecordId(null);
    setSkillActionError("");
    setSkillPendingActionKey(null);
  }, [snapshot?.generated_at]);

  const activeProjectPreset = _activeProjectPreset(project);

  if (isLoading && !snapshot) {
    return (
      <section className="metadata-section" data-testid="plugin-skill-inventory-panel">
        <div className="section-header">
          <h4>{copy.title}</h4>
        </div>
        <p className="muted">{copy.loading}</p>
      </section>
    );
  }

  if (!snapshot) {
    return (
      <section className="metadata-section" data-testid="plugin-skill-inventory-panel">
        <div className="section-header">
          <h4>{copy.title}</h4>
        </div>
        {error ? <p className="error-text">{String((error as Error)?.message ?? error)}</p> : null}
        <p className="muted">{copy.unavailable}</p>
      </section>
    );
  }

  const selected = filteredItems.find((item) => item.id === selectedId) ?? null;
  const selectedPlan = selected?.kind === "plugin" ? pluginPlans[selected.plugin.record_id] ?? null : null;
  const selectedPlanError = selected?.kind === "plugin" ? planErrors[selected.plugin.record_id] ?? "" : "";
  const selectedApplyResult = selected?.kind === "plugin" ? applyResults[selected.plugin.record_id] ?? null : null;
  const selectedApplyError = selected?.kind === "plugin" ? applyErrors[selected.plugin.record_id] ?? "" : "";
  const selectedSkillActionError = selected?.kind === "skill" && skillActionErrorRecordId === selected.skill.record_id ? skillActionError : "";
  const unsupported = items.length === 0 && (pluginListStatus === "unsupported" || skillListStatus === "unsupported");

  async function handlePreviewPlan(plugin: CodexPluginRegistryRecord) {
    setPlanPendingRecordId(plugin.record_id);
    setPlanErrors((current) => {
      const next = { ...current };
      delete next[plugin.record_id];
      return next;
    });
    try {
      const plan = await api.runtimePluginInstallPlan({
        plugin_id: plugin.plugin_id,
        source_catalog_id: plugin.source_catalog_id,
      });
      setPluginPlans((current) => ({ ...current, [plugin.record_id]: plan }));
    } catch (planError) {
      const message = String((planError as Error)?.message ?? planError ?? "Failed to prepare plugin install plan.");
      setPlanErrors((current) => ({ ...current, [plugin.record_id]: message }));
    } finally {
      setPlanPendingRecordId((current) => (current === plugin.record_id ? null : current));
    }
  }

  async function handleApplyPlan(plugin: CodexPluginRegistryRecord) {
    setApplyPendingRecordId(plugin.record_id);
    setApplyErrors((current) => {
      const next = { ...current };
      delete next[plugin.record_id];
      return next;
    });
    try {
      const result = await api.runtimePluginInstallApply({
        plugin_id: plugin.plugin_id,
        source_catalog_id: plugin.source_catalog_id,
      });
      setApplyResults((current) => ({ ...current, [plugin.record_id]: result }));
      if (result.status === "applied" || result.status === "noop") {
        await onRegistryChanged?.();
      }
    } catch (applyError) {
      const message = String((applyError as Error)?.message ?? applyError ?? "Failed to apply plugin install plan.");
      setApplyErrors((current) => ({ ...current, [plugin.record_id]: message }));
    } finally {
      setApplyPendingRecordId((current) => (current === plugin.record_id ? null : current));
    }
  }

  async function handleSkillEnablementUpdate(
    skill: CodexSkillRegistryRecord,
    scope: "global" | "project",
    enablementStatus: "enabled" | "disabled" | "inherited",
  ) {
    const actionKey = `${skill.record_id}:${scope}:${enablementStatus}`;
    setSkillPendingActionKey(actionKey);
    setSkillActionErrorRecordId(null);
    setSkillActionError("");
    try {
      await api.runtimeSkillEnablementUpdate({
        record_id: skill.record_id,
        scope,
        enablement_status: enablementStatus,
      });
      await onRegistryChanged?.();
    } catch (mutationError) {
      setSkillActionErrorRecordId(skill.record_id);
      setSkillActionError(String((mutationError as Error)?.message ?? mutationError ?? "Failed to update skill enablement."));
    } finally {
      setSkillPendingActionKey((current) => (current === actionKey ? null : current));
    }
  }

  async function handleProjectPresetMutation(payload: Parameters<typeof api.updateProjectPluginSkillPresets>[0]) {
    setPresetPending(true);
    setPresetError("");
    try {
      const response = await api.updateProjectPluginSkillPresets(payload);
      onProjectChanged?.(response.project);
    } catch (mutationError) {
      setPresetError(String((mutationError as Error)?.message ?? mutationError ?? "Failed to update project preset."));
    } finally {
      setPresetPending(false);
    }
  }

  return (
    <div className="manager-panel" data-testid="plugin-skill-inventory-panel">
      <div className="metadata-actions metadata-actions-compact">
        <div>
          <span className="eyebrow">{copy.title}</span>
          <h3>{copy.inventory}</h3>
          <p className="muted">{copy.summary}</p>
        </div>
        <div className="mcp-health-row">
          <span>{copy.pluginsCount}: {snapshot.plugins.length}</span>
          <span>{copy.skillsCount}: {snapshot.skills.length}</span>
          <span>{copy.sourcesCount}: {snapshot.source_catalogs.length}</span>
          <span>{copy.pluginList}: {_formatStatus(pluginListStatus)}</span>
          <span>{copy.skillList}: {_formatStatus(skillListStatus)}</span>
        </div>
      </div>

      {error ? <p className="error-text">{String((error as Error)?.message ?? error)}</p> : null}

      {unsupported ? (
        <section className="metadata-section">
          <div className="section-header">
            <h4>{copy.details}</h4>
            <span className="status-tag capability-warn">{copy.attention}</span>
          </div>
          <p>{copy.unsupportedKernel}</p>
          <p className="muted">{copy.unsupportedHint}</p>
          <div className="mcp-health-row">
            <span>{copy.pluginList}: {_formatStatus(pluginListStatus)}</span>
            <span>{copy.skillList}: {_formatStatus(skillListStatus)}</span>
          </div>
        </section>
      ) : null}

      {project ? (
        <section className="metadata-section">
          <div className="section-header">
            <h4>{copy.projectPreset}</h4>
            <div className="extensions-inline-actions">
              <button
                type="button"
                className="ghost-button compact-button"
                disabled={presetPending || (!_projectPresetPluginCount(activeProjectPreset) && !_projectPresetSkillCount(activeProjectPreset))}
                onClick={() => void handleProjectPresetMutation({ operation: "reset", preset_id: activeProjectPreset.preset_id })}
              >
                {presetPending ? copy.presetPending : copy.resetPreset}
              </button>
            </div>
          </div>
          <p className="muted">{copy.presetSummary}</p>
          {presetError ? <p className="error-text">{presetError}</p> : null}
          <div className="extensions-detail-grid">
            <div><span>{copy.activePreset}</span><strong>{activeProjectPreset.display_name}</strong></div>
            <div><span>{copy.presetPlugins}</span><strong>{_projectPresetPluginCount(activeProjectPreset)}</strong></div>
            <div><span>{copy.presetSkills}</span><strong>{_projectPresetSkillCount(activeProjectPreset)}</strong></div>
            <div><span>{copy.generatedAt}</span><strong>{project.updated_at}</strong></div>
          </div>
          <div className="extensions-tag-list">
            {_detailTags(
              [
                ...((activeProjectPreset.plugin_refs ?? []).map((item) => item.display_name || item.plugin_id)),
                ...((activeProjectPreset.skill_refs ?? []).map((item) => item.display_name || item.skill_name)),
              ],
              copy.none,
            )}
          </div>
        </section>
      ) : null}

      <div className="metadata-editor extensions-editor">
        <div className="metadata-list-pane">
          <div className="metadata-section extensions-actions">
            <div className="section-header">
              <h4>{copy.inventory}</h4>
              <small className="muted">{copy.generatedAt}: {snapshot.generated_at}</small>
            </div>
            <div className="extensions-filter-grid">
              <label className="field">
                <span>{copy.search}</span>
                <input aria-label={copy.search} value={search} onChange={(event) => setSearch(event.target.value)} />
              </label>
              <div className="field">
                <span>{copy.type}</span>
                <div className="segmented segmented-wrap" role="group" aria-label={copy.type}>
                  <button type="button" className={kind === "all" ? "segmented-active" : ""} onClick={() => setKind("all")}>{copy.all}</button>
                  <button type="button" className={kind === "plugins" ? "segmented-active" : ""} onClick={() => setKind("plugins")}>{copy.plugins}</button>
                  <button type="button" className={kind === "skills" ? "segmented-active" : ""} onClick={() => setKind("skills")}>{copy.skills}</button>
                </div>
              </div>
              <label className="field">
                <span>{copy.status}</span>
                <select aria-label={copy.status} value={status} onChange={(event) => setStatus(event.target.value as InventoryStatusFilter)}>
                  <option value="all">{copy.all}</option>
                  <option value="installed">{copy.installed}</option>
                  <option value="available">{copy.available}</option>
                  <option value="attention">{copy.attention}</option>
                  <option value="disabled">{copy.disabled}</option>
                </select>
              </label>
            </div>
          </div>

          <div className="extensions-list">
            {filteredItems.map((item) => (
              <button
                key={item.id}
                type="button"
                className={selected?.id === item.id ? "metadata-row metadata-row-active" : "metadata-row"}
                onClick={() => setSelectedId(item.id)}
              >
                <div className="extensions-row-shell">
                  <ExtensionIconPreview icon={item.icon} title={item.title} decorative compact />
                  <div className="extensions-row-content">
                    <div className="extensions-row-top">
                      <span className="metadata-row-title">{item.title}</span>
                      <span className={`status-tag ${item.attention ? "capability-warn" : "capability-ok"}`}>{item.kind === "plugin" ? copy.plugin : copy.skill}</span>
                    </div>
                    <span className="metadata-row-id">{item.subtitle}</span>
                    <span className="metadata-row-id">{item.source?.display_name ?? copy.none}</span>
                    <span className="extensions-row-badges">
                      <span>{_formatStatus(item.installStatus)}</span>
                      <span>{_formatStatus(item.enablementStatus)}</span>
                      <span>{_formatStatus(item.compatibilityStatus)}</span>
                      <span>{_iconProvenanceLabel(item.icon?.provenance_kind, copy)}</span>
                    </span>
                  </div>
                </div>
              </button>
            ))}
            {!filteredItems.length ? <div className="metadata-section"><p className="muted">{copy.noMatches}</p></div> : null}
          </div>
        </div>

        <div className="metadata-detail-pane">
          {selected ? (
            <>
              <div className="metadata-detail-header">
                <div className="extensions-detail-hero">
                  <ExtensionIconPreview icon={selected.icon} title={selected.title} />
                  <div>
                    <span className="eyebrow">{selected.kind === "plugin" ? copy.plugin : copy.skill}</span>
                    <h3>{selected.title}</h3>
                    <p className="muted">{selected.description || copy.none}</p>
                  </div>
                </div>
                <div className="extensions-row-badges">
                  <span className="status-tag">{_formatStatus(selected.installStatus)}</span>
                  <span className="status-tag">{_formatStatus(selected.enablementStatus)}</span>
                  <span className={`status-tag ${selected.attention ? "capability-warn" : "capability-ok"}`}>{_formatStatus(selected.compatibilityStatus)}</span>
                </div>
              </div>

              <section className="metadata-section">
                <h4>{copy.details}</h4>
                <div className="extensions-detail-grid">
                  <div><span>{copy.source}</span><strong>{selected.source?.display_name ?? copy.none}</strong></div>
                  <div><span>{copy.sourceCatalog}</span><strong>{selected.source?.kind ?? copy.none}</strong></div>
                  <div><span>{copy.installStatus}</span><strong>{_formatStatus(selected.installStatus)}</strong></div>
                  <div><span>{copy.enablement}</span><strong>{_formatStatus(selected.enablementStatus)}</strong></div>
                  <div><span>{copy.compatibility}</span><strong>{_formatStatus(selected.compatibilityStatus)}</strong></div>
                  <div><span>{copy.generatedAt}</span><strong>{snapshot.generated_at}</strong></div>
                  {selected.kind === "plugin" ? (
                    <>
                      <div><span>{copy.pluginId}</span><strong>{selected.plugin.plugin_id}</strong></div>
                      <div><span>{copy.versions}</span><strong>{_pluginVersions(selected.plugin) || copy.none}</strong></div>
                    </>
                  ) : (
                    <>
                      <div><span>{copy.skillName}</span><strong>{selected.skill.skill_name}</strong></div>
                      <div><span>{copy.owningPlugin}</span><strong>{selected.skill.owner_plugin_id || copy.none}</strong></div>
                    </>
                  )}
                </div>
              </section>

              {selected.kind === "plugin" ? (
                <section className="metadata-section">
                  <div className="section-header">
                    <h4>{copy.planTitle}</h4>
                    <div className="extensions-inline-actions">
                      <button
                        type="button"
                        className="ghost-button compact-button"
                        disabled={planPendingRecordId === selected.plugin.record_id}
                        onClick={() => void handlePreviewPlan(selected.plugin)}
                      >
                        {planPendingRecordId === selected.plugin.record_id ? copy.planPreviewPending : copy.planPreview}
                      </button>
                      <button
                        type="button"
                        className="primary-button compact-button"
                        disabled={!selectedPlan || selectedPlan.status !== "ready" || applyPendingRecordId === selected.plugin.record_id}
                        onClick={() => void handleApplyPlan(selected.plugin)}
                      >
                        {applyPendingRecordId === selected.plugin.record_id ? copy.applyPending : copy.applyAction}
                      </button>
                    </div>
                  </div>
                  <p className="muted">{copy.planSummary}</p>
                  {selectedPlanError ? <p className="error-text">{selectedPlanError}</p> : null}
                  {selectedApplyError ? <p className="error-text">{selectedApplyError}</p> : null}
                  {!selectedPlan ? (
                    <p className="muted">{copy.planNotLoaded}</p>
                  ) : (
                    <>
                      <div className="extensions-detail-grid">
                        <div><span>{copy.planAction}</span><strong>{_formatStatus(selectedPlan.action)}</strong></div>
                        <div><span>{copy.planReason}</span><strong>{_formatStatus(selectedPlan.reason)}</strong></div>
                        <div><span>{copy.currentVersion}</span><strong>{selectedPlan.versions.current_version || copy.none}</strong></div>
                        <div><span>{copy.targetVersion}</span><strong>{selectedPlan.versions.target_version || copy.none}</strong></div>
                        <div><span>{copy.source}</span><strong>{selectedPlan.source.display_name || copy.none}</strong></div>
                        <div><span>{copy.sourceCatalog}</span><strong>{selectedPlan.source.kind || copy.none}</strong></div>
                        <div><span>{copy.planSourceRoot}</span><strong>{selectedPlan.files.source_root || selectedPlan.source.source_path || copy.none}</strong></div>
                        <div><span>{copy.planTargetRoot}</span><strong>{selectedPlan.files.target_root || copy.none}</strong></div>
                        <div><span>{copy.sourceUrl}</span><strong>{selectedPlan.source.source_url || copy.none}</strong></div>
                        <div><span>{copy.planRollback}</span><strong>{selectedPlan.rollback_snapshot.snapshot_id || copy.none}</strong></div>
                        <div><span>{copy.rollbackStatus}</span><strong>{_formatStatus(selectedPlan.rollback_snapshot.status)}</strong></div>
                        <div><span>{copy.generatedAt}</span><strong>{selectedPlan.generated_at}</strong></div>
                      </div>

                      <h4>{copy.permissions}</h4>
                      <div className="extensions-tag-list">
                        {_detailTags(selectedPlan.permission_hints, copy.none)}
                      </div>
                      <h4>{copy.apps}</h4>
                      <div className="extensions-tag-list">
                        {_detailTags(selectedPlan.declared_app_ids, copy.none)}
                      </div>
                      <h4>{copy.declaredMcp}</h4>
                      <div className="extensions-tag-list">
                        {_detailTags(selectedPlan.mcp_changes.declared_servers, copy.none)}
                      </div>
                      <h4>{copy.skills}</h4>
                      <div className="extensions-tag-list">
                        {_detailTags(selectedPlan.skill_changes.declared_skills, copy.none)}
                      </div>

                      <div className="extensions-plan-files">
                        <div>
                          <h4>{copy.sourceFiles} ({selectedPlan.files.source_file_count})</h4>
                          {_renderPlanFileEntries(selectedPlan.files.source_files, copy.none)}
                        </div>
                        <div>
                          <h4>{copy.targetFiles} ({selectedPlan.files.existing_target_file_count})</h4>
                          {_renderPlanFileEntries(selectedPlan.files.existing_target_files, copy.none)}
                        </div>
                        <div>
                          <h4>{copy.plannedWrites} ({selectedPlan.files.planned_write_count})</h4>
                          {_renderPlanFileEntries(selectedPlan.files.planned_write_files, copy.none)}
                        </div>
                      </div>

                      <h4>{copy.rollbackFiles} ({selectedPlan.rollback_snapshot.captured_file_count})</h4>
                      {_renderPlanFileEntries(selectedPlan.rollback_snapshot.captured_files, copy.none)}

                      <div className="extensions-plan-warning-grid">
                        <div>
                          <h4>{copy.planErrors}</h4>
                          <div className="extensions-warning-list">
                            {(selectedPlan.errors ?? []).length
                              ? (selectedPlan.errors ?? []).map((warning) => (
                                  <div key={`error:${warning.code}:${warning.field ?? ""}`} className="extensions-warning-item">
                                    <strong>{warning.code}</strong>
                                    <span>{warning.message}</span>
                                  </div>
                                ))
                              : <p className="muted">{copy.none}</p>}
                          </div>
                        </div>
                        <div>
                          <h4>{copy.planWarnings}</h4>
                          <div className="extensions-warning-list">
                            {(selectedPlan.warnings ?? []).length
                              ? (selectedPlan.warnings ?? []).map((warning) => (
                                  <div key={`warning:${warning.code}:${warning.field ?? ""}`} className="extensions-warning-item">
                                    <strong>{warning.code}</strong>
                                    <span>{warning.message}</span>
                                  </div>
                                ))
                              : <p className="muted">{copy.noWarnings}</p>}
                          </div>
                        </div>
                      </div>

                      <h4>{copy.notes}</h4>
                      <div className="extensions-tag-list">
                        {_detailTags(selectedPlan.notes, copy.none)}
                      </div>

                      {selectedApplyResult ? (
                        <div className="extensions-execution-summary">
                          <h4>{copy.applyResult}</h4>
                          <div className="extensions-detail-grid">
                            <div><span>{copy.executionStatus}</span><strong>{_formatStatus(selectedApplyResult.status)}</strong></div>
                            <div><span>{copy.planAction}</span><strong>{_formatStatus(selectedApplyResult.action)}</strong></div>
                            <div><span>{copy.rollbackStatus}</span><strong>{_formatStatus(selectedApplyResult.rollback_snapshot.status)}</strong></div>
                            <div><span>{copy.reportPath}</span><strong>{selectedApplyResult.artifact_paths.result_path || copy.none}</strong></div>
                          </div>
                          {(selectedApplyResult.errors ?? []).length ? (
                            <div className="extensions-warning-list">
                              {(selectedApplyResult.errors ?? []).map((warning) => (
                                <div key={`apply:${warning.code}:${warning.field ?? ""}`} className="extensions-warning-item">
                                  <strong>{warning.code}</strong>
                                  <span>{warning.message}</span>
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </>
                  )}
                </section>
              ) : null}

              <section className="metadata-section">
                <h4>{copy.icon}</h4>
                <div className="extensions-detail-grid">
                  <div><span>{copy.iconProvenance}</span><strong>{_iconProvenanceLabel(selected.icon?.provenance_kind, copy)}</strong></div>
                  <div><span>{copy.iconValidated}</span><strong>{selected.icon?.validated ? copy.yes : copy.no}</strong></div>
                  <div><span>{copy.asset}</span><strong>{selected.icon?.asset_path || selected.icon?.asset_url || copy.none}</strong></div>
                  <div><span>{copy.checksum}</span><strong>{selected.icon?.checksum_algorithm && selected.icon?.checksum_value ? `${selected.icon.checksum_algorithm}:${selected.icon.checksum_value}` : copy.none}</strong></div>
                </div>
                <div className="extensions-tag-list">
                  {_detailTags(selected.icon?.notes, copy.none)}
                </div>
              </section>

              {selected.kind === "plugin" ? (
                <section className="metadata-section">
                  {project ? (
                    <>
                      <div className="section-header">
                        <h4>{copy.projectPreset}</h4>
                        <div className="extensions-inline-actions">
                          <button
                            type="button"
                            className="ghost-button compact-button"
                            disabled={presetPending}
                            onClick={() =>
                              void handleProjectPresetMutation(
                                _pluginPresetContains(activeProjectPreset, selected.plugin)
                                  ? {
                                      operation: "remove_plugin",
                                      preset_id: activeProjectPreset.preset_id,
                                      plugin_ref: {
                                        plugin_id: selected.plugin.plugin_id,
                                        source_catalog_id: selected.plugin.source_catalog_id,
                                        display_name: selected.plugin.display_name,
                                      },
                                    }
                                  : {
                                      operation: "add_plugin",
                                      preset_id: activeProjectPreset.preset_id,
                                      plugin_ref: {
                                        plugin_id: selected.plugin.plugin_id,
                                        source_catalog_id: selected.plugin.source_catalog_id,
                                        display_name: selected.plugin.display_name,
                                      },
                                    },
                              )
                            }
                          >
                            {presetPending
                              ? copy.presetPending
                              : _pluginPresetContains(activeProjectPreset, selected.plugin)
                                ? copy.removeFromPreset
                                : copy.addToPreset}
                          </button>
                        </div>
                      </div>
                      {presetError ? <p className="error-text">{presetError}</p> : null}
                    </>
                  ) : null}
                  <h4>{copy.permissions}</h4>
                  <div className="extensions-tag-list">
                    {_detailTags(selected.plugin.permission_hints, copy.none)}
                  </div>
                  <h4>{copy.declaredMcp}</h4>
                  <div className="extensions-tag-list">
                    {_detailTags(selected.plugin.declared_mcp_servers, copy.none)}
                  </div>
                  <h4>{copy.declaredApps}</h4>
                  <div className="extensions-tag-list">
                    {_detailTags(selected.plugin.declared_app_ids, copy.none)}
                  </div>
                  <h4>{copy.declaredHooks}</h4>
                  <div className="extensions-tag-list">
                    {_detailTags(selected.plugin.declared_hook_keys, copy.none)}
                  </div>
                </section>
              ) : (
                <section className="metadata-section">
                  {project ? (
                    <>
                      <div className="section-header">
                        <h4>{copy.projectPreset}</h4>
                        <div className="extensions-inline-actions">
                          <button
                            type="button"
                            className="ghost-button compact-button"
                            disabled={presetPending}
                            onClick={() =>
                              void handleProjectPresetMutation(
                                _skillPresetContains(activeProjectPreset, selected.skill)
                                  ? {
                                      operation: "remove_skill",
                                      preset_id: activeProjectPreset.preset_id,
                                      skill_ref: {
                                        record_id: selected.skill.record_id,
                                        skill_name: selected.skill.skill_name,
                                        owner_plugin_id: selected.skill.owner_plugin_id,
                                        source_catalog_id: selected.skill.source_catalog_id,
                                        display_name: selected.skill.display_name,
                                      },
                                    }
                                  : {
                                      operation: "add_skill",
                                      preset_id: activeProjectPreset.preset_id,
                                      skill_ref: {
                                        record_id: selected.skill.record_id,
                                        skill_name: selected.skill.skill_name,
                                        owner_plugin_id: selected.skill.owner_plugin_id,
                                        source_catalog_id: selected.skill.source_catalog_id,
                                        display_name: selected.skill.display_name,
                                      },
                                    },
                              )
                            }
                          >
                            {presetPending
                              ? copy.presetPending
                              : _skillPresetContains(activeProjectPreset, selected.skill)
                                ? copy.removeFromPreset
                                : copy.addToPreset}
                          </button>
                        </div>
                      </div>
                      {presetError ? <p className="error-text">{presetError}</p> : null}
                    </>
                  ) : null}
                  <div className="section-header">
                    <h4>{copy.skillControls}</h4>
                    <div className="extensions-inline-actions">
                      <button
                        type="button"
                        className="ghost-button compact-button"
                        disabled={
                          !!skillPendingActionKey
                          || _skillGlobalStatus(selected.skill) === "enabled"
                          || _skillEffectiveStatus(selected.skill) === "blocked"
                        }
                        onClick={() => void handleSkillEnablementUpdate(selected.skill, "global", "enabled")}
                      >
                        {skillPendingActionKey === `${selected.skill.record_id}:global:enabled` ? copy.skillUpdatePending : copy.enableGlobally}
                      </button>
                      <button
                        type="button"
                        className="ghost-button compact-button"
                        disabled={!!skillPendingActionKey || _skillGlobalStatus(selected.skill) === "disabled"}
                        onClick={() => void handleSkillEnablementUpdate(selected.skill, "global", "disabled")}
                      >
                        {skillPendingActionKey === `${selected.skill.record_id}:global:disabled` ? copy.skillUpdatePending : copy.disableGlobally}
                      </button>
                    </div>
                  </div>
                  <div className="extensions-detail-grid">
                    <div><span>{copy.effectiveEnablement}</span><strong>{_formatStatus(_skillEffectiveStatus(selected.skill))}</strong></div>
                    <div><span>{copy.observedEnablement}</span><strong>{_formatStatus(selected.skill.observed_enablement_status || selected.skill.enablement_status)}</strong></div>
                    <div><span>{copy.globalDefault}</span><strong>{_formatStatus(_skillGlobalStatus(selected.skill))}</strong></div>
                    <div><span>{copy.projectOverride}</span><strong>{_formatStatus(selected.skill.project_enablement_status || "unknown")}</strong></div>
                    <div><span>{copy.enablementSourceLabel}</span><strong>{_formatStatus(selected.skill.enablement_source || "unknown")}</strong></div>
                    <div><span>{copy.owningPlugin}</span><strong>{selected.skill.owner_plugin_id || copy.none}</strong></div>
                  </div>
                  {selectedSkillActionError ? <p className="error-text">{selectedSkillActionError}</p> : null}
                  {selected.skill.project_override_supported !== false ? (
                    <div className="extensions-inline-actions">
                      <button
                        type="button"
                        className="ghost-button compact-button"
                        disabled={
                          !!skillPendingActionKey
                          || (selected.skill.project_enablement_status || "unknown") === "enabled"
                          || _skillEffectiveStatus(selected.skill) === "blocked"
                        }
                        onClick={() => void handleSkillEnablementUpdate(selected.skill, "project", "enabled")}
                      >
                        {skillPendingActionKey === `${selected.skill.record_id}:project:enabled` ? copy.skillUpdatePending : copy.enableForProject}
                      </button>
                      <button
                        type="button"
                        className="ghost-button compact-button"
                        disabled={!!skillPendingActionKey || (selected.skill.project_enablement_status || "unknown") === "disabled"}
                        onClick={() => void handleSkillEnablementUpdate(selected.skill, "project", "disabled")}
                      >
                        {skillPendingActionKey === `${selected.skill.record_id}:project:disabled` ? copy.skillUpdatePending : copy.disableForProject}
                      </button>
                      <button
                        type="button"
                        className="ghost-button compact-button"
                        disabled={!!skillPendingActionKey || (selected.skill.project_enablement_status || "unknown") === "inherited"}
                        onClick={() => void handleSkillEnablementUpdate(selected.skill, "project", "inherited")}
                      >
                        {skillPendingActionKey === `${selected.skill.record_id}:project:inherited` ? copy.skillUpdatePending : copy.useGlobalSetting}
                      </button>
                    </div>
                  ) : null}
                  <div className="extensions-path-list">
                    <div><span>{copy.globalStatePath}</span><strong>{selected.skill.global_state_path || copy.none}</strong></div>
                    <div><span>{copy.projectStatePath}</span><strong>{selected.skill.project_state_path || copy.none}</strong></div>
                  </div>
                  <h4>{copy.owningPlugin}</h4>
                  <p>{selected.skill.owner_plugin_id || copy.none}</p>
                  <h4>{copy.triggerHints}</h4>
                  <div className="extensions-tag-list">
                    {_detailTags(selected.skill.trigger_hints, copy.none)}
                  </div>
                  <h4>{copy.permissions}</h4>
                  <div className="extensions-tag-list">
                    {_detailTags(selected.skill.permission_hints, copy.none)}
                  </div>
                </section>
              )}

              <section className="metadata-section">
                <h4>{copy.provenance}</h4>
                <div className="extensions-detail-grid">
                  {_provenanceRows(selected.kind === "plugin" ? selected.plugin.provenance : selected.skill.provenance, copy.none).map((row) => (
                    <div key={row.label}>
                      <span>{row.label}</span>
                      <strong>{row.value}</strong>
                    </div>
                  ))}
                  <div><span>{copy.writable}</span><strong>{selected.source?.writable ? copy.yes : copy.no}</strong></div>
                </div>
              </section>

              <section className="metadata-section">
                <h4>{copy.warnings}</h4>
                <div className="extensions-warning-list">
                  {selected.warnings.length ? selected.warnings.map((warning) => (
                    <div key={`${warning.code}:${warning.field ?? ""}`} className="extensions-warning-item">
                      <strong>{warning.code}</strong>
                      <span>{warning.message}</span>
                    </div>
                  )) : <p className="muted">{copy.noWarnings}</p>}
                </div>
                <h4>{copy.notes}</h4>
                <div className="extensions-tag-list">
                  {_detailTags(selected.notes, copy.none)}
                </div>
              </section>
            </>
          ) : (
            <section className="metadata-section">
              <h4>{copy.details}</h4>
              <p className="muted">{copy.noSelection}</p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

function ExtensionIconPreview({
  icon,
  title,
  decorative = false,
  compact = false,
}: {
  icon: CodexRegistryIconMetadata | null | undefined;
  title: string;
  decorative?: boolean;
  compact?: boolean;
}) {
  const src = _iconSrc(icon);
  const label = _iconBadgeLabel(icon, title);
  if (src) {
    return (
      <div className={compact ? "extensions-icon-preview extensions-icon-preview-compact" : "extensions-icon-preview"} aria-hidden={decorative || undefined}>
        <img src={src} alt={decorative ? "" : `${title} icon`} />
      </div>
    );
  }
  return (
    <div className={compact ? "extensions-icon-preview extensions-icon-preview-compact" : "extensions-icon-preview"} aria-hidden={decorative || undefined}>
      <span>{label}</span>
    </div>
  );
}

function _pluginItem(plugin: CodexPluginRegistryRecord, source: CodexRegistrySourceCatalog | null): InventoryItem {
  const warnings = plugin.compatibility_warnings ?? [];
  const notes = plugin.notes ?? [];
  const description = plugin.description?.trim() || "";
  return {
    id: plugin.record_id,
    kind: "plugin",
    title: plugin.display_name || plugin.plugin_id,
    subtitle: plugin.plugin_id,
    description,
    searchText: [
      plugin.display_name,
      plugin.plugin_id,
      source?.display_name,
      plugin.description,
      ...(plugin.permission_hints ?? []),
      ...(plugin.declared_mcp_servers ?? []),
      ...(plugin.declared_app_ids ?? []),
      ...(plugin.declared_hook_keys ?? []),
      ...notes,
    ].join(" ").toLowerCase(),
    source,
    installStatus: String(plugin.install_status || "unknown"),
    enablementStatus: String(plugin.enablement_status || "unknown"),
    compatibilityStatus: String(plugin.compatibility_status || "unknown"),
    warnings,
    notes,
    attention: _needsAttention(String(plugin.install_status || "unknown"), String(plugin.enablement_status || "unknown"), String(plugin.compatibility_status || "unknown"), warnings),
    icon: plugin.icon ?? null,
    plugin,
  };
}

function _skillItem(skill: CodexSkillRegistryRecord, source: CodexRegistrySourceCatalog | null): InventoryItem {
  const warnings = skill.compatibility_warnings ?? [];
  const notes = skill.notes ?? [];
  const description = skill.short_description?.trim() || skill.description?.trim() || "";
  return {
    id: skill.record_id,
    kind: "skill",
    title: skill.display_name || skill.skill_name,
    subtitle: skill.skill_name,
    description,
    searchText: [
      skill.display_name,
      skill.skill_name,
      source?.display_name,
      skill.owner_plugin_id,
      skill.description,
      skill.short_description,
      ...(skill.permission_hints ?? []),
      ...(skill.trigger_hints ?? []),
      ...notes,
    ].join(" ").toLowerCase(),
    source,
    installStatus: String(skill.install_status || "unknown"),
    enablementStatus: String(skill.enablement_status || "unknown"),
    compatibilityStatus: String(skill.compatibility_status || "unknown"),
    warnings,
    notes,
    attention: _needsAttention(String(skill.install_status || "unknown"), String(skill.enablement_status || "unknown"), String(skill.compatibility_status || "unknown"), warnings),
    icon: skill.icon ?? null,
    skill,
  };
}

function _noteMap(notes: string[]) {
  const result: Record<string, string> = {};
  for (const note of notes) {
    const text = String(note || "").trim();
    if (!text) continue;
    const separator = text.indexOf(":");
    if (separator < 0) continue;
    result[text.slice(0, separator)] = text.slice(separator + 1);
  }
  return result;
}

function _formatStatus(value: string | null | undefined) {
  const text = String(value || "unknown").trim() || "unknown";
  return text.replace(/[_/]+/g, " ");
}

function _needsAttention(
  installStatus: string,
  enablementStatus: string,
  compatibilityStatus: string,
  warnings: CodexRegistryCompatibilityWarning[],
) {
  if (warnings.length > 0) return true;
  if (enablementStatus === "disabled" || enablementStatus === "blocked") return true;
  if (!["compatible", "enabled", "installed", "available", "update_available", "inherited"].includes(compatibilityStatus) && compatibilityStatus !== "compatible") {
    if (compatibilityStatus !== "unknown") return true;
  }
  return ["malformed", "incompatible", "unavailable"].includes(installStatus) || ["warning", "incompatible"].includes(compatibilityStatus);
}

function _detailTags(values: string[] | undefined, emptyLabel: string) {
  const entries = (values ?? []).filter((item) => String(item || "").trim());
  if (!entries.length) {
    return <span>{emptyLabel}</span>;
  }
  return entries.map((value) => <span key={value}>{value}</span>);
}

function _renderPlanFileEntries(entries: CodexPluginInstallPlanFileEntry[] | undefined, emptyLabel: string) {
  const values = (entries ?? []).filter((item) => String(item?.relative_path || item?.path || "").trim());
  if (!values.length) {
    return <p className="muted">{emptyLabel}</p>;
  }
  return (
    <div className="extensions-file-list">
      {values.map((entry) => (
        <div key={`${entry.path}:${entry.relative_path}`} className="extensions-file-item">
          <strong>{entry.relative_path || entry.path}</strong>
          <span>{entry.bytes != null ? `${entry.bytes} B` : entry.path}</span>
        </div>
      ))}
    </div>
  );
}

function _iconSrc(icon: CodexRegistryIconMetadata | null | undefined) {
  const assetPath = String(icon?.asset_path || "").trim();
  if (assetPath) {
    return isTauri() ? convertFileSrc(assetPath) : "";
  }
  const assetUrl = String(icon?.asset_url || "").trim();
  return assetUrl || "";
}

function _iconBadgeLabel(icon: CodexRegistryIconMetadata | null | undefined, title: string) {
  const explicit = String(icon?.label || "").trim();
  if (explicit) {
    return explicit.slice(0, 2).toUpperCase();
  }
  const parts = title.split(/[^0-9A-Za-z]+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return (parts[0] || title || "AB").slice(0, 2).toUpperCase();
}

function _skillEffectiveStatus(skill: CodexSkillRegistryRecord) {
  return String(skill.effective_enablement_status || skill.enablement_status || "unknown");
}

function _skillGlobalStatus(skill: CodexSkillRegistryRecord) {
  return String(skill.global_enablement_status || skill.observed_enablement_status || skill.enablement_status || "unknown");
}

function _activeProjectPreset(project?: ProjectFile | null) {
  const presets = project?.plugin_skill_presets?.presets ?? [];
  const activePresetId = project?.plugin_skill_presets?.active_preset_id ?? "project-default";
  return (
    presets.find((item) => item.preset_id === activePresetId)
    ?? {
      preset_id: "project-default",
      display_name: "Project default",
      plugin_refs: [],
      skill_refs: [],
      notes: [],
    }
  );
}

function _pluginPresetContains(
  preset: ReturnType<typeof _activeProjectPreset>,
  plugin: CodexPluginRegistryRecord,
) {
  return (preset.plugin_refs ?? []).some(
    (item) => item.plugin_id === plugin.plugin_id && String(item.source_catalog_id || "") === String(plugin.source_catalog_id || ""),
  );
}

function _skillPresetContains(
  preset: ReturnType<typeof _activeProjectPreset>,
  skill: CodexSkillRegistryRecord,
) {
  return (preset.skill_refs ?? []).some((item) => item.record_id === skill.record_id);
}

function _projectPresetPluginCount(preset: ReturnType<typeof _activeProjectPreset>) {
  return (preset.plugin_refs ?? []).length;
}

function _projectPresetSkillCount(preset: ReturnType<typeof _activeProjectPreset>) {
  return (preset.skill_refs ?? []).length;
}

function _iconProvenanceLabel(
  value: string | null | undefined,
  copy: { official: string; bundledLocal: string; generatedFallback: string; none: string },
) {
  if (value === "official") return copy.official;
  if (value === "bundled_local") return copy.bundledLocal;
  if (value === "generated_fallback") return copy.generatedFallback;
  return copy.none;
}

function _pluginVersions(plugin: CodexPluginRegistryRecord) {
  const values = [plugin.installed_version, plugin.available_version, plugin.version].filter((item) => String(item || "").trim());
  return [...new Set(values)].join(" / ");
}

function _provenanceRows(
  provenance: { source_path?: string | null; source_url?: string | null; manifest_path?: string | null; relative_root?: string | null; checksum_algorithm?: string | null; checksum_value?: string | null } | null | undefined,
  emptyLabel: string,
) {
  const checksum = provenance?.checksum_algorithm && provenance?.checksum_value ? `${provenance.checksum_algorithm}:${provenance.checksum_value}` : emptyLabel;
  return [
    { label: LABELS.en.manifestPath, value: provenance?.manifest_path || emptyLabel },
    { label: LABELS.en.sourcePath, value: provenance?.source_path || emptyLabel },
    { label: LABELS.en.sourceUrl, value: provenance?.source_url || emptyLabel },
    { label: LABELS.en.relativeRoot, value: provenance?.relative_root || emptyLabel },
    { label: LABELS.en.checksum, value: checksum },
  ];
}
