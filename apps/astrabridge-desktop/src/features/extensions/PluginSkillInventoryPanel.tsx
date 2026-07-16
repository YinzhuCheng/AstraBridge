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
  ProjectFilePreview,
  SkillPluginCreatorScenarioExecution,
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

type PluginCreatorScenarioSpec = {
  triggerPath: string;
  fixtureContractPath: string;
  briefPath: string;
  runRoot: string;
  pluginRoot: string;
  manifestPath: string;
  marketplacePath: string;
  suggestedReportPath: string;
  referenceReportPath: string;
  referenceScreenshotPath: string;
};

const PLUGIN_CREATOR_SCENARIO_SPEC: PluginCreatorScenarioSpec = {
  triggerPath: "能力 -> 技能 -> Plugin Creator",
  fixtureContractPath: "apps/astrabridge-sidecar/tests/fixtures/skill_plugin_creator_fixture/fixture-contract.json",
  briefPath: "apps/astrabridge-sidecar/tests/fixtures/skill_plugin_creator_fixture/input/plugin-creator-brief.md",
  runRoot: "PRIVATE/demo-runs/skills-plugin-creator-scenario/",
  pluginRoot: "PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/plugins/astrabridge-skills-dogfood-sample/",
  manifestPath: "PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/plugins/astrabridge-skills-dogfood-sample/.codex-plugin/plugin.json",
  marketplacePath: "PRIVATE/demo-runs/skills-plugin-creator-scenario/generated/.agents/plugins/marketplace.json",
  suggestedReportPath: "apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/step12-skills-plugin-creator-pass.json",
  referenceReportPath: "apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/step10-skills-plugin-creator-report-partial.json",
  referenceScreenshotPath: "apps/astrabridge-desktop/output/playwright/real-scenario-dogfood/step10-skills-plugin-creator-reference.png",
};

const LABELS = {
  en: {
    title: "Extensions",
    loading: "Loading plugin and skill inventory...",
    unavailable: "Plugin and skill inventory is unavailable.",
    summary: "Inspect discovered Codex plugins and skills across AstraBridge-managed runtime roots. Plugin install stays explicit, and selected skills can expose controlled task evidence alongside enablement controls.",
    summaryPlugins: "Review plugin inventory, source boundaries, and explicit install status inside AstraBridge-managed runtime roots. Installation stays isolated and always requires an explicit preview first.",
    summarySkills: "Inspect discovered skills, owning plugins, effective enablement state, and any controlled task evidence exposed for real-scenario dogfooding.",
    pluginList: "Plugin list",
    skillList: "Skill list",
    pluginsCount: "Plugins",
    skillsCount: "Skills",
    sourcesCount: "Sources",
    installedCount: "Installed",
    availableCount: "Ready to install",
    attentionCount: "Needs attention",
    generatedAt: "Generated",
    registryRefresh: "Refresh registry",
    registryRefreshPending: "Refreshing...",
    registryRefreshingHint: "Refreshing inventory while keeping the last verified snapshot visible.",
    pluginDiscovery: "Plugin discovery",
    skillDiscovery: "Skill discovery",
    inventory: "Inventory",
    inventoryPlugins: "Plugins",
    inventorySkills: "Skills",
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
    enabled: "enabled",
    blocked: "blocked",
    warning: "warning",
    compatible: "compatible",
    unknown: "unknown",
    supported: "supported",
    inherited: "inherited",
    ready: "ready",
    planned: "planned",
    applied: "applied",
    install: "install",
    update: "update",
    noop: "up to date",
    unsupported: "unsupported",
    updateAvailable: "update available",
    noMatches: "No plugins or skills match the current filters.",
    noPluginMatches: "No plugins match the current filters.",
    noSkillMatches: "No skills match the current filters.",
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
    sourceKindLocal: "local",
    sourceKindProjectLocal: "project local",
    sourceKindManual: "manual",
    sourceKindOfficial: "official",
    sourceKindCurated: "curated",
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
    planWorkflow: "Operation guidance",
    planWorkflowBoundary: "All plugin writes stay inside AstraBridge-managed isolated runtime roots and evidence directories.",
    planWorkflowIdle: "Preview the plan first. AstraBridge only writes a plugin into its isolated runtime after you explicitly apply the prepared plan.",
    planWorkflowInstall: "This plugin is ready to install from an AstraBridge-managed local source. Applying the plan copies files into the isolated runtime and records rollback evidence.",
    planWorkflowUpdate: "This plugin has an update path. Applying the plan replaces the isolated runtime copy and captures rollback evidence before mutation.",
    planWorkflowNoop: "This plugin is already current in the isolated runtime. Re-preview the plan when you need to inspect source, target, or rollback metadata.",
    planWorkflowUnsupported: "This plugin is visible for inspection, but the current source cannot be applied directly. Mirror it into an AstraBridge-managed local catalog before expecting install actions here.",
    planWorkflowApplied: "The latest execution result is shown below. Report paths stay inside AstraBridge-managed evidence roots.",
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
    enablementReason: "Effective state reason",
    waitingApproval: "Waiting for approval",
    waitingApprovalHint: "This skill came from a newly installed plugin and remains disabled until you explicitly approve it.",
    blockedByOwner: "Owning plugin unavailable",
    blockedByOwnerHint: "AstraBridge cannot enable this skill until its owning plugin becomes available again.",
    disabledByProject: "Disabled by project override",
    disabledByProjectHint: "The current project preset keeps this skill disabled for this workspace.",
    disabledByGlobal: "Disabled by global default",
    disabledByGlobalHint: "The global runtime rule keeps this skill disabled until you enable it again.",
    skillUpdatePending: "Updating...",
    contributions: "Contributions",
    pass: "pass",
    failed: "failed",
    timeout: "timeout",
    skillScenarioTitle: "Controlled task",
    skillScenarioBadge: "fixture scenario",
    skillScenarioRun: "Run controlled task",
    skillScenarioRunning: "Running...",
    skillScenarioSummary: "Plugin Creator is wired to a fixed fixture task for AstraBridge's real-scenario dogfood flow.",
    skillScenarioBoundary: "This task only reads the fixed fixture brief and writes under PRIVATE/demo-runs/skills-plugin-creator-scenario/. It does not touch official Codex state.",
    skillScenarioNotRun: "No controlled task has been started from this panel yet. You can still inspect the fixed inputs, expected outputs, and the backend reference report from step 10.",
    skillScenarioLatestRunHint: "The latest execution result below is the evidence surface that step 12 will reuse for full in-app acceptance.",
    skillScenarioTriggerPath: "Trigger path",
    skillScenarioFixtureContract: "Fixture contract",
    skillScenarioBriefPath: "Fixed brief path",
    skillScenarioSuggestedReport: "Suggested report",
    skillScenarioReferenceReport: "Reference report",
    skillScenarioReferenceScreenshot: "Reference screenshot",
    skillScenarioRunRoot: "Run root",
    skillScenarioPluginRoot: "Plugin root",
    skillScenarioManifest: "Manifest path",
    skillScenarioMarketplace: "Marketplace path",
    skillScenarioLatestRun: "Latest execution",
    skillScenarioStatus: "Scenario status",
    skillScenarioExecutionId: "Execution ID",
    skillScenarioExecutionRoot: "Execution root",
    skillScenarioResultPath: "Result path",
    skillScenarioEventsPath: "Events path",
    skillScenarioReportSeedPath: "Report seed",
    skillScenarioFailureReason: "Failure reason",
    skillScenarioPreviewTitle: "Artifact preview",
    skillScenarioPreviewEmpty: "Run the controlled task first, then preview the generated manifest or marketplace output here.",
    skillScenarioPreviewLoading: "Loading preview...",
    skillScenarioPreviewManifest: "Preview manifest",
    skillScenarioPreviewMarketplace: "Preview marketplace",
    skillScenarioPreviewPath: "Preview path",
    skillScenarioPreviewKind: "Preview kind",
    skillScenarioPreviewSize: "Bytes",
  },
  "zh-CN": {
    title: "扩展",
    loading: "正在加载插件与技能清单...",
    unavailable: "插件与技能清单暂不可用。",
    summary: "查看 AstraBridge 托管运行时根目录中发现的 Codex 插件与技能。插件安装保持显式操作，部分技能会额外展示受控任务证据与启用控制。",
    summaryPlugins: "查看插件清单、来源边界和显式安装状态。安装始终先预览计划，再写入 AstraBridge 托管的隔离运行时。",
    summarySkills: "查看技能清单、所属插件、实际启用状态，以及真实场景狗粮验收使用的受控任务证据。",
    pluginList: "插件列表",
    skillList: "技能列表",
    pluginsCount: "插件",
    skillsCount: "技能",
    sourcesCount: "来源",
    installedCount: "已安装",
    availableCount: "待安装",
    attentionCount: "需关注",
    generatedAt: "生成时间",
    registryRefresh: "刷新清单",
    registryRefreshPending: "刷新中...",
    registryRefreshingHint: "正在刷新清单，并保留上一份已验证快照可见。",
    pluginDiscovery: "插件发现",
    skillDiscovery: "技能发现",
    inventory: "清单",
    inventoryPlugins: "插件",
    inventorySkills: "技能",
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
    enabled: "已启用",
    blocked: "已阻止",
    warning: "警告",
    compatible: "兼容",
    unknown: "未知",
    supported: "已支持",
    inherited: "继承",
    ready: "就绪",
    planned: "已计划",
    applied: "已执行",
    install: "安装",
    update: "更新",
    noop: "已是最新",
    unsupported: "不支持",
    updateAvailable: "可更新",
    noMatches: "当前筛选条件下没有匹配的插件或技能。",
    noPluginMatches: "当前筛选条件下没有匹配的插件。",
    noSkillMatches: "当前筛选条件下没有匹配的技能。",
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
    official: "官方",
    bundledLocal: "本地内置",
    generatedFallback: "生成占位",
    icon: "图标",
    iconProvenance: "图标来源",
    iconValidated: "图标已验证",
    asset: "资源",
    sourceKindLocal: "本地",
    sourceKindProjectLocal: "项目本地",
    sourceKindManual: "手动来源",
    sourceKindOfficial: "官方",
    sourceKindCurated: "精选来源",
    planTitle: "安装计划",
    planSummary: "在发生任何文件变更前预览安装或更新范围。",
    planWorkflow: "操作说明",
    planWorkflowBoundary: "所有插件写入都只会落在 AstraBridge 托管的隔离运行时目录和证据目录中。",
    planWorkflowIdle: "请先预览计划。只有在你明确点击执行后，AstraBridge 才会把插件写入隔离运行时。",
    planWorkflowInstall: "该插件已经具备安装条件。执行计划后会把文件复制进隔离运行时，并记录可回滚证据。",
    planWorkflowUpdate: "该插件存在更新路径。执行计划前会先捕获回滚快照，再替换隔离运行时中的版本。",
    planWorkflowNoop: "该插件已经是隔离运行时中的最新版本。需要检查来源、目标目录或回滚信息时，可以重新预览计划。",
    planWorkflowUnsupported: "当前只能查看该插件，不能直接执行安装。请先把来源镜像到 AstraBridge 托管的本地目录。",
    planWorkflowApplied: "最近一次执行结果显示在下方，报告路径仍保留在 AstraBridge 的证据目录中。",
    planAction: "动作",
    planReason: "原因",
    planSourceRoot: "来源根目录",
    planTargetRoot: "目标根目录",
    planRollback: "回滚快照",
    planPreview: "预览计划",
    planPreviewPending: "正在生成计划...",
    planNotLoaded: "还没有为这个插件生成安装或更新计划。",
    currentVersion: "当前版本",
    targetVersion: "目标版本",
    sourceFiles: "来源文件",
    targetFiles: "现有目标文件",
    plannedWrites: "计划写入",
    planErrors: "计划错误",
    planWarnings: "计划告警",
    rollbackFiles: "回滚捕获",
    rollbackStatus: "回滚状态",
    apps: "应用",
    applyAction: "执行",
    applyPending: "正在执行...",
    applyResult: "执行结果",
    executionStatus: "执行状态",
    reportPath: "报告路径",
    projectPreset: "项目预设",
    activePreset: "当前预设",
    presetPlugins: "预设插件",
    presetSkills: "预设技能",
    addToPreset: "加入项目预设",
    removeFromPreset: "移出项目预设",
    resetPreset: "重置预设",
    presetPending: "正在保存预设...",
    presetSummary: "项目内的插件和技能引用保存在 AstraBridge 项目文件中，不写入官方 Codex 状态。",
    skillControls: "技能控制",
    observedEnablement: "运行时观测",
    effectiveEnablement: "实际启用状态",
    globalDefault: "全局默认",
    projectOverride: "项目覆盖",
    enablementSourceLabel: "启用来源",
    enableGlobally: "全局启用",
    disableGlobally: "全局禁用",
    enableForProject: "本项目启用",
    disableForProject: "本项目禁用",
    useGlobalSetting: "使用全局设置",
    globalStatePath: "全局状态路径",
    projectStatePath: "项目状态路径",
    skillUpdatePending: "正在更新...",
    contributions: "贡献能力",
    pass: "通过",
    failed: "失败",
    timeout: "超时",
    skillScenarioTitle: "受控任务",
    skillScenarioBadge: "固定场景",
    skillScenarioRun: "运行受控任务",
    skillScenarioRunning: "正在运行...",
    skillScenarioSummary: "Plugin Creator 已绑定到 AstraBridge 真实场景狗粮验收使用的固定 fixture 任务。",
    skillScenarioBoundary: "该任务只会读取固定 brief，并且只写入 PRIVATE/demo-runs/skills-plugin-creator-scenario/ 下的证据目录，不会触碰官方 Codex 状态。",
    skillScenarioNotRun: "当前界面还没有触发过这个受控任务。你仍然可以先检查固定输入、预期输出，以及步骤 10 留下的后端参考报告。",
    skillScenarioLatestRunHint: "下方最近一次执行结果会作为步骤 12 完整 in-app 验收复用的证据面。",
    skillScenarioTriggerPath: "触发路径",
    skillScenarioFixtureContract: "契约文件",
    skillScenarioBriefPath: "固定 brief 路径",
    skillScenarioSuggestedReport: "建议报告路径",
    skillScenarioReferenceReport: "参考报告路径",
    skillScenarioReferenceScreenshot: "参考截图路径",
    skillScenarioRunRoot: "运行根目录",
    skillScenarioPluginRoot: "插件根目录",
    skillScenarioManifest: "Manifest 路径",
    skillScenarioMarketplace: "Marketplace 路径",
    skillScenarioLatestRun: "最近一次执行",
    skillScenarioStatus: "场景状态",
    skillScenarioExecutionId: "执行 ID",
    skillScenarioExecutionRoot: "执行目录",
    skillScenarioResultPath: "结果路径",
    skillScenarioEventsPath: "事件路径",
    skillScenarioReportSeedPath: "报告种子",
    skillScenarioFailureReason: "失败原因",
    skillScenarioPreviewTitle: "产物预览",
    skillScenarioPreviewEmpty: "先运行受控任务，再在这里预览生成的 manifest 或 marketplace 产物。",
    skillScenarioPreviewLoading: "正在加载预览...",
    skillScenarioPreviewManifest: "预览 Manifest",
    skillScenarioPreviewMarketplace: "预览 Marketplace",
    skillScenarioPreviewPath: "预览路径",
    skillScenarioPreviewKind: "预览类型",
    skillScenarioPreviewSize: "字节数",
  },
} as const;

type InventoryCopy = Record<keyof typeof LABELS.en, string>;

export function PluginSkillInventoryPanel({
  locale,
  snapshot,
  isLoading,
  error,
  project,
  initialKind = "all",
  onProjectChanged,
  onRegistryChanged,
}: {
  locale: LocaleCode;
  snapshot?: CodexPluginSkillRegistrySnapshot | null;
  isLoading: boolean;
  error?: unknown;
  project?: ProjectFile | null;
  initialKind?: InventoryKind;
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
  const [skillScenarioResults, setSkillScenarioResults] = useState<Record<string, SkillPluginCreatorScenarioExecution>>({});
  const [skillScenarioErrorRecordId, setSkillScenarioErrorRecordId] = useState<string | null>(null);
  const [skillScenarioError, setSkillScenarioError] = useState("");
  const [skillScenarioPendingRecordId, setSkillScenarioPendingRecordId] = useState<string | null>(null);
  const [artifactPreviewPath, setArtifactPreviewPath] = useState("");
  const [artifactPreview, setArtifactPreview] = useState<ProjectFilePreview | null>(null);
  const [artifactPreviewPending, setArtifactPreviewPending] = useState(false);
  const [artifactPreviewError, setArtifactPreviewError] = useState("");
  const [registryRefreshPending, setRegistryRefreshPending] = useState(false);
  const [registryRefreshError, setRegistryRefreshError] = useState("");

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
  const pluginRecordIds = useMemo(() => new Set((snapshot?.plugins ?? []).map((plugin) => plugin.record_id)), [snapshot?.plugins]);
  const skillRecordIds = useMemo(() => new Set((snapshot?.skills ?? []).map((skill) => skill.record_id)), [snapshot?.skills]);

  const filteredItems = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    return items.filter((item) => {
      if (kind === "plugins" && item.kind !== "plugin") return false;
      if (kind === "skills" && item.kind !== "skill") return false;
      if (status === "installed" && item.installStatus !== "installed") return false;
      if (status === "available" && !["available", "update_available"].includes(item.installStatus)) return false;
      if (status === "attention" && !item.attention) return false;
      if (status === "disabled" && !["disabled", "blocked"].includes(item.enablementStatus)) return false;
      if (!normalizedSearch) return true;
      return item.searchText.includes(normalizedSearch);
    });
  }, [items, kind, search, status]);

  useEffect(() => {
    setKind(initialKind);
  }, [initialKind]);

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
    setPluginPlans((current) => _filterRecordMap(current, pluginRecordIds));
    setPlanErrors((current) => _filterRecordMap(current, pluginRecordIds));
    setPlanPendingRecordId((current) => (current && pluginRecordIds.has(current) ? current : null));
    setApplyResults((current) => _filterRecordMap(current, pluginRecordIds));
    setApplyErrors((current) => _filterRecordMap(current, pluginRecordIds));
    setApplyPendingRecordId((current) => (current && pluginRecordIds.has(current) ? current : null));
    setSkillActionErrorRecordId((current) => (current && skillRecordIds.has(current) ? current : null));
    setSkillPendingActionKey((current) => {
      if (!current) return null;
      const separatorIndex = current.indexOf(":");
      if (separatorIndex <= 0) return null;
      const recordId = current.slice(0, separatorIndex);
      return skillRecordIds.has(recordId) ? current : null;
    });
    setSkillScenarioResults((current) => _filterRecordMap(current, skillRecordIds));
    setSkillScenarioErrorRecordId((current) => (current && skillRecordIds.has(current) ? current : null));
    setSkillScenarioPendingRecordId((current) => (current && skillRecordIds.has(current) ? current : null));
  }, [pluginRecordIds, skillRecordIds]);

  useEffect(() => {
    setArtifactPreviewPath("");
    setArtifactPreview(null);
    setArtifactPreviewPending(false);
    setArtifactPreviewError("");
  }, [selectedId, skillScenarioResults]);

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
  const selectedSkillScenarioResult = selected?.kind === "skill" ? skillScenarioResults[selected.skill.record_id] ?? null : null;
  const selectedSkillScenarioError = selected?.kind === "skill" && skillScenarioErrorRecordId === selected.skill.record_id ? skillScenarioError : "";
  const selectedSkillScenarioSpec = selected?.kind === "skill" ? _pluginCreatorScenarioSpec(selected.skill) : null;
  const unsupported = items.length === 0 && (pluginListStatus === "unsupported" || skillListStatus === "unsupported");
  const installedPluginCount = (snapshot.plugins ?? []).filter((plugin) => plugin.install_status === "installed").length;
  const availablePluginCount = (snapshot.plugins ?? []).filter((plugin) => ["available", "update_available"].includes(String(plugin.install_status || ""))).length;
  const attentionPluginCount = (snapshot.plugins ?? []).filter((plugin) => _needsAttention(
    String(plugin.install_status || "unknown"),
    String(plugin.enablement_status || "unknown"),
    String(plugin.compatibility_status || "unknown"),
    plugin.compatibility_warnings ?? [],
  )).length;
  const inventoryTitle = kind === "plugins" ? copy.inventoryPlugins : kind === "skills" ? copy.inventorySkills : copy.inventory;
  const inventorySummary = kind === "plugins" ? copy.summaryPlugins : kind === "skills" ? copy.summarySkills : copy.summary;
  const noMatchesText = kind === "plugins" ? copy.noPluginMatches : kind === "skills" ? copy.noSkillMatches : copy.noMatches;
  const selectedWorkflowMessage = selected?.kind === "plugin" ? _pluginWorkflowMessage(selected.plugin, selected.source, selectedPlan, copy) : "";
  const selectedContributionCount = selected
    ? selected.kind === "plugin"
      ? (selected.plugin.declared_mcp_servers?.length ?? 0)
        + (selected.plugin.declared_app_ids?.length ?? 0)
        + (selected.plugin.declared_hook_keys?.length ?? 0)
      : (selected.skill.trigger_hints?.length ?? 0) + (selected.skill.permission_hints?.length ?? 0)
    : 0;
  const selectedEnablementStatus = selected?.kind === "skill" ? _skillEffectiveStatus(selected.skill) : selected?.enablementStatus ?? "unknown";
  const selectedSkillEnablementNotice = selected?.kind === "skill" ? _skillEnablementNotice(selected.skill, copy) : null;

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

  async function handleRefreshRegistry() {
    if (!onRegistryChanged || registryRefreshPending) return;
    setRegistryRefreshPending(true);
    setRegistryRefreshError("");
    try {
      await onRegistryChanged();
    } catch (refreshError) {
      setRegistryRefreshError(String((refreshError as Error)?.message ?? refreshError ?? "Failed to refresh registry."));
    } finally {
      setRegistryRefreshPending(false);
    }
  }

  async function handleRunSkillScenario(skill: CodexSkillRegistryRecord) {
    setSkillScenarioPendingRecordId(skill.record_id);
    setSkillScenarioErrorRecordId(null);
    setSkillScenarioError("");
    try {
      const result = await api.runtimeSkillPluginCreatorFixtureScenario({
        skill_name: skill.skill_name,
      });
      setSkillScenarioResults((current) => ({ ...current, [skill.record_id]: result }));
    } catch (scenarioError) {
      setSkillScenarioErrorRecordId(skill.record_id);
      setSkillScenarioError(String((scenarioError as Error)?.message ?? scenarioError ?? "Failed to run controlled skill scenario."));
    } finally {
      setSkillScenarioPendingRecordId((current) => (current === skill.record_id ? null : current));
    }
  }

  async function handleLoadArtifactPreview(path: string) {
    const normalizedPath = path.trim();
    if (!normalizedPath) return;
    setArtifactPreviewPath(normalizedPath);
    setArtifactPreviewPending(true);
    setArtifactPreviewError("");
    try {
      const preview = await api.projectFileRead(normalizedPath);
      setArtifactPreview(preview);
    } catch (previewError) {
      setArtifactPreview(null);
      setArtifactPreviewError(String((previewError as Error)?.message ?? previewError ?? "Failed to load file preview."));
    } finally {
      setArtifactPreviewPending(false);
    }
  }

  return (
    <div className="manager-panel extensions-panel" data-testid="plugin-skill-inventory-panel">
      <div className="metadata-actions metadata-actions-compact">
        <div className="extensions-summary-copy">
          <span className="eyebrow">{copy.title}</span>
          <h3>{inventoryTitle}</h3>
          <p className="muted">{inventorySummary}</p>
          {isLoading ? <p className="muted">{copy.registryRefreshingHint}</p> : null}
          {registryRefreshError ? <p className="error-text">{registryRefreshError}</p> : null}
        </div>
        <div className="extensions-summary-actions">
          <button
            type="button"
            className="ghost-button compact-button"
            disabled={!onRegistryChanged || registryRefreshPending}
            onClick={() => void handleRefreshRegistry()}
          >
            {registryRefreshPending ? copy.registryRefreshPending : copy.registryRefresh}
          </button>
        </div>
        <div className="extensions-summary-bar">
          <div className="extensions-inline-actions extensions-summary-capabilities">
            <span className={`status-tag ${pluginListStatus === "supported" ? "capability-ok" : "capability-warn"}`}>
              {copy.pluginDiscovery}: {_statusLabel(pluginListStatus, copy)}
            </span>
            <span className={`status-tag ${skillListStatus === "supported" ? "capability-ok" : "capability-warn"}`}>
              {copy.skillDiscovery}: {_statusLabel(skillListStatus, copy)}
            </span>
          </div>
          <div className="extensions-summary-grid" aria-label={copy.inventory} data-testid="extensions-summary-grid">
            <span className="extensions-summary-stat" data-testid="extensions-summary-plugins">
              <span>{copy.pluginsCount}</span>
              <strong>{snapshot.plugins.length}</strong>
            </span>
            <span className="extensions-summary-stat" data-testid="extensions-summary-installed">
              <span>{copy.installedCount}</span>
              <strong>{installedPluginCount}</strong>
            </span>
            <span className="extensions-summary-stat" data-testid="extensions-summary-available">
              <span>{copy.availableCount}</span>
              <strong>{availablePluginCount}</strong>
            </span>
            <span className="extensions-summary-stat" data-testid="extensions-summary-attention">
              <span>{copy.attentionCount}</span>
              <strong>{attentionPluginCount}</strong>
            </span>
            <span className="extensions-summary-stat" data-testid="extensions-summary-sources">
              <span>{copy.sourcesCount}</span>
              <strong>{snapshot.source_catalogs.length}</strong>
            </span>
            <span className="extensions-summary-stat" data-testid="extensions-summary-skills-status">
              <span>{copy.skillList}</span>
              <strong>{_statusLabel(skillListStatus, copy)}</strong>
            </span>
          </div>
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
            <span>{copy.pluginList}: {_statusLabel(pluginListStatus, copy)}</span>
            <span>{copy.skillList}: {_statusLabel(skillListStatus, copy)}</span>
          </div>
        </section>
      ) : null}

      {project ? (
        <details className="manager-disclosure extensions-project-preset">
          <summary>
            <span>{copy.projectPreset}</span>
          </summary>
          <section className="metadata-section manager-disclosure-content">
          <div className="section-header">
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
        </details>
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
                    <span className="extensions-row-meta">
                      {item.kind === "plugin"
                        ? _pluginRowMeta(item.plugin, item.source, copy)
                        : _skillRowMeta(item.skill, item.source, copy)}
                    </span>
                    {item.description ? <span className="extensions-row-description">{item.description}</span> : null}
                    <span className="extensions-row-badges">
                      <span>{_statusLabel(item.installStatus, copy)}</span>
                      {item.enablementStatus !== "enabled" ? <span>{_statusLabel(item.enablementStatus, copy)}</span> : null}
                      {item.compatibilityStatus !== "compatible" ? <span>{_statusLabel(item.compatibilityStatus, copy)}</span> : null}
                      <span>{_sourceKindLabel(item.source?.kind, copy)}</span>
                    </span>
                  </div>
                </div>
              </button>
            ))}
            {!filteredItems.length ? <div className="metadata-section"><p className="muted">{noMatchesText}</p></div> : null}
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
                  <span className="status-tag">{_statusLabel(selected.installStatus, copy)}</span>
                  <span className="status-tag">{_statusLabel(selectedEnablementStatus, copy)}</span>
                  <span className={`status-tag ${selected.attention ? "capability-warn" : "capability-ok"}`}>{_statusLabel(selected.compatibilityStatus, copy)}</span>
                </div>
              </div>

              <section className="metadata-section">
                <h4>{copy.details}</h4>
                <div className="extensions-detail-grid">
                  <div><span>{copy.source}</span><strong>{selected.source?.display_name ?? copy.none}</strong></div>
                  <div><span>{copy.sourceCatalog}</span><strong>{_sourceKindLabel(selected.source?.kind, copy)}</strong></div>
                  <div><span>{copy.installStatus}</span><strong>{_statusLabel(selected.installStatus, copy)}</strong></div>
                  <div><span>{copy.enablement}</span><strong>{_statusLabel(selectedEnablementStatus, copy)}</strong></div>
                  <div><span>{copy.compatibility}</span><strong>{_statusLabel(selected.compatibilityStatus, copy)}</strong></div>
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

              <section className="metadata-section">
                <div className="section-header">
                  <h4>{copy.contributions}</h4>
                  <span className="status-tag">{selectedContributionCount}</span>
                </div>
                {selected.kind === "plugin" ? (
                  <>
                    <div className="extensions-detail-grid">
                      <div><span>{copy.declaredMcp}</span><strong>{selected.plugin.declared_mcp_servers?.length ?? 0}</strong></div>
                      <div><span>{copy.apps}</span><strong>{selected.plugin.declared_app_ids?.length ?? 0}</strong></div>
                      <div><span>{copy.declaredHooks}</span><strong>{selected.plugin.declared_hook_keys?.length ?? 0}</strong></div>
                      <div><span>{copy.permissions}</span><strong>{selected.plugin.permission_hints?.length ?? 0}</strong></div>
                    </div>
                    <div className="extensions-contribution-grid">
                      <div>
                        <h4>{copy.declaredMcp}</h4>
                        <div className="extensions-tag-list">
                          {_detailTags(selected.plugin.declared_mcp_servers, copy.none)}
                        </div>
                      </div>
                      <div>
                        <h4>{copy.apps}</h4>
                        <div className="extensions-tag-list">
                          {_detailTags(selected.plugin.declared_app_ids, copy.none)}
                        </div>
                      </div>
                      <div>
                        <h4>{copy.declaredHooks}</h4>
                        <div className="extensions-tag-list">
                          {_detailTags(selected.plugin.declared_hook_keys, copy.none)}
                        </div>
                      </div>
                      <div>
                        <h4>{copy.permissions}</h4>
                        <div className="extensions-tag-list">
                          {_detailTags(selected.plugin.permission_hints, copy.none)}
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="extensions-detail-grid">
                      <div><span>{copy.owningPlugin}</span><strong>{selected.skill.owner_plugin_id || copy.none}</strong></div>
                      <div><span>{copy.triggerHints}</span><strong>{selected.skill.trigger_hints?.length ?? 0}</strong></div>
                      <div><span>{copy.permissions}</span><strong>{selected.skill.permission_hints?.length ?? 0}</strong></div>
                      <div><span>{copy.enablementSourceLabel}</span><strong>{_statusLabel(selected.skill.enablement_source || "unknown", copy)}</strong></div>
                      <div><span>{copy.enablementReason}</span><strong>{_skillEnablementReasonLabel(selected.skill, copy)}</strong></div>
                    </div>
                    <div className="extensions-contribution-grid">
                      <div>
                        <h4>{copy.triggerHints}</h4>
                        <div className="extensions-tag-list">
                          {_detailTags(selected.skill.trigger_hints, copy.none)}
                        </div>
                      </div>
                      <div>
                        <h4>{copy.permissions}</h4>
                        <div className="extensions-tag-list">
                          {_detailTags(selected.skill.permission_hints, copy.none)}
                        </div>
                      </div>
                    </div>
                  </>
                )}
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
                  <div className="extensions-operation-callout">
                    <strong>{copy.planWorkflow}</strong>
                    <p>{copy.planWorkflowBoundary}</p>
                    <p>{selectedWorkflowMessage}</p>
                    {selectedApplyResult ? <p>{copy.planWorkflowApplied}</p> : null}
                  </div>
                  {selectedPlanError ? <p className="error-text">{selectedPlanError}</p> : null}
                  {selectedApplyError ? <p className="error-text">{selectedApplyError}</p> : null}
                  {!selectedPlan ? (
                    <p className="muted">{copy.planNotLoaded}</p>
                  ) : (
                    <>
                      <div className="extensions-detail-grid">
                        <div><span>{copy.planAction}</span><strong>{_statusLabel(selectedPlan.action, copy)}</strong></div>
                        <div><span>{copy.planReason}</span><strong>{_formatStatus(selectedPlan.reason)}</strong></div>
                        <div><span>{copy.currentVersion}</span><strong>{selectedPlan.versions.current_version || copy.none}</strong></div>
                        <div><span>{copy.targetVersion}</span><strong>{selectedPlan.versions.target_version || copy.none}</strong></div>
                        <div><span>{copy.source}</span><strong>{selectedPlan.source.display_name || copy.none}</strong></div>
                        <div><span>{copy.sourceCatalog}</span><strong>{_sourceKindLabel(selectedPlan.source.kind, copy)}</strong></div>
                        <div><span>{copy.planSourceRoot}</span><strong>{selectedPlan.files.source_root || selectedPlan.source.source_path || copy.none}</strong></div>
                        <div><span>{copy.planTargetRoot}</span><strong>{selectedPlan.files.target_root || copy.none}</strong></div>
                        <div><span>{copy.sourceUrl}</span><strong>{selectedPlan.source.source_url || copy.none}</strong></div>
                        <div><span>{copy.planRollback}</span><strong>{selectedPlan.rollback_snapshot.snapshot_id || copy.none}</strong></div>
                        <div><span>{copy.rollbackStatus}</span><strong>{_statusLabel(selectedPlan.rollback_snapshot.status, copy)}</strong></div>
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
                            <div><span>{copy.executionStatus}</span><strong>{_statusLabel(selectedApplyResult.status, copy)}</strong></div>
                            <div><span>{copy.planAction}</span><strong>{_statusLabel(selectedApplyResult.action, copy)}</strong></div>
                            <div><span>{copy.rollbackStatus}</span><strong>{_statusLabel(selectedApplyResult.rollback_snapshot.status, copy)}</strong></div>
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
                    <div><span>{copy.effectiveEnablement}</span><strong>{_statusLabel(_skillEffectiveStatus(selected.skill), copy)}</strong></div>
                    <div><span>{copy.observedEnablement}</span><strong>{_statusLabel(selected.skill.observed_enablement_status || selected.skill.enablement_status, copy)}</strong></div>
                    <div><span>{copy.globalDefault}</span><strong>{_statusLabel(_skillGlobalStatus(selected.skill), copy)}</strong></div>
                    <div><span>{copy.projectOverride}</span><strong>{_statusLabel(selected.skill.project_enablement_status || "unknown", copy)}</strong></div>
                    <div><span>{copy.enablementSourceLabel}</span><strong>{_statusLabel(selected.skill.enablement_source || "unknown", copy)}</strong></div>
                    <div><span>{copy.enablementReason}</span><strong>{_skillEnablementReasonLabel(selected.skill, copy)}</strong></div>
                    <div><span>{copy.owningPlugin}</span><strong>{selected.skill.owner_plugin_id || copy.none}</strong></div>
                  </div>
                  {selectedSkillEnablementNotice ? (
                    <div className="extensions-operation-callout">
                      <strong>{selectedSkillEnablementNotice.title}</strong>
                      <p>{selectedSkillEnablementNotice.detail}</p>
                    </div>
                  ) : null}
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

              {selected.kind === "skill" && selectedSkillScenarioSpec ? (
                <section className="metadata-section" data-testid="plugin-creator-skill-scenario-panel">
                  <div className="section-header">
                    <h4>{copy.skillScenarioTitle}</h4>
                    <div className="extensions-inline-actions">
                      <span className="status-tag capability-ok">{copy.skillScenarioBadge}</span>
                      <button
                        type="button"
                        className="primary-button compact-button"
                        disabled={skillScenarioPendingRecordId === selected.skill.record_id}
                        onClick={() => void handleRunSkillScenario(selected.skill)}
                      >
                        {skillScenarioPendingRecordId === selected.skill.record_id ? copy.skillScenarioRunning : copy.skillScenarioRun}
                      </button>
                    </div>
                  </div>
                  <div className="extensions-operation-callout">
                    <strong>{copy.skillScenarioSummary}</strong>
                    <p>{copy.skillScenarioBoundary}</p>
                    <p>{selectedSkillScenarioResult ? copy.skillScenarioLatestRunHint : copy.skillScenarioNotRun}</p>
                  </div>
                  {selectedSkillScenarioError ? <p className="error-text">{selectedSkillScenarioError}</p> : null}
                  <div className="extensions-detail-grid">
                    <div><span>{copy.skillScenarioTriggerPath}</span><strong>{selectedSkillScenarioSpec.triggerPath}</strong></div>
                    <div><span>{copy.skillScenarioFixtureContract}</span><strong className="extensions-value-code">{selectedSkillScenarioResult?.input.fixture_contract_path || selectedSkillScenarioSpec.fixtureContractPath}</strong></div>
                    <div><span>{copy.skillScenarioBriefPath}</span><strong className="extensions-value-code">{selectedSkillScenarioResult?.input.brief_path || selectedSkillScenarioSpec.briefPath}</strong></div>
                    <div><span>{copy.skillScenarioSuggestedReport}</span><strong className="extensions-value-code">{selectedSkillScenarioResult?.report_seed?.suggested_report_path || selectedSkillScenarioSpec.suggestedReportPath}</strong></div>
                    <div><span>{copy.skillScenarioReferenceReport}</span><strong className="extensions-value-code">{selectedSkillScenarioSpec.referenceReportPath}</strong></div>
                    <div><span>{copy.skillScenarioReferenceScreenshot}</span><strong className="extensions-value-code">{selectedSkillScenarioSpec.referenceScreenshotPath}</strong></div>
                  </div>
                  <div className="extensions-path-list">
                    <div><span>{copy.skillScenarioRunRoot}</span><strong className="extensions-value-code">{selectedSkillScenarioResult?.output.run_root || selectedSkillScenarioSpec.runRoot}</strong></div>
                    <div><span>{copy.skillScenarioPluginRoot}</span><strong className="extensions-value-code">{selectedSkillScenarioResult?.output.plugin_root || selectedSkillScenarioSpec.pluginRoot}</strong></div>
                    <div><span>{copy.skillScenarioManifest}</span><strong className="extensions-value-code">{selectedSkillScenarioResult?.output.manifest_path || selectedSkillScenarioSpec.manifestPath}</strong></div>
                    <div><span>{copy.skillScenarioMarketplace}</span><strong className="extensions-value-code">{selectedSkillScenarioResult?.output.marketplace_path || selectedSkillScenarioSpec.marketplacePath}</strong></div>
                  </div>

                  {selectedSkillScenarioResult ? (
                    <div className="extensions-execution-summary">
                      <h4>{copy.skillScenarioLatestRun}</h4>
                      <div className="extensions-detail-grid">
                        <div><span>{copy.skillScenarioStatus}</span><strong>{_statusLabel(selectedSkillScenarioResult.status, copy)}</strong></div>
                        <div><span>{copy.skillScenarioExecutionId}</span><strong>{selectedSkillScenarioResult.execution_id}</strong></div>
                        <div><span>{copy.generatedAt}</span><strong>{selectedSkillScenarioResult.completed_at || selectedSkillScenarioResult.started_at}</strong></div>
                        <div><span>{copy.executionStatus}</span><strong>{selectedSkillScenarioResult.checks.filter((check) => check.passed).length}/{selectedSkillScenarioResult.checks.length}</strong></div>
                      </div>
                      <div className="extensions-path-list">
                        <div><span>{copy.skillScenarioExecutionRoot}</span><strong className="extensions-value-code">{selectedSkillScenarioResult.output.execution_root}</strong></div>
                        <div><span>{copy.skillScenarioResultPath}</span><strong className="extensions-value-code">{selectedSkillScenarioResult.artifact_paths.result_path}</strong></div>
                        <div><span>{copy.skillScenarioEventsPath}</span><strong className="extensions-value-code">{selectedSkillScenarioResult.artifact_paths.events_path}</strong></div>
                        <div><span>{copy.skillScenarioReportSeedPath}</span><strong className="extensions-value-code">{selectedSkillScenarioResult.artifact_paths.report_seed_path}</strong></div>
                      </div>
                      {selectedSkillScenarioResult.failure_reason ? (
                        <div className="extensions-warning-list">
                          <div className="extensions-warning-item">
                            <strong>{copy.skillScenarioFailureReason}</strong>
                            <span>{selectedSkillScenarioResult.failure_reason}</span>
                          </div>
                        </div>
                      ) : null}
                      <div className="section-header">
                        <h4>{copy.skillScenarioPreviewTitle}</h4>
                        <div className="extensions-inline-actions">
                          <button
                            type="button"
                            className="ghost-button compact-button"
                            disabled={artifactPreviewPending}
                            onClick={() => void handleLoadArtifactPreview(selectedSkillScenarioResult.output.manifest_path)}
                          >
                            {copy.skillScenarioPreviewManifest}
                          </button>
                          <button
                            type="button"
                            className="ghost-button compact-button"
                            disabled={artifactPreviewPending}
                            onClick={() => void handleLoadArtifactPreview(selectedSkillScenarioResult.output.marketplace_path)}
                          >
                            {copy.skillScenarioPreviewMarketplace}
                          </button>
                        </div>
                      </div>
                      {artifactPreviewError ? <p className="error-text">{artifactPreviewError}</p> : null}
                      {artifactPreviewPending ? <p className="muted">{copy.skillScenarioPreviewLoading}</p> : null}
                      {!artifactPreviewPending && !artifactPreview && !artifactPreviewError ? <p className="muted">{copy.skillScenarioPreviewEmpty}</p> : null}
                      {artifactPreview ? (
                        <div className="extensions-artifact-preview" data-testid="plugin-creator-artifact-preview">
                          <div className="extensions-detail-grid">
                            <div><span>{copy.skillScenarioPreviewPath}</span><strong className="extensions-value-code">{artifactPreviewPath}</strong></div>
                            <div><span>{copy.skillScenarioPreviewKind}</span><strong>{artifactPreview.kind}</strong></div>
                            <div><span>{copy.skillScenarioPreviewSize}</span><strong>{artifactPreview.size}</strong></div>
                            <div><span>{copy.generatedAt}</span><strong>{new Date(artifactPreview.updated_at).toLocaleString()}</strong></div>
                          </div>
                          <ArtifactPreviewContent preview={artifactPreview} />
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </section>
              ) : null}

              <section className="metadata-section">
                <h4>{copy.provenance}</h4>
                <div className="extensions-detail-grid">
                  {_provenanceRows(selected.kind === "plugin" ? selected.plugin.provenance : selected.skill.provenance, copy).map((row) => (
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

function ArtifactPreviewContent({ preview }: { preview: ProjectFilePreview }) {
  if (preview.kind === "json") {
    return <pre className="extensions-artifact-code">{_formatJsonPreview(preview.content)}</pre>;
  }
  if (preview.kind === "markdown" || preview.kind === "text") {
    return <pre className="extensions-artifact-code">{preview.content || ""}</pre>;
  }
  if (preview.message) {
    return <p className="muted">{preview.message}</p>;
  }
  return <p className="muted">{preview.kind}</p>;
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

function _formatJsonPreview(content: string | undefined) {
  const text = String(content || "").trim();
  if (!text) return "";
  try {
    return JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    return text;
  }
}

function _skillItem(skill: CodexSkillRegistryRecord, source: CodexRegistrySourceCatalog | null): InventoryItem {
  const warnings = skill.compatibility_warnings ?? [];
  const notes = skill.notes ?? [];
  const description = skill.short_description?.trim() || skill.description?.trim() || "";
  const effectiveEnablementStatus = _skillEffectiveStatus(skill);
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
    enablementStatus: effectiveEnablementStatus,
    compatibilityStatus: String(skill.compatibility_status || "unknown"),
    warnings,
    notes,
    attention: _needsAttention(String(skill.install_status || "unknown"), effectiveEnablementStatus, String(skill.compatibility_status || "unknown"), warnings),
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

function _statusLabel(
  value: string | null | undefined,
  copy: {
    installed: string;
    available: string;
    attention: string;
    disabled: string;
    enabled: string;
    blocked: string;
    warning: string;
    compatible: string;
    unknown: string;
    supported: string;
    inherited: string;
    ready: string;
    planned: string;
    applied: string;
    install: string;
    update: string;
    noop: string;
    unsupported: string;
    updateAvailable: string;
    pass: string;
    failed: string;
    timeout: string;
    yes: string;
    no: string;
    none: string;
  },
) {
  const text = String(value || "unknown").trim() || "unknown";
  if (text === "installed") return copy.installed;
  if (text === "available") return copy.available;
  if (text === "update_available") return copy.updateAvailable;
  if (text === "attention") return copy.attention;
  if (text === "disabled") return copy.disabled;
  if (text === "enabled") return copy.enabled;
  if (text === "blocked") return copy.blocked;
  if (text === "warning") return copy.warning;
  if (text === "compatible") return copy.compatible;
  if (text === "unknown") return copy.unknown;
  if (text === "supported") return copy.supported;
  if (text === "inherited") return copy.inherited;
  if (text === "ready") return copy.ready;
  if (text === "planned") return copy.planned;
  if (text === "applied") return copy.applied;
  if (text === "install") return copy.install;
  if (text === "update") return copy.update;
  if (text === "noop") return copy.noop;
  if (text === "unsupported") return copy.unsupported;
  if (text === "pass") return copy.pass;
  if (text === "failed" || text === "fail") return copy.failed;
  if (text === "timeout") return copy.timeout;
  if (text === "yes") return copy.yes;
  if (text === "no") return copy.no;
  if (text === "none") return copy.none;
  return _formatStatus(text);
}

function _pluginCreatorScenarioSpec(skill: CodexSkillRegistryRecord): PluginCreatorScenarioSpec | null {
  return String(skill.skill_name || "").trim() === "plugin-creator" ? PLUGIN_CREATOR_SCENARIO_SPEC : null;
}

function _sourceKindLabel(
  value: string | null | undefined,
  copy: {
    sourceKindLocal: string;
    sourceKindProjectLocal: string;
    sourceKindManual: string;
    sourceKindOfficial: string;
    sourceKindCurated: string;
    none: string;
  },
) {
  if (!value) return copy.none;
  if (value === "local") return copy.sourceKindLocal;
  if (value === "project_local") return copy.sourceKindProjectLocal;
  if (value === "manual") return copy.sourceKindManual;
  if (value === "official") return copy.sourceKindOfficial;
  if (value === "curated") return copy.sourceKindCurated;
  return _formatStatus(value);
}

function _pluginRowMeta(
  plugin: CodexPluginRegistryRecord,
  source: CodexRegistrySourceCatalog | null,
  copy: {
    versions: string;
    source: string;
    none: string;
  },
) {
  return `${copy.versions}: ${_pluginVersions(plugin) || copy.none} · ${copy.source}: ${source?.display_name || copy.none}`;
}

function _skillRowMeta(
  skill: CodexSkillRegistryRecord,
  source: CodexRegistrySourceCatalog | null,
  copy: {
    owningPlugin: string;
    source: string;
    none: string;
  },
) {
  return `${copy.owningPlugin}: ${skill.owner_plugin_id || copy.none} · ${copy.source}: ${source?.display_name || copy.none}`;
}

function _skillEnablementReasonLabel(skill: CodexSkillRegistryRecord, copy: InventoryCopy) {
  const notes = new Set(skill.notes ?? []);
  if (notes.has("enablement_pending_user_approval")) return copy.waitingApproval;
  if (_skillEffectiveStatus(skill) === "blocked") {
    return skill.enablement_block_reason ? _formatStatus(skill.enablement_block_reason) : copy.blockedByOwner;
  }
  if (String(skill.project_enablement_status || "unknown") === "disabled") return copy.disabledByProject;
  if (_skillGlobalStatus(skill) === "disabled") return copy.disabledByGlobal;
  return _statusLabel(skill.enablement_source || "unknown", copy);
}

function _skillEnablementNotice(skill: CodexSkillRegistryRecord, copy: InventoryCopy) {
  const notes = new Set(skill.notes ?? []);
  if (notes.has("enablement_pending_user_approval")) {
    return {
      title: copy.waitingApproval,
      detail: copy.waitingApprovalHint,
    };
  }
  if (_skillEffectiveStatus(skill) === "blocked") {
    const blockReason = skill.enablement_block_reason ? _formatStatus(skill.enablement_block_reason) : "";
    return {
      title: copy.blockedByOwner,
      detail: blockReason ? `${copy.blockedByOwnerHint} (${blockReason})` : copy.blockedByOwnerHint,
    };
  }
  if (String(skill.project_enablement_status || "unknown") === "disabled") {
    return {
      title: copy.disabledByProject,
      detail: copy.disabledByProjectHint,
    };
  }
  if (_skillGlobalStatus(skill) === "disabled") {
    return {
      title: copy.disabledByGlobal,
      detail: copy.disabledByGlobalHint,
    };
  }
  return null;
}

function _pluginWorkflowMessage(
  plugin: CodexPluginRegistryRecord,
  source: CodexRegistrySourceCatalog | null,
  plan: CodexPluginInstallPlan | null,
  copy: {
    planWorkflowIdle: string;
    planWorkflowInstall: string;
    planWorkflowUpdate: string;
    planWorkflowNoop: string;
    planWorkflowUnsupported: string;
  },
) {
  const action = String(plan?.action || "").trim();
  if (action === "install") return copy.planWorkflowInstall;
  if (action === "update") return copy.planWorkflowUpdate;
  if (action === "noop") return copy.planWorkflowNoop;
  if (action === "unsupported") return copy.planWorkflowUnsupported;
  const installStatus = String(plugin.install_status || "unknown");
  if (installStatus === "update_available") return copy.planWorkflowUpdate;
  if (installStatus === "installed") return copy.planWorkflowNoop;
  if (["local", "project_local", "manual"].includes(String(source?.kind || ""))) return copy.planWorkflowInstall;
  if (installStatus === "available") return copy.planWorkflowIdle;
  return copy.planWorkflowUnsupported;
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

function _filterRecordMap<T>(value: Record<string, T>, allowedRecordIds: Set<string>) {
  const entries = Object.entries(value).filter(([recordId]) => allowedRecordIds.has(recordId));
  return entries.length === Object.keys(value).length ? value : Object.fromEntries(entries);
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
  copy: {
    manifestPath: string;
    sourcePath: string;
    sourceUrl: string;
    relativeRoot: string;
    checksum: string;
    none: string;
  },
) {
  const checksum = provenance?.checksum_algorithm && provenance?.checksum_value ? `${provenance.checksum_algorithm}:${provenance.checksum_value}` : copy.none;
  return [
    { label: copy.manifestPath, value: provenance?.manifest_path || copy.none },
    { label: copy.sourcePath, value: provenance?.source_path || copy.none },
    { label: copy.sourceUrl, value: provenance?.source_url || copy.none },
    { label: copy.relativeRoot, value: provenance?.relative_root || copy.none },
    { label: copy.checksum, value: checksum },
  ];
}
