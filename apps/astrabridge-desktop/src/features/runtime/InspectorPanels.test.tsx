import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api";
import type { ProjectFile, ProjectFilePreview, ProjectFilesTree, ProjectReviewDiff, ProjectReviewStatus } from "../../types";
import {
  BrowserInspectorPanel,
  FilesInspectorPanel,
  ReviewInspectorPanel,
  WorkflowEvidencePanel,
} from "./InspectorPanels";
import { browserStageAspectRatio, desiredBrowserLayoutMode, shouldUseBrowserTwoPageStack } from "./browserLayout";
import type { TaskWorkflowFacts } from "./taskWorkflowFacts";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const project = {
  workspace_root: "D:/AstraBridge",
} as ProjectFile;

function renderBrowserPanel(
  patch: Partial<ComponentProps<typeof BrowserInspectorPanel>> = {},
) {
  render(
    <BrowserInspectorPanel
      locale="zh-CN"
      supervisor={undefined}
      latestSmoke={null}
      statusLabel={(value) => (value === "pass" ? "pass" : value || "not run")}
      onPrepareWorkflowDemo={vi.fn()}
      onPrepareNativeKernelDemo={vi.fn()}
      onRunReleaseSmoke={vi.fn()}
      onRunProviderSwitchSmoke={vi.fn()}
      onRunNativeKernelSmoke={vi.fn()}
      {...patch}
    />,
  );
}

function renderFilesPanel(
  preview: ProjectFilePreview | undefined,
  mediaUrl?: string,
  patch: Partial<ComponentProps<typeof FilesInspectorPanel>> = {},
) {
  const tree: ProjectFilesTree = {
    workspace_root: "D:/AstraBridge",
    items: preview
      ? [
          {
            path: preview.path,
            name: preview.name,
            kind: preview.kind,
            size: preview.size,
            updated_at: preview.updated_at,
          },
        ]
      : [],
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
      selectedPath={preview?.path}
      onQueryChange={vi.fn()}
      onSelectPath={vi.fn()}
      {...patch}
    />,
  );
}

function workflowFacts(patch: Partial<TaskWorkflowFacts> = {}): TaskWorkflowFacts {
  return {
    laneCount: 2,
    handoffCount: 1,
    checkpointCount: 0,
    commandCount: 0,
    diagnosticCount: 0,
    failedCommandCount: 0,
    recoveredCommandCount: 0,
    backend: "app_server",
    checkpointRefs: [],
    commandRefs: [],
    diagnosticRefs: [],
    ...patch,
  };
}

function reviewStatus(): ProjectReviewStatus {
  return {
    workspace_root: "D:/AstraBridge",
    git: {
      is_repo: true,
      branch: "codex/review-panel",
      changed_files: 3,
      added: 1,
      deleted: 1,
    },
    files: [
      { path: "src/older.ts", status: "modified", updated_at: 10 },
      { path: "src/newer.ts", status: "modified", updated_at: 30 },
      { path: "src/middle.ts", status: "modified", updated_at: 20 },
    ],
    updated_at: "2026-06-27T00:00:00Z",
  };
}

function reviewDiff(): ProjectReviewDiff {
  return {
    ok: true,
    path: "src/newer.ts",
    diff: "diff --git a/src/newer.ts b/src/newer.ts\n--- a/src/newer.ts\n+++ b/src/newer.ts\n@@ -1,2 +1,2 @@\n const keep = true;\n-oldValue();\n+newValue();",
  };
}

describe("InspectorPanels", () => {
  it("chooses mobile browser layout for tall right-pane surfaces before falling back to a two-page stack", () => {
    expect(browserStageAspectRatio(420, 900)).toBeCloseTo(2.14, 2);
    expect(desiredBrowserLayoutMode({ isRemote: true, width: 420, height: 900 })).toBe("mobile");
    expect(desiredBrowserLayoutMode({ isRemote: true, width: 900, height: 520 })).toBe("desktop");
    expect(desiredBrowserLayoutMode({ isRemote: false, width: 420, height: 900 })).toBe("desktop");

    expect(
      shouldUseBrowserTwoPageStack({
        isRemote: true,
        desiredMode: "mobile",
        aspect: 2.2,
        mobileOptimized: false,
        responsiveFitScore: 48,
        hasPeer: true,
      }),
    ).toBe(true);
    expect(
      shouldUseBrowserTwoPageStack({
        isRemote: true,
        desiredMode: "mobile",
        aspect: 2.2,
        mobileOptimized: false,
        responsiveFitScore: 82,
        hasPeer: true,
      }),
    ).toBe(false);
  });

  it("opens a managed browser session and uses a live frame when the site can render inline", async () => {
    const session = {
      id: "ab-browser-example",
      role: "Example",
      title: "AstraBridge Browser - Example",
      url: "https://example.com/",
      status: "open",
      error: null,
      preview_mode: "remote",
      viewport_width: 1365,
      viewport_height: 900,
      updated_at: "2026-06-28T00:00:00Z",
      page_title: "Example Domain",
    } as const;
    vi.spyOn(api, "browserList").mockResolvedValueOnce([]).mockResolvedValueOnce([session]);
    vi.spyOn(api, "browserCreate").mockResolvedValueOnce(session);

    renderBrowserPanel();

    fireEvent.change(screen.getByTestId("browser-address-input"), { target: { value: "example.com" } });
    fireEvent.click(screen.getByTestId("browser-go-button"));

    await waitFor(() => expect(api.browserCreate).toHaveBeenCalled());
    expect(api.browserCreate).toHaveBeenCalledWith(expect.objectContaining({ url: "https://example.com/" }));
    const frame = await screen.findByTestId("browser-live-frame");
    expect(frame).toHaveAttribute("src", "https://example.com/");
    expect(screen.queryByTestId("browser-remote-snapshot-surface")).not.toBeInTheDocument();
    expect(screen.getByTestId("browser-workbench")).toHaveTextContent("Example Domain");
    expect(screen.getByTestId("browser-canvas-bar")).toHaveTextContent("Example Domain");
    expect(screen.getByTestId("browser-toolbar-nav")).toBeInTheDocument();
  });

  it("syncs the address bar to the effective mobile entry URL returned by the workbench", async () => {
    const session = {
      id: "ab-browser-youtube-mobile",
      role: "YouTube",
      title: "AstraBridge Browser - YouTube",
      url: "https://m.youtube.com/results?search_query=astrabridge",
      status: "open",
      error: null,
      preview_mode: "remote",
      viewport_width: 390,
      viewport_height: 844,
      layout_mode: "mobile",
      mobile_strategy: "mobile_host_rewrite_viewport",
      updated_at: "2026-07-03T00:00:00Z",
      page_title: "YouTube",
    } as const;
    vi.spyOn(api, "browserList").mockResolvedValueOnce([]).mockResolvedValueOnce([session]);
    vi.spyOn(api, "browserCreate").mockResolvedValueOnce(session);

    renderBrowserPanel();

    fireEvent.change(screen.getByTestId("browser-address-input"), {
      target: { value: "https://www.youtube.com/results?search_query=astrabridge" },
    });
    fireEvent.click(screen.getByTestId("browser-open-button"));

    await waitFor(() => {
      expect(screen.getByTestId("browser-address-input")).toHaveValue("https://m.youtube.com/results?search_query=astrabridge");
    });

  });

  it("renders managed remote sessions as browser snapshots for frame-blocked sites", async () => {
    const session = {
      id: "ab-browser-youtube",
      role: "YouTube",
      title: "AstraBridge Browser - YouTube",
      url: "https://www.youtube.com/",
      status: "open",
      error: null,
      preview_mode: "remote",
      viewport_width: 1365,
      viewport_height: 900,
      layout_mode: "mobile",
      mobile_optimized: true,
      updated_at: "2026-06-28T00:00:00Z",
      page_title: "YouTube",
    } as const;
    vi.spyOn(api, "browserList").mockResolvedValue([session]);

    renderBrowserPanel({ locale: "en" });

    const surface = await screen.findByTestId("browser-remote-snapshot-surface");
    expect(surface).toHaveClass("mobile");
    expect(screen.getByTestId("browser-surface")).toHaveAttribute("data-mobile-strategy", "mobile");
    expect(within(surface).getByRole("img", { name: "YouTube" })).toHaveAttribute(
      "src",
      expect.stringContaining("ab-browser-youtube"),
    );
    expect(screen.getByTestId("browser-toolbar-meta")).toHaveTextContent("Responsive narrow view");
    expect(screen.getByTestId("browser-canvas-bar")).toHaveTextContent("Managed snapshot");
    expect(screen.queryByTestId("browser-live-frame")).not.toBeInTheDocument();
  });

  it("keeps the browser chrome compact for desktop remote sessions", async () => {
    const session = {
      id: "ab-browser-google",
      role: "Google",
      title: "AstraBridge Browser - Google",
      url: "https://www.google.com/search?q=astrabridge",
      status: "open",
      error: null,
      preview_mode: "remote",
      viewport_width: 1365,
      viewport_height: 900,
      layout_mode: "desktop",
      mobile_strategy: "desktop_viewport",
      updated_at: "2026-07-03T00:00:00Z",
      page_title: "Google",
    } as const;
    vi.spyOn(api, "browserList").mockResolvedValue([session]);

    renderBrowserPanel({ locale: "en" });

    await screen.findByTestId("browser-remote-snapshot-surface");
    expect(screen.queryByTestId("browser-toolbar-meta")).not.toBeInTheDocument();
  });

  it("shows the mobile-entry strategy when a known mobile host is selected", async () => {
    const session = {
      id: "ab-browser-youtube-mobile",
      role: "YouTube",
      title: "AstraBridge Browser - YouTube",
      url: "https://m.youtube.com/watch?v=test",
      status: "open",
      error: null,
      preview_mode: "remote",
      viewport_width: 390,
      viewport_height: 844,
      layout_mode: "mobile",
      mobile_strategy: "mobile_host_rewrite_viewport",
      updated_at: "2026-07-03T00:00:00Z",
      page_title: "YouTube",
    } as const;
    vi.spyOn(api, "browserList").mockResolvedValue([session]);

    renderBrowserPanel({ locale: "en" });

    const meta = await screen.findByTestId("browser-toolbar-meta");
    expect(meta).toHaveTextContent("Mobile entry");
    expect(meta).toHaveTextContent("m.youtube.com");
  });

  it("shows the canonical host for responsive mobile rendering when no dedicated mobile site exists", async () => {
    const session = {
      id: "ab-browser-mdn-mobile",
      role: "MDN",
      title: "AstraBridge Browser - MDN",
      url: "https://developer.mozilla.org/en-US/docs/Web/HTML",
      status: "open",
      error: null,
      preview_mode: "remote",
      viewport_width: 390,
      viewport_height: 844,
      layout_mode: "mobile",
      mobile_strategy: "mobile_user_agent_viewport",
      updated_at: "2026-07-03T00:00:00Z",
      page_title: "MDN Web Docs",
    } as const;
    vi.spyOn(api, "browserList").mockResolvedValue([session]);

    renderBrowserPanel({ locale: "en" });

    const meta = await screen.findByTestId("browser-toolbar-meta");
    expect(meta).toHaveTextContent("Responsive narrow view");
    expect(meta).toHaveTextContent("developer.mozilla.org");
  });

  it("renders the Google mobile embed entry as a live inline frame", async () => {
    const session = {
      id: "ab-browser-google-mobile",
      role: "Google",
      title: "AstraBridge Browser - Google",
      url: "https://www.google.com/search?q=astrabridge&igu=1",
      status: "open",
      error: null,
      preview_mode: "remote",
      viewport_width: 390,
      viewport_height: 844,
      layout_mode: "mobile",
      mobile_strategy: "mobile_host_rewrite_viewport",
      updated_at: "2026-07-03T00:00:00Z",
      page_title: "Google",
    } as const;
    vi.spyOn(api, "browserList").mockResolvedValue([session]);

    renderBrowserPanel({ locale: "en" });

    const frame = await screen.findByTestId("browser-live-frame");
    expect(frame).toHaveAttribute("src", "https://www.google.com/search?q=astrabridge&igu=1");
    expect(screen.queryByTestId("browser-remote-snapshot-surface")).not.toBeInTheDocument();
    expect(screen.getByTestId("browser-toolbar-meta")).toHaveTextContent("Mobile entry");
  });

  it("routes reload through the managed browser session instead of only reloading the iframe shell", async () => {
    const session = {
      id: "ab-browser-example-managed",
      role: "Example",
      title: "AstraBridge Browser - Example",
      url: "https://example.com/",
      status: "open",
      error: null,
      preview_mode: "remote",
      viewport_width: 1365,
      viewport_height: 900,
      layout_mode: "desktop",
      mobile_strategy: "desktop_viewport",
      updated_at: "2026-07-03T00:00:00Z",
      page_title: "Example Domain",
    } as const;
    vi.spyOn(api, "browserList").mockResolvedValue([session]);
    vi.spyOn(api, "browserAction").mockResolvedValue(session);

    renderBrowserPanel({ locale: "en" });

    await screen.findByTestId("browser-live-frame");
    fireEvent.click(screen.getByTestId("browser-reload-button"));

    await waitFor(() => expect(api.browserAction).toHaveBeenCalledWith({ id: "ab-browser-example-managed", action: "reload" }));
  });

  it("renders web fallback sessions as real iframe pages", async () => {
    const session = {
      id: "ab-browser-example",
      role: "Example",
      title: "AstraBridge Browser - Example",
      url: "https://example.com/",
      status: "web_fallback",
      error: null,
      preview_mode: "web_fallback",
      page_title: "Example Domain",
    } as const;
    vi.spyOn(api, "browserList").mockResolvedValue([session]);

    renderBrowserPanel();

    const frame = await screen.findByTestId("browser-live-frame");
    expect(frame).toHaveAttribute("src", "https://example.com/");
    expect(screen.getByTestId("browser-surface")).not.toHaveTextContent("AstraBridge WebView2");
  });

  it("renders native browser sessions as foreground windows with background supervision", async () => {
    vi.spyOn(api, "browserList").mockResolvedValue([
      {
        id: "ab-browser-youtube",
        role: "YouTube",
        title: "AstraBridge Browser - YouTube",
        url: "https://www.youtube.com/",
        status: "open",
        error: null,
        preview_mode: "native",
        supervision_status: "ready",
        screenshot_path: "PRIVATE/browser-workbench/ab-browser-youtube/frame.png",
      },
    ]);

    renderBrowserPanel({ locale: "en" });

    const nativeSurface = await screen.findByTestId("browser-native-surface");
    expect(nativeSurface).toHaveTextContent("Native browser window is open");
    expect(nativeSurface).toHaveTextContent("Supervision: ready");
    expect(within(nativeSurface).getByRole("img", { name: "Background supervision snapshot" })).toHaveAttribute(
      "src",
      expect.stringContaining("frame.png"),
    );
    expect(screen.queryByTestId("browser-live-frame")).not.toBeInTheDocument();
  });

  it("summarizes browser evidence with screenshot path and failure counts", () => {
    renderBrowserPanel({ locale: "en",
      latestSmoke: {
        label: "Step 10 browser evidence",
        status: "pass",
        url: "http://127.0.0.1:4181/",
        screenshot_path: "PRIVATE/agent-bench-dogfood/screenshots/step10-browser-supervision/browser-panel.png",
        console_errors: ["console warning"],
        request_failures: [
          { method: "GET", resource_type: "image", error_text: "404", url: "http://127.0.0.1:4181/missing.png" },
          { method: "GET", resource_type: "script", error_text: "blocked", url: "http://127.0.0.1:4181/blocked.js" },
        ],
      },
    });

    const panel = screen.getByTestId("browser-panel");
    const surface = screen.getByTestId("browser-surface");
    expect(panel.querySelector(".browser-status-chip")).toHaveTextContent("pass");
    expect(within(surface).getByTestId("browser-live-frame")).toHaveAttribute("src", "http://127.0.0.1:4181/");
    expect(screen.getByTestId("browser-canvas-bar")).toHaveTextContent("Step 10 browser evidence");
    const diagnostics = panel.querySelector(".browser-diagnostics-strip");
    expect(diagnostics).toHaveTextContent("Console: 1");
    expect(diagnostics).toHaveTextContent("Request failures: 2");
    expect(diagnostics).toHaveTextContent("Screenshot: captured");
    expect(panel.querySelector(".browser-request-preview")).toHaveTextContent("127.0.0.1:4181/missing.png");
    expect(panel.querySelector(".browser-request-preview")).toHaveTextContent("127.0.0.1:4181/blocked.js");
  });

  it("renders browser workbench errors as alerts with wrapped detail", async () => {
    vi.spyOn(api, "browserList").mockRejectedValueOnce(new Error("sidecar unavailable at D:/AstraBridge/.astrabridge/browser/session.json"));

    renderBrowserPanel({ locale: "en" });

    const alert = await screen.findByTestId("browser-workbench-error");
    expect(alert).toHaveAttribute("role", "alert");
    expect(alert).toHaveTextContent("Browser workbench error");
    expect(alert).toHaveTextContent("sidecar unavailable");
    expect(alert).toHaveTextContent("D:/AstraBridge/.astrabridge/browser/session.json");
  });

  it("keeps review file status collapsed to the latest modified file until expanded", async () => {
    const onSelectPath = vi.fn();
    render(
      <ReviewInspectorPanel
        locale="en"
        review={reviewStatus()}
        diff={reviewDiff()}
        selectedPath=""
        onSelectPath={onSelectPath}
      />,
    );

    await waitFor(() => expect(onSelectPath).toHaveBeenCalledWith("src/newer.ts"));
    const initialRows = screen.getAllByTestId("review-file-row");
    expect(initialRows).toHaveLength(1);
    expect(initialRows[0]).toHaveAttribute("title", "src/newer.ts");
    expect(screen.getByTestId("review-file-toggle")).toHaveTextContent("2 more");

    fireEvent.click(screen.getByTestId("review-file-toggle"));

    expect(screen.getAllByTestId("review-file-row")).toHaveLength(3);
    expect(screen.getByTestId("review-file-toggle")).toHaveTextContent("Collapse");
  });

  it("renders review diffs as colored hunks with old and new line numbers", () => {
    const onSelectPath = vi.fn();
    const { container } = render(
      <ReviewInspectorPanel
        locale="en"
        review={reviewStatus()}
        diff={reviewDiff()}
        selectedPath="src/newer.ts"
        onSelectPath={onSelectPath}
      />,
    );

    expect(container.querySelector(".review-diff-hunk")).toBeInTheDocument();
    expect(container.querySelector(".review-diff-add")).toHaveTextContent("newValue();");
    expect(container.querySelector(".review-diff-del")).toHaveTextContent("oldValue();");
    expect(container.querySelectorAll(".review-diff-line-no")[0]).toHaveTextContent("1");
  });

  it("renders markdown project files as a readable preview", () => {
    renderFilesPanel(
      {
        path: "notes/demo.md",
        name: "demo.md",
        kind: "markdown",
        size: 24,
        updated_at: 1,
        content: "# Heading\n\n- First item\n- Second item",
      },
      "http://127.0.0.1:8790/api/project/files/media?path=notes%2Fdemo.md",
      { locale: "en" },
    );

    expect(screen.getByText("Heading")).toBeInTheDocument();
    expect(screen.getByText("First item")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open raw" })).toHaveAttribute("href", expect.stringContaining("notes%2Fdemo.md"));
  });

  it("does not override an explicit selected file path that is outside the sidebar item list", () => {
    const onSelectPath = vi.fn();
    render(
      <FilesInspectorPanel
        locale="en"
        project={project}
        tree={{
          workspace_root: "D:/AstraBridge",
          items: [
            {
              path: "README.md",
              name: "README.md",
              kind: "markdown",
              size: 24,
              updated_at: 1,
            },
          ],
          truncated: false,
          updated_at: "2026-06-26T00:00:00Z",
        }}
        preview={{
          path: "PRIVATE/task-graph/fixture-run/report.md",
          name: "report.md",
          kind: "markdown",
          size: 32,
          updated_at: 2,
          content: "# Run summary",
        }}
        query=""
        selectedPath="PRIVATE/task-graph/fixture-run/report.md"
        onQueryChange={vi.fn()}
        onSelectPath={onSelectPath}
      />,
    );

    expect(onSelectPath).not.toHaveBeenCalled();
    expect(screen.getByText("Run summary")).toBeInTheDocument();
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

  it("renders image previews with compact path metadata and mime details", () => {
    renderFilesPanel(
      {
        path: ".astrabridge/assets/generated/sample-image.png",
        name: "sample-image.png",
        kind: "image",
        size: 1536,
        updated_at: 1,
        mime_type: "image/png",
        data_url: "data:image/png;base64,AAAA",
      },
      undefined,
      { locale: "en" },
    );

    const canvas = screen.getByTestId("file-canvas");
    expect(within(canvas).getByText("sample-image.png")).toBeInTheDocument();
    expect(within(canvas).getByText("assets/generated")).toBeInTheDocument();
    expect(within(canvas).getByText(/Image .*2 KB .*image\/png/)).toBeInTheDocument();
    expect(canvas.querySelector("img")).toHaveAttribute("src", "data:image/png;base64,AAAA");
  });

  it("shows sanitized preview errors inside the file canvas", () => {
    renderFilesPanel(undefined, undefined, {
      locale: "en",
      selectedPath: ".astrabridge/runtime_events.jsonl",
      previewError: "Only selected AstraBridge artifact files can be previewed.",
    });

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("runtime_events.jsonl");
    expect(alert).toHaveTextContent("Only selected AstraBridge artifact files can be previewed.");
    expect(alert).not.toHaveTextContent("D:/AstraBridge");
  });

  it("shows media endpoint failures for previewable pdf files without rendering an empty frame", () => {
    renderFilesPanel(
      {
        path: ".astrabridge/capabilities/preview-smoke/sample.pdf",
        name: "sample.pdf",
        kind: "pdf",
        size: 2048,
        updated_at: 1,
        mime_type: "application/pdf",
      },
      undefined,
      {
        locale: "en",
        mediaError: "Media preview is limited to 52428800 bytes.",
      },
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("sample.pdf");
    expect(alert).toHaveTextContent("Media preview is limited to 52428800 bytes.");
    expect(screen.queryByTitle("sample.pdf")).not.toBeInTheDocument();
  });

  it("prepares the managed News and YouTube browser scenario for Computer Use", async () => {
    const news = {
      id: "ab-browser-news",
      role: "News",
      title: "AstraBridge Browser - News",
      url: "https://news.google.com/search?q=%E5%AE%9E%E6%97%B6%E6%96%B0%E9%97%BB&hl=zh-CN&gl=US&ceid=US:zh-Hans",
      status: "open",
      error: null,
      preview_mode: "remote",
      page_title: "Google News",
    };
    const youtube = {
      id: "ab-browser-youtube",
      role: "YouTube",
      title: "AstraBridge Browser - YouTube",
      url: "https://www.youtube.com/",
      status: "open",
      error: null,
      preview_mode: "remote",
      page_title: "YouTube",
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

    renderBrowserPanel({ locale: "en" });
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
    expect(await screen.findByTestId("browser-cua-report")).toHaveTextContent("CUA event observed");
    expect(screen.getByTestId("browser-cua-report")).toHaveTextContent("Model comparison: current model: CUA event observed");
    expect(screen.getByTestId("browser-cua-report")).toHaveTextContent("yunwu/gpt-5.5: turn started, no CUA event yet");
    expect(screen.getAllByTestId("browser-workbench-row")).toHaveLength(2);
    expect(screen.getByTestId("browser-remote-snapshot-surface")).toBeInTheDocument();
    expect(screen.queryByTestId("browser-live-frame")).not.toBeInTheDocument();
  });

  it("keeps workflow facts compact when there are no actionable issues", () => {
    render(<WorkflowEvidencePanel locale="en" facts={workflowFacts({ laneCount: 4, handoffCount: 2, commandCount: 8 })} />);

    const panel = screen.getByTestId("workflow-evidence-panel");
    expect(panel).toHaveTextContent("Workflow is clear.");
    expect(panel).not.toHaveTextContent("Execution lanes");
    expect(panel).not.toHaveTextContent("Provider handoffs");
    expect(screen.queryByTestId("workflow-command-row")).not.toBeInTheDocument();
  });

  it("shows failed commands, checkpoints, and diagnostics as actionable workflow evidence", () => {
    render(
      <WorkflowEvidencePanel
        locale="en"
        facts={workflowFacts({
          checkpointCount: 1,
          commandCount: 2,
          diagnosticCount: 1,
          failedCommandCount: 1,
          checkpointRefs: [{ save_id: "save-1", description: "Before retry" }],
          commandRefs: [
            { command: "npm test", status: "failed", exit_code: 1 },
            { command: "npm run build", status: "completed", exit_code: 0 },
          ],
          diagnosticRefs: [{ key: "diag-1", kind: "runtime_transition", summary: "Runtime recovered" }],
        })}
      />,
    );

    expect(screen.getByTestId("workflow-command-row")).toHaveTextContent("npm test");
    expect(screen.queryByText("npm run build")).not.toBeInTheDocument();
    expect(screen.getByTestId("workflow-checkpoint-row")).toHaveTextContent("Before retry");
    expect(screen.getByTestId("workflow-diagnostic-row")).toHaveTextContent("Runtime recovered");
  });
});
