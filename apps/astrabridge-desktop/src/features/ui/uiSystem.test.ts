import { describe, expect, it } from "vitest";

import { UI_DENSITY_TOKENS, UI_PRIMITIVE_CLASS_NAMES, uiPrimitiveClassNames } from "./uiSystem";

describe("UI system contract", () => {
  it("keeps compact geometry and typography tokens explicit", () => {
    expect(UI_DENSITY_TOKENS.geometry.controlHeight).toBe("2.125rem");
    expect(UI_DENSITY_TOKENS.geometry.surfaceRadius).toBe("8px");
    expect(UI_DENSITY_TOKENS.typography.body).toBe("0.875rem");
  });

  it("exposes stable class names for shared primitives", () => {
    expect(uiPrimitiveClassNames("flatSection", "denseList")).toBe("flat-section dense-list");
    expect(UI_PRIMITIVE_CLASS_NAMES.tooltip).toBe("ui-tooltip");
  });
});
