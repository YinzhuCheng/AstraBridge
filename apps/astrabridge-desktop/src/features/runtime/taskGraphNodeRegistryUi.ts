import type {
  LocaleCode,
  NodeTypeRegistryEntry,
  NodeTypeRegistrySnapshot,
  TaskGraphNode,
} from "../../types";

type RawPaletteVariant = {
  kind?: unknown;
  label?: unknown;
  description?: unknown;
  palette_sections?: unknown;
  icon?: unknown;
  tone?: unknown;
};

export type TaskGraphPaletteItem = {
  kind: string;
  label: string;
  description: string;
  tone: string;
  icon: string;
  sectionIds: string[];
  resolvedTypeId: string;
};

export type TaskGraphPaletteSection = {
  id: string;
  label: string;
  kinds: string[];
};

export type TaskGraphNodeRegistryUi = {
  byKind: Map<string, TaskGraphPaletteItem>;
  byTypeId: Map<string, NodeTypeRegistryEntry>;
  paletteSections: TaskGraphPaletteSection[];
  kindForNode: (node: TaskGraphNode) => string;
  kindForTemplate: (kind: string) => string;
  typeSpecForKind: (kind: string) => NodeTypeRegistryEntry | null;
  typeSpecForNode: (node: TaskGraphNode | null) => NodeTypeRegistryEntry | null;
};

type StaticPaletteMeta = Omit<TaskGraphPaletteItem, "resolvedTypeId">;

const STATIC_PALETTE_META: Record<string, StaticPaletteMeta> = {
  supervisor: {
    kind: "supervisor",
    label: "Supervisor",
    description:
      "Plans the bounded workflow and coordinates downstream workers.",
    tone: "planner",
    icon: "compass",
    sectionIds: ["planning"],
  },
  planner: {
    kind: "planner",
    label: "Planner",
    description:
      "Breaks work into explicit steps and hands them to other agents.",
    tone: "planner",
    icon: "file-text",
    sectionIds: ["planning"],
  },
  researcher: {
    kind: "researcher",
    label: "Researcher",
    description:
      "Collects evidence, docs, or comparisons before synthesis.",
    tone: "extractor",
    icon: "search",
    sectionIds: ["planning"],
  },
  extractor: {
    kind: "extractor",
    label: "Extractor",
    description:
      "Pulls structured facts from files, docs, or provider metadata.",
    tone: "extractor",
    icon: "database",
    sectionIds: ["planning"],
  },
  worker: {
    kind: "worker",
    label: "Worker",
    description:
      "Executes the main task and returns the primary artifact.",
    tone: "worker",
    icon: "wrench",
    sectionIds: ["execution"],
  },
  coder: {
    kind: "coder",
    label: "Coder",
    description:
      "Applies code or document changes in a bounded implementation lane.",
    tone: "worker",
    icon: "braces",
    sectionIds: ["execution"],
  },
  synthesizer: {
    kind: "synthesizer",
    label: "Synthesizer",
    description:
      "Merges branch outputs into one bounded answer or artifact set.",
    tone: "synthesizer",
    icon: "sparkles",
    sectionIds: ["execution"],
  },
  reviewer: {
    kind: "reviewer",
    label: "Reviewer",
    description:
      "Reads outputs critically and returns review feedback or approval.",
    tone: "reviewer",
    icon: "eye",
    sectionIds: ["execution"],
  },
  validator: {
    kind: "validator",
    label: "Validator",
    description:
      "Runs checks, tests, or smoke validation before promotion.",
    tone: "validator",
    icon: "shield-check",
    sectionIds: ["execution"],
  },
  gate: {
    kind: "gate",
    label: "Gate",
    description:
      "Pauses the graph behind an explicit approval or promotion decision.",
    tone: "gate",
    icon: "lock",
    sectionIds: ["control"],
  },
  custom: {
    kind: "custom",
    label: "Custom",
    description:
      "Starts as a neutral agent shell with the default fallback icon.",
    tone: "neutral",
    icon: "bot",
    sectionIds: ["control"],
  },
  mcp_tool: {
    kind: "mcp_tool",
    label: "MCP Tool",
    description:
      "Executes one declared MCP tool operation through the broker boundary.",
    tone: "neutral",
    icon: "wrench",
    sectionIds: ["control"],
  },
  mcp_resource: {
    kind: "mcp_resource",
    label: "MCP Resource",
    description: "Reads one declared MCP resource into the graph.",
    tone: "neutral",
    icon: "database",
    sectionIds: ["control"],
  },
  transform: {
    kind: "transform",
    label: "Transform",
    description:
      "Applies a deterministic transform between typed graph ports.",
    tone: "neutral",
    icon: "repeat",
    sectionIds: ["execution"],
  },
  router_condition: {
    kind: "router_condition",
    label: "Router / Condition",
    description:
      "Routes control flow based on deterministic conditions.",
    tone: "neutral",
    icon: "git-branch",
    sectionIds: ["control"],
  },
  loop: {
    kind: "loop",
    label: "Loop",
    description:
      "Repeats a bounded subpath with explicit iteration controls.",
    tone: "neutral",
    icon: "repeat",
    sectionIds: ["control"],
  },
  subgraph: {
    kind: "subgraph",
    label: "Subgraph",
    description: "Invokes a nested bounded graph with typed I/O.",
    tone: "neutral",
    icon: "boxes",
    sectionIds: ["control"],
  },
  artifact_source: {
    kind: "artifact_source",
    label: "Artifact Source",
    description: "Introduces an external or preserved artifact into the graph.",
    tone: "neutral",
    icon: "file-text",
    sectionIds: ["control"],
  },
  artifact_sink: {
    kind: "artifact_sink",
    label: "Artifact Sink",
    description: "Persists or promotes a typed artifact as a terminal sink.",
    tone: "neutral",
    icon: "square-stack",
    sectionIds: ["control"],
  },
  agent_model: {
    kind: "agent_model",
    label: "Agent / Model",
    description:
      "Bounded provider-backed agent lane with explicit routing and typed ports.",
    tone: "neutral",
    icon: "bot",
    sectionIds: ["planning", "execution"],
  },
  human_approval: {
    kind: "human_approval",
    label: "Human Approval",
    description:
      "Pauses execution behind an explicit review and approval decision.",
    tone: "gate",
    icon: "lock",
    sectionIds: ["control"],
  },
};

const FALLBACK_SECTIONS = [
  { id: "planning", labelEn: "Planning", labelZh: "规划与研究" },
  { id: "execution", labelEn: "Execution", labelZh: "执行与收束" },
  { id: "control", labelEn: "Control", labelZh: "控制与自定义" },
] as const;

function sectionLabel(id: string, locale: LocaleCode) {
  const section = FALLBACK_SECTIONS.find((item) => item.id === id);
  if (!section) return id;
  return locale === "zh-CN" ? section.labelZh : section.labelEn;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function normalizeText(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeVariantSections(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => normalizeText(item))
    .filter(Boolean);
}

function defaultMetaForKind(kind: string): TaskGraphPaletteItem {
  const normalized = normalizeText(kind) || "custom";
  const fallback = STATIC_PALETTE_META[normalized] ?? STATIC_PALETTE_META.custom;
  return {
    ...fallback,
    resolvedTypeId: normalized,
  };
}

function paletteVariantsForSpec(spec: NodeTypeRegistryEntry): TaskGraphPaletteItem[] {
  const uiHints = asRecord(spec.ui_hints) ?? {};
  const rawVariants = Array.isArray(uiHints.palette_variants)
    ? (uiHints.palette_variants as RawPaletteVariant[])
    : [];
  const variants = rawVariants
    .map((variant) => {
      const kind = normalizeText(variant.kind);
      if (!kind) return null;
      const fallback = defaultMetaForKind(kind);
      return {
        kind,
        label: normalizeText(variant.label) || fallback.label,
        description: normalizeText(variant.description) || fallback.description,
        tone: normalizeText(variant.tone) || fallback.tone,
        icon: normalizeText(variant.icon) || fallback.icon,
        sectionIds:
          normalizeVariantSections(variant.palette_sections).length > 0
            ? normalizeVariantSections(variant.palette_sections)
            : fallback.sectionIds,
        resolvedTypeId: spec.type_id,
      } satisfies TaskGraphPaletteItem;
    })
    .filter((item): item is TaskGraphPaletteItem => Boolean(item));
  if (variants.length) return variants;

  const defaultKind =
    spec.type_id === "human_approval"
      ? "gate"
      : spec.type_id === "artifact_source"
        ? "custom"
        : spec.type_id;
  const fallback = defaultMetaForKind(defaultKind);
  const sectionIds = normalizeVariantSections(uiHints.palette_sections);
  return [
    {
      kind: defaultKind,
      label: spec.title || fallback.label,
      description: spec.description || fallback.description,
      tone: normalizeText(uiHints.tone) || fallback.tone,
      icon: normalizeText(uiHints.icon) || fallback.icon,
      sectionIds: sectionIds.length ? sectionIds : fallback.sectionIds,
      resolvedTypeId: spec.type_id,
    },
  ];
}

export function buildTaskGraphNodeRegistryUi(args: {
  locale: LocaleCode;
  snapshot?: NodeTypeRegistrySnapshot | null;
}): TaskGraphNodeRegistryUi {
  const { locale, snapshot } = args;
  const byKind = new Map<string, TaskGraphPaletteItem>();
  const byTypeId = new Map<string, NodeTypeRegistryEntry>();
  const preferredKindByTypeId = new Map<string, string>();
  const kindAliases = snapshot?.kind_aliases ?? {};

  if (snapshot?.node_types?.length) {
    for (const spec of snapshot.node_types) {
      byTypeId.set(spec.type_id, spec);
      for (const item of paletteVariantsForSpec(spec)) {
        if (!byKind.has(item.kind)) byKind.set(item.kind, item);
        preferredKindByTypeId.set(spec.type_id, item.kind);
      }
    }
  }

  if (byKind.size === 0) {
    for (const item of Object.values(STATIC_PALETTE_META)) {
      byKind.set(item.kind, { ...item, resolvedTypeId: item.kind });
      preferredKindByTypeId.set(item.kind, item.kind);
    }
  }

  const paletteSections = FALLBACK_SECTIONS.map((section) => {
    const kinds = Array.from(byKind.values())
      .filter((item) => item.sectionIds.includes(section.id))
      .map((item) => item.kind);
    return {
      id: section.id,
      label: sectionLabel(section.id, locale),
      kinds,
    };
  }).filter((section) => section.kinds.length > 0);

  const typeSpecForKind = (kind: string) => {
    const normalized = normalizeText(kind);
    if (!normalized) return null;
    const direct = byTypeId.get(normalized);
    if (direct) return direct;
    const resolvedTypeId = normalizeText(kindAliases[normalized]);
    return resolvedTypeId ? (byTypeId.get(resolvedTypeId) ?? null) : null;
  };

  const kindForTemplate = (kind: string) => {
    const normalized = normalizeText(kind);
    if (byKind.has(normalized)) return normalized;
    if (normalized === "artifact_source" && byKind.has("custom")) {
      return "custom";
    }
    const resolved = typeSpecForKind(normalized);
    if (!resolved) return normalized || "custom";
    return preferredKindByTypeId.get(resolved.type_id) ?? normalized;
  };

  const kindForNode = (node: TaskGraphNode) => {
    const uiHints = asRecord(node.ui_hints) ?? {};
    const paletteRole = normalizeText(uiHints.palette_role);
    if (paletteRole && byKind.has(paletteRole)) return paletteRole;
    return kindForTemplate(node.kind);
  };

  const typeSpecForNode = (node: TaskGraphNode | null) => {
    if (!node) return null;
    const uiHints = asRecord(node.ui_hints) ?? {};
    const nodeTypeId = normalizeText(uiHints.node_type_id);
    if (nodeTypeId && byTypeId.has(nodeTypeId)) {
      return byTypeId.get(nodeTypeId) ?? null;
    }
    return typeSpecForKind(node.kind);
  };

  return {
    byKind,
    byTypeId,
    paletteSections,
    kindForNode,
    kindForTemplate,
    typeSpecForKind,
    typeSpecForNode,
  };
}

export function taskGraphPaletteMeta(
  ui: TaskGraphNodeRegistryUi,
  kind: string,
): TaskGraphPaletteItem {
  return ui.byKind.get(kind) ?? defaultMetaForKind(kind);
}
