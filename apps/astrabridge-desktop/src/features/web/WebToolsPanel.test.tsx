import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { WebResearchBriefResponse } from "../../types";
import { WebToolsPanel } from "./WebToolsPanel";

function buildResearchResponse(
  resultOverrides: Partial<WebResearchBriefResponse["result"]> = {},
  responseOverrides: Partial<Omit<WebResearchBriefResponse, "result">> = {},
): WebResearchBriefResponse {
  return {
    ok: true,
    record_id: "research-brief-base",
    tool_event_verified: true,
    tool_context: null,
    path: ".astrabridge/research/research-brief-base.json",
    ...responseOverrides,
    result: {
      tool: "astrabridge_web_research_brief",
      research_goal: "summarize astra bridge changes",
      query_plan: ["summarize astra bridge changes"],
      source_policy: {
        mode: "search_expanded",
        pinned_source_count: 0,
        hinted_source_count: 0,
        search_expansion: "enabled",
        search_result_count: 1,
      },
      search: { query_count: 1, result_count: 1, warnings: [] },
      sources: [],
      source_count: 0,
      fetched_source_count: 0,
      failures: [],
      fetch_summary: {
        requested_count: 0,
        ok_count: 0,
        failed_count: 0,
        cache_hit_count: 0,
      },
      brief: "Structured brief",
      unresolved_questions: [],
      suggested_followup_queries: [],
      citation_rule: "Use only URLs in sources, and include access_date when freshness matters.",
      evidence_kind: "source_pack_only",
      conclusion_status: "not_synthesized",
      conclusion_note:
        "This run fetched and extracted sources only. A model or user must still synthesize final claims from cited URLs.",
      ...resultOverrides,
    },
  };
}

describe("WebToolsPanel", () => {
  afterEach(() => cleanup());

  it("disables run until a query is present and renders search results with record path", async () => {
    const onSearchBatch = vi.fn(async () => ({
      ok: true,
      record_id: "search-batch-1",
      tool_event_verified: true,
      tool_context: null,
      path: ".astrabridge/research/search-batch-1.json",
      result: {
        tool: "astrabridge_web_search_batch",
        source: "duckduckgo_html_with_ranked_variants",
        query_count: 1,
        result_count: 1,
        results_by_query: [],
        merged_results: [
          {
            title: "AstraBridge latest update",
            url: "https://example.com/update",
            snippet: "Recent update summary",
          },
        ],
        warnings: [],
        note: "ok",
      },
    }));

    render(<WebToolsPanel locale="en" onSearchBatch={onSearchBatch} onResearchBrief={vi.fn()} />);

    const runButton = screen.getByRole("button", { name: "Run web search" });
    expect(runButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Query"), { target: { value: "astra bridge" } });
    expect(runButton).not.toBeDisabled();
    fireEvent.click(runButton);

    await waitFor(() => expect(onSearchBatch).toHaveBeenCalledWith({ queries: [{ query: "astra bridge" }] }));
    expect(screen.getByTestId("web-state-success-search")).toBeInTheDocument();
    expect(screen.getByText("AstraBridge latest update")).toBeInTheDocument();
    expect(screen.getByText(".astrabridge/research/search-batch-1.json")).toBeInTheDocument();
  });

  it("switches to deep research and renders conclusion, policy, and freshness evidence", async () => {
    const onResearchBrief = vi.fn(async () =>
      buildResearchResponse({
        sources: [
          {
            title: "AstraBridge notes",
            url: "https://example.com/notes",
            query: "summarize astra bridge changes",
            source_origin: "search_result",
            snippet: "Snippet",
            fetch_ok: true,
            excerpt: "Detailed excerpt",
            truncated: false,
            content_type: "text/html",
            source_host: "example.com",
            cache_hit: false,
            fetched_at: "2026-06-28T12:00:00Z",
            access_date: "2026-06-28",
            status_code: 200,
          },
        ],
        source_count: 1,
        fetched_source_count: 1,
        fetch_summary: {
          requested_count: 1,
          ok_count: 1,
          failed_count: 0,
          cache_hit_count: 0,
        },
      }),
    );

    render(<WebToolsPanel locale="en" onSearchBatch={vi.fn()} onResearchBrief={onResearchBrief} />);

    fireEvent.click(screen.getByTestId("web-mode-research"));
    fireEvent.change(screen.getByLabelText("Query"), { target: { value: "summarize astra bridge changes" } });
    fireEvent.click(screen.getByRole("button", { name: "Run deep research" }));

    await waitFor(() => expect(onResearchBrief).toHaveBeenCalledWith({ research_goal: "summarize astra bridge changes" }));
    expect(screen.getByTestId("web-state-success-research")).toBeInTheDocument();
    expect(screen.getByTestId("web-research-conclusion-card")).toHaveTextContent("Fetched source pack only");
    expect(screen.getByText("Structured brief")).toBeInTheDocument();
    expect(screen.getByText("AstraBridge notes")).toBeInTheDocument();
    expect(screen.getByText("Source policy")).toBeInTheDocument();
    expect(screen.getByText(/Search-expanded mode/)).toBeInTheDocument();
    expect(screen.getByText("Search result")).toBeInTheDocument();
    expect(screen.getByText("Accessed: 2026-06-28")).toBeInTheDocument();
    expect(screen.getByText("Host: example.com")).toBeInTheDocument();
    expect(screen.getByText(".astrabridge/research/research-brief-base.json")).toBeInTheDocument();
  });

  it("passes pinned source URLs to deep research requests", async () => {
    const onResearchBrief = vi.fn(async () =>
      buildResearchResponse(
        {
          research_goal: "summarize agent risk controls",
          query_plan: [],
          source_policy: {
            mode: "pinned_source_urls",
            pinned_source_count: 2,
            hinted_source_count: 0,
            search_expansion: "skipped",
            search_result_count: 0,
            reason: "source_urls supplied without explicit queries",
          },
          sources: [
            {
              title: "",
              url: "https://genai.owasp.org/llmrisk/llm062025-excessive-agency/",
              query: "source_urls",
              source_origin: "pinned_source_url",
              snippet: "Pinned source snippet",
              fetch_ok: true,
              excerpt: "Pinned source excerpt",
              truncated: false,
              content_type: "text/html",
              source_host: "genai.owasp.org",
              cache_hit: false,
              access_date: "2026-06-28",
              status_code: 200,
            },
          ],
          source_count: 2,
          fetched_source_count: 2,
          fetch_summary: {
            requested_count: 2,
            ok_count: 2,
            failed_count: 0,
            cache_hit_count: 0,
          },
          brief: "Pinned source brief",
        },
        { path: ".astrabridge/research/research-brief-pinned.json" },
      ),
    );

    render(<WebToolsPanel locale="en" onSearchBatch={vi.fn()} onResearchBrief={onResearchBrief} />);

    fireEvent.click(screen.getByTestId("web-mode-research"));
    fireEvent.change(screen.getByLabelText("Query"), { target: { value: "summarize agent risk controls" } });
    fireEvent.change(screen.getByLabelText("Source URLs (optional)"), {
      target: {
        value: "https://genai.owasp.org/llmrisk/llm062025-excessive-agency/\nhttps://airc.nist.gov/airmf-resources/airmf/5-sec-core/",
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run deep research" }));

    await waitFor(() =>
      expect(onResearchBrief).toHaveBeenCalledWith({
        research_goal: "summarize agent risk controls",
        source_urls: [
          "https://genai.owasp.org/llmrisk/llm062025-excessive-agency/",
          "https://airc.nist.gov/airmf-resources/airmf/5-sec-core/",
        ],
      }),
    );
    expect(screen.getByText("Pinned source brief")).toBeInTheDocument();
    expect(screen.getByText(/Pinned-source mode/)).toBeInTheDocument();
    expect(screen.getByText("Pinned source")).toBeInTheDocument();
    expect(screen.getByText("Reason: source_urls supplied without explicit queries")).toBeInTheDocument();
  });

  it("uses locale-specific placeholders in Chinese mode instead of English fallback prompts", () => {
    render(<WebToolsPanel locale="zh-CN" onSearchBatch={vi.fn()} onResearchBrief={vi.fn()} />);

    const [searchBox] = screen.getAllByRole("textbox");
    expect(searchBox).toHaveAttribute("placeholder");
    expect(searchBox.getAttribute("placeholder")).toContain("AstraBridge");
    expect(searchBox.getAttribute("placeholder")).not.toMatch(/For example/i);

    fireEvent.click(screen.getByTestId("web-mode-research"));

    const textboxes = screen.getAllByRole("textbox");
    expect(textboxes).toHaveLength(2);
    expect(textboxes[0].getAttribute("placeholder")).toContain("AstraBridge");
    expect(textboxes[0].getAttribute("placeholder")).not.toMatch(/For example/i);
    expect(textboxes[1].getAttribute("placeholder")).not.toMatch(/One public source URL/i);
    expect(screen.queryByPlaceholderText(/summarize recent astrabridge plugin/i)).not.toBeInTheDocument();
  });

  it("keeps search results out of the deep research panel before any research run", async () => {
    const onSearchBatch = vi.fn(async () => ({
      ok: true,
      record_id: "search-batch-2",
      tool_event_verified: true,
      tool_context: null,
      path: ".astrabridge/research/search-batch-2.json",
      result: {
        tool: "astrabridge_web_search_batch",
        source: "duckduckgo_html_with_ranked_variants",
        query_count: 1,
        result_count: 1,
        results_by_query: [],
        merged_results: [
          {
            title: "AstraBridge latest update",
            url: "https://example.com/update",
            snippet: "Recent update summary",
          },
        ],
        warnings: [],
        note: "ok",
      },
    }));

    render(<WebToolsPanel locale="en" onSearchBatch={onSearchBatch} onResearchBrief={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Query"), { target: { value: "astra bridge" } });
    fireEvent.click(screen.getByRole("button", { name: "Run web search" }));

    await waitFor(() => expect(onSearchBatch).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("web-mode-research"));

    expect(screen.getByText("Research result")).toBeInTheDocument();
    expect(screen.getByText("No sources yet.")).toBeInTheDocument();
    expect(screen.queryByText("AstraBridge latest update")).not.toBeInTheDocument();
    expect(screen.queryByText(".astrabridge/research/search-batch-2.json")).not.toBeInTheDocument();
  });

  it("renders object-shaped deep research briefs without crashing the panel", async () => {
    const onResearchBrief = vi.fn(async () =>
      buildResearchResponse(
        {
          brief: {
            summary: "Structured extractive brief",
            goal: "summarize astra bridge changes",
            source_extracts: [{ source_index: 1, url: "https://example.com/notes", extract: "Snippet" }],
          },
        },
        { path: ".astrabridge/research/research-brief-2.json" },
      ),
    );

    render(<WebToolsPanel locale="en" onSearchBatch={vi.fn()} onResearchBrief={onResearchBrief} />);

    fireEvent.click(screen.getByTestId("web-mode-research"));
    fireEvent.change(screen.getByLabelText("Query"), { target: { value: "summarize astra bridge changes" } });
    fireEvent.click(screen.getByRole("button", { name: "Run deep research" }));

    await waitFor(() => expect(onResearchBrief).toHaveBeenCalledWith({ research_goal: "summarize astra bridge changes" }));
    expect(screen.getByText(/Structured extractive brief/)).toBeInTheDocument();
    expect(screen.getByText("Snippet")).toBeInTheDocument();
    expect(screen.getByText("https://example.com/notes")).toBeInTheDocument();
    expect(screen.queryByText(/source_extracts/)).not.toBeInTheDocument();
    expect(screen.getByText("Fetched source pack")).toBeInTheDocument();
  });

  it("shows a running notice and keeps the last deep research result visible while refreshing", async () => {
    let resolvePending: ((value: WebResearchBriefResponse) => void) | undefined;
    const onResearchBrief = vi
      .fn()
      .mockResolvedValueOnce(
        buildResearchResponse(
          {
            research_goal: "first run",
            query_plan: ["first run"],
            brief: "First brief",
          },
          { path: ".astrabridge/research/research-brief-3.json" },
        ),
      )
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolvePending = resolve;
          }),
      );

    render(<WebToolsPanel locale="en" onSearchBatch={vi.fn()} onResearchBrief={onResearchBrief} />);

    fireEvent.click(screen.getByTestId("web-mode-research"));
    fireEvent.change(screen.getByLabelText("Query"), { target: { value: "first run" } });
    fireEvent.click(screen.getByRole("button", { name: "Run deep research" }));
    await waitFor(() => expect(screen.getByText("First brief")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Query"), { target: { value: "second run" } });
    fireEvent.click(screen.getByRole("button", { name: "Run deep research" }));

    expect(screen.getByTestId("web-state-running-research")).toBeInTheDocument();
    expect(screen.getByText("Deep research in progress")).toBeInTheDocument();
    expect(screen.getByText(/last successful result stays visible below/i)).toBeInTheDocument();
    expect(screen.getByText("First brief")).toBeInTheDocument();
    expect(screen.getByText(".astrabridge/research/research-brief-3.json")).toBeInTheDocument();

    resolvePending?.(
      buildResearchResponse(
        {
          research_goal: "second run",
          query_plan: ["second run"],
          brief: "Second brief",
        },
        { path: ".astrabridge/research/research-brief-4.json" },
      ),
    );

    await waitFor(() => expect(screen.getByText("Second brief")).toBeInTheDocument());
  });

  it("shows timeout guidance for deep research when the sidecar does not respond", async () => {
    const onResearchBrief = vi.fn(async () => {
      throw new Error("The desktop sidecar did not respond in time for /api/tools/web/research-brief. Open Runtime and verify Codex login, provider key, model, and router health.");
    });

    render(<WebToolsPanel locale="en" onSearchBatch={vi.fn()} onResearchBrief={onResearchBrief} />);

    fireEvent.click(screen.getByTestId("web-mode-research"));
    fireEvent.change(screen.getByLabelText("Query"), { target: { value: "timeout run" } });
    fireEvent.click(screen.getByRole("button", { name: "Run deep research" }));

    await waitFor(() => expect(screen.getByTestId("web-state-error-research")).toBeInTheDocument());
    expect(screen.getByText("Request timed out")).toBeInTheDocument();
    expect(screen.getByText(/did not answer in time/i)).toBeInTheDocument();
    expect(screen.getByText(/The desktop sidecar did not respond in time/)).toBeInTheDocument();
  });

  it("keeps the last deep research result visible when a retry fails", async () => {
    const onResearchBrief = vi
      .fn()
      .mockResolvedValueOnce(
        buildResearchResponse(
          {
            research_goal: "initial run",
            query_plan: ["initial run"],
            brief: "Stable brief",
          },
          { path: ".astrabridge/research/research-brief-5.json" },
        ),
      )
      .mockRejectedValueOnce(new Error("Request failed: /api/tools/web/research-brief (502)"));

    render(<WebToolsPanel locale="en" onSearchBatch={vi.fn()} onResearchBrief={onResearchBrief} />);

    fireEvent.click(screen.getByTestId("web-mode-research"));
    fireEvent.change(screen.getByLabelText("Query"), { target: { value: "initial run" } });
    fireEvent.click(screen.getByRole("button", { name: "Run deep research" }));
    await waitFor(() => expect(screen.getByText("Stable brief")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("Query"), { target: { value: "retry run" } });
    fireEvent.click(screen.getByRole("button", { name: "Run deep research" }));

    await waitFor(() => expect(screen.getByTestId("web-state-error-research")).toBeInTheDocument());
    expect(screen.getByText("Request failed")).toBeInTheDocument();
    expect(screen.getByText(/previous successful result remains visible below/i)).toBeInTheDocument();
    expect(screen.getByText("Stable brief")).toBeInTheDocument();
    expect(screen.getByText(".astrabridge/research/research-brief-5.json")).toBeInTheDocument();
    expect(screen.getByText(/Request failed: \/api\/tools\/web\/research-brief/)).toBeInTheDocument();
  });

  it("renders cache hits, fetch failures, and citation freshness details", async () => {
    const onResearchBrief = vi.fn(async () =>
      buildResearchResponse(
        {
          source_policy: {
            mode: "pinned_source_urls",
            pinned_source_count: 2,
            hinted_source_count: 0,
            search_expansion: "skipped",
            search_result_count: 0,
            reason: "source_urls supplied without explicit queries",
          },
          sources: [
            {
              title: "Pinned note",
              url: "https://example.com/good",
              query: "source_urls",
              source_origin: "pinned_source_url",
              snippet: "Snippet",
              fetch_ok: true,
              excerpt: "Cached excerpt",
              truncated: false,
              content_type: "text/html",
              source_host: "example.com",
              cache_hit: true,
              fetched_at: "2026-06-28T13:00:00Z",
              access_date: "2026-06-28",
              status_code: 200,
            },
            {
              title: "Broken source",
              url: "https://example.com/bad",
              query: "source_urls",
              source_origin: "pinned_source_url",
              snippet: "",
              fetch_ok: false,
              excerpt: "",
              truncated: false,
              content_type: "text/html",
              source_host: "example.com",
              cache_hit: false,
              access_date: "2026-06-28",
              status_code: 502,
              warning: "RuntimeError: upstream 502",
            },
          ],
          source_count: 2,
          fetched_source_count: 1,
          failures: [
            {
              url: "https://example.com/bad",
              warning: "RuntimeError: upstream 502",
              source_origin: "pinned_source_url",
              query: "source_urls",
              source_host: "example.com",
            },
          ],
          fetch_summary: {
            requested_count: 2,
            ok_count: 1,
            failed_count: 1,
            cache_hit_count: 1,
          },
        },
        { path: ".astrabridge/research/research-brief-cache-and-failure.json" },
      ),
    );

    render(<WebToolsPanel locale="en" onSearchBatch={vi.fn()} onResearchBrief={onResearchBrief} />);

    fireEvent.click(screen.getByTestId("web-mode-research"));
    fireEvent.change(screen.getByLabelText("Query"), { target: { value: "summarize agent risk controls" } });
    fireEvent.change(screen.getByLabelText("Source URLs (optional)"), {
      target: { value: "https://example.com/good\nhttps://example.com/bad" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Run deep research" }));

    await waitFor(() => expect(screen.getByTestId("web-state-success-research")).toBeInTheDocument());
    expect(screen.getByTestId("web-research-conclusion-card")).toHaveTextContent("Fetched source pack only");
    expect(screen.getByText("Cache hit")).toBeInTheDocument();
    expect(screen.getByText("Fetch failed")).toBeInTheDocument();
    expect(screen.getAllByText("Accessed: 2026-06-28").length).toBeGreaterThan(0);
    expect(screen.getByText("Reason: source_urls supplied without explicit queries")).toBeInTheDocument();
    expect(screen.getByTestId("web-research-failures")).toHaveTextContent("RuntimeError: upstream 502");
    expect(screen.getByText(/include access_date when freshness matters/i)).toBeInTheDocument();
  });
});
