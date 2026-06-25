import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api";
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

  it("prepares the managed News and YouTube browser scenario for Computer Use", async () => {
    const news = {
      id: "ab-browser-news",
      role: "News",
      title: "AstraBridge Browser - News",
      url: "https://news.google.com/search?q=%E5%AE%9E%E6%97%B6%E6%96%B0%E9%97%BB&hl=zh-CN&gl=US&ceid=US:zh-Hans",
      status: "open",
      error: null,
    };
    const youtube = {
      id: "ab-browser-youtube",
      role: "YouTube",
      title: "AstraBridge Browser - YouTube",
      url: "https://www.youtube.com/",
      status: "open",
      error: null,
    };
    vi.spyOn(api, "browserList").mockResolvedValueOnce([]).mockResolvedValueOnce([news, youtube]);
    vi.spyOn(api, "browserCreate").mockResolvedValueOnce(news).mockResolvedValueOnce(youtube);
    vi.spyOn(api, "browserTileTwoUp").mockResolvedValue([news, youtube]);
    vi.spyOn(api, "runtimeComputerUseBrowserScenario").mockResolvedValue({
      schema_version: "astrabridge-computer-use-browser-scenario-v1",
      scenario_id: "CUA_test",
      scenario: "news-video-two-window",
      generated_at: "2026-06-26T00:00:00+08:00",
      status: "model_runner_cua_observed",
      artifact_path: "D:/AstraBridge/.astrabridge/dogfood/computer-use/CUA_test.json",
      browser_targets: [],
      attempts: [
        { attempt_id: "current-model", status: "cua_event_observed" },
        { attempt_id: "yunwu-gpt-5.5", status: "turn_started_no_cua_event_yet" },
      ],
    });

    renderBrowserPanel();
    fireEvent.click(screen.getByTestId("browser-open-scenario-button"));

    await waitFor(() => {
      expect(api.browserTileTwoUp).toHaveBeenCalledWith(["ab-browser-news", "ab-browser-youtube"]);
    });
    expect(api.runtimeComputerUseBrowserScenario).toHaveBeenCalledWith({
      run_model: true,
      include_yunwu: true,
      allow_fallback_sites: true,
      max_wait_sec: 8,
    });
    expect(await screen.findByTestId("browser-cua-report")).toHaveTextContent("已观察到 CUA 事件");
    expect(screen.getByTestId("browser-cua-report")).toHaveTextContent("当前模型: 已观察到 CUA 事件");
    expect(screen.getByTestId("browser-cua-report")).toHaveTextContent("yunwu/gpt-5.5: 已启动，暂未观察到 CUA");
    expect(screen.getAllByTestId("browser-workbench-row")).toHaveLength(2);
    expect(screen.getByTestId("browser-workbench-detail")).toHaveTextContent("星桥 WebView2");
  });
});
