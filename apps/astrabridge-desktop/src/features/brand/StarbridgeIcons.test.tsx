import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  StarbridgeAttachIcon,
  StarbridgeBrowserIcon,
  StarbridgeCompactContextIcon,
  StarbridgePermissionAutoIcon,
  StarbridgeSendIcon,
  StarbridgeSessionIcon,
  StarbridgeTaskCreateIcon,
  StarbridgeWorkflowGoalIcon,
} from "./StarbridgeIcons";

describe("StarbridgeIcons", () => {
  afterEach(() => cleanup());

  it("renders the first-pass high-visibility icon family", () => {
    render(
      <div>
        <StarbridgeTaskCreateIcon data-testid="icon-new-task" />
        <StarbridgeSessionIcon data-testid="icon-session" />
        <StarbridgeCompactContextIcon data-testid="icon-compact" />
        <StarbridgeAttachIcon data-testid="icon-attach" />
        <StarbridgeSendIcon data-testid="icon-send" />
        <StarbridgePermissionAutoIcon data-testid="icon-auto" />
        <StarbridgeWorkflowGoalIcon data-testid="icon-goal" />
        <StarbridgeBrowserIcon data-testid="icon-browser" />
      </div>,
    );

    expect(screen.getByTestId("icon-new-task").tagName).toBe("svg");
    expect(screen.getByTestId("icon-session").tagName).toBe("svg");
    expect(screen.getByTestId("icon-compact").tagName).toBe("svg");
    expect(screen.getByTestId("icon-attach").tagName).toBe("svg");
    expect(screen.getByTestId("icon-send").tagName).toBe("svg");
    expect(screen.getByTestId("icon-auto").tagName).toBe("svg");
    expect(screen.getByTestId("icon-goal").tagName).toBe("svg");
    expect(screen.getByTestId("icon-browser").tagName).toBe("svg");
  });
});
