import { describe, expect, it } from "vitest";
import { dictionaries, t } from "./catalog";

describe("i18n catalog", () => {
  it("contains router metadata setup labels for both locales", () => {
    expect(t("en", "setup_tab_metadata")).toBe("Metadata");
    expect(t("zh-CN", "setup_tab_metadata")).toBe("Metadata");
    expect(t("en", "provider_keys")).toBe("Providers & API keys");
    expect(t("zh-CN", "provider_keys")).not.toBe("provider_keys");
  });

  it("keeps English and Chinese dictionaries in parity", () => {
    expect(Object.keys(dictionaries["zh-CN"]).sort()).toEqual(Object.keys(dictionaries.en).sort());
  });

  it("does not contain mojibake sentinels in Chinese copy", () => {
    const combined = Object.values(dictionaries["zh-CN"]).join("\n");
    expect(combined).not.toMatch(/[�]|鈥|灏|鐨|绋|鎵|璺/);
  });

  it("localizes LLM Manager density copy without falling back to keys", () => {
    expect(t("en", "manager_login_summary")).toContain("Managed login");
    expect(t("zh-CN", "manager_login_summary")).toContain("托管登录");
    expect(t("zh-CN", "manager_login_summary")).not.toBe("manager_login_summary");
    expect(t("zh-CN", "browser_prepare_native")).toContain("native kernel");
  });
});
