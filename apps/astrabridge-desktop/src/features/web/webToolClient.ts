import type {
  WebFetchRequest,
  WebFetchResponse,
  WebResearchBriefRequest,
  WebResearchBriefResponse,
  WebSearchBatchRequest,
  WebSearchBatchResponse,
} from "../../types";

export type WebToolTransport<TResponse> = (path: string, payload: Record<string, unknown>) => Promise<TResponse>;

export type WebToolRequestState<TPayload extends Record<string, unknown>> =
  | { enabled: true; payload: TPayload }
  | { enabled: false; reason: string };

function cleanString(value: string | null | undefined) {
  return String(value ?? "").trim();
}

function cleanStringList(values: string[] | null | undefined) {
  return (values ?? []).map((value) => cleanString(value)).filter(Boolean);
}

export function buildWebSearchBatchRequest(payload: WebSearchBatchRequest): WebToolRequestState<Record<string, unknown>> {
  const queries = (payload.queries ?? [])
    .map((query) => ({
      query: cleanString(query.query),
      max_results: query.max_results,
      domains: cleanStringList(query.domains),
      exclude_domains: cleanStringList(query.exclude_domains),
    }))
    .filter((query) => query.query);
  if (queries.length === 0) {
    return { enabled: false, reason: "At least one non-empty search query is required." };
  }
  return {
    enabled: true,
    payload: {
      queries,
      dedupe: payload.dedupe ?? true,
      timeout_sec: payload.timeout_sec,
      tool_context: payload.tool_context,
    },
  };
}

export function buildWebResearchBriefRequest(payload: WebResearchBriefRequest): WebToolRequestState<Record<string, unknown>> {
  const researchGoal = cleanString(payload.research_goal);
  if (!researchGoal) {
    return { enabled: false, reason: "Research goal is required." };
  }
  return {
    enabled: true,
    payload: {
      research_goal: researchGoal,
      queries: cleanStringList(payload.queries),
      source_urls: cleanStringList(payload.source_urls),
      search_top_k: payload.search_top_k,
      fetch_top_n: payload.fetch_top_n,
      max_chars_per_source: payload.max_chars_per_source,
      timeout_sec: payload.timeout_sec,
      tool_context: payload.tool_context,
    },
  };
}

export function buildWebFetchRequest(payload: WebFetchRequest): WebToolRequestState<Record<string, unknown>> {
  const url = cleanString(payload.url);
  if (!url) {
    return { enabled: false, reason: "URL is required." };
  }
  return {
    enabled: true,
    payload: {
      url,
      max_chars: payload.max_chars,
      timeout_sec: payload.timeout_sec,
      tool_context: payload.tool_context,
    },
  };
}

export async function requestWebSearchBatch(
  transport: WebToolTransport<WebSearchBatchResponse>,
  payload: WebSearchBatchRequest,
): Promise<WebSearchBatchResponse> {
  const request = buildWebSearchBatchRequest(payload);
  if (!request.enabled) throw new Error(request.reason);
  return transport("/api/tools/web/search-batch", request.payload);
}

export async function requestWebResearchBrief(
  transport: WebToolTransport<WebResearchBriefResponse>,
  payload: WebResearchBriefRequest,
): Promise<WebResearchBriefResponse> {
  const request = buildWebResearchBriefRequest(payload);
  if (!request.enabled) throw new Error(request.reason);
  return transport("/api/tools/web/research-brief", request.payload);
}

export async function requestWebFetch(
  transport: WebToolTransport<WebFetchResponse>,
  payload: WebFetchRequest,
): Promise<WebFetchResponse> {
  const request = buildWebFetchRequest(payload);
  if (!request.enabled) throw new Error(request.reason);
  return transport("/api/tools/web/fetch", request.payload);
}
