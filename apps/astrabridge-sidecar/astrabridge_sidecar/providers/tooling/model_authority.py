from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


AuthorityTier = Literal["A", "B", "C", "D"]


@dataclass(frozen=True)
class AuthorityAssessment:
    tier: AuthorityTier
    reason: str
    ui_warnings: tuple[str, ...] = field(default_factory=tuple)
    parallel_tool_call_status: str = "unsupported"

    def to_dict(self) -> dict[str, Any]:
        return {
            "authority_tier": self.tier,
            "authority_reason": self.reason,
            "parallel_tool_call_status": self.parallel_tool_call_status,
            "authority_ui_warnings": list(self.ui_warnings),
        }


def assess_model_authority(model: dict[str, Any]) -> AuthorityAssessment:
    codex_agent_enabled = bool(model.get("codex_agent_enabled", True))
    supports_tool_calls = bool(model.get("supports_tool_calls", model.get("supports_mcp_tools", False) or model.get("apply_patch_tool_type")))
    supports_parallel = bool(model.get("supports_parallel_tool_calls", False))
    mcp_policy = str(model.get("mcp_tool_call_policy") or "unsupported")
    tool_mode = str(model.get("tool_mode") or "").strip().lower()
    apply_patch_tool_type = model.get("apply_patch_tool_type")
    ui_warnings: list[str] = []

    if not codex_agent_enabled:
        return AuthorityAssessment(
            tier="D",
            reason="Model is not exposed as a Codex agent model.",
            ui_warnings=("This model is not eligible for agent mode.",),
            parallel_tool_call_status="disabled",
        )

    if not supports_tool_calls:
        return AuthorityAssessment(
            tier="C",
            reason="Model has no verified structured tool-calling surface.",
            ui_warnings=("Tool calling is unavailable or unverified for this model; keep it in review/explain mode.",),
            parallel_tool_call_status="disabled",
        )

    if apply_patch_tool_type and mcp_policy in {"verified", "conservative"} and tool_mode != "propose_only":
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

    return AuthorityAssessment(
        tier=tier,
        reason=reason,
        ui_warnings=tuple(ui_warnings),
        parallel_tool_call_status=parallel_status,
    )
