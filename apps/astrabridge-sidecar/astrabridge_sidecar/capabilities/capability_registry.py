from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..model_catalog import effective_model_record, provider_model_records
from ..providers import get_provider_profile
from ..web_tool_service import web_lane_descriptor
from .specs import AdapterContract, CapabilitySpec, default_adapter_contracts, default_capability_specs


_CAPABILITY_MODALITY_HINTS = {
    "image.generate": ("text", "image"),
    "vision.analyze": ("text", "image"),
    "speech.transcribe": ("text", "audio"),
    "speech.synthesize": ("text", "audio"),
    "web.search": ("text",),
}


def _clean_string_list(values: Any) -> list[str]:
    items = values if isinstance(values, (list, tuple)) else [values]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


def _merge_modalities(base_modalities: list[str], capability_id: str) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in list(base_modalities) + list(_CAPABILITY_MODALITY_HINTS.get(capability_id, ())):
        text = str(item or "").strip().lower()
        if not text or text in seen:
            continue
        ordered.append(text)
        seen.add(text)
    return ordered or ["text"]


def _merge_models(*groups: Any) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in _clean_string_list(group):
            native = item.split("/", 1)[1] if "/" in item else item
            if native in seen:
                continue
            ordered.append(native)
            seen.add(native)
    return ordered


@dataclass(frozen=True)
class CapabilityCandidate:
    capability_id: str
    adapter_id: str
    provider_id: str | None
    model: str | None
    lane_type: str
    transport_mode: str
    source: str
    catalog_present: bool
    default_for_provider: bool
    recommended: bool
    input_modalities: tuple[str, ...]
    catalog_input_modalities: tuple[str, ...]
    provider_default_model: str | None
    provider_fallback_models: tuple[str, ...]
    eligibility_notes: tuple[str, ...]
    model_record: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "capability_id": self.capability_id,
            "adapter_id": self.adapter_id,
            "provider_id": self.provider_id,
            "model": self.model,
            "lane_type": self.lane_type,
            "transport_mode": self.transport_mode,
            "source": self.source,
            "catalog_present": self.catalog_present,
            "default_for_provider": self.default_for_provider,
            "recommended": self.recommended,
            "input_modalities": list(self.input_modalities),
            "catalog_input_modalities": list(self.catalog_input_modalities),
            "provider_default_model": self.provider_default_model,
            "provider_fallback_models": list(self.provider_fallback_models),
            "eligibility_notes": list(self.eligibility_notes),
        }
        if self.model_record:
            payload["model_record"] = dict(self.model_record)
        return payload


class CapabilityRegistry:
    def __init__(
        self,
        *,
        capability_specs: list[CapabilitySpec] | None = None,
        adapter_contracts: list[AdapterContract] | None = None,
    ) -> None:
        specs = capability_specs or default_capability_specs()
        adapters = adapter_contracts or default_adapter_contracts()
        self._specs = {spec.capability_id: spec for spec in specs}
        self._adapters = list(adapters)
        self._adapters_by_capability: dict[str, list[AdapterContract]] = {}
        for adapter in self._adapters:
            self._adapters_by_capability.setdefault(adapter.capability_id, []).append(adapter)

    def capability_ids(self) -> list[str]:
        return list(self._specs)

    def capability_spec(self, capability_id: str) -> CapabilitySpec:
        spec = self._specs.get(str(capability_id or "").strip())
        if spec is None:
            raise ValueError(f"Unknown capability id: {capability_id}")
        return spec

    def adapter_contracts(self, capability_id: str | None = None) -> list[AdapterContract]:
        if capability_id is None:
            return list(self._adapters)
        return list(self._adapters_by_capability.get(str(capability_id or "").strip(), []))

    def resolve_candidates(
        self,
        capability_id: str,
        configured_models: list[dict[str, Any]] | None = None,
        *,
        include_deprecated: bool = False,
    ) -> list[dict[str, Any]]:
        spec = self.capability_spec(capability_id)
        if spec.lane_type == "web_standalone":
            return [self.resolve_web_lane(capability_id)]
        candidates: list[CapabilityCandidate] = []
        for adapter in self.adapter_contracts(spec.capability_id):
            candidates.extend(
                self._resolve_adapter_candidates(
                    spec,
                    adapter,
                    configured_models=configured_models,
                    include_deprecated=include_deprecated,
                )
            )
        return [candidate.to_dict() for candidate in self._sort_candidates(candidates)]

    def preferred_candidate(
        self,
        capability_id: str,
        configured_models: list[dict[str, Any]] | None = None,
        *,
        include_deprecated: bool = False,
    ) -> dict[str, Any] | None:
        candidates = self.resolve_candidates(
            capability_id,
            configured_models,
            include_deprecated=include_deprecated,
        )
        return candidates[0] if candidates else None

    def resolve_web_lane(self, capability_id: str) -> dict[str, Any]:
        spec = self.capability_spec(capability_id)
        if spec.lane_type != "web_standalone":
            raise ValueError(f"Capability {capability_id} is not a standalone web lane.")
        candidate = self._standalone_candidate(spec).to_dict()
        candidate["lane_descriptor"] = web_lane_descriptor()
        return candidate

    def resolve_model_backed_candidates(
        self,
        capability_id: str,
        configured_models: list[dict[str, Any]] | None = None,
        *,
        include_deprecated: bool = False,
    ) -> list[dict[str, Any]]:
        spec = self.capability_spec(capability_id)
        if spec.lane_type != "model_backed":
            raise ValueError(f"Capability {capability_id} is not model-backed and must not enter the model router.")
        return self.resolve_candidates(
            capability_id,
            configured_models,
            include_deprecated=include_deprecated,
        )

    def _standalone_candidate(self, spec: CapabilitySpec) -> CapabilityCandidate:
        return CapabilityCandidate(
            capability_id=spec.capability_id,
            adapter_id=f"{spec.capability_id}.standalone",
            provider_id=None,
            model=None,
            lane_type=spec.lane_type,
            transport_mode=spec.transport_mode,
            source="standalone_lane",
            catalog_present=True,
            default_for_provider=True,
            recommended=True,
            input_modalities=tuple(_CAPABILITY_MODALITY_HINTS.get(spec.capability_id, ("text",))),
            catalog_input_modalities=tuple(_CAPABILITY_MODALITY_HINTS.get(spec.capability_id, ("text",))),
            provider_default_model=None,
            provider_fallback_models=(),
            eligibility_notes=(
                "Standalone web lane; not resolved through provider/model selection.",
                "Search result interpretation is delegated to the caller LLM.",
            ),
            model_record=None,
        )

    def _resolve_adapter_candidates(
        self,
        spec: CapabilitySpec,
        adapter: AdapterContract,
        *,
        configured_models: list[dict[str, Any]] | None,
        include_deprecated: bool,
    ) -> list[CapabilityCandidate]:
        profile = get_provider_profile(adapter.provider_id)
        catalog_records = provider_model_records(
            adapter.provider_id,
            configured_models,
            include_disabled=False,
            include_deprecated=include_deprecated,
        )
        matching_catalog_records = [
            record for record in catalog_records if self._model_matches_adapter(adapter, str(record.get("native_model") or ""))
        ]
        models = _merge_models(
            adapter.model_match,
            [record.get("native_model") for record in matching_catalog_records],
            profile.default_model,
            profile.fallback_models,
        )
        candidates: list[CapabilityCandidate] = []
        for native_model in models:
            if not self._model_matches_adapter(adapter, native_model):
                continue
            record = effective_model_record(adapter.provider_id, native_model, configured_models)
            catalog_modalities = _clean_string_list((record or {}).get("input_modalities") or profile.context_policy.default_input_modalities)
            resolved_modalities = _merge_modalities(catalog_modalities, spec.capability_id)
            source = self._candidate_source(adapter, profile, native_model, record)
            notes = self._eligibility_notes(spec, adapter, profile, native_model, record, source, catalog_modalities, resolved_modalities)
            candidates.append(
                CapabilityCandidate(
                    capability_id=spec.capability_id,
                    adapter_id=adapter.adapter_id,
                    provider_id=adapter.provider_id,
                    model=native_model,
                    lane_type=spec.lane_type,
                    transport_mode=spec.transport_mode,
                    source=source,
                    catalog_present=record is not None,
                    default_for_provider=bool((record or {}).get("default_for_provider", native_model == profile.default_model)),
                    recommended=bool((record or {}).get("recommended", native_model == profile.default_model)),
                    input_modalities=tuple(resolved_modalities),
                    catalog_input_modalities=tuple(catalog_modalities),
                    provider_default_model=profile.default_model,
                    provider_fallback_models=tuple(profile.fallback_models),
                    eligibility_notes=tuple(notes),
                    model_record=dict(record) if record else None,
                )
            )
        return candidates

    def _model_matches_adapter(self, adapter: AdapterContract, native_model: str) -> bool:
        if not adapter.model_match:
            return True
        full_id = f"{adapter.provider_id}/{native_model}"
        return native_model in adapter.model_match or full_id in adapter.model_match

    def _candidate_source(
        self,
        adapter: AdapterContract,
        profile: Any,
        native_model: str,
        record: dict[str, Any] | None,
    ) -> str:
        if record is not None:
            if native_model == profile.default_model:
                return "catalog_default_model"
            if native_model in profile.fallback_models:
                return "catalog_fallback_model"
            return "catalog_model"
        if native_model == profile.default_model:
            return "provider_default_model"
        if native_model in profile.fallback_models:
            return "provider_fallback_model"
        if native_model in adapter.model_match:
            return "adapter_override"
        return "inferred"

    def _eligibility_notes(
        self,
        spec: CapabilitySpec,
        adapter: AdapterContract,
        profile: Any,
        native_model: str,
        record: dict[str, Any] | None,
        source: str,
        catalog_modalities: list[str],
        resolved_modalities: list[str],
    ) -> list[str]:
        notes = [
            f"Eligible through adapter `{adapter.adapter_id}` for capability `{spec.capability_id}`.",
            f"Provider eligibility rule: {spec.provider_eligibility_rule}.",
        ]
        if record is None:
            notes.append("Model is not currently present in the effective model catalog; adapter override or provider defaults keep it eligible.")
        else:
            notes.append(f"Model catalog source status: {record.get('source_status') or 'unknown'}.")
        if native_model == profile.default_model:
            notes.append("Provider default model candidate.")
        elif native_model in profile.fallback_models:
            notes.append("Provider fallback model candidate.")
        if list(catalog_modalities) != list(resolved_modalities):
            notes.append(
                "Resolved input modalities were expanded from catalog/profile defaults using capability-specific modality hints."
            )
        return notes

    def _sort_candidates(self, candidates: list[CapabilityCandidate]) -> list[CapabilityCandidate]:
        source_rank = {
            "catalog_default_model": 0,
            "catalog_model": 1,
            "catalog_fallback_model": 2,
            "provider_default_model": 3,
            "provider_fallback_model": 4,
            "adapter_override": 5,
            "inferred": 6,
        }
        return sorted(
            candidates,
            key=lambda item: (
                0 if item.default_for_provider else 1,
                0 if item.recommended else 1,
                source_rank.get(item.source, 99),
                str(item.provider_id or ""),
                str(item.model or ""),
            ),
        )


def default_capability_registry() -> CapabilityRegistry:
    return CapabilityRegistry()
