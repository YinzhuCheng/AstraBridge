import type { Profile, RouterModelEntry } from "../../types";

export type AutomationRuntimeProviderStatus = {
  provider_id: string;
  label?: string | null;
  secret_loaded: boolean;
};

export type AutomationProfileGateState =
  | {
      status: "ready";
      code: "ready";
      model: RouterModelEntry | null;
      detail: string;
    }
  | {
      status: "warn";
      code: "read_only_review_mode";
      model: RouterModelEntry | null;
      detail: string;
    }
  | {
      status: "blocked";
      code:
        | "profile_missing"
        | "model_contract_missing"
        | "runtime_secret_missing"
        | "authority_unknown"
        | "authority_requires_read_only"
        | "authority_unverified_for_tools"
        | "command_execution_unverified";
      model: RouterModelEntry | null;
      detail: string;
    };

const BLOCKED_COMMAND_EXECUTION_STATUSES = new Set([
  "partial_no_command_execution",
  "completed_without_command_execution",
]);

export function resolveAutomationProfileModel(
  profile: Profile | null | undefined,
  catalogModels: RouterModelEntry[],
): RouterModelEntry | null {
  if (!profile) return null;
  const profileId = String(profile.profile_id || "").trim();
  const providerId = String(profile.provider_id || "").trim();
  const nativeModel = String(profile.model || "").trim();
  if (!providerId || !nativeModel) return null;
  return (
    catalogModels.find((model) => String(model.adapter_profile || "").trim() === profileId) ??
    catalogModels.find(
      (model) =>
        String(model.provider || "").trim() === providerId &&
        String(model.native_model || "").trim() === nativeModel,
    ) ??
    null
  );
}

export function resolveStandaloneAutomationProfileGate(
  profile: Profile | null | undefined,
  catalogModels: RouterModelEntry[],
  permissionMode: string | null | undefined,
  runtimeProviders: AutomationRuntimeProviderStatus[] = [],
): AutomationProfileGateState {
  if (!profile) {
    return {
      status: "blocked",
      code: "profile_missing",
      model: null,
      detail: "Choose a configured runtime profile before running a standalone automation.",
    };
  }
  const providerId = String(profile.provider_id || "").trim();
  const runtimeProvider = runtimeProviders.find((provider) => String(provider.provider_id || "").trim() === providerId) ?? null;
  if (runtimeProvider && !runtimeProvider.secret_loaded) {
    return {
      status: "blocked",
      code: "runtime_secret_missing",
      model: null,
      detail:
        "This provider does not have a loaded secret in the current managed runtime. Load the provider key before running standalone automations.",
    };
  }
  const model = resolveAutomationProfileModel(profile, catalogModels);
  if (!model) {
    return {
      status: "blocked",
      code: "model_contract_missing",
      model: null,
      detail: "AstraBridge could not find an authoritative runtime contract for this profile's model.",
    };
  }
  const authorityTier = String(model.authority_tier || "").trim().toUpperCase();
  const authorityReason = String(model.authority_reason || "").trim();
  const commandExecutionStatus = String(model.command_execution_status || "").trim().toLowerCase();
  const normalizedPermission = String(permissionMode || "workspace-write").trim().toLowerCase();

  if (BLOCKED_COMMAND_EXECUTION_STATUSES.has(commandExecutionStatus)) {
    return {
      status: "blocked",
      code: "command_execution_unverified",
      model,
      detail:
        String(model.command_execution_note || "").trim() ||
        "This model has not shown reliable command execution in AstraBridge validation.",
    };
  }

  if (!authorityTier) {
    return {
      status: "blocked",
      code: "authority_unknown",
      model,
      detail: authorityReason || "This model does not have a classified automation authority tier yet.",
    };
  }

  if (authorityTier === "A") {
    return {
      status: "ready",
      code: "ready",
      model,
      detail: authorityReason || "This model can run guarded standalone automation flows.",
    };
  }

  if (authorityTier === "B") {
    if (normalizedPermission === "read-only") {
      return {
        status: "warn",
        code: "read_only_review_mode",
        model,
        detail: authorityReason || "This model should stay in review mode; read-only standalone runs remain allowed.",
      };
    }
    return {
      status: "blocked",
      code: "authority_requires_read_only",
      model,
      detail:
        authorityReason ||
        "This model is limited to review-mode automation and should not run write-capable standalone flows.",
    };
  }

  return {
    status: "blocked",
    code: "authority_unverified_for_tools",
    model,
    detail:
      authorityReason ||
      "This model has no verified structured tool-calling surface for standalone automation execution.",
  };
}
