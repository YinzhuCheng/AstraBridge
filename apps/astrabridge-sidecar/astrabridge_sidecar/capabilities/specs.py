from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


CAPABILITY_CONTRACT_SCHEMA_VERSION = "astrabridge-capability-contract-v1"
ADAPTER_CONTRACT_SCHEMA_VERSION = "astrabridge-adapter-contract-v1"

LaneType = Literal["model_backed", "web_standalone"]
TransportMode = Literal["request_response", "stream_sse", "realtime_ws"]
ValueType = Literal[
    "string",
    "integer",
    "number",
    "boolean",
    "object",
    "artifact_ref",
    "text_part",
    "image_part",
    "audio_part",
    "array[string]",
    "array[object]",
    "array[artifact_ref]",
    "array[text_part]",
    "array[image_part]",
    "array[audio_part]",
]


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _clean_string_list(values: Any) -> list[str]:
    items = values if isinstance(values, (list, tuple)) else [values]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


@dataclass(frozen=True)
class CapabilityField:
    name: str
    value_type: ValueType
    required: bool = False
    description: str = ""
    repeated: bool = False
    nullable: bool = False
    enum_values: tuple[str, ...] = ()
    default_value: Any = None

    @classmethod
    def from_any(cls, payload: Any) -> "CapabilityField":
        if isinstance(payload, CapabilityField):
            return payload
        if not isinstance(payload, dict):
            raise TypeError("Capability field payload must be a dict.")
        name = _clean_text(payload.get("name"))
        value_type = _clean_text(payload.get("value_type") or payload.get("type"))
        if not name:
            raise ValueError("Capability field name is required.")
        if not value_type:
            raise ValueError(f"Capability field {name} is missing value_type.")
        return cls(
            name=name,
            value_type=value_type,  # type: ignore[arg-type]
            required=bool(payload.get("required", False)),
            description=_clean_text(payload.get("description")),
            repeated=bool(payload.get("repeated", False)),
            nullable=bool(payload.get("nullable", False)),
            enum_values=tuple(_clean_string_list(payload.get("enum_values") or payload.get("enum"))),
            default_value=payload.get("default_value", payload.get("default")),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "name": self.name,
            "value_type": self.value_type,
            "required": self.required,
            "description": self.description,
            "repeated": self.repeated,
            "nullable": self.nullable,
        }
        if self.enum_values:
            payload["enum_values"] = list(self.enum_values)
        if self.default_value is not None:
            payload["default_value"] = self.default_value
        return payload


@dataclass(frozen=True)
class CapabilitySchema:
    fields: tuple[CapabilityField, ...]
    required_fields: tuple[str, ...] = ()
    allow_additional_fields: bool = False
    envelope: str = "object"

    @classmethod
    def from_any(cls, payload: Any) -> "CapabilitySchema":
        if isinstance(payload, CapabilitySchema):
            return payload
        if not isinstance(payload, dict):
            raise TypeError("Capability schema payload must be a dict.")
        raw_fields = payload.get("fields") or []
        normalized_fields = tuple(CapabilityField.from_any(item) for item in raw_fields)
        known_names = {field.name for field in normalized_fields}
        required_fields = tuple(
            name for name in _clean_string_list(payload.get("required_fields")) if name in known_names
        )
        return cls(
            fields=normalized_fields,
            required_fields=required_fields,
            allow_additional_fields=bool(payload.get("allow_additional_fields", False)),
            envelope=_clean_text(payload.get("envelope") or "object") or "object",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fields": [field.to_dict() for field in self.fields],
            "required_fields": list(self.required_fields),
            "allow_additional_fields": self.allow_additional_fields,
            "envelope": self.envelope,
        }


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    display_name: str
    lane_type: LaneType
    transport_mode: TransportMode
    input_schema: CapabilitySchema
    output_schema: CapabilitySchema
    artifact_policy: str
    provider_eligibility_rule: str
    default_timeout_sec: int = 60
    smoke_status: str = "untested"
    schema_version: str = CAPABILITY_CONTRACT_SCHEMA_VERSION
    notes: tuple[str, ...] = ()

    @classmethod
    def from_any(cls, payload: Any) -> "CapabilitySpec":
        if isinstance(payload, CapabilitySpec):
            return payload
        if not isinstance(payload, dict):
            raise TypeError("Capability spec payload must be a dict.")
        capability_id = _clean_text(payload.get("capability_id"))
        lane_type = _clean_text(payload.get("lane_type"))
        transport_mode = _clean_text(payload.get("transport_mode"))
        if not capability_id:
            raise ValueError("Capability spec requires capability_id.")
        if lane_type not in {"model_backed", "web_standalone"}:
            raise ValueError(f"Capability {capability_id} has unsupported lane_type: {lane_type or '<missing>'}.")
        if transport_mode not in {"request_response", "stream_sse", "realtime_ws"}:
            raise ValueError(
                f"Capability {capability_id} has unsupported transport_mode: {transport_mode or '<missing>'}."
            )
        return cls(
            capability_id=capability_id,
            display_name=_clean_text(payload.get("display_name") or capability_id),
            lane_type=lane_type,  # type: ignore[arg-type]
            transport_mode=transport_mode,  # type: ignore[arg-type]
            input_schema=normalize_schema(payload.get("input_schema")),
            output_schema=normalize_schema(payload.get("output_schema")),
            artifact_policy=_clean_text(payload.get("artifact_policy") or "none") or "none",
            provider_eligibility_rule=_clean_text(payload.get("provider_eligibility_rule") or "explicit_adapter_only"),
            default_timeout_sec=max(1, int(payload.get("default_timeout_sec") or 60)),
            smoke_status=_clean_text(payload.get("smoke_status") or "untested") or "untested",
            schema_version=_clean_text(payload.get("schema_version") or CAPABILITY_CONTRACT_SCHEMA_VERSION),
            notes=tuple(_clean_string_list(payload.get("notes"))),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "capability_id": self.capability_id,
            "display_name": self.display_name,
            "lane_type": self.lane_type,
            "transport_mode": self.transport_mode,
            "input_schema": self.input_schema.to_dict(),
            "output_schema": self.output_schema.to_dict(),
            "artifact_policy": self.artifact_policy,
            "provider_eligibility_rule": self.provider_eligibility_rule,
            "default_timeout_sec": self.default_timeout_sec,
            "smoke_status": self.smoke_status,
        }
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


@dataclass(frozen=True)
class AdapterContract:
    adapter_id: str
    capability_id: str
    provider_id: str
    model_match: tuple[str, ...] = ()
    supports_streaming: bool = False
    supports_batch: bool = False
    normalization_rules: tuple[str, ...] = ()
    request_builder: str = ""
    response_parser: str = ""
    artifact_persister: str = ""
    smoke_case_id: str = ""
    schema_version: str = ADAPTER_CONTRACT_SCHEMA_VERSION

    @classmethod
    def from_any(cls, payload: Any) -> "AdapterContract":
        if isinstance(payload, AdapterContract):
            return payload
        if not isinstance(payload, dict):
            raise TypeError("Adapter contract payload must be a dict.")
        adapter_id = _clean_text(payload.get("adapter_id"))
        capability_id = _clean_text(payload.get("capability_id"))
        provider_id = _clean_text(payload.get("provider_id"))
        if not adapter_id or not capability_id or not provider_id:
            raise ValueError("Adapter contract requires adapter_id, capability_id, and provider_id.")
        return cls(
            adapter_id=adapter_id,
            capability_id=capability_id,
            provider_id=provider_id,
            model_match=tuple(_clean_string_list(payload.get("model_match"))),
            supports_streaming=bool(payload.get("supports_streaming", False)),
            supports_batch=bool(payload.get("supports_batch", False)),
            normalization_rules=tuple(_clean_string_list(payload.get("normalization_rules"))),
            request_builder=_clean_text(payload.get("request_builder")),
            response_parser=_clean_text(payload.get("response_parser")),
            artifact_persister=_clean_text(payload.get("artifact_persister")),
            smoke_case_id=_clean_text(payload.get("smoke_case_id")),
            schema_version=_clean_text(payload.get("schema_version") or ADAPTER_CONTRACT_SCHEMA_VERSION),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "adapter_id": self.adapter_id,
            "capability_id": self.capability_id,
            "provider_id": self.provider_id,
            "model_match": list(self.model_match),
            "supports_streaming": self.supports_streaming,
            "supports_batch": self.supports_batch,
            "normalization_rules": list(self.normalization_rules),
            "request_builder": self.request_builder,
            "response_parser": self.response_parser,
            "artifact_persister": self.artifact_persister,
            "smoke_case_id": self.smoke_case_id,
        }


def normalize_schema(payload: Any) -> CapabilitySchema:
    schema = CapabilitySchema.from_any(payload or {})
    required_names = set(schema.required_fields)
    fields: list[CapabilityField] = []
    seen: set[str] = set()
    for field in schema.fields:
        if field.name in seen:
            continue
        fields.append(
            CapabilityField(
                name=field.name,
                value_type=field.value_type,
                required=field.required or field.name in required_names,
                description=field.description,
                repeated=field.repeated,
                nullable=field.nullable,
                enum_values=field.enum_values,
                default_value=field.default_value,
            )
        )
        seen.add(field.name)
    ordered_required = tuple(field.name for field in fields if field.required)
    return CapabilitySchema(
        fields=tuple(fields),
        required_fields=ordered_required,
        allow_additional_fields=schema.allow_additional_fields,
        envelope=schema.envelope,
    )


def normalize_capability_spec(payload: Any) -> CapabilitySpec:
    return CapabilitySpec.from_any(payload)


def normalize_adapter_contract(payload: Any) -> AdapterContract:
    return AdapterContract.from_any(payload)


def capability_spec_index(specs: list[CapabilitySpec] | tuple[CapabilitySpec, ...]) -> dict[str, CapabilitySpec]:
    return {spec.capability_id: spec for spec in specs}


def _field(name: str, value_type: ValueType, *, required: bool = False, description: str = "", repeated: bool = False) -> dict[str, Any]:
    return {
        "name": name,
        "value_type": value_type,
        "required": required,
        "description": description,
        "repeated": repeated,
    }


def default_capability_specs() -> list[CapabilitySpec]:
    return [
        normalize_capability_spec(
            {
                "capability_id": "web.search",
                "display_name": "Web Search",
                "lane_type": "web_standalone",
                "transport_mode": "request_response",
                "artifact_policy": "persist_research_record",
                "provider_eligibility_rule": "standalone_web_service_only",
                "default_timeout_sec": 20,
                "smoke_status": "existing_service_smoke",
                "notes": [
                    "Search remains a standalone tool lane.",
                    "Search result interpretation is performed by the caller LLM, not by the search service.",
                ],
                "input_schema": {
                    "fields": [
                        _field("queries", "array[string]", required=True, description="Search queries to execute."),
                        _field("dedupe", "boolean", description="Whether to deduplicate overlapping search results."),
                        _field("timeout_sec", "integer", description="Per-request timeout in seconds."),
                        _field("tool_context", "object", description="Sanitized project/task context for record keeping."),
                    ]
                },
                "output_schema": {
                    "fields": [
                        _field("record_id", "string", required=True, description="Persisted research record id."),
                        _field("path", "string", required=True, description="Persisted research record path."),
                        _field("result", "object", required=True, description="Structured search result payload."),
                    ]
                },
            }
        ),
        normalize_capability_spec(
            {
                "capability_id": "image.generate",
                "display_name": "Image Generation",
                "lane_type": "model_backed",
                "transport_mode": "request_response",
                "artifact_policy": "persist_generated_assets",
                "provider_eligibility_rule": "requires_image_generation_adapter",
                "default_timeout_sec": 300,
                "input_schema": {
                    "fields": [
                        _field("prompt", "string", required=True, description="Primary generation prompt."),
                        _field("image_inputs", "array[image_part]", description="Optional reference images."),
                        _field("size", "string", description="Requested canvas size."),
                        _field("quality", "string", description="Requested generation quality."),
                        _field("n", "integer", description="Requested image count."),
                        _field("background", "string", description="Requested image background mode."),
                    ]
                },
                "output_schema": {
                    "fields": [
                        _field("artifact_refs", "array[artifact_ref]", required=True, description="Generated asset references."),
                        _field("provider_id", "string", required=True, description="Resolved provider id."),
                        _field("model", "string", required=True, description="Resolved upstream model."),
                        _field("revised_prompt", "string", description="Upstream-revised prompt if returned."),
                    ]
                },
            }
        ),
        normalize_capability_spec(
            {
                "capability_id": "vision.analyze",
                "display_name": "Vision Analysis",
                "lane_type": "model_backed",
                "transport_mode": "request_response",
                "artifact_policy": "persist_optional_visual_artifacts",
                "provider_eligibility_rule": "requires_vision_adapter_and_image_inputs",
                "default_timeout_sec": 120,
                "input_schema": {
                    "fields": [
                        _field("prompt", "string", required=True, description="Vision task instruction."),
                        _field("image_inputs", "array[image_part]", required=True, description="One or more images to analyze."),
                        _field("detail", "string", description="Requested image detail level."),
                        _field("max_output_tokens", "integer", description="Optional output limit."),
                    ]
                },
                "output_schema": {
                    "fields": [
                        _field("text", "string", required=True, description="Primary natural-language answer."),
                        _field("provider_id", "string", required=True, description="Resolved provider id."),
                        _field("model", "string", required=True, description="Resolved upstream model."),
                        _field("annotations", "array[object]", description="Optional structured annotations."),
                    ]
                },
            }
        ),
        normalize_capability_spec(
            {
                "capability_id": "speech.transcribe",
                "display_name": "Speech Transcription",
                "lane_type": "model_backed",
                "transport_mode": "request_response",
                "artifact_policy": "persist_audio_request_and_transcript",
                "provider_eligibility_rule": "requires_transcription_adapter_and_audio_inputs",
                "default_timeout_sec": 180,
                "notes": ["Qwen ASR adapters must support the provider's audio-only content constraint."],
                "input_schema": {
                    "fields": [
                        _field("audio_inputs", "array[audio_part]", required=True, description="Audio parts to transcribe."),
                        _field("language_hint", "string", description="Optional language hint."),
                        _field("enable_itn", "boolean", description="Whether to enable inverse text normalization."),
                        _field("prompt", "string", description="Optional transcription instruction when supported by the provider."),
                    ]
                },
                "output_schema": {
                    "fields": [
                        _field("text", "string", required=True, description="Full transcript text."),
                        _field("language", "string", description="Detected or applied language."),
                        _field("segments", "array[object]", description="Optional time-coded segments."),
                        _field("annotations", "array[object]", description="Optional provider-specific annotations."),
                    ]
                },
            }
        ),
        normalize_capability_spec(
            {
                "capability_id": "speech.synthesize",
                "display_name": "Speech Synthesis",
                "lane_type": "model_backed",
                "transport_mode": "stream_sse",
                "artifact_policy": "persist_audio_output_and_text_sidecar",
                "provider_eligibility_rule": "requires_tts_adapter",
                "default_timeout_sec": 240,
                "notes": ["Streaming adapters may emit text and audio concurrently before final artifact persistence."],
                "input_schema": {
                    "fields": [
                        _field("text", "string", required=True, description="Text to synthesize."),
                        _field("voice", "string", description="Requested voice id."),
                        _field("audio_format", "string", description="Requested output audio format."),
                        _field("instructions", "string", description="Optional style or pronunciation instructions."),
                    ]
                },
                "output_schema": {
                    "fields": [
                        _field("artifact_refs", "array[artifact_ref]", required=True, description="Persisted audio artifact references."),
                        _field("text", "string", description="Text emitted or confirmed by the provider."),
                        _field("mime_type", "string", description="Output mime type."),
                        _field("duration_sec", "number", description="Audio duration when available."),
                    ]
                },
            }
        ),
    ]


def default_adapter_contracts() -> list[AdapterContract]:
    return [
        normalize_adapter_contract(
            {
                "adapter_id": "yunwu.image.generate.v1",
                "capability_id": "image.generate",
                "provider_id": "yunwu",
                "model_match": ["gpt-image-2", "gpt-image-2-all", "gpt-image-1", "flux-kontext-pro", "flux-kontext-max"],
                "supports_batch": True,
                "normalization_rules": ["persist_assets", "normalize_generation_result"],
                "request_builder": "yunwu_image_service.generate/edit payload builder",
                "response_parser": "yunwu_image_service result normalizer",
                "artifact_persister": "yunwu_image_service._persist_assets",
                "smoke_case_id": "yunwu_image_generate_smoke",
            }
        ),
        normalize_adapter_contract(
            {
                "adapter_id": "qwen.vision.chat.v1",
                "capability_id": "vision.analyze",
                "provider_id": "qwen",
                "model_match": ["qwen3.7-plus", "qwen3.6-flash", "qwen3-vl-plus", "qwen3-vl-flash"],
                "normalization_rules": ["image_url_or_data_uri", "chat_completion_text_extraction"],
                "request_builder": "chat completions image_url content builder",
                "response_parser": "chat completion visible text parser",
                "artifact_persister": "optional request/response smoke persistence",
                "smoke_case_id": "qwen_vision_smoke",
            }
        ),
        normalize_adapter_contract(
            {
                "adapter_id": "kimi.vision.chat.v1",
                "capability_id": "vision.analyze",
                "provider_id": "kimi",
                "model_match": ["kimi-k2.6", "kimi-k2.7-code", "kimi-k2.7-code-highspeed"],
                "normalization_rules": ["image_url_or_data_uri", "chat_completion_text_extraction"],
                "request_builder": "chat completions image_url content builder",
                "response_parser": "chat completion visible text parser",
                "artifact_persister": "optional request/response smoke persistence",
                "smoke_case_id": "kimi_vision_smoke",
            }
        ),
        normalize_adapter_contract(
            {
                "adapter_id": "qwen.asr.chat.v1",
                "capability_id": "speech.transcribe",
                "provider_id": "qwen",
                "model_match": ["qwen3-asr-flash"],
                "normalization_rules": ["audio_only_message_content", "asr_options_out_of_band", "chat_completion_text_extraction"],
                "request_builder": "chat completions audio-only content builder",
                "response_parser": "chat completion transcript parser",
                "artifact_persister": "persist transcript and raw response",
                "smoke_case_id": "qwen_asr_smoke",
            }
        ),
        normalize_adapter_contract(
            {
                "adapter_id": "qwen.tts.omni.v1",
                "capability_id": "speech.synthesize",
                "provider_id": "qwen",
                "model_match": ["qwen3.5-omni-plus", "qwen3.5-omni-flash", "qwen3-omni-flash"],
                "supports_streaming": True,
                "normalization_rules": ["sse_delta_audio_data", "modalities_text_audio", "persist_audio_sidecar"],
                "request_builder": "chat completions streaming audio builder",
                "response_parser": "sse chunk text/audio accumulator",
                "artifact_persister": "persist synthesized audio bytes and transcript text",
                "smoke_case_id": "qwen_omni_tts_smoke",
            }
        ),
    ]
