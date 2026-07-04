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
    expect(t("zh-CN", "browser_prepare_native")).toContain("原生内核");
  });

  it("uses multimodal route wording for the capability routing surface", () => {
    expect(t("en", "setup_tab_capabilities")).toBe("Multimodal routes");
    expect(t("en", "manager_capabilities_title")).toBe("Multimodal routes");
    expect(t("zh-CN", "setup_tab_capabilities")).toBe("多模态能力路由");
    expect(t("zh-CN", "manager_capabilities_title")).toBe("多模态能力路由");
  });

  it("localizes the compact sidebar groups and API manager scope", () => {
    expect(t("en", "sidebar_more_capabilities")).toBe("More capabilities");
    expect(t("zh-CN", "sidebar_more_capabilities")).toBe("更多能力");
    expect(t("zh-CN", "sidebar_group_settings")).toBe("设置");
    expect(t("zh-CN", "sidebar_group_developer")).toBe("开发者功能");
    expect(t("zh-CN", "setup_tab_dogfood")).toBe("狗粮台账");
    expect(t("zh-CN", "provider_settings_subtitle")).toContain("模型目录");
    expect(t("zh-CN", "provider_settings_subtitle")).not.toContain("MCP");
    expect(t("zh-CN", "provider_settings_subtitle")).not.toContain("健康检查");
    expect(t("zh-CN", "manager_nav_summary")).toBe("登录、用户、API 密钥、提供方和模型。");
    expect(t("zh-CN", "manager_nav_summary")).not.toContain("运行时");
  });
});
