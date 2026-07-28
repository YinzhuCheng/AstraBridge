import type { RouterModelEntry, RuntimeRouteAdmission } from "../../types";

export type RouteAdmissionTone = "ok" | "warning" | "danger" | "info";

export type ModelRouteAdmissionState = {
  status: string;
  label: string;
  tone: RouteAdmissionTone;
  sendBlocked: boolean;
  requiresConfirmation: boolean;
  notice: string;
};

export type RouteAdmissionCopy = {
  title: string;
  badge: string;
  tone: RouteAdmissionTone;
  summary: string;
  reasons: string[];
  canContinue: boolean;
  continueLabel: string;
  cancelLabel: string;
  effectiveLine: string;
  fallbackLine: string | null;
};

function text(value: unknown) {
  return String(value ?? "").trim();
}

function routeLabel(locale: "en" | "zh-CN", status: string) {
  const labels: Record<string, [string, string]> = {
    default_eligible: ["Default-ready route", "可作为默认线路"],
    verified_non_default: ["Verified non-default route", "已验证的非默认线路"],
    tool_contract_only: ["Reduced-authority route", "降级权限线路"],
    review_only: ["Preview / review route", "预览 / 审阅线路"],
    blocked: ["Blocked route", "已阻止线路"],
    disabled: ["Disabled route", "已禁用线路"],
    legacy_unqualified: ["Unqualified compatibility route", "未认证兼容线路"],
  };
  const pair = labels[status] ?? ["Route status unknown", "线路状态未知"];
  return locale === "zh-CN" ? pair[1] : pair[0];
}

export function modelRouteAdmissionState(model: Pick<RouterModelEntry,
  "execution_route_status" |
  "execution_route_warning" |
  "execution_route_default_eligible" |
  "codex_agent_enabled" |
  "authority_tier"
> | null | undefined, locale: "en" | "zh-CN" = "en"): ModelRouteAdmissionState | null {
  if (!model) return null;
  const status = text(model.execution_route_status).toLowerCase() || "not_recorded";
  const agentDisabled = model.codex_agent_enabled === false || text(model.authority_tier).toUpperCase() === "D";
  if (agentDisabled || ["blocked", "disabled", "rejected", "unavailable"].includes(status)) {
    return {
      status,
      label: routeLabel(locale, "blocked"),
      tone: "danger",
      sendBlocked: true,
      requiresConfirmation: false,
      notice: text(model.execution_route_warning) || "This model is blocked from AstraBridge agent execution.",
    };
  }
  if (status === "default_eligible" && model.execution_route_default_eligible) {
    return {
      status,
      label: routeLabel(locale, "default_eligible"),
      tone: "ok",
      sendBlocked: false,
      requiresConfirmation: false,
      notice: "",
    };
  }
  if (status === "verified_non_default") {
    return {
      status,
      label: routeLabel(locale, "verified_non_default"),
      tone: "info",
      sendBlocked: false,
      requiresConfirmation: false,
      notice: text(model.execution_route_warning) || "This route is verified for explicit selection, but it is not eligible as the project default.",
    };
  }
  if (status === "tool_contract_only") {
    return {
      status,
      label: routeLabel(locale, "tool_contract_only"),
      tone: "warning",
      sendBlocked: false,
      requiresConfirmation: true,
      notice: text(model.execution_route_warning) || "This route can review or propose, but it is not verified for autonomous coding tools.",
    };
  }
  return {
    status,
    label: routeLabel(locale, "review_only"),
    tone: "warning",
    sendBlocked: false,
    requiresConfirmation: true,
    notice: text(model.execution_route_warning) || "This model is documented but its exact execution route remains review-only until evidence is verified.",
  };
}

export function routeAdmissionCopy(
  admission: RuntimeRouteAdmission,
  locale: "en" | "zh-CN",
): RouteAdmissionCopy {
  const status = text(admission.status).toLowerCase() || "blocked";
  const routeStatus = text(admission.route?.admission).toLowerCase() || status;
  const blocked = status === "blocked";
  const requiresConfirmation = status === "confirmation_required";
  const effective = admission.effective ?? {};
  const reasons = (admission.degradation?.reasons ?? [])
    .map((reason) => text(reason.message))
    .filter(Boolean);
  const fallbackTargets = admission.fallback?.target_models ?? [];
  const effectiveLine = locale === "zh-CN"
    ? `有效模式：${text(effective.execution_driver) || "unknown"} · 工具策略 ${text(effective.execution_policy) || "unknown"} · 权限 ${text(effective.permission_mode) || "unknown"}`
    : `Effective mode: ${text(effective.execution_driver) || "unknown"} · tools ${text(effective.execution_policy) || "unknown"} · permissions ${text(effective.permission_mode) || "unknown"}`;
  const fallbackLine = fallbackTargets.length > 0
    ? locale === "zh-CN"
      ? `可选备用模型：${fallbackTargets.join("、")}。系统不会自动替换你选择的模型。`
      : `Available fallback models: ${fallbackTargets.join(", ")}. AstraBridge will not switch models automatically.`
    : null;

  if (blocked) {
    return {
      title: locale === "zh-CN" ? "该执行线路已被阻止" : "This execution route is blocked",
      badge: routeLabel(locale, "blocked"),
      tone: "danger",
      summary: locale === "zh-CN"
        ? "AstraBridge 没有启动 provider，也没有改写你的模型选择。请改用支持所需能力的模型或完成该线路的验证。"
        : "AstraBridge did not start the provider or change your model selection. Choose a route that supports the requested capability or complete route verification.",
      reasons,
      canContinue: false,
      continueLabel: "",
      cancelLabel: locale === "zh-CN" ? "返回并选择模型" : "Back to model selection",
      effectiveLine,
      fallbackLine,
    };
  }

  return {
    title: locale === "zh-CN" ? "确认以降级线路继续" : "Confirm reduced-authority route",
    badge: routeLabel(locale, routeStatus),
    tone: "warning",
    summary: locale === "zh-CN"
      ? "会保留你选择的模型，但本轮会以只读、无工具的审阅模式启动；不会自动切换到其他模型。"
      : "Your selected model is preserved, but this turn will run in read-only, no-tools review mode; AstraBridge will not switch to another model automatically.",
    reasons,
    canContinue: requiresConfirmation || status === "admitted",
    continueLabel: locale === "zh-CN" ? "以审阅模式继续" : "Continue in review mode",
    cancelLabel: locale === "zh-CN" ? "返回并选择模型" : "Back to model selection",
    effectiveLine,
    fallbackLine,
  };
}
