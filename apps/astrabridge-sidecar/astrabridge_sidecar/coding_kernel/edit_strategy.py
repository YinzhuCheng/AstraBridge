from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Literal


EditOperation = Literal["apply_patch", "replace_file", "write_file", "structured_edit", "propose_only"]
EditSizeClass = Literal["small", "medium", "large"]

_VALID_OPERATIONS = {"apply_patch", "replace_file", "write_file", "structured_edit", "propose_only"}


@dataclass(frozen=True)
class EditStrategyDecision:
    requested_operation: EditOperation | None
    policy_operation: EditOperation
    selected_operation: EditOperation
    size_class: EditSizeClass
    authority_tier: str
    provider_id: str | None
    model_id: str | None
    profile_id: str | None
    reason: str
    available_operations: tuple[EditOperation, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def classify_edit_size(*, estimated_bytes: int, edit_count: int = 1) -> EditSizeClass:
    score = max(int(estimated_bytes or 0), int(edit_count or 0) * 120)
    if score <= 4_000:
        return "small"
    if score <= 24_000:
        return "medium"
    return "large"


def select_edit_strategy(
    *,
    model: dict[str, Any],
    requested_operation: str | None,
    available_operations: Iterable[str],
    target_exists: bool,
    estimated_bytes: int,
    edit_count: int = 1,
    profile_id: str | None = None,
    provider_id: str | None = None,
    model_id: str | None = None,
) -> EditStrategyDecision:
    available = tuple(_normalize_operation(item) for item in available_operations if _normalize_operation(item))
    if not available:
        raise ValueError("No executable edit operations are available for this payload.")

    size_class = classify_edit_size(estimated_bytes=estimated_bytes, edit_count=edit_count)
    authority_tier = str(model.get("authority_tier") or "B").strip() or "B"
    requested = _normalize_operation(requested_operation)
    policy_raw = str(((model.get("edit_policy") or {}).get(size_class) or "")).strip().lower() or "patch"
    policy_operation = _policy_to_operation(policy_raw, target_exists=target_exists)

    if authority_tier in {"C", "D"} and "propose_only" in available:
        return EditStrategyDecision(
            requested_operation=requested,
            policy_operation=policy_operation,
            selected_operation="propose_only",
            size_class=size_class,
            authority_tier=authority_tier,
            provider_id=provider_id,
            model_id=model_id,
            profile_id=profile_id,
            reason="Model authority is limited to review/propose mode.",
            available_operations=available,
        )

    if requested == "propose_only" and "propose_only" in available:
        return EditStrategyDecision(
            requested_operation=requested,
            policy_operation=policy_operation,
            selected_operation="propose_only",
            size_class=size_class,
            authority_tier=authority_tier,
            provider_id=provider_id,
            model_id=model_id,
            profile_id=profile_id,
            reason="Explicit propose-only request preserved.",
            available_operations=available,
        )

    if policy_operation in available:
        return EditStrategyDecision(
            requested_operation=requested,
            policy_operation=policy_operation,
            selected_operation=policy_operation,
            size_class=size_class,
            authority_tier=authority_tier,
            provider_id=provider_id,
            model_id=model_id,
            profile_id=profile_id,
            reason=f"Selected from provider edit policy for {size_class} edits.",
            available_operations=available,
        )

    requested_fallback = requested if requested in available else None
    compatible_operation = _compatible_policy_fallback(policy_operation, available)
    selected = compatible_operation or requested_fallback or _best_available_operation(available, target_exists=target_exists)
    reason = (
        f"Provider policy preferred {policy_operation}, but payload only supports {selected}."
        if selected != policy_operation
        else f"Selected from provider edit policy for {size_class} edits."
    )
    return EditStrategyDecision(
        requested_operation=requested,
        policy_operation=policy_operation,
        selected_operation=selected,
        size_class=size_class,
        authority_tier=authority_tier,
        provider_id=provider_id,
        model_id=model_id,
        profile_id=profile_id,
        reason=reason,
        available_operations=available,
    )


def _normalize_operation(value: str | None) -> EditOperation | None:
    candidate = str(value or "").strip().lower()
    if candidate in _VALID_OPERATIONS:
        return candidate  # type: ignore[return-value]
    return None


def _policy_to_operation(value: str, *, target_exists: bool) -> EditOperation:
    normalized = str(value or "").strip().lower()
    if normalized == "patch":
        return "apply_patch"
    if normalized == "structured_edit":
        return "structured_edit"
    if normalized == "replace":
        return "replace_file" if target_exists else "write_file"
    return "propose_only"


def _compatible_policy_fallback(policy_operation: EditOperation, available: tuple[EditOperation, ...]) -> EditOperation | None:
    if policy_operation == "apply_patch" and "structured_edit" in available:
        return "structured_edit"
    if policy_operation == "structured_edit" and "apply_patch" in available:
        return "apply_patch"
    if policy_operation in {"replace_file", "write_file"}:
        if "replace_file" in available:
            return "replace_file"
        if "write_file" in available:
            return "write_file"
    return None


def _best_available_operation(available: tuple[EditOperation, ...], *, target_exists: bool) -> EditOperation:
    for candidate in (
        "replace_file" if target_exists else "write_file",
        "write_file",
        "apply_patch",
        "structured_edit",
        "propose_only",
    ):
        if candidate in available:
            return candidate  # type: ignore[return-value]
    return available[0]
