import { describe, expect, it } from "vitest";

import {
  ABILITY_ENTRY_DEFINITIONS,
  API_MANAGER_TABS,
  SETUP_ROUTE_TABS,
  SIDEBAR_UTILITY_GROUPS,
} from "./abilityEntries";

describe("ABILITY_ENTRY_DEFINITIONS", () => {
  it("exposes the five user-facing ability entries without dogfood", () => {
    expect(ABILITY_ENTRY_DEFINITIONS.map((entry) => entry.id)).toEqual([
      "plugins",
      "automations",
      "skills",
      "multimodal_routes",
      "web",
    ]);
  });

  it("keeps plugins and automations as primary sidebar entries", () => {
    expect(ABILITY_ENTRY_DEFINITIONS.filter((entry) => entry.placement === "primary").map((entry) => entry.id)).toEqual([
      "plugins",
      "automations",
    ]);
  });

  it("moves lower-frequency abilities behind the more abilities group", () => {
    expect(ABILITY_ENTRY_DEFINITIONS.filter((entry) => entry.placement === "more").map((entry) => entry.id)).toEqual([
      "skills",
      "multimodal_routes",
      "web",
    ]);
  });

  it("routes multimodal and web entries to dedicated setup tabs", () => {
    const multimodal = ABILITY_ENTRY_DEFINITIONS.find((entry) => entry.id === "multimodal_routes");
    const web = ABILITY_ENTRY_DEFINITIONS.find((entry) => entry.id === "web");

    expect(multimodal?.targetTab).toBe("capabilities");
    expect(web?.targetTab).toBe("web");
  });

  it("limits the LLM API manager tabs to API administration", () => {
    expect(API_MANAGER_TABS).toEqual(["login", "users", "keys", "providers", "models"]);
    expect(SETUP_ROUTE_TABS.slice(0, 5)).toEqual(["file", "view", "tools", "runtime_overview", "settings_overview"]);
    expect(API_MANAGER_TABS).not.toContain("capabilities");
    expect(API_MANAGER_TABS).not.toContain("web");
    expect(API_MANAGER_TABS).not.toContain("automations");
    expect(API_MANAGER_TABS).not.toContain("mcp");
    expect(API_MANAGER_TABS).not.toContain("view");
    expect(API_MANAGER_TABS).not.toContain("file");
    expect(API_MANAGER_TABS).not.toContain("tools");
    expect(API_MANAGER_TABS).not.toContain("runtime_overview");
    expect(API_MANAGER_TABS).not.toContain("settings_overview");
    expect(API_MANAGER_TABS.every((tab) => SETUP_ROUTE_TABS.includes(tab))).toBe(true);
  });

  it("groups settings and developer entries outside the LLM manager", () => {
    expect(SIDEBAR_UTILITY_GROUPS.map((group) => group.id)).toEqual(["settings", "developer"]);
    expect(SIDEBAR_UTILITY_GROUPS.find((group) => group.id === "settings")?.entries.map((entry) => entry.id)).toEqual([
      "providers_keys",
      "health",
      "archived",
    ]);
    expect(SIDEBAR_UTILITY_GROUPS.find((group) => group.id === "developer")?.entries.map((entry) => entry.id)).toEqual([
      "mcp",
      "runtime",
      "saves",
      "reports",
      "updates",
      "dogfood",
    ]);
  });
});
