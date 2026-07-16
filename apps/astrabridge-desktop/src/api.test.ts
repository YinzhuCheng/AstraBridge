import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiRequestError,
  api,
  resetApiModuleStateForTests,
  seedLegacyAdminSessionTokenPromiseForTests,
} from "./api";

describe("api.health", () => {
  afterEach(() => {
    resetApiModuleStateForTests();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    window.localStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("normalizes top-level router health into runtime.router", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          ok: true,
          service: "astrabridge-sidecar",
          runtime: {
            codex_cli: "codex",
            running: true,
            runtime_config: {
              configured: false,
              codex_home: "D:\\AstraBridgeRuntime\\codex_home",
              provider_id: null,
              provider_name: null,
              base_url: null,
              model: null,
              reasoning_effort: null,
              wire_api: null,
              env_key: null,
              secret_loaded: false,
              proxy_mode: "direct",
              proxy_url: "",
            },
          },
          router: {
            ok: true,
            service: "astrabridge",
            running: true,
            listen_host: "127.0.0.1",
            listen_port: 8787,
            base_url: "http://127.0.0.1:8787/v1",
            router_env_key: "CODEX_ROUTER_API_KEY",
            token_loaded: true,
            provider_count: 1,
            model_count: 1,
            providers: [
              {
                provider_id: "qwen",
                label: "Qwen / DashScope",
                base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
                model: "qwen3.7-plus",
                wire_api: "responses",
                secret_loaded: true,
              },
            ],
          },
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.health()).resolves.toMatchObject({
      runtime: {
        router: {
          providers: [{ provider_id: "qwen", secret_loaded: true }],
        },
      },
    });
  });
});

describe("api.runtimeEvents", () => {
  afterEach(() => {
    resetApiModuleStateForTests();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    window.localStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("uses a long-poll timeout budget instead of the default 15-second GET timeout", async () => {
    window.history.replaceState({}, "", "/?sidecar=http%3A%2F%2F127.0.0.1%3A8852");
    vi.useFakeTimers();
    let capturedSignal: AbortSignal | undefined;
    const fetchMock = vi.fn().mockImplementation((_, init?: RequestInit) => {
      capturedSignal = init?.signal ?? undefined;
      return new Promise((_, reject) => {
        capturedSignal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), {
          once: true,
        });
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const pending = api.runtimeEvents(0).catch((error) => error);
    await vi.advanceTimersByTimeAsync(15001);
    expect(capturedSignal?.aborted).toBe(false);

    await vi.advanceTimersByTimeAsync(50000);
    expect(capturedSignal?.aborted).toBe(true);
    await expect(pending).resolves.toBeInstanceOf(Error);
  }, 10000);
});

describe("api.runTaskGraph", () => {
  afterEach(() => {
    resetApiModuleStateForTests();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    window.localStorage.clear();
    window.history.replaceState({}, "", "/");
  });

  it("prewarms and reuses the admin session token before a live task-graph mutation", async () => {
    window.history.replaceState({}, "", "/?sidecar=http%3A%2F%2F127.0.0.1%3A8852");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ admin_session_token: "prefetched-admin-token" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            schema_version: "astrabridge-task-graph-live-run-v1",
            live_run: {
              run_id: "graph-run-live-prefetched",
              run_status: "running",
              run_ref: {
                run_id: "graph-run-live-prefetched",
                graph_id: "graph-step21",
                task_id: "task-step21",
                status: "running",
                created_at: "2026-07-15T05:00:00+09:00",
                updated_at: "2026-07-15T05:00:01+09:00",
              },
            },
            graph: { graph_id: "graph-step21", nodes: [], edges: [] },
            task: { task_id: "task-step21", graph_run_refs: [] },
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.ensureAdminSession()).resolves.toBeUndefined();
    await expect(
      api.runTaskGraph({
        graph_id: "graph-step21",
        budget: { limits: { total_tokens: 80_000 } },
      }),
    ).resolves.toMatchObject({
      live_run: { run_id: "graph-run-live-prefetched" },
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8852/api/admin/session");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://127.0.0.1:8852/api/task-graphs/run");
  });

  it("routes browser dogfood live-run mutations through the same-origin sidecar proxy", async () => {
    window.history.replaceState({}, "", "/?sidecar=http%3A%2F%2F127.0.0.1%3A8852");
    vi.spyOn(window.navigator, "userAgent", "get").mockReturnValue(
      "Mozilla/5.0 AstraBridge Browser QA",
    );
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ admin_session_token: "prefetched-admin-token" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            schema_version: "astrabridge-task-graph-live-run-v1",
            live_run: {
              run_id: "graph-run-live-proxied",
              run_status: "running",
              run_ref: {
                run_id: "graph-run-live-proxied",
                graph_id: "graph-step21",
                task_id: "task-step21",
                status: "running",
                created_at: "2026-07-15T09:00:00+09:00",
                updated_at: "2026-07-15T09:00:01+09:00",
              },
            },
            graph: { graph_id: "graph-step21", nodes: [], edges: [] },
            task: { task_id: "task-step21", graph_run_refs: [] },
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      api.runTaskGraph({
        graph_id: "graph-step21",
        budget: { limits: { total_tokens: 80_000 } },
      }),
    ).resolves.toMatchObject({
      live_run: { run_id: "graph-run-live-proxied" },
    });

    const expectedProxyBase = `${window.location.origin}/__astrabridge_proxy__`;
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8852/api/admin/session");
    expect(fetchMock.mock.calls[1]?.[0]).toBe(`${expectedProxyBase}/api/task-graphs/run`);
    expect(
      (fetchMock.mock.calls[0]?.[1] as { headers?: Record<string, string> } | undefined)
        ?.headers?.["X-AstraBridge-Sidecar-Base"],
    ).toBeUndefined();
    expect(
      (fetchMock.mock.calls[1]?.[1] as { headers?: Record<string, string> } | undefined)
        ?.headers?.["X-AstraBridge-Sidecar-Base"],
    ).toBe("http://127.0.0.1:8852");
  });

  it("preserves structured terminal failure payloads for failed live runs", async () => {
    window.history.replaceState({}, "", "/?sidecar=http%3A%2F%2F127.0.0.1%3A8851");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ admin_session_token: "unit-admin-token" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ok: false,
            error: "Model runtime ended with an error.",
            graph: { graph_id: "graph-step20" },
            task: {
              task_id: "task-step20",
              graph_activity_summary: { latest_run_status: "failed" },
              graph_run_refs: [
                {
                  run_id: "graph-run-live-123",
                  graph_id: "graph-step20",
                  task_id: "task-step20",
                  status: "failed",
                  created_at: "2026-07-13T22:35:58+09:00",
                  updated_at: "2026-07-13T22:36:44+09:00",
                },
              ],
            },
            live_run: {
              run_id: "graph-run-live-123",
              run_status: "failed",
              run_ref: {
                run_id: "graph-run-live-123",
                graph_id: "graph-step20",
                task_id: "task-step20",
                status: "failed",
                created_at: "2026-07-13T22:35:58+09:00",
                updated_at: "2026-07-13T22:36:44+09:00",
              },
              artifact_paths: {
                summary_json: "PRIVATE/task-graph/live-run/graph-run-live-123/summary.json",
              },
            },
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    let captured: unknown;
    await api
      .runTaskGraph({
        graph_id: "graph-step20",
        budget: { limits: { total_tokens: 80_000 } },
      })
      .catch((error) => {
        captured = error;
      });

    expect(captured).toBeInstanceOf(ApiRequestError);
    expect((captured as ApiRequestError).message).toBe(
      "Model runtime ended with an error.",
    );
    expect((captured as ApiRequestError).status).toBe(200);
    expect(
      ((captured as ApiRequestError).data?.live_run as { run_id?: string } | undefined)
        ?.run_id,
    ).toBe("graph-run-live-123");
    expect(
      (
        ((captured as ApiRequestError).data?.live_run as {
          run_ref?: { status?: string };
        } | undefined)?.run_ref?.status
      ),
    ).toBe("failed");
  });

  it("reuses the already-current project without bootstrapping an admin session", async () => {
    window.history.replaceState({}, "", "/?sidecar=http%3A%2F%2F127.0.0.1%3A8852");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            project: {
              project_id: "proj-current",
              name: "Current Demo",
              project_file: "D:\\work\\Current-Demo.abproj",
            },
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.openProject("d:/work/current-demo.abproj")).resolves.toEqual({
      project: {
        project_id: "proj-current",
        name: "Current Demo",
        project_file: "D:\\work\\Current-Demo.abproj",
      },
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8852/api/projects/current");
  });

  it("clears a failed admin-session token fetch and retries on the next mutation", async () => {
    window.history.replaceState({}, "", "/?sidecar=http%3A%2F%2F127.0.0.1%3A8852");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ project: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockRejectedValueOnce(new Error("admin session bootstrap failed"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ project: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ admin_session_token: "fresh-admin-token" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ project: { project_id: "proj-1", name: "Demo" } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.openProject("D:/work/demo.abproj")).rejects.toThrow("admin session bootstrap failed");
    await expect(api.openProject("D:/work/demo.abproj")).resolves.toEqual({
      project: { project_id: "proj-1", name: "Demo" },
    });

    expect(fetchMock).toHaveBeenCalledTimes(5);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8852/api/projects/current");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://127.0.0.1:8852/api/admin/session");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("http://127.0.0.1:8852/api/projects/current");
    expect(fetchMock.mock.calls[3]?.[0]).toBe("http://127.0.0.1:8852/api/admin/session");
    expect(fetchMock.mock.calls[4]?.[0]).toBe("http://127.0.0.1:8852/api/projects/open");
  });

  it("times out a hung admin-session response body and clears the cached promise for the next mutation", async () => {
    window.history.replaceState({}, "", "/?sidecar=http%3A%2F%2F127.0.0.1%3A8852");
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ project: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => new Promise(() => undefined),
      })
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ project: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ admin_session_token: "fresh-admin-token" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ project: { project_id: "proj-3", name: "Recovered Demo" } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const firstAttempt = api.openProject("D:/work/demo.abproj");
    const firstAttemptExpectation = expect(firstAttempt).rejects.toThrow(
      "did not respond in time for /api/admin/session",
    );
    await vi.advanceTimersByTimeAsync(12001);
    await firstAttemptExpectation;

    await expect(api.openProject("D:/work/demo.abproj")).resolves.toEqual({
      project: { project_id: "proj-3", name: "Recovered Demo" },
    });

    expect(fetchMock).toHaveBeenCalledTimes(5);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8852/api/projects/current");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://127.0.0.1:8852/api/admin/session");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("http://127.0.0.1:8852/api/projects/current");
    expect(fetchMock.mock.calls[3]?.[0]).toBe("http://127.0.0.1:8852/api/admin/session");
    expect(fetchMock.mock.calls[4]?.[0]).toBe("http://127.0.0.1:8852/api/projects/open");
  });

  it("does not reuse a hanging prewarm admin-session promise for a later mutation", async () => {
    window.history.replaceState({}, "", "/?sidecar=http%3A%2F%2F127.0.0.1%3A8852");
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        text: () => new Promise(() => undefined),
      })
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ project: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ admin_session_token: "fresh-admin-token" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ project: { project_id: "proj-prewarm", name: "Recovered From Prewarm" } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const prewarm = api.ensureAdminSession().catch(() => undefined);

    await expect(api.openProject("D:/work/demo.abproj")).resolves.toEqual({
      project: { project_id: "proj-prewarm", name: "Recovered From Prewarm" },
    });

    await vi.advanceTimersByTimeAsync(12001);
    await prewarm;

    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8852/api/admin/session");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://127.0.0.1:8852/api/projects/current");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("http://127.0.0.1:8852/api/admin/session");
    expect(fetchMock.mock.calls[3]?.[0]).toBe("http://127.0.0.1:8852/api/projects/open");
  });

  it("evicts a legacy bare admin-session promise before a live task-graph mutation", async () => {
    window.history.replaceState({}, "", "/?sidecar=http%3A%2F%2F127.0.0.1%3A8852");
    seedLegacyAdminSessionTokenPromiseForTests(
      "http://127.0.0.1:8852",
      new Promise(() => undefined),
    );
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ admin_session_token: "fresh-admin-token" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            schema_version: "astrabridge-task-graph-live-run-v1",
            live_run: {
              run_id: "graph-run-live-fresh",
              run_status: "running",
              run_ref: {
                run_id: "graph-run-live-fresh",
                graph_id: "graph-step21",
                task_id: "task-step21",
                status: "running",
                created_at: "2026-07-15T10:00:00+09:00",
                updated_at: "2026-07-15T10:00:01+09:00",
              },
            },
            graph: { graph_id: "graph-step21", nodes: [], edges: [] },
            task: { task_id: "task-step21", graph_run_refs: [] },
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      api.runTaskGraph({
        graph_id: "graph-step21",
        budget: { limits: { total_tokens: 80_000 } },
      }),
    ).resolves.toMatchObject({
      live_run: { run_id: "graph-run-live-fresh" },
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8852/api/admin/session");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://127.0.0.1:8852/api/task-graphs/run");
  });

  it("refreshes the admin token after an invalid-session mutation response", async () => {
    window.history.replaceState({}, "", "/?sidecar=http%3A%2F%2F127.0.0.1%3A8852");
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ project: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ admin_session_token: "stale-admin-token" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: "Admin session token expired." }), {
          status: 400,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ admin_session_token: "fresh-admin-token" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ project: { project_id: "proj-2", name: "Retry Demo" } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.openProject("D:/work/retry.abproj")).resolves.toEqual({
      project: { project_id: "proj-2", name: "Retry Demo" },
    });

    expect(fetchMock).toHaveBeenCalledTimes(5);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://127.0.0.1:8852/api/projects/current");
    expect(fetchMock.mock.calls[1]?.[0]).toBe("http://127.0.0.1:8852/api/admin/session");
    expect(fetchMock.mock.calls[2]?.[0]).toBe("http://127.0.0.1:8852/api/projects/open");
    expect(fetchMock.mock.calls[3]?.[0]).toBe("http://127.0.0.1:8852/api/admin/session");
    expect(fetchMock.mock.calls[4]?.[0]).toBe("http://127.0.0.1:8852/api/projects/open");
    const retriedHeaders = fetchMock.mock.calls[4]?.[1] as RequestInit | undefined;
    expect((retriedHeaders?.headers as Record<string, string>)["X-Admin-Token"]).toBe("fresh-admin-token");
  });
});
