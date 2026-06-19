import { describe, expect, it } from "vitest";
import { t } from "./catalog";

describe("i18n catalog", () => {
  it("contains router metadata setup labels for both locales", () => {
    expect(t("en", "setup_tab_metadata")).toBe("Metadata");
    expect(t("zh-CN", "setup_tab_metadata")).toBe("Metadata");
    expect(t("en", "provider_keys")).toBe("Providers & API keys");
    expect(t("zh-CN", "provider_keys")).not.toBe("provider_keys");
  });
});

