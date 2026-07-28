import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RuntimeRouteAdmission } from "../../types";
import { RouteAdmissionDialog } from "./RouteAdmissionDialog";

afterEach(() => cleanup());

const confirmationRequired: RuntimeRouteAdmission = {
  schema_version: "astrabridge-runtime-route-admission-v1",
  status: "confirmation_required",
  presentation_state: "preview_review",
  route: { admission: "review_only", default_route_eligible: false },
  effective: { execution_driver: "preview_review", execution_policy: "no_tools", permission_mode: "ask" },
  degradation: {
    requires_confirmation: true,
    reasons: [{ code: "tool_semantics_removed", message: "Tools are disabled for this unverified route." }],
  },
  fallback: { target_models: ["kimi/kimi-k4"], automatic_fallback: false },
};

describe("RouteAdmissionDialog", () => {
  it("explains the no-tools degradation and requires an explicit confirmation", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<RouteAdmissionDialog admission={confirmationRequired} locale="en" onConfirm={onConfirm} onCancel={onCancel} />);

    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    expect(screen.getByText(/read-only, no-tools review mode/i)).toBeInTheDocument();
    expect(screen.getByText(/will not switch models automatically/i)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("route-admission-confirm"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("lets the user cancel a blocked route with Escape instead of silently changing models", () => {
    const onCancel = vi.fn();
    render(
      <RouteAdmissionDialog
        admission={{
          ...confirmationRequired,
          status: "blocked",
          presentation_state: "blocked",
          degradation: { requires_confirmation: false, reasons: [{ code: "model_disabled", message: "The model is disabled." }] },
        }}
        locale="en"
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />,
    );

    expect(screen.queryByTestId("route-admission-confirm")).not.toBeInTheDocument();
    fireEvent.keyDown(screen.getByTestId("route-admission-dialog"), { key: "Escape" });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
