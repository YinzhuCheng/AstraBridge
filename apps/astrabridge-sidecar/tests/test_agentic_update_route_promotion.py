from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agentic_updates import (  # noqa: E402
    AGENTIC_UPDATE_DIFF_SCHEMA_VERSION,
    apply_execution_route_promotion_proposal,
    apply_metadata_only_proposal,
    agentic_update_proposal_template,
    build_agentic_update_diff,
    normalize_route_promotion_record,
    rollback_metadata_apply,
    run_agentic_update_validation_gates,
    validate_update_proposal,
)
from astrabridge_sidecar.providers.execution_route import (  # noqa: E402
    EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION,
    resolve_execution_route,
)


NOW = datetime(2026, 7, 27, tzinfo=timezone.utc)


class AgenticUpdateRoutePromotionTests(unittest.TestCase):
    def test_discovery_adds_kimi_k3_facts_but_no_execution_route_proof(self) -> None:
        provider = _provider()
        candidate = _kimi_candidate()
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            diff = build_agentic_update_diff(
                workspace_root=workspace,
                run_id="kimi-k3-docs",
                run_contract={
                    "scope": "provider_metadata",
                    "providers": ["kimi"],
                    "allow_network": False,
                    "apply_mode": "isolated_apply",
                },
                parser_output={"proposals": [candidate]},
                current_models=[],
                update_proposal=False,
            )
            records = list(diff["route_promotion"]["records"])
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["action"], "document")
            self.assertEqual(records[0]["target_state"], "documented")
            self.assertEqual(records[0]["required_gates"], [])
            self.assertEqual([change["change_type"] for change in diff["changes"]], ["added_model"])

            proposal = _proposal(
                run_id="kimi-k3-docs",
                contract={
                    "scope": "provider_metadata",
                    "providers": ["kimi"],
                    "allow_network": False,
                    "apply_mode": "isolated_apply",
                },
                diff=diff,
            )
            applied = apply_metadata_only_proposal(
                workspace_root=workspace,
                run_id="kimi-k3-docs",
                proposal=proposal,
                approval=_approval(),
                router_config_snapshot={"providers": [provider], "models": [], "reasoning": {}, "capability_routes": {}},
                generated_catalog_snapshot=_catalog_snapshot([]),
            )
            stored = json.loads(Path(applied["touched"]["router_config"]).read_text(encoding="utf-8"))
            model = next(item for item in stored["models"] if item["id"] == "kimi/kimi-k3")
            route = resolve_execution_route(model, provider=provider, now=NOW)

            self.assertNotIn("execution_route_evidence", model)
            self.assertEqual(route["evidence"]["effective_state"], "documented")
            self.assertEqual(route["driver"]["admission"], "review_only")
            self.assertEqual(route["tool_mode"]["effective"], "review_only")
            self.assertIn("documented_metadata_staged_without_execution_route_authority", applied["warnings"])

    def test_route_promotions_require_real_provider_backed_gate_evidence(self) -> None:
        provider = _provider()
        model = _model()
        adapter_evidence = _evidence(model, provider, state="adapter_dry_run_passed")
        provider_evidence = _evidence(model, provider, state="provider_smoke_passed")
        record = normalize_route_promotion_record(
            {
                "action": "promote",
                "provider_id": "kimi",
                "model_id": "kimi/kimi-k3",
                "native_model": "kimi-k3",
                "previous_state": "adapter_dry_run_passed",
                "target_state": "provider_smoke_passed",
                "route_subject": adapter_evidence["subject"],
                "previous_evidence": adapter_evidence,
                "route_evidence": provider_evidence,
                "source_provenance": {"kind": "controlled_smoke", "issuer": "astrabridge-tests", "record_id": "provider-gate"},
                "evidence_refs": ["PRIVATE/provider-compatibility/runs/kimi-k3/provider-smoke.json"],
            },
            now=NOW,
        )
        diff = _route_diff(record, risk_class="requires_provider_smoke")
        proposal = _proposal(
            run_id="provider-gate",
            contract={
                "scope": "execution_routes",
                "providers": ["kimi"],
                "allow_network": False,
                "allow_provider_calls": False,
                "apply_mode": "promote_after_smoke",
            },
            diff=diff,
        )
        proposal["validation_result"] = {
            "schema_version": "astrabridge-agentic-update-validation-result-v1",
            "status": "pass",
            "gates": [
                {"gate_id": "execution_route_dry_run", "status": "pass", "blocks_promotion": False, "evidence_mode": "internal"},
                {"gate_id": "execution_route_provider_smoke", "status": "pass", "blocks_promotion": False, "evidence_mode": "fixture"},
            ],
            "evidence_paths": [],
            "warnings": [],
        }
        proposal = validate_update_proposal(proposal)

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(ValueError, "allow_provider_calls"):
                apply_execution_route_promotion_proposal(
                    workspace_root=Path(temp_dir),
                    run_id="provider-gate",
                    proposal=proposal,
                    approval=_approval(),
                    router_config_snapshot=_router_snapshot(provider, [{**model, "execution_route_evidence": adapter_evidence}]),
                    generated_catalog_snapshot=_catalog_snapshot([model]),
                )

    def test_adapter_dry_run_promotion_persists_only_reduced_authority_proof(self) -> None:
        provider = _provider()
        model = _model()
        adapter_evidence = _evidence(model, provider, state="adapter_dry_run_passed")
        record = normalize_route_promotion_record(
            {
                "action": "promote",
                "provider_id": "kimi",
                "model_id": "kimi/kimi-k3",
                "native_model": "kimi-k3",
                "previous_state": "documented",
                "target_state": "adapter_dry_run_passed",
                "route_subject": adapter_evidence["subject"],
                "route_evidence": adapter_evidence,
                "source_provenance": {"kind": "adapter_dry_run", "issuer": "astrabridge-tests", "record_id": "adapter-dry-run"},
                "evidence_refs": ["PRIVATE/provider-compatibility/runs/kimi-k3/adapter-dry-run.json"],
            },
            now=NOW,
        )
        proposal = _proposal(
            run_id="adapter-promotion",
            contract={
                "scope": "execution_routes",
                "providers": ["kimi"],
                "allow_network": False,
                "apply_mode": "verify_candidate",
            },
            diff=_route_diff(record, risk_class="metadata_only"),
        )
        proposal["validation_result"] = {
            "schema_version": "astrabridge-agentic-update-validation-result-v1",
            "status": "pass",
            "gates": [
                {"gate_id": "execution_route_dry_run", "status": "pass", "blocks_promotion": False, "evidence_mode": "internal"}
            ],
            "evidence_paths": [],
            "warnings": [],
        }
        proposal = validate_update_proposal(proposal)
        with tempfile.TemporaryDirectory() as temp_dir:
            applied = apply_execution_route_promotion_proposal(
                workspace_root=Path(temp_dir),
                run_id="adapter-promotion",
                proposal=proposal,
                approval=_approval(),
                router_config_snapshot=_router_snapshot(provider, [model]),
                generated_catalog_snapshot=_catalog_snapshot([model]),
            )
            stored = json.loads(Path(applied["touched"]["router_config"]).read_text(encoding="utf-8"))
            admitted = next(item for item in stored["models"] if item["id"] == model["id"])
            route = resolve_execution_route(
                admitted,
                provider=provider,
                evidence=admitted.get("execution_route_evidence"),
                now=NOW,
            )

            self.assertEqual(admitted["execution_route_evidence"]["state"], "adapter_dry_run_passed")
            self.assertEqual(route["evidence"]["effective_state"], "adapter_dry_run_passed")
            self.assertEqual(route["driver"]["admission"], "review_only")
            self.assertTrue(Path(applied["route_promotion"]["apply_ledger_path"]).exists())

    def test_route_downgrade_and_rollback_preserve_model_metadata(self) -> None:
        provider = _provider()
        model = _model()
        coding_evidence = _evidence(model, provider, state="coding_route_verified")
        record = normalize_route_promotion_record(
            {
                "action": "downgrade",
                "provider_id": "kimi",
                "model_id": "kimi/kimi-k3",
                "native_model": "kimi-k3",
                "previous_state": "coding_route_verified",
                "target_state": "documented",
                "route_subject": coding_evidence["subject"],
                "previous_evidence": coding_evidence,
                "reason": "adapter_signature_changed_requires_route_depromotion",
                "source_provenance": {"kind": "route_lifecycle_audit", "issuer": "astrabridge", "record_id": "adapter-drift"},
                "evidence_refs": ["PRIVATE/provider-compatibility/runs/kimi-k3/adapter-drift.json"],
            },
            now=NOW,
        )
        proposal = _proposal(
            run_id="route-downgrade",
            contract={
                "scope": "execution_routes",
                "providers": ["kimi"],
                "allow_network": False,
                "apply_mode": "verify_candidate",
            },
            diff=_route_diff(record, risk_class="metadata_only"),
        )
        proposal["validation_result"] = {
            "schema_version": "astrabridge-agentic-update-validation-result-v1",
            "status": "pass",
            "gates": [
                {"gate_id": "execution_route_dry_run", "status": "pass", "blocks_promotion": False, "evidence_mode": "internal"}
            ],
            "evidence_paths": [],
            "warnings": [],
        }
        proposal = validate_update_proposal(proposal)
        original_model = {**model, "execution_route_evidence": coding_evidence}
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            applied = apply_execution_route_promotion_proposal(
                workspace_root=workspace,
                run_id="route-downgrade",
                proposal=proposal,
                approval=_approval(),
                router_config_snapshot=_router_snapshot(provider, [original_model]),
                generated_catalog_snapshot=_catalog_snapshot([model]),
            )
            router_path = Path(applied["touched"]["router_config"])
            downgraded = next(item for item in json.loads(router_path.read_text(encoding="utf-8"))["models"] if item["id"] == model["id"])

            self.assertEqual(applied["status"], "applied_route_promotion")
            self.assertEqual(applied["track_ids"], ["execution_routes"])
            self.assertNotIn("execution_route_evidence", downgraded)
            self.assertEqual(downgraded["display_name"], model["display_name"])
            self.assertEqual(downgraded["advertised_context_window"], model["advertised_context_window"])
            self.assertEqual(resolve_execution_route(downgraded, provider=provider, now=NOW)["driver"]["admission"], "review_only")
            self.assertTrue(Path(applied["route_promotion"]["apply_ledger_path"]).exists())

            rollback = rollback_metadata_apply(workspace_root=workspace, run_id="route-downgrade")
            restored = next(item for item in json.loads(router_path.read_text(encoding="utf-8"))["models"] if item["id"] == model["id"])

            self.assertEqual(rollback["status"], "rolled_back")
            self.assertEqual(restored["execution_route_evidence"]["state"], "coding_route_verified")
            self.assertEqual(restored["display_name"], model["display_name"])
            self.assertTrue(Path(rollback["route_promotion"]["rollback_record_path"]).exists())

    def test_route_specific_validation_binds_fake_smoke_to_exact_subject(self) -> None:
        provider = _provider()
        model = _model()
        adapter_evidence = _evidence(model, provider, state="adapter_dry_run_passed")
        provider_evidence = _evidence(model, provider, state="provider_smoke_passed")
        record = normalize_route_promotion_record(
            {
                "action": "promote",
                "provider_id": "kimi",
                "model_id": "kimi/kimi-k3",
                "native_model": "kimi-k3",
                "previous_state": "adapter_dry_run_passed",
                "target_state": "provider_smoke_passed",
                "route_subject": adapter_evidence["subject"],
                "previous_evidence": adapter_evidence,
                "route_evidence": provider_evidence,
                "source_provenance": {"kind": "controlled_smoke", "issuer": "astrabridge-tests", "record_id": "exact-subject"},
                "evidence_refs": ["PRIVATE/provider-compatibility/runs/kimi-k3/provider-smoke.json"],
            },
            now=NOW,
        )
        proposal = _proposal(
            run_id="route-provider-smoke",
            contract={
                "scope": "execution_routes",
                "providers": ["kimi"],
                "allow_network": True,
                "allow_provider_calls": True,
                "apply_mode": "promote_after_smoke",
            },
            diff=_route_diff(record, risk_class="metadata_only"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            # The validator writes back to the durable proposal path; this is a
            # deterministic callback, not a provider or key call.
            proposal_path = workspace / "PRIVATE" / "agentic-update-pipeline" / "runs" / "route-provider-smoke" / "proposals" / "proposal.json"
            proposal_path.parent.mkdir(parents=True, exist_ok=True)
            proposal_path.write_text(json.dumps(proposal), encoding="utf-8")
            report = run_agentic_update_validation_gates(
                workspace_root=workspace,
                run_id="route-provider-smoke",
                proposal=proposal,
                mode="provider_backed",
                allow_provider_calls=True,
                execute_commands=False,
                fixture_command_results={
                    "metadata_tests": {"status": "pass"},
                    "model_catalog_tests": {"status": "pass"},
                    "diff_check": {"status": "pass"},
                    "secret_scan": {"status": "pass"},
                },
                route_smoke_runner=lambda payload: {
                    "record_results": [
                        {
                            "record_id": payload["records"][0]["record_id"],
                            "status": "pass",
                            "route_subject": payload["records"][0]["route_subject"],
                            "evidence_refs": ["PRIVATE/provider-compatibility/runs/kimi-k3/provider-smoke.json"],
                        }
                    ],
                    "evidence_refs": ["PRIVATE/provider-compatibility/runs/kimi-k3/provider-smoke.json"],
                },
            )
            route_gate = next(gate for gate in report["gates"] if gate["gate_id"] == "execution_route_provider_smoke")
            stored_proposal = json.loads(proposal_path.read_text(encoding="utf-8"))

            self.assertEqual(route_gate["status"], "pass")
            self.assertEqual(route_gate["evidence_mode"], "provider")
            self.assertEqual(stored_proposal["validation_result"]["gates"][-1]["evidence_mode"], "provider")

    def test_diff_records_adapter_depromotion_and_evidence_expiry(self) -> None:
        provider = _provider()
        model = _model()
        current = {**model, "execution_route_evidence": _evidence(model, provider, state="coding_route_verified")}
        candidate = _kimi_candidate()
        candidate["adapter_requirements"] = {"reasoning_parameter": "thinking", "codex_to_provider_reasoning_effort": {"high": "high"}}
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            adapter_diff = build_agentic_update_diff(
                workspace_root=workspace,
                run_id="adapter-drift",
                run_contract={"scope": "provider_adapter", "providers": ["kimi"], "allow_network": False},
                parser_output={"proposals": [candidate]},
                current_models=[current],
                update_proposal=False,
            )
            expired = _evidence(model, provider, state="coding_route_verified")
            expired["expires_at"] = "2000-01-01T00:00:00+00:00"
            expiry_diff = build_agentic_update_diff(
                workspace_root=workspace,
                run_id="expired-route",
                run_contract={"scope": "execution_routes", "providers": ["kimi"], "allow_network": False},
                current_models=[{**model, "execution_route_evidence": expired}],
                update_proposal=False,
            )

            self.assertTrue(
                any(
                    record["action"] == "downgrade"
                    and record["reason"] == "adapter_contract_changed_requires_route_depromotion"
                    for record in adapter_diff["route_promotion"]["records"]
                )
            )
            self.assertIn("route_downgraded", [change["change_type"] for change in adapter_diff["changes"]])
            self.assertTrue(any(record["action"] == "expire" for record in expiry_diff["route_promotion"]["records"]))
            self.assertIn("route_evidence_expired", [change["change_type"] for change in expiry_diff["changes"]])


def _provider() -> dict[str, object]:
    return {
        "id": "kimi",
        "provider_id": "kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "adapter_type": "chat",
        "runtime_backend": "app_server",
    }


def _model() -> dict[str, object]:
    return {
        "id": "kimi/kimi-k3",
        "provider": "kimi",
        "native_model": "kimi-k3",
        "display_name": "Kimi K3",
        "authority_tier": "A",
        "tool_mode": "guarded_actions",
        "apply_patch_tool_type": "json",
        "supports_mcp_tools": True,
        "mcp_tool_call_policy": "verified",
        "advertised_context_window": 1_048_576,
        "input_modalities": ["text"],
        "supported_reasoning_levels": ["low", "medium", "high"],
        "default_reasoning_level": "medium",
        "pricing_input_per_mtok": 0.5,
        "pricing_output_per_mtok": 2.0,
        "pricing_currency": "USD",
    }


def _kimi_candidate() -> dict[str, object]:
    return {
        "proposal_id": "kimi-k3-docs",
        "provider_id": "kimi",
        "model_id": "kimi/kimi-k3",
        "native_model": "kimi-k3",
        "display_name": "Kimi K3",
        "candidate_metadata": {
            "advertised_context_window": 1_048_576,
            "input_modalities": ["text"],
            "supported_reasoning_levels": ["low", "medium", "high"],
            "default_reasoning_level": "medium",
            "pricing": {"input_per_mtok": 0.5, "output_per_mtok": 2.0, "currency": "USD"},
            "deprecated": False,
            "default_for_provider": False,
            "recommended": False,
            "confidence": "official_docs",
        },
        "capability_claims": {
            name: {"declared": False, "verified": False}
            for name in ("tool_calls", "web_search", "vision", "audio", "apply_patch")
        },
        "source_refs": [
            {
                "source_id": "kimi-k3-official-docs",
                "source_url": "https://platform.moonshot.cn/docs/models/kimi-k3",
                "content_hash": "sha256:1234567890abcdef",
            }
        ],
        "warnings": [],
    }


def _evidence(model: dict[str, object], provider: dict[str, object], *, state: str) -> dict[str, object]:
    route = resolve_execution_route(model, provider=provider, now=NOW)
    return {
        "schema_version": EXECUTION_ROUTE_EVIDENCE_SCHEMA_VERSION,
        "state": state,
        "subject": {
            **dict(route["subject"]),
            "endpoint_fingerprint": dict(route["endpoint"])["fingerprint"],
            "adapter_signature": dict(route["adapter"])["signature"],
        },
        "source_provenance": {"kind": "controlled_smoke", "issuer": "astrabridge-tests", "record_id": f"{state}-proof"},
        "evidence_refs": [f"PRIVATE/provider-compatibility/runs/kimi-k3/{state}.json"],
        "validation_scope": ["execution_route"],
        "verified_at": "2026-07-27T00:00:00+00:00",
        "expires_at": "2026-08-31T00:00:00+00:00",
    }


def _route_diff(record: dict[str, object], *, risk_class: str) -> dict[str, object]:
    action = str(record["action"])
    change_type = {
        "promote": "route_promoted",
        "downgrade": "route_downgraded",
        "expire": "route_evidence_expired",
        "rollback": "route_rollback_requested",
    }[action]
    return {
        "schema_version": AGENTIC_UPDATE_DIFF_SCHEMA_VERSION,
        "status": "changes_detected",
        "risk_class": risk_class,
        "summary": {"change_count": 1, "risk_counts": {risk_class: 1}},
        "changes": [
            {
                "change_id": f"{change_type}-{record['record_id']}",
                "change_type": change_type,
                "risk_class": risk_class,
                "target": record["model_id"],
                "model_id": record["model_id"],
                "provider_id": record["provider_id"],
                "reasons": [record["reason"]],
                "details": {"route_promotion_record_id": record["record_id"]},
                "source_refs": [],
                "current_state_refs": [],
                "validation_requirements": list(record["required_gates"]),
            }
        ],
        "warnings": [],
        "route_promotion": {"records": [record]},
    }


def _proposal(*, run_id: str, contract: dict[str, object], diff: dict[str, object]) -> dict[str, object]:
    proposal = agentic_update_proposal_template(contract, run_id=run_id, created_at="2026-07-27T00:00:00+00:00")
    proposal["diff"] = dict(diff)
    proposal["route_promotion"] = dict(diff.get("route_promotion") or {})
    return validate_update_proposal(proposal)


def _approval() -> dict[str, str | bool]:
    return {"approved": True, "approved_by": "route-promotion-test", "approved_at": "2026-07-27T00:00:00+00:00"}


def _router_snapshot(provider: dict[str, object], models: list[dict[str, object]]) -> dict[str, object]:
    return {"providers": [provider], "models": models, "reasoning": {}, "capability_routes": {}}


def _catalog_snapshot(models: list[dict[str, object]]) -> dict[str, object]:
    return {
        "models_lock": {"schema_version": "astrabridge-model-catalog-v1", "generated_at": "2026-07-27T00:00:00+00:00", "models": models},
        "sources_lock": {"schema_version": "astrabridge-model-catalog-v1", "generated_at": "2026-07-27T00:00:00+00:00", "sources": [], "fetch_status": []},
    }


if __name__ == "__main__":
    unittest.main()
