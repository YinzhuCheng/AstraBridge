import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AgenticUpdateJobStatus, AgenticUpdateProposalResult, AgenticUpdateRunContract, RouterProvider } from "../../types";
import { AgenticUpdateReviewPanel } from "./AgenticUpdateReviewPanel";

afterEach(() => cleanup());

const baseContract: AgenticUpdateRunContract = {
  scope: ["provider_metadata"],
  providers: [],
  models: [],
  version_policy: "stable",
  target_version: null,
  apply_mode: "proposal_only",
  allow_network: true,
  allow_provider_calls: false,
  allow_install: false,
  allow_code_changes: false,
  approval_policy: "manual_review_required",
};

const successStatus: AgenticUpdateJobStatus = {
  schema_version: "astrabridge-agentic-update-job-v1",
  job_id: "agentic-update-job-test",
  run_id: "agentic-update-test",
  status: "success",
  running: false,
  summary: { status: "proposal_only_complete" },
  artifact_paths: {},
};

const proposalResult: AgenticUpdateProposalResult = {
  schema_version: "astrabridge-agentic-update-proposal-only-result-v1",
  generated_at: "2026-07-05T00:00:00Z",
  run_id: "agentic-update-test",
  run_contract: baseContract,
  summary: {
    status: "proposal_only_complete",
    proposal_status: "metadata_delta",
    risk_class: "low",
    change_count: 2,
    applied: false,
    provider_calls_attempted: false,
    install_attempted: false,
    code_changes_attempted: false,
  },
  discovery: null,
  parser_output: null,
  kernel_candidates: null,
  diff: {
    status: "metadata_delta",
    risk_class: "low",
    changes: [
      {
        change_id: "qwen-context-window",
        action: "update",
        summary: "Raise advertised context hint after source review.",
        risk_class: "low",
      },
    ],
    artifact_paths: {
      proposal_markdown: "D:\\AstraBridge\\PRIVATE\\agentic-update-pipeline\\proposal.md",
    },
  },
  proposal: {
    schema_version: "astrabridge-agentic-update-proposal-v1",
    run_id: "agentic-update-test",
    discovery_result: {
      sources: [
        {
          source_id: "openai-docs",
          trust_label: "official",
          status: "ok",
          url: "https://docs.example.test/models",
          short_excerpt: "Authorization: Bearer should-not-render raw external document body",
        },
      ],
      findings: [],
      warnings: [],
    },
    diff: {
      status: "metadata_delta",
      risk_class: "low",
      changes: [
        {
          change_id: "qwen-context-window",
          action: "update",
          summary: "Raise advertised context hint after source review.",
          risk_class: "low",
        },
      ],
      artifact_paths: {
        proposal_markdown: "D:\\AstraBridge\\PRIVATE\\agentic-update-pipeline\\proposal.md",
      },
    },
    validation_result: {
      status: "not_run",
      gates: [],
      warnings: ["proposal_only_service_does_not_run_validation"],
    },
    approval_state: {
      status: "pending_manual_review",
      policy: "manual_review_required",
    },
    apply_manifest: {
      changed_paths: [],
      warnings: ["proposal_only_service_does_not_apply_changes"],
    },
    rollback_manifest: {
      reversible: true,
      steps: [],
      warnings: ["no_runtime_or_source_state_changed"],
    },
  },
  artifact_paths: {
    proposal: "D:\\AstraBridge\\PRIVATE\\agentic-update-pipeline\\proposal.json",
    summary: "D:\\AstraBridge\\PRIVATE\\agentic-update-pipeline\\summary.json",
  },
  mutations: {
    source_code_changed: false,
  },
};

function provider(id: string, displayName: string): RouterProvider {
  return {
    id,
    display_name: displayName,
    enabled: true,
    adapter_type: "chat",
    base_url: "https://example.test/v1",
    default_model: `${id}-model`,
    request_timeout_ms: 120000,
    stream_idle_timeout_ms: 60000,
    env_key: `${id.toUpperCase()}_API_KEY`,
    auth_mode: "os_keychain",
    proxy_mode: "direct",
    proxy_url: "",
  };
}

function renderPanel(options?: {
  start?: ReturnType<typeof vi.fn>;
  result?: ReturnType<typeof vi.fn>;
}) {
  const start = options?.start ?? vi.fn(async () => successStatus);
  const result = options?.result ?? vi.fn(async () => proposalResult);
  render(
    <AgenticUpdateReviewPanel
      locale="en"
      providers={[provider("qwen", "Qwen"), provider("openai", "OpenAI")]}
      api={{ start, result }}
    />,
  );
  return { start, result };
}

describe("AgenticUpdateReviewPanel", () => {
  it("builds a scoped proposal request from user selections", async () => {
    const user = userEvent.setup();
    const { start } = renderPanel();

    await user.click(screen.getByRole("checkbox", { name: /Codex kernel/i }));
    await user.selectOptions(screen.getByTestId("agentic-update-provider"), "qwen");
    await user.selectOptions(screen.getByTestId("agentic-update-version-policy"), "pinned");
    await user.type(screen.getByTestId("agentic-update-target-version"), "qwen3-next-stable");
    await user.selectOptions(screen.getByTestId("agentic-update-apply-mode"), "discover_only");
    await user.click(screen.getByRole("button", { name: /Generate proposal/i }));

    expect(await screen.findByText("agentic-update-test")).toBeInTheDocument();
    expect(start).toHaveBeenCalledTimes(1);
    expect(start.mock.calls[0][0].run_contract).toMatchObject({
      providers: ["qwen"],
      version_policy: "pinned",
      target_version: "qwen3-next-stable",
      apply_mode: "discover_only",
      allow_provider_calls: false,
      allow_install: false,
      allow_code_changes: false,
    });
    expect(start.mock.calls[0][0].run_contract.scope).toEqual(expect.arrayContaining(["provider_metadata", "codex_kernel"]));
  });

  it("renders proposal summary, trusted sources, validation warnings, artifacts, and disabled unsafe actions", async () => {
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole("button", { name: /Generate proposal/i }));

    expect(await screen.findByText("low")).toBeInTheDocument();
    expect(screen.getByText("openai-docs")).toBeInTheDocument();
    expect(screen.getByText(/official/)).toBeInTheDocument();
    expect(screen.getByText("proposal_only_service_does_not_run_validation")).toBeInTheDocument();
    expect(screen.getByText("D:\\AstraBridge\\PRIVATE\\agentic-update-pipeline\\proposal.json")).toBeInTheDocument();
    expect(screen.getByTestId("agentic-update-apply")).toBeDisabled();
    expect(screen.getByTestId("agentic-update-provider-smoke")).toBeDisabled();
    expect(screen.getByTestId("agentic-update-install")).toBeDisabled();
    expect(screen.queryByText(/Authorization/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/raw external document body/i)).not.toBeInTheDocument();
  });

  it("shows request errors without enabling unsafe actions", async () => {
    const user = userEvent.setup();
    renderPanel({ start: vi.fn(async () => { throw new Error("sidecar unavailable"); }) });

    await user.click(screen.getByRole("button", { name: /Generate proposal/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Proposal request failed");
    expect(screen.getByTestId("agentic-update-apply")).toBeDisabled();
    expect(screen.getByTestId("agentic-update-provider-smoke")).toBeDisabled();
    expect(screen.getByTestId("agentic-update-install")).toBeDisabled();
  });
});
