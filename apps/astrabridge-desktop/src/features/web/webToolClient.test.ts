import { describe, expect, it, vi } from "vitest";

import {
  buildWebSearchBatchRequest,
  requestWebFetch,
  requestWebResearchBrief,
  requestWebSearchBatch,
} from "./webToolClient";

describe("webToolClient", () => {
  it("dispatches a successful batched search request through the provided transport", async () => {
    const transport = vi.fn(async () => ({
      ok: true,
      record_id: "search-batch-123",
      tool_event_verified: true,
      tool_context: {},
      path: ".astrabridge/research/search-batch-123.json",
      result: {
        tool: "astrabridge_web_search_batch",
        source: "duckduckgo_html_with_ranked_variants",
        query_count: 1,
        result_count: 1,
        results_by_query: [],
        merged_results: [],
        warnings: [],
        note: "ok",
      },
    }));

    const response = await requestWebSearchBatch(transport, {
      queries: [{ query: "  astra bridge  " }],
    });

    expect(transport).toHaveBeenCalledWith(
      "/api/tools/web/search-batch",
      expect.objectContaining({
        queries: [expect.objectContaining({ query: "astra bridge" })],
        dedupe: true,
      }),
    );
    expect(response.record_id).toBe("search-batch-123");
  });

  it("propagates transport failures for research brief and fetch", async () => {
    const timeout = new Error("The desktop sidecar did not respond in time for /api/tools/web/research-brief.");
    const transport = vi
      .fn()
      .mockRejectedValueOnce(timeout)
      .mockRejectedValueOnce(new Error("Request failed: /api/tools/web/fetch"));

    await expect(
      requestWebResearchBrief(transport, {
        research_goal: "latest astra bridge release notes",
      }),
    ).rejects.toThrow("did not respond in time");

    await expect(
      requestWebFetch(transport, {
        url: "https://example.com",
      }),
    ).rejects.toThrow("Request failed");
  });

  it("disables empty search queries before any transport call", async () => {
    expect(buildWebSearchBatchRequest({ queries: [{ query: "   " }] })).toEqual({
      enabled: false,
      reason: "At least one non-empty search query is required.",
    });

    const transport = vi.fn();
    await expect(
      requestWebSearchBatch(transport, {
        queries: [{ query: "" }],
      }),
    ).rejects.toThrow("At least one non-empty search query is required.");
    expect(transport).not.toHaveBeenCalled();
  });
});
