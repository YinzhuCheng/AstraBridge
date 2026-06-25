import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  CapabilityManagementEntry,
  CapabilityRouteCandidate,
  CapabilityRouteEntry,
  CodexPluginSkillRegistrySnapshot,
} from "../../types";
import { CapabilityRoutesPanel, type CapabilityRouteDraft } from "./CapabilityRoutesPanel";

function buildModelCandidate(
  capabilityId: string,
  adapterId: string,
  providerId: string,
  model: string,
): CapabilityRouteCandidate {
  return {
    capability_id: capabilityId,
    adapter_id: adapterId,
    provider_id: providerId,
    model,
    lane_type: "model_backed",
    transport_mode: "request_response",
    source: "adapter",
    input_modalities: ["text", "image"],
    eligibility_notes: [],
  };
}

function buildModelRoute(capabilityId: string, displayName: string, candidates?: CapabilityRouteCandidate[]): CapabilityRouteEntry {
  const routeCandidates =
    candidates ??
    [
      buildModelCandidate(capabilityId, `${capabilityId}.qwen.v1`, "qwen", "qwen3-vl-plus"),
      buildModelCandidate(capabilityId, `${capabilityId}.kimi.v1`, "kimi", "kimi-k2.6"),
    ];
  return {
    capability_id: capabilityId,
    display_name: displayName,
    lane_type: "model_backed",
    transport_mode: "request_response",
    route_mode: "auto",
    route_record: { capability_id: capabilityId, mode: "auto", provider_id: null, model: null },
    resolution_status: "ok",
    resolved_candidate: routeCandidates[0],
    candidates: routeCandidates,
  };
}

function buildStandaloneRoute(): CapabilityRouteEntry {
  return {
    capability_id: "web.search",
    display_name: "Web Search",
    lane_type: "web_standalone",
    transport_mode: "request_response",
    route_mode: "auto",
    route_record: { capability_id: "web.search", mode: "auto", provider_id: null, model: null },
    resolution_status: "standalone",
    resolved_candidate: {
      capability_id: "web.search",
      adapter_id: "web.search.standalone",
      lane_type: "web_standalone",
      transport_mode: "request_response",
      source: "standalone",
      input_modalities: ["text"],
      eligibility_notes: [],
    },
    candidates: [
      {
        capability_id: "web.search",
        adapter_id: "web.search.standalone",
        lane_type: "web_standalone",
        transport_mode: "request_response",
        source: "standalone",
        input_modalities: ["text"],
        eligibility_notes: [],
      },
    ],
  };
}

function artifactPolicyFor(route: CapabilityRouteEntry): string {
  if (route.capability_id === "image.generate") {
    return "persist_generated_assets";
  }
  if (route.capability_id.startsWith("speech.")) {
    return "persist_optional_audio_artifacts";
  }
  if (route.capability_id === "web.search") {
    return "no_local_artifacts";
  }
  return "persist_optional_visual_artifacts";
}

function buildManagementEntry(route: CapabilityRouteEntry): CapabilityManagementEntry {
  const firstCandidate = route.candidates[0];
  const artifactPolicy = artifactPolicyFor(route);
  return {
    capability_id: route.capability_id,
    display_name: route.display_name,
    lane_type: route.lane_type,
    transport_mode: "request_response",
    route,
    availability: {
      available: Boolean(route.resolved_candidate),
      candidate_count: route.candidates.length,
      resolution_status: route.resolution_status,
    },
    contract: {
      schema_version: "astrabridge-capability-contract-v1",
      capability_id: route.capability_id,
      display_name: route.display_name,
      lane_type: route.lane_type,
      transport_mode: "request_response",
      input_schema: { fields: [] },
      output_schema: { fields: [] },
      artifact_policy: artifactPolicy,
      provider_eligibility_rule: route.lane_type === "web_standalone" ? "standalone_lane" : "requires_provider_adapter",
      default_timeout_sec: 120,
      smoke_status: "untested",
    },
    adapters:
      route.lane_type === "model_backed" && firstCandidate?.provider_id
        ? [
            {
              schema_version: "astrabridge-adapter-contract-v1",
              adapter_id: firstCandidate.adapter_id,
              capability_id: route.capability_id,
              provider_id: firstCandidate.provider_id,
              model_match: firstCandidate.model ? [firstCandidate.model] : [],
              supports_streaming: false,
              supports_batch: false,
              normalization_rules: [],
              request_builder: "",
              response_parser: "",
              artifact_persister: "",
              smoke_case_id: `${route.capability_id}.smoke`,
            },
          ]
        : [],
    smoke: {
      status: "untested",
      case_ids: route.lane_type === "web_standalone" ? [] : [`${route.capability_id}.smoke`],
      last_result: null,
      evidence_refs: [],
    },
    artifacts: { policy: artifactPolicy, recent_refs: [] },
  };
}

const visionRoute = buildModelRoute("vision.analyze", "Vision Analysis");
const visionManagementEntry = buildManagementEntry(visionRoute);

type RenderPanelOptions = {
  routes?: CapabilityRouteEntry[];
  managementEntries?: CapabilityManagementEntry[];
  pluginSkillRegistry?: CodexPluginSkillRegistrySnapshot | null;
  pluginSkillRegistryLoading?: boolean;
  pluginSkillRegistryError?: boolean;
  onSave?: ReturnType<typeof vi.fn>;
  onRunSmoke?: ReturnType<typeof vi.fn>;
  onInstallMcpPreset?: ReturnType<typeof vi.fn>;
};

function renderPanel(options: RenderPanelOptions = {}) {
  const onSave = options.onSave ?? vi.fn();
  const onRunSmoke = options.onRunSmoke ?? vi.fn();
  const onInstallMcpPreset = options.onInstallMcpPreset ?? vi.fn();
  const routes = options.routes ?? [visionRoute];
  const managementEntries = options.managementEntries ?? [visionManagementEntry];

  function Harness() {
    const [drafts, setDrafts] = useState<Record<string, CapabilityRouteDraft>>({});
    return (
      <CapabilityRoutesPanel
        locale="en"
        routes={routes}
        managementEntries={managementEntries}
        mcpPreset={{
          server_name: "astrabridge_capabilities",
          configured: true,
          enabled: true,
          runtime_visible: null,
          tool_names: ["astrabridge_capability_routes"],
          expected_tool_names: [
            "astrabridge_capability_routes",
            "astrabridge_capability_image_generate",
            "astrabridge_capability_vision_analyze",
            "astrabridge_capability_speech_transcribe",
            "astrabridge_capability_speech_synthesize",
          ],
          missing_tool_names: [],
          configured_tool_count: 5,
          health_status: "configured",
          approval_modes: { astrabridge_capability_routes: "auto" },
        }}
        pluginSkillRegistry={options.pluginSkillRegistry ?? null}
        pluginSkillRegistryLoading={options.pluginSkillRegistryLoading ?? false}
        pluginSkillRegistryError={options.pluginSkillRegistryError ?? false}
        drafts={drafts}
        setDrafts={setDrafts}
        isLoading={false}
        isError={false}
        isSaving={false}
        smokeResults={{}}
        smokePendingCapabilityId={null}
        isSmokePending={false}
        artifacts={[
          {
            artifact_id: "vision-run",
            capability_id: "vision.analyze",
            provider_id: "qwen",
            model: "qwen3-vl-plus",
            saved_at: "2026-06-25T01:00:00Z",
            summary_path: "D:/AstraBridge/.astrabridge/capabilities/vision_analyze/vision-run/summary.json",
            relative_summary_path: ".astrabridge/capabilities/vision_analyze/vision-run/summary.json",
            artifact_refs: [
              {
                artifact_type: "text",
                path: "D:/AstraBridge/.astrabridge/capabilities/vision_analyze/vision-run/text.txt",
                relative_path: ".astrabridge/capabilities/vision_analyze/vision-run/text.txt",
                exists: true,
                mime_type: "text/plain",
              },
            ],
            preview: { kind: "text", text: "AstraBridge vision artifact preview", audio_path: "", image_path: "" },
            metadata: { image_input_count: 1 },
          },
        ]}
        artifactsLoading={false}
        artifactsError={false}
        providerCredentials={{
          qwen: {
            provider_id: "qwen",
            label: "Qwen",
            enabled: true,
            auth_mode: "os_keychain",
            status: "configured",
          },
          kimi: {
            provider_id: "kimi",
            label: "Kimi",
            enabled: true,
            auth_mode: "os_keychain",
            status: "missing",
          },
        }}
        mcpRuntimeVisible={true}
        mcpRuntimeToolCount={5}
        mcpVisibilityLoading={false}
        mcpVisibilityError={false}
        isInstallingMcpPreset={false}
        toMediaSrc={(path) => `file://${path}`}
        onInstallMcpPreset={onInstallMcpPreset}
        onSave={onSave}
        onRunSmoke={onRunSmoke}
      />
    );
  }

  render(<Harness />);
  return { onSave, onRunSmoke, onInstallMcpPreset };
}

describe("CapabilityRoutesPanel", () => {
  afterEach(() => cleanup());

  it("renders route details and saves a pinned candidate", () => {
    const { onSave } = renderPanel();

    expect(screen.getByText("Vision Analysis")).toBeInTheDocument();
    expect(screen.getByText("Candidates: 2")).toBeInTheDocument();
    expect(screen.getByText("Adapters: 1")).toBeInTheDocument();
    expect(screen.getByText("MCP preset: configured")).toBeInTheDocument();
    expect(screen.getByText("Runtime: visible")).toBeInTheDocument();
    expect(screen.getByText("tools: 5/5 (5 runtime tools)")).toBeInTheDocument();
    expect(screen.getByText("Provider-backed calls may spend paid quota")).toBeInTheDocument();
    expect(screen.getByText("Artifacts may be large and retained locally")).toBeInTheDocument();
    expect(screen.getByText("qwen: credential configured")).toBeInTheDocument();
    expect(screen.getByText("kimi: credential missing")).toBeInTheDocument();
    expect(screen.getByText("AstraBridge vision artifact preview")).toBeInTheDocument();
    expect(screen.getByText("1 refs")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Route mode"), { target: { value: "pinned" } });
    fireEvent.change(screen.getByLabelText("Pinned candidate"), { target: { value: "kimi/kimi-k2.6" } });
    expect(screen.getByRole("button", { name: "Save route" })).toBeDisabled();
    expect(screen.getByText("Pinned routing is disabled until this provider has a usable redacted credential state.")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Pinned candidate"), { target: { value: "qwen/qwen3-vl-plus" } });
    fireEvent.click(screen.getByRole("button", { name: "Save route" }));

    expect(onSave).toHaveBeenCalledWith(
      visionRoute,
      expect.objectContaining({ mode: "pinned", provider_id: "qwen", model: "qwen3-vl-plus" }),
    );
  });

  it("reapplies the capability MCP preset from the capability panel", () => {
    const onInstallMcpPreset = vi.fn();
    renderPanel({ onInstallMcpPreset });

    fireEvent.click(screen.getByRole("button", { name: "Install / reapply preset" }));

    expect(onInstallMcpPreset).toHaveBeenCalledTimes(1);
  });

  it("resets unsaved route changes", () => {
    const { onSave } = renderPanel();

    fireEvent.change(screen.getByLabelText("Route mode"), { target: { value: "pinned" } });
    expect(screen.getByRole("button", { name: "Reset" })).not.toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Reset" }));

    expect(screen.getByRole("button", { name: "Reset" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save route" })).toBeDisabled();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("runs no-key dry-run smoke from the capability panel", () => {
    const onRunSmoke = vi.fn();
    renderPanel({ onRunSmoke });

    expect(screen.getByText("Dry-run smoke")).toBeInTheDocument();
    expect(screen.getByText("Last smoke: not run")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Run dry smoke" }));

    expect(onRunSmoke).toHaveBeenCalledWith("vision.analyze");
  });

  it("shows plugin and skill visibility guidance without rerouting standalone web search", () => {
    const imageRoute = buildModelRoute("image.generate", "Image Generation");
    const speechRoute = buildModelRoute("speech.transcribe", "Speech Transcription");
    const webRoute = buildStandaloneRoute();
    const registry: CodexPluginSkillRegistrySnapshot = {
      schema_version: "astrabridge-plugin-skill-registry-v1",
      generated_at: "2026-06-25T22:30:00+08:00",
      source_catalogs: [],
      plugins: [
        {
          schema_version: "astrabridge-plugin-skill-registry-v1",
          record_id: "plugin:browser",
          plugin_id: "browser",
          source_catalog_id: "official::browser",
          display_name: "Browser",
          install_status: "installed",
          enablement_status: "enabled",
          compatibility_status: "compatible",
          description: "Browser tooling",
          compatibility_warnings: [],
          notes: [],
        },
      ],
      skills: [
        {
          schema_version: "astrabridge-plugin-skill-registry-v1",
          record_id: "skill:imagegen",
          skill_name: "imagegen",
          source_catalog_id: "local::skills",
          display_name: "imagegen",
          install_status: "installed",
          enablement_status: "disabled",
          compatibility_status: "compatible",
          description: "Image generation skill",
          effective_enablement_status: "disabled",
          compatibility_warnings: [],
          notes: [],
        },
      ],
      notes: [],
    };

    renderPanel({
      routes: [visionRoute, imageRoute, speechRoute, webRoute],
      managementEntries: [visionRoute, imageRoute, speechRoute, webRoute].map(buildManagementEntry),
      pluginSkillRegistry: registry,
    });

    expect(screen.getAllByText("Related plugin and skill context").length).toBeGreaterThan(0);
    expect(screen.getByText("Browser")).toBeInTheDocument();
    expect(screen.getAllByText("plugin available").length).toBeGreaterThan(0);
    expect(screen.getAllByText("imagegen").length).toBeGreaterThan(0);
    expect(screen.getAllByText("skill disabled").length).toBeGreaterThan(0);
    expect(screen.getAllByText("OpenAI Primary Runtime").length).toBeGreaterThan(0);
    expect(screen.getAllByText("plugin missing").length).toBeGreaterThan(0);
    expect(screen.getByText("Standalone web lane")).toBeInTheDocument();
    expect(screen.getByText("web.search stays separate from model-backed routing, and plugin or skill inventory does not reroute it.")).toBeInTheDocument();
  });
});
