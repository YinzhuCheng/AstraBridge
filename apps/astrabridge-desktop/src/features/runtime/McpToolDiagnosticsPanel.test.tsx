import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { McpStatusResponse } from "../../types";
import {
  flattenMcpTools,
  formatJsonForUi,
  McpToolDiagnosticsPanel,
  parseArgumentsObject,
  redactSensitive,
} from "./McpToolDiagnosticsPanel";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const status: McpStatusResponse = {
  thread_id: "mcp-status-thread",
  next_cursor: null,
  servers: [
    {
      name: "fixture",
      serverInfo: { name: "fixture-server" },
      tools: {
        deterministic_echo: {
          description: "Echo deterministic input",
          inputSchema: { type: "object" },
        },
      },
      resources: [],
      resourceTemplates: [],
      authStatus: "ok",
    },
  ],
};

describe("McpToolDiagnosticsPanel", () => {
  it("lists discovered runtime tools and calls the selected tool with JSON arguments", async () => {
    const onCallTool = vi.fn().mockResolvedValue({ result: { ok: true, echo: "done" } });

    render(
      <McpToolDiagnosticsPanel
        locale="en"
        status={status}
        profileId="fixture-default"
        onCallTool={onCallTool}
      />,
    );

    expect(screen.getByText("Discovered: 1")).toBeInTheDocument();
    expect(screen.getByLabelText("Server")).toHaveValue("fixture");
    expect(screen.getByLabelText("Tool")).toHaveValue("deterministic_echo");

    fireEvent.change(screen.getByLabelText("Arguments JSON"), { target: { value: "{\"message\":\"hello\"}" } });
    fireEvent.click(screen.getByRole("button", { name: "Call tool" }));

    await waitFor(() =>
      expect(onCallTool).toHaveBeenCalledWith({
        profile_id: "fixture-default",
        thread_id: "mcp-status-thread",
        server: "fixture",
        tool: "deterministic_echo",
        arguments: { message: "hello" },
      }),
    );
    expect(screen.getByTestId("mcp-tool-call-result")).toHaveTextContent("Replay envelope");
    expect(screen.getByTestId("mcp-tool-call-result")).toHaveTextContent("Result preview");
  });

  it("shows an actionable empty state when no tools are visible", () => {
    render(
      <McpToolDiagnosticsPanel
        locale="en"
        status={{ ...status, servers: [{ ...status.servers[0], tools: {} }] }}
        onCallTool={vi.fn()}
      />,
    );

    expect(screen.getByText("No runtime MCP tools are visible.")).toBeInTheDocument();
    expect(screen.getByText("Reload MCP, install a preset, or check provider/runtime health before expecting tool calls here.")).toBeInTheDocument();
  });

  it("keeps schema errors local when arguments are not a JSON object", () => {
    const onCallTool = vi.fn();
    render(<McpToolDiagnosticsPanel locale="en" status={status} onCallTool={onCallTool} />);

    fireEvent.change(screen.getByLabelText("Arguments JSON"), { target: { value: "[1,2,3]" } });
    fireEvent.click(screen.getByRole("button", { name: "Call tool" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Arguments must be a JSON object.");
    expect(onCallTool).not.toHaveBeenCalled();
  });

  it("shows an actionable error when the MCP status thread is missing", () => {
    const onCallTool = vi.fn();
    render(
      <McpToolDiagnosticsPanel
        locale="en"
        status={{ ...status, thread_id: "" }}
        onCallTool={onCallTool}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Call tool" }));

    expect(screen.getByRole("alert")).toHaveTextContent("MCP status thread is not ready. Refresh status or reload MCP, then retry.");
    expect(onCallTool).not.toHaveBeenCalled();
  });

  it("redacts sensitive arguments and truncates large results in the UI", async () => {
    const onCallTool = vi.fn().mockResolvedValue({
      result: {
        token: "raw-token",
        payload: "x".repeat(4000),
      },
    });
    render(<McpToolDiagnosticsPanel locale="en" status={status} onCallTool={onCallTool} />);

    fireEvent.change(screen.getByLabelText("Arguments JSON"), { target: { value: "{\"api_key\":\"secret\",\"query\":\"ok\"}" } });
    fireEvent.click(screen.getByRole("button", { name: "Call tool" }));

    await waitFor(() => expect(screen.getByTestId("mcp-tool-call-result")).toBeInTheDocument());
    const result = screen.getByTestId("mcp-tool-call-result");
    expect(result).toHaveTextContent("[redacted]");
    expect(result).not.toHaveTextContent("raw-token");
    expect(result).not.toHaveTextContent("secret");
    expect(result).toHaveTextContent("Large result truncated for UI display.");
  });
});

describe("MCP diagnostics helpers", () => {
  it("normalizes tool lists, validates arguments, redacts secrets, and formats previews", () => {
    expect(flattenMcpTools(status)).toEqual([
      expect.objectContaining({ server: "fixture", tool: "deterministic_echo" }),
    ]);
    expect(parseArgumentsObject("{\"ok\":true}")).toEqual({ ok: true, value: { ok: true } });
    expect(parseArgumentsObject("[1]")).toEqual({ ok: false });
    expect(redactSensitive({ nested: { authorization: "Bearer abc" } })).toEqual({ nested: { authorization: "[redacted]" } });
    const preview = formatJsonForUi({ data: "abcdef" }, 8);
    expect(preview.truncated).toBe(true);
    expect(preview.originalLength).toBe(22);
    expect(preview.text).toMatch(/\n\.\.\.$/);

    const circular: Record<string, unknown> = {};
    circular.self = circular;
    expect(redactSensitive(circular)).toEqual({ self: "[circular]" });
  });
});
