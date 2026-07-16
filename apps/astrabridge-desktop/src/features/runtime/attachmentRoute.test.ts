import { describe, expect, it } from "vitest";

import { imageAttachmentRouteState } from "./attachmentRoute";

describe("imageAttachmentRouteState", () => {
  it("allows image attachments only after the App Server route is verified", () => {
    expect(imageAttachmentRouteState({
      hasImageAttachments: true,
      model: { input_modalities: ["text", "image"], modality_limits: { app_server_image_input_status: "verified" } },
    })).toBe("ready");
  });

  it("fails closed when provider metadata advertises images but the App Server transport is unverified", () => {
    expect(imageAttachmentRouteState({
      hasImageAttachments: true,
      model: { input_modalities: ["text", "image"], modality_limits: {} },
    })).toBe("runtime_unverified");
  });

  it("rejects image attachments for text-only models", () => {
    expect(imageAttachmentRouteState({
      hasImageAttachments: true,
      model: { input_modalities: ["text"], modality_limits: {} },
    })).toBe("model_unsupported");
  });
});
