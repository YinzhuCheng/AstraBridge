export type SetupRouteTab =
  | "file"
  | "view"
  | "tools"
  | "runtime_overview"
  | "settings_overview"
  | "login"
  | "users"
  | "keys"
  | "providers"
  | "models"
  | "capabilities"
  | "web"
  | "health"
  | "mcp"
  | "extensions"
  | "runtime"
  | "automations"
  | "saves"
  | "dogfood"
  | "reports";

export type AbilityEntryId = "automations" | "plugins" | "skills" | "multimodal_routes" | "web";
export type AbilityEntryExtensionKind = "plugins" | "skills";
export type AbilityEntryTargetTab = Extract<SetupRouteTab, "automations" | "extensions" | "capabilities" | "web">;
export type SidebarAbilityPlacement = "primary" | "more";
export type SidebarUtilityGroupId = "settings" | "developer";

export type AbilityEntryDefinition = {
  id: AbilityEntryId;
  labelKey:
    | "sidebar_nav_automations"
    | "sidebar_nav_plugins"
    | "sidebar_nav_skills"
    | "sidebar_nav_multimodal_routes"
    | "sidebar_nav_web";
  targetTab: AbilityEntryTargetTab;
  placement: SidebarAbilityPlacement;
  extensionKind?: AbilityEntryExtensionKind;
  testId: string;
  countMode: "automation" | "plugin" | "skill" | null;
};

export type SidebarUtilityEntryDefinition = {
  id: string;
  labelKey: string;
  targetTab?: SetupRouteTab;
  action?: "archive";
  testId: string;
};

export type SidebarUtilityGroupDefinition = {
  id: SidebarUtilityGroupId;
  labelKey: "sidebar_group_settings" | "sidebar_group_developer";
  entries: SidebarUtilityEntryDefinition[];
};

export const SETUP_ROUTE_TABS: SetupRouteTab[] = [
  "file",
  "view",
  "tools",
  "runtime_overview",
  "settings_overview",
  "login",
  "users",
  "keys",
  "providers",
  "models",
  "capabilities",
  "web",
  "health",
  "mcp",
  "extensions",
  "runtime",
  "automations",
  "saves",
  "dogfood",
  "reports",
];

export const API_MANAGER_TABS: SetupRouteTab[] = ["login", "users", "keys", "providers", "models"];

export const ABILITY_ENTRY_DEFINITIONS: AbilityEntryDefinition[] = [
  {
    id: "plugins",
    labelKey: "sidebar_nav_plugins",
    targetTab: "extensions",
    placement: "primary",
    extensionKind: "plugins",
    testId: "sidebar-nav-plugins",
    countMode: "plugin",
  },
  {
    id: "automations",
    labelKey: "sidebar_nav_automations",
    targetTab: "automations",
    placement: "primary",
    testId: "sidebar-nav-automations",
    countMode: "automation",
  },
  {
    id: "skills",
    labelKey: "sidebar_nav_skills",
    targetTab: "extensions",
    placement: "more",
    extensionKind: "skills",
    testId: "sidebar-nav-skills",
    countMode: "skill",
  },
  {
    id: "multimodal_routes",
    labelKey: "sidebar_nav_multimodal_routes",
    targetTab: "capabilities",
    placement: "more",
    testId: "sidebar-nav-multimodal-routes",
    countMode: null,
  },
  {
    id: "web",
    labelKey: "sidebar_nav_web",
    targetTab: "web",
    placement: "more",
    testId: "sidebar-nav-web",
    countMode: null,
  },
];

export const SIDEBAR_UTILITY_GROUPS: SidebarUtilityGroupDefinition[] = [
  {
    id: "settings",
    labelKey: "sidebar_group_settings",
    entries: [
      { id: "providers_keys", labelKey: "provider_keys", targetTab: "login", testId: "sidebar-nav-provider-keys" },
      { id: "health", labelKey: "setup_tab_health", targetTab: "health", testId: "sidebar-nav-health" },
      { id: "archived", labelKey: "archived_threads", action: "archive", testId: "sidebar-nav-archived" },
    ],
  },
  {
    id: "developer",
    labelKey: "sidebar_group_developer",
    entries: [
      { id: "mcp", labelKey: "setup_tab_mcp", targetTab: "mcp", testId: "sidebar-nav-mcp" },
      { id: "runtime", labelKey: "setup_tab_runtime", targetTab: "runtime", testId: "sidebar-nav-runtime" },
      { id: "saves", labelKey: "setup_tab_saves", targetTab: "saves", testId: "sidebar-nav-saves" },
      { id: "reports", labelKey: "setup_tab_reports", targetTab: "reports", testId: "sidebar-nav-reports" },
      { id: "dogfood", labelKey: "setup_tab_dogfood", targetTab: "dogfood", testId: "sidebar-nav-dogfood" },
    ],
  },
];
