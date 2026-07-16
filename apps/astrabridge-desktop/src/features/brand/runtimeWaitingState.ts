import type { LocaleCode, RuntimeActivityState, RuntimeDiffSummary } from "../../types";
import { shortenActivityPath } from "../runtime/runtimeActivity";
import type { StarbridgeWaitingPhase } from "./StarbridgeWaitingConstellation";

type RuntimeWaitingInputs = {
  locale: LocaleCode;
  routeLabel?: string;
  liveActivity?: RuntimeActivityState;
  liveDiff?: RuntimeDiffSummary;
  waitingOnApproval: boolean;
  activeStatusType: string;
  startPending?: boolean;
  createThreadPending?: boolean;
  creatingTaskName?: string | null;
};

export type RuntimeWaitingDescriptor = {
  phase: StarbridgeWaitingPhase;
  label: string;
  title: string;
  detail: string;
};

export type RuntimeWaitingReplayState = {
  status: { type: string; activeFlags?: string[] };
  activity?: RuntimeActivityState;
  diff?: RuntimeDiffSummary;
};

function zh(locale: LocaleCode) {
  return locale === "zh-CN";
}

function compactLine(value: string | undefined | null, limit = 88) {
  const compact = String(value ?? "").replace(/\s+/g, " ").trim();
  if (!compact) return "";
  if (compact.length <= limit) return compact;
  return `${compact.slice(0, limit).trimEnd()}...`;
}

function firstDetailLine(detail: string | undefined) {
  return String(detail ?? "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find(Boolean) ?? "";
}

function previewText(activity: RuntimeActivityState | undefined) {
  return compactLine(activity?.preview || firstDetailLine(activity?.detail) || activity?.label);
}

function routeText(locale: LocaleCode, routeLabel: string | undefined) {
  const cleanRoute = compactLine(routeLabel, 72);
  if (!cleanRoute) return "";
  return zh(locale) ? `当前路由 · ${cleanRoute}` : `Current route · ${cleanRoute}`;
}

function formatFileDetail(locale: LocaleCode, diff: RuntimeDiffSummary | undefined) {
  if (!diff) return "";
  const fileNames = (diff.file_paths ?? []).map((file) => shortenActivityPath(file)).filter(Boolean);
  const fileSummary = fileNames.slice(0, 2).join(", ");
  const countSummary = zh(locale)
    ? `${diff.files} 个文件 · +${diff.added} -${diff.deleted}`
    : `${diff.files} files · +${diff.added} -${diff.deleted}`;
  return [fileSummary, countSummary].filter(Boolean).join(" · ");
}

function classifyToolLikePhase(activity: RuntimeActivityState | undefined) {
  const haystack = `${activity?.label ?? ""}\n${activity?.preview ?? ""}\n${activity?.detail ?? ""}`.toLowerCase();
  if (
    activity?.kind === "browser" ||
    haystack.includes("browser") ||
    haystack.includes("astrabridge_web_") ||
    haystack.includes("web_search") ||
    haystack.includes("sources:") ||
    haystack.includes("http://") ||
    haystack.includes("https://") ||
    haystack.includes("research")
  ) {
    return "web" as const;
  }
  if (
    activity?.kind === "compact" ||
    activity?.kind === "fork" ||
    activity?.kind === "review" ||
    haystack.includes("checkpoint") ||
    haystack.includes("handoff") ||
    haystack.includes("restore")
  ) {
    return "automation" as const;
  }
  return "tools" as const;
}

function phaseFromActivity(activity: RuntimeActivityState | undefined, diff: RuntimeDiffSummary | undefined, waitingOnApproval: boolean) {
  if (waitingOnApproval) return "approval" as const;
  if (activity?.kind) {
    if (activity.kind === "file_change" || activity.kind === "file_edit") return "files" as const;
    if (activity.kind === "thinking") return "thinking" as const;
    if (activity.kind === "web" || activity.kind === "web_search" || activity.kind === "browser") return "web" as const;
    if (activity.kind === "compact" || activity.kind === "fork" || activity.kind === "review") return "automation" as const;
    if (activity.kind === "mcp" || activity.kind === "tool" || activity.kind === "command" || activity.kind === "multimodal") {
      return classifyToolLikePhase(activity);
    }
  }
  if (diff) return "files" as const;
  return "thinking" as const;
}

function phaseLabel(locale: LocaleCode, phase: StarbridgeWaitingPhase) {
  if (zh(locale)) {
    if (phase === "approval") return "等待审批";
    if (phase === "files") return "正在编辑";
    if (phase === "web") return "正在联网";
    if (phase === "automation") return "正在推进";
    if (phase === "tools") return "正在调用工具";
    return "正在思考";
  }
  if (phase === "approval") return "Waiting for approval";
  if (phase === "files") return "Editing";
  if (phase === "web") return "Using web";
  if (phase === "automation") return "Advancing";
  if (phase === "tools") return "Calling tools";
  return "Thinking";
}

function phaseTitle(locale: LocaleCode, phase: StarbridgeWaitingPhase, activity: RuntimeActivityState | undefined, diff: RuntimeDiffSummary | undefined, sending: boolean) {
  if (phase === "approval") return zh(locale) ? "等待你的审批" : "Waiting for your approval";
  if (phase === "files") {
    if (diff?.files) {
      return zh(locale) ? `正在编辑 ${diff.files} 个文件` : `Editing ${diff.files} file${diff.files === 1 ? "" : "s"}`;
    }
    return zh(locale) ? "正在修改项目文件" : "Editing project files";
  }
  if (phase === "web") return zh(locale) ? "正在联网收集证据" : "Collecting web evidence";
  if (phase === "automation") return zh(locale) ? "正在推进自动化步骤" : "Advancing automation";
  if (phase === "tools") {
    if (activity?.kind === "multimodal") {
      return zh(locale) ? "正在处理多模态输入" : "Handling multimodal input";
    }
    return zh(locale) ? "正在调用本地工具" : "Calling local tools";
  }
  if (sending) return zh(locale) ? "正在准备下一轮" : "Preparing the next turn";
  return zh(locale) ? "正在思考下一步" : "Thinking through the next step";
}

function phaseDetail(
  locale: LocaleCode,
  phase: StarbridgeWaitingPhase,
  routeLabel: string | undefined,
  activity: RuntimeActivityState | undefined,
  diff: RuntimeDiffSummary | undefined,
) {
  const preview = phase === "files" ? formatFileDetail(locale, diff) : previewText(activity);
  const route = routeText(locale, routeLabel);
  if (phase === "approval") {
    return [preview || (zh(locale) ? "系统已暂停，等待你确认下一步。" : "The runtime is paused until you confirm the next action."), route]
      .filter(Boolean)
      .join(" · ");
  }
  return [preview, route].filter(Boolean).join(" · ");
}

export function resolveRuntimeWaitingState({
  locale,
  routeLabel,
  liveActivity,
  liveDiff,
  waitingOnApproval,
  activeStatusType,
  startPending = false,
  createThreadPending = false,
  creatingTaskName,
}: RuntimeWaitingInputs): RuntimeWaitingDescriptor {
  if (creatingTaskName) {
    return {
      phase: "thinking",
      label: zh(locale) ? "新任务" : "New task",
      title: zh(locale) ? "正在创建新任务" : "Creating new task",
      detail: zh(locale)
        ? `${compactLine(creatingTaskName, 72)}。完成前，输入仍会保留在当前任务。`
        : `${compactLine(creatingTaskName, 72)}. Input remains in the current task until creation finishes.`,
    };
  }
  const sending = startPending || createThreadPending;
  const phase = phaseFromActivity(liveActivity, liveDiff, waitingOnApproval);
  return {
    phase,
    label: `${zh(locale) ? "实时运行" : "Live run"} · ${phaseLabel(locale, phase)}`,
    title: phaseTitle(locale, phase, liveActivity, liveDiff, sending || activeStatusType === "pending"),
    detail: phaseDetail(locale, phase, routeLabel, liveActivity, liveDiff),
  };
}

export function buildRuntimeWaitingReplayState(phase: StarbridgeWaitingPhase, locale: LocaleCode): RuntimeWaitingReplayState {
  if (phase === "approval") {
    return {
      status: { type: "active", activeFlags: ["waitingOnApproval"] },
      activity: {
        kind: "mcp",
        label: zh(locale) ? "正在等待工具审批" : "Waiting for tool approval",
        status: "active",
        preview: "filesystem.read_file · approval required",
      },
    };
  }
  if (phase === "files") {
    return {
      status: { type: "active", activeFlags: [] },
      diff: {
        files: 2,
        added: 14,
        deleted: 5,
        file_paths: [
          "apps/astrabridge-desktop/src/App.tsx",
          "apps/astrabridge-desktop/src/features/brand/runtimeWaitingState.ts",
        ],
        detail: "apps/astrabridge-desktop/src/App.tsx\napps/astrabridge-desktop/src/features/brand/runtimeWaitingState.ts",
      },
    };
  }
  if (phase === "web") {
    return {
      status: { type: "active", activeFlags: [] },
      activity: {
        kind: "web_search",
        label: zh(locale) ? "正在联网搜索" : "Searching the web",
        status: "active",
        preview: "sources: 3 · docs.openai.com · github.com · example.com",
      },
    };
  }
  if (phase === "automation") {
    return {
      status: { type: "active", activeFlags: [] },
      activity: {
        kind: "compact",
        label: zh(locale) ? "正在推进自动化恢复" : "Advancing automation recovery",
        status: "active",
        preview: "checkpoint recovery · restore lane",
      },
    };
  }
  if (phase === "tools") {
    return {
      status: { type: "active", activeFlags: [] },
      activity: {
        kind: "tool",
        label: zh(locale) ? "正在调用工具" : "Calling a tool",
        status: "active",
        preview: "functions.shell_command · npm test src/features/brand",
      },
    };
  }
  return {
    status: { type: "active", activeFlags: [] },
    activity: {
      kind: "thinking",
      label: zh(locale) ? "正在思考" : "Thinking",
      status: "active",
      preview: zh(locale) ? "正在准备下一步修复。" : "Preparing the next repair step.",
    },
  };
}
