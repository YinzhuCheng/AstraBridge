import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { QueuedInstructionQueueItem } from "./QueuedInstructionQueue";
import { QueuedInstructionQueue, summarizeQueuedInstruction } from "./QueuedInstructionQueue";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const fileAttachment = {
  id: "a1",
  path: "D:/AstraBridge/notes.md",
  name: "notes.md",
  mimeType: "text/markdown",
  kind: "file" as const,
};

function renderQueue(patch: Partial<ComponentProps<typeof QueuedInstructionQueue>> = {}) {
  const items: QueuedInstructionQueueItem[] = [
    {
      id: "q1",
      text: "First queued instruction\nwith details",
      attachments: [],
    },
    {
      id: "q2",
      text: "",
      attachments: [fileAttachment],
    },
  ];
  const props: ComponentProps<typeof QueuedInstructionQueue> = {
    locale: "en",
    items,
    expanded: true,
    editingId: null,
    busyId: null,
    blockedId: null,
    onToggleExpanded: vi.fn(),
    onEdit: vi.fn(),
    onCancelEdit: vi.fn(),
    onSaveEdit: vi.fn(),
    onSendNow: vi.fn(),
    ...patch,
  };
  render(<QueuedInstructionQueue {...props} />);
  return props;
}

describe("QueuedInstructionQueue", () => {
  it("does not render when the queue is empty", () => {
    renderQueue({ items: [] });

    expect(screen.queryByTestId("queued-instruction-card")).not.toBeInTheDocument();
  });

  it("summarizes text, truncates long messages, and appends attachment counts", () => {
    const longItem: QueuedInstructionQueueItem = {
      id: "long",
      text: `  ${"x".repeat(90)}  \nsecond paragraph`,
      attachments: [fileAttachment],
    };

    const summary = summarizeQueuedInstruction(longItem, "en");

    expect(summary).toContain("...");
    expect(summary).toContain("+ 1 attachment");
    expect(summary.length).toBeLessThan(90);
  });

  it("renders expanded and collapsed states with an accessible toggle", () => {
    const onToggleExpanded = vi.fn();
    renderQueue({ expanded: false, onToggleExpanded });

    const card = screen.getByTestId("queued-instruction-card");
    expect(card).toHaveTextContent("Queued messages");
    expect(card).toHaveTextContent("2");
    expect(screen.queryByRole("list")).not.toBeInTheDocument();

    fireEvent.click(within(card).getByRole("button", { expanded: false }));

    expect(onToggleExpanded).toHaveBeenCalledTimes(1);
  });

  it("renders each queued item with edit and send-now icon buttons", () => {
    const onEdit = vi.fn();
    const onSendNow = vi.fn();
    renderQueue({ onEdit, onSendNow });

    expect(screen.getByText("First queued instruction")).toBeInTheDocument();
    expect(screen.getByText("Attachment message · 1 attachment")).toBeInTheDocument();

    fireEvent.click(screen.getAllByLabelText("Edit queued message")[0]);
    fireEvent.click(screen.getAllByLabelText("Send now")[1]);

    expect(onEdit).toHaveBeenCalledWith("q1");
    expect(onSendNow).toHaveBeenCalledWith("q2");
    expect(screen.getAllByTitle("Edit queued message")).toHaveLength(2);
    expect(screen.getAllByTitle("Send now")).toHaveLength(2);
  });

  it("edits a queued message inline and supports cancel", () => {
    const onSaveEdit = vi.fn();
    const onCancelEdit = vi.fn();
    renderQueue({ editingId: "q1", onSaveEdit, onCancelEdit });

    fireEvent.change(screen.getByRole("textbox", { name: "Edit queued message" }), { target: { value: "Revised instruction" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSaveEdit).toHaveBeenCalledWith("q1", "Revised instruction");

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancelEdit).toHaveBeenCalledTimes(1);
  });

  it("allows saving an attachment-only queued message with empty text", () => {
    const onSaveEdit = vi.fn();
    renderQueue({ editingId: "q2", onSaveEdit });

    fireEvent.change(screen.getByRole("textbox", { name: "Edit queued message" }), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSaveEdit).toHaveBeenCalledWith("q2", "");
  });
});
