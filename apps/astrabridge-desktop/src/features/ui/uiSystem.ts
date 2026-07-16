export const UI_DENSITY_TOKENS = Object.freeze({
  spacing: Object.freeze({ compact: "0.25rem", control: "0.5rem", section: "0.75rem", page: "1rem" }),
  typography: Object.freeze({ meta: "0.75rem", body: "0.875rem", section: "0.9375rem", page: "1.125rem" }),
  geometry: Object.freeze({ controlHeight: "2.125rem", controlRadius: "6px", surfaceRadius: "8px" }),
});

export const UI_PRIMITIVE_CLASS_NAMES = Object.freeze({
  flatSection: "flat-section",
  denseSection: "dense-section",
  denseList: "dense-list",
  denseToolbar: "dense-toolbar",
  dialog: "ui-dialog",
  popover: "ui-popover",
  tooltip: "ui-tooltip",
  statusRow: "status-row",
});

export type UiPrimitive = keyof typeof UI_PRIMITIVE_CLASS_NAMES;

export function uiPrimitiveClassNames(...primitives: UiPrimitive[]) {
  return primitives.map((primitive) => UI_PRIMITIVE_CLASS_NAMES[primitive]).join(" ");
}
