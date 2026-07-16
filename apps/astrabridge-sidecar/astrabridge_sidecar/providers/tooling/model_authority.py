from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


AuthorityTier = Literal["A", "B", "C", "D"]
SUPPORTED_APPLY_PATCH_TOOL_TYPES = {"freeform", "json"}
STRUCTURED_MCP_POLICIES = {"verified", "conservative"}


@dataclass(frozen=True)
class AuthorityAssessment:
    tier: AuthorityTier
    reason: str
    ui_warnings: tuple[str, ...] = field(default_factory=tuple)
    parallel_tool_call_status: str = "unsupported"
    command_execution_status: str = "unknown"
    command_execution_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "authority_tier": self.tier,
            "authority_reason": self.reason,
            "parallel_tool_call_status": self.parallel_tool_call_status,
            "command_execution_status": self.command_execution_status,
            "command_execution_note": self.command_execution_note,
            "authority_ui_warnings": list(self.ui_warnings),
        }


def normalize_apply_patch_tool_type(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    if normalized in SUPPORTED_APPLY_PATCH_TOOL_TYPES:
        return normalized
    return None


def has_structured_tool_surface(model: dict[str, Any]) -> bool:
    apply_patch_tool_type = normalize_apply_patch_tool_type(model.get("apply_patch_tool_type"))
    supports_mcp_tools = bool(model.get("supports_mcp_tools", False))
    mcp_policy = str(model.get("mcp_tool_call_policy") or "unsupported").strip().lower()
    return bool(apply_patch_tool_type or (supports_mcp_tools and mcp_policy in STRUCTURED_MCP_POLICIES))


def assess_model_authority(model: dict[str, Any]) -> AuthorityAssessment:
    codex_agent_enabled = bool(model.get("codex_agent_enabled", True))
    supports_tool_calls = has_structured_tool_surface(model)
    supports_parallel = bool(model.get("supports_parallel_tool_calls", False))
    mcp_policy = str(model.get("mcp_tool_call_policy") or "unsupported").strip().lower()
    tool_mode = str(model.get("tool_mode") or "").strip().lower()
    apply_patch_tool_type = normalize_apply_patch_tool_type(model.get("apply_patch_tool_type"))
    command_execution_status = str(model.get("command_execution_status") or "unknown").strip().lower() or "unknown"
    command_execution_note = str(model.get("command_execution_note") or "").strip()
    ui_warnings: list[str] = []
    _append_command_execution_warning(
        ui_warnings,
        command_execution_status=command_execution_status,
        command_execution_note=command_execution_note,
    )

    if not codex_agent_enabled:
        return AuthorityAssessment(
            tier="D",
            reason="Model is not exposed as a Codex agent model.",
            ui_warnings=("This model is not eligible for agent mode.", *ui_warnings),
            parallel_tool_call_status="disabled",
            command_execution_status=command_execution_status,
            command_execution_note=command_execution_note,
        )

    if not supports_tool_calls:
        return AuthorityAssessment(
            tier="C",
            reason="Model has no verified structured tool-calling surface.",
            ui_warnings=("Tool calling is unavailable or unverified for this model; keep it in review/explain mode.", *ui_warnings),
            parallel_tool_call_status="disabled",
            command_execution_status=command_execution_status,
            command_execution_note=command_execution_note,
        )

    if apply_patch_tool_type and mcp_policy in STRUCTURED_MCP_POLICIES and tool_mode != "propose_only":
        tier: AuthorityTier = "A" if tool_mode in {"", "native", "full"} else "B"
    elif tool_mode == "propose_only":
        tier = "B"
    else:
        tier = "B"

    if tier == "A":
        reason = "Model can participate in read/write/tool workflows with guarded tool execution."
    else:
        reason = "Model should stay in review/propose mode unless validation or approval promotes the action."
        ui_warnings.append("This model should propose changes before apply/execute actions.")

    if supports_parallel:
        parallel_status = "verified"
    else:
        parallel_status = "serial_only"
        ui_warnings.append("Parallel tool calls are disabled unless this model is explicitly verified for parallel execution.")

    if command_execution_status == "verified":
        command_execution_note = command_execution_note or "Provider-backed validation observed command execution."

    return AuthorityAssessment(
        tier=tier,
        reason=reason,
        ui_warnings=tuple(ui_warnings),
        parallel_tool_call_status=parallel_status,
        command_execution_status=command_execution_status,
        command_execution_note=command_execution_note,
    )


def _append_command_execution_warning(
    ui_warnings: list[str],
    *,
    command_execution_status: str,
    command_execution_note: str,
) -> None:
    if command_execution_status in {"partial_no_command_execution", "completed_without_command_execution"}:
        ui_warnings.append(
            "Provider-backed code-agent validation is only partial: turns may complete without any observable command execution."
        )
        if command_execution_note:
            ui_warnings.append(command_execution_note)
