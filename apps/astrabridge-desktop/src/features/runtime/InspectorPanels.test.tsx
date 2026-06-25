import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProjectFile, ProjectFilePreview, ProjectFilesTree } from "../../types";
import { BrowserInspectorPanel, FilesInspectorPanel } from "./InspectorPanels";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const project = {
  workspace_root: "D:/AstraBridge",
} as ProjectFile;

function renderBrowserPanel() {
  render(
    <BrowserInspectorPanel
      locale="zh-CN"
      supervisor={undefined}
      latestSmoke={null}
      statusLabel={(value) => value || "未运行"}
      onPrepareWorkflowDemo={vi.fn()}
      onPrepareNativeKernelDemo={vi.fn()}
      onRunReleaseSmoke={vi.fn()}
      onRunProviderSwitchSmoke={vi.fn()}
      onRunNativeKernelSmoke={vi.fn()}
    />,
  );
}

function renderFilesPanel(preview: ProjectFilePreview, mediaUrl?: string) {
  const tree: ProjectFilesTree = {
    workspace_root: "D:/AstraBridge",
    items: [
      {
        path: preview.path,
        name: preview.name,
        kind: preview.kind,
        size: preview.size,
        updated_at: preview.updated_at,
      },
    ],
    truncated: false,
    updated_at: "2026-06-26T00:00:00Z",
  };
  render(
    <FilesInspectorPanel
      locale="zh-CN"
      project={project}
      tree={tree}
      preview={preview}
      mediaUrl={mediaUrl}
      query=""
      selectedPath={preview.path}
      onQueryChange={vi.fn()}
      onSelectPath={vi.fn()}
    />,
  );
}

describe("InspectorPanels", () => {
  it("normalizes browser address input and navigates the embedded frame", () => {
    renderBrowserPanel();

    fireEvent.change(screen.getByTestId("browser-address-input"), { target: { value: "example.com" } });
    fireEvent.click(screen.getByTestId("browser-go-button"));

    expect(screen.getByTestId("browser-preview-frame").getAttribute("src")).toBe("https://example.com");
  });

  it("renders markdown project files as a readable preview", () => {
    renderFilesPanel(
      {
        path: "notes/demo.md",
        name: "demo.md",
        kind: "markdown",
        size: 24,
        updated_at: 1,
        content: "# 标题\n\n- 第一项\n- 第二项",
      },
      "http://127.0.0.1:8790/api/project/files/media?path=notes%2Fdemo.md",
    );

    expect(screen.getByText("标题")).toBeInTheDocument();
    expect(screen.getByText("第一项")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开" })).toHaveAttribute("href", expect.stringContaining("notes%2Fdemo.md"));
  });

  it("renders pdf project files through the media endpoint", () => {
    renderFilesPanel(
      {
        path: "reports/sample.pdf",
        name: "sample.pdf",
        kind: "pdf",
        size: 2048,
        updated_at: 1,
        mime_type: "application/pdf",
      },
      "http://127.0.0.1:8790/api/project/files/media?path=reports%2Fsample.pdf",
    );

    const frame = screen.getByTitle("sample.pdf");
    expect(frame.tagName).toBe("IFRAME");
    expect(frame).toHaveAttribute("src", expect.stringContaining("reports%2Fsample.pdf"));
  });
});
