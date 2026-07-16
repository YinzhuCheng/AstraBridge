import type { RouterModelEntry } from "../../types";

export type ImageAttachmentRouteState = "ready" | "model_unsupported" | "runtime_unverified";

export function imageAttachmentRouteState({
  hasImageAttachments,
  model,
}: {
  hasImageAttachments: boolean;
  model: Pick<RouterModelEntry, "input_modalities" | "modality_limits"> | null | undefined;
}): ImageAttachmentRouteState {
  if (!hasImageAttachments) return "ready";
  if (!model?.input_modalities?.includes("image")) return "model_unsupported";
  const runtimeStatus = String(model.modality_limits?.app_server_image_input_status ?? "unverified").trim().toLowerCase();
  return runtimeStatus === "verified" ? "ready" : "runtime_unverified";
}
