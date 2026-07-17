import {
  AudioLines,
  ArrowLeft,
  ArrowRight,
  Braces,
  Boxes,
  ChevronDown,
  ChevronRight,
  Compass,
  Database,
  FileDown,
  FileJson,
  FileText,
  FileUp,
  GitBranch,
  GitCompareArrows,
  Image as ImageIcon,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
  ScanSearch,
  Play,
  Plus,
  Repeat,
  Save,
  Sparkles,
  SquareStack,
  TestTubeDiagonal,
  Undo2,
  Video,
  X,
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type DragEvent as ReactDragEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";
import { RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import { Bot, Eye, Lock, Search, ShieldCheck, Wrench } from "lucide-react";

import type {
  LocaleCode,
  NodeTypeRegistrySnapshot,
  TaskGraphContextPolicy,
  TaskGraphDefinition,
  TaskGraphDryRunResult,
  TaskGraphEdge,
  TaskGraphNode,
  TaskGraphNodePosition,
  TaskGraphRunRef,
  TaskGraphSnapshotRef,
  TaskGraphRunTimelineEvent,
  TaskGraphTemplateSummary,
} from "../../types";
import { isTaskGraphRunRefStale } from "./taskGraphRunRefs";
import { TaskGraphSchemaForm } from "./TaskGraphSchemaForm";
import {
  buildTaskGraphNodeRegistryUi,
  taskGraphPaletteMeta,
} from "./taskGraphNodeRegistryUi";

type TaskGraphWorkspaceProps = {
  locale: LocaleCode;
  templates: TaskGraphTemplateSummary[];
  graph: TaskGraphDefinition | null;
  selectedNodeId: string | null;
  selectedEdgeId: string | null;
  providerOptions: string[];
  modelSuggestions: string[];
  nodeTypeRegistry?: NodeTypeRegistrySnapshot | null;
  nodeSaveError: string | null;
  edgeSaveError: string | null;
  dryRunResult: TaskGraphDryRunResult | null;
  dryRunError: string | null;
  reportHref: string | null;
  latestRunRef: TaskGraphRunRef | null;
  artifactHrefFor: (path: string) => string;
  onInspectArtifactPath?: (path: string) => void;
  onSelectNode: (nodeId: string) => void;
  onSelectEdge: (edgeId: string) => void;
  onInstantiateTemplate: (templateId: string) => void;
  onCreateNode: (payload: {
    kind: string;
    position?: TaskGraphNodePosition | null;
  }) => void;
  onMoveNode: (nodeId: string, position: TaskGraphNodePosition) => void;
  onSaveNode: (
    nodeId: string,
    configuration: {
      label: string;
      provider_id: string;
      model_id: string;
      reasoning_effort: string;
      permission_mode: string;
      collaboration_mode: string;
      execution_backend: string;
      human_summary_template: string;
      machine_result_schema: Record<string, unknown>;
      execution_policy: Record<string, unknown>;
      output_contract: Record<string, unknown>;
      approval_gate?: Record<string, unknown>;
      ui_hints: Record<string, unknown>;
    },
  ) => void;
  onSaveEdge: (payload: {
    edge_id?: string;
    from_node_id: string;
    to_node_id: string;
    edge_type: string;
    handoff_contract?: TaskGraphEdge["handoff_contract"];
    context_policy: TaskGraphContextPolicy;
    status?: string;
  }) => void;
  onDeleteEdge: (edgeId: string) => void;
  onRunDryRun: (payload: { tokenBudget: number }) => void;
  onRunLive: (payload: { tokenBudget: number }) => void;
  onRunFixture: () => void;
  onRunCancellableFixture: () => void;
  onCancelLatestRun: () => void;
  onRecoverLatestRun: (payload: {
    strategy:
      | "resume_run"
      | "retry_failed_nodes"
      | "rerun_selected_nodes"
      | "partial_execution";
    selectedNodeIds?: string[];
  }) => void;
  onApprovePendingRun: () => void;
  onRejectPendingRun: () => void;
  onImportGraph: () => void;
  onExportGraph: () => void;
  snapshotRefs: TaskGraphSnapshotRef[];
  selectedSnapshotId: string | null;
  onSelectSnapshot: (snapshotId: string) => void;
  onCreateSnapshot: () => void;
  onCompareSnapshot: () => void;
  onRollbackSnapshot: () => void;
  onClose: () => void;
  importExportError: string | null;
  lastImportedPath: string | null;
  lastExportedPath: string | null;
  lastExportPreview: string | null;
  snapshotError: string | null;
  snapshotStatus: string | null;
  snapshotDiffMarkdown: string | null;
  isInstantiating: boolean;
  isLoadingTemplates: boolean;
  isLoadingGraph: boolean;
  isSavingNode: boolean;
  isSavingEdge: boolean;
  isDryRunPending: boolean;
  isLiveRunPending: boolean;
  showLiveRunPendingChrome?: boolean;
  isFixtureRunPending: boolean;
  runActionDisabledReason?: string | null;
  isRunCancellationPending: boolean;
  isRunRecoveryPending: boolean;
  isApprovalDecisionPending: boolean;
  isImportingGraph: boolean;
  isExportingGraph: boolean;
  isSnapshotPending: boolean;
  isSnapshotDiffPending: boolean;
  isSnapshotRollbackPending: boolean;
};

type NodeDraft = {
  label: string;
  provider_id: string;
  model_id: string;
  reasoning_effort: string;
  permission_mode: string;
  collaboration_mode: string;
  execution_backend: string;
  context_policy_preset: string;
  memory_policy_preset: string;
  human_summary_template: string;
  machine_result_schema_text: string;
  artifact_outputs_text: string;
  artifact_only: boolean;
  human_summary_required: boolean;
  allow_provider_calls: boolean;
  allow_code_changes: boolean;
  allow_install: boolean;
  requires_human_approval: boolean;
  approval_review_kind: string;
  node_type_config: Record<string, unknown>;
};

type EdgeDraft = {
  from_node_id: string;
  to_node_id: string;
  edge_type: string;
  handoff_message_template: string;
  required_output_schema_refs_text: string;
  include_message_machine_result: boolean;
  include_message_human_summary: boolean;
  include_message_artifact_ref: boolean;
  include_message_structured_json: boolean;
  include_message_text: boolean;
  history_mode: string;
  artifact_mode: string;
  history_length: string;
  summary_strategy: string;
  include_machine_results: boolean;
  include_human_summaries: boolean;
  exclude_private_memory: boolean;
  included_artifacts_text: string;
  resource_refs_text: string;
};

type DragState = {
  pointerId: number;
  nodeId: string;
  startX: number;
  startY: number;
  originX: number;
  originY: number;
};

type PanelResizeState = {
  side: "left";
  startX: number;
  startWidth: number;
};

type SidebarPaneId = "nodes" | "edges";

type VariablePreviewEntry = {
  token: string;
  preview: string;
};

const REASONING_OPTIONS = ["off", "minimal", "low", "medium", "high", "xhigh"];
const PERMISSION_OPTIONS = ["ask", "auto", "full"];
const COLLABORATION_OPTIONS = ["default", "plan"];
const BACKEND_OPTIONS = ["app_server", "native_kernel"];
const MEMORY_POLICY_OPTIONS = [
  { value: "default", label: "Shared lane" },
  { value: "ephemeral", label: "Ephemeral" },
  { value: "private_only", label: "Private only" },
];
const APPROVAL_KIND_OPTIONS = [
  "human_gate",
  "policy_gate",
  "provider_call_gate",
  "filesystem_write_gate",
  "external_write_gate",
  "install_gate",
];
const CONTEXT_POLICY_OPTIONS = [
  { value: "task_digest", label: "Task digest" },
  { value: "latest_summary_only", label: "Latest summary only" },
  { value: "artifact_first", label: "Artifact first" },
  { value: "isolated_artifacts_only", label: "Artifacts only" },
];
const EDGE_TYPE_OPTIONS = [
  "context_handoff",
  "artifact_handoff",
  "control_dependency",
  "approval_dependency",
  "fanout_branch",
  "fanin_merge",
];
const EDGE_HISTORY_OPTIONS = [
  "none",
  "last_n_messages",
  "latest_summary_only",
  "latest_machine_result_only",
  "explicit_refs_only",
];
const EDGE_ARTIFACT_OPTIONS = [
  "none",
  "explicit_artifacts",
  "latest_matching_kind",
  "required_output_only",
];
const EDGE_SUMMARY_OPTIONS = [
  "no_summary",
  "human_summary_only",
  "machine_result_only",
  "human_and_machine",
];
const NODE_CARD_WIDTH = 152;
const NODE_CARD_HEIGHT = 60;
const NODE_EDGE_ANCHOR_X = NODE_CARD_WIDTH / 2;
const NODE_EDGE_ANCHOR_Y = NODE_CARD_HEIGHT / 2;
const STAGE_PADDING = 32;
const MIN_STAGE_WIDTH = 640;
const MIN_STAGE_HEIGHT = 512;
const MIN_CANVAS_SCALE = 0.55;
const MAX_CANVAS_SCALE = 1.6;
const DEFAULT_CANVAS_SCALE = 1;
const TASK_GRAPH_SIDEBAR_WIDTH_STORAGE_KEY =
  "astrabridge.task_graph.sidebar_width";
const TASK_GRAPH_WORKSPACE_STATE_STORAGE_KEY_PREFIX =
  "astrabridge.task_graph.workspace_state";
const DEFAULT_TASK_GRAPH_SIDEBAR_WIDTH = 60;
const MIN_TASK_GRAPH_SIDEBAR_WIDTH = 52;
const MAX_VISIBLE_PORT_PREVIEW = 3;
const MAX_DISCLOSURE_PREVIEW_ITEMS = 3;

function buildDisclosurePreview<T>(
  items: readonly T[],
  expanded: boolean,
  limit = MAX_DISCLOSURE_PREVIEW_ITEMS,
): { visibleItems: readonly T[]; hiddenCount: number } {
  const hiddenCount = Math.max(0, items.length - limit);
  if (expanded || hiddenCount === 0) {
    return { visibleItems: items, hiddenCount };
  }
  return {
    visibleItems: items.slice(0, limit),
    hiddenCount,
  };
}

function summarizeDisclosureStrings(items: readonly string[]) {
  const indexByLabel = new Map<string, number>();
  const ordered: Array<{ label: string; count: number }> = [];
  for (const rawItem of items) {
    const label = String(rawItem || "")
      .replace(/\s+/g, " ")
      .replace(/\s+([,.;:!?])/g, "$1")
      .trim();
    if (!label) continue;
    const existingIndex = indexByLabel.get(label);
    if (existingIndex !== undefined) {
      ordered[existingIndex]!.count += 1;
      continue;
    }
    indexByLabel.set(label, ordered.length);
    ordered.push({ label, count: 1 });
  }
  return ordered;
}

function disclosureToggleLabel(
  locale: LocaleCode,
  expanded: boolean,
  hiddenCount: number,
  copy: { showLess: string },
) {
  if (expanded) return copy.showLess;
  return locale === "zh-CN" ? `还有 ${hiddenCount} 条` : `${hiddenCount} more`;
}

function disclosureToggleText(
  expanded: boolean,
  hiddenCount: number,
  copy: { showLess: string },
) {
  if (expanded) return copy.showLess;
  return `+${hiddenCount}`;
}

function disclosurePreviewSummary(
  visibleCount: number,
  totalCount: number,
  locale: LocaleCode,
) {
  if (totalCount <= visibleCount) {
    return locale === "zh-CN"
      ? `显示全部 ${totalCount} 项`
      : `Showing all ${totalCount}`;
  }
  return locale === "zh-CN"
    ? `显示前 ${visibleCount} 项，共 ${totalCount} 项`
    : `Showing ${visibleCount} of ${totalCount}`;
}

type TaskGraphWorkspaceStoredState = {
  sidebarExpanded: boolean;
  inspectorExpanded: boolean;
  inspectorWorkspace: "selection" | "run";
  readinessExpanded: boolean;
  latestRunExpanded: boolean;
  recoveryExpanded: boolean;
};

export function TaskGraphWorkspace({
  locale,
  templates: rawTemplates,
  graph,
  selectedNodeId,
  selectedEdgeId,
  providerOptions: rawProviderOptions,
  modelSuggestions: rawModelSuggestions,
  nodeTypeRegistry,
  nodeSaveError,
  edgeSaveError,
  dryRunResult,
  dryRunError,
  reportHref,
  latestRunRef,
  artifactHrefFor,
  onInspectArtifactPath,
  onSelectNode,
  onSelectEdge,
  onInstantiateTemplate,
  onCreateNode,
  onMoveNode,
  onSaveNode,
  onSaveEdge,
  onDeleteEdge,
  onRunDryRun,
  onRunLive,
  onRunFixture,
  onRunCancellableFixture,
  onCancelLatestRun,
  onRecoverLatestRun,
  onApprovePendingRun,
  onRejectPendingRun,
  onImportGraph,
  onExportGraph,
  snapshotRefs: rawSnapshotRefs,
  selectedSnapshotId,
  onSelectSnapshot,
  onCreateSnapshot,
  onCompareSnapshot,
  onRollbackSnapshot,
  onClose,
  importExportError,
  lastImportedPath,
  lastExportedPath,
  lastExportPreview,
  snapshotError,
  snapshotStatus,
  snapshotDiffMarkdown,
  isInstantiating,
  isLoadingTemplates,
  isLoadingGraph,
  isSavingNode,
  isSavingEdge,
  isDryRunPending,
  isLiveRunPending,
  showLiveRunPendingChrome,
  isFixtureRunPending,
  runActionDisabledReason,
  isRunCancellationPending,
  isRunRecoveryPending,
  isApprovalDecisionPending,
  isImportingGraph,
  isExportingGraph,
  isSnapshotPending,
  isSnapshotDiffPending,
  isSnapshotRollbackPending,
}: TaskGraphWorkspaceProps) {
  const templates = Array.isArray(rawTemplates) ? rawTemplates : [];
  const providerOptions = Array.isArray(rawProviderOptions)
    ? rawProviderOptions
    : [];
  const modelSuggestions = Array.isArray(rawModelSuggestions)
    ? rawModelSuggestions
    : [];
  const snapshotRefs = Array.isArray(rawSnapshotRefs) ? rawSnapshotRefs : [];
  const copy =
    locale === "zh-CN"
      ? {
          workspace: "\u4efb\u52a1\u56fe",
          chooseTemplate: "\u9009\u62e9\u6a21\u677f\u5f00\u59cb\u89c4\u5212",
          backToChat: "\u8fd4\u56de\u5bf9\u8bdd",
          templates: "\u6a21\u677f",
          presetTemplates: "\u5b98\u65b9\u9884\u8bbe",
          customTemplates: "\u81ea\u5b9a\u4e49\u6a21\u677f",
          presetTemplatesHint:
            "\u6309\u5e38\u89c1\u4efb\u52a1\u8def\u5f84\u6574\u7406\u597d\u7684\u8d77\u6b65\u6a21\u677f\u3002",
          customTemplatesHint:
            "\u4f60\u81ea\u5df1\u4fdd\u5b58\u6216\u8c03\u6574\u8fc7\u7684\u6a21\u677f\u3002",
          noCustomTemplates:
            "\u5f53\u524d\u8fd8\u6ca1\u6709\u81ea\u5b9a\u4e49\u6a21\u677f\u3002",
          currentTemplate: "\u5f53\u524d\u4efb\u52a1",
          templateStructure: "\u7ed3\u6784",
          loadingTemplates: "\u6b63\u5728\u52a0\u8f7d\u6a21\u677f...",
          noTemplates: "\u5f53\u524d\u6ca1\u6709\u53ef\u7528\u6a21\u677f\u3002",
          nodePalette: "\u8282\u70b9",
          addNode: "\u6dfb\u52a0\u8282\u70b9",
          currentNodes: "\u5f53\u524d\u8282\u70b9",
          browseNodes:
            "\u5148\u4ece\u9876\u90e8\u6a21\u677f\u6309\u94ae\u5b9e\u4f8b\u5316\u4e00\u4e2a\u6a21\u677f\uff0c\u518d\u6d4f\u89c8\u8282\u70b9\u3002",
          edges: "\u8fb9",
          noEdges: "\u5f53\u524d\u8fd8\u6ca1\u6709\u8fb9\u3002",
          canvas: "\u753b\u5e03",
          loadingGraph: "\u6b63\u5728\u52a0\u8f7d\u4efb\u52a1\u56fe...",
          noGraph: "\u8fd8\u6ca1\u6709\u4efb\u52a1\u56fe",
          noGraphHint:
            "\u5148\u4ece\u9876\u90e8\u6a21\u677f\u6309\u94ae\u9009\u4e00\u4e2a\u8d77\u70b9\uff0c\u518d\u5728\u753b\u5e03\u4e0a\u7ee7\u7eed\u7ec6\u5316\u3002",
          inspector: "\u68c0\u67e5\u5668",
          selectNode:
            "\u9009\u62e9\u4e00\u4e2a\u8282\u70b9\u6216\u8fb9\u6765\u67e5\u770b\u548c\u7f16\u8f91\u914d\u7f6e\u3002",
          roleLabel: "\u89d2\u8272\u6807\u7b7e",
          unspecified: "\u672a\u6307\u5b9a",
          provider: "Provider",
          model: "\u6a21\u578b",
          reasoning: "\u63a8\u7406\u5f3a\u5ea6",
          permission: "\u6743\u9650",
          collaboration: "\u534f\u4f5c\u6a21\u5f0f",
          backend: "\u6267\u884c\u540e\u7aef",
          contextPolicy: "\u4e0a\u4e0b\u6587\u7b56\u7565",
          memoryPolicy: "\u8bb0\u5fc6\u7b56\u7565",
          promptAndOutput: "\u63d0\u793a\u8bcd\u4e0e\u8f93\u51fa",
          toolsAndApproval: "\u5de5\u5177\u4e0e\u5ba1\u6279",
          promptTemplate: "\u63d0\u793a\u8bcd\u6a21\u677f",
          promptVariables: "\u53ef\u7528\u53d8\u91cf",
          insertVariable: "\u63d2\u5165\u53d8\u91cf",
          promptPreview: "\u9884\u89c8",
          payloadPreview: "Payload \u9884\u89c8",
          outputSchema: "\u8f93\u51fa Schema",
          artifactOutputs: "\u4ea7\u7269\u8f93\u51fa",
          artifactOnly: "\u4ec5\u4ea7\u7269",
          humanSummaryRequired: "\u9700\u8981\u4eba\u5de5\u6458\u8981",
          allowProviderCalls: "\u5141\u8bb8 provider \u8c03\u7528",
          allowCodeChanges: "\u5141\u8bb8\u4fee\u6539\u4ee3\u7801",
          allowInstall: "\u5141\u8bb8\u5b89\u88c5\u4f9d\u8d56",
          requiresApproval: "\u9700\u8981\u4eba\u5de5\u5ba1\u6279",
          approvalKind: "\u5ba1\u6279\u7c7b\u578b",
          defaultApprovalKind: "\u9009\u62e9\u5ba1\u6279\u7c7b\u578b",
          advancedNodeTitle:
            "\u5c55\u5f00\u8282\u70b9\u7684 prompt\u3001schema\u3001tool \u548c approval \u8bbe\u7f6e\u3002",
          invalidPromptVariable:
            "\u63d0\u793a\u8bcd\u91cc\u542b\u6709\u672a\u77e5\u53d8\u91cf\u3002",
          invalidSchema:
            "\u8f93\u51fa schema \u5fc5\u987b\u662f\u5408\u6cd5\u7684 JSON \u5bf9\u8c61\u3002",
          unsafeToolPolicy:
            "\u5f00\u542f\u4ee3\u7801\u4fee\u6539\u6216\u5b89\u88c5\u65f6\uff0c\u5fc5\u987b\u6253\u5f00\u4eba\u5de5\u5ba1\u6279\u3002",
          missingApprovalKind:
            "\u5f00\u542f\u4eba\u5de5\u5ba1\u6279\u540e\uff0c\u9700\u8981\u9009\u62e9\u5ba1\u6279\u7c7b\u578b\u3002",
          noPromptPreview:
            "\u9009\u4e2d\u7684\u53d8\u91cf\u4f1a\u5728\u8fd9\u91cc\u751f\u6210\u63d0\u793a\u8bcd\u9884\u89c8\u3002",
          noPayloadPreview:
            "\u9009\u4e2d\u8282\u70b9\u6216\u8fb9\u540e\uff0c\u8fd9\u91cc\u4f1a\u9884\u89c8\u53d1\u9001\u7ed9\u4e0b\u6e38 agent \u7684\u7ed3\u6784\u5316 payload\u3002",
          runFixture: "\u5939\u5177\u8fd0\u884c",
          runCancellableFixture: "\u53ef\u53d6\u6d88\u5939\u5177",
          dryRun: "Dry-run",
          runLive: "\u76f4\u63a5\u8fd0\u884c",
          runningLive: "\u6b63\u5728\u542f\u52a8\u76f4\u63a5\u8fd0\u884c...",
          runningFixture: "\u6b63\u5728\u8fd0\u884c\u5939\u5177...",
          runningDryRun: "\u6b63\u5728\u6267\u884c dry-run...",
          importGraph: "导入",
          exportGraph: "导出",
          snapshotGraph: "快照",
          creatingSnapshot: "正在快照...",
          comparingSnapshot: "正在对比...",
          compareSnapshot: "对比",
          rollbackSnapshot: "回滚",
          rollingBackSnapshot: "正在回滚...",
          recentSnapshots: "最近快照",
          showMore: "展开",
          showLess: "收起",
          currentGraphDiff: "与当前图对比",
          snapshotDiff: "快照差异",
          importingGraph: "正在导入...",
          exportingGraph: "正在导出...",
          importedGraph: "已导入",
          exportedGraph: "已导出",
          exportPreview: "导出预览",
          lines: "行",
          templatesHelp:
            "\u4ece\u6a21\u677f\u5f00\u59cb\uff0c\u800c\u4e0d\u662f\u4ece\u7a7a\u767d\u753b\u5e03\u5f00\u59cb\u3002",
          templateDetails: "\u6a21\u677f\u8be6\u60c5",
          useTemplate: "\u5b9e\u4f8b\u5316\u6a21\u677f",
          templatePreview: "\u9884\u89c8",
          recommendedProviders: "\u63a8\u8350 Provider",
          recommendedModels: "\u63a8\u8350\u6a21\u578b",
          expectedArtifacts: "\u9884\u671f\u4ea7\u7269",
          templatePreflight: "\u8fd0\u884c\u524d\u8981\u70b9",
          templateConstraints: "\u7ea6\u675f",
          blankTemplateHint:
            "\u5148\u9884\u89c8\u6a21\u677f\uff0c\u518d\u5b9e\u4f8b\u5316\u5230\u753b\u5e03\u3002",
          createEdgeTitle:
            "\u521b\u5efa\u65b0\u7684\u8282\u70b9\u8fde\u7ebf\uff0c\u5e76\u7f16\u8f91\u5b83\u7684\u4e0a\u4e0b\u6587\u7b56\u7565\u3002",
          paletteHint:
            "\u70b9\u51fb\u76f4\u63a5\u6dfb\u52a0\uff0c\u6216\u62d6\u62fd\u5230\u753b\u5e03\u4e0a\u653e\u7f6e\u3002",
          incompleteNodeWarning:
            "\u8fd9\u4e2a agent \u8fd8\u6ca1\u6709 provider \u548c model\uff0c\u8fd0\u884c\u524d\u9700\u8981\u5728\u68c0\u67e5\u5668\u91cc\u8865\u5168\u3002",
          nodeMode: "\u8282\u70b9",
          nodeModeTitle:
            "\u67e5\u770b\u5e76\u7f16\u8f91\u6240\u9009\u8282\u70b9\u7684 provider\u3001\u6a21\u578b\u548c\u6267\u884c\u8bbe\u7f6e\u3002",
          edgeMode: "\u8fb9",
          edgeModeTitle:
            "\u67e5\u770b\u5e76\u7f16\u8f91\u4e0a\u4e0b\u6587\u5982\u4f55\u5728\u8282\u70b9\u4e4b\u95f4\u4f20\u9012\u3002",
          runReadiness: "\u8fd0\u884c\u68c0\u67e5",
          openReport: "\u6253\u5f00\u62a5\u544a",
          noWarnings: "\u6ca1\u6709\u963b\u585e\u6216\u8b66\u544a\u3002",
          latestRun: "\u6700\u8fd1\u4e00\u6b21\u8fd0\u884c",
          selectionWorkspace: "\u9009\u4e2d\u5bf9\u8c61",
          runWorkspace: "\u8fd0\u884c\u68c0\u67e5",
          selectionWorkspaceHint:
            "\u7f16\u8f91\u5f53\u524d\u9009\u4e2d\u7684\u8282\u70b9\u6216\u8fb9\u3002",
          runWorkspaceHint:
            "\u67e5\u770b dry-run\u3001\u6700\u8fd1\u8fd0\u884c\u3001\u5ba1\u6279\u548c worker \u4ea7\u7269\u3002",
          noRunInspection:
            "\u8fd8\u6ca1\u6709 dry-run \u6216\u8fd0\u884c\u8bb0\u5f55\u3002\u4ece\u753b\u5e03\u5de5\u5177\u680f\u542f\u52a8\u4e00\u6b21\u9a8c\u8bc1\u6216\u5939\u5177\u8fd0\u884c\u3002",
          workers: "\u4e2a worker",
          artifacts: "\u4e2a\u4ea7\u7269",
          retryDryRun: "\u91cd\u8bd5 Dry-run",
          replayFixture: "\u91cd\u653e\u5939\u5177",
          recoveryPath: "Recovery",
          resumeRun: "Resume run",
          retryFailedNodes: "Retry failed",
          rerunSelectedNodes: "Rerun selected",
          partialRerun: "Partial rerun",
          rerunNodes: "Rerun",
          reusedNodes: "Reused",
          recoverySourceRun: "Source run",
          recoveryArtifacts: "Recovery artifacts",
          recoveryManifest: "Manifest",
          recoveryReport: "Report",
          recoveringRun: "Recovering...",
          eventTargetNode: "\u8282\u70b9",
          eventTargetEdge: "\u8fb9",
          cancelRun: "\u53d6\u6d88\u8fd0\u884c",
          cancellingRun: "\u6b63\u5728\u53d6\u6d88...",
          approvalRequired: "\u9700\u8981\u5ba1\u6279",
          approvalRecorded: "\u5ba1\u6279\u5df2\u8bb0\u5f55",
          approvalExpired: "\u5ba1\u6279\u5df2\u8fc7\u671f",
          approvalRejected: "\u5ba1\u6279\u5df2\u62d2\u7edd",
          approveGate: "\u6279\u51c6\u5173\u5361",
          rejectGate: "\u62d2\u7edd\u5173\u5361",
          deciding: "\u5904\u7406\u4e2d...",
          timeline: "\u65f6\u95f4\u7ebf",
          diagnostics: "\u8bca\u65ad",
          workerOutputs: "Worker \u8f93\u51fa",
          noWorkerOutputs:
            "\u8fd8\u6ca1\u6709\u8bb0\u5f55\u4efb\u4f55 worker \u8f93\u51fa\u3002",
          workerOutputsSyncing:
            "Worker \u8be6\u60c5\u6b63\u5728\u540c\u6b65\uff0c\u8bf7\u4ee5\u65f6\u95f4\u7ebf\u548c\u4ea7\u7269\u4e3a\u51c6\u3002",
          tokenBudget: "Token \u4e0a\u9650",
          tokenBudgetTitle:
            "Live run \u548c Dry-run \u4f7f\u7528\u7684\u603b token \u4e0a\u9650\uff0c\u8fd0\u884c\u65f6\u4f1a\u6309 agent \u5206\u914d\u3002",
          from: "\u8d77\u70b9",
          to: "\u7ec8\u70b9",
          selectSource: "\u9009\u62e9\u8d77\u70b9",
          selectTarget: "\u9009\u62e9\u7ec8\u70b9",
          edgeType: "\u8fb9\u7c7b\u578b",
          handoffContract: "\u901a\u4fe1\u5951\u7ea6",
          handoffMessageTemplate: "\u4ea4\u63a5\u6d88\u606f\u6a21\u677f",
          requiredSchemaRefs: "\u9700\u8981\u8f93\u5165 Schema \u5f15\u7528",
          producedOutputSchema: "\u4e0a\u6e38\u8f93\u51fa Schema",
          messagePartModes: "\u6d88\u606f\u7247\u6bb5",
          sourceSchemaHint:
            "\u7edf\u4e00\u5951\u7ea6\u5bfc\u51fa\u65f6\uff0c\u8fd9\u4e9b Schema \u5f15\u7528\u4f1a\u9644\u5230\u4e0b\u6e38\u4ea4\u63a5\u5951\u7ea6\u3002",
          noProducedSchema:
            "\u5f53\u524d\u8d77\u70b9\u8fd8\u6ca1\u6709\u58f0\u660e\u673a\u5668\u8f93\u51fa Schema\u3002",
          messagePartMachineResult: "\u673a\u5668\u7ed3\u679c",
          messagePartHumanSummary: "\u4eba\u5de5\u6458\u8981",
          messagePartArtifactRef: "\u4ea7\u7269\u5f15\u7528",
          messagePartStructuredJson: "\u7ed3\u6784\u5316 JSON",
          messagePartText: "\u7eaf\u6587\u672c",
          historyMode: "\u5386\u53f2\u6a21\u5f0f",
          artifactInclusion: "\u4ea7\u7269\u5305\u542b\u7b56\u7565",
          historyLength: "\u5386\u53f2\u957f\u5ea6",
          summaryStrategy: "\u6458\u8981\u7b56\u7565",
          includedArtifacts: "\u5305\u542b\u7684\u4ea7\u7269",
          resourceRefs: "\u8d44\u6e90\u5f15\u7528",
          excludePrivateMemory: "\u6392\u9664\u79c1\u6709\u8bb0\u5fc6",
          includeMachineResults: "\u5305\u542b\u673a\u5668\u7ed3\u679c",
          includeHumanSummaries: "\u5305\u542b\u4eba\u5de5\u6458\u8981",
          createEdgeAction: "\u521b\u5efa\u8fb9",
          saveEdge: "\u4fdd\u5b58\u8fb9",
          latestNodeRun: "\u8282\u70b9\u6700\u65b0\u8fd0\u884c",
          latestEdgeRun: "\u8fb9\u6700\u65b0\u4ea4\u63a5",
          latestEvent: "\u6700\u65b0\u4e8b\u4ef6",
          relatedEvents: "\u76f8\u5173\u4e8b\u4ef6",
          handoffInput: "\u4e0b\u6e38\u8f93\u5165",
          artifactPaths: "\u4ea7\u7269\u8def\u5f84",
          nextHints: "\u4e0b\u4e00\u6b65\u63d0\u793a",
          noNodeRunDetails:
            "\u5f53\u524d\u9009\u4e2d\u8282\u70b9\u8fd8\u6ca1\u6709 worker \u8f93\u51fa\u6216\u65f6\u95f4\u7ebf\u8bb0\u5f55\u3002",
          noEdgeRunDetails:
            "\u5f53\u524d\u9009\u4e2d\u8fb9\u8fd8\u6ca1\u6709 handoff \u6216\u8fd0\u884c\u4e8b\u4ef6\u8bb0\u5f55\u3002",
          inspectRunDetails: "\u68c0\u67e5\u8fd0\u884c\u7ec6\u8282",
          edgeRuntime: "\u8fb9\u8fd0\u884c\u6001",
          approvalPanelTitle:
            "\u8fd9\u4e2a\u8282\u70b9\u9700\u8981\u4eba\u5de5\u786e\u8ba4\u540e\u624d\u80fd\u7ee7\u7eed\u6267\u884c\u3002",
          fixtureTitle:
            "\u4f7f\u7528\u5939\u5177\u6570\u636e\u9a8c\u8bc1\u4efb\u52a1\u56fe\u8def\u5f84\uff0c\u4e0d\u4f9d\u8d56\u771f\u5b9e\u4efb\u52a1\u4e0a\u4e0b\u6587\u3002",
          cancellableFixtureTitle:
            "\u542f\u52a8\u4e00\u4e2a\u53ef\u53d6\u6d88\u7684 fan-out \u5939\u5177\u8fd0\u884c\uff0c\u9a8c\u8bc1\u8fd0\u884c\u4e2d\u548c\u53d6\u6d88\u540e\u7684\u6062\u590d\u884c\u4e3a\u3002",
          dryRunTitle:
            "\u53ea\u9a8c\u8bc1\u4efb\u52a1\u56fe\u7ed3\u6784\u3001\u6743\u9650\u548c\u8def\u7531\u517c\u5bb9\u6027\uff0c\u4e0d\u542f\u52a8\u5b9e\u9645\u6267\u884c\u3002",
          liveRunTitle:
            "\u4f7f\u7528\u771f\u5b9e provider \u8def\u7531\u542f\u52a8\u4efb\u52a1\u56fe\uff0c\u4fdd\u7559 per-node artifact \u548c\u5e76\u884c\u8fd0\u884c\u8bc1\u636e\u3002",
          closeTitle: "\u8fd4\u56de\u4e3b\u5bf9\u8bdd\u5de5\u4f5c\u533a\u3002",
          fitView: "\u9002\u5e94\u89c6\u56fe",
          fitViewTitle:
            "\u6839\u636e\u5f53\u524d\u8282\u70b9\u5e03\u5c40\u81ea\u52a8\u7f29\u653e\uff0c\u8ba9\u4efb\u52a1\u56fe\u5b8c\u6574\u843d\u5728\u53ef\u89c6\u753b\u5e03\u5185\u3002",
          resetView: "\u91cd\u7f6e\u89c6\u56fe",
          resetViewTitle:
            "\u6062\u590d\u9ed8\u8ba4\u7f29\u653e\u7ea7\u522b\uff0c\u5e76\u56de\u5230\u753b\u5e03\u539f\u70b9\u3002",
          zoomInTitle:
            "\u653e\u5927\u753b\u5e03\uff0c\u4fbf\u4e8e\u7cbe\u7ec6\u8c03\u6574\u8282\u70b9\u548c\u8fde\u7ebf\u3002",
          zoomOutTitle:
            "\u7f29\u5c0f\u753b\u5e03\uff0c\u4e00\u6b21\u67e5\u770b\u66f4\u591a\u4efb\u52a1\u56fe\u5185\u5bb9\u3002",
          dragHint: "\u62d6\u52a8",
          connectHint: "\u8fde\u7ebf",
          pickTargetHint: "\u9009\u62e9\u76ee\u6807",
          reset: "\u91cd\u7f6e",
          saving: "\u4fdd\u5b58\u4e2d...",
          saveNode: "\u4fdd\u5b58\u8282\u70b9",
          collapsePanel: "\u6536\u8d77\u9762\u677f",
          expandPanel: "\u5c55\u5f00\u9762\u677f",
          moreSettings: "\u66f4\u591a\u8bbe\u7f6e",
          advancedEdgeTitle:
            "\u5c55\u5f00\u8fb9\u7684\u9ad8\u7ea7\u4e0a\u4e0b\u6587\u8bbe\u7f6e\u3002",
          typedPorts: "\u7c7b\u578b\u7aef\u53e3",
          inputs: "\u8f93\u5165",
          outputs: "\u8f93\u51fa",
          sourceOutputs: "\u8d77\u70b9\u8f93\u51fa",
          targetInputs: "\u7ec8\u70b9\u8f93\u5165",
          edgeCompatibility: "\u517c\u5bb9\u6027",
          compatiblePorts: "\u53ef\u8fde\u63a5\u7aef\u53e3",
          compatibleConnection:
            "\u5f53\u524d\u7c7b\u578b\u7aef\u53e3\u53ef\u4ee5\u76f4\u63a5\u8fde\u63a5\u3002",
          incompatibleConnection:
            "\u8d77\u70b9\u8f93\u51fa\u548c\u7ec8\u70b9\u8f93\u5165\u4e4b\u95f4\u6ca1\u6709\u53ef\u517c\u5bb9\u7684\u7c7b\u578b\u7aef\u53e3\u3002",
          controlOnlyConnection:
            "\u8fd9\u6761\u8fb9\u53ef\u4ee5\u4f5c\u4e3a\u63a7\u5236\u4f9d\u8d56\u4fdd\u7559\uff0c\u4f46\u5f53\u524d typed payload \u4e0d\u5339\u914d\u3002",
          portType: "\u7c7b\u578b",
        }
      : {
          workspace: "Task graph",
          chooseTemplate: "Choose a template to start planning",
          backToChat: "Back to chat",
          templates: "Templates",
          presetTemplates: "Preset templates",
          customTemplates: "Custom templates",
          presetTemplatesHint:
            "Curated starting points organized around common task flows.",
          customTemplatesHint:
            "Templates you tailor and keep for your own workflow.",
          noCustomTemplates: "No custom templates have been saved yet.",
          currentTemplate: "Current task",
          templateStructure: "Structure",
          loadingTemplates: "Loading templates...",
          noTemplates: "No templates are available.",
          nodePalette: "Node palette",
          addNode: "Add node",
          currentNodes: "Current nodes",
          browseNodes:
            "Instantiate a template from the top toolbar before browsing nodes.",
          edges: "Edges",
          noEdges: "No edges yet.",
          canvas: "Canvas",
          loadingGraph: "Loading graph...",
          noGraph: "No graph yet",
          noGraphHint:
            "Start from the Templates button in the top toolbar, then refine the workflow on the canvas.",
          inspector: "Inspector",
          selectNode: "Select a node or edge to inspect its configuration.",
          roleLabel: "Role label",
          unspecified: "Unspecified",
          provider: "Provider",
          model: "Model",
          reasoning: "Reasoning",
          permission: "Permission",
          collaboration: "Collaboration",
          backend: "Backend",
          contextPolicy: "Context policy",
          memoryPolicy: "Memory policy",
          promptAndOutput: "Prompt & output",
          toolsAndApproval: "Tools & approval",
          promptTemplate: "Prompt template",
          promptVariables: "Variables",
          insertVariable: "Insert variable",
          promptPreview: "Preview",
          payloadPreview: "Payload preview",
          outputSchema: "Output schema",
          artifactOutputs: "Artifact outputs",
          artifactOnly: "Artifact only",
          humanSummaryRequired: "Human summary required",
          allowProviderCalls: "Allow provider calls",
          allowCodeChanges: "Allow code changes",
          allowInstall: "Allow installs",
          requiresApproval: "Require human approval",
          approvalKind: "Approval kind",
          defaultApprovalKind: "Select an approval kind",
          advancedNodeTitle:
            "Expand prompt, schema, tool, and approval controls for the selected node.",
          invalidPromptVariable:
            "The prompt template contains an unknown variable.",
          invalidSchema: "Output schema must be valid JSON object text.",
          unsafeToolPolicy:
            "Code changes or install access require human approval.",
          missingApprovalKind:
            "Choose an approval kind when human approval is enabled.",
          noPromptPreview:
            "Prompt preview appears here after template variables are resolved.",
          noPayloadPreview:
            "Select a node or edge to preview the structured payload sent downstream.",
          runFixture: "Fixture run",
          runCancellableFixture: "Cancellable fixture",
          dryRun: "Dry-run",
          runLive: "Live run",
          runningLive: "Starting live run...",
          runningFixture: "Running fixture...",
          runningDryRun: "Running dry-run...",
          importGraph: "Import",
          exportGraph: "Export",
          snapshotGraph: "Snapshot",
          creatingSnapshot: "Saving snapshot...",
          comparingSnapshot: "Comparing...",
          compareSnapshot: "Compare",
          rollbackSnapshot: "Rollback",
          rollingBackSnapshot: "Rolling back...",
          recentSnapshots: "Recent snapshots",
          showMore: "Show more",
          showLess: "Show less",
          currentGraphDiff: "Compare with current graph",
          snapshotDiff: "Snapshot diff",
          importingGraph: "Importing...",
          exportingGraph: "Exporting...",
          importedGraph: "Imported",
          exportedGraph: "Exported",
          exportPreview: "Export preview",
          lines: "lines",
          templatesHelp:
            "Start from a bounded template instead of a blank graph.",
          templateDetails: "Template details",
          useTemplate: "Instantiate template",
          templatePreview: "Preview",
          recommendedProviders: "Providers",
          recommendedModels: "Models",
          expectedArtifacts: "Artifacts",
          templatePreflight: "Preflight",
          templateConstraints: "Constraints",
          blankTemplateHint:
            "Preview a template first, then instantiate it onto the canvas.",
          createEdgeTitle:
            "Create a new connection between nodes and edit its context policy.",
          paletteHint:
            "Click to add directly, or drag onto the canvas to place it.",
          incompleteNodeWarning:
            "This agent is still missing provider and model settings. Finish them in the inspector before running it.",
          nodeMode: "Node",
          nodeModeTitle:
            "Inspect and edit the selected node's provider, model, and execution settings.",
          edgeMode: "Edge",
          edgeModeTitle: "Inspect and edit how context moves between nodes.",
          runReadiness: "Run readiness",
          openReport: "Open report",
          noWarnings: "No blockers or warnings.",
          latestRun: "Latest run",
          selectionWorkspace: "Selection",
          runWorkspace: "Run inspection",
          selectionWorkspaceHint:
            "Edit the node or edge that is currently selected on the canvas.",
          runWorkspaceHint:
            "Inspect dry-run state, the latest run, approvals, diagnostics, and worker artifacts.",
          noRunInspection:
            "No dry-run or run evidence is available yet. Start a dry-run or fixture run from the canvas toolbar.",
          workers: "workers",
          artifacts: "artifacts",
          retryDryRun: "Retry dry-run",
          replayFixture: "Replay fixture",
          recoveryPath: "Recovery",
          resumeRun: "Resume run",
          retryFailedNodes: "Retry failed",
          rerunSelectedNodes: "Rerun selected",
          partialRerun: "Partial rerun",
          rerunNodes: "Rerun",
          reusedNodes: "Reused",
          recoverySourceRun: "Source run",
          recoveryArtifacts: "Recovery artifacts",
          recoveryManifest: "Manifest",
          recoveryReport: "Report",
          recoveringRun: "Recovering...",
          eventTargetNode: "Node",
          eventTargetEdge: "Edge",
          cancelRun: "Cancel run",
          cancellingRun: "Cancelling...",
          approvalRequired: "Approval required",
          approvalRecorded: "Approval recorded",
          approvalExpired: "Approval expired",
          approvalRejected: "Approval rejected",
          approveGate: "Approve gate",
          rejectGate: "Reject gate",
          deciding: "Deciding...",
          timeline: "Timeline",
          diagnostics: "Diagnostics",
          workerOutputs: "Worker outputs",
          noWorkerOutputs: "No worker outputs have been recorded yet.",
          workerOutputsSyncing:
            "Worker details are syncing; artifacts and timeline remain authoritative.",
          tokenBudget: "Token limit",
          tokenBudgetTitle:
            "Total token limit shared across agents for live-run and dry-run validation.",
          from: "From",
          to: "To",
          selectSource: "Select source",
          selectTarget: "Select target",
          edgeType: "Edge type",
          handoffContract: "Handoff contract",
          handoffMessageTemplate: "Handoff message template",
          requiredSchemaRefs: "Required input schema refs",
          producedOutputSchema: "Produced output schema",
          messagePartModes: "Message parts",
          sourceSchemaHint:
            "These schema refs become the downstream handoff contract during canonical export.",
          noProducedSchema:
            "The current source node does not declare a machine output schema yet.",
          messagePartMachineResult: "Machine result",
          messagePartHumanSummary: "Human summary",
          messagePartArtifactRef: "Artifact ref",
          messagePartStructuredJson: "Structured JSON",
          messagePartText: "Plain text",
          historyMode: "History mode",
          artifactInclusion: "Artifact inclusion",
          historyLength: "History length",
          summaryStrategy: "Summary strategy",
          includedArtifacts: "Included artifacts",
          resourceRefs: "Resource refs",
          excludePrivateMemory: "Exclude private memory",
          includeMachineResults: "Include machine results",
          includeHumanSummaries: "Include human summaries",
          createEdgeAction: "Create edge",
          saveEdge: "Save edge",
          latestNodeRun: "Latest node run",
          latestEdgeRun: "Latest edge handoff",
          latestEvent: "Latest event",
          relatedEvents: "Related events",
          handoffInput: "Downstream input",
          artifactPaths: "Artifact paths",
          nextHints: "Next-step hints",
          noNodeRunDetails:
            "No worker output or timeline evidence has been recorded for this node yet.",
          noEdgeRunDetails:
            "No handoff or run-event evidence has been recorded for this edge yet.",
          inspectRunDetails: "Inspect run details",
          edgeRuntime: "Edge runtime",
          approvalPanelTitle:
            "This node requires a human decision before execution can continue.",
          fixtureTitle:
            "Use fixture data to validate the graph path without depending on real task context.",
          cancellableFixtureTitle:
            "Start a cancellable fan-out fixture run to verify in-flight and post-cancel recovery.",
          dryRunTitle:
            "Validate graph structure, permissions, and route compatibility without starting execution.",
          liveRunTitle:
            "Start a provider-backed task-graph run and retain per-node artifacts plus parallel execution evidence.",
          closeTitle: "Return to the main chat workspace.",
          fitView: "Fit view",
          fitViewTitle:
            "Scale the graph so the current node layout fits within the visible canvas.",
          resetView: "Reset view",
          resetViewTitle:
            "Restore the default zoom level and return to the canvas origin.",
          zoomInTitle: "Zoom in for more precise node and edge edits.",
          zoomOutTitle: "Zoom out to inspect more of the graph at once.",
          dragHint: "Drag",
          connectHint: "Connect",
          pickTargetHint: "Pick target",
          reset: "Reset",
          saving: "Saving...",
          saveNode: "Save node",
          collapsePanel: "Collapse panel",
          expandPanel: "Expand panel",
          moreSettings: "More settings",
          advancedEdgeTitle: "Expand advanced edge context settings.",
          typedPorts: "Typed ports",
          inputs: "Inputs",
          outputs: "Outputs",
          sourceOutputs: "Source outputs",
          targetInputs: "Target inputs",
          edgeCompatibility: "Compatibility",
          compatiblePorts: "Compatible ports",
          compatibleConnection: "Typed ports can connect.",
          incompatibleConnection:
            "No compatible typed ports between source outputs and target inputs.",
          controlOnlyConnection:
            "This edge can stay control-only, but the current typed payload does not match.",
          portType: "Type",
        };
  const selectedNode =
    graph?.nodes.find((node) => node.node_id === selectedNodeId) ??
    graph?.nodes[0] ??
    null;
  const registryUi = useMemo(
    () =>
      buildTaskGraphNodeRegistryUi({
        locale,
        snapshot: nodeTypeRegistry,
      }),
    [locale, nodeTypeRegistry],
  );
  const selectedNodeTypeSpec = useMemo(
    () => registryUi.typeSpecForNode(selectedNode),
    [registryUi, selectedNode],
  );
  const selectedNodeTypeConfigSchema =
    (asRecord(selectedNodeTypeSpec?.config_schema) ?? null);
  const selectedEdge =
    graph?.edges.find((edge) => edge.edge_id === selectedEdgeId) ?? null;
  const nodeMap = useMemo(
    () => new Map((graph?.nodes ?? []).map((node) => [node.node_id, node])),
    [graph?.nodes],
  );
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const promptTemplateRef = useRef<HTMLTextAreaElement | null>(null);
  const edgeMessageTemplateRef = useRef<HTMLTextAreaElement | null>(null);
  const initialWorkspaceStateKey = taskGraphWorkspaceStateStorageKey(
    graph?.task_id,
    graph?.graph_id,
  );
  const initialPendingRunInspectorStorageKey = initialWorkspaceStateKey
    ? `${initialWorkspaceStateKey}.pending_run_inspector`
    : null;
  const initialPendingRunInspectorReopen = consumePendingRunInspectorReopen(
    initialPendingRunInspectorStorageKey,
  );
  const initialWorkspaceState = initialWorkspaceStateKey
    ? readStoredTaskGraphWorkspaceState(initialWorkspaceStateKey)
    : null;
  const [nodeDraft, setNodeDraft] = useState<NodeDraft | null>(null);
  const [nodeDraftBaseline, setNodeDraftBaseline] = useState<NodeDraft | null>(
    null,
  );
  const [nodeTypeConfigValid, setNodeTypeConfigValid] = useState(true);
  const [edgeDraft, setEdgeDraft] = useState<EdgeDraft | null>(null);
  const [edgeDraftBaseline, setEdgeDraftBaseline] = useState<EdgeDraft | null>(
    null,
  );
  const [isCreatingEdge, setIsCreatingEdge] = useState(false);
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [previewPositions, setPreviewPositions] = useState<
    Record<string, TaskGraphNodePosition>
  >({});
  const [readinessExpanded, setReadinessExpanded] = useState(
    Boolean(initialWorkspaceState?.readinessExpanded),
  );
  const [latestRunExpanded, setLatestRunExpanded] = useState(
    Boolean(initialWorkspaceState?.latestRunExpanded),
  );
  const [recoveryExpanded, setRecoveryExpanded] = useState(
    Boolean(initialWorkspaceState?.recoveryExpanded),
  );
  const [dryRunReasonsExpanded, setDryRunReasonsExpanded] = useState(false);
  const [snapshotsExpanded, setSnapshotsExpanded] = useState(false);
  const [selectedRunEventId, setSelectedRunEventId] = useState<string | null>(
    null,
  );
  const [inspectorWorkspace, setInspectorWorkspace] = useState<
    "selection" | "run"
  >(
    initialPendingRunInspectorReopen
      ? "run"
      : initialWorkspaceState?.inspectorWorkspace ?? "selection",
  );
  const [selectionInspectorRequested, setSelectionInspectorRequested] =
    useState(false);
  const [runInspectorRequested, setRunInspectorRequested] = useState(
    initialPendingRunInspectorReopen,
  );
  const [canvasScale, setCanvasScale] = useState(DEFAULT_CANVAS_SCALE);
  const [runTokenBudget, setRunTokenBudget] = useState(80_000);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const [hoveredPaletteKind, setHoveredPaletteKind] = useState<string | null>(
    null,
  );
  const [edgeCreateSourceId, setEdgeCreateSourceId] = useState<string | null>(
    null,
  );
  const [sidebarExpanded, setSidebarExpanded] = useState(
    Boolean(initialWorkspaceState?.sidebarExpanded),
  );
  const [inspectorExpanded, setInspectorExpanded] = useState(
    initialPendingRunInspectorReopen
      ? true
      : Boolean(initialWorkspaceState?.inspectorExpanded),
  );
  const [panelResizeState, setPanelResizeState] =
    useState<PanelResizeState | null>(null);
  const [sidebarWidth, setSidebarWidth] = useState(() =>
    readStoredTaskGraphPanelWidth(
      "left",
      TASK_GRAPH_SIDEBAR_WIDTH_STORAGE_KEY,
      DEFAULT_TASK_GRAPH_SIDEBAR_WIDTH,
    ),
  );
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(
    templates[0]?.template_id ?? null,
  );
  const [templateBrowserOpen, setTemplateBrowserOpen] = useState(false);
  const selectedTemplateIdRef = useRef<string | null>(
    templates[0]?.template_id ?? null,
  );
  const workspaceStateStorageKey = useMemo(
    () => taskGraphWorkspaceStateStorageKey(graph?.task_id, graph?.graph_id),
    [graph?.graph_id, graph?.task_id],
  );
  const pendingRunInspectorStorageKey = useMemo(
    () =>
      workspaceStateStorageKey
        ? `${workspaceStateStorageKey}.pending_run_inspector`
        : null,
    [workspaceStateStorageKey],
  );
  const workspaceStateKeyRef = useRef<string | null>(initialWorkspaceStateKey);
  const [workspaceStateReady, setWorkspaceStateReady] = useState(true);
  const normalizedRunTokenBudget = Number.isFinite(runTokenBudget)
    ? Math.max(1, Math.floor(runTokenBudget))
    : 80_000;
  const promptVariableEntries = useMemo(
    () =>
      selectedNode && nodeDraft
        ? availablePromptVariables(selectedNode, nodeDraft, graph)
        : [],
    [graph, nodeDraft, selectedNode],
  );
  const edgeVariableEntries = useMemo(
    () => availableEdgeMessageVariables({ draft: edgeDraft, nodeMap }),
    [edgeDraft, nodeMap],
  );

  useEffect(() => {
    selectedTemplateIdRef.current = selectedTemplateId;
  }, [selectedTemplateId]);

  const insertPromptVariable = (token: string) => {
    setNodeDraft((current) =>
      current
        ? {
            ...current,
            human_summary_template: insertTokenIntoText(
              current.human_summary_template,
              token,
            ),
          }
        : current,
    );
    window.requestAnimationFrame(() => promptTemplateRef.current?.focus());
  };

  const insertEdgeMessageVariable = (token: string) => {
    setEdgeDraft((current) =>
      current
        ? {
            ...current,
            handoff_message_template: insertTokenIntoText(
              current.handoff_message_template,
              token,
            ),
          }
        : current,
    );
    window.requestAnimationFrame(() => edgeMessageTemplateRef.current?.focus());
  };

  useEffect(() => {
    setPreviewPositions({});
    setCanvasScale(DEFAULT_CANVAS_SCALE);
  }, [graph?.graph_id, graph?.state_version]);

  useEffect(() => {
    if (!templates.length) {
      setSelectedTemplateId(null);
      selectedTemplateIdRef.current = null;
      return;
    }
    if (
      !selectedTemplateId ||
      !templates.some((template) => template.template_id === selectedTemplateId)
    ) {
      if (
        graph?.template_id &&
        templates.some((template) => template.template_id === graph.template_id)
      ) {
        selectedTemplateIdRef.current = graph.template_id;
        setSelectedTemplateId(graph.template_id);
        return;
      }
      selectedTemplateIdRef.current = templates[0].template_id;
      setSelectedTemplateId(templates[0].template_id);
    }
  }, [graph?.template_id, selectedTemplateId, templates]);

  const handleSelectTemplate = (templateId: string) => {
    selectedTemplateIdRef.current = templateId;
    setSelectedTemplateId(templateId);
  };

  const handleInstantiateSelectedTemplate = () => {
    const templateId =
      selectedTemplateIdRef.current ||
      selectedTemplate?.template_id ||
      templates[0]?.template_id;
    if (!templateId) return;
    setTemplateBrowserOpen(false);
    onInstantiateTemplate(templateId);
  };

  const openTemplateBrowser = () => {
    setTemplateBrowserOpen(true);
  };

  const closeTemplateBrowser = () => {
    setTemplateBrowserOpen(false);
  };

  useEffect(() => {
    if (dryRunError || dryRunResult?.overall_status === "blocked") {
      setReadinessExpanded(true);
    }
  }, [dryRunError, dryRunResult?.overall_status]);

  useEffect(() => {
    if (
      latestRunRef?.status === "running" ||
      latestRunRef?.status === "paused_for_review"
    ) {
      setLatestRunExpanded(true);
      setInspectorWorkspace("run");
    }
  }, [latestRunRef?.run_id, latestRunRef?.status]);

  useEffect(() => {
    const nextNodeDraft = selectedNode ? buildNodeDraft(selectedNode) : null;
    setNodeDraft(nextNodeDraft);
    setNodeDraftBaseline(nextNodeDraft);
    setNodeTypeConfigValid(true);
  }, [selectedNode]);

  useEffect(() => {
    if (isCreatingEdge) {
      if (graph) {
        const fallbackDraft = defaultCreateEdgeDraft(
          graph,
          edgeCreateSourceId ?? selectedNode?.node_id ?? null,
        );
        setEdgeDraft((current) => current ?? fallbackDraft);
        setEdgeDraftBaseline((current) => current ?? fallbackDraft);
      }
      return;
    }
    setEdgeCreateSourceId(null);
    const nextEdgeDraft = selectedEdge ? buildEdgeDraft(selectedEdge) : null;
    setEdgeDraft(nextEdgeDraft);
    setEdgeDraftBaseline(nextEdgeDraft);
  }, [edgeCreateSourceId, graph, isCreatingEdge, selectedEdge, selectedNode?.node_id]);

  useEffect(() => {
    if (!dragState) return undefined;
    const handlePointerMove = (event: MouseEvent) => {
      const nextPosition = projectNodePosition({
        stageElement: stageRef.current,
        originX: dragState.originX,
        originY: dragState.originY,
        deltaX: event.clientX - dragState.startX,
        deltaY: event.clientY - dragState.startY,
      });
      setPreviewPositions((current) => ({
        ...current,
        [dragState.nodeId]: nextPosition,
      }));
    };
    const handlePointerUp = (event: MouseEvent) => {
      const deltaX = event.clientX - dragState.startX;
      const deltaY = event.clientY - dragState.startY;
      const nextPosition = projectNodePosition({
        stageElement: stageRef.current,
        originX: dragState.originX,
        originY: dragState.originY,
        deltaX,
        deltaY,
      });
      setPreviewPositions((current) => ({
        ...current,
        [dragState.nodeId]: nextPosition,
      }));
      setDragState(null);
      if (Math.abs(deltaX) > 3 || Math.abs(deltaY) > 3) {
        onMoveNode(dragState.nodeId, nextPosition);
      }
    };
    window.addEventListener("mousemove", handlePointerMove);
    window.addEventListener("mouseup", handlePointerUp, { once: true });
    return () => {
      window.removeEventListener("mousemove", handlePointerMove);
      window.removeEventListener("mouseup", handlePointerUp);
    };
  }, [dragState, onMoveNode]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const handleWindowResize = () => {
      setSidebarWidth((current) =>
        normalizeTaskGraphPanelWidth("left", current),
      );
    };
    window.addEventListener("resize", handleWindowResize);
    return () => window.removeEventListener("resize", handleWindowResize);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(
      TASK_GRAPH_SIDEBAR_WIDTH_STORAGE_KEY,
      String(sidebarWidth),
    );
  }, [sidebarWidth]);

  useEffect(() => {
    if (workspaceStateKeyRef.current === workspaceStateStorageKey) {
      return;
    }
    workspaceStateKeyRef.current = workspaceStateStorageKey;
    setWorkspaceStateReady(false);
    if (!workspaceStateStorageKey) {
      setSidebarExpanded(false);
      setInspectorExpanded(false);
      setInspectorWorkspace("selection");
      setRunInspectorRequested(false);
      setReadinessExpanded(false);
      setLatestRunExpanded(false);
      setRecoveryExpanded(false);
      setWorkspaceStateReady(true);
      return;
    }
    const storedState = readStoredTaskGraphWorkspaceState(
      workspaceStateStorageKey,
    );
    const pendingRunInspectorReopen = consumePendingRunInspectorReopen(
      pendingRunInspectorStorageKey,
    );
    setSidebarExpanded(Boolean(storedState?.sidebarExpanded));
    setInspectorExpanded(pendingRunInspectorReopen);
    setRunInspectorRequested(pendingRunInspectorReopen);
    setInspectorWorkspace(
      pendingRunInspectorReopen
        ? "run"
        : storedState?.inspectorWorkspace ?? "selection",
    );
    setReadinessExpanded(Boolean(storedState?.readinessExpanded));
    setLatestRunExpanded(Boolean(storedState?.latestRunExpanded));
    setRecoveryExpanded(Boolean(storedState?.recoveryExpanded));
    setWorkspaceStateReady(true);
  }, [pendingRunInspectorStorageKey, workspaceStateStorageKey]);

  useEffect(() => {
    if (!workspaceStateReady || !workspaceStateStorageKey) return;
    if (typeof window === "undefined") return;
    const nextState: TaskGraphWorkspaceStoredState = {
      sidebarExpanded,
      inspectorExpanded: false,
      inspectorWorkspace,
      readinessExpanded,
      latestRunExpanded,
      recoveryExpanded,
    };
    window.localStorage.setItem(
      workspaceStateStorageKey,
      JSON.stringify(nextState),
    );
  }, [
    inspectorWorkspace,
    latestRunExpanded,
    readinessExpanded,
    recoveryExpanded,
    sidebarExpanded,
    workspaceStateReady,
    workspaceStateStorageKey,
  ]);

  useEffect(() => {
    if (!inspectorExpanded && !templateBrowserOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (templateBrowserOpen) {
          setTemplateBrowserOpen(false);
          return;
        }
        closeInspectorDialog();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [inspectorExpanded, templateBrowserOpen]);

  useEffect(() => {
    if (!panelResizeState) return undefined;
    document.body.classList.add("resizing");
    const handlePointerMove = (event: MouseEvent) => {
      const delta = event.clientX - panelResizeState.startX;
      setSidebarWidth(
        normalizeTaskGraphPanelWidth(
          "left",
          panelResizeState.startWidth + delta,
        ),
      );
    };
    const stopResize = () => setPanelResizeState(null);
    window.addEventListener("mousemove", handlePointerMove);
    window.addEventListener("mouseup", stopResize, { once: true });
    window.addEventListener("blur", stopResize, { once: true });
    return () => {
      document.body.classList.remove("resizing");
      window.removeEventListener("mousemove", handlePointerMove);
      window.removeEventListener("mouseup", stopResize);
      window.removeEventListener("blur", stopResize);
    };
  }, [panelResizeState]);

  const providerChoices = providerOptions.length
    ? providerOptions
    : ["deepseek", "glm", "kimi", "openai", "qwen", "yunwu"];
  const nodeDraftDirty = Boolean(
    nodeDraftBaseline &&
    nodeDraft &&
    !nodeDraftEqual(nodeDraft, nodeDraftBaseline),
  );
  const nodeDraftError = validateNodeDraft({
    draft: nodeDraft,
    node: selectedNode,
    graph,
  });
  const effectiveNodeDraftError = !nodeTypeConfigValid
    ? "Node type config contains invalid values."
    : nodeDraftError;
  const nodeDraftWarning = selectedNode
    ? incompleteNodeWarning(copy.incompleteNodeWarning, selectedNode, nodeDraft)
    : "";
  const inspectorMode = isCreatingEdge || selectedEdge ? "edge" : "node";
  const nodeStatusMap = useMemo(
    () =>
      new Map(
        (dryRunResult?.node_results ?? []).map((item) => [item.node_id, item]),
      ),
    [dryRunResult?.node_results],
  );
  const edgeStatusMap = useMemo(
    () =>
      new Map(
        (dryRunResult?.edge_results ?? []).map((item) => [item.edge_id, item]),
      ),
    [dryRunResult?.edge_results],
  );
  const graphBounds = useMemo(
    () => measureGraphBounds(graph?.nodes ?? [], previewPositions),
    [graph?.nodes, previewPositions],
  );
  const stageWidth = Math.max(
    MIN_STAGE_WIDTH,
    graphBounds.width + STAGE_PADDING * 2,
  );
  const stageHeight = Math.max(
    MIN_STAGE_HEIGHT,
    graphBounds.height + STAGE_PADDING * 2,
  );
  const scaledStageWidth = Math.max(stageWidth * canvasScale, 0);
  const scaledStageHeight = Math.max(stageHeight * canvasScale, 0);
  const edgeDraftDirty = useMemo(() => {
    if (!edgeDraft) return false;
    if (isCreatingEdge) return true;
    return Boolean(
      edgeDraftBaseline && !edgeDraftEqual(edgeDraft, edgeDraftBaseline),
    );
  }, [edgeDraft, edgeDraftBaseline, isCreatingEdge]);
  const edgeDraftError = validateEdgeDraft({
    draft: edgeDraft,
    graph,
    selectedEdgeId,
    isCreatingEdge,
    nodeMap,
  });
  const selectedNodePorts = useMemo(
    () => (selectedNode ? nodePortSummary(selectedNode, graph) : null),
    [graph, selectedNode],
  );
  const edgePortCompatibility = useMemo(
    () => edgeDraftCompatibility(edgeDraft, graph, nodeMap),
    [edgeDraft, graph, nodeMap],
  );
  const producedOutputSchemaPreview = useMemo(() => {
    if (!edgeDraft?.from_node_id) return "";
    const sourceNode = nodeMap.get(edgeDraft.from_node_id);
    if (!sourceNode) return "";
    const outputContract = asRecord(sourceNode.output_contract) ?? {};
    const machineSchema =
      asRecord(outputContract.machine_result_schema) ??
      asRecord(sourceNode.machine_result_schema) ??
      null;
    return machineSchema ? stringifyJson(machineSchema) : "";
  }, [edgeDraft?.from_node_id, nodeMap]);
  const producedOutputSchemaRef = useMemo(() => {
    if (!edgeDraft?.from_node_id) return "";
    return inferNodeSchemaRef(nodeMap.get(edgeDraft.from_node_id) ?? null);
  }, [edgeDraft?.from_node_id, nodeMap]);
  const latestRunStatus = String(latestRunRef?.status ?? "").trim().toLowerCase();
  const hasAuthoritativeTerminalLatestRun =
    Boolean(latestRunRef?.run_id) &&
    !String(latestRunRef?.run_id ?? "").startsWith(
      `pending-${graph?.graph_id ?? ""}`,
    ) &&
    ["completed", "failed", "cancelled", "blocked"].includes(latestRunStatus);
  const showSyntheticLivePendingRun =
    (showLiveRunPendingChrome ?? isLiveRunPending) &&
    Boolean(graph) &&
    !hasAuthoritativeTerminalLatestRun &&
    latestRunRef?.status !== "running" &&
    latestRunRef?.status !== "paused_for_review" &&
    !latestRunRef?.approval_details?.status;
  const effectiveLatestRunRef = useMemo<TaskGraphRunRef | null>(() => {
    if (showSyntheticLivePendingRun && graph) {
      const now = new Date().toISOString();
      return {
        run_id: `pending-${graph.graph_id}`,
        graph_id: graph.graph_id,
        task_id: graph.task_id,
        status: "running",
        created_at: latestRunRef?.created_at ?? now,
        updated_at: now,
        entry_node_ids: graph.graph_policy?.entry_node_ids ?? [],
        node_status_counts: { running: 1 },
        artifact_count: latestRunRef?.artifact_count ?? 0,
        event_count: 1,
        latest_event_type: "run_started",
        latest_event_at: now,
        timeline_events: [
          {
            event_id: `pending-${graph.graph_id}-started`,
            event_type: "run_started",
            created_at: now,
            summary: copy.runningLive,
            status: "in_progress",
          },
        ],
        metrics: latestRunRef?.metrics ?? null,
        budget: latestRunRef?.budget ?? null,
        worker_count: latestRunRef?.worker_count ?? 0,
        worker_bindings: latestRunRef?.worker_bindings ?? [],
      };
    }
    if (
      isFixtureRunPending &&
      graph &&
      latestRunRef?.status !== "running" &&
      latestRunRef?.status !== "paused_for_review" &&
      !latestRunRef?.approval_details?.status
    ) {
      const now = new Date().toISOString();
      return {
        run_id: `pending-${graph.graph_id}`,
        graph_id: graph.graph_id,
        task_id: graph.task_id,
        status: "running",
        created_at: latestRunRef?.created_at ?? now,
        updated_at: now,
        entry_node_ids: graph.graph_policy?.entry_node_ids ?? [],
        node_status_counts: { running: 1 },
        artifact_count: latestRunRef?.artifact_count ?? 0,
        event_count: 1,
        latest_event_type: "run_started",
        latest_event_at: now,
        timeline_events: [
          {
            event_id: `pending-${graph.graph_id}-started`,
            event_type: "run_started",
            created_at: now,
            summary: copy.runningFixture,
            status: "in_progress",
          },
        ],
        metrics: latestRunRef?.metrics ?? null,
        budget: latestRunRef?.budget ?? null,
        worker_count: latestRunRef?.worker_count ?? 0,
        worker_bindings: latestRunRef?.worker_bindings ?? [],
      };
    }
    return latestRunRef;
  }, [
    copy.runningFixture,
    copy.runningLive,
    graph,
    isFixtureRunPending,
    showSyntheticLivePendingRun,
    latestRunRef,
  ]);
  const runMetricCopy = useMemo(
    () => ({
      run: locale === "zh-CN" ? "运行" : "Run",
      updated: locale === "zh-CN" ? "更新" : "Updated",
      tokens: "Tokens",
      calls: locale === "zh-CN" ? "调用" : "Calls",
      elapsed: locale === "zh-CN" ? "耗时" : "Elapsed",
      budget: locale === "zh-CN" ? "预算" : "Budget",
      cost: locale === "zh-CN" ? "成本" : "Cost",
    }),
    [locale],
  );
  const latestRunTokens = formatRunTokenUsage(
    effectiveLatestRunRef?.metrics?.token_usage ?? null,
    locale,
  );
  const latestRunCalls = formatRunCallSummary(
    effectiveLatestRunRef?.metrics?.provider_call_count ?? null,
    effectiveLatestRunRef?.metrics?.tool_call_count ?? null,
    locale,
  );
  const latestRunElapsed = formatRunElapsed(
    effectiveLatestRunRef?.metrics?.elapsed_ms ?? null,
    locale,
  );
  const latestRunBudget = formatRunBudgetSummary(
    effectiveLatestRunRef?.budget ?? null,
    locale,
  );
  const latestRunCost = formatRunCost(
    effectiveLatestRunRef?.metrics?.cost ?? null,
    locale,
  );
  const latestRunStatusCountsSummary = formatRunStatusCountsSummary(
    effectiveLatestRunRef?.node_status_counts ?? null,
    locale,
  );
  const latestRunPrimaryEventSummary = useMemo(() => {
    const latestEvent =
      effectiveLatestRunRef?.timeline_events?.[
        (effectiveLatestRunRef.timeline_events?.length ?? 1) - 1
      ] ?? null;
    if (!latestEvent) return "";
    return String(latestEvent.summary || latestEvent.event_type || "").trim();
  }, [effectiveLatestRunRef?.timeline_events]);
  const latestRunIsStale = isTaskGraphRunRefStale(effectiveLatestRunRef);
  const latestRunDisplayStatus = latestRunIsStale
    ? "stale"
    : String(effectiveLatestRunRef?.status ?? "").trim();
  const latestRunStatusTitle = latestRunIsStale
    ? locale === "zh-CN"
      ? "该运行长时间没有活动信号，可取消后重新运行。"
      : "This run has no recent activity. Cancel it before retrying."
    : undefined;
  const latestRunHeadlineSummary =
    effectiveLatestRunRef &&
    (latestRunDisplayStatus === "queued" ||
      latestRunDisplayStatus === "running" ||
      latestRunDisplayStatus === "paused_for_review") &&
    (effectiveLatestRunRef.worker_count ?? 0) === 0 &&
    (effectiveLatestRunRef.artifact_count ?? 0) === 0 &&
    latestRunStatusCountsSummary
      ? latestRunStatusCountsSummary
      : `${effectiveLatestRunRef?.worker_count ?? 0} ${copy.workers} / ${
          effectiveLatestRunRef?.artifact_count ?? 0
        } ${copy.artifacts}`;

  useEffect(() => {
    if (
      selectionInspectorRequested &&
      (isCreatingEdge || selectedEdgeId || selectedNodeId)
    ) {
      setInspectorWorkspace("selection");
      return;
    }
    if (effectiveLatestRunRef || dryRunResult || dryRunError) {
      setInspectorWorkspace("run");
      return;
    }
    if (isCreatingEdge || selectedEdgeId || selectedNodeId) {
      setInspectorWorkspace("selection");
    }
  }, [
    dryRunError,
    dryRunResult,
    effectiveLatestRunRef,
    isCreatingEdge,
    selectionInspectorRequested,
    selectedEdgeId,
    selectedNodeId,
  ]);
  useEffect(() => {
    if (!runInspectorRequested) return;
    if (
      isDryRunPending ||
      isFixtureRunPending ||
      effectiveLatestRunRef ||
      dryRunResult ||
      dryRunError
    ) {
      setInspectorWorkspace("run");
      setInspectorExpanded(true);
    }
  }, [
    dryRunError,
    dryRunResult,
    effectiveLatestRunRef,
    isDryRunPending,
    isFixtureRunPending,
    runInspectorRequested,
  ]);
  useEffect(() => {
    setSelectedRunEventId(null);
  }, [effectiveLatestRunRef?.run_id]);
  const approvalStatus =
    effectiveLatestRunRef?.approval_details?.status ?? null;
  const showApprovalPanel =
    approvalStatus === "pending" ||
    approvalStatus === "approved" ||
    approvalStatus === "rejected" ||
    approvalStatus === "expired";
  const selectedRunEvent = useMemo(
    () =>
      effectiveLatestRunRef?.timeline_events?.find(
        (event) => event.event_id === selectedRunEventId,
      ) ?? null,
    [effectiveLatestRunRef?.timeline_events, selectedRunEventId],
  );
  const selectedRunEventTarget = useMemo(() => {
    if (!graph || !selectedRunEvent) return null;
    if (
      selectedRunEvent.edge_id &&
      graph.edges.some((edge) => edge.edge_id === selectedRunEvent.edge_id)
    ) {
      const targetEdge = graph.edges.find(
        (edge) => edge.edge_id === selectedRunEvent.edge_id,
      );
      return {
        kind: "edge" as const,
        id: selectedRunEvent.edge_id,
        label: targetEdge
          ? edgeLabel(targetEdge, nodeMap)
          : selectedRunEvent.edge_id,
      };
    }
    if (
      selectedRunEvent.node_id &&
      graph.nodes.some((node) => node.node_id === selectedRunEvent.node_id)
    ) {
      return {
        kind: "node" as const,
        id: selectedRunEvent.node_id,
        label: labelForNodeId(nodeMap, selectedRunEvent.node_id),
      };
    }
    if (
      selectedRunEvent.event_type === "approval_requested" &&
      effectiveLatestRunRef?.approval_details?.node_id &&
      graph.nodes.some(
        (node) =>
          node.node_id === effectiveLatestRunRef.approval_details?.node_id,
      )
    ) {
      return {
        kind: "node" as const,
        id: effectiveLatestRunRef.approval_details.node_id,
        label: labelForNodeId(
          nodeMap,
          effectiveLatestRunRef.approval_details.node_id,
        ),
      };
    }
    return null;
  }, [
    effectiveLatestRunRef?.approval_details?.node_id,
    graph,
    nodeMap,
    selectedRunEvent,
  ]);
  const runtimeNodeStatusMap = useMemo(() => {
    const statuses = new Map<string, string>();
    for (const binding of effectiveLatestRunRef?.worker_bindings ?? []) {
      if (!binding?.node_id) continue;
      statuses.set(binding.node_id, String(binding.status || "").trim());
    }
    for (const event of effectiveLatestRunRef?.timeline_events ?? []) {
      const nodeId = String(event.node_id || "").trim();
      if (!nodeId || statuses.has(nodeId)) continue;
      const eventStatus = String(event.status || "").trim();
      if (eventStatus) statuses.set(nodeId, eventStatus);
    }
    const approvalNodeId = String(
      effectiveLatestRunRef?.approval_details?.node_id || "",
    ).trim();
    if (
      approvalNodeId &&
      !statuses.has(approvalNodeId) &&
      effectiveLatestRunRef?.approval_details?.status
    ) {
      statuses.set(
        approvalNodeId,
        String(effectiveLatestRunRef.approval_details.status),
      );
    }
    return statuses;
  }, [
    effectiveLatestRunRef?.approval_details?.node_id,
    effectiveLatestRunRef?.approval_details?.status,
    effectiveLatestRunRef?.timeline_events,
    effectiveLatestRunRef?.worker_bindings,
  ]);
  const runtimeEdgeStatusMap = useMemo(() => {
    const statuses = new Map<string, string>();
    for (const binding of effectiveLatestRunRef?.worker_bindings ?? []) {
      for (const handoff of binding.downstream_handoffs ?? []) {
        const edgeId = String(handoff.edge_id || "").trim();
        if (!edgeId) continue;
        statuses.set(edgeId, String(binding.status || "").trim() || "completed");
      }
    }
    for (const event of effectiveLatestRunRef?.timeline_events ?? []) {
      const edgeId = String(event.edge_id || "").trim();
      if (!edgeId) continue;
      const eventStatus = String(event.status || "").trim();
      if (eventStatus || !statuses.has(edgeId)) {
        statuses.set(edgeId, eventStatus || "completed");
      }
    }
    return statuses;
  }, [effectiveLatestRunRef?.timeline_events, effectiveLatestRunRef?.worker_bindings]);
  const selectedNodeRunDetails = useMemo(() => {
    if (!selectedNode || !effectiveLatestRunRef) return null;
    const binding =
      effectiveLatestRunRef.worker_bindings?.find(
        (item) => item.node_id === selectedNode.node_id,
      ) ?? null;
    const relatedEvents = (effectiveLatestRunRef.timeline_events ?? []).filter(
      (event) => event.node_id === selectedNode.node_id,
    );
    const latestEvent = relatedEvents[relatedEvents.length - 1] ?? null;
    const status =
      runtimeNodeStatusMap.get(selectedNode.node_id) ??
      latestEvent?.status ??
      binding?.status ??
      null;
    return { binding, relatedEvents, latestEvent, status };
  }, [effectiveLatestRunRef, runtimeNodeStatusMap, selectedNode]);
  const selectedEdgeRunDetails = useMemo(() => {
    if (!selectedEdge || !effectiveLatestRunRef) return null;
    const handoffs = (effectiveLatestRunRef.worker_bindings ?? []).flatMap(
      (binding) =>
        (binding.downstream_handoffs ?? [])
          .filter((handoff) => handoff.edge_id === selectedEdge.edge_id)
          .map((handoff) => ({ binding, handoff })),
    );
    const relatedEvents = (effectiveLatestRunRef.timeline_events ?? []).filter(
      (event) => event.edge_id === selectedEdge.edge_id,
    );
    const latestEvent = relatedEvents[relatedEvents.length - 1] ?? null;
    const status =
      runtimeEdgeStatusMap.get(selectedEdge.edge_id) ??
      latestEvent?.status ??
      handoffs[0]?.binding.status ??
      null;
    return { handoffs, relatedEvents, latestEvent, status };
  }, [effectiveLatestRunRef, runtimeEdgeStatusMap, selectedEdge]);
  const exportPreviewLineCount = useMemo(() => {
    const text = String(lastExportPreview || "").trim();
    if (!text) return 0;
    return text.split(/\r?\n/).length;
  }, [lastExportPreview]);
  const dryRunReasons = dryRunResult?.graph_result.reasons ?? [];
  const dryRunReasonEntries = useMemo(
    () => summarizeDisclosureStrings(dryRunReasons),
    [dryRunReasons],
  );
  const dryRunReasonsKey = useMemo(
    () =>
      dryRunReasonEntries
        .map((entry) => `${entry.label}:${entry.count}`)
        .join("\u0001"),
    [dryRunReasonEntries],
  );
  const {
    visibleItems: visibleDryRunReasons,
    hiddenCount: hiddenDryRunReasonCount,
  } = buildDisclosurePreview(
    dryRunReasonEntries,
    dryRunReasonsExpanded,
    MAX_DISCLOSURE_PREVIEW_ITEMS,
  );
  const snapshotDiffLineCount = useMemo(() => {
    const text = String(snapshotDiffMarkdown || "").trim();
    if (!text) return 0;
    return text.split(/\r?\n/).length;
  }, [snapshotDiffMarkdown]);
  const snapshotRefsKey = useMemo(
    () =>
      snapshotRefs
        .map(
          (snapshot) =>
            `${snapshot.snapshot_id}:${snapshot.state_version}:${snapshot.label ?? ""}`,
        )
        .join("\u0001"),
    [snapshotRefs],
  );
  const { visibleItems: visibleSnapshotRefs, hiddenCount: hiddenSnapshotCount } =
    buildDisclosurePreview(
      snapshotRefs,
      snapshotsExpanded,
      MAX_DISCLOSURE_PREVIEW_ITEMS,
    );
  const selectedSnapshot = useMemo(
    () =>
      snapshotRefs.find((item) => item.snapshot_id === selectedSnapshotId) ??
      snapshotRefs[0] ??
      null,
    [selectedSnapshotId, snapshotRefs],
  );
  const dryRunSummaryTitle = dryRunResult
    ? `${dryRunResult.status_counts.pass ?? 0} pass / ${dryRunResult.status_counts.warning ?? 0} warning / ${dryRunResult.status_counts.blocked ?? 0} blocked`
    : "";
  const dryRunSummaryCompactLabel = dryRunResult
    ? `${dryRunResult.status_counts.pass ?? 0} / ${dryRunResult.status_counts.warning ?? 0} / ${dryRunResult.status_counts.blocked ?? 0}`
    : "";
  const dryRunReasonsToggleLabel = disclosureToggleLabel(
    locale,
    dryRunReasonsExpanded,
    hiddenDryRunReasonCount,
    copy,
  );
  const dryRunReasonsToggleText = disclosureToggleText(
    dryRunReasonsExpanded,
    hiddenDryRunReasonCount,
    copy,
  );
  const dryRunReasonsPreviewSummary = disclosurePreviewSummary(
    visibleDryRunReasons.length,
    dryRunReasonEntries.length,
    locale,
  );
  const snapshotsToggleLabel = disclosureToggleLabel(
    locale,
    snapshotsExpanded,
    hiddenSnapshotCount,
    copy,
  );
  const snapshotsToggleText = disclosureToggleText(
    snapshotsExpanded,
    hiddenSnapshotCount,
    copy,
  );
  const snapshotsPreviewSummary = disclosurePreviewSummary(
    visibleSnapshotRefs.length,
    snapshotRefs.length,
    locale,
  );
  useEffect(() => {
    setDryRunReasonsExpanded(false);
  }, [dryRunResult?.run_id, dryRunReasonsKey]);
  useEffect(() => {
    if (!readinessExpanded) {
      setDryRunReasonsExpanded(false);
    }
  }, [readinessExpanded]);
  useEffect(() => {
    setSnapshotsExpanded(false);
  }, [graph?.graph_id, effectiveLatestRunRef?.run_id, snapshotRefsKey]);
  useEffect(() => {
    if (!latestRunExpanded) {
      setSnapshotsExpanded(false);
    }
  }, [latestRunExpanded]);
  const graphTitle = graph?.title?.trim() || copy.canvas;
  const selectedTemplate = useMemo(
    () =>
      templates.find(
        (template) => template.template_id === selectedTemplateId,
      ) ??
      templates[0] ??
      null,
    [selectedTemplateId, templates],
  );
  const selectedTemplateSummary = useMemo(
    () => summarizeTemplate(selectedTemplate, locale),
    [locale, selectedTemplate],
  );
  const templateSections = useMemo(
    () => {
      const presetTemplates = templates.filter(
        (template) => !isCustomTemplate(template),
      );
      const customTemplates = templates.filter((template) =>
        isCustomTemplate(template),
      );
      return [
        {
          id: "preset",
          label: copy.presetTemplates,
          hint: copy.presetTemplatesHint,
          empty: copy.noTemplates,
          templates: presetTemplates,
        },
        {
          id: "custom",
          label: copy.customTemplates,
          hint: copy.customTemplatesHint,
          empty: copy.noCustomTemplates,
          templates: customTemplates,
        },
      ];
    },
    [
      copy.customTemplates,
      copy.customTemplatesHint,
      copy.noCustomTemplates,
      copy.noTemplates,
      copy.presetTemplates,
      copy.presetTemplatesHint,
      templates,
    ],
  );
  const [activeSidebarPane, setActiveSidebarPane] =
    useState<SidebarPaneId>("nodes");
  const sidebarPanes = useMemo(
    () => [
      {
        id: "nodes" as const,
        label: copy.nodePalette,
        count: graph?.nodes.length ?? 0,
        icon: <Boxes size={15} />,
        title: graph ? copy.paletteHint : copy.browseNodes,
        disabled: false,
      },
      {
        id: "edges" as const,
        label: copy.edges,
        count: graph?.edges.length ?? 0,
        icon: <GitBranch size={15} />,
        title: copy.createEdgeTitle,
        disabled: !graph,
      },
    ],
    [
      copy.browseNodes,
      copy.createEdgeTitle,
      copy.edges,
      copy.nodePalette,
      copy.paletteHint,
      graph,
    ],
  );
  const activeSidebarPaneMeta =
    sidebarPanes.find((pane) => pane.id === activeSidebarPane) ??
    sidebarPanes[0];
  const resizeSidebarLabel = `Resize ${copy.nodePalette} panel`;
  /*
      ? `拖动调整${copy.templates}侧栏宽度`
      ? `拖动调整${copy.inspector}侧栏宽度`
  */
  const taskGraphGridStyle = useMemo(
    () =>
      ({
        "--task-graph-sidebar-width": `${sidebarWidth}px`,
      }) as CSSProperties,
    [sidebarWidth],
  );
  const canReplayLatestRun = Boolean(
    graph &&
    effectiveLatestRunRef &&
    effectiveLatestRunRef.status !== "running" &&
    effectiveLatestRunRef.status !== "paused_for_review" &&
    !String(effectiveLatestRunRef.status || "").startsWith("dry_run"),
  );
  const canRetryLatestDryRun = Boolean(
    graph &&
    effectiveLatestRunRef &&
    String(effectiveLatestRunRef.status || "").startsWith("dry_run"),
  );
  const latestRunRecovery = effectiveLatestRunRef?.policy_snapshot?.recovery ?? null;
  const canResumeLatestRun = Boolean(
    effectiveLatestRunRef &&
    effectiveLatestRunRef.status === "cancelled",
  );
  const hasFailedOrBlockedNodes = Boolean(
    effectiveLatestRunRef &&
    ((effectiveLatestRunRef.node_status_counts.failed ?? 0) > 0 ||
      (effectiveLatestRunRef.node_status_counts.blocked ?? 0) > 0 ||
      (effectiveLatestRunRef.node_outcome_counts?.failed ?? 0) > 0 ||
      (effectiveLatestRunRef.node_outcome_counts?.blocked ?? 0) > 0),
  );
  const canRetryFailedNodes = Boolean(
    effectiveLatestRunRef &&
    effectiveLatestRunRef.status !== "running" &&
    effectiveLatestRunRef.status !== "paused_for_review" &&
    hasFailedOrBlockedNodes,
  );
  const canRerunSelectedNode = Boolean(
    effectiveLatestRunRef &&
    selectedNode &&
    effectiveLatestRunRef.status !== "running" &&
    effectiveLatestRunRef.status !== "paused_for_review" &&
    !String(effectiveLatestRunRef.status || "").startsWith("dry_run"),
  );
  const recoveryArtifactRefs = useMemo(
    () =>
      (effectiveLatestRunRef?.artifact_refs ?? []).filter((artifact) =>
        /recovery-(manifest|report)/.test(String(artifact.artifact_id || "")),
      ),
    [effectiveLatestRunRef?.artifact_refs],
  );
  const recoveryStrategyLabel = useMemo(() => {
    switch (String(latestRunRecovery?.strategy || "").trim()) {
      case "resume_run":
        return copy.resumeRun;
      case "retry_failed_nodes":
        return copy.retryFailedNodes;
      case "rerun_selected_nodes":
        return copy.rerunSelectedNodes;
      case "partial_execution":
        return copy.partialRerun;
      default:
        return String(latestRunRecovery?.strategy || "").trim();
    }
  }, [
    copy.partialRerun,
    copy.rerunSelectedNodes,
    copy.resumeRun,
    copy.retryFailedNodes,
    latestRunRecovery?.strategy,
  ]);

  useEffect(() => {
    setRecoveryExpanded(Boolean(latestRunRecovery));
  }, [effectiveLatestRunRef?.run_id, latestRunRecovery]);

  useEffect(() => {
    if (!latestRunRecovery) return;
    setRecoveryExpanded(true);
    setLatestRunExpanded(true);
    setInspectorWorkspace("run");
  }, [latestRunRecovery]);

  useEffect(() => {
    if (activeSidebarPane === "edges" && !graph) {
      setActiveSidebarPane("nodes");
    }
  }, [activeSidebarPane, graph]);

  const openSidebarPane = (paneId: SidebarPaneId) => {
    setActiveSidebarPane(paneId);
    setSidebarExpanded(true);
  };

  const recenterCanvasViewport = (nextScale: number) => {
    requestAnimationFrame(() => {
      const canvasElement = canvasRef.current;
      if (!canvasElement) return;
      const maxScrollLeft = Math.max(
        0,
        stageWidth * nextScale - canvasElement.clientWidth,
      );
      const maxScrollTop = Math.max(
        0,
        stageHeight * nextScale - canvasElement.clientHeight,
      );
      canvasElement.scrollTo({
        left: maxScrollLeft / 2,
        top: maxScrollTop / 2,
      });
    });
  };

  const applyCanvasScale = (
    nextScale: number,
    options?: { center?: boolean; reset?: boolean },
  ) => {
    const normalizedScale = clamp(
      Number(nextScale.toFixed(2)),
      MIN_CANVAS_SCALE,
      MAX_CANVAS_SCALE,
    );
    setCanvasScale(normalizedScale);
    requestAnimationFrame(() => {
      const canvasElement = canvasRef.current;
      if (!canvasElement) return;
      if (options?.reset) {
        canvasElement.scrollTo({ left: 0, top: 0 });
        return;
      }
      if (options?.center) {
        recenterCanvasViewport(normalizedScale);
      }
    });
  };

  const handleSelectRunEvent = (event: TaskGraphRunTimelineEvent) => {
    setSelectedRunEventId(event.event_id);
    if (
      event.edge_id &&
      graph?.edges.some((edge) => edge.edge_id === event.edge_id)
    ) {
      setIsCreatingEdge(false);
      onSelectEdge(event.edge_id);
      return;
    }
    if (
      event.node_id &&
      graph?.nodes.some((node) => node.node_id === event.node_id)
    ) {
      setIsCreatingEdge(false);
      onSelectNode(event.node_id);
      return;
    }
    if (
      event.event_type === "approval_requested" &&
      effectiveLatestRunRef?.approval_details?.node_id &&
      graph?.nodes.some(
        (node) =>
          node.node_id === effectiveLatestRunRef.approval_details?.node_id,
      )
    ) {
      setIsCreatingEdge(false);
      onSelectNode(effectiveLatestRunRef.approval_details.node_id);
    }
  };

  const handleFitView = () => {
    const canvasElement = canvasRef.current;
    if (!canvasElement) return;
    const availableWidth = Math.max(
      320,
      canvasElement.clientWidth - STAGE_PADDING * 2,
    );
    const availableHeight = Math.max(
      240,
      canvasElement.clientHeight - STAGE_PADDING * 2,
    );
    const nextScale = Math.min(
      MAX_CANVAS_SCALE,
      Math.max(
        MIN_CANVAS_SCALE,
        Math.min(availableWidth / stageWidth, availableHeight / stageHeight),
      ),
    );
    applyCanvasScale(nextScale, { center: true });
  };

  const handleResetView = () => {
    applyCanvasScale(DEFAULT_CANVAS_SCALE, { reset: true });
  };

  const handleZoomIn = () => {
    applyCanvasScale(canvasScale + 0.15, { center: true });
  };

  const handleZoomOut = () => {
    applyCanvasScale(canvasScale - 0.15, { center: true });
  };

  const saveNode = () => {
    if (!selectedNode || !nodeDraft || effectiveNodeDraftError) return;
    const parsedSchema = parseNodeSchemaText(
      nodeDraft.machine_result_schema_text,
    );
    if (!parsedSchema) return;
    const nextExecutionPolicy = {
      ...(asRecord(selectedNode.execution_policy) ?? {}),
      allow_provider_calls: nodeDraft.allow_provider_calls,
      allow_code_changes: nodeDraft.allow_code_changes,
      allow_install: nodeDraft.allow_install,
      requires_human_approval: nodeDraft.requires_human_approval,
    };
    const nextOutputContract = {
      ...(asRecord(selectedNode.output_contract) ?? {}),
      artifact_outputs: parseList(nodeDraft.artifact_outputs_text),
      artifact_only: nodeDraft.artifact_only,
      human_summary_required: nodeDraft.human_summary_required,
      machine_result_schema: parsedSchema,
    };
    const nextApprovalGate =
      nodeDraft.requires_human_approval && nodeDraft.approval_review_kind.trim()
        ? { review_kind: nodeDraft.approval_review_kind.trim() }
        : undefined;
    onSaveNode(selectedNode.node_id, {
      label: nodeDraft.label.trim(),
      provider_id: nodeDraft.provider_id.trim(),
      model_id: nodeDraft.model_id.trim(),
      reasoning_effort: nodeDraft.reasoning_effort,
      permission_mode: nodeDraft.permission_mode,
      collaboration_mode: nodeDraft.collaboration_mode,
      execution_backend: nodeDraft.execution_backend,
      human_summary_template: nodeDraft.human_summary_template.trim(),
      machine_result_schema: parsedSchema,
      execution_policy: nextExecutionPolicy,
      output_contract: nextOutputContract,
      ...(nextApprovalGate ? { approval_gate: nextApprovalGate } : {}),
      ui_hints: {
        ...(asRecord(selectedNode.ui_hints) ?? {}),
        context_policy_preset: nodeDraft.context_policy_preset,
        memory_policy_preset: nodeDraft.memory_policy_preset,
        node_type_config: nodeDraft.node_type_config,
        node_type_id:
          selectedNodeTypeSpec?.type_id ??
          asRecord(selectedNode.ui_hints)?.node_type_id,
        node_type_registry_fingerprint:
          nodeTypeRegistry?.registry_fingerprint ??
          asRecord(selectedNode.ui_hints)?.node_type_registry_fingerprint,
      },
    });
    const savedDraft: NodeDraft = {
      ...nodeDraft,
      label: nodeDraft.label.trim(),
      provider_id: nodeDraft.provider_id.trim(),
      model_id: nodeDraft.model_id.trim(),
      human_summary_template: nodeDraft.human_summary_template.trim(),
      machine_result_schema_text: stringifyJson(parsedSchema),
      artifact_outputs_text: stringifyList(
        parseList(nodeDraft.artifact_outputs_text),
      ),
      approval_review_kind: nodeDraft.requires_human_approval
        ? nodeDraft.approval_review_kind.trim()
        : "",
    };
    setNodeDraft(savedDraft);
    setNodeDraftBaseline(savedDraft);
    closeInspectorDialog();
  };

  const saveEdge = () => {
    if (!graph || !edgeDraft || edgeDraftError) return;
    const includedArtifacts = normalizeIncludedArtifactsForMode(
      edgeDraft.artifact_mode,
      parseList(edgeDraft.included_artifacts_text),
    );
    const contextPolicy: TaskGraphContextPolicy = {
      policy_id:
        selectedEdge?.context_policy.policy_id ||
        `policy_${sanitizeToken(edgeDraft.from_node_id)}_${sanitizeToken(edgeDraft.to_node_id)}_${sanitizeToken(edgeDraft.edge_type)}`,
      history_mode: edgeDraft.history_mode,
      artifact_mode: edgeDraft.artifact_mode,
      exclude_private_memory: edgeDraft.exclude_private_memory,
      include_machine_results: edgeDraft.include_machine_results,
      include_human_summaries: edgeDraft.include_human_summaries,
      summary_strategy: edgeDraft.summary_strategy,
      history_length: Number.parseInt(edgeDraft.history_length, 10),
      included_artifacts: includedArtifacts,
      resource_refs: parseList(edgeDraft.resource_refs_text),
    };
    const handoffContract = {
      message_template: edgeDraft.handoff_message_template.trim(),
      message_part_modes: edgeMessagePartModes(edgeDraft),
      required_output_schema_refs: parseList(
        edgeDraft.required_output_schema_refs_text,
      ),
      port_bindings: edgePortCompatibility?.matches.map((match) => ({
        from_port_id: match.source.key,
        to_port_id: match.target.key,
      })),
    };
    onSaveEdge({
      edge_id: isCreatingEdge ? undefined : selectedEdge?.edge_id,
      from_node_id: edgeDraft.from_node_id,
      to_node_id: edgeDraft.to_node_id,
      edge_type: edgeDraft.edge_type,
      handoff_contract: handoffContract,
      context_policy: contextPolicy,
      status: selectedEdge?.status ?? "ready",
    });
    const savedDraft: EdgeDraft = {
      ...edgeDraft,
      handoff_message_template: edgeDraft.handoff_message_template.trim(),
      required_output_schema_refs_text: stringifyList(
        parseList(edgeDraft.required_output_schema_refs_text),
      ),
      history_length: String(contextPolicy.history_length),
      included_artifacts_text: stringifyList(includedArtifacts),
      resource_refs_text: stringifyList(parseList(edgeDraft.resource_refs_text)),
    };
    setEdgeDraft(savedDraft);
    setEdgeDraftBaseline(savedDraft);
    closeInspectorDialog();
  };

  const openInspectorDialog = (workspace?: "selection" | "run") => {
    if (workspace) {
      setInspectorWorkspace(workspace);
      setSelectionInspectorRequested(workspace === "selection");
      setRunInspectorRequested(workspace === "run");
      writePendingRunInspectorReopen(
        pendingRunInspectorStorageKey,
        workspace === "run",
      );
    }
    setInspectorExpanded(true);
  };

  const closeInspectorDialog = () => {
    writePendingRunInspectorReopen(pendingRunInspectorStorageKey, false);
    setInspectorExpanded(false);
    setSelectionInspectorRequested(false);
    setRunInspectorRequested(false);
  };

  const beginCanvasEdgeDraft = (sourceNodeId: string) => {
    if (!graph || graph.nodes.length < 2) return;
    if (isCreatingEdge && edgeCreateSourceId === sourceNodeId) {
      setIsCreatingEdge(false);
      return;
    }
    setIsCreatingEdge(true);
    setEdgeCreateSourceId(sourceNodeId);
    setEdgeDraft(defaultCreateEdgeDraft(graph, sourceNodeId));
    setEdgeDraftBaseline(defaultCreateEdgeDraft(graph, sourceNodeId));
    onSelectNode(sourceNodeId);
  };

  const startCreateEdge = () => {
    if (!graph || graph.nodes.length < 2) return;
    beginCanvasEdgeDraft(selectedNode?.node_id ?? graph.nodes[0]?.node_id ?? "");
    openInspectorDialog("selection");
  };

  const createNodeFromPalette = (
    kind: string,
    position?: TaskGraphNodePosition | null,
  ) => {
    if (!graph) return;
    setIsCreatingEdge(false);
    onCreateNode({ kind, position });
  };

  const handlePaletteDragStart = (
    event: ReactDragEvent<HTMLButtonElement>,
    kind: string,
  ) => {
    event.dataTransfer.effectAllowed = "copy";
    event.dataTransfer.setData(
      "application/x-astrabridge-task-graph-node-kind",
      kind,
    );
    setHoveredPaletteKind(kind);
  };

  const handleCanvasDrop = (event: ReactDragEvent<HTMLDivElement>) => {
    const kind = event.dataTransfer.getData(
      "application/x-astrabridge-task-graph-node-kind",
    );
    if (!kind || !graph || !stageRef.current) return;
    event.preventDefault();
    const stageRect = stageRef.current.getBoundingClientRect();
    createNodeFromPalette(kind, {
      x: Math.max(
        16,
        Math.round(
          (event.clientX - stageRect.left) / canvasScale - NODE_CARD_WIDTH / 2,
        ),
      ),
      y: Math.max(
        16,
        Math.round(
          (event.clientY - stageRect.top) / canvasScale - NODE_CARD_HEIGHT / 2,
        ),
      ),
    });
    setHoveredPaletteKind(null);
  };

  const selectEdgeTargetNode = (nodeId: string) => {
    if (!isCreatingEdge) return false;
    if (edgeCreateSourceId && edgeCreateSourceId === nodeId) return false;
    setEdgeDraft((current) =>
      current ? { ...current, to_node_id: nodeId } : current,
    );
    openInspectorDialog("selection");
    return true;
  };

  const startPanelResize = (side: "left", clientX: number) => {
    setPanelResizeState({
      side,
      startX: clientX,
      startWidth: sidebarWidth,
    });
  };

  const handlePanelResizeKeyDown = (
    side: "left",
    event: ReactKeyboardEvent<HTMLDivElement>,
  ) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const delta = event.key === "ArrowLeft" ? -18 : 18;
    setSidebarWidth((current) =>
      normalizeTaskGraphPanelWidth(side, current + delta),
    );
  };

  function renderArtifactLink({
    key,
    path,
    label,
    testId,
  }: {
    key: string;
    path: string;
    label: string;
    testId: string;
  }) {
    return (
      <button
        type="button"
        key={key}
        className="task-graph-worker-artifact-link"
        data-testid={testId}
        title={path}
        onClick={(event) => {
          event.preventDefault();
          if (onInspectArtifactPath) {
            onInspectArtifactPath(path);
          }
        }}
      >
        <span className="task-graph-worker-artifact-copy">
          <span className="task-graph-worker-artifact-label">{label}</span>
          <span className="task-graph-worker-artifact-path">
            {artifactFilename(path)}
          </span>
        </span>
      </button>
    );
  }

  function renderRuntimeStatusPill(
    status: string | null | undefined,
    testId?: string,
  ) {
    const normalizedStatus = String(status || "").trim();
    if (!normalizedStatus) return null;
    const tone = statusVisualTone(normalizedStatus);
    return (
      <span
        className={`task-graph-node-state-pill task-graph-node-state-${tone}`}
        data-testid={testId}
      >
        {normalizedStatus}
      </span>
    );
  }

  const selectedNodeRunPanel =
    selectedNode && effectiveLatestRunRef ? (
      <details
        className="task-graph-inline-section task-graph-selection-run-panel"
        data-testid="task-graph-selection-node-run-panel"
      >
        <summary
          className="task-graph-inline-section-summary"
          title={copy.inspectRunDetails}
        >
          <strong>{copy.latestNodeRun}</strong>
          {renderRuntimeStatusPill(
            selectedNodeRunDetails?.status,
            "task-graph-selection-node-run-status",
          )}
        </summary>
        <div className="task-graph-selection-run-body">
          {selectedNodeRunDetails?.binding ? (
            <>
              <div className="task-graph-run-meta">
                <span className="task-graph-run-metric">
                  {shortThreadId(selectedNodeRunDetails.binding.parent_thread_id)}
                  {" -> "}
                  {shortThreadId(selectedNodeRunDetails.binding.worker_thread_id)}
                </span>
                {selectedNodeRunDetails.relatedEvents.length ? (
                  <span className="task-graph-run-metric">
                    {selectedNodeRunDetails.relatedEvents.length}{" "}
                    {copy.relatedEvents}
                  </span>
                ) : null}
              </div>
              {selectedNodeRunDetails.binding.output_summary?.human_summary ? (
                <p
                  className="task-graph-worker-summary"
                  data-testid="task-graph-selection-node-run-summary"
                >
                  {selectedNodeRunDetails.binding.output_summary.human_summary}
                </p>
              ) : null}
              {selectedNodeRunDetails.binding.output_summary?.next_action_hints
                ?.length ? (
                <div className="task-graph-selection-run-list">
                  <span className="task-graph-variable-label">
                    {copy.nextHints}
                  </span>
                  <ul data-testid="task-graph-selection-node-run-hints">
                    {selectedNodeRunDetails.binding.output_summary.next_action_hints.map(
                      (hint) => (
                        <li key={hint}>{hint}</li>
                      ),
                    )}
                  </ul>
                </div>
              ) : null}
              {selectedNodeRunDetails.binding.artifact_refs?.length ? (
                <div
                  className="task-graph-worker-artifacts"
                  data-testid="task-graph-selection-node-run-artifacts"
                >
                  {selectedNodeRunDetails.binding.artifact_refs.map((artifact) =>
                    renderArtifactLink({
                      key: `${selectedNodeRunDetails.binding?.binding_id}:${artifact.artifact_id}`,
                      path: artifact.path,
                      label: artifactLabel(artifact),
                      testId: `task-graph-selection-node-run-artifact-${artifact.artifact_id}`,
                    }),
                  )}
                </div>
              ) : null}
            </>
          ) : (
            <p
              className="task-graph-muted"
              data-testid="task-graph-selection-node-run-empty"
            >
              {copy.noNodeRunDetails}
            </p>
          )}
          {selectedNodeRunDetails?.latestEvent ? (
            <div
              className="task-graph-selection-run-event"
              data-testid="task-graph-selection-node-run-event"
            >
              <span className="task-graph-variable-label">{copy.latestEvent}</span>
              <strong>
                {selectedNodeRunDetails.latestEvent.summary ||
                  selectedNodeRunDetails.latestEvent.event_type}
              </strong>
              <small>
                {new Date(
                  selectedNodeRunDetails.latestEvent.created_at,
                ).toLocaleString()}
              </small>
            </div>
          ) : null}
        </div>
      </details>
    ) : null;

  const selectedEdgeRunPanel =
    selectedEdge && effectiveLatestRunRef ? (
      <details
        className="task-graph-inline-section task-graph-selection-run-panel"
        data-testid="task-graph-selection-edge-run-panel"
      >
        <summary
          className="task-graph-inline-section-summary"
          title={copy.inspectRunDetails}
        >
          <strong>{copy.latestEdgeRun}</strong>
          {renderRuntimeStatusPill(
            selectedEdgeRunDetails?.status,
            "task-graph-selection-edge-run-status",
          )}
        </summary>
        <div className="task-graph-selection-run-body">
          {selectedEdgeRunDetails?.handoffs.length ? (
            <>
              <div className="task-graph-run-meta">
                <span className="task-graph-run-metric">
                  {selectedEdgeRunDetails.handoffs.length} {copy.relatedEvents}
                </span>
                <span className="task-graph-run-metric">
                  {copy.to}:{" "}
                  {labelForNodeId(
                    nodeMap,
                    selectedEdgeRunDetails.handoffs[0]?.handoff.to_node_id,
                  )}
                </span>
              </div>
              <div
                className="task-graph-selection-run-event"
                data-testid="task-graph-selection-edge-run-handoff"
              >
                <span className="task-graph-variable-label">
                  {copy.handoffInput}
                </span>
                <strong>
                  {selectedEdgeRunDetails.handoffs[0]?.handoff.downstream_input
                    .source || selectedEdge.edge_type}
                </strong>
                <small>
                  {selectedEdgeRunDetails.handoffs[0]?.handoff.downstream_input
                    .artifact_paths.length ?? 0}{" "}
                  {copy.artifactPaths}
                </small>
              </div>
              {selectedEdgeRunDetails.handoffs[0]?.handoff.downstream_input
                .artifact_paths.length ? (
                <div
                  className="task-graph-selection-run-list"
                  data-testid="task-graph-selection-edge-run-artifact-paths"
                >
                  <span className="task-graph-variable-label">
                    {copy.artifactPaths}
                  </span>
                  <ul>
                    {selectedEdgeRunDetails.handoffs[0].handoff.downstream_input.artifact_paths.map(
                      (artifactPath) => (
                        <li key={artifactPath}>{artifactPath}</li>
                      ),
                    )}
                  </ul>
                </div>
              ) : null}
            </>
          ) : (
            <p
              className="task-graph-muted"
              data-testid="task-graph-selection-edge-run-empty"
            >
              {copy.noEdgeRunDetails}
            </p>
          )}
          {selectedEdgeRunDetails?.latestEvent ? (
            <div
              className="task-graph-selection-run-event"
              data-testid="task-graph-selection-edge-run-event"
            >
              <span className="task-graph-variable-label">{copy.latestEvent}</span>
              <strong>
                {selectedEdgeRunDetails.latestEvent.summary ||
                  selectedEdgeRunDetails.latestEvent.event_type}
              </strong>
              <small>
                {new Date(
                  selectedEdgeRunDetails.latestEvent.created_at,
                ).toLocaleString()}
              </small>
            </div>
          ) : null}
        </div>
      </details>
    ) : null;

  const runReadinessPanel =
    dryRunResult || dryRunError ? (
      <details
        className="task-graph-dock-panel task-graph-dock-panel-inline"
        data-testid="task-graph-dry-run-panel"
        open={readinessExpanded}
        onToggle={(event) => setReadinessExpanded(event.currentTarget.open)}
      >
        <summary
          className="task-graph-dock-summary"
          title={readinessExpanded ? copy.collapsePanel : copy.expandPanel}
        >
          <span className="task-graph-dock-summary-main">
            {readinessExpanded ? (
              <ChevronDown size={14} />
            ) : (
              <ChevronRight size={14} />
            )}
            <strong>{copy.runReadiness}</strong>
            {dryRunResult ? (
              <span
                className={`task-graph-status-pill task-graph-status-${dryRunResult.overall_status}`}
              >
                {dryRunResult.overall_status}
              </span>
            ) : null}
          </span>
          {dryRunResult ? (
            <span className="task-graph-dock-summary-meta">
              {dryRunResult.status_counts.pass ?? 0} /{" "}
              {dryRunResult.status_counts.warning ?? 0} /{" "}
              {dryRunResult.status_counts.blocked ?? 0}
            </span>
          ) : null}
        </summary>
        <div className="task-graph-readiness-panel">
          {dryRunError ? (
            <p
              className="task-graph-validation"
              data-testid="task-graph-dry-run-error"
            >
              {dryRunError}
            </p>
          ) : null}
          {dryRunResult ? (
            <div className="task-graph-readiness-body">
              <p
                className="task-graph-muted task-graph-readiness-summary"
                data-testid="task-graph-dry-run-summary"
                title={`${dryRunSummaryTitle}\n${dryRunReasonsPreviewSummary}`}
              >
                {dryRunSummaryCompactLabel}
              </p>
              {dryRunReasonEntries.length ? (
                <div className="task-graph-readiness-list-shell">
                  <small
                    className="task-graph-readiness-preview-meta"
                    data-testid="task-graph-dry-run-preview-meta"
                    title={dryRunReasonsPreviewSummary}
                  >
                    {dryRunReasonsPreviewSummary}
                  </small>
                  <ul
                    className={`task-graph-readiness-list${dryRunReasonsExpanded ? " is-expanded" : ""}`}
                    data-testid="task-graph-dry-run-reasons"
                  >
                    {visibleDryRunReasons.map((reason, index) => (
                      <li key={`${index}-${reason.label}`}>
                        <span title={reason.label}>{reason.label}</span>
                        {reason.count > 1 ? (
                          <small
                            className="task-graph-readiness-list-count"
                            title={`${reason.count} repeated nodes`}
                          >
                            x{reason.count}
                          </small>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p
                  className="task-graph-muted"
                  data-testid="task-graph-dry-run-reasons"
                >
                  {copy.noWarnings}
                </p>
              )}
              {hiddenDryRunReasonCount > 0 ? (
                <button
                  type="button"
                  className="task-graph-disclosure-button"
                  data-testid="task-graph-dry-run-reasons-toggle"
                  onClick={() =>
                    setDryRunReasonsExpanded((expanded) => !expanded)
                  }
                  aria-expanded={dryRunReasonsExpanded}
                  aria-label={dryRunReasonsToggleLabel}
                  title={dryRunReasonsToggleLabel}
                >
                  {dryRunReasonsExpanded ? (
                    <ChevronDown size={12} aria-hidden="true" />
                  ) : (
                    <ChevronRight size={12} aria-hidden="true" />
                  )}
                  <span>
                    {dryRunReasonsToggleText}
                  </span>
                </button>
              ) : null}
              {reportHref ? (
                <a
                  href={reportHref}
                  className="ghost-button task-graph-report-link"
                  data-testid="task-graph-open-dry-run-report"
                  title={copy.dryRunTitle}
                >
                  {copy.openReport}
                </a>
              ) : null}
            </div>
          ) : null}
        </div>
      </details>
    ) : null;

  const latestRunPanel =
    effectiveLatestRunRef &&
    (!dryRunResult && !dryRunError || isLiveRunPending || isFixtureRunPending) ? (
    <details
      className="task-graph-dock-panel task-graph-dock-panel-inline task-graph-run-dock-inline"
      data-testid="task-graph-run-panel"
      open={latestRunExpanded}
      onToggle={(event) => setLatestRunExpanded(event.currentTarget.open)}
    >
      <summary
        className="task-graph-dock-summary"
        title={latestRunExpanded ? copy.collapsePanel : copy.expandPanel}
      >
        <span className="task-graph-dock-summary-main">
          {latestRunExpanded ? (
            <ChevronDown size={14} />
          ) : (
            <ChevronRight size={14} />
          )}
          <strong>{copy.latestRun}</strong>
          <span
            className={`task-graph-status-pill task-graph-status-${latestRunDisplayStatus}`}
            data-testid="task-graph-latest-run-status"
            title={latestRunStatusTitle}
          >
            {latestRunDisplayStatus}
          </span>
        </span>
        <span
          className="task-graph-dock-summary-meta"
          data-testid="task-graph-latest-run-summary-meta"
        >
          {latestRunHeadlineSummary}
        </span>
      </summary>
        <div className="task-graph-run-panel">
          {latestRunPrimaryEventSummary ? (
            <div
              className="task-graph-variable task-graph-run-primary-status"
              data-testid="task-graph-run-primary-status"
            >
              <span className="task-graph-variable-label">{copy.latestEvent}</span>
              <strong title={latestRunPrimaryEventSummary}>
                {latestRunPrimaryEventSummary}
              </strong>
            </div>
          ) : null}
          <div className="task-graph-run-meta" data-testid="task-graph-run-meta">
            <span
              className="task-graph-run-metric task-graph-run-metric-id"
              data-testid="task-graph-run-id"
          >
            <span className="task-graph-run-metric-label">
              {locale === "zh-CN" ? "运行" : "Run"}
            </span>
            <strong title={effectiveLatestRunRef.run_id}>
              {shortRunId(effectiveLatestRunRef.run_id)}
            </strong>
          </span>
          <span className="task-graph-run-metric">
            <span className="task-graph-run-metric-label">{copy.workers}</span>
            <strong>{effectiveLatestRunRef.worker_count ?? 0}</strong>
          </span>
          <span className="task-graph-run-metric">
            <span className="task-graph-run-metric-label">{copy.artifacts}</span>
            <strong>{effectiveLatestRunRef.artifact_count}</strong>
          </span>
          {effectiveLatestRunRef.event_count ? (
            <span className="task-graph-run-metric">
              <span className="task-graph-run-metric-label">
                {copy.timeline}
              </span>
              <strong>{effectiveLatestRunRef.event_count}</strong>
            </span>
          ) : null}
          {effectiveLatestRunRef.updated_at ? (
            <span className="task-graph-run-metric">
              <span className="task-graph-run-metric-label">
                {locale === "zh-CN" ? "更新" : "Updated"}
              </span>
              <strong>{formatRunUpdatedAt(effectiveLatestRunRef.updated_at)}</strong>
            </span>
          ) : null}
          <span
            className="task-graph-run-metric"
            data-testid="task-graph-run-metric-tokens"
          >
            <span className="task-graph-run-metric-label">
              {runMetricCopy.tokens}
            </span>
            <strong>{latestRunTokens}</strong>
          </span>
          <span
            className="task-graph-run-metric"
            data-testid="task-graph-run-metric-calls"
          >
            <span className="task-graph-run-metric-label">
              {runMetricCopy.calls}
            </span>
            <strong>{latestRunCalls}</strong>
          </span>
          <span
            className="task-graph-run-metric"
            data-testid="task-graph-run-metric-elapsed"
          >
            <span className="task-graph-run-metric-label">
              {runMetricCopy.elapsed}
            </span>
            <strong>{latestRunElapsed}</strong>
          </span>
          <span
            className="task-graph-run-metric"
            data-testid="task-graph-run-metric-budget"
          >
            <span className="task-graph-run-metric-label">
              {runMetricCopy.budget}
            </span>
            <strong>{latestRunBudget}</strong>
          </span>
          <span
            className="task-graph-run-metric"
            data-testid="task-graph-run-metric-cost"
          >
            <span className="task-graph-run-metric-label">
              {runMetricCopy.cost}
            </span>
            <strong>{latestRunCost}</strong>
          </span>
        </div>
        {effectiveLatestRunRef.diagnostic_refs?.length ? (
          <div
            className="task-graph-run-primary-artifacts"
            data-testid="task-graph-run-primary-artifacts"
          >
            {effectiveLatestRunRef.diagnostic_refs.map((artifact) =>
              renderArtifactLink({
                key: `primary:${artifact.artifact_id}:${artifact.path}`,
                path: artifact.path,
                label: artifact.label || artifact.artifact_kind,
                testId: `task-graph-run-primary-artifact-${artifact.artifact_id}`,
              }),
            )}
          </div>
        ) : null}
        {effectiveLatestRunRef.status === "running" ||
        effectiveLatestRunRef.status === "paused_for_review" ? (
          <div className="task-graph-run-actions">
            <button
              type="button"
              className="ghost-button"
              data-testid="task-graph-cancel-run"
              onClick={onCancelLatestRun}
              disabled={isRunCancellationPending}
              title={copy.cancellableFixtureTitle}
            >
              {isRunCancellationPending ? copy.cancellingRun : copy.cancelRun}
            </button>
          </div>
        ) : null}
        {canResumeLatestRun ||
        canRetryFailedNodes ||
        canRerunSelectedNode ||
        latestRunRecovery ? (
          <details
            className="task-graph-inline-section task-graph-recovery-panel"
            data-testid="task-graph-recovery-panel"
            open={recoveryExpanded}
            onToggle={(event) =>
              setRecoveryExpanded(event.currentTarget.open)
            }
          >
            <summary className="task-graph-inline-section-summary">
              <strong>{copy.recoveryPath}</strong>
              {recoveryStrategyLabel ? (
                <span className="task-graph-inline-section-meta">
                  {recoveryStrategyLabel}
                </span>
              ) : null}
            </summary>
            <div className="task-graph-recovery-body">
              {(canResumeLatestRun || canRetryFailedNodes || canRerunSelectedNode) && (
                <div className="task-graph-run-actions recovery-action-list">
                  {canResumeLatestRun ? (
                    <button
                      type="button"
                      className="ghost-button"
                      data-testid="task-graph-recovery-resume"
                      onClick={() => onRecoverLatestRun({ strategy: "resume_run" })}
                      disabled={isRunRecoveryPending}
                    >
                      {isRunRecoveryPending ? copy.recoveringRun : copy.resumeRun}
                    </button>
                  ) : null}
                  {canRetryFailedNodes ? (
                    <button
                      type="button"
                      className="ghost-button"
                      data-testid="task-graph-recovery-retry-failed"
                      onClick={() =>
                        onRecoverLatestRun({ strategy: "retry_failed_nodes" })
                      }
                      disabled={isRunRecoveryPending}
                    >
                      {isRunRecoveryPending ? copy.recoveringRun : copy.retryFailedNodes}
                    </button>
                  ) : null}
                  {canRerunSelectedNode ? (
                    <>
                      <button
                        type="button"
                        className="ghost-button"
                        data-testid="task-graph-recovery-rerun-selected"
                        onClick={() =>
                          onRecoverLatestRun({
                            strategy: "rerun_selected_nodes",
                            selectedNodeIds: selectedNode ? [selectedNode.node_id] : [],
                          })
                        }
                        disabled={isRunRecoveryPending}
                      >
                        {isRunRecoveryPending ? copy.recoveringRun : copy.rerunSelectedNodes}
                      </button>
                      <button
                        type="button"
                        className="ghost-button"
                        data-testid="task-graph-recovery-partial-selected"
                        onClick={() =>
                          onRecoverLatestRun({
                            strategy: "partial_execution",
                            selectedNodeIds: selectedNode ? [selectedNode.node_id] : [],
                          })
                        }
                        disabled={isRunRecoveryPending}
                      >
                        {isRunRecoveryPending ? copy.recoveringRun : copy.partialRerun}
                      </button>
                    </>
                  ) : null}
                </div>
              )}
              {latestRunRecovery ? (
                <div
                  className="task-graph-recovery-summary"
                  data-testid="task-graph-recovery-summary"
                >
                  {latestRunRecovery.source_run_id ? (
                    <div className="task-graph-recovery-row">
                      <span>{copy.recoverySourceRun}</span>
                      <strong>{latestRunRecovery.source_run_id}</strong>
                    </div>
                  ) : null}
                  {latestRunRecovery.rerun_node_ids?.length ? (
                    <div className="task-graph-recovery-block">
                      <span className="task-graph-recovery-block-label">
                        {copy.rerunNodes}
                      </span>
                      <div className="task-graph-recovery-chip-list">
                        {latestRunRecovery.rerun_node_ids.map((nodeId) => (
                          <span
                            key={`rerun:${nodeId}`}
                            className="task-graph-worker-handoff-chip"
                            data-testid={`task-graph-recovery-rerun-${nodeId}`}
                          >
                            {labelForNodeId(nodeMap, nodeId)}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {latestRunRecovery.reused_node_ids?.length ? (
                    <div className="task-graph-recovery-block">
                      <span className="task-graph-recovery-block-label">
                        {copy.reusedNodes}
                      </span>
                      <div className="task-graph-recovery-chip-list">
                        {latestRunRecovery.reused_node_ids.map((nodeId) => (
                          <span
                            key={`reused:${nodeId}`}
                            className="task-graph-worker-handoff-chip"
                            data-testid={`task-graph-recovery-reused-${nodeId}`}
                          >
                            {labelForNodeId(nodeMap, nodeId)}
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {recoveryArtifactRefs.length ? (
                    <div className="task-graph-recovery-block">
                      <span className="task-graph-recovery-block-label">
                        {copy.recoveryArtifacts}
                      </span>
                      <div className="task-graph-run-diagnostic-links">
                        {recoveryArtifactRefs.map((artifact) =>
                          renderArtifactLink({
                            key: `recovery:${artifact.artifact_id}:${artifact.path}`,
                            path: artifact.path,
                            label:
                              artifact.label ||
                              (String(artifact.artifact_id || "").includes("manifest")
                                ? copy.recoveryManifest
                                : copy.recoveryReport),
                            testId: `task-graph-recovery-artifact-${artifact.artifact_id}`,
                          }),
                        )}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </details>
        ) : null}
        {canRetryLatestDryRun || canReplayLatestRun ? (
          <div className="task-graph-run-actions">
            {canRetryLatestDryRun ? (
              <button
                type="button"
                className="ghost-button"
                data-testid="task-graph-retry-dry-run"
                onClick={() => onRunDryRun({ tokenBudget: normalizedRunTokenBudget })}
                disabled={isDryRunPending}
                title={copy.dryRunTitle}
              >
                {copy.retryDryRun}
              </button>
            ) : null}
            {canReplayLatestRun ? (
              <button
                type="button"
                className="ghost-button"
                data-testid="task-graph-replay-fixture"
                onClick={onRunFixture}
                disabled={isFixtureRunPending}
                title={copy.fixtureTitle}
              >
                {copy.replayFixture}
              </button>
            ) : null}
          </div>
        ) : null}
        {showApprovalPanel && effectiveLatestRunRef.approval_details ? (
          <div
            className={`task-graph-approval-panel task-graph-approval-${effectiveLatestRunRef.approval_details.status}`}
            data-testid="task-graph-approval-panel"
          >
            <div className="task-graph-approval-head">
              <strong title={copy.approvalPanelTitle}>
                {effectiveLatestRunRef.approval_details.status === "pending"
                  ? copy.approvalRequired
                  : effectiveLatestRunRef.approval_details.status === "approved"
                    ? copy.approvalRecorded
                    : effectiveLatestRunRef.approval_details.status ===
                        "expired"
                      ? copy.approvalExpired
                      : copy.approvalRejected}
              </strong>
              {effectiveLatestRunRef.approval_details.review_kind ? (
                <span className="task-graph-approval-kind">
                  {effectiveLatestRunRef.approval_details.review_kind}
                </span>
              ) : null}
            </div>
            {effectiveLatestRunRef.approval_details.reason ? (
              <p
                className="task-graph-approval-copy"
                data-testid="task-graph-approval-reason"
              >
                {effectiveLatestRunRef.approval_details.reason}
              </p>
            ) : null}
            {effectiveLatestRunRef.approval_details.resolution_summary ? (
              <p
                className="task-graph-approval-copy"
                data-testid="task-graph-approval-resolution"
              >
                {effectiveLatestRunRef.approval_details.resolution_summary}
              </p>
            ) : null}
            {effectiveLatestRunRef.approval_details.notes ? (
              <p
                className="task-graph-approval-note"
                data-testid="task-graph-approval-notes"
              >
                {effectiveLatestRunRef.approval_details.notes}
              </p>
            ) : null}
            {effectiveLatestRunRef.approval_details.status === "pending" ? (
              <div className="task-graph-approval-actions">
                <button
                  type="button"
                  className="primary-button"
                  data-testid="task-graph-approval-approve"
                  onClick={onApprovePendingRun}
                  disabled={isApprovalDecisionPending}
                  title={copy.approvalPanelTitle}
                >
                  {isApprovalDecisionPending ? copy.deciding : copy.approveGate}
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  data-testid="task-graph-approval-reject"
                  onClick={onRejectPendingRun}
                  disabled={isApprovalDecisionPending}
                  title={copy.approvalPanelTitle}
                >
                  {copy.rejectGate}
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
        {selectedRunEvent && selectedRunEventTarget ? (
          <div
            className="task-graph-run-event-focus"
            data-testid="task-graph-run-event-focus"
          >
            <span className="task-graph-run-event-focus-label">
              {selectedRunEventTarget.kind === "edge"
                ? copy.eventTargetEdge
                : copy.eventTargetNode}
            </span>
            <strong>{selectedRunEventTarget.label}</strong>
          </div>
        ) : null}
        {effectiveLatestRunRef.timeline_events?.length ? (
          <details
            className="task-graph-inline-section"
            open={
              effectiveLatestRunRef.status === "running" ||
              effectiveLatestRunRef.status === "paused_for_review"
            }
          >
            <summary className="task-graph-inline-section-summary">
              <strong>{copy.timeline}</strong>
              <span className="task-graph-inline-section-meta">
                {effectiveLatestRunRef.timeline_events.length}
              </span>
            </summary>
            <div
              className="task-graph-run-timeline"
              data-testid="task-graph-run-timeline"
            >
              <div className="task-graph-run-timeline-list">
                {effectiveLatestRunRef.timeline_events.map((event) => (
                  <button
                    type="button"
                    key={event.event_id}
                    className={`timeline-step timeline-${event.status || "pending"} ${selectedRunEventId === event.event_id ? "timeline-step-active" : ""}`}
                    data-testid={`task-graph-run-event-${event.event_id}`}
                    onClick={() => handleSelectRunEvent(event)}
                    aria-pressed={selectedRunEventId === event.event_id}
                  >
                    <span className="timeline-dot" aria-hidden="true" />
                    <div>
                      <strong>{event.summary || event.event_type}</strong>
                      <small>
                        {event.node_id
                          ? `${labelForNodeId(nodeMap, event.node_id)} / `
                          : ""}
                        {new Date(event.created_at).toLocaleString()}
                      </small>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </details>
        ) : null}
        {effectiveLatestRunRef.diagnostic_refs?.length ? (
          <details className="task-graph-inline-section">
            <summary className="task-graph-inline-section-summary">
              <strong>{copy.diagnostics}</strong>
              <span className="task-graph-inline-section-meta">
                {effectiveLatestRunRef.diagnostic_refs.length}
              </span>
            </summary>
            <div
              className="task-graph-run-diagnostics"
              data-testid="task-graph-run-diagnostics"
            >
              <div className="task-graph-run-diagnostic-links">
                {effectiveLatestRunRef.diagnostic_refs.map((artifact) =>
                  renderArtifactLink({
                    key: `${artifact.artifact_id}:${artifact.path}`,
                    path: artifact.path,
                    label: artifact.label || artifact.artifact_kind,
                    testId: `task-graph-run-diagnostic-${artifact.artifact_id}`,
                  }),
                )}
              </div>
            </div>
          </details>
        ) : null}
        {effectiveLatestRunRef.worker_bindings?.length ? (
          <details
            className="task-graph-inline-section"
            open={
              effectiveLatestRunRef.status === "running" ||
              effectiveLatestRunRef.status === "paused_for_review"
            }
          >
            <summary className="task-graph-inline-section-summary">
              <strong>{copy.workerOutputs}</strong>
              <span className="task-graph-inline-section-meta">
                {effectiveLatestRunRef.worker_bindings.length}
              </span>
            </summary>
            <div
              className="task-graph-worker-timeline"
              data-testid="task-graph-worker-timeline"
            >
              {effectiveLatestRunRef.worker_bindings.map((binding) => (
                <section
                  key={binding.binding_id}
                  className="task-graph-worker-card"
                  data-testid={`task-graph-worker-${binding.node_id}`}
                >
                  <div className="task-graph-worker-head">
                    <div>
                      <strong>
                        {binding.agent_nickname || binding.node_id}
                      </strong>
                      <small>
                        {binding.agent_role ||
                          binding.worker_origin ||
                          "worker"}
                      </small>
                    </div>
                    <span
                      className={`task-graph-worker-state task-graph-worker-state-${binding.status}`}
                    >
                      {binding.status}
                    </span>
                  </div>
                  <p className="task-graph-worker-thread">
                    {shortThreadId(binding.parent_thread_id)} {"->"}{" "}
                    {shortThreadId(binding.worker_thread_id)}
                  </p>
                  {binding.output_summary?.human_summary ? (
                    <p className="task-graph-worker-summary">
                      {binding.output_summary.human_summary}
                    </p>
                  ) : null}
                  {binding.downstream_handoffs?.length ? (
                    <div
                      className="task-graph-worker-handoffs"
                      data-testid={`task-graph-worker-handoffs-${binding.node_id}`}
                    >
                      {binding.downstream_handoffs.map((handoff) => (
                        <span
                          key={`${binding.binding_id}:${handoff.edge_id}`}
                          className="task-graph-worker-handoff-chip"
                        >
                          <span className="task-graph-worker-handoff-kind">
                            {handoff.edge_type}
                          </span>
                          <strong>
                            {labelForNodeId(nodeMap, handoff.to_node_id)}
                          </strong>
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {binding.artifact_refs?.length ? (
                    <div
                      className="task-graph-worker-artifacts"
                      data-testid={`task-graph-worker-artifacts-${binding.node_id}`}
                    >
                      {binding.artifact_refs.map((artifact) =>
                        renderArtifactLink({
                          key: `${binding.binding_id}:${artifact.artifact_id}`,
                          path: artifact.path,
                          label: artifactLabel(artifact),
                          testId: `task-graph-worker-artifact-${binding.node_id}-${artifact.artifact_id}`,
                        }),
                      )}
                    </div>
                  ) : null}
                </section>
              ))}
            </div>
          </details>
        ) : (
          <p className="task-graph-muted" data-testid="task-graph-run-empty">
            {(effectiveLatestRunRef.worker_count ?? 0) > 0
              ? copy.workerOutputsSyncing
              : copy.noWorkerOutputs}
          </p>
        )}
      </div>
    </details>
    ) : null;

  const runWorkspaceSubtitle = dryRunResult || dryRunError
    ? copy.runReadiness
    : effectiveLatestRunRef
      ? [
        shortRunId(effectiveLatestRunRef.run_id),
        latestRunDisplayStatus,
        effectiveLatestRunRef.updated_at
          ? formatRunUpdatedAt(effectiveLatestRunRef.updated_at)
          : "",
      ]
        .filter(Boolean)
        .join(" / ")
      : copy.noRunInspection;

  return (
    <section
      className="task-graph-workspace"
      data-testid="task-graph-workspace"
    >
      <div
        className="task-graph-grid"
        data-testid="task-graph-grid"
        data-sidebar-expanded={sidebarExpanded ? "true" : "false"}
        data-inspector-expanded={inspectorExpanded ? "true" : "false"}
        style={taskGraphGridStyle}
      >
        <aside
          className={`task-graph-sidebar ${sidebarExpanded ? "task-graph-sidebar-expanded" : "task-graph-sidebar-collapsed"}`}
          data-testid="task-graph-template-sidebar"
        >
          <button
            type="button"
            className="task-graph-panel-head task-graph-panel-toggle task-graph-panel-toggle-icon"
            data-testid="task-graph-sidebar-toggle"
            onClick={() => setSidebarExpanded((current) => !current)}
            aria-expanded={sidebarExpanded}
            aria-label={`${activeSidebarPaneMeta.label} / ${sidebarExpanded ? copy.collapsePanel : copy.expandPanel}`}
            title={`${activeSidebarPaneMeta.label} / ${sidebarExpanded ? copy.collapsePanel : copy.expandPanel}`}
            style={{ display: "none" }}
          >
            <span
              className="task-graph-panel-toggle-meta task-graph-panel-toggle-meta-solo"
              aria-hidden="true"
            >
              {sidebarExpanded ? (
                <PanelLeftClose size={14} />
              ) : (
                <PanelLeftOpen size={14} />
              )}
            </span>
          </button>
          {sidebarExpanded ? (
            <>
              <div
                className="task-graph-sidebar-toolbar"
                role="tablist"
                aria-label={copy.nodePalette}
                style={{ display: "none" }}
              >
                {sidebarPanes.map((pane) => {
                  const isActive = pane.id === activeSidebarPane;
                  return (
                    <button
                      key={pane.id}
                      type="button"
                      className={`task-graph-sidebar-pane-button task-graph-sidebar-pane-button-compact ${isActive ? "task-graph-sidebar-pane-button-active" : ""}`}
                      data-testid={`task-graph-sidebar-pane-${pane.id}`}
                      role="tab"
                      aria-selected={isActive}
                      disabled={pane.disabled}
                      onClick={() => setActiveSidebarPane(pane.id)}
                      title={pane.title}
                      aria-label={pane.title}
                    >
                      <span className="task-graph-sidebar-icon" aria-hidden="true">
                        {pane.icon}
                      </span>
                    </button>
                  );
                })}
                {activeSidebarPane === "edges" ? (
                  <button
                    type="button"
                    className="task-graph-inline-action task-graph-sidebar-mini-action"
                    data-testid="task-graph-create-edge"
                    onClick={(event) => {
                      event.preventDefault();
                      startCreateEdge();
                    }}
                    disabled={!graph || graph.nodes.length < 2}
                    title={copy.createEdgeTitle}
                    aria-label={copy.createEdgeTitle}
                  >
                    <Plus size={14} />
                  </button>
                ) : null}
              </div>
              <div className="task-graph-sidebar-body">
                {false ? (
                <section className="task-graph-sidebar-section">
                  <div
                    className="task-graph-template-list"
                    data-testid="task-graph-template-list"
                  >
                    {isLoadingTemplates ? (
                      <p className="task-graph-muted">
                        {copy.loadingTemplates}
                      </p>
                    ) : null}
                    {!isLoadingTemplates && !templates.length ? (
                      <p className="task-graph-muted">{copy.noTemplates}</p>
                    ) : null}
                    {templates.map((template) => (
                      <button
                        key={template.template_id}
                        type="button"
                        className={`task-graph-template-card ${selectedTemplate?.template_id === template.template_id ? "task-graph-template-card-active" : ""}`}
                        data-testid={`task-graph-template-${template.template_id}`}
                        onClick={() =>
                          handleSelectTemplate(template.template_id)
                        }
                        title={template.summary || template.title}
                        aria-pressed={
                          selectedTemplate?.template_id === template.template_id
                        }
                      >
                        <div className="task-graph-template-title-row">
                          <strong>{template.title}</strong>
                          <span>
                            {template.node_count}N / {template.edge_count}E
                          </span>
                        </div>
                        <div className="task-graph-template-kinds">
                          {template.node_kinds
                            .slice(0, 4)
                            .map((kind, index) => (
                              <span
                                key={`${template.template_id}:${kind}:${index}`}
                              >
                                {kind}
                              </span>
                            ))}
                        </div>
                      </button>
                    ))}
                  </div>
                  {selectedTemplate ? (
                    <section
                      className="task-graph-template-summary-panel"
                      data-testid="task-graph-template-summary-panel"
                    >
                      <div className="task-graph-template-summary-head">
                        <div className="task-graph-template-quick-actions">
                          <div className="task-graph-template-quick-copy">
                            <span className="task-graph-template-summary-id">
                              {copy.templateDetails}
                            </span>
                            <strong>{selectedTemplate.title}</strong>
                            <span className="task-graph-template-quick-meta">
                              {selectedTemplate.node_count}N /{" "}
                              {selectedTemplate.edge_count}E
                            </span>
                          </div>
                          <button
                            type="button"
                            className="primary-button task-graph-template-use-button"
                            data-testid="task-graph-template-instantiate"
                            onClick={handleInstantiateSelectedTemplate}
                            disabled={isInstantiating}
                          >
                            {copy.useTemplate}
                          </button>
                        </div>
                        <p className="task-graph-muted task-graph-template-summary-copy">
                          {selectedTemplate.summary || copy.blankTemplateHint}
                        </p>
                      </div>
                      <details className="task-graph-template-detail-panel">
                        <summary className="task-graph-template-summary-disclosure">
                          <strong>{copy.templatePreview}</strong>
                          <span className="task-graph-sidebar-summary-meta">
                            {selectedTemplate.node_count}N /{" "}
                            {selectedTemplate.edge_count}E
                          </span>
                        </summary>
                        <div className="task-graph-template-summary-content">
                          <div
                            className="task-graph-template-preview-shell"
                            data-testid="task-graph-template-preview"
                          >
                            <div className="task-graph-template-preview-head">
                              <strong>{copy.templatePreview}</strong>
                              <span className="task-graph-sidebar-summary-meta">
                                {selectedTemplate.node_count}N /{" "}
                                {selectedTemplate.edge_count}E
                              </span>
                            </div>
                            <div className="task-graph-template-preview-track">
                              {selectedTemplate.preview_graph.nodes.map(
                                (node, index) => {
                                  const visibleKind =
                                    registryUi.kindForTemplate(node.kind);
                                  const item = taskGraphPaletteMeta(
                                    registryUi,
                                    visibleKind,
                                  );
                                  return (
                                    <div
                                      key={`${selectedTemplate.template_id}:preview:${node.node_id}`}
                                      className="task-graph-template-preview-node"
                                    >
                                      <span
                                        className={`task-graph-palette-icon task-graph-node-role-badge-${nodeToneForKind(visibleKind)}`}
                                        aria-hidden="true"
                                      >
                                        {nodeKindIcon(item.icon || visibleKind, 12)}
                                      </span>
                                      <span>{node.label}</span>
                                      {index <
                                      selectedTemplate.preview_graph.nodes
                                        .length -
                                        1 ? (
                                        <span
                                          className="task-graph-template-preview-arrow"
                                          aria-hidden="true"
                                        >
                                          {"->"}
                                        </span>
                                      ) : null}
                                    </div>
                                  );
                                },
                              )}
                            </div>
                          </div>
                          <div className="task-graph-template-summary-grid">
                            <div>
                              <strong>{copy.recommendedProviders}</strong>
                              <p>
                                {selectedTemplate.recommended_provider_ids?.join(
                                  ", ",
                                ) || "—"}
                              </p>
                            </div>
                            <div>
                              <strong>{copy.recommendedModels}</strong>
                              <p>
                                {selectedTemplate.recommended_model_ids?.join(
                                  ", ",
                                ) || "—"}
                              </p>
                            </div>
                          </div>
                          <details
                            className="task-graph-template-meta-block"
                            open
                          >
                            <summary>{copy.expectedArtifacts}</summary>
                            <div className="task-graph-template-meta-chips">
                              {((selectedTemplate.artifact_expectations ?? [])
                                .length
                                ? (selectedTemplate.artifact_expectations ?? [])
                                : ["—"]
                              ).map((item) => (
                                <span
                                  key={`${selectedTemplate.template_id}:artifact:${item}`}
                                >
                                  {item}
                                </span>
                              ))}
                            </div>
                          </details>
                          <details className="task-graph-template-meta-block">
                            <summary>{copy.templatePreflight}</summary>
                            <ul className="task-graph-template-meta-list">
                              {((selectedTemplate.validation_hints ?? [])
                                .length
                                ? (selectedTemplate.validation_hints ?? [])
                                : ["—"]
                              ).map((item) => (
                                <li
                                  key={`${selectedTemplate.template_id}:hint:${item}`}
                                >
                                  {item}
                                </li>
                              ))}
                            </ul>
                          </details>
                          <details className="task-graph-template-meta-block">
                            <summary>{copy.templateConstraints}</summary>
                            <ul className="task-graph-template-meta-list">
                              {((selectedTemplate.constraints ?? []).length
                                ? (selectedTemplate.constraints ?? [])
                                : ["—"]
                              ).map((item) => (
                                <li
                                  key={`${selectedTemplate.template_id}:constraint:${item}`}
                                >
                                  {item}
                                </li>
                              ))}
                            </ul>
                          </details>
                        </div>
                      </details>
                    </section>
                  ) : null}
                </section>
                ) : null}

                {activeSidebarPane === "nodes" ? (
                <section className="task-graph-sidebar-section">
                  <div data-testid="task-graph-node-palette">
                    {registryUi.paletteSections.map((section) => (
                      <section
                        key={section.id}
                        className="task-graph-palette-section"
                        data-testid={`task-graph-palette-section-${section.id}`}
                      >
                        <div className="task-graph-node-palette-grid">
                          {section.kinds.map((kind) => {
                            const item = taskGraphPaletteMeta(registryUi, kind);
                            return (
                              <button
                                key={kind}
                                type="button"
                                className={`task-graph-palette-item ${hoveredPaletteKind === kind ? "task-graph-palette-item-hover" : ""}`}
                                data-testid={`task-graph-palette-add-${kind}`}
                                disabled={!graph}
                                draggable={Boolean(graph)}
                                title={`${item.label}: ${item.description}`}
                                aria-label={item.label}
                                aria-describedby={`task-graph-palette-tooltip-${kind}`}
                                onClick={() => {
                                  setHoveredPaletteKind(kind);
                                  createNodeFromPalette(kind);
                                }}
                                onMouseEnter={() => setHoveredPaletteKind(kind)}
                                onMouseLeave={() =>
                                  setHoveredPaletteKind((current) =>
                                    current === kind ? null : current,
                                  )
                                }
                                onFocus={() => setHoveredPaletteKind(kind)}
                                onBlur={() =>
                                  setHoveredPaletteKind((current) =>
                                    current === kind ? null : current,
                                  )
                                }
                                onDragStart={(event) =>
                                  handlePaletteDragStart(event, kind)
                                }
                                onDragEnd={() => setHoveredPaletteKind(null)}
                              >
                                <span
                                  className={`task-graph-palette-icon task-graph-node-role-badge-${nodeToneForKind(kind)}`}
                                  aria-hidden="true"
                                >
                                  {nodeKindIcon(item.icon || kind, 14)}
                                </span>
                                <span
                                  id={`task-graph-palette-tooltip-${kind}`}
                                  role="tooltip"
                                  className="task-graph-palette-tooltip"
                                  data-testid={`task-graph-palette-tooltip-${kind}`}
                                >
                                  <strong>{item.label}</strong>
                                  <span>{item.description}</span>
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      </section>
                    ))}
                  </div>
                </section>
                ) : null}

                {activeSidebarPane === "edges" ? (
                <section className="task-graph-sidebar-section">
                  <div
                    className="task-graph-edge-list"
                    data-testid="task-graph-edge-list"
                  >
                    {!graph?.edges.length ? (
                      <p className="task-graph-muted">{copy.noEdges}</p>
                    ) : null}
                    {graph?.edges.map((edge) => (
                      <button
                        type="button"
                        key={edge.edge_id}
                        className={`task-graph-edge-chip ${selectedEdge?.edge_id === edge.edge_id && !isCreatingEdge ? "task-graph-edge-chip-active" : ""}`}
                        data-testid={`task-graph-edge-chip-${edge.edge_id}`}
                        onClick={() => {
                          setIsCreatingEdge(false);
                          onSelectEdge(edge.edge_id);
                          openInspectorDialog("selection");
                        }}
                        title={`${edgeLabel(edge, nodeMap)} / ${edge.edge_type}`}
                      >
                        <span className="task-graph-chip-main">
                          <span
                            className="task-graph-edge-chip-icon"
                            aria-hidden="true"
                          >
                            {edgeTypeIcon(edge.edge_type, 12)}
                          </span>
                          <span>{edgeLabel(edge, nodeMap)}</span>
                        </span>
                        <div className="task-graph-chip-meta">
                          <span
                            className="task-graph-port-inline-summary"
                            title={portSummaryTitle(edgePortSummary(edge, graph))}
                          >
                            {renderPortSummaryIcons(edgePortSummary(edge, graph))}
                          </span>
                          {edgeStatusMap.get(edge.edge_id) ? (
                            <span
                              className={`task-graph-status-pill task-graph-status-${edgeStatusMap.get(edge.edge_id)?.status ?? "pass"}`}
                            >
                              {edgeStatusMap.get(edge.edge_id)?.status}
                            </span>
                          ) : null}
                          <small>{edge.edge_type}</small>
                        </div>
                      </button>
                    ))}
                  </div>
                </section>
                ) : null}
              </div>
              <div
                className="resize-handle task-graph-panel-resize-handle task-graph-panel-resize-handle-left"
                data-testid="task-graph-sidebar-resize-handle"
                role="separator"
                aria-orientation="vertical"
                aria-label={resizeSidebarLabel}
                tabIndex={0}
                onMouseDown={(event) => {
                  event.preventDefault();
                  startPanelResize("left", event.clientX);
                }}
                onKeyDown={(event) => handlePanelResizeKeyDown("left", event)}
              />
            </>
          ) : (
            <div className="task-graph-sidebar-rail">
              {sidebarPanes.map((pane) => {
                const isActive = pane.id === activeSidebarPane;
                return (
                  <button
                    key={pane.id}
                    type="button"
                    className={`task-graph-sidebar-rail-button ${isActive ? "task-graph-sidebar-rail-button-active" : ""}`}
                    data-testid={`task-graph-sidebar-rail-${pane.id}`}
                    disabled={pane.disabled}
                    onClick={() => openSidebarPane(pane.id)}
                    title={pane.title || pane.label}
                    aria-label={pane.title || pane.label}
                  >
                    <span className="task-graph-sidebar-icon" aria-hidden="true">
                      {pane.icon}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </aside>

        <div className="task-graph-canvas-panel">
          <div className="task-graph-panel-head">
            <button
              type="button"
              className="task-graph-inline-action task-graph-canvas-icon-button task-graph-graph-title-button"
              data-testid="task-graph-graph-title-button"
              title={graphTitle}
              aria-label={graphTitle}
              onClick={() => {
                if (templates.length) {
                  openTemplateBrowser();
                }
              }}
            >
              <GitBranch size={15} aria-hidden="true" />
            </button>
            <div className="task-graph-canvas-head-actions">
              {importExportError ? (
                <span
                  className="task-graph-inline-status task-graph-validation"
                  data-testid="task-graph-import-export-error"
                >
                  {importExportError}
                </span>
              ) : null}
              {snapshotError ? (
                <span
                  className="task-graph-inline-status task-graph-validation"
                  data-testid="task-graph-snapshot-error"
                >
                  {snapshotError}
                </span>
              ) : null}
              {!importExportError &&
              (lastImportedPath || lastExportedPath || lastExportPreview) ? (
                <span
                  className="task-graph-inline-status"
                  data-testid="task-graph-import-export-status"
                >
                  {lastImportedPath ? (
                    <span data-testid="task-graph-last-imported-path">
                      {copy.importedGraph}: {lastImportedPath}
                    </span>
                  ) : null}
                  {lastExportedPath ? (
                    <span data-testid="task-graph-last-exported-path">
                      {copy.exportedGraph}: {lastExportedPath}
                    </span>
                  ) : null}
                  {lastExportPreview ? (
                    <span data-testid="task-graph-last-export-preview">
                      {copy.exportPreview}: {exportPreviewLineCount}{" "}
                      {copy.lines}
                    </span>
                  ) : null}
                </span>
              ) : null}
              {!snapshotError && snapshotStatus ? (
                <span
                  className="task-graph-inline-status"
                  data-testid="task-graph-snapshot-status"
                >
                  {snapshotStatus}
                </span>
              ) : null}
              <div className="task-graph-canvas-action-groups">
                <div
                  className="task-graph-canvas-run-actions"
                  role="toolbar"
                  aria-label={copy.workspace}
                >
                  <label
                    className="task-graph-run-token-budget"
                    title={copy.tokenBudgetTitle}
                  >
                    <span>{copy.tokenBudget}</span>
                    <input
                      type="number"
                      min={1}
                      step={1000}
                      value={runTokenBudget}
                      onChange={(event) => setRunTokenBudget(Number(event.target.value))}
                      aria-label={copy.tokenBudget}
                      data-testid="task-graph-run-token-budget"
                    />
                  </label>
                  <button
                    type="button"
                    className="ghost-button task-graph-canvas-action-button task-graph-canvas-action-button-primary"
                    data-testid="task-graph-run-live"
                    onClick={() => {
                      openInspectorDialog("run");
                      onRunLive({ tokenBudget: normalizedRunTokenBudget });
                    }}
                    disabled={
                      !graph ||
                      isFixtureRunPending ||
                      isLiveRunPending ||
                      Boolean(runActionDisabledReason)
                    }
                    title={runActionDisabledReason || copy.liveRunTitle}
                    aria-label={runActionDisabledReason || copy.liveRunTitle}
                  >
                    <Play size={13} aria-hidden="true" />
                    <span>
                      {showSyntheticLivePendingRun ? copy.runningLive : copy.runLive}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="ghost-button task-graph-canvas-action-button task-graph-canvas-action-button-primary"
                    data-testid="task-graph-run-fixture"
                    onClick={() => {
                      openInspectorDialog("run");
                      onRunFixture();
                    }}
                    disabled={
                      !graph ||
                      isFixtureRunPending ||
                      isLiveRunPending ||
                      Boolean(runActionDisabledReason)
                    }
                    title={runActionDisabledReason || copy.fixtureTitle}
                    aria-label={runActionDisabledReason || copy.fixtureTitle}
                  >
                    <Boxes size={13} aria-hidden="true" />
                    <span>
                      {isFixtureRunPending
                        ? copy.runningFixture
                        : copy.runFixture}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="ghost-button task-graph-canvas-action-button task-graph-canvas-action-button-primary"
                    data-testid="task-graph-run-cancellable-fixture"
                    onClick={() => {
                      openInspectorDialog("run");
                      onRunCancellableFixture();
                    }}
                    disabled={
                      !graph ||
                      graph.template_id !== "fanout_fanin_research" ||
                      isFixtureRunPending ||
                      isLiveRunPending ||
                      Boolean(runActionDisabledReason)
                    }
                    title={runActionDisabledReason || copy.cancellableFixtureTitle}
                    aria-label={runActionDisabledReason || copy.cancellableFixtureTitle}
                  >
                    <Repeat size={13} aria-hidden="true" />
                    <span>
                      {isFixtureRunPending
                        ? copy.runningFixture
                        : copy.runCancellableFixture}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="ghost-button task-graph-canvas-action-button task-graph-canvas-action-button-primary"
                    data-testid="task-graph-run-dry-run"
                    onClick={() => {
                      if (
                        !graph ||
                        isDryRunPending ||
                        Boolean(runActionDisabledReason)
                      ) {
                        return;
                      }
                      openInspectorDialog("run");
                      onRunDryRun({ tokenBudget: normalizedRunTokenBudget });
                    }}
                    disabled={!graph || isDryRunPending || Boolean(runActionDisabledReason)}
                    title={runActionDisabledReason || copy.dryRunTitle}
                    aria-label={runActionDisabledReason || copy.dryRunTitle}
                  >
                    <TestTubeDiagonal size={13} aria-hidden="true" />
                    <span>
                      {isDryRunPending ? copy.runningDryRun : copy.dryRun}
                    </span>
                  </button>
                </div>
                <div
                  className="task-graph-canvas-secondary-actions"
                  role="toolbar"
                  aria-label={copy.templates}
                >
                  <button
                    type="button"
                    className="ghost-button task-graph-canvas-action-button task-graph-canvas-action-button-utility"
                    data-testid="task-graph-open-template-browser"
                    onClick={openTemplateBrowser}
                    title={copy.chooseTemplate}
                    aria-label={copy.chooseTemplate}
                  >
                    <Sparkles size={13} aria-hidden="true" />
                    <span>{copy.templates}</span>
                  </button>
                  <button
                    type="button"
                    className="ghost-button task-graph-canvas-action-button task-graph-canvas-action-button-utility"
                    data-testid="task-graph-close"
                    onClick={onClose}
                    title={copy.closeTitle}
                    aria-label={copy.closeTitle}
                  >
                    <ArrowLeft size={13} aria-hidden="true" />
                    <span>{copy.backToChat}</span>
                  </button>
                  <button
                    type="button"
                    className="task-graph-inline-action task-graph-canvas-icon-button"
                    data-testid="task-graph-open-run-inspection"
                    onClick={() => openInspectorDialog("run")}
                    title={copy.inspectRunDetails}
                    aria-label={copy.inspectRunDetails}
                  >
                    <Eye size={14} aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    className="task-graph-inline-action task-graph-canvas-icon-button"
                    data-testid="task-graph-import"
                    onClick={onImportGraph}
                    disabled={isImportingGraph}
                    title={
                      isImportingGraph ? copy.importingGraph : copy.importGraph
                    }
                    aria-label={
                      isImportingGraph ? copy.importingGraph : copy.importGraph
                    }
                  >
                    <FileUp size={14} aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    className="task-graph-inline-action task-graph-canvas-icon-button"
                    data-testid="task-graph-export"
                    onClick={onExportGraph}
                    disabled={!graph || isExportingGraph}
                    title={
                      isExportingGraph ? copy.exportingGraph : copy.exportGraph
                    }
                    aria-label={
                      isExportingGraph ? copy.exportingGraph : copy.exportGraph
                    }
                  >
                    <FileDown size={14} aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    className="task-graph-inline-action task-graph-canvas-icon-button"
                    data-testid="task-graph-snapshot"
                    onClick={onCreateSnapshot}
                    disabled={!graph || isSnapshotPending}
                    title={
                      isSnapshotPending
                        ? copy.creatingSnapshot
                        : copy.snapshotGraph
                    }
                    aria-label={
                      isSnapshotPending
                        ? copy.creatingSnapshot
                        : copy.snapshotGraph
                    }
                  >
                    <SquareStack size={14} aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    className="task-graph-inline-action task-graph-canvas-icon-button"
                    data-testid="task-graph-compare-snapshot"
                    onClick={onCompareSnapshot}
                    disabled={!selectedSnapshot || isSnapshotDiffPending}
                    title={
                      isSnapshotDiffPending
                        ? copy.comparingSnapshot
                        : copy.currentGraphDiff
                    }
                    aria-label={
                      isSnapshotDiffPending
                        ? copy.comparingSnapshot
                        : copy.currentGraphDiff
                    }
                  >
                    <GitCompareArrows size={14} aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    className="task-graph-inline-action task-graph-canvas-icon-button"
                    data-testid="task-graph-rollback-snapshot"
                    onClick={onRollbackSnapshot}
                    disabled={!selectedSnapshot || isSnapshotRollbackPending}
                    title={
                      isSnapshotRollbackPending
                        ? copy.rollingBackSnapshot
                        : copy.rollbackSnapshot
                    }
                    aria-label={
                      isSnapshotRollbackPending
                        ? copy.rollingBackSnapshot
                        : copy.rollbackSnapshot
                    }
                  >
                    <Undo2 size={14} aria-hidden="true" />
                  </button>
                </div>
              </div>
              {snapshotRefs.length ? (
                <div
                  className="task-graph-snapshot-strip"
                  data-testid="task-graph-snapshot-strip"
                >
                  <span className="task-graph-snapshot-label">
                    {copy.recentSnapshots}
                  </span>
                  <small
                    className="task-graph-snapshot-preview-meta"
                    data-testid="task-graph-snapshot-preview-meta"
                    title={snapshotsPreviewSummary}
                  >
                    {snapshotsPreviewSummary}
                  </small>
                  <div
                    className={`task-graph-snapshot-list${snapshotsExpanded ? " is-expanded" : ""}`}
                    role="list"
                    aria-label={copy.recentSnapshots}
                  >
                    {visibleSnapshotRefs.map((snapshot) => {
                      const active =
                        snapshot.snapshot_id === selectedSnapshot?.snapshot_id;
                      const snapshotLabel =
                        snapshot.label ?? snapshot.snapshot_id;
                      const snapshotVersion =
                        typeof snapshot.state_version === "number" &&
                        Number.isFinite(snapshot.state_version)
                          ? snapshot.state_version
                          : null;
                      return (
                        <button
                          key={snapshot.snapshot_id}
                          type="button"
                          role="listitem"
                          className={`task-graph-snapshot-chip${active ? " is-active" : ""}`}
                          data-testid={
                            active ? "task-graph-snapshot-selected" : undefined
                          }
                          onClick={() => onSelectSnapshot(snapshot.snapshot_id)}
                          title={`${snapshotLabel}${snapshotVersion == null ? "" : ` - v${snapshotVersion}`}`}
                          aria-pressed={active}
                        >
                          <span>{snapshotLabel}</span>
                          {snapshotVersion == null ? null : (
                            <span>v{snapshotVersion}</span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                  {hiddenSnapshotCount > 0 ? (
                    <button
                      type="button"
                      className="task-graph-disclosure-button task-graph-snapshot-toggle"
                      data-testid="task-graph-snapshot-toggle"
                      onClick={() =>
                        setSnapshotsExpanded((expanded) => !expanded)
                      }
                      aria-expanded={snapshotsExpanded}
                      aria-label={snapshotsToggleLabel}
                      title={snapshotsToggleLabel}
                    >
                      {snapshotsExpanded ? (
                        <ChevronDown size={12} aria-hidden="true" />
                      ) : (
                        <ChevronRight size={12} aria-hidden="true" />
                      )}
                      <span>
                        {snapshotsToggleText}
                      </span>
                    </button>
                  ) : null}
                  {snapshotDiffMarkdown ? (
                    <span
                      className="task-graph-inline-status"
                      data-testid="task-graph-snapshot-diff-status"
                    >
                      {copy.snapshotDiff}: {snapshotDiffLineCount} {copy.lines}
                    </span>
                  ) : null}
                </div>
              ) : null}
              {snapshotDiffMarkdown ? (
                <details className="task-graph-snapshot-diff-panel">
                  <summary>{copy.snapshotDiff}</summary>
                  <pre
                    className="task-graph-snapshot-diff-markdown"
                    data-testid="task-graph-snapshot-diff-markdown"
                  >
                    {snapshotDiffMarkdown}
                  </pre>
                </details>
              ) : null}
            </div>
          </div>
          <div
            className="task-graph-canvas"
            data-testid="task-graph-canvas"
            data-canvas-scale={canvasScale.toFixed(2)}
            ref={canvasRef}
            onDragOver={(event) => {
              if (
                event.dataTransfer.types.includes(
                  "application/x-astrabridge-task-graph-node-kind",
                )
              ) {
                event.preventDefault();
                event.dataTransfer.dropEffect = "copy";
              }
            }}
          >
            {isLoadingGraph && !graph ? (
              <p className="task-graph-muted">{copy.loadingGraph}</p>
            ) : null}
            <div
              className="task-graph-canvas-toolbar task-graph-canvas-toolbar-floating"
              role="toolbar"
              aria-label={copy.canvas}
            >
              <button
                type="button"
                className="task-graph-inline-action task-graph-canvas-icon-button"
                data-testid="task-graph-fit-view"
                title={copy.fitViewTitle}
                aria-label={copy.fitView}
                onClick={handleFitView}
                disabled={!graph}
              >
                <Compass size={14} />
              </button>
              <button
                type="button"
                className="task-graph-inline-action task-graph-canvas-icon-button"
                data-testid="task-graph-reset-view"
                title={copy.resetViewTitle}
                aria-label={copy.resetView}
                onClick={handleResetView}
                disabled={!graph}
              >
                <RotateCcw size={14} />
              </button>
              <button
                type="button"
                className="task-graph-inline-action task-graph-canvas-icon-button"
                data-testid="task-graph-zoom-out"
                title={copy.zoomOutTitle}
                aria-label={copy.zoomOutTitle}
                onClick={handleZoomOut}
                disabled={!graph}
              >
                <ZoomOut size={14} />
              </button>
              <button
                type="button"
                className="task-graph-inline-action task-graph-canvas-icon-button"
                data-testid="task-graph-zoom-in"
                title={copy.zoomInTitle}
                aria-label={copy.zoomInTitle}
                onClick={handleZoomIn}
                disabled={!graph}
              >
                <ZoomIn size={14} />
              </button>
            </div>
            {!isLoadingGraph && !graph ? (
              <div
                className="task-graph-empty-state"
                data-testid="task-graph-empty"
              >
                <Compass size={18} aria-hidden="true" />
                <strong>{copy.noGraph}</strong>
                <p>{copy.noGraphHint}</p>
                <button
                  type="button"
                  className="ghost-button task-graph-empty-action"
                  data-testid="task-graph-empty-open-template-browser"
                  onClick={openTemplateBrowser}
                >
                  <Sparkles size={13} aria-hidden="true" />
                  <span>{copy.templates}</span>
                </button>
              </div>
            ) : null}
            {graph ? (
              <div
                className="task-graph-stage-frame"
                data-testid="task-graph-stage-frame"
                style={{
                  width: `${scaledStageWidth}px`,
                  height: `${scaledStageHeight}px`,
                }}
                onDrop={handleCanvasDrop}
              >
                <div
                  className="task-graph-stage"
                  data-testid="task-graph-stage"
                  data-canvas-scale={canvasScale.toFixed(2)}
                  ref={stageRef}
                  style={{
                    width: `${stageWidth}px`,
                    height: `${stageHeight}px`,
                    transform: `scale(${canvasScale})`,
                    transformOrigin: "top left",
                  }}
                >
                  <svg className="task-graph-edge-layer" aria-hidden="true">
                    <defs>
                      <marker
                        id="task-graph-edge-arrow"
                        markerWidth="10"
                        markerHeight="10"
                        refX="8"
                        refY="5"
                        orient="auto"
                        markerUnits="strokeWidth"
                      >
                        <path
                          d="M 0 0 L 10 5 L 0 10 z"
                          className="task-graph-edge-arrowhead"
                        />
                      </marker>
                    </defs>
                    {graph.edges.map((edge) => {
                      const fromNode = nodeMap.get(edge.from_node_id);
                      const toNode = nodeMap.get(edge.to_node_id);
                      if (!fromNode || !toNode) return null;
                      const fromPosition =
                        previewPositions[fromNode.node_id] ?? fromNode.position;
                      const toPosition =
                        previewPositions[toNode.node_id] ?? toNode.position;
                      const x1 = fromPosition.x + NODE_EDGE_ANCHOR_X;
                      const y1 = fromPosition.y + NODE_EDGE_ANCHOR_Y;
                      const x2 = toPosition.x + NODE_EDGE_ANCHOR_X;
                      const y2 = toPosition.y + NODE_EDGE_ANCHOR_Y;
                      const midX = Math.round((x1 + x2) / 2);
                      const isRunEventEdge =
                        selectedRunEventTarget?.kind === "edge" &&
                        selectedRunEventTarget.id === edge.edge_id;
                      const isActive =
                        (selectedEdge?.edge_id === edge.edge_id &&
                          !isCreatingEdge) ||
                        isRunEventEdge;
                      const isHovered = hoveredEdgeId === edge.edge_id;
                      const edgeStatus =
                        runtimeEdgeStatusMap.get(edge.edge_id) ??
                        edgeStatusMap.get(edge.edge_id)?.status ??
                        null;
                      const edgeStatusTone = edgeStatus
                        ? statusVisualTone(edgeStatus)
                        : null;
                      return (
                        <g key={edge.edge_id}>
                          <path
                            d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                            className="task-graph-edge-hit"
                            data-testid={`task-graph-edge-hit-${edge.edge_id}`}
                            onClick={() => {
                              setIsCreatingEdge(false);
                              onSelectEdge(edge.edge_id);
                              openInspectorDialog("selection");
                            }}
                            onContextMenu={(event) => {
                              event.preventDefault();
                              setIsCreatingEdge(false);
                              onDeleteEdge(edge.edge_id);
                            }}
                            onMouseEnter={() => setHoveredEdgeId(edge.edge_id)}
                            onMouseLeave={() =>
                              setHoveredEdgeId((current) =>
                                current === edge.edge_id ? null : current,
                              )
                            }
                          />
                          <path
                            data-testid={`task-graph-edge-${edge.edge_id}`}
                            d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
                            markerEnd="url(#task-graph-edge-arrow)"
                            className={`task-graph-edge ${isActive ? "task-graph-edge-active" : ""} ${isHovered ? "task-graph-edge-hover" : ""} ${edgeStatusTone ? `task-graph-edge-${edgeStatusTone}` : ""}`}
                            onContextMenu={(event) => {
                              event.preventDefault();
                              setIsCreatingEdge(false);
                              onDeleteEdge(edge.edge_id);
                            }}
                          />
                        </g>
                      );
                    })}
                  </svg>
                  {graph.edges.map((edge) => {
                    const fromNode = nodeMap.get(edge.from_node_id);
                    const toNode = nodeMap.get(edge.to_node_id);
                    if (!fromNode || !toNode) return null;
                    const fromPosition =
                      previewPositions[fromNode.node_id] ?? fromNode.position;
                    const toPosition =
                      previewPositions[toNode.node_id] ?? toNode.position;
                    const x1 = fromPosition.x + NODE_EDGE_ANCHOR_X;
                    const y1 = fromPosition.y + NODE_EDGE_ANCHOR_Y;
                    const x2 = toPosition.x + NODE_EDGE_ANCHOR_X;
                    const y2 = toPosition.y + NODE_EDGE_ANCHOR_Y;
                    const midX = Math.round((x1 + x2) / 2);
                    const midY = Math.round((y1 + y2) / 2);
                    const isRunEventEdge =
                      selectedRunEventTarget?.kind === "edge" &&
                      selectedRunEventTarget.id === edge.edge_id;
                    const isActive =
                      (selectedEdge?.edge_id === edge.edge_id &&
                        !isCreatingEdge) ||
                      isRunEventEdge;
                    const isHovered = hoveredEdgeId === edge.edge_id;
                    const edgeStatus =
                      runtimeEdgeStatusMap.get(edge.edge_id) ??
                      edgeStatusMap.get(edge.edge_id)?.status ??
                      null;
                    const edgeStatusTone = edgeStatus
                      ? statusVisualTone(edgeStatus)
                      : null;
                    const edgePorts = edgePortSummary(edge, graph);
                    const edgeHints = edgeSemanticHints(edge, graph);
                    return (
                      <button
                        type="button"
                        key={`chip:${edge.edge_id}`}
                        className={`task-graph-canvas-edge-chip task-graph-canvas-edge-chip-${sanitizeToken(edge.edge_type)} task-graph-canvas-edge-chip-tone-${edgeTypeTone(edge.edge_type)} ${isActive ? "task-graph-canvas-edge-chip-active" : ""} ${isHovered ? "task-graph-canvas-edge-chip-hover" : ""} ${isActive || isHovered ? "task-graph-canvas-edge-chip-expanded" : ""}`}
                        data-testid={`task-graph-canvas-edge-chip-${edge.edge_id}`}
                        data-edge-type={edge.edge_type}
                        style={{ left: `${midX}px`, top: `${midY}px` }}
                        title={edgeCanvasTitle(edge, nodeMap, graph)}
                        aria-label={edgeCanvasTitle(edge, nodeMap, graph)}
                        onClick={() => {
                          setIsCreatingEdge(false);
                          onSelectEdge(edge.edge_id);
                          openInspectorDialog("selection");
                        }}
                        onContextMenu={(event) => {
                          event.preventDefault();
                          setIsCreatingEdge(false);
                          onDeleteEdge(edge.edge_id);
                        }}
                      >
                        <span className="task-graph-canvas-edge-chip-main">
                          <span
                            className="task-graph-canvas-edge-chip-icon"
                            aria-hidden="true"
                          >
                            {edgeTypeIcon(edge.edge_type, 11)}
                          </span>
                          {edgeHints.length ? (
                            <span
                              className="task-graph-canvas-edge-chip-hints"
                              aria-hidden="true"
                            >
                              {edgeHints.map((hint) => (
                                <span
                                  key={`${edge.edge_id}:${hint.key}`}
                                  className={`task-graph-canvas-edge-chip-hint task-graph-canvas-edge-chip-hint-${hint.tone}`}
                                  title={hint.label}
                                >
                                  {hint.icon}
                                </span>
                              ))}
                            </span>
                          ) : null}
                          <span
                            className="task-graph-canvas-edge-chip-ports"
                            title={portSummaryTitle(edgePorts)}
                          >
                            {renderPortSummaryIcons(edgePorts)}
                          </span>
                        </span>
                        <span className="task-graph-canvas-edge-chip-label">
                          {edgeTypeLabel(edge.edge_type)}
                        </span>
                        {edgeStatus ? (
                          <span
                            className={`task-graph-edge-state-pill task-graph-edge-state-${edgeStatusTone ?? "warning"}`}
                            data-testid={`task-graph-canvas-edge-status-${edge.edge_id}`}
                            title={`${copy.edgeRuntime}: ${edgeStatus}`}
                          >
                            {compactStatusLabel(edgeStatus)}
                          </span>
                        ) : null}
                      </button>
                    );
                  })}
                  {graph.nodes.map((node) => {
                    const position =
                      previewPositions[node.node_id] ?? node.position;
                    const isDragging = dragState?.nodeId === node.node_id;
                    const nodeStatus =
                      runtimeNodeStatusMap.get(node.node_id) ??
                      nodeStatusMap.get(node.node_id)?.status ??
                      null;
                    const nodeStatusTone = nodeStatus
                      ? statusVisualTone(nodeStatus)
                      : null;
                    const visibleKind = registryUi.kindForNode(node);
                    const visibleKindMeta = taskGraphPaletteMeta(
                      registryUi,
                      visibleKind,
                    );
                    const nodeTone = nodeToneForKind(visibleKindMeta.tone);
                    const nodePorts = nodePortSummary(node, graph);
                    const isEdgeSource =
                      edgeCreateSourceId === node.node_id && isCreatingEdge;
                    const nodeEdgeCompatibility =
                      isCreatingEdge &&
                      edgeCreateSourceId &&
                      edgeCreateSourceId !== node.node_id
                        ? nodeEdgeTargetCompatibility(
                            edgeCreateSourceId,
                            node.node_id,
                            graph,
                            nodeMap,
                          )
                        : null;
                    const isRunEventNode =
                      selectedRunEventTarget?.kind === "node" &&
                      selectedRunEventTarget.id === node.node_id;
                    return (
                      <div
                        key={node.node_id}
                        className={`task-graph-node-card task-graph-node-tone-${nodeTone} ${selectedNode?.node_id === node.node_id && inspectorMode === "node" ? "task-graph-node-card-active" : ""} ${isRunEventNode ? "task-graph-node-card-trace-focus" : ""} ${isDragging ? "task-graph-node-card-dragging" : ""} ${isEdgeSource ? "task-graph-node-card-connection-source" : ""} ${nodeEdgeCompatibility?.compatible ? "task-graph-node-card-compatible-target" : ""} ${nodeEdgeCompatibility && !nodeEdgeCompatibility.compatible ? "task-graph-node-card-incompatible-target" : ""} ${nodeStatusTone ? `task-graph-node-card-${nodeStatusTone}` : ""}`}
                        data-testid={`task-graph-node-${node.node_id}`}
                        data-node-kind={visibleKind}
                        data-node-status={nodeStatus ?? "idle"}
                        data-trace-highlighted={
                          isRunEventNode ? "true" : "false"
                        }
                        role="button"
                        tabIndex={0}
                        style={{
                          left: `${position.x}px`,
                          top: `${position.y}px`,
                        }}
                        title={
                          nodeEdgeCompatibility
                            ? `${node.label} / ${visibleKindMeta.label} / ${nodeEdgeCompatibility.message}`
                            : `${node.label} / ${visibleKindMeta.label}`
                        }
                        aria-label={
                          nodeEdgeCompatibility
                            ? `${node.label} / ${visibleKindMeta.label} / ${nodeEdgeCompatibility.message}`
                            : `${node.label} / ${visibleKindMeta.label}`
                        }
                        onKeyDown={(event) => {
                          if (event.key !== "Enter" && event.key !== " ") return;
                          event.preventDefault();
                          if (selectEdgeTargetNode(node.node_id)) return;
                          setIsCreatingEdge(false);
                          onSelectNode(node.node_id);
                          openInspectorDialog("selection");
                        }}
                        onClick={() => {
                          if (selectEdgeTargetNode(node.node_id)) return;
                          setIsCreatingEdge(false);
                          onSelectNode(node.node_id);
                          openInspectorDialog("selection");
                        }}
                        onMouseDown={(event) =>
                          isCreatingEdge
                            ? undefined
                            : handleNodeMouseDown({
                                event,
                                node,
                                onSelectNode: (nodeId) => {
                                  setIsCreatingEdge(false);
                                  onSelectNode(nodeId);
                                },
                                setDragState,
                              })
                        }
                      >
                        <span className="task-graph-node-card-header">
                          <span className="task-graph-node-title">
                            <span
                              className={`task-graph-node-role-badge task-graph-node-role-badge-${nodeTone}`}
                              data-testid={`task-graph-node-kind-${node.node_id}`}
                              aria-label={visibleKindMeta.label}
                              title={visibleKindMeta.label}
                            >
                              {nodeKindIcon(
                                visibleKindMeta.icon || visibleKind,
                                13,
                              )}
                            </span>
                            <strong>{node.label}</strong>
                          </span>
                          {nodeStatus ? (
                            <span
                              className={`task-graph-node-state-pill task-graph-node-state-${nodeStatusTone ?? "warning"}`}
                              data-testid={`task-graph-node-status-${node.node_id}`}
                            >
                              {nodeStatus}
                            </span>
                          ) : null}
                        </span>
                        <span
                          className="task-graph-node-port-rail"
                          data-testid={`task-graph-node-ports-${node.node_id}`}
                        >
                          <button
                            type="button"
                            className={`task-graph-node-port-group task-graph-node-port-group-input ${isCreatingEdge && edgeCreateSourceId && edgeCreateSourceId !== node.node_id ? "task-graph-node-port-group-targetable" : ""}`}
                            data-testid={`task-graph-node-input-${node.node_id}`}
                            title={`${copy.inputs}: ${portSummaryTitle(nodePorts.inputs)}`}
                            aria-label={`${copy.inputs}: ${portSummaryTitle(nodePorts.inputs)}`}
                            onMouseDown={(event) => event.stopPropagation()}
                            onClick={(event) => {
                              event.stopPropagation();
                              if (selectEdgeTargetNode(node.node_id)) return;
                              setIsCreatingEdge(false);
                              onSelectNode(node.node_id);
                              openInspectorDialog("selection");
                            }}
                          >
                            <ArrowLeft
                              className="task-graph-node-port-direction"
                              size={11}
                              aria-hidden="true"
                            />
                            {renderPortSummaryIcons(nodePorts.inputs)}
                          </button>
                          <button
                            type="button"
                            className={`task-graph-node-port-group task-graph-node-port-group-output ${isEdgeSource ? "task-graph-node-port-group-active" : ""}`}
                            data-testid={`task-graph-node-output-${node.node_id}`}
                            title={`${copy.outputs}: ${portSummaryTitle(nodePorts.outputs)}`}
                            aria-label={`${copy.outputs}: ${portSummaryTitle(nodePorts.outputs)}`}
                            onMouseDown={(event) => event.stopPropagation()}
                            onClick={(event) => {
                              event.stopPropagation();
                              beginCanvasEdgeDraft(node.node_id);
                            }}
                          >
                            {renderPortSummaryIcons(nodePorts.outputs)}
                            <ArrowRight
                              className="task-graph-node-port-direction"
                              size={11}
                              aria-hidden="true"
                            />
                          </button>
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <button
          type="button"
          data-testid="task-graph-inspector-toggle"
          onClick={() => {
            if (inspectorExpanded) {
              closeInspectorDialog();
              return;
            }
            openInspectorDialog(inspectorWorkspace);
          }}
          aria-expanded={inspectorExpanded}
          aria-label={`${copy.inspector} / ${inspectorExpanded ? copy.collapsePanel : copy.expandPanel}`}
          title={`${copy.inspector} / ${inspectorExpanded ? copy.collapsePanel : copy.expandPanel}`}
          style={{ display: "none" }}
        >
          {copy.inspector}
        </button>
      </div>
      {templateBrowserOpen ? (
        <div
          className="modal-scrim task-graph-template-browser-scrim"
          onClick={closeTemplateBrowser}
        >
          <div
            className="modal-card task-graph-template-browser"
            data-testid="task-graph-template-browser"
            role="dialog"
            aria-modal="true"
            aria-label={copy.templates}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="task-graph-template-browser-header">
              <div className="task-graph-template-browser-copy">
                <div className="task-graph-panel-title">
                  <span className="task-graph-sidebar-icon" aria-hidden="true">
                    <Sparkles size={15} />
                  </span>
                  <span className="task-graph-panel-title-copy">
                    <strong>{copy.templates}</strong>
                    <span>{copy.chooseTemplate}</span>
                  </span>
                </div>
              </div>
              <button
                type="button"
                className="task-graph-inline-action task-graph-canvas-icon-button"
                data-testid="task-graph-template-browser-close"
                onClick={closeTemplateBrowser}
                title={copy.collapsePanel}
                aria-label={copy.collapsePanel}
              >
                <X size={14} aria-hidden="true" />
              </button>
            </div>
            <div className="task-graph-template-browser-body">
              <div className="task-graph-template-browser-list">
                {isLoadingTemplates ? (
                  <p className="task-graph-muted" data-testid="task-graph-template-loading">
                    {copy.loadingTemplates}
                  </p>
                ) : null}
                {!isLoadingTemplates && !templates.length ? (
                  <p className="task-graph-muted" data-testid="task-graph-template-empty">
                    {copy.noTemplates}
                  </p>
                ) : null}
                {templateSections.map((section) => (
                  <section
                    key={section.id}
                    className="task-graph-template-browser-section"
                    data-testid={`task-graph-template-section-${section.id}`}
                  >
                    <div className="task-graph-template-browser-section-head">
                      <strong>{section.label}</strong>
                      <span>{section.hint}</span>
                    </div>
                    {section.templates.length ? (
                      <div
                        className="task-graph-template-list"
                        data-testid={
                          section.id === "preset"
                            ? "task-graph-template-list"
                            : `task-graph-template-list-${section.id}`
                        }
                      >
                        {section.templates.map((template) => {
                          const isSelected =
                            selectedTemplate?.template_id === template.template_id;
                          const isCurrentGraphTemplate =
                            graph?.template_id === template.template_id;
                          return (
                            <button
                              key={template.template_id}
                              type="button"
                              className={`task-graph-template-card ${isSelected ? "task-graph-template-card-active" : ""}`}
                              data-testid={`task-graph-template-${template.template_id}`}
                              onClick={() =>
                                handleSelectTemplate(template.template_id)
                              }
                              title={summarizeTemplate(template, locale)}
                              aria-pressed={isSelected}
                            >
                              <div className="task-graph-template-card-head">
                                <strong>{template.title}</strong>
                                {isCurrentGraphTemplate ? (
                                  <span className="task-graph-template-card-badge">
                                    {copy.currentTemplate}
                                  </span>
                                ) : null}
                              </div>
                              <p>{summarizeTemplate(template, locale)}</p>
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="task-graph-muted task-graph-template-browser-empty">
                        {section.empty}
                      </p>
                    )}
                  </section>
                ))}
              </div>
              <div className="task-graph-template-browser-detail">
                {selectedTemplate ? (
                  <section
                    className="task-graph-template-summary-panel"
                    data-testid="task-graph-template-summary-panel"
                  >
                    <div className="task-graph-template-summary-head">
                      <div className="task-graph-template-quick-actions">
                        <div className="task-graph-template-quick-copy">
                          <span className="task-graph-template-summary-id">
                            {isCustomTemplate(selectedTemplate)
                              ? copy.customTemplates
                              : copy.presetTemplates}
                          </span>
                          <strong>{selectedTemplate.title}</strong>
                          <span className="task-graph-template-quick-meta">
                            {copy.templateStructure}:{" "}
                            {formatTemplateStructure(selectedTemplate, locale)}
                          </span>
                        </div>
                        <button
                          type="button"
                          className="primary-button task-graph-template-use-button"
                          data-testid="task-graph-template-instantiate"
                          onClick={handleInstantiateSelectedTemplate}
                          disabled={isInstantiating}
                        >
                          {copy.useTemplate}
                        </button>
                      </div>
                      <p className="task-graph-muted task-graph-template-summary-copy">
                        {selectedTemplateSummary || copy.blankTemplateHint}
                      </p>
                    </div>
                    <details className="task-graph-template-detail-panel" open>
                      <summary className="task-graph-template-summary-disclosure">
                        <strong>{copy.templatePreview}</strong>
                      </summary>
                      <div className="task-graph-template-summary-content">
                        <div
                          className="task-graph-template-preview-shell"
                          data-testid="task-graph-template-preview"
                        >
                          <div className="task-graph-template-preview-head">
                            <strong>{copy.templatePreview}</strong>
                          </div>
                          <div className="task-graph-template-preview-track">
                            {selectedTemplate.preview_graph.nodes.map(
                              (node, index) => {
                                const visibleKind =
                                  registryUi.kindForTemplate(node.kind);
                                const item = taskGraphPaletteMeta(
                                  registryUi,
                                  visibleKind,
                                );
                                return (
                                  <div
                                    key={`${selectedTemplate.template_id}:preview:${node.node_id}`}
                                    className="task-graph-template-preview-node"
                                  >
                                    <span
                                      className={`task-graph-palette-icon task-graph-node-role-badge-${nodeToneForKind(visibleKind)}`}
                                      aria-hidden="true"
                                    >
                                      {nodeKindIcon(item.icon || visibleKind, 12)}
                                    </span>
                                    <span>{node.label}</span>
                                    {index <
                                    selectedTemplate.preview_graph.nodes.length - 1 ? (
                                      <span
                                        className="task-graph-template-preview-arrow"
                                        aria-hidden="true"
                                      >
                                        {"->"}
                                      </span>
                                    ) : null}
                                  </div>
                                );
                              },
                            )}
                          </div>
                        </div>
                        <div className="task-graph-template-summary-grid">
                          <div>
                            <strong>{copy.recommendedProviders}</strong>
                            <p>
                              {selectedTemplate.recommended_provider_ids?.join(
                                ", ",
                              ) || "-"}
                            </p>
                          </div>
                          <div>
                            <strong>{copy.recommendedModels}</strong>
                            <p>
                              {selectedTemplate.recommended_model_ids?.join(
                                ", ",
                              ) || "-"}
                            </p>
                          </div>
                        </div>
                        <details className="task-graph-template-meta-block" open>
                          <summary>{copy.expectedArtifacts}</summary>
                          <div className="task-graph-template-meta-chips">
                            {((selectedTemplate.artifact_expectations ?? [])
                              .length
                              ? (selectedTemplate.artifact_expectations ?? [])
                              : ["-"]
                            ).map((item) => (
                              <span
                                key={`${selectedTemplate.template_id}:artifact:${item}`}
                              >
                                {item}
                              </span>
                            ))}
                          </div>
                        </details>
                        <details className="task-graph-template-meta-block">
                          <summary>{copy.templatePreflight}</summary>
                          <ul className="task-graph-template-meta-list">
                            {((selectedTemplate.validation_hints ?? []).length
                              ? (selectedTemplate.validation_hints ?? [])
                              : ["-"]
                            ).map((item) => (
                              <li
                                key={`${selectedTemplate.template_id}:hint:${item}`}
                              >
                                {item}
                              </li>
                            ))}
                          </ul>
                        </details>
                        <details className="task-graph-template-meta-block">
                          <summary>{copy.templateConstraints}</summary>
                          <ul className="task-graph-template-meta-list">
                            {((selectedTemplate.constraints ?? []).length
                              ? (selectedTemplate.constraints ?? [])
                              : ["-"]
                            ).map((item) => (
                              <li
                                key={`${selectedTemplate.template_id}:constraint:${item}`}
                              >
                                {item}
                              </li>
                            ))}
                          </ul>
                        </details>
                      </div>
                    </details>
                  </section>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      ) : null}
      {inspectorExpanded ? (
        <div
          className="modal-scrim task-graph-inspector-scrim"
          onClick={closeInspectorDialog}
        >
          <div
            className="modal-card task-graph-inspector task-graph-inspector-modal"
            data-testid="task-graph-inspector"
            role="dialog"
            aria-modal="true"
            aria-label={copy.inspector}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="task-graph-inspector-modal-header">
              <div className="task-graph-inspector-modal-copy">
                <div className="task-graph-panel-title">
                  <span className="task-graph-sidebar-icon" aria-hidden="true">
                    {inspectorWorkspace === "run" ? (
                      <Compass size={15} />
                    ) : (
                      <ScanSearch size={15} />
                    )}
                  </span>
                  <span className="task-graph-panel-title-copy">
                    <strong>{copy.inspector}</strong>
                    <span>
                      {inspectorWorkspace === "run"
                        ? copy.runWorkspace
                        : inspectorMode === "edge"
                          ? copy.edgeMode
                          : copy.nodeMode}
                    </span>
                  </span>
                </div>
              </div>
              <button
                type="button"
                className="task-graph-inline-action task-graph-canvas-icon-button"
                data-testid="task-graph-inspector-close"
                onClick={closeInspectorDialog}
                title={copy.collapsePanel}
                aria-label={copy.collapsePanel}
              >
                <X size={14} aria-hidden="true" />
              </button>
            </div>
            <div className="task-graph-inspector-shell">
                <div
                  className="task-graph-inspector-overview"
                  data-testid="task-graph-inspector-overview"
                >
                  <div
                    className="task-graph-inspector-workspace-switch"
                    role="tablist"
                    aria-label={copy.inspector}
                    data-testid="task-graph-inspector-workspace-switch"
                  >
                    <button
                      type="button"
                      role="tab"
                      aria-selected={inspectorWorkspace === "selection"}
                      className={`task-graph-mode-chip ${inspectorWorkspace === "selection" ? "task-graph-mode-chip-active" : ""}`}
                      data-testid="task-graph-inspector-workspace-selection"
                      title={copy.selectionWorkspaceHint}
                      onClick={() => {
                        setSelectionInspectorRequested(true);
                        setInspectorWorkspace("selection");
                      }}
                    >
                      {copy.selectionWorkspace}
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={inspectorWorkspace === "run"}
                      className={`task-graph-mode-chip ${inspectorWorkspace === "run" ? "task-graph-mode-chip-active" : ""}`}
                      data-testid="task-graph-inspector-workspace-run"
                      title={copy.runWorkspaceHint}
                      onClick={() => {
                        setSelectionInspectorRequested(false);
                        setInspectorWorkspace("run");
                      }}
                    >
                      {copy.runWorkspace}
                    </button>
                  </div>
                </div>
                {inspectorWorkspace === "selection" ? (
                  <div className="task-graph-inspector-editor">
                  {graph ? (
                    <div className="task-graph-inspector-modebar">
                      <button
                        type="button"
                        className={`task-graph-mode-chip ${inspectorMode === "node" ? "task-graph-mode-chip-active" : ""}`}
                        data-testid="task-graph-mode-node"
                        title={copy.nodeModeTitle}
                        onClick={() => {
                          setIsCreatingEdge(false);
                          if (selectedNode) onSelectNode(selectedNode.node_id);
                        }}
                      >
                        {copy.nodeMode}
                      </button>
                      <button
                        type="button"
                        className={`task-graph-mode-chip ${inspectorMode === "edge" ? "task-graph-mode-chip-active" : ""}`}
                        data-testid="task-graph-mode-edge"
                        title={copy.edgeModeTitle}
                        onClick={() => {
                          if (!selectedEdge && !isCreatingEdge)
                            startCreateEdge();
                          else if (selectedEdge) {
                            setIsCreatingEdge(false);
                            onSelectEdge(selectedEdge.edge_id);
                          }
                        }}
                        disabled={!graph.nodes.length}
                      >
                        {copy.edgeMode}
                      </button>
                    </div>
                  ) : null}
                  {!graph ? (
                    <p className="task-graph-muted">{copy.selectNode}</p>
                  ) : null}
                  {graph &&
                  inspectorMode === "node" &&
                  selectedNode &&
                  nodeDraft ? (
                    <div className="task-graph-inspector-body task-graph-inspector-body-node">
                      <div className="task-graph-inspector-title">
                        <strong>{selectedNode.label}</strong>
                        <div className="task-graph-inspector-title-meta">
                          <span>
                            {
                              taskGraphPaletteMeta(
                                registryUi,
                                registryUi.kindForNode(selectedNode),
                              ).label
                            }
                          </span>
                          <small>{selectedNode.node_id}</small>
                        </div>
                      </div>

                      {selectedNodePorts ? (
                        <section
                          className="task-graph-port-detail-panel"
                          data-testid="task-graph-inspector-node-ports"
                        >
                          <div className="task-graph-port-detail-head">
                            <strong>{copy.typedPorts}</strong>
                          </div>
                          <div className="task-graph-port-detail-grid">
                            <div
                              className="task-graph-port-detail-column"
                              data-testid="task-graph-inspector-node-port-inputs"
                            >
                              <span className="task-graph-port-detail-label">
                                {copy.inputs}
                              </span>
                              {selectedNodePorts.inputs.map((port) => (
                                <div
                                  key={`input:${port.key}`}
                                  className="task-graph-port-detail-item"
                                  title={`${port.label}: ${portTypeLabel(port.portType)}`}
                                >
                                  <span
                                    className={`task-graph-port-badge task-graph-port-badge-${sanitizeToken(port.portType)}`}
                                    aria-hidden="true"
                                  >
                                    {portTypeIcon(port.portType, 11)}
                                  </span>
                                  <span className="task-graph-port-detail-copy">
                                    <strong>{port.label}</strong>
                                    <small>
                                      {copy.portType}:{" "}
                                      {portTypeLabel(port.portType)}
                                    </small>
                                  </span>
                                </div>
                              ))}
                            </div>
                            <div
                              className="task-graph-port-detail-column"
                              data-testid="task-graph-inspector-node-port-outputs"
                            >
                              <span className="task-graph-port-detail-label">
                                {copy.outputs}
                              </span>
                              {selectedNodePorts.outputs.map((port) => (
                                <div
                                  key={`output:${port.key}`}
                                  className="task-graph-port-detail-item"
                                  title={`${port.label}: ${portTypeLabel(port.portType)}`}
                                >
                                  <span
                                    className={`task-graph-port-badge task-graph-port-badge-${sanitizeToken(port.portType)}`}
                                    aria-hidden="true"
                                  >
                                    {portTypeIcon(port.portType, 11)}
                                  </span>
                                  <span className="task-graph-port-detail-copy">
                                    <strong>{port.label}</strong>
                                    <small>
                                      {copy.portType}:{" "}
                                      {portTypeLabel(port.portType)}
                                    </small>
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </section>
                      ) : null}

                      {selectedNodeTypeSpec && selectedNodeTypeConfigSchema ? (
                        <details
                          className="task-graph-advanced-panel"
                          data-testid="task-graph-inspector-node-type-config"
                        >
                          <summary className="task-graph-advanced-summary">
                            <strong>{selectedNodeTypeSpec.title}</strong>
                          </summary>
                          <div className="task-graph-advanced-body">
                            {selectedNodeTypeSpec.description ? (
                              <p className="task-graph-muted">
                                {selectedNodeTypeSpec.description}
                              </p>
                            ) : null}
                            <TaskGraphSchemaForm
                              schema={selectedNodeTypeConfigSchema}
                              value={nodeDraft.node_type_config}
                              onChange={(nextValue) =>
                                setNodeDraft((current) =>
                                  current
                                    ? {
                                        ...current,
                                        node_type_config: nextValue,
                                      }
                                    : current,
                                )
                              }
                              onValidityChange={setNodeTypeConfigValid}
                              testIdPrefix="task-graph-inspector-node-type-config-field"
                            />
                            {!nodeTypeConfigValid ? (
                              <small
                                className="task-graph-danger"
                                data-testid="task-graph-inspector-node-type-config-error"
                              >
                                Node type config contains invalid values.
                              </small>
                            ) : null}
                          </div>
                        </details>
                      ) : null}

                      <label className="task-graph-field">
                        <span>{copy.roleLabel}</span>
                        <input
                          data-testid="task-graph-inspector-label"
                          value={nodeDraft.label}
                          onChange={(event) =>
                            setNodeDraft((current) =>
                              current
                                ? { ...current, label: event.target.value }
                                : current,
                            )
                          }
                        />
                      </label>

                      <label className="task-graph-field">
                        <span>{copy.provider}</span>
                        <select
                          data-testid="task-graph-inspector-provider"
                          value={nodeDraft.provider_id}
                          onChange={(event) =>
                            setNodeDraft((current) =>
                              current
                                ? {
                                    ...current,
                                    provider_id: event.target.value,
                                  }
                                : current,
                            )
                          }
                        >
                          <option value="">{copy.unspecified}</option>
                          {providerChoices.map((providerId) => (
                            <option key={providerId} value={providerId}>
                              {providerId}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label className="task-graph-field">
                        <span>{copy.model}</span>
                        <input
                          data-testid="task-graph-inspector-model"
                          list="task-graph-model-suggestions"
                          value={nodeDraft.model_id}
                          onChange={(event) =>
                            setNodeDraft((current) =>
                              current
                                ? { ...current, model_id: event.target.value }
                                : current,
                            )
                          }
                        />
                      </label>
                      <datalist id="task-graph-model-suggestions">
                        {modelSuggestions.map((modelId) => (
                          <option key={modelId} value={modelId} />
                        ))}
                      </datalist>

                      <div className="task-graph-field-grid">
                        <label className="task-graph-field">
                          <span>{copy.reasoning}</span>
                          <select
                            data-testid="task-graph-inspector-reasoning"
                            value={nodeDraft.reasoning_effort}
                            onChange={(event) =>
                              setNodeDraft((current) =>
                                current
                                  ? {
                                      ...current,
                                      reasoning_effort: event.target.value,
                                    }
                                  : current,
                              )
                            }
                          >
                            {REASONING_OPTIONS.map((option) => (
                              <option key={option} value={option}>
                                {option}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="task-graph-field">
                          <span>{copy.permission}</span>
                          <select
                            data-testid="task-graph-inspector-permission"
                            value={nodeDraft.permission_mode}
                            onChange={(event) =>
                              setNodeDraft((current) =>
                                current
                                  ? {
                                      ...current,
                                      permission_mode: event.target.value,
                                    }
                                  : current,
                              )
                            }
                          >
                            {PERMISSION_OPTIONS.map((option) => (
                              <option key={option} value={option}>
                                {option}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>

                      <div className="task-graph-field-grid">
                        <label className="task-graph-field">
                          <span>{copy.collaboration}</span>
                          <select
                            data-testid="task-graph-inspector-collaboration"
                            value={nodeDraft.collaboration_mode}
                            onChange={(event) =>
                              setNodeDraft((current) =>
                                current
                                  ? {
                                      ...current,
                                      collaboration_mode: event.target.value,
                                    }
                                  : current,
                              )
                            }
                          >
                            {COLLABORATION_OPTIONS.map((option) => (
                              <option key={option} value={option}>
                                {option}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="task-graph-field">
                          <span>{copy.backend}</span>
                          <select
                            data-testid="task-graph-inspector-backend"
                            value={nodeDraft.execution_backend}
                            onChange={(event) =>
                              setNodeDraft((current) =>
                                current
                                  ? {
                                      ...current,
                                      execution_backend: event.target.value,
                                    }
                                  : current,
                              )
                            }
                          >
                            {BACKEND_OPTIONS.map((option) => (
                              <option key={option} value={option}>
                                {option}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>

                      <label className="task-graph-field">
                        <span>{copy.contextPolicy}</span>
                        <select
                          data-testid="task-graph-inspector-context-policy"
                          value={nodeDraft.context_policy_preset}
                          onChange={(event) =>
                            setNodeDraft((current) =>
                              current
                                ? {
                                    ...current,
                                    context_policy_preset: event.target.value,
                                  }
                                : current,
                            )
                          }
                        >
                          {CONTEXT_POLICY_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label className="task-graph-field">
                        <span>{copy.memoryPolicy}</span>
                        <select
                          data-testid="task-graph-inspector-memory-policy"
                          value={nodeDraft.memory_policy_preset}
                          onChange={(event) =>
                            setNodeDraft((current) =>
                              current
                                ? {
                                    ...current,
                                    memory_policy_preset: event.target.value,
                                  }
                                : current,
                            )
                          }
                        >
                          {MEMORY_POLICY_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>

                      <details
                        className="task-graph-advanced-panel"
                        data-testid="task-graph-inspector-prompt-output"
                      >
                        <summary
                          className="task-graph-advanced-summary"
                          title={copy.advancedNodeTitle}
                        >
                          <strong>{copy.promptAndOutput}</strong>
                        </summary>
                        <div className="task-graph-advanced-body">
                          <label className="task-graph-field">
                            <span>{copy.promptTemplate}</span>
                            <textarea
                              ref={promptTemplateRef}
                              data-testid="task-graph-inspector-prompt-template"
                              value={nodeDraft.human_summary_template}
                              onChange={(event) =>
                                setNodeDraft((current) =>
                                  current
                                    ? {
                                        ...current,
                                        human_summary_template:
                                          event.target.value,
                                      }
                                    : current,
                                )
                              }
                            />
                          </label>

                          <div className="task-graph-variable-panel">
                            <span className="task-graph-variable-label">
                              {copy.promptVariables}
                            </span>
                            <div className="task-graph-variable-chip-row">
                              {promptVariableEntries.map((entry) => (
                                <button
                                  key={entry.token}
                                  type="button"
                                  className="task-graph-variable-chip"
                                  data-testid={`task-graph-prompt-variable-${sanitizeToken(entry.token)}`}
                                  title={`${copy.insertVariable}: ${entry.preview}`}
                                  onClick={() =>
                                    insertPromptVariable(entry.token)
                                  }
                                >
                                  {entry.token}
                                </button>
                              ))}
                            </div>
                          </div>

                          <div
                            className="task-graph-preview-panel"
                            data-testid="task-graph-inspector-prompt-preview"
                          >
                            <span className="task-graph-variable-label">
                              {copy.promptPreview}
                            </span>
                            <pre>
                              {buildPromptPreview(
                                selectedNode,
                                nodeDraft,
                                graph,
                              ) || copy.noPromptPreview}
                            </pre>
                          </div>

                          <div
                            className="task-graph-preview-panel"
                            data-testid="task-graph-inspector-payload-preview"
                          >
                            <span className="task-graph-variable-label">
                              {copy.payloadPreview}
                            </span>
                            <pre>
                              {buildNodePayloadPreview(
                                selectedNode,
                                nodeDraft,
                                graph,
                              ) || copy.noPayloadPreview}
                            </pre>
                          </div>

                          <label className="task-graph-field">
                            <span>{copy.outputSchema}</span>
                            <textarea
                              data-testid="task-graph-inspector-output-schema"
                              value={nodeDraft.machine_result_schema_text}
                              onChange={(event) =>
                                setNodeDraft((current) =>
                                  current
                                    ? {
                                        ...current,
                                        machine_result_schema_text:
                                          event.target.value,
                                      }
                                    : current,
                                )
                              }
                            />
                          </label>

                          <label className="task-graph-field">
                            <span>{copy.artifactOutputs}</span>
                            <input
                              data-testid="task-graph-inspector-artifact-outputs"
                              value={nodeDraft.artifact_outputs_text}
                              onChange={(event) =>
                                setNodeDraft((current) =>
                                  current
                                    ? {
                                        ...current,
                                        artifact_outputs_text:
                                          event.target.value,
                                      }
                                    : current,
                                )
                              }
                            />
                          </label>

                          <div className="task-graph-checkbox-grid">
                            <label className="task-graph-checkbox">
                              <input
                                type="checkbox"
                                data-testid="task-graph-inspector-artifact-only"
                                checked={nodeDraft.artifact_only}
                                onChange={(event) =>
                                  setNodeDraft((current) =>
                                    current
                                      ? {
                                          ...current,
                                          artifact_only: event.target.checked,
                                        }
                                      : current,
                                  )
                                }
                              />
                              <span>{copy.artifactOnly}</span>
                            </label>
                            <label className="task-graph-checkbox">
                              <input
                                type="checkbox"
                                data-testid="task-graph-inspector-human-summary-required"
                                checked={nodeDraft.human_summary_required}
                                onChange={(event) =>
                                  setNodeDraft((current) =>
                                    current
                                      ? {
                                          ...current,
                                          human_summary_required:
                                            event.target.checked,
                                        }
                                      : current,
                                  )
                                }
                              />
                              <span>{copy.humanSummaryRequired}</span>
                            </label>
                          </div>
                        </div>
                      </details>

                      <details
                        className="task-graph-advanced-panel"
                        data-testid="task-graph-inspector-tools-approval"
                      >
                        <summary
                          className="task-graph-advanced-summary"
                          title={copy.advancedNodeTitle}
                        >
                          <strong>{copy.toolsAndApproval}</strong>
                        </summary>
                        <div className="task-graph-advanced-body">
                          <div className="task-graph-checkbox-grid">
                            <label className="task-graph-checkbox">
                              <input
                                type="checkbox"
                                data-testid="task-graph-inspector-allow-provider-calls"
                                checked={nodeDraft.allow_provider_calls}
                                onChange={(event) =>
                                  setNodeDraft((current) =>
                                    current
                                      ? {
                                          ...current,
                                          allow_provider_calls:
                                            event.target.checked,
                                        }
                                      : current,
                                  )
                                }
                              />
                              <span>{copy.allowProviderCalls}</span>
                            </label>
                            <label className="task-graph-checkbox">
                              <input
                                type="checkbox"
                                data-testid="task-graph-inspector-allow-code-changes"
                                checked={nodeDraft.allow_code_changes}
                                onChange={(event) =>
                                  setNodeDraft((current) =>
                                    current
                                      ? {
                                          ...current,
                                          allow_code_changes:
                                            event.target.checked,
                                        }
                                      : current,
                                  )
                                }
                              />
                              <span>{copy.allowCodeChanges}</span>
                            </label>
                            <label className="task-graph-checkbox">
                              <input
                                type="checkbox"
                                data-testid="task-graph-inspector-allow-install"
                                checked={nodeDraft.allow_install}
                                onChange={(event) =>
                                  setNodeDraft((current) =>
                                    current
                                      ? {
                                          ...current,
                                          allow_install: event.target.checked,
                                        }
                                      : current,
                                  )
                                }
                              />
                              <span>{copy.allowInstall}</span>
                            </label>
                            <label className="task-graph-checkbox">
                              <input
                                type="checkbox"
                                data-testid="task-graph-inspector-requires-approval"
                                checked={nodeDraft.requires_human_approval}
                                onChange={(event) =>
                                  setNodeDraft((current) =>
                                    current
                                      ? {
                                          ...current,
                                          requires_human_approval:
                                            event.target.checked,
                                          approval_review_kind:
                                            event.target.checked &&
                                            !current.approval_review_kind
                                              ? defaultApprovalKindForDraft(
                                                  current,
                                                )
                                              : current.approval_review_kind,
                                        }
                                      : current,
                                  )
                                }
                              />
                              <span>{copy.requiresApproval}</span>
                            </label>
                          </div>

                          <label className="task-graph-field">
                            <span>{copy.approvalKind}</span>
                            <select
                              data-testid="task-graph-inspector-approval-kind"
                              value={nodeDraft.approval_review_kind}
                              onChange={(event) =>
                                setNodeDraft((current) =>
                                  current
                                    ? {
                                        ...current,
                                        approval_review_kind:
                                          event.target.value,
                                      }
                                    : current,
                                )
                              }
                            >
                              <option value="">
                                {copy.defaultApprovalKind}
                              </option>
                              {APPROVAL_KIND_OPTIONS.map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          </label>
                        </div>
                      </details>

                      {selectedNodeRunPanel}
                      {effectiveNodeDraftError ? (
                        <p
                          className="task-graph-validation"
                          data-testid="task-graph-inspector-validation"
                        >
                          {effectiveNodeDraftError}
                        </p>
                      ) : null}
                      {!effectiveNodeDraftError && nodeDraftWarning ? (
                        <p
                          className="task-graph-validation"
                          data-testid="task-graph-inspector-warning"
                        >
                          {nodeDraftWarning}
                        </p>
                      ) : null}
                      {!effectiveNodeDraftError && nodeSaveError ? (
                        <p
                          className="task-graph-validation"
                          data-testid="task-graph-inspector-save-error"
                        >
                          {nodeSaveError}
                        </p>
                      ) : null}

                      <div className="task-graph-inspector-actions">
                        <button
                          type="button"
                          className="ghost-button"
                          data-testid="task-graph-inspector-reset"
                          onClick={() => {
                            setNodeDraft(
                              nodeDraftBaseline ?? buildNodeDraft(selectedNode),
                            );
                            setNodeTypeConfigValid(true);
                          }}
                          disabled={!nodeDraftDirty || isSavingNode}
                        >
                          {copy.reset}
                        </button>
                        <button
                          type="button"
                          className="primary-button"
                          data-testid="task-graph-inspector-save"
                          onClick={saveNode}
                          disabled={
                            !nodeDraftDirty ||
                            Boolean(effectiveNodeDraftError) ||
                            isSavingNode
                          }
                          title={copy.nodeModeTitle}
                        >
                          <span
                            className="task-graph-save-icon"
                            aria-hidden="true"
                          >
                            <Save size={14} />
                          </span>
                          {isSavingNode ? copy.saving : copy.saveNode}
                        </button>
                      </div>
                    </div>
                  ) : null}

                  {graph && inspectorMode === "edge" && edgeDraft ? (
                    <div className="task-graph-inspector-body task-graph-inspector-body-edge">
                      <div className="task-graph-inspector-title">
                        <strong>
                          {isCreatingEdge
                            ? "draft edge"
                            : (selectedEdge?.edge_type ?? "edge")}
                        </strong>
                        <div className="task-graph-inspector-title-meta">
                          <span>
                            {edgeDraft.from_node_id && edgeDraft.to_node_id
                              ? `${labelForNodeId(nodeMap, edgeDraft.from_node_id)} -> ${labelForNodeId(nodeMap, edgeDraft.to_node_id)}`
                              : isCreatingEdge
                                ? "draft"
                                : (selectedEdge?.edge_type ?? "edge")}
                          </span>
                          <small>
                            {isCreatingEdge
                              ? "new_edge"
                              : (selectedEdge?.edge_id ?? "edge")}
                          </small>
                        </div>
                      </div>

                      <div className="task-graph-field-grid">
                        <label className="task-graph-field">
                          <span>{copy.from}</span>
                          <select
                            data-testid="task-graph-edge-from"
                            value={edgeDraft.from_node_id}
                            onChange={(event) =>
                              setEdgeDraft((current) =>
                                current
                                  ? {
                                      ...current,
                                      from_node_id: event.target.value,
                                    }
                                  : current,
                              )
                            }
                          >
                            <option value="">{copy.selectSource}</option>
                            {graph.nodes.map((node) => (
                              <option key={node.node_id} value={node.node_id}>
                                {node.label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="task-graph-field">
                          <span>{copy.to}</span>
                          <select
                            data-testid="task-graph-edge-to"
                            value={edgeDraft.to_node_id}
                            onChange={(event) =>
                              setEdgeDraft((current) =>
                                current
                                  ? {
                                      ...current,
                                      to_node_id: event.target.value,
                                    }
                                  : current,
                              )
                            }
                          >
                            <option value="">{copy.selectTarget}</option>
                            {graph.nodes.map((node) => (
                              <option key={node.node_id} value={node.node_id}>
                                {node.label}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>

                      <label className="task-graph-field">
                        <span>{copy.edgeType}</span>
                        <select
                          data-testid="task-graph-edge-type"
                          value={edgeDraft.edge_type}
                          onChange={(event) =>
                            setEdgeDraft((current) =>
                              current
                                ? { ...current, edge_type: event.target.value }
                                : current,
                            )
                          }
                        >
                          {EDGE_TYPE_OPTIONS.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                            ))}
                          </select>
                          <div
                            className="task-graph-edge-type-chip-row"
                            role="group"
                            aria-label={copy.edgeType}
                          >
                            {EDGE_TYPE_OPTIONS.map((option) => {
                              const active = edgeDraft.edge_type === option;
                              return (
                                <button
                                  key={option}
                                  type="button"
                                  className={`task-graph-mode-chip task-graph-edge-type-chip ${active ? "task-graph-mode-chip-active" : ""}`}
                                  data-testid={`task-graph-edge-type-chip-${option}`}
                                  aria-pressed={active}
                                  title={option}
                                  onClick={() =>
                                    setEdgeDraft((current) =>
                                      current
                                        ? {
                                            ...current,
                                            edge_type: option,
                                          }
                                        : current,
                                    )
                                  }
                                >
                                  <span
                                    className={`task-graph-port-badge task-graph-port-badge-${sanitizeToken(edgeTypeTone(option))}`}
                                    aria-hidden="true"
                                  >
                                    {edgeTypeIcon(option, 10)}
                                  </span>
                                  <span>{edgeTypeLabel(option)}</span>
                                </button>
                              );
                            })}
                          </div>
                      </label>

                      {edgePortCompatibility ? (
                        <section
                          className="task-graph-port-detail-panel"
                          data-testid="task-graph-edge-compatibility"
                        >
                          <div className="task-graph-port-detail-head">
                            <strong>{copy.edgeCompatibility}</strong>
                            <span
                              className={`task-graph-port-compatibility-status ${edgePortCompatibility.compatible ? "task-graph-port-compatibility-status-pass" : edgePortCompatibility.blocking ? "task-graph-port-compatibility-status-blocked" : "task-graph-port-compatibility-status-warning"}`}
                              data-testid="task-graph-edge-compatibility-status"
                            >
                              {edgePortCompatibility.compatible
                                ? copy.compatibleConnection
                                : edgePortCompatibility.blocking
                                  ? copy.incompatibleConnection
                                  : copy.controlOnlyConnection}
                            </span>
                          </div>
                          <div className="task-graph-port-detail-grid">
                            <div
                              className="task-graph-port-detail-column"
                              data-testid="task-graph-edge-compatibility-source"
                            >
                              <span className="task-graph-port-detail-label">
                                {copy.sourceOutputs}
                              </span>
                              {edgePortCompatibility.sourcePorts.map((port) => (
                                <div
                                  key={`source:${port.key}`}
                                  className="task-graph-port-detail-item"
                                >
                                  <span
                                    className={`task-graph-port-badge task-graph-port-badge-${sanitizeToken(port.portType)}`}
                                    aria-hidden="true"
                                  >
                                    {portTypeIcon(port.portType, 11)}
                                  </span>
                                  <span className="task-graph-port-detail-copy">
                                    <strong>{port.label}</strong>
                                    <small>
                                      {copy.portType}:{" "}
                                      {portTypeLabel(port.portType)}
                                    </small>
                                  </span>
                                </div>
                              ))}
                            </div>
                            <div
                              className="task-graph-port-detail-column"
                              data-testid="task-graph-edge-compatibility-target"
                            >
                              <span className="task-graph-port-detail-label">
                                {copy.targetInputs}
                              </span>
                              {edgePortCompatibility.targetPorts.map((port) => (
                                <div
                                  key={`target:${port.key}`}
                                  className="task-graph-port-detail-item"
                                >
                                  <span
                                    className={`task-graph-port-badge task-graph-port-badge-${sanitizeToken(port.portType)}`}
                                    aria-hidden="true"
                                  >
                                    {portTypeIcon(port.portType, 11)}
                                  </span>
                                  <span className="task-graph-port-detail-copy">
                                    <strong>{port.label}</strong>
                                    <small>
                                      {copy.portType}:{" "}
                                      {portTypeLabel(port.portType)}
                                    </small>
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                          {edgePortCompatibility.matches.length ? (
                            <div
                              className="task-graph-port-match-row"
                              data-testid="task-graph-edge-compatibility-matches"
                            >
                              <span className="task-graph-port-detail-label">
                                {copy.compatiblePorts}
                              </span>
                              <div className="task-graph-port-match-list">
                                {edgePortCompatibility.matches.map((match) => (
                                  <span
                                    key={`${match.source.key}:${match.target.key}`}
                                    className="task-graph-port-match-chip"
                                  >
                                    <span
                                      className={`task-graph-port-badge task-graph-port-badge-${sanitizeToken(match.source.portType)}`}
                                      aria-hidden="true"
                                    >
                                      {portTypeIcon(match.source.portType, 10)}
                                    </span>
                                    {match.source.label} {"->"} {match.target.label}
                                  </span>
                                ))}
                              </div>
                            </div>
                          ) : null}
                        </section>
                      ) : null}

                      <details
                        className="task-graph-advanced-panel"
                        data-testid="task-graph-edge-handoff-contract"
                      >
                        <summary
                          className="task-graph-advanced-summary"
                          title={copy.advancedEdgeTitle}
                        >
                          <strong>{copy.handoffContract}</strong>
                        </summary>
                        <div className="task-graph-advanced-body">
                          <label className="task-graph-field">
                            <span>{copy.handoffMessageTemplate}</span>
                            <textarea
                              ref={edgeMessageTemplateRef}
                              data-testid="task-graph-edge-message-template"
                              value={edgeDraft.handoff_message_template}
                              onChange={(event) =>
                                setEdgeDraft((current) =>
                                  current
                                    ? {
                                        ...current,
                                        handoff_message_template:
                                          event.target.value,
                                      }
                                    : current,
                                )
                              }
                              rows={3}
                            />
                          </label>

                          <div className="task-graph-variable-panel">
                            <span className="task-graph-variable-label">
                              {copy.promptVariables}
                            </span>
                            <div className="task-graph-variable-chip-row">
                              {edgeVariableEntries.map((entry) => (
                                <button
                                  key={entry.token}
                                  type="button"
                                  className="task-graph-variable-chip"
                                  data-testid={`task-graph-edge-variable-${sanitizeToken(entry.token)}`}
                                  title={`${copy.insertVariable}: ${entry.preview}`}
                                  onClick={() =>
                                    insertEdgeMessageVariable(entry.token)
                                  }
                                >
                                  {entry.token}
                                </button>
                              ))}
                            </div>
                          </div>

                          <label className="task-graph-field">
                            <span>{copy.requiredSchemaRefs}</span>
                            <input
                              data-testid="task-graph-edge-required-schema-refs"
                              value={edgeDraft.required_output_schema_refs_text}
                              onChange={(event) =>
                                setEdgeDraft((current) =>
                                  current
                                    ? {
                                        ...current,
                                        required_output_schema_refs_text:
                                          event.target.value,
                                      }
                                    : current,
                                )
                              }
                            />
                          </label>

                          <div
                            className="task-graph-preview-panel"
                            data-testid="task-graph-edge-produced-output-schema"
                          >
                            <span className="task-graph-variable-label">
                              {copy.producedOutputSchema}
                            </span>
                            <pre>
                              {producedOutputSchemaPreview ||
                                producedOutputSchemaRef ||
                                copy.noProducedSchema}
                            </pre>
                            <small className="task-graph-muted">
                              {copy.sourceSchemaHint}
                            </small>
                          </div>

                          <div
                            className="task-graph-preview-panel"
                            data-testid="task-graph-edge-payload-preview"
                          >
                            <span className="task-graph-variable-label">
                              {copy.payloadPreview}
                            </span>
                            <pre>
                              {buildEdgePayloadPreview({
                                draft: edgeDraft,
                                nodeMap,
                              }) || copy.noPayloadPreview}
                            </pre>
                          </div>

                          <div className="task-graph-variable-panel">
                            <span className="task-graph-variable-label">
                              {copy.messagePartModes}
                            </span>
                            <div className="task-graph-checkbox-grid">
                              <label className="task-graph-checkbox">
                                <input
                                  data-testid="task-graph-edge-part-machine-result"
                                  type="checkbox"
                                  checked={
                                    edgeDraft.include_message_machine_result
                                  }
                                  onChange={(event) =>
                                    setEdgeDraft((current) =>
                                      current
                                        ? {
                                            ...current,
                                            include_message_machine_result:
                                              event.target.checked,
                                          }
                                        : current,
                                    )
                                  }
                                />
                                <span>{copy.messagePartMachineResult}</span>
                              </label>
                              <label className="task-graph-checkbox">
                                <input
                                  data-testid="task-graph-edge-part-human-summary"
                                  type="checkbox"
                                  checked={
                                    edgeDraft.include_message_human_summary
                                  }
                                  onChange={(event) =>
                                    setEdgeDraft((current) =>
                                      current
                                        ? {
                                            ...current,
                                            include_message_human_summary:
                                              event.target.checked,
                                          }
                                        : current,
                                    )
                                  }
                                />
                                <span>{copy.messagePartHumanSummary}</span>
                              </label>
                              <label className="task-graph-checkbox">
                                <input
                                  data-testid="task-graph-edge-part-artifact-ref"
                                  type="checkbox"
                                  checked={
                                    edgeDraft.include_message_artifact_ref
                                  }
                                  onChange={(event) =>
                                    setEdgeDraft((current) =>
                                      current
                                        ? {
                                            ...current,
                                            include_message_artifact_ref:
                                              event.target.checked,
                                          }
                                        : current,
                                    )
                                  }
                                />
                                <span>{copy.messagePartArtifactRef}</span>
                              </label>
                              <label className="task-graph-checkbox">
                                <input
                                  data-testid="task-graph-edge-part-structured-json"
                                  type="checkbox"
                                  checked={
                                    edgeDraft.include_message_structured_json
                                  }
                                  onChange={(event) =>
                                    setEdgeDraft((current) =>
                                      current
                                        ? {
                                            ...current,
                                            include_message_structured_json:
                                              event.target.checked,
                                          }
                                        : current,
                                    )
                                  }
                                />
                                <span>{copy.messagePartStructuredJson}</span>
                              </label>
                              <label className="task-graph-checkbox">
                                <input
                                  data-testid="task-graph-edge-part-text"
                                  type="checkbox"
                                  checked={edgeDraft.include_message_text}
                                  onChange={(event) =>
                                    setEdgeDraft((current) =>
                                      current
                                        ? {
                                            ...current,
                                            include_message_text:
                                              event.target.checked,
                                          }
                                        : current,
                                    )
                                  }
                                />
                                <span>{copy.messagePartText}</span>
                              </label>
                            </div>
                          </div>
                        </div>
                      </details>

                      <div className="task-graph-field-grid">
                        <label className="task-graph-field">
                          <span>{copy.historyMode}</span>
                          <select
                            data-testid="task-graph-edge-history-mode"
                            value={edgeDraft.history_mode}
                            onChange={(event) =>
                              setEdgeDraft((current) =>
                                current
                                  ? {
                                      ...current,
                                      history_mode: event.target.value,
                                    }
                                  : current,
                              )
                            }
                          >
                            {EDGE_HISTORY_OPTIONS.map((option) => (
                              <option key={option} value={option}>
                                {option}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="task-graph-field">
                          <span>{copy.artifactInclusion}</span>
                          <select
                            data-testid="task-graph-edge-artifact-mode"
                            value={edgeDraft.artifact_mode}
                            onChange={(event) =>
                              setEdgeDraft((current) =>
                                current
                                  ? {
                                      ...current,
                                      artifact_mode: event.target.value,
                                    }
                                  : current,
                              )
                            }
                          >
                            {EDGE_ARTIFACT_OPTIONS.map((option) => (
                              <option key={option} value={option}>
                                {option}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>

                      <div className="task-graph-field-grid">
                        <label className="task-graph-field">
                          <span>{copy.historyLength}</span>
                          <input
                            data-testid="task-graph-edge-history-length"
                            inputMode="numeric"
                            value={edgeDraft.history_length}
                            onChange={(event) =>
                              setEdgeDraft((current) =>
                                current
                                  ? {
                                      ...current,
                                      history_length: event.target.value,
                                    }
                                  : current,
                              )
                            }
                          />
                        </label>
                        <label className="task-graph-field">
                          <span>{copy.summaryStrategy}</span>
                          <select
                            data-testid="task-graph-edge-summary-strategy"
                            value={edgeDraft.summary_strategy}
                            onChange={(event) =>
                              setEdgeDraft((current) =>
                                current
                                  ? {
                                      ...current,
                                      summary_strategy: event.target.value,
                                    }
                                  : current,
                              )
                            }
                          >
                            {EDGE_SUMMARY_OPTIONS.map((option) => (
                              <option key={option} value={option}>
                                {option}
                              </option>
                            ))}
                          </select>
                        </label>
                      </div>

                      <details className="task-graph-advanced-panel">
                        <summary
                          className="task-graph-advanced-summary"
                          title={copy.advancedEdgeTitle}
                        >
                          {copy.moreSettings}
                        </summary>
                        <div className="task-graph-advanced-body">
                          <label className="task-graph-field">
                            <span>{copy.includedArtifacts}</span>
                            <input
                              data-testid="task-graph-edge-included-artifacts"
                              value={edgeDraft.included_artifacts_text}
                              onChange={(event) =>
                                setEdgeDraft((current) =>
                                  current
                                    ? {
                                        ...current,
                                        included_artifacts_text:
                                          event.target.value,
                                      }
                                    : current,
                                )
                              }
                            />
                          </label>

                          <label className="task-graph-field">
                            <span>{copy.resourceRefs}</span>
                            <textarea
                              data-testid="task-graph-edge-resource-refs"
                              value={edgeDraft.resource_refs_text}
                              onChange={(event) =>
                                setEdgeDraft((current) =>
                                  current
                                    ? {
                                        ...current,
                                        resource_refs_text: event.target.value,
                                      }
                                    : current,
                                )
                              }
                              rows={3}
                            />
                          </label>

                          <div className="task-graph-checkbox-grid">
                            <label className="task-graph-checkbox">
                              <input
                                data-testid="task-graph-edge-exclude-private-memory"
                                type="checkbox"
                                checked={edgeDraft.exclude_private_memory}
                                onChange={(event) =>
                                  setEdgeDraft((current) =>
                                    current
                                      ? {
                                          ...current,
                                          exclude_private_memory:
                                            event.target.checked,
                                        }
                                      : current,
                                  )
                                }
                              />
                              <span>{copy.excludePrivateMemory}</span>
                            </label>
                            <label className="task-graph-checkbox">
                              <input
                                data-testid="task-graph-edge-include-machine-results"
                                type="checkbox"
                                checked={edgeDraft.include_machine_results}
                                onChange={(event) =>
                                  setEdgeDraft((current) =>
                                    current
                                      ? {
                                          ...current,
                                          include_machine_results:
                                            event.target.checked,
                                        }
                                      : current,
                                  )
                                }
                              />
                              <span>{copy.includeMachineResults}</span>
                            </label>
                            <label className="task-graph-checkbox">
                              <input
                                data-testid="task-graph-edge-include-human-summaries"
                                type="checkbox"
                                checked={edgeDraft.include_human_summaries}
                                onChange={(event) =>
                                  setEdgeDraft((current) =>
                                    current
                                      ? {
                                          ...current,
                                          include_human_summaries:
                                            event.target.checked,
                                        }
                                      : current,
                                  )
                                }
                              />
                              <span>{copy.includeHumanSummaries}</span>
                            </label>
                          </div>
                        </div>
                      </details>

                      {selectedEdgeRunPanel}
                      {edgeDraftError ? (
                        <p
                          className="task-graph-validation"
                          data-testid="task-graph-edge-validation"
                        >
                          {edgeDraftError}
                        </p>
                      ) : null}
                      {!edgeDraftError && edgeSaveError ? (
                        <p
                          className="task-graph-validation"
                          data-testid="task-graph-edge-save-error"
                        >
                          {edgeSaveError}
                        </p>
                      ) : null}

                      <div className="task-graph-inspector-actions">
                        <button
                          type="button"
                          className="ghost-button"
                          data-testid="task-graph-edge-reset"
                          onClick={() => {
                            if (isCreatingEdge && graph) {
                              const nextDraft = defaultCreateEdgeDraft(
                                graph,
                                selectedNode?.node_id ?? null,
                              );
                              setEdgeDraft(nextDraft);
                              setEdgeDraftBaseline(nextDraft);
                              return;
                            }
                            if (selectedEdge) {
                              setEdgeDraft(
                                edgeDraftBaseline ?? buildEdgeDraft(selectedEdge),
                              );
                            }
                          }}
                          disabled={!edgeDraftDirty || isSavingEdge}
                        >
                          {copy.reset}
                        </button>
                        <button
                          type="button"
                          className="primary-button"
                          data-testid="task-graph-edge-save"
                          onClick={saveEdge}
                          disabled={
                            !edgeDraftDirty ||
                            Boolean(edgeDraftError) ||
                            isSavingEdge
                          }
                          title={copy.edgeModeTitle}
                        >
                          <span
                            className="task-graph-save-icon"
                            aria-hidden="true"
                          >
                            <Save size={14} />
                          </span>
                          {isSavingEdge
                            ? copy.saving
                            : isCreatingEdge
                              ? copy.createEdgeAction
                              : copy.saveEdge}
                        </button>
                      </div>
                    </div>
                  ) : null}
                  </div>
                ) : null}
                {inspectorWorkspace === "run" ? (
                  <div className="task-graph-inspector-editor">
                    <section
                      className="task-graph-inspector-workspace"
                      data-testid="task-graph-inspector-run-workspace"
                    >
                      <div className="task-graph-inspector-section-head">
                        <strong>{copy.runWorkspace}</strong>
                        <span className="task-graph-muted">
                          {runWorkspaceSubtitle}
                        </span>
                      </div>
                      {runReadinessPanel}
                      {latestRunPanel}
                      {!runReadinessPanel && !latestRunPanel ? (
                        <p
                          className="task-graph-muted"
                          data-testid="task-graph-inspector-run-empty"
                        >
                          {copy.noRunInspection}
                        </p>
                      ) : null}
                    </section>
                  </div>
                ) : null}
              </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function buildNodeDraft(node: TaskGraphNode): NodeDraft {
  const executionPolicy = asRecord(node.execution_policy) ?? {};
  const outputContract = asRecord(node.output_contract) ?? {};
  const uiHints = asRecord(node.ui_hints) ?? {};
  const machineSchema = asRecord(outputContract.machine_result_schema) ??
    asRecord(node.machine_result_schema) ?? {
      type: "object",
      required: ["result"],
    };
  const approvalGate = asRecord(node.approval_gate) ?? {};
  return {
    label: node.label,
    provider_id: node.provider_id ?? "",
    model_id: node.model_id ?? "",
    reasoning_effort: node.reasoning_effort ?? "medium",
    permission_mode: node.permission_mode ?? "ask",
    collaboration_mode: node.collaboration_mode ?? "default",
    execution_backend: node.execution_backend ?? "app_server",
    context_policy_preset: contextPolicyPreset(node),
    memory_policy_preset:
      typeof uiHints.memory_policy_preset === "string" &&
      uiHints.memory_policy_preset
        ? uiHints.memory_policy_preset
        : "default",
    human_summary_template: String(node.human_summary_template ?? "").trim(),
    machine_result_schema_text: stringifyJson(machineSchema),
    artifact_outputs_text: stringifyList(
      Array.isArray(outputContract.artifact_outputs)
        ? outputContract.artifact_outputs
        : ["required_output"],
    ),
    artifact_only: Boolean(outputContract.artifact_only),
    human_summary_required: outputContract.human_summary_required !== false,
    allow_provider_calls: executionPolicy.allow_provider_calls !== false,
    allow_code_changes: Boolean(executionPolicy.allow_code_changes),
    allow_install: Boolean(executionPolicy.allow_install),
    requires_human_approval: Boolean(executionPolicy.requires_human_approval),
    approval_review_kind:
      typeof approvalGate.review_kind === "string"
        ? approvalGate.review_kind
        : "",
    node_type_config: asRecord(uiHints.node_type_config) ?? {},
  };
}

function buildEdgeDraft(edge: TaskGraphEdge): EdgeDraft {
  const handoffContract = asRecord(edge.handoff_contract) ?? {};
  const messagePartModes = normalizeStringList(
    handoffContract.message_part_modes,
  );
  const fallbackSchemaRef = edge.from_node_id
    ? `schema.${edge.from_node_id}.machine_result`
    : "";
  const includedArtifacts = normalizeIncludedArtifactsForMode(
    edge.context_policy.artifact_mode,
    edge.context_policy.included_artifacts,
  );
  return {
    from_node_id: edge.from_node_id,
    to_node_id: edge.to_node_id,
    edge_type: edge.edge_type,
    handoff_message_template: String(
      handoffContract.message_template ||
        defaultEdgeMessageTemplate(edge.from_node_id, edge.to_node_id),
    ),
    required_output_schema_refs_text: stringifyList(
      normalizeStringList(handoffContract.required_output_schema_refs).length
        ? normalizeStringList(handoffContract.required_output_schema_refs)
        : [fallbackSchemaRef].filter(Boolean),
    ),
    include_message_machine_result: messagePartModes.length
      ? messagePartModes.includes("machine_result")
      : true,
    include_message_human_summary: messagePartModes.length
      ? messagePartModes.includes("human_summary")
      : true,
    include_message_artifact_ref: messagePartModes.includes("artifact_ref"),
    include_message_structured_json:
      messagePartModes.includes("structured_json"),
    include_message_text: messagePartModes.includes("text"),
    history_mode: edge.context_policy.history_mode,
    artifact_mode: edge.context_policy.artifact_mode,
    history_length: String(edge.context_policy.history_length ?? 0),
    summary_strategy:
      edge.context_policy.summary_strategy ?? "human_summary_only",
    include_machine_results: edge.context_policy.include_machine_results,
    include_human_summaries: edge.context_policy.include_human_summaries,
    exclude_private_memory: edge.context_policy.exclude_private_memory,
    included_artifacts_text: stringifyList(includedArtifacts),
    resource_refs_text: stringifyList(edge.context_policy.resource_refs),
  };
}

function defaultCreateEdgeDraft(
  graph: TaskGraphDefinition,
  selectedNodeId: string | null,
): EdgeDraft {
  const sourceId =
    selectedNodeId &&
    graph.nodes.some((node) => node.node_id === selectedNodeId)
      ? selectedNodeId
      : (graph.nodes[0]?.node_id ?? "");
  const targetId =
    graph.nodes.find((node) => node.node_id !== sourceId)?.node_id ??
    graph.nodes[1]?.node_id ??
    "";
  const inferredSchemaRef = inferNodeSchemaRef(
    graph.nodes.find((node) => node.node_id === sourceId) ?? null,
  );
  return {
    from_node_id: sourceId,
    to_node_id: targetId,
    edge_type: "artifact_handoff",
    handoff_message_template: defaultEdgeMessageTemplate(sourceId, targetId),
    required_output_schema_refs_text: inferredSchemaRef,
    include_message_machine_result: true,
    include_message_human_summary: true,
    include_message_artifact_ref: false,
    include_message_structured_json: false,
    include_message_text: false,
    history_mode: "latest_summary_only",
    artifact_mode: "required_output_only",
    history_length: "1",
    summary_strategy: "human_summary_only",
    include_machine_results: true,
    include_human_summaries: true,
    exclude_private_memory: true,
    included_artifacts_text: "",
    resource_refs_text: "",
  };
}

function edgeLabel(edge: TaskGraphEdge, nodeMap: Map<string, TaskGraphNode>) {
  const fromLabel = nodeMap.get(edge.from_node_id)?.label ?? edge.from_node_id;
  const toLabel = nodeMap.get(edge.to_node_id)?.label ?? edge.to_node_id;
  return `${fromLabel} -> ${toLabel}`;
}

function defaultEdgeMessageTemplate(fromNodeId: string, toNodeId: string) {
  const fromLabel = fromNodeId || "source";
  const toLabel = toNodeId || "target";
  return `Deliver the required output from ${fromLabel} to ${toLabel}.`;
}

function inferNodeSchemaRef(node: TaskGraphNode | null) {
  if (!node) return "";
  const outputContract = asRecord(node.output_contract) ?? {};
  const schemaRef = String(
    outputContract.machine_result_schema_ref || "",
  ).trim();
  if (schemaRef) return schemaRef;
  return `schema.${node.node_id}.machine_result`;
}

function normalizeIncludedArtifactsForMode(
  artifactMode: string,
  values: unknown,
): string[] {
  const normalized = normalizeStringList(values);
  if (artifactMode === "required_output_only") {
    return normalized.filter((entry) => entry !== "required_output");
  }
  return normalized;
}

function edgeMessagePartModes(draft: EdgeDraft) {
  const next: string[] = [];
  if (draft.include_message_machine_result) next.push("machine_result");
  if (draft.include_message_human_summary) next.push("human_summary");
  if (draft.include_message_artifact_ref) next.push("artifact_ref");
  if (draft.include_message_structured_json) next.push("structured_json");
  if (draft.include_message_text) next.push("text");
  return next;
}

function normalizeStringList(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || "").trim()).filter(Boolean);
}

function edgeTypeLabel(edgeType: string) {
  switch (edgeType) {
    case "context_handoff":
      return "Context";
    case "artifact_handoff":
      return "Artifact";
    case "control_dependency":
      return "Control";
    case "approval_dependency":
      return "Approval";
    case "fanout_branch":
      return "Fan-out";
    case "fanin_merge":
      return "Fan-in";
    default:
      return edgeType || "Edge";
  }
}

function edgeTypeIcon(edgeType: string, size = 12) {
  switch (edgeType) {
    case "context_handoff":
      return <MessageSquareText size={size} />;
    case "artifact_handoff":
      return <Boxes size={size} />;
    case "control_dependency":
      return <GitBranch size={size} />;
    case "approval_dependency":
      return <ShieldCheck size={size} />;
    case "fanout_branch":
      return <GitBranch size={size} />;
    case "fanin_merge":
      return <GitCompareArrows size={size} />;
    default:
      return <SquareStack size={size} />;
  }
}

function edgeTypeTone(edgeType: string) {
  switch (edgeType) {
    case "context_handoff":
      return "context";
    case "artifact_handoff":
      return "artifact";
    case "control_dependency":
      return "control";
    case "approval_dependency":
      return "approval";
    case "fanout_branch":
      return "fanout";
    case "fanin_merge":
      return "fanin";
    default:
      return "neutral";
  }
}

function statusVisualTone(status: string) {
  const normalized = String(status || "").trim().toLowerCase();
  if (
    [
      "pass",
      "completed",
      "succeeded",
      "success",
      "approved",
      "ready",
    ].includes(normalized)
  ) {
    return "pass";
  }
  if (
    [
      "blocked",
      "failed",
      "error",
      "rejected",
      "cancelled",
      "canceled",
      "expired",
    ].includes(normalized)
  ) {
    return "blocked";
  }
  return "warning";
}

function compactStatusLabel(status: string) {
  const normalized = String(status || "").trim().toLowerCase();
  switch (normalized) {
    case "completed":
    case "succeeded":
    case "success":
      return "done";
    case "paused_for_review":
      return "hold";
    case "in_progress":
      return "live";
    case "waiting_on_dependencies":
      return "wait";
    case "cancelled":
    case "canceled":
      return "stop";
    default:
      return normalized.slice(0, 4) || "run";
  }
}

function edgeCanvasTitle(
  edge: TaskGraphEdge,
  nodeMap: Map<string, TaskGraphNode>,
  graph: TaskGraphDefinition | null,
) {
  return [
    edgeTypeLabel(edge.edge_type),
    edgeLabel(edge, nodeMap),
    portSummaryTitle(edgePortSummary(edge, graph)),
  ].join(" / ");
}

function edgeSemanticHints(edge: TaskGraphEdge, graph: TaskGraphDefinition | null) {
  const contract = asRecord(edge.handoff_contract) ?? {};
  const modes = normalizeStringList(contract.message_part_modes);
  const typedPorts = edgePortSummary(edge, graph);
  const hasMultimodalPort = typedPorts.some((item) =>
    ["image", "audio", "video", "document", "code_diff", "dataset"].includes(
      item.portType,
    ),
  );
  const hints: Array<{
    key: string;
    label: string;
    tone: string;
    icon: ReactNode;
  }> = [];
  if (
    modes.includes("machine_result") ||
    modes.includes("structured_json") ||
    typedPorts.some((item) => item.portType === "structured_json")
  ) {
    hints.push({
      key: "machine_result",
      label: "Machine result",
      tone: "structured_json",
      icon: <FileJson size={10} />,
    });
  }
  if (modes.includes("human_summary") || modes.includes("text")) {
    hints.push({
      key: "summary",
      label: "Summary",
      tone: "text",
      icon: <MessageSquareText size={10} />,
    });
  }
  if (modes.includes("artifact_ref")) {
    hints.push({
      key: "artifact_ref",
      label: "Artifact reference",
      tone: "artifact",
      icon: <Boxes size={10} />,
    });
  }
  if (hasMultimodalPort) {
    hints.push({
      key: "multimodal",
      label: "Multimodal payload",
      tone: "multimodal",
      icon: <Sparkles size={10} />,
    });
  }
  return hints.slice(0, 2);
}

type PortPreview = {
  key: string;
  label: string;
  portType: string;
};

type PortCompatibilityMatch = {
  source: PortPreview;
  target: PortPreview;
};

type EdgePortCompatibility = {
  sourceNode: TaskGraphNode | null;
  targetNode: TaskGraphNode | null;
  sourcePorts: PortPreview[];
  targetPorts: PortPreview[];
  matches: PortCompatibilityMatch[];
  compatible: boolean;
  blocking: boolean;
  message: string;
};

function nodePortSummary(node: TaskGraphNode, graph: TaskGraphDefinition | null) {
  const orchestrationNode = orchestrationNodeForTaskNode(graph, node.node_id);
  if (orchestrationNode) {
    return {
      inputs: orchestrationPortsForNode(orchestrationNode, "inputs"),
      outputs: orchestrationPortsForNode(orchestrationNode, "outputs"),
    };
  }
  return {
    inputs: fallbackInputPorts(node, graph),
    outputs: fallbackOutputPorts(node),
  };
}

function edgePortSummary(edge: TaskGraphEdge, graph: TaskGraphDefinition | null) {
  const orchestrationEdge = orchestrationEdgeForTaskEdge(graph, edge.edge_id);
  if (orchestrationEdge) {
    const bindings = normalizedPortBindings(orchestrationEdge);
    const sourceNode = orchestrationNodeForTaskNode(graph, edge.from_node_id);
    const targetNode = orchestrationNodeForTaskNode(graph, edge.to_node_id);
    const sourcePorts = sourceNode ? orchestrationPortsForNode(sourceNode, "outputs") : [];
    const targetPorts = targetNode ? orchestrationPortsForNode(targetNode, "inputs") : [];
    const bound: PortPreview[] = [];
    for (const binding of bindings) {
      const sourcePort = sourcePorts.find((item) => item.key === binding.from_port_id);
      const targetPort = targetPorts.find((item) => item.key === binding.to_port_id);
      if (sourcePort) bound.push(sourcePort);
      if (targetPort) bound.push(targetPort);
    }
    if (bound.length) return dedupePortPreviews(bound);
  }
  return dedupePortPreviews([
    ...fallbackOutputPorts(graph?.nodes.find((item) => item.node_id === edge.from_node_id) ?? null),
    ...fallbackInputPorts(graph?.nodes.find((item) => item.node_id === edge.to_node_id) ?? null, graph),
  ]);
}

function orchestrationNodeForTaskNode(
  graph: TaskGraphDefinition | null,
  nodeId: string,
) {
  const orchestrationGraph = asRecord(graph?.orchestration_graph);
  const nodes = Array.isArray(orchestrationGraph?.nodes) ? orchestrationGraph.nodes : [];
  return nodes.find((item) => asRecord(item)?.node_id === nodeId) ?? null;
}

function orchestrationEdgeForTaskEdge(
  graph: TaskGraphDefinition | null,
  edgeId: string,
) {
  const orchestrationGraph = asRecord(graph?.orchestration_graph);
  const edges = Array.isArray(orchestrationGraph?.edges) ? orchestrationGraph.edges : [];
  return edges.find((item) => asRecord(item)?.edge_id === edgeId) ?? null;
}

function orchestrationPortsForNode(
  nodeRecord: unknown,
  direction: "inputs" | "outputs",
) {
  const ports = asRecord(asRecord(nodeRecord)?.ports)?.[direction];
  if (Array.isArray(ports)) {
    return dedupePortPreviews(
      ports
        .map((item) => {
          const record = asRecord(item);
          const portType = String(record?.port_type || "").trim();
          const portId = String(record?.port_id || "").trim();
          if (!portType || !portId) return null;
          return {
            key: portId,
            label: String(record?.label || portId),
            portType,
          } satisfies PortPreview;
        })
        .filter((item): item is PortPreview => Boolean(item)),
    );
  }
  return contractPortsForNode(nodeRecord, direction);
}

function contractPortsForNode(
  nodeRecord: unknown,
  direction: "inputs" | "outputs",
) {
  const node = asRecord(nodeRecord);
  if (!node) return [];
  if (direction === "inputs") {
    const inputContract = asRecord(node.input_contract);
    const inputMode = String(inputContract?.mode || "").trim();
    if (inputMode === "task_context") {
      return [{ key: "task_context", label: "Task Context", portType: "text" }];
    }
    return [];
  }
  const outputContract = asRecord(node.output_contract);
  if (!outputContract) return [];
  const previews: PortPreview[] = [];
  if (String(outputContract.machine_result_schema_ref || "").trim()) {
    previews.push({
      key: "machine_result",
      label: "Machine Result",
      portType: "structured_json",
    });
  }
  const artifactSpecs = Array.isArray(outputContract.artifact_specs)
    ? outputContract.artifact_specs
    : [];
  for (const item of artifactSpecs) {
    const record = asRecord(item);
    const artifactId = String(record?.id || record?.kind || "").trim();
    const artifactKind = String(record?.kind || artifactId).trim();
    if (!artifactId || !artifactKind) continue;
    previews.push({
      key: artifactId,
      label: artifactId,
      portType: artifactKindToPortType(artifactKind),
    });
  }
  return dedupePortPreviews(previews);
}

function normalizedPortBindings(edgeRecord: unknown) {
  const bindings = asRecord(asRecord(edgeRecord)?.handoff_contract)?.port_bindings;
  if (!Array.isArray(bindings)) return [];
  return bindings
    .map((item) => {
      const record = asRecord(item);
      const fromPortId = String(record?.from_port_id || "").trim();
      const toPortId = String(record?.to_port_id || "").trim();
      if (!fromPortId || !toPortId) return null;
      return { from_port_id: fromPortId, to_port_id: toPortId };
    })
    .filter(
      (item): item is { from_port_id: string; to_port_id: string } =>
        Boolean(item),
    );
}

function fallbackInputPorts(
  node: TaskGraphNode | null,
  graph: TaskGraphDefinition | null,
) {
  if (!node) return [];
  const incomingEdges = (graph?.edges ?? []).filter(
    (edge) => edge.to_node_id === node.node_id,
  );
  if (!incomingEdges.length) {
    return [{ key: "task_context", label: "Task Context", portType: "text" }];
  }
  const previews: PortPreview[] = [];
  for (const edge of incomingEdges) {
    const contract = asRecord(edge.handoff_contract) ?? {};
    const modes = normalizeStringList(contract.message_part_modes);
    if (modes.includes("machine_result") || modes.includes("structured_json")) {
      previews.push({
        key: `${edge.edge_id}:machine_result`,
        label: "Machine Result",
        portType: "structured_json",
      });
    }
    if (modes.includes("human_summary") || modes.includes("text")) {
      previews.push({
        key: `${edge.edge_id}:summary`,
        label: "Summary",
        portType: "text",
      });
    }
    if (modes.includes("artifact_ref")) {
      previews.push({
        key: `${edge.edge_id}:artifact`,
        label: "Artifact",
        portType: fallbackPrimaryArtifactPortType(
          graph?.nodes.find((item) => item.node_id === edge.from_node_id) ?? null,
        ),
      });
    }
  }
  return dedupePortPreviews(
    previews.length
      ? previews
      : [{ key: "task_context", label: "Task Context", portType: "text" }],
  );
}

function fallbackOutputPorts(node: TaskGraphNode | null) {
  if (!node) return [];
  const outputContract = asRecord(node.output_contract) ?? {};
  const artifactOutputs = Array.isArray(outputContract.artifact_outputs)
    ? outputContract.artifact_outputs
    : [];
  const previews: PortPreview[] = [];
  const machineSchema =
    asRecord(outputContract.machine_result_schema) ??
    asRecord(node.machine_result_schema);
  if (machineSchema && !Boolean(outputContract.artifact_only)) {
    previews.push({
      key: "machine_result",
      label: "Machine Result",
      portType: "structured_json",
    });
  }
  for (const item of artifactOutputs) {
    const artifactKind = String(item || "").trim();
    if (!artifactKind) continue;
    previews.push({
      key: artifactKind,
      label: artifactKind,
      portType: artifactKindToPortType(artifactKind),
    });
  }
  return dedupePortPreviews(
    previews.length
      ? previews
      : [{ key: "summary", label: "Summary", portType: "text" }],
  );
}

function fallbackPrimaryArtifactPortType(node: TaskGraphNode | null) {
  return fallbackOutputPorts(node)[0]?.portType ?? "text";
}

function artifactKindToPortType(kind: string) {
  switch (String(kind || "").trim()) {
    case "image":
      return "image";
    case "audio":
      return "audio";
    case "video":
      return "video";
    case "document_extract":
      return "document";
    case "code_diff":
      return "code_diff";
    case "dataset":
      return "dataset";
    case "validation_report":
    case "run_summary":
    case "test_report":
    case "diagnostic_bundle":
      return "agent_report";
    case "approval_record":
      return "approval_record";
    case "structured_json":
      return "structured_json";
    default:
      return "text";
  }
}

function portTypeLabel(portType: string) {
  switch (String(portType || "").trim()) {
    case "text":
      return "Text";
    case "structured_json":
      return "Structured JSON";
    case "image":
      return "Image";
    case "audio":
      return "Audio";
    case "video":
      return "Video";
    case "document":
      return "Document";
    case "code_diff":
      return "Code Diff";
    case "dataset":
      return "Dataset";
    case "tool_result":
      return "Tool Result";
    case "agent_report":
      return "Agent Report";
    case "approval_record":
      return "Approval";
    default:
      return portType || "Port";
  }
}

function portTypeIcon(portType: string, size = 11) {
  switch (String(portType || "").trim()) {
    case "text":
      return <MessageSquareText size={size} />;
    case "structured_json":
      return <FileJson size={size} />;
    case "image":
      return <ImageIcon size={size} />;
    case "audio":
      return <AudioLines size={size} />;
    case "video":
      return <Video size={size} />;
    case "document":
      return <FileText size={size} />;
    case "code_diff":
      return <Braces size={size} />;
    case "dataset":
      return <Database size={size} />;
    case "tool_result":
      return <Wrench size={size} />;
    case "agent_report":
      return <ScanSearch size={size} />;
    case "approval_record":
      return <ShieldCheck size={size} />;
    default:
      return <SquareStack size={size} />;
  }
}

function portSummaryTitle(items: PortPreview[]) {
  if (!items.length) return "No typed ports";
  return items
    .map((item) => `${item.label}: ${portTypeLabel(item.portType)}`)
    .join(" | ");
}

function renderPortSummaryIcons(items: PortPreview[]) {
  const visible = items.slice(0, MAX_VISIBLE_PORT_PREVIEW);
  return (
    <>
      {visible.map((item) => (
        <span
          key={`${item.key}:${item.portType}`}
          className={`task-graph-port-badge task-graph-port-badge-${sanitizeToken(item.portType)}`}
          aria-label={`${item.label}: ${portTypeLabel(item.portType)}`}
          title={`${item.label}: ${portTypeLabel(item.portType)}`}
        >
          {portTypeIcon(item.portType, 11)}
        </span>
      ))}
      {items.length > visible.length ? (
        <span className="task-graph-port-badge task-graph-port-badge-overflow">
          +{items.length - visible.length}
        </span>
      ) : null}
    </>
  );
}

function dedupePortPreviews(items: PortPreview[]) {
  const seen = new Set<string>();
  const result: PortPreview[] = [];
  for (const item of items) {
    const key = `${item.portType}:${item.label}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(item);
  }
  return result;
}

function edgeTypeRequiresTypedCompatibility(edgeType: string) {
  return String(edgeType || "").trim() !== "control_dependency";
}

function buildEdgePortCompatibility(args: {
  fromNodeId: string;
  toNodeId: string;
  edgeType: string;
  graph: TaskGraphDefinition | null;
  nodeMap: Map<string, TaskGraphNode>;
}): EdgePortCompatibility | null {
  const { fromNodeId, toNodeId, edgeType, graph, nodeMap } = args;
  if (!graph || !fromNodeId || !toNodeId) return null;
  const sourceNode = nodeMap.get(fromNodeId) ?? null;
  const targetNode = nodeMap.get(toNodeId) ?? null;
  if (!sourceNode || !targetNode) return null;
  const sourcePorts = nodePortSummary(sourceNode, graph).outputs;
  const targetPorts = nodePortSummary(targetNode, graph).inputs;
  const remainingTargets = [...targetPorts];
  const matches: PortCompatibilityMatch[] = [];
  for (const source of sourcePorts) {
    const matchIndex = remainingTargets.findIndex(
      (target) => target.portType === source.portType,
    );
    if (matchIndex < 0) continue;
    const [target] = remainingTargets.splice(matchIndex, 1);
    matches.push({ source, target });
  }
  const compatible = matches.length > 0;
  const blocking = edgeTypeRequiresTypedCompatibility(edgeType) && !compatible;
  return {
    sourceNode,
    targetNode,
    sourcePorts,
    targetPorts,
    matches,
    compatible,
    blocking,
    message: compatible
      ? `Compatible typed ports: ${matches
          .map(
            (match) =>
              `${match.source.label} -> ${match.target.label} (${portTypeLabel(match.source.portType)})`,
          )
          .join(" | ")}`
      : blocking
        ? "No compatible typed ports between source outputs and target inputs."
        : "Control-only edge; typed payload does not currently match.",
  };
}

function edgeDraftCompatibility(
  draft: EdgeDraft | null,
  graph: TaskGraphDefinition | null,
  nodeMap: Map<string, TaskGraphNode>,
) {
  if (!draft?.from_node_id || !draft?.to_node_id) return null;
  return buildEdgePortCompatibility({
    fromNodeId: draft.from_node_id,
    toNodeId: draft.to_node_id,
    edgeType: draft.edge_type,
    graph,
    nodeMap,
  });
}

function nodeEdgeTargetCompatibility(
  sourceNodeId: string,
  targetNodeId: string,
  graph: TaskGraphDefinition | null,
  nodeMap: Map<string, TaskGraphNode>,
) {
  return buildEdgePortCompatibility({
    fromNodeId: sourceNodeId,
    toNodeId: targetNodeId,
    edgeType: "artifact_handoff",
    graph,
    nodeMap,
  });
}

function labelForNodeId(nodeMap: Map<string, TaskGraphNode>, nodeId: string) {
  return nodeMap.get(nodeId)?.label ?? nodeId;
}

function shortThreadId(value: string | undefined) {
  const text = String(value || "").trim();
  if (!text) return "no-thread";
  return text.length <= 18 ? text : `${text.slice(0, 8)}...${text.slice(-6)}`;
}

function shortRunId(value: string | undefined) {
  const text = String(value || "").trim();
  if (!text) return "no-run";
  return text.length <= 30 ? text : `${text.slice(0, 14)}...${text.slice(-10)}`;
}

function formatRunUpdatedAt(value: string | undefined) {
  if (!value) return "";
  return new Date(value).toLocaleString();
}

function formatRunTokenUsage(
  tokenUsage:
    | {
        status?: string | null;
        total_tokens?: number | null;
      }
    | null
    | undefined,
  locale: LocaleCode,
) {
  const totalTokens = tokenUsage?.total_tokens;
  if (typeof totalTokens === "number" && Number.isFinite(totalTokens)) {
    return totalTokens.toLocaleString(locale);
  }
  return locale === "zh-CN" ? "未提供" : "n/a";
}

function formatRunCallSummary(
  providerCalls: number | null | undefined,
  toolCalls: number | null | undefined,
  locale: LocaleCode,
) {
  const hasProviderCalls =
    typeof providerCalls === "number" && Number.isFinite(providerCalls);
  const hasToolCalls =
    typeof toolCalls === "number" && Number.isFinite(toolCalls);
  if (!hasProviderCalls && !hasToolCalls) {
    return locale === "zh-CN" ? "未提供" : "n/a";
  }
  return `P${hasProviderCalls ? providerCalls : "?"} / T${hasToolCalls ? toolCalls : "?"}`;
}

function formatRunElapsed(
  elapsedMs: number | null | undefined,
  locale: LocaleCode,
) {
  if (typeof elapsedMs !== "number" || !Number.isFinite(elapsedMs)) {
    return locale === "zh-CN" ? "未提供" : "n/a";
  }
  if (elapsedMs < 1000) return `${Math.max(0, Math.round(elapsedMs))} ms`;
  return `${(elapsedMs / 1000).toFixed(elapsedMs >= 10_000 ? 0 : 1)} s`;
}

function formatRunBudgetSummary(
  budget:
    | {
        status?: string | null;
      }
    | null
    | undefined,
  locale: LocaleCode,
) {
  const status = String(budget?.status || "").trim();
  if (!status) return locale === "zh-CN" ? "未配置" : "not configured";
  switch (status) {
    case "within_budget":
      return locale === "zh-CN" ? "预算内" : "within budget";
    case "exceeded":
      return locale === "zh-CN" ? "已超限" : "exceeded";
    case "unknown":
      return locale === "zh-CN" ? "未知" : "unknown";
    case "not_configured":
      return locale === "zh-CN" ? "未配置" : "not configured";
    default:
      return status.replace(/_/g, " ");
  }
}

function formatRunCost(
  cost:
    | {
        total_cost?: number | null;
        currency?: string | null;
        status?: string | null;
      }
    | null
    | undefined,
  locale: LocaleCode,
) {
  const totalCost = cost?.total_cost;
  if (typeof totalCost === "number" && Number.isFinite(totalCost)) {
    const currency = String(cost?.currency || "").trim();
    return currency
      ? `${currency} ${totalCost.toFixed(totalCost >= 1 ? 2 : 4)}`
      : totalCost.toFixed(totalCost >= 1 ? 2 : 4);
  }
  const status = String(cost?.status || "").trim();
  if (status === "not_available") {
    return locale === "zh-CN" ? "未提供" : "n/a";
  }
  return locale === "zh-CN" ? "未提供" : "n/a";
}

function humanizeRunStatusKey(statusKey: string, locale: LocaleCode) {
  switch (String(statusKey || "").trim()) {
    case "queued":
      return locale === "zh-CN" ? "排队" : "queued";
    case "waiting_on_dependencies":
      return locale === "zh-CN" ? "等待依赖" : "waiting";
    case "running":
      return locale === "zh-CN" ? "运行中" : "running";
    case "completed":
      return locale === "zh-CN" ? "已完成" : "completed";
    case "failed":
      return locale === "zh-CN" ? "失败" : "failed";
    case "blocked":
      return locale === "zh-CN" ? "阻塞" : "blocked";
    case "paused_for_review":
      return locale === "zh-CN" ? "待审核" : "review";
    case "cancelled":
      return locale === "zh-CN" ? "已取消" : "cancelled";
    case "partial":
      return locale === "zh-CN" ? "部分完成" : "partial";
    default:
      return String(statusKey || "")
        .trim()
        .replace(/_/g, " ");
  }
}

function formatRunStatusCountsSummary(
  statusCounts: Record<string, number> | null | undefined,
  locale: LocaleCode,
  maxItems = 3,
) {
  if (!statusCounts || typeof statusCounts !== "object") return "";
  const priority: Record<string, number> = {
    queued: 0,
    running: 1,
    waiting_on_dependencies: 2,
    paused_for_review: 3,
    blocked: 4,
    failed: 5,
    partial: 6,
    completed: 7,
    cancelled: 8,
  };
  const entries = Object.entries(statusCounts)
    .filter(
      ([, count]) =>
        typeof count === "number" && Number.isFinite(count) && count > 0,
    )
    .sort((a, b) => {
      const priorityDelta =
        (priority[a[0]] ?? Number.MAX_SAFE_INTEGER) -
        (priority[b[0]] ?? Number.MAX_SAFE_INTEGER);
      if (priorityDelta !== 0) return priorityDelta;
      return b[1] - a[1];
    });
  if (!entries.length) return "";
  return entries
    .slice(0, maxItems)
    .map(
      ([statusKey, count]) =>
        `${count.toLocaleString(locale)} ${humanizeRunStatusKey(statusKey, locale)}`,
    )
    .join(" / ");
}

function artifactLabel(artifact: { artifact_kind: string; path: string }) {
  const path = String(artifact.path || "").replace(/\\/g, "/");
  const filename = path.split("/").filter(Boolean).pop() || path;
  return `${artifact.artifact_kind}: ${filename}`;
}

function artifactFilename(path: string) {
  const normalized = String(path || "").replace(/\\/g, "/");
  return normalized.split("/").filter(Boolean).pop() || normalized;
}

function contextPolicyPreset(node: TaskGraphNode) {
  const uiHints =
    node.ui_hints &&
    typeof node.ui_hints === "object" &&
    !Array.isArray(node.ui_hints)
      ? (node.ui_hints as Record<string, unknown>)
      : {};
  return typeof uiHints.context_policy_preset === "string" &&
    uiHints.context_policy_preset
    ? uiHints.context_policy_preset
    : "task_digest";
}

function displayNodeKind(node: TaskGraphNode) {
  const uiHints =
    node.ui_hints &&
    typeof node.ui_hints === "object" &&
    !Array.isArray(node.ui_hints)
      ? (node.ui_hints as Record<string, unknown>)
      : {};
  return typeof uiHints.palette_role === "string" && uiHints.palette_role.trim()
    ? uiHints.palette_role.trim()
    : node.kind;
}

function displayTemplateNodeKind(kind: string) {
  const normalized = String(kind || "").trim();
  if (normalized === "artifact_source") return "custom";
  if (normalized === "planner") return "supervisor";
  return normalized || "custom";
}

function isCustomTemplate(template: TaskGraphTemplateSummary) {
  const templateId = String(template.template_id || "").trim().toLowerCase();
  const title = String(template.title || "").trim().toLowerCase();
  return templateId.startsWith("custom_") || title.startsWith("custom ");
}

function summarizeTemplate(
  template: TaskGraphTemplateSummary | null,
  locale: LocaleCode,
) {
  if (!template) return "";
  const overrides =
    locale === "zh-CN"
      ? {
          supervisor_worker_synthesizer:
            "一个规划节点拆解任务，一个执行节点完成动作，最后统一收束成结果。",
          fanout_fanin_research:
            "把研究任务拆成并行分支，最后集中合并为一份结论。",
          code_fix_test_review:
            "先规划修改，再落地代码、运行检查，最后补一轮审查。",
          provider_update_smoke_gate:
            "先发现 provider 变化，再跑烟测覆盖，最后通过人工关卡决定是否推广。",
          document_extract_analyze_report:
            "先提取材料，再做分析，最后产出一份可交付的报告。",
          multimodal_capability_adapter:
            "先探测多模态能力，再适配契约，并验证降级和回退路径。",
          custom_blank_graph:
            "从空白起步，按你的任务方式自己搭建整张工作流图。",
        }
      : {
          supervisor_worker_synthesizer:
            "Plan once, run one bounded worker lane, then merge the result into a final answer.",
          fanout_fanin_research:
            "Split research into parallel branches, then combine the findings into one conclusion.",
          code_fix_test_review:
            "Plan the code change, implement it, run checks, and finish with a review step.",
          provider_update_smoke_gate:
            "Track provider changes, run smoke coverage, and hold promotion behind a human gate.",
          document_extract_analyze_report:
            "Extract source material, analyze it, and finish with a deliverable report.",
          multimodal_capability_adapter:
            "Probe multimodal capabilities, adapt the contract, and verify the fallback path.",
          custom_blank_graph:
            "Start from a blank graph when you want to design the workflow yourself.",
        };
  const override = overrides[template.template_id as keyof typeof overrides];
  const fallback = String(template.summary || "").trim();
  return override || fallback || (locale === "zh-CN"
    ? "一个可复用的任务工作流模板。"
    : "A reusable task workflow template.");
}

function formatTemplateStructure(
  template: TaskGraphTemplateSummary | null,
  locale: LocaleCode,
) {
  if (!template) return "";
  return locale === "zh-CN"
    ? `${template.node_count} \u4e2a\u8282\u70b9 / ${template.edge_count} \u6761\u8fde\u7ebf`
    : `${template.node_count} nodes / ${template.edge_count} edges`;
}

function paletteSections(locale: LocaleCode) {
  if (locale === "zh-CN") {
    return [
      {
        id: "planning",
        label: "规划与研究",
        kinds: ["supervisor", "planner", "researcher", "extractor"] as const,
      },
      {
        id: "execution",
        label: "执行与收敛",
        kinds: [
          "worker",
          "coder",
          "synthesizer",
          "reviewer",
          "validator",
        ] as const,
      },
      {
        id: "control",
        label: "控制与自定义",
        kinds: ["gate", "custom"] as const,
      },
    ];
  }
  return [
    {
      id: "planning",
      label: "Planning",
      kinds: ["supervisor", "planner", "researcher", "extractor"] as const,
    },
    {
      id: "execution",
      label: "Execution",
      kinds: ["worker", "coder", "synthesizer", "reviewer", "validator"] as const,
    },
    {
      id: "control",
      label: "Control",
      kinds: ["gate", "custom"] as const,
    },
  ];
}

function nodeDraftEqual(left: NodeDraft, right: NodeDraft) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function edgeDraftEqual(left: EdgeDraft, right: EdgeDraft) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function validateNodeDraft(args: {
  draft: NodeDraft | null;
  node: TaskGraphNode | null;
  graph: TaskGraphDefinition | null;
}) {
  const { draft, node, graph } = args;
  if (!draft) return "";
  if (!draft.label.trim()) return "Role label is required.";
  if (draft.model_id.trim() && !draft.provider_id.trim())
    return "Provider is required when a model is set.";
  if (!draft.context_policy_preset.trim()) return "Context policy is required.";
  if (!draft.memory_policy_preset.trim()) return "Memory policy is required.";
  const invalidPromptVariables = collectUnknownPromptVariables({
    draft,
    node,
    graph,
  });
  if (invalidPromptVariables.length) {
    return `Unknown prompt variables: ${invalidPromptVariables.join(", ")}.`;
  }
  if (
    (draft.allow_code_changes || draft.allow_install) &&
    !draft.requires_human_approval
  ) {
    return "Code changes or install access require human approval.";
  }
  if (draft.requires_human_approval && !draft.approval_review_kind.trim()) {
    return "Choose an approval kind when human approval is enabled.";
  }
  const parsedSchema = parseNodeSchemaText(draft.machine_result_schema_text);
  if (draft.machine_result_schema_text.trim() && !parsedSchema) {
    return "Output schema must be a valid JSON object.";
  }
  if (!draft.artifact_only && !parsedSchema) {
    return "Output schema must be a valid JSON object.";
  }
  return "";
}

function incompleteNodeWarning(
  message: string,
  node: TaskGraphNode,
  draft: NodeDraft | null,
) {
  const providerId = String(
    draft?.provider_id ?? node.provider_id ?? "",
  ).trim();
  const modelId = String(draft?.model_id ?? node.model_id ?? "").trim();
  if (providerId && modelId) return "";
  return message;
}

function validateEdgeDraft(args: {
  draft: EdgeDraft | null;
  graph: TaskGraphDefinition | null;
  selectedEdgeId: string | null;
  isCreatingEdge: boolean;
  nodeMap: Map<string, TaskGraphNode>;
}) {
  const { draft, graph, selectedEdgeId, isCreatingEdge, nodeMap } = args;
  if (!draft) return "";
  if (!draft.from_node_id.trim()) return "Source node is required.";
  if (!draft.to_node_id.trim()) return "Target node is required.";
  if (draft.from_node_id === draft.to_node_id)
    return "Source and target must be different nodes.";
  if (!draft.edge_type.trim()) return "Edge type is required.";
  if (!draft.handoff_message_template.trim())
    return "Handoff message template is required.";
  const requiredSchemaRefs = parseList(draft.required_output_schema_refs_text);
  if (!requiredSchemaRefs.length)
    return "At least one required input schema ref is required.";
  const inferredSourceSchemaRef = inferNodeSchemaRef(
    nodeMap.get(draft.from_node_id) ?? null,
  );
  if (
    inferredSourceSchemaRef &&
    !requiredSchemaRefs.includes(inferredSourceSchemaRef)
  ) {
    return `Required input schema refs must include ${inferredSourceSchemaRef}.`;
  }
  if (!edgeMessagePartModes(draft).length)
    return "Select at least one message part for the handoff payload.";
  if (!draft.exclude_private_memory)
    return "Private memory exclusion is required for worker-safe handoff.";
  if (!/^\d+$/.test(draft.history_length.trim()))
    return "History length must be a non-negative integer.";
  if (!graph) return "";
  const compatibility = edgeDraftCompatibility(draft, graph, nodeMap);
  if (compatibility?.blocking) {
    return compatibility.message;
  }
  const duplicate = graph.edges.some((edge) => {
    if (!isCreatingEdge && edge.edge_id === selectedEdgeId) return false;
    return (
      edge.from_node_id === draft.from_node_id &&
      edge.to_node_id === draft.to_node_id &&
      edge.edge_type === draft.edge_type
    );
  });
  if (duplicate)
    return "An edge with the same source, target, and type already exists.";
  return "";
}

function parseNodeSchemaText(value: string) {
  const text = String(value || "").trim();
  if (!text) return {};
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

function stringifyJson(value: Record<string, unknown>) {
  return JSON.stringify(value, null, 2);
}

function insertTokenIntoText(currentValue: string, token: string) {
  const cleanValue = String(currentValue || "");
  if (!cleanValue.trim()) return token;
  return /\s$/.test(cleanValue)
    ? `${cleanValue}${token}`
    : `${cleanValue} ${token}`;
}

function promptVariables(
  node: TaskGraphNode,
  draft: NodeDraft,
  graph: TaskGraphDefinition | null,
) {
  const upstreamEdges = (graph?.edges ?? []).filter(
    (edge) => edge.to_node_id === node.node_id,
  );
  const upstreamNodes = upstreamEdges
    .map(
      (edge) =>
        graph?.nodes.find((item) => item.node_id === edge.from_node_id) ?? null,
    )
    .filter((item): item is TaskGraphNode => Boolean(item));
  const upstreamArtifactOutputs = upstreamNodes.flatMap((item) =>
    parseArtifactOutputs(item),
  );
  const upstreamSchemaRefs = upstreamNodes
    .map((item) => inferNodeSchemaRef(item))
    .filter((item): item is string => Boolean(item));
  return {
    graph_id: graph?.graph_id ?? "",
    graph_title: graph?.title ?? "",
    graph_template_id: graph?.template_id ?? "",
    node_id: node.node_id,
    node_label: draft.label.trim() || node.label,
    role: displayNodeKind(node),
    provider_id: draft.provider_id.trim(),
    model_id: draft.model_id.trim(),
    reasoning_effort: draft.reasoning_effort,
    permission_mode: draft.permission_mode,
    collaboration_mode: draft.collaboration_mode,
    execution_backend: draft.execution_backend,
    context_policy_preset: draft.context_policy_preset,
    memory_policy_preset: draft.memory_policy_preset,
    artifact_outputs: parseList(draft.artifact_outputs_text).join(", "),
    upstream_node_ids: upstreamNodes.map((item) => item.node_id).join(", "),
    upstream_node_labels: upstreamNodes.map((item) => item.label).join(", "),
    upstream_artifact_outputs: upstreamArtifactOutputs.join(", "),
    upstream_schema_refs: upstreamSchemaRefs.join(", "),
  };
}

function availablePromptVariables(
  node: TaskGraphNode,
  draft: NodeDraft,
  graph: TaskGraphDefinition | null,
): VariablePreviewEntry[] {
  return Object.entries(promptVariables(node, draft, graph)).map(
    ([key, value]) => ({
      token: `{{${key}}}`,
      preview: String(value || "unset"),
    }),
  );
}

function buildPromptPreview(
  node: TaskGraphNode,
  draft: NodeDraft,
  graph: TaskGraphDefinition | null,
) {
  const template = String(draft.human_summary_template || "").trim();
  if (!template) return "";
  const values = promptVariables(node, draft, graph);
  return template.replace(
    /\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}/g,
    (_match, variable) => String(values[variable as keyof typeof values] ?? ""),
  );
}

function buildNodePayloadPreview(
  node: TaskGraphNode,
  draft: NodeDraft,
  graph: TaskGraphDefinition | null,
) {
  const resolvedPrompt = buildPromptPreview(node, draft, graph);
  const parsedSchema = parseNodeSchemaText(draft.machine_result_schema_text);
  return JSON.stringify(
    {
      node_id: node.node_id,
      label: draft.label.trim() || node.label,
      resolved_prompt: resolvedPrompt,
      provider_id: draft.provider_id.trim(),
      model_id: draft.model_id.trim(),
      output_contract: {
        artifact_only: draft.artifact_only,
        human_summary_required: draft.human_summary_required,
        artifact_outputs: parseList(draft.artifact_outputs_text),
        machine_result_schema:
          parsedSchema && typeof parsedSchema === "object"
            ? parsedSchema
            : null,
      },
      upstream_context: {
        node_labels: promptVariables(node, draft, graph).upstream_node_labels,
        artifact_outputs: promptVariables(node, draft, graph)
          .upstream_artifact_outputs,
        schema_refs: promptVariables(node, draft, graph).upstream_schema_refs,
      },
    },
    null,
    2,
  );
}

function collectUnknownPromptVariables(args: {
  draft: NodeDraft;
  node: TaskGraphNode | null;
  graph: TaskGraphDefinition | null;
}) {
  const { draft, node, graph } = args;
  const known = new Set(
    node
      ? Object.keys(promptVariables(node, draft, graph))
      : [
          "node_id",
          "node_label",
          "role",
          "provider_id",
          "model_id",
          "reasoning_effort",
          "permission_mode",
          "collaboration_mode",
          "execution_backend",
          "context_policy_preset",
          "memory_policy_preset",
          "artifact_outputs",
        ],
  );
  const unknown = new Set<string>();
  for (const match of String(draft.human_summary_template || "").matchAll(
    /\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}/g,
  )) {
    const name = String(match[1] || "").trim();
    if (name && !known.has(name)) unknown.add(name);
  }
  return [...unknown];
}

function parseArtifactOutputs(node: TaskGraphNode | null) {
  if (!node) return [];
  const outputContract = asRecord(node.output_contract) ?? {};
  const artifactOutputs = Array.isArray(outputContract.artifact_outputs)
    ? outputContract.artifact_outputs
    : [];
  return artifactOutputs
    .map((item) => String(item || "").trim())
    .filter(Boolean);
}

function edgeMessageVariables(args: {
  draft: EdgeDraft | null;
  nodeMap: Map<string, TaskGraphNode>;
}) {
  const { draft, nodeMap } = args;
  const sourceNode = draft?.from_node_id
    ? (nodeMap.get(draft.from_node_id) ?? null)
    : null;
  const targetNode = draft?.to_node_id
    ? (nodeMap.get(draft.to_node_id) ?? null)
    : null;
  return {
    source_node_id: sourceNode?.node_id ?? "",
    source_node_label: sourceNode?.label ?? "",
    target_node_id: targetNode?.node_id ?? "",
    target_node_label: targetNode?.label ?? "",
    source_artifact_outputs: parseArtifactOutputs(sourceNode).join(", "),
    source_schema_ref: inferNodeSchemaRef(sourceNode) ?? "",
    edge_type: draft?.edge_type ?? "",
  };
}

function availableEdgeMessageVariables(args: {
  draft: EdgeDraft | null;
  nodeMap: Map<string, TaskGraphNode>;
}): VariablePreviewEntry[] {
  return Object.entries(edgeMessageVariables(args)).map(([key, value]) => ({
    token: `{{${key}}}`,
    preview: String(value || "unset"),
  }));
}

function buildEdgePayloadPreview(args: {
  draft: EdgeDraft | null;
  nodeMap: Map<string, TaskGraphNode>;
}) {
  const { draft, nodeMap } = args;
  if (!draft) return "";
  const values = edgeMessageVariables({ draft, nodeMap });
  const resolvedMessage = String(draft.handoff_message_template || "").replace(
    /\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}/g,
    (_match, variable) => String(values[variable as keyof typeof values] ?? ""),
  );
  return JSON.stringify(
    {
      from_node_id: draft.from_node_id,
      to_node_id: draft.to_node_id,
      edge_type: draft.edge_type,
      resolved_message: resolvedMessage,
      required_output_schema_refs: parseList(
        draft.required_output_schema_refs_text,
      ),
      message_part_modes: edgeMessagePartModes(draft),
      context_policy: {
        history_mode: draft.history_mode,
        artifact_mode: draft.artifact_mode,
        history_length: /^\d+$/.test(draft.history_length.trim())
          ? Number.parseInt(draft.history_length, 10)
          : null,
        included_artifacts: normalizeIncludedArtifactsForMode(
          draft.artifact_mode,
          parseList(draft.included_artifacts_text),
        ),
        resource_refs: parseList(draft.resource_refs_text),
      },
    },
    null,
    2,
  );
}

function defaultApprovalKindForDraft(draft: NodeDraft) {
  if (draft.allow_install) return "install_gate";
  if (draft.allow_code_changes) return "filesystem_write_gate";
  if (draft.allow_provider_calls) return "provider_call_gate";
  return "human_gate";
}

function handleNodeMouseDown(args: {
  event: ReactMouseEvent<HTMLDivElement>;
  node: TaskGraphNode;
  onSelectNode: (nodeId: string) => void;
  setDragState: (state: DragState) => void;
}) {
  const { event, node, onSelectNode, setDragState } = args;
  if (event.button !== 0) return;
  onSelectNode(node.node_id);
  setDragState({
    pointerId: 0,
    nodeId: node.node_id,
    startX: event.clientX,
    startY: event.clientY,
    originX: node.position.x,
    originY: node.position.y,
  });
}

function projectNodePosition(args: {
  stageElement: HTMLDivElement | null;
  originX: number;
  originY: number;
  deltaX: number;
  deltaY: number;
}) {
  const { stageElement, originX, originY, deltaX, deltaY } = args;
  const rawX = originX + deltaX;
  const rawY = originY + deltaY;
  const maxX = Math.max(0, (stageElement?.clientWidth ?? 0) - NODE_CARD_WIDTH);
  const maxY = Math.max(
    0,
    (stageElement?.clientHeight ?? 0) - NODE_CARD_HEIGHT,
  );
  return {
    x: clamp(Math.round(rawX), 16, maxX || Math.round(rawX)),
    y: clamp(Math.round(rawY), 16, maxY || Math.round(rawY)),
  };
}

function measureGraphBounds(
  nodes: TaskGraphNode[],
  previewPositions: Record<string, TaskGraphNodePosition>,
) {
  if (!nodes.length) {
    return { width: MIN_STAGE_WIDTH, height: MIN_STAGE_HEIGHT };
  }
  const rightMost = Math.max(
    ...nodes.map((node) => {
      const position = previewPositions[node.node_id] ?? node.position;
      return position.x + NODE_CARD_WIDTH;
    }),
  );
  const bottomMost = Math.max(
    ...nodes.map((node) => {
      const position = previewPositions[node.node_id] ?? node.position;
      return position.y + NODE_CARD_HEIGHT;
    }),
  );
  return {
    width: Math.max(MIN_STAGE_WIDTH, rightMost + STAGE_PADDING),
    height: Math.max(MIN_STAGE_HEIGHT, bottomMost + STAGE_PADDING),
  };
}

function nodeToneForKind(kind: string) {
  switch (
    String(kind || "")
      .trim()
      .toLowerCase()
  ) {
    case "supervisor":
    case "planner":
      return "planner";
    case "worker":
    case "coder":
      return "worker";
    case "synthesizer":
      return "synthesizer";
    case "validator":
      return "validator";
    case "reviewer":
      return "reviewer";
    case "gate":
      return "gate";
    case "extractor":
    case "researcher":
      return "extractor";
    default:
      return "neutral";
  }
}

function nodeKindIcon(kind: string, size = 14) {
  switch (
    String(kind || "")
      .trim()
      .toLowerCase()
  ) {
    case "supervisor":
    case "compass":
      return <Compass size={size} />;
    case "planner":
    case "file-text":
      return <FileText size={size} />;
    case "worker":
    case "mcp_tool":
    case "wrench":
      return <Wrench size={size} />;
    case "coder":
    case "braces":
      return <Braces size={size} />;
    case "synthesizer":
    case "sparkles":
      return <Sparkles size={size} />;
    case "validator":
    case "shield-check":
      return <ShieldCheck size={size} />;
    case "reviewer":
    case "eye":
      return <Eye size={size} />;
    case "gate":
    case "human_approval":
    case "lock":
      return <Lock size={size} />;
    case "researcher":
    case "search":
      return <Search size={size} />;
    case "extractor":
    case "mcp_resource":
    case "database":
      return <Database size={size} />;
    case "transform":
    case "loop":
    case "repeat":
      return <Repeat size={size} />;
    case "router_condition":
    case "git-branch":
      return <GitBranch size={size} />;
    case "subgraph":
    case "boxes":
      return <Boxes size={size} />;
    case "artifact_source":
      return <FileText size={size} />;
    case "artifact_sink":
    case "square-stack":
      return <SquareStack size={size} />;
    default:
      return <Bot size={size} />;
  }
}

function paletteNodeMeta(kind: string) {
  switch (
    String(kind || "")
      .trim()
      .toLowerCase()
  ) {
    case "supervisor":
      return {
        label: "Supervisor",
        description:
          "Plans the bounded workflow and coordinates downstream workers.",
      };
    case "planner":
      return {
        label: "Planner",
        description:
          "Breaks work into explicit steps and hands them to other agents.",
      };
    case "worker":
      return {
        label: "Worker",
        description: "Executes the main task and returns the primary artifact.",
      };
    case "coder":
      return {
        label: "Coder",
        description:
          "Applies code or document changes in a bounded implementation lane.",
      };
    case "reviewer":
      return {
        label: "Reviewer",
        description:
          "Reads outputs critically and returns review feedback or approval.",
      };
    case "validator":
      return {
        label: "Validator",
        description:
          "Runs checks, tests, or smoke validation before promotion.",
      };
    case "researcher":
      return {
        label: "Researcher",
        description:
          "Collects evidence, docs, or comparisons before synthesis.",
      };
    case "extractor":
      return {
        label: "Extractor",
        description:
          "Pulls structured facts from files, docs, or provider metadata.",
      };
    case "synthesizer":
      return {
        label: "Synthesizer",
        description:
          "Merges branch outputs into one bounded answer or artifact set.",
      };
    case "gate":
      return {
        label: "Gate",
        description:
          "Requires human review or a safety decision before continuing.",
      };
    default:
      return {
        label: "Custom",
        description:
          "Starts as a neutral agent shell with the default fallback icon.",
      };
  }
}

function sanitizeToken(value: string) {
  return value
    .trim()
    .replace(/[^a-z0-9_]+/gi, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
}

function asRecord(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function parseList(value: string) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function stringifyList(value: string[] | undefined) {
  return Array.isArray(value) ? value.join(", ") : "";
}

function clamp(value: number, min: number, max: number) {
  if (max < min) return min;
  return Math.min(max, Math.max(min, value));
}

function taskGraphPanelWidthRange(side: "left") {
  const viewportWidth =
    typeof window === "undefined" ? 1440 : window.innerWidth;
  return {
    min: MIN_TASK_GRAPH_SIDEBAR_WIDTH,
    max: Math.max(
      MIN_TASK_GRAPH_SIDEBAR_WIDTH,
      Math.min(80, Math.round(viewportWidth * 0.08)),
    ),
  };
}

function normalizeTaskGraphPanelWidth(side: "left", value: number) {
  const { min, max } = taskGraphPanelWidthRange(side);
  return clamp(Math.round(value), min, max);
}

function readStoredTaskGraphPanelWidth(
  side: "left",
  storageKey: string,
  fallback: number,
) {
  if (typeof window === "undefined") return fallback;
  const rawValue = Number.parseFloat(
    window.localStorage.getItem(storageKey) || "",
  );
  if (!Number.isFinite(rawValue)) return fallback;
  return normalizeTaskGraphPanelWidth(side, rawValue);
}

function taskGraphWorkspaceStateStorageKey(
  taskId: string | undefined,
  graphId: string | undefined,
) {
  const normalizedTaskId = String(taskId || "").trim();
  const normalizedGraphId = String(graphId || "").trim();
  if (!normalizedTaskId || !normalizedGraphId) return null;
  return `${TASK_GRAPH_WORKSPACE_STATE_STORAGE_KEY_PREFIX}.${normalizedTaskId}.${normalizedGraphId}`;
}

function readStoredTaskGraphWorkspaceState(
  storageKey: string,
): TaskGraphWorkspaceStoredState | null {
  if (typeof window === "undefined") return null;
  try {
    const rawValue = window.localStorage.getItem(storageKey);
    if (!rawValue) return null;
    const parsed = JSON.parse(rawValue) as Partial<TaskGraphWorkspaceStoredState>;
    if (
      parsed.inspectorWorkspace !== "selection" &&
      parsed.inspectorWorkspace !== "run"
    ) {
      return null;
    }
    return {
      sidebarExpanded: Boolean(parsed.sidebarExpanded),
      inspectorExpanded: Boolean(parsed.inspectorExpanded),
      inspectorWorkspace: parsed.inspectorWorkspace,
      readinessExpanded: Boolean(parsed.readinessExpanded),
      latestRunExpanded: Boolean(parsed.latestRunExpanded),
      recoveryExpanded: Boolean(parsed.recoveryExpanded),
    };
  } catch {
    return null;
  }
}

function writePendingRunInspectorReopen(
  storageKey: string | null,
  value: boolean,
) {
  if (typeof window === "undefined" || !storageKey) return;
  try {
    if (value) {
      window.localStorage.setItem(storageKey, "1");
      return;
    }
    window.localStorage.removeItem(storageKey);
  } catch {
    // Ignore storage write failures; they only affect best-effort modal restore.
  }
}

function consumePendingRunInspectorReopen(storageKey: string | null): boolean {
  if (typeof window === "undefined" || !storageKey) return false;
  try {
    const pending = window.localStorage.getItem(storageKey) === "1";
    if (pending) {
      window.localStorage.removeItem(storageKey);
    }
    return pending;
  } catch {
    return false;
  }
}
