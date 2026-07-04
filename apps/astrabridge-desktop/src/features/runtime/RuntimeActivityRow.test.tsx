import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { RuntimeActivityEntry } from "../../types";
import { RuntimeActivityRow } from "./RuntimeActivityRow";

afterEach(() => {
  cleanup();
});

const fileEditEntry: RuntimeActivityEntry = {
  id: "file-edit",
  kind: "file_edit",
  status: "active",
  label: "File edit",
  preview: "QueuedInstructionQueue.tsx",
  detail: "src/features/runtime/QueuedInstructionQueue.tsx · update · +4 -3",
  files: ["D:/AstraBridge/apps/astrabridge-desktop/src/features/runtime/QueuedInstructionQueue.tsx"],
  diff: {
    files: 1,
    added: 4,
    deleted: 3,
    file_paths: ["D:/AstraBridge/apps/astrabridge-desktop/src/features/runtime/QueuedInstructionQueue.tsx"],
  },
};

describe("RuntimeActivityRow", () => {
  it("renders a compact grey activity line by default", () => {
    render(<RuntimeActivityRow locale="zh-CN" entry={fileEditEntry} />);

    expect(screen.getByTestId("runtime-activity-row")).toHaveTextContent("正在编辑");
    expect(screen.getByTestId("runtime-activity-row")).toHaveTextContent("runtime/QueuedInstructionQueue.tsx");
    expect(screen.queryByText(/src\/features\/runtime/)).not.toBeInTheDocument();
  });

  it("expands details with full paths on click", () => {
    render(<RuntimeActivityRow locale="zh-CN" entry={fileEditEntry} />);

    fireEvent.click(screen.getByRole("button", { expanded: false }));

    expect(screen.getByRole("button", { expanded: true })).toBeInTheDocument();
    expect(screen.getByText("runtime/QueuedInstructionQueue.tsx")).toHaveAttribute(
      "title",
      "D:/AstraBridge/apps/astrabridge-desktop/src/features/runtime/QueuedInstructionQueue.tsx",
    );
    expect(screen.getByText(/added: 4/)).toBeInTheDocument();
  });

  it("uses a changing diff key so line counts can animate", () => {
    const { rerender } = render(<RuntimeActivityRow locale="zh-CN" entry={fileEditEntry} />);

    expect(screen.getByTestId("runtime-activity-diff")).toHaveAttribute("data-diff-key", "1:4:3");

    rerender(
      <RuntimeActivityRow
        locale="zh-CN"
        entry={{
          ...fileEditEntry,
          diff: { ...fileEditEntry.diff!, added: 8, deleted: 5 },
        }}
      />,
    );

    expect(screen.getByTestId("runtime-activity-diff")).toHaveAttribute("data-diff-key", "1:8:5");
  });

  it("renders command completion wording in English", () => {
    render(
      <RuntimeActivityRow
        locale="en"
        entry={{
          id: "command",
          kind: "command",
          status: "completed",
          label: "Command",
          preview: "Get-Content README.md",
          detail: "README",
        }}
      />,
    );

    expect(screen.getByTestId("runtime-activity-row")).toHaveTextContent("Ran Get-Content README.md");
  });
});
