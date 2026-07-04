import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { type ComponentProps, useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  CapabilityArtifactEntry,
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

function buildNoCandidateRoute(capabilityId: string, displayName: string): CapabilityRouteEntry {
  return {
    capability_id: capabilityId,
    display_name: displayName,
    lane_type: "model_backed",
    transport_mode: "request_response",
    route_mode: "auto",
    route_record: { capability_id: capabilityId, mode: "auto", provider_id: null, model: null },
    resolution_status: "no_capability_candidate",
    resolved_candidate: null,
    candidates: [],
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
  onRunProviderSmoke?: ReturnType<typeof vi.fn>;
  onInstallMcpPreset?: ReturnType<typeof vi.fn>;
  smokeResults?: ComponentProps<typeof CapabilityRoutesPanel>["smokeResults"];
  providerCredentials?: ComponentProps<typeof CapabilityRoutesPanel>["providerCredentials"];
  artifacts?: CapabilityArtifactEntry[];
  toMediaSrc?: (path: string) => string;
};

function renderPanel(options: RenderPanelOptions = {}) {
  const onSave = options.onSave ?? vi.fn();
  const onRunSmoke = options.onRunSmoke ?? vi.fn();
  const onRunProviderSmoke = options.onRunProviderSmoke ?? vi.fn();
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
        smokeResults={options.smokeResults ?? {}}
        smokePendingCapabilityId={null}
        isSmokePending={false}
        artifacts={options.artifacts ?? [
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
        providerCredentials={
          options.providerCredentials ?? {
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
          }
        }
        mcpRuntimeVisible={true}
        mcpRuntimeToolCount={5}
        mcpVisibilityLoading={false}
        mcpVisibilityError={false}
        isInstallingMcpPreset={false}
        toMediaSrc={options.toMediaSrc ?? ((path) => `file://${path}`)}
        onInstallMcpPreset={onInstallMcpPreset}
        onSave={onSave}
        onRunSmoke={onRunSmoke}
        onRunProviderSmoke={onRunProviderSmoke}
      />
    );
  }

  render(<Harness />);
  return { onSave, onRunSmoke, onRunProviderSmoke, onInstallMcpPreset };
}

describe("CapabilityRoutesPanel", () => {
  afterEach(() => cleanup());

  it("renders route details and saves a pinned candidate", () => {
    const { onSave } = renderPanel();

    expect(screen.getByText("Multimodal routes")).toBeInTheDocument();
    expect(screen.getByText("Choose auto routing or pin a provider/model for each multimodal capability. Web stays standalone.")).toBeInTheDocument();
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

  it("renders image artifact previews without spilling text into the image frame", () => {
    const imageRoute = buildModelRoute("image.generate", "Image Generation", [
      buildModelCandidate("image.generate", "image.generate.yunwu.v1", "yunwu", "gpt-image-2"),
    ]);
    renderPanel({
      routes: [imageRoute],
      managementEntries: [buildManagementEntry(imageRoute)],
      artifacts: [
        {
          artifact_id: "asset-1",
          capability_id: "image.generate",
          provider_id: "yunwu",
          model: "gpt-image-2",
          saved_at: "2026-06-27T01:00:00+08:00",
          summary_path: "D:/AstraBridge/workspace/.astrabridge/assets/generated/asset_manifest.json",
          relative_summary_path: ".astrabridge/assets/generated/asset_manifest.json",
          artifact_refs: [
            {
              artifact_type: "image",
              path: "D:/AstraBridge/workspace/.astrabridge/assets/generated/asset-1.png",
              relative_path: ".astrabridge/assets/generated/asset-1.png",
              exists: true,
              mime_type: "image/png",
            },
          ],
          preview: {
            kind: "image",
            text: "agent_bench_step14_transparent_asset",
            audio_path: "",
            image_path: "D:/AstraBridge/workspace/.astrabridge/assets/generated/asset-1.png",
          },
          metadata: { transparency_status: "passed" },
        },
      ],
      toMediaSrc: (path) => `media://${path}`,
    });

    const preview = document.querySelector(".capability-artifact-preview");
    const image = preview?.querySelector("img");

    expect(image).not.toBeNull();
    expect(image).toHaveAttribute("src", "media://D:/AstraBridge/workspace/.astrabridge/assets/generated/asset-1.png");
    expect(preview?.querySelector("p")).toBeNull();
    expect(screen.getByText("asset-1")).toBeInTheDocument();
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

  it("runs explicit provider smoke only from a configured resolved route", () => {
    const onRunProviderSmoke = vi.fn();
    renderPanel({ onRunProviderSmoke });

    expect(screen.getByTestId("capability-provider-smoke-vision.analyze")).toBeDisabled();
    expect(screen.getByTestId("capability-provider-smoke-skip-vision.analyze")).toHaveTextContent("Explicit authorization is required");
    fireEvent.click(screen.getByLabelText("Allow this one real provider smoke run"));
    fireEvent.click(screen.getByRole("button", { name: "Run provider smoke" }));

    expect(onRunProviderSmoke).toHaveBeenCalledWith("vision.analyze");
  });

  it("shows provider smoke errors without hiding the smoke status", () => {
    renderPanel({
      smokeResults: {
        "vision.analyze": {
          schema_version: "astrabridge-capability-smoke-result-v1",
          capability_id: "vision.analyze",
          mode: "provider",
          status: "fail",
          provider_invoked: false,
          provider_requested: true,
          case_id: "dry_run_vision_analyze",
          route: {
            route_mode: "auto",
            resolution_status: "ok",
            resolved_candidate: visionRoute.resolved_candidate,
            error: null,
          },
          sanitized_request: {},
          sanitized_response: {
            provider_error: "qwen vision adapter requires an api_key or DASHSCOPE_API_KEY.",
          },
          artifact_refs: [],
          evidence_refs: [],
          created_at: "2026-06-25T01:00:00Z",
        },
      },
    });

    expect(screen.getByText("Last smoke: provider · fail / dry_run_vision_analyze / provider not called")).toBeInTheDocument();
    expect(screen.getByText("qwen vision adapter requires an api_key or DASHSCOPE_API_KEY.")).toBeInTheDocument();
  });

  it("shows multimodal dry-run pass states for vision and speech capabilities", () => {
    const speechRoute = buildModelRoute("speech.transcribe", "Speech Transcription", [
      buildModelCandidate("speech.transcribe", "speech.transcribe.qwen-asr.v1", "qwen", "qwen3-asr-flash"),
    ]);

    renderPanel({
      routes: [visionRoute, speechRoute],
      managementEntries: [visionRoute, speechRoute].map(buildManagementEntry),
      smokeResults: {
        "vision.analyze": {
          schema_version: "astrabridge-capability-smoke-result-v1",
          capability_id: "vision.analyze",
          mode: "dry_run",
          status: "pass",
          provider_invoked: false,
          provider_requested: false,
          case_id: "dry_run_vision_analyze",
          route: { route_mode: "auto", resolution_status: "ok", resolved_candidate: visionRoute.resolved_candidate, error: null },
          sanitized_request: { fixture: "astrabridge-title-card" },
          sanitized_response: { elapsed_ms: 12 },
          artifact_refs: [],
          evidence_refs: [],
          created_at: "2026-06-25T01:00:00Z",
        },
        "speech.transcribe": {
          schema_version: "astrabridge-capability-smoke-result-v1",
          capability_id: "speech.transcribe",
          mode: "dry_run",
          status: "pass",
          provider_invoked: false,
          provider_requested: false,
          case_id: "dry_run_speech_transcribe",
          route: { route_mode: "auto", resolution_status: "ok", resolved_candidate: speechRoute.resolved_candidate, error: null },
          sanitized_request: { fixture: "astrabridge-speech-smoke.wav" },
          sanitized_response: { elapsed_ms: 19 },
          artifact_refs: [],
          evidence_refs: [],
          created_at: "2026-06-25T01:00:00Z",
        },
      },
    });

    expect(screen.getByText("Last smoke: dry-run · pass / dry_run_vision_analyze / provider not called / elapsed 12 ms")).toBeInTheDocument();
    expect(screen.getByText("Last smoke: dry-run · pass / dry_run_speech_transcribe / provider not called / elapsed 19 ms")).toBeInTheDocument();
  });

  it("shows provider smoke as skipped when the resolved credential is not configured", () => {
    renderPanel({
      providerCredentials: {
        qwen: {
          provider_id: "qwen",
          label: "Qwen",
          enabled: true,
          auth_mode: "os_keychain",
          status: "missing",
        },
      },
    });

    expect(screen.getByTestId("capability-provider-smoke-vision.analyze")).toBeDisabled();
    expect(screen.getByTestId("capability-provider-smoke-skip-vision.analyze")).toHaveTextContent("Provider smoke skipped");
    expect(screen.getByText("The resolved provider credential is missing.")).toBeInTheDocument();
  });

  it("shows an unconfigured route and skips provider smoke instead of reporting a failure", () => {
    const noRoute = buildNoCandidateRoute("speech.transcribe", "Speech Transcription");

    renderPanel({
      routes: [noRoute],
      managementEntries: [buildManagementEntry(noRoute)],
      providerCredentials: {},
      smokeResults: {
        "speech.transcribe": {
          schema_version: "astrabridge-capability-smoke-result-v1",
          capability_id: "speech.transcribe",
          mode: "dry_run",
          status: "skipped",
          provider_invoked: false,
          provider_requested: false,
          case_id: "dry_run_speech_transcribe",
          route: { route_mode: "auto", resolution_status: "no_capability_candidate", resolved_candidate: null, error: "no_capability_candidate" },
          sanitized_request: {},
          sanitized_response: {},
          artifact_refs: [],
          evidence_refs: [],
          created_at: "2026-06-25T01:00:00Z",
        },
      },
    });

    expect(screen.getAllByText("no candidate").length).toBeGreaterThan(0);
    expect(screen.getByText("Last smoke: dry-run · skipped / dry_run_speech_transcribe / provider not called")).toBeInTheDocument();
    expect(screen.getByText("No resolved provider route is available, so the real provider smoke was not started.")).toBeInTheDocument();
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

  it("keeps showing plugin and skill guidance during background registry refreshes", () => {
    const imageRoute = buildModelRoute("image.generate", "Image Generation");
    const registry: CodexPluginSkillRegistrySnapshot = {
      schema_version: "astrabridge-plugin-skill-registry-v1",
      generated_at: "2026-06-27T01:45:00+08:00",
      source_catalogs: [],
      plugins: [],
      skills: [
        {
          schema_version: "astrabridge-plugin-skill-registry-v1",
          record_id: "skill:imagegen",
          skill_name: "imagegen",
          source_catalog_id: "local::skills",
          display_name: "imagegen",
          install_status: "installed",
          enablement_status: "enabled",
          compatibility_status: "compatible",
          description: "Image generation skill",
          effective_enablement_status: "enabled",
          compatibility_warnings: [],
          notes: [],
        },
      ],
      notes: [],
    };

    renderPanel({
      routes: [imageRoute],
      managementEntries: [buildManagementEntry(imageRoute)],
      pluginSkillRegistry: registry,
      pluginSkillRegistryLoading: true,
    });

    expect(screen.queryByText("Checking plugin and skill inventory...")).not.toBeInTheDocument();
    expect(screen.getAllByText("imagegen").length).toBeGreaterThan(0);
    expect(screen.getByText("skill enabled")).toBeInTheDocument();
  });
});
