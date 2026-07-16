import type { TaskGraphDefinition } from "../../types";

export type TaskGraphRequestedRunIntent = {
  kind: "dry_run" | "live";
  graphId: string;
  tokenBudget: number;
  fallbackTriggered: boolean;
};

export function resolveTaskGraphRunPrecondition(args: {
  actionLabel: string;
  currentTaskGraph: TaskGraphDefinition | null | undefined;
  graphId: string | null | undefined;
  routeUnavailable: boolean;
}) {
  const actionLabel = String(args.actionLabel || "").trim() || "运行";
  if (!args.currentTaskGraph) {
    return `${actionLabel}已被阻止：当前任务图尚未加载完成。请等待任务图加载后重试。`;
  }
  if (args.routeUnavailable) {
    return `${actionLabel}已被阻止：任务图运行路由当前不可用。请刷新任务图或检查 sidecar 路由状态后重试。`;
  }
  if (!String(args.graphId || "").trim()) {
    return `${actionLabel}已被阻止：当前任务图缺少可运行的 graph id。请先保存或重新实例化任务图后重试。`;
  }
  return null;
}

export function shouldPromoteDryRunToLiveRun(options: {
  intent: TaskGraphRequestedRunIntent | null;
  dryRunGraphId: string | null | undefined;
  dryRunOverallStatus: string | null | undefined;
  liveRunPending: boolean;
}): { graphId: string; tokenBudget: number } | null {
  const intent = options.intent;
  if (!intent || intent.kind !== "live" || intent.fallbackTriggered) {
    return null;
  }
  if (options.liveRunPending) {
    return null;
  }
  const dryRunGraphId = String(options.dryRunGraphId || "").trim();
  if (!dryRunGraphId || dryRunGraphId !== intent.graphId) {
    return null;
  }
  if (String(options.dryRunOverallStatus || "").trim() !== "pass") {
    return null;
  }
  return {
    graphId: intent.graphId,
    tokenBudget: intent.tokenBudget,
  };
}

export function hasTaskGraphLiveDispatchTimedOut(options: {
  intent: TaskGraphRequestedRunIntent | null;
  optimisticRunCreatedAt: string | null | undefined;
  hasAuthoritativeActiveRun: boolean;
  timeoutMs: number;
  nowMs?: number;
}): boolean {
  const intent = options.intent;
  if (!intent || intent.kind !== "live" || options.hasAuthoritativeActiveRun) {
    return false;
  }
  if (options.timeoutMs <= 0) {
    return false;
  }
  const createdAtMs = Date.parse(String(options.optimisticRunCreatedAt ?? ""));
  if (!Number.isFinite(createdAtMs)) {
    return false;
  }
  return (options.nowMs ?? Date.now()) - createdAtMs >= options.timeoutMs;
}
