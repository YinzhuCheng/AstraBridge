import { useState } from "react";

import type {
  LocaleCode,
  WebResearchBriefResult,
  WebResearchBriefRequest,
  WebResearchBriefResponse,
  WebResearchSource,
  WebSearchBatchResponse,
} from "../../types";

type WebMode = "search" | "research";

type WebToolsPanelProps = {
  locale: LocaleCode;
  onSearchBatch: (payload: { queries: Array<{ query: string }> }) => Promise<WebSearchBatchResponse>;
  onResearchBrief: (payload: WebResearchBriefRequest) => Promise<WebResearchBriefResponse>;
};

type WebRunState =
  | {
      mode: "search";
      response: WebSearchBatchResponse;
    }
  | {
      mode: "research";
      response: WebResearchBriefResponse;
    };

type WebRunStateMap = Record<WebMode, WebRunState | null>;
type WebErrorStateMap = Record<WebMode, string>;

type WebActiveRun = {
  mode: WebMode;
  query: string;
} | null;

type FormattedResearchBrief = {
  summary: string;
  extracts: Array<{
    sourceIndex: string;
    url: string;
    extract: string;
  }>;
  raw: string;
};

type WebCopy = {
  eyebrow: string;
  title: string;
  summary: string;
  modeLabel: string;
  searchMode: string;
  researchMode: string;
  queryLabel: string;
  sourceUrlsLabel: string;
  sourceUrlsPlaceholder: string;
  sourceUrlsHint: string;
  searchPlaceholder: string;
  researchPlaceholder: string;
  runSearch: string;
  runResearch: string;
  running: string;
  searchSummaryTitle: string;
  researchSummaryTitle: string;
  recordPath: string;
  recordId: string;
  resultCount: string;
  sourceCount: string;
  fetchCount: string;
  failureCount: string;
  cacheHitCount: string;
  sourcePolicyLabel: string;
  sourcePolicyPinnedMode: string;
  sourcePolicyHintedMode: string;
  sourcePolicySearchMode: string;
  sourcePolicySkipped: string;
  sourcePolicyEnabled: string;
  sourcePolicyReason: string;
  pinnedSource: string;
  hintedSource: string;
  searchSource: string;
  fetchedStatus: string;
  cachedStatus: string;
  failedStatus: string;
  warnings: string;
  unresolved: string;
  citationRule: string;
  currentQuery: string;
  noResults: string;
  noSources: string;
  runningTitleSearch: string;
  runningTitleResearch: string;
  runningBody: string;
  staleBody: string;
  successTitleSearch: string;
  successTitleResearch: string;
  successBody: string;
  failureTitle: string;
  timeoutTitle: string;
  failureBody: string;
  timeoutBody: string;
  failureStaleBody: string;
  errorTitle: string;
  conclusionTitle: string;
  conclusionSourcePackOnly: string;
  conclusionNoteFallback: string;
  sourcePackTitle: string;
  sourcesTitle: string;
  fetchFailuresTitle: string;
  followupQueriesTitle: string;
  accessDate: string;
  hostLabel: string;
};

function copyFor(locale: LocaleCode): WebCopy {
  if (locale === "zh-CN") {
    return {
      eyebrow: "联网",
      title: "联网工具",
      summary: "Web 保持独立工具通道，不进入模型路由。这里区分普通搜索、已抓取来源包和后续结论生成，方便审计来源质量。",
      modeLabel: "模式",
      searchMode: "普通搜索",
      researchMode: "深度研究",
      queryLabel: "查询",
      sourceUrlsLabel: "来源 URL（可选）",
      sourceUrlsPlaceholder: "每行一个公开来源 URL；用于固定深度研究来源。",
      sourceUrlsHint: "固定来源会先直接抓取，再决定是否扩展广搜，减少无关来源混入。",
      searchPlaceholder: "例如：AstraBridge 最新更新",
      researchPlaceholder: "例如：总结 AstraBridge 最近的插件和能力入口变更，并明确来源日期",
      runSearch: "运行搜索",
      runResearch: "运行深度研究",
      running: "运行中...",
      searchSummaryTitle: "搜索结果",
      researchSummaryTitle: "研究结果",
      recordPath: "记录路径",
      recordId: "记录 ID",
      resultCount: "结果数",
      sourceCount: "来源数",
      fetchCount: "抓取成功",
      failureCount: "抓取失败",
      cacheHitCount: "缓存命中",
      sourcePolicyLabel: "来源策略",
      sourcePolicyPinnedMode: "固定来源模式",
      sourcePolicyHintedMode: "一方来源提示",
      sourcePolicySearchMode: "扩展搜索模式",
      sourcePolicySkipped: "已跳过广搜",
      sourcePolicyEnabled: "已启用扩展搜索",
      sourcePolicyReason: "原因",
      pinnedSource: "固定来源",
      hintedSource: "提示来源",
      searchSource: "搜索结果",
      fetchedStatus: "已抓取",
      cachedStatus: "缓存命中",
      failedStatus: "抓取失败",
      warnings: "警告",
      unresolved: "待澄清问题",
      citationRule: "引用规则",
      currentQuery: "当前查询",
      noResults: "暂无结果。",
      noSources: "暂无来源。",
      runningTitleSearch: "普通搜索进行中",
      runningTitleResearch: "深度研究进行中",
      runningBody: "请求已发出，完成后会自动刷新本面板。",
      staleBody: "下方暂时保留上一轮成功结果，方便继续查看记录路径和来源证据。",
      successTitleSearch: "普通搜索已完成",
      successTitleResearch: "深度研究已完成",
      successBody: "最新结果已保存，可继续使用记录 ID 和路径做复核。",
      failureTitle: "请求失败",
      timeoutTitle: "请求超时",
      failureBody: "可以直接调整查询后重试；如果问题持续，请检查 Runtime、网络和 sidecar 状态。",
      timeoutBody: "桌面 sidecar 在预期时间内没有返回结果。请检查 Runtime、模型和网络健康状态后重试。",
      failureStaleBody: "上一轮成功结果仍保留在下方，方便继续查看记录路径和来源证据。",
      errorTitle: "错误",
      conclusionTitle: "结论状态",
      conclusionSourcePackOnly: "当前只有来源包，没有模型综合结论",
      conclusionNoteFallback: "当前运行只抓取并提炼来源。最终结论仍需要模型或用户基于引用 URL 继续综合。",
      sourcePackTitle: "已抓取来源包",
      sourcesTitle: "来源明细",
      fetchFailuresTitle: "抓取失败",
      followupQueriesTitle: "建议后续查询",
      accessDate: "访问日期",
      hostLabel: "来源域名",
    };
  }
  return {
    eyebrow: "Web",
    title: "Web tools",
    summary: "Web stays a standalone tool lane instead of entering model-backed routing. This panel separates fetched evidence packs from any later synthesis work.",
    modeLabel: "Mode",
    searchMode: "General web search",
    researchMode: "Deep research",
    queryLabel: "Query",
    sourceUrlsLabel: "Source URLs (optional)",
    sourceUrlsPlaceholder: "One public source URL per line; used to pin deep-research sources.",
    sourceUrlsHint: "Pinned sources are fetched directly before search results, reducing broad-search spillover.",
    searchPlaceholder: "For example: latest AstraBridge updates",
    researchPlaceholder: "For example: summarize recent AstraBridge plugin and capability-entry changes with dated sources",
    runSearch: "Run web search",
    runResearch: "Run deep research",
    running: "Running...",
    searchSummaryTitle: "Search results",
    researchSummaryTitle: "Research result",
    recordPath: "Record path",
    recordId: "Record ID",
    resultCount: "Result count",
    sourceCount: "Source count",
    fetchCount: "Fetched",
    failureCount: "Failures",
    cacheHitCount: "Cache hits",
    sourcePolicyLabel: "Source policy",
    sourcePolicyPinnedMode: "Pinned-source mode",
    sourcePolicyHintedMode: "First-party hints",
    sourcePolicySearchMode: "Search-expanded mode",
    sourcePolicySkipped: "broad search skipped",
    sourcePolicyEnabled: "search expansion enabled",
    sourcePolicyReason: "Reason",
    pinnedSource: "Pinned source",
    hintedSource: "Hinted source",
    searchSource: "Search result",
    fetchedStatus: "Fetched",
    cachedStatus: "Cache hit",
    failedStatus: "Fetch failed",
    warnings: "Warnings",
    unresolved: "Unresolved questions",
    citationRule: "Citation rule",
    currentQuery: "Current query",
    noResults: "No results yet.",
    noSources: "No sources yet.",
    runningTitleSearch: "Web search in progress",
    runningTitleResearch: "Deep research in progress",
    runningBody: "The request is still running. This panel will refresh when the latest result arrives.",
    staleBody: "The last successful result stays visible below so you can keep the record path and evidence in view.",
    successTitleSearch: "Web search complete",
    successTitleResearch: "Deep research complete",
    successBody: "The latest result has been saved. Keep the record id and path for audit or follow-up.",
    failureTitle: "Request failed",
    timeoutTitle: "Request timed out",
    failureBody: "Update the query and retry, or inspect the runtime, network, and sidecar configuration if the failure continues.",
    timeoutBody: "The desktop sidecar did not answer in time. Check Runtime, model, and network health, then retry.",
    failureStaleBody: "The previous successful result remains visible below so you can keep the record path and evidence in view.",
    errorTitle: "Request failed",
    conclusionTitle: "Conclusion status",
    conclusionSourcePackOnly: "Fetched source pack only",
    conclusionNoteFallback: "This run fetched and extracted sources only. A model or user must still synthesize final claims from cited URLs.",
    sourcePackTitle: "Fetched source pack",
    sourcesTitle: "Source details",
    fetchFailuresTitle: "Fetch failures",
    followupQueriesTitle: "Suggested follow-up queries",
    accessDate: "Accessed",
    hostLabel: "Host",
  };
}

function runLabel(copy: WebCopy, mode: WebMode) {
  return mode === "search" ? copy.runSearch : copy.runResearch;
}

function resultTitle(copy: WebCopy, mode: WebMode) {
  return mode === "search" ? copy.searchSummaryTitle : copy.researchSummaryTitle;
}

function successTitle(copy: WebCopy, mode: WebMode) {
  return mode === "search" ? copy.successTitleSearch : copy.successTitleResearch;
}

function runningTitle(copy: WebCopy, mode: WebMode) {
  return mode === "search" ? copy.runningTitleSearch : copy.runningTitleResearch;
}

function classifyRequestError(message: string) {
  return /did not respond in time|timed out|timeout/i.test(message) ? "timeout" : "failure";
}

function parseSourceUrls(value: string) {
  return value
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function sourceOriginLabel(copy: WebCopy, source: WebResearchSource) {
  if (source.source_origin === "pinned_source_url" || source.query === "source_urls") {
    return copy.pinnedSource;
  }
  if (source.source_origin === "hinted_source" || source.query === "hinted_sources") {
    return copy.hintedSource;
  }
  return copy.searchSource;
}

function sourceOriginClassName(source: WebResearchSource) {
  if (source.source_origin === "pinned_source_url" || source.query === "source_urls") {
    return "web-tool-source-badge web-tool-source-badge-pinned";
  }
  if (source.source_origin === "hinted_source" || source.query === "hinted_sources") {
    return "web-tool-source-badge web-tool-source-badge-hinted";
  }
  return "web-tool-source-badge";
}

function sourceFetchStatus(copy: WebCopy, source: WebResearchSource) {
  if (!source.fetch_ok) {
    return { label: copy.failedStatus, className: "web-tool-source-badge web-tool-source-badge-failed" };
  }
  if (source.cache_hit) {
    return { label: copy.cachedStatus, className: "web-tool-source-badge web-tool-source-badge-cached" };
  }
  return { label: copy.fetchedStatus, className: "web-tool-source-badge web-tool-source-badge-fetched" };
}

function sourcePolicySummary(copy: WebCopy, result: WebResearchBriefResult) {
  const policy = result.source_policy;
  if (!policy) {
    return "";
  }
  const mode = policy.mode === "pinned_source_urls"
    ? copy.sourcePolicyPinnedMode
    : policy.mode === "hinted_first_party_sources"
      ? copy.sourcePolicyHintedMode
      : copy.sourcePolicySearchMode;
  const expansion = policy.search_expansion === "skipped" ? copy.sourcePolicySkipped : copy.sourcePolicyEnabled;
  return [
    mode,
    `${copy.pinnedSource}: ${policy.pinned_source_count ?? 0}`,
    `${copy.hintedSource}: ${policy.hinted_source_count ?? 0}`,
    `${copy.searchSource}: ${policy.search_result_count ?? 0}`,
    expansion,
  ].join(" · ");
}

function formatUnknownBriefValue(value: unknown) {
  if (typeof value === "string") {
    return value.trim();
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "";
}

function formatResearchBrief(brief: unknown, emptyLabel: string): FormattedResearchBrief {
  if (typeof brief === "string") {
    const text = brief.trim();
    return { summary: text || emptyLabel, extracts: [], raw: "" };
  }
  if (brief == null) {
    return { summary: emptyLabel, extracts: [], raw: "" };
  }
  if (typeof brief === "object") {
    const record = brief as Record<string, unknown>;
    const summary = formatUnknownBriefValue(record.summary) || formatUnknownBriefValue(record.goal) || emptyLabel;
    const extracts = Array.isArray(record.source_extracts)
      ? record.source_extracts
          .map((item, index) => {
            if (!item || typeof item !== "object") {
              return null;
            }
            const source = item as Record<string, unknown>;
            const extract = formatUnknownBriefValue(source.extract);
            const url = formatUnknownBriefValue(source.url);
            if (!extract && !url) {
              return null;
            }
            return {
              sourceIndex: formatUnknownBriefValue(source.source_index) || String(index + 1),
              url,
              extract,
            };
          })
          .filter((item): item is FormattedResearchBrief["extracts"][number] => Boolean(item))
      : [];
    return {
      summary,
      extracts,
      raw: extracts.length > 0 ? "" : JSON.stringify(brief, null, 2),
    };
  }
  try {
    return { summary: String(brief), extracts: [], raw: "" };
  } catch {
    return { summary: emptyLabel, extracts: [], raw: "" };
  }
}

function WebAuditMeta({ copy, currentRunState }: { copy: WebCopy; currentRunState: WebRunState }) {
  const items = currentRunState.mode === "search"
    ? [
        { label: copy.recordId, value: currentRunState.response.record_id },
        { label: copy.recordPath, value: currentRunState.response.path, path: true },
        { label: copy.resultCount, value: String(currentRunState.response.result.result_count) },
      ]
    : [
        { label: copy.recordId, value: currentRunState.response.record_id },
        { label: copy.recordPath, value: currentRunState.response.path, path: true },
        { label: copy.sourceCount, value: String(currentRunState.response.result.source_count) },
        {
          label: copy.fetchCount,
          value: `${currentRunState.response.result.fetch_summary?.ok_count ?? currentRunState.response.result.fetched_source_count}/${currentRunState.response.result.fetch_summary?.requested_count ?? currentRunState.response.result.source_count}`,
        },
        {
          label: copy.failureCount,
          value: String(currentRunState.response.result.fetch_summary?.failed_count ?? currentRunState.response.result.failures.length),
        },
        {
          label: copy.cacheHitCount,
          value: String(currentRunState.response.result.fetch_summary?.cache_hit_count ?? currentRunState.response.result.sources.filter((item) => item.cache_hit).length),
        },
      ];
  return (
    <dl className="web-tool-meta-strip" aria-label="Web result audit metadata">
      {items.map((item) => (
        <div className={`web-tool-meta-item ${item.path ? "web-tool-meta-path" : ""}`} key={`${item.label}-${item.value}`}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function WebToolsPanel({ locale, onSearchBatch, onResearchBrief }: WebToolsPanelProps) {
  const copy = copyFor(locale);
  const [mode, setMode] = useState<WebMode>("search");
  const [query, setQuery] = useState("");
  const [sourceUrlsText, setSourceUrlsText] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [activeRun, setActiveRun] = useState<WebActiveRun>(null);
  const [errorByMode, setErrorByMode] = useState<WebErrorStateMap>({ search: "", research: "" });
  const [runStateByMode, setRunStateByMode] = useState<WebRunStateMap>({ search: null, research: null });
  const cleanedQuery = query.trim();
  const currentRunState = runStateByMode[mode];
  const currentError = errorByMode[mode];
  const currentErrorType = classifyRequestError(currentError);
  const isCurrentModeRunning = isRunning && activeRun?.mode === mode;
  const hasCurrentModeStaleResult = isCurrentModeRunning && Boolean(currentRunState);

  async function run() {
    if (!cleanedQuery) return;
    const currentMode = mode;
    const currentQuery = cleanedQuery;
    setIsRunning(true);
    setActiveRun({ mode: currentMode, query: currentQuery });
    setErrorByMode((current) => ({ ...current, [currentMode]: "" }));
    try {
      if (currentMode === "search") {
        const response = await onSearchBatch({ queries: [{ query: currentQuery }] });
        setRunStateByMode((current) => ({ ...current, search: { mode: "search", response } }));
      } else {
        const sourceUrls = parseSourceUrls(sourceUrlsText);
        const response = await onResearchBrief({
          research_goal: currentQuery,
          ...(sourceUrls.length > 0 ? { source_urls: sourceUrls } : {}),
        });
        setRunStateByMode((current) => ({ ...current, research: { mode: "research", response } }));
      }
    } catch (nextError) {
      setErrorByMode((current) => ({
        ...current,
        [currentMode]: String((nextError as Error)?.message ?? nextError),
      }));
    } finally {
      setIsRunning(false);
      setActiveRun((current) => (current?.mode === currentMode ? null : current));
    }
  }

  return (
    <div className="manager-panel web-tools-shell" data-testid="web-tools-panel">
      <div className="manager-hero">
        <div>
          <span className="eyebrow">{copy.eyebrow}</span>
          <h3>{copy.title}</h3>
          <p className="muted">{copy.summary}</p>
        </div>
        <span className="session-badge">{mode === "search" ? copy.searchMode : copy.researchMode}</span>
      </div>
      <div className="manager-grid web-tools-layout">
        <section className="manager-section web-tool-query-pane">
          <label className="field">
            <span>{copy.modeLabel}</span>
            <div className="segmented segmented-wrap" role="group" aria-label={copy.modeLabel}>
              <button
                type="button"
                data-testid="web-mode-search"
                className={mode === "search" ? "segmented-active" : ""}
                onClick={() => setMode("search")}
              >
                {copy.searchMode}
              </button>
              <button
                type="button"
                data-testid="web-mode-research"
                className={mode === "research" ? "segmented-active" : ""}
                onClick={() => setMode("research")}
              >
                {copy.researchMode}
              </button>
            </div>
          </label>
          <label className="field">
            <span>{copy.queryLabel}</span>
            <textarea
              rows={mode === "search" ? 3 : 4}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={mode === "search" ? copy.searchPlaceholder : copy.researchPlaceholder}
            />
          </label>
          {mode === "research" ? (
            <label className="field">
              <span>{copy.sourceUrlsLabel}</span>
              <textarea
                aria-label={copy.sourceUrlsLabel}
                rows={3}
                value={sourceUrlsText}
                onChange={(event) => setSourceUrlsText(event.target.value)}
                placeholder={copy.sourceUrlsPlaceholder}
              />
              <small className="muted compact-copy">{copy.sourceUrlsHint}</small>
            </label>
          ) : null}
          <div className="field-row">
            <button
              type="button"
              className="primary-button"
              disabled={!cleanedQuery || isRunning}
              onClick={() => void run()}
            >
              {isCurrentModeRunning ? copy.running : runLabel(copy, mode)}
            </button>
          </div>
        </section>
        <section className="manager-section web-tool-results-pane">
          {isCurrentModeRunning ? (
            <div className="web-tool-state-panel capability-ok" data-testid={`web-state-running-${mode}`} role="status" aria-live="polite">
              <strong>{runningTitle(copy, mode)}</strong>
              <p className="compact-copy">{copy.runningBody}</p>
              <p className="compact-copy">
                <span className="web-tool-state-label">{copy.currentQuery}: </span>
                {activeRun?.query}
              </p>
              {hasCurrentModeStaleResult ? <p className="compact-copy">{copy.staleBody}</p> : null}
            </div>
          ) : null}
          {!isCurrentModeRunning && currentError ? (
            <div className="web-tool-state-panel capability-warn" data-testid={`web-state-error-${mode}`} role="status" aria-live="polite">
              <strong>{currentErrorType === "timeout" ? copy.timeoutTitle : copy.failureTitle}</strong>
              <p className="compact-copy">{currentErrorType === "timeout" ? copy.timeoutBody : copy.failureBody}</p>
              {currentRunState ? <p className="compact-copy">{copy.failureStaleBody}</p> : null}
              <p className="error-text">{copy.errorTitle}: {currentError}</p>
            </div>
          ) : null}
          {!isCurrentModeRunning && !currentError && currentRunState ? (
            <div className="web-tool-state-panel capability-ok" data-testid={`web-state-success-${mode}`} role="status" aria-live="polite">
              <strong>{successTitle(copy, mode)}</strong>
              <p className="compact-copy">{copy.successBody}</p>
            </div>
          ) : null}
          {currentRunState ? (
            <>
              <WebAuditMeta copy={copy} currentRunState={currentRunState} />
              {currentRunState.mode === "search" ? (
                <>
                  <h4 className="web-tool-section-title">{copy.searchSummaryTitle}</h4>
                  <div className="web-tool-result-list">
                    {currentRunState.response.result.merged_results.length > 0 ? (
                      currentRunState.response.result.merged_results.map((item) => (
                        <article className="web-tool-result-row" key={`${item.url}-${item.title}`}>
                          <a className="web-tool-result-link" href={item.url} target="_blank" rel="noreferrer">
                            {item.title || item.url}
                          </a>
                          <p className="muted compact-copy">{item.snippet}</p>
                        </article>
                      ))
                    ) : (
                      <p className="muted">{copy.noResults}</p>
                    )}
                  </div>
                  {currentRunState.response.result.warnings.length > 0 ? (
                    <>
                      <h4 className="web-tool-section-title">{copy.warnings}</h4>
                      <ul className="web-tool-warning-list">
                        {currentRunState.response.result.warnings.map((warning) => <li key={warning}>{warning}</li>)}
                      </ul>
                    </>
                  ) : null}
                </>
              ) : (
                <>
                  {(() => {
                    const result = currentRunState.response.result;
                    const brief = formatResearchBrief(result.brief, copy.noSources);
                    const policy = sourcePolicySummary(copy, result);
                    return (
                      <>
                        <div className="web-tool-research-summary">
                          <section className="web-tool-conclusion-card" data-testid="web-research-conclusion-card" aria-label={copy.conclusionTitle}>
                            <div className="web-tool-conclusion-header">
                              <strong>{copy.conclusionTitle}</strong>
                              <span className="web-tool-source-badge web-tool-conclusion-status">
                                {result.conclusion_status === "not_synthesized" ? copy.conclusionSourcePackOnly : result.conclusion_status || copy.conclusionSourcePackOnly}
                              </span>
                            </div>
                            <p className="compact-copy">{result.conclusion_note || copy.conclusionNoteFallback}</p>
                          </section>
                          {policy ? (
                            <section className="web-tool-source-policy">
                              <strong>{copy.sourcePolicyLabel}</strong>
                              <span>{policy}</span>
                              {result.source_policy?.reason ? (
                                <small>{copy.sourcePolicyReason}: {result.source_policy.reason}</small>
                              ) : null}
                            </section>
                          ) : null}
                        </div>

                        <h4 className="web-tool-section-title">{copy.sourcePackTitle}</h4>
                        <section className="web-tool-brief-panel" aria-label={copy.sourcePackTitle}>
                          <p className="web-tool-brief-summary">{brief.summary}</p>
                          {brief.extracts.length > 0 ? (
                            <ol className="web-tool-brief-extracts">
                              {brief.extracts.map((extract) => (
                                <li key={`${extract.sourceIndex}-${extract.url}-${extract.extract}`}>
                                  <span className="web-tool-brief-source">#{extract.sourceIndex}</span>
                                  <p>{extract.extract || extract.url}</p>
                                  {extract.url ? <a href={extract.url} target="_blank" rel="noreferrer">{extract.url}</a> : null}
                                </li>
                              ))}
                            </ol>
                          ) : null}
                          {brief.raw ? <pre className="web-tool-brief-raw">{brief.raw}</pre> : null}
                        </section>

                        <h4 className="web-tool-section-title">{copy.sourcesTitle}</h4>
                        <div className="web-tool-result-list">
                          {result.sources.length > 0 ? (
                            result.sources.map((source) => {
                              const fetchStatus = sourceFetchStatus(copy, source);
                              return (
                                <article className="web-tool-result-row" data-testid="web-source-row" key={`${source.url}-${source.query}`}>
                                  <a className="web-tool-result-link" href={source.url} target="_blank" rel="noreferrer">
                                    {source.title || source.url}
                                  </a>
                                  <div className="web-tool-source-meta">
                                    <span className={sourceOriginClassName(source)}>{sourceOriginLabel(copy, source)}</span>
                                    <span className={fetchStatus.className}>{fetchStatus.label}</span>
                                    {source.access_date ? <span>{copy.accessDate}: {source.access_date}</span> : null}
                                    {source.source_host ? <span>{copy.hostLabel}: {source.source_host}</span> : null}
                                    {source.query ? <span>{source.query}</span> : null}
                                  </div>
                                  <p className="muted compact-copy">{source.excerpt || source.snippet || source.warning}</p>
                                  {source.warning ? <p className="error-text compact-copy web-tool-source-warning">{source.warning}</p> : null}
                                </article>
                              );
                            })
                          ) : (
                            <p className="muted">{copy.noSources}</p>
                          )}
                        </div>

                        {result.failures.length > 0 ? (
                          <>
                            <h4 className="web-tool-section-title">{copy.fetchFailuresTitle}</h4>
                            <ul className="web-tool-warning-list web-tool-failure-list" data-testid="web-research-failures">
                              {result.failures.map((failure) => (
                                <li key={`${failure.url}-${failure.warning}`}>
                                  <strong>{failure.source_host || failure.url}</strong>
                                  <span>{failure.warning}</span>
                                </li>
                              ))}
                            </ul>
                          </>
                        ) : null}

                        {result.unresolved_questions.length > 0 ? (
                          <>
                            <h4 className="web-tool-section-title">{copy.unresolved}</h4>
                            <ul className="web-tool-warning-list">
                              {result.unresolved_questions.map((item) => <li key={item}>{item}</li>)}
                            </ul>
                          </>
                        ) : null}

                        {result.suggested_followup_queries.length > 0 ? (
                          <>
                            <h4 className="web-tool-section-title">{copy.followupQueriesTitle}</h4>
                            <ul className="web-tool-warning-list">
                              {result.suggested_followup_queries.map((item) => <li key={item}>{item}</li>)}
                            </ul>
                          </>
                        ) : null}

                        <p className="muted compact-copy">{copy.citationRule}: {result.citation_rule}</p>
                      </>
                    );
                  })()}
                </>
              )}
            </>
          ) : (
            <>
              <h4 className="web-tool-section-title">{resultTitle(copy, mode)}</h4>
              <p className="muted">{mode === "search" ? copy.noResults : copy.noSources}</p>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
