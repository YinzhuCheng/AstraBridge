import { describe, expect, it } from "vitest";

import type { RouterModelEntry } from "../../types";
import { mergeComposerCatalogModels } from "./composerModelCatalog";

function buildModel(
  provider: string,
  nativeModel: string,
  patch: Partial<RouterModelEntry> = {},
): RouterModelEntry {
  return {
    id: `${provider}/${nativeModel}`,
    provider,
    native_model: nativeModel,
    display_name: nativeModel,
    enabled: true,
    advertised_context_window: 128000,
    ui_context_hint_only: true,
    adapter_profile: "default",
    ...patch,
  };
}

describe("mergeComposerCatalogModels", () => {
  it("keeps router models when the session is anonymous", () => {
    const models = mergeComposerCatalogModels(
      "anonymous",
      [buildModel("qwen", "qwen3.7-plus")],
      [buildModel("qwen", "qwen3-vl-plus")],
    );

    expect(models.map((item) => item.native_model)).toEqual(["qwen3-vl-plus"]);
  });

  it("keeps managed verified models first and appends router-only models", () => {
    const models = mergeComposerCatalogModels(
      "managed_user",
      [buildModel("qwen", "qwen3.7-plus")],
      [
        buildModel("qwen", "qwen3.7-plus", { display_name: "Qwen3.7 Plus Router" }),
        buildModel("qwen", "qwen3-vl-plus"),
        buildModel("kimi", "kimi-k2.7-code"),
      ],
    );

    expect(models.map((item) => item.native_model)).toEqual(["qwen3.7-plus", "qwen3-vl-plus", "kimi-k2.7-code"]);
    expect(models[0].display_name).toBe("qwen3.7-plus");
  });

  it("falls back to model id when provider/native fields are incomplete", () => {
    const incompleteManaged = {
      ...buildModel("qwen", "qwen3.7-plus"),
      provider: "",
      native_model: "",
    };
    const incompleteRouter = {
      ...buildModel("qwen", "qwen3-vl-plus"),
      provider: "",
      native_model: "",
    };

    const models = mergeComposerCatalogModels("managed_user", [incompleteManaged], [incompleteRouter]);

    expect(models.map((item) => item.id)).toEqual(["qwen/qwen3.7-plus", "qwen/qwen3-vl-plus"]);
  });
});
