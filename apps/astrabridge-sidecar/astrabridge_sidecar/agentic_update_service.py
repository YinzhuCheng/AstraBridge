from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import threading
from typing import Any, Callable

from .agentic_updates import (
    AGENTIC_UPDATE_DIFF_SCHEMA_VERSION,
    agentic_update_proposal_template,
    apply_metadata_only_proposal,
    assert_secret_free_agentic_update_payload,
    build_agentic_update_diff,
    discover_codex_kernel_candidates,
    ensure_agentic_update_run_layout,
    normalize_update_scope_contract,
    parse_agentic_update_source_pack,
    plan_code_change_worktree_boundary,
    rollback_metadata_apply,
    run_agentic_update_kernel_candidate_verification,
    run_agentic_update_validation_gates,
    run_agentic_update_discovery,
    validate_update_proposal,
)
from .model_catalog import current_generated_catalog
from .common import new_id, now_iso, read_json, write_json


AGENTIC_UPDATE_JOB_SCHEMA_VERSION = "astrabridge-agentic-update-job-v1"
PROPOSAL_ONLY_ALLOWED_APPLY_MODES = {"discover_only", "proposal_only"}
PROVIDER_DISCOVERY_SCOPES = {"provider_metadata", "provider_adapter", "capability_routes", "docs_only", "plugin_skill_surface"}


class AgenticUpdateService:
    def __init__(
        self,
        *,
        workspace_root: str | Path | None = None,
        workspace_root_resolver: Callable[[], str | Path] | None = None,
        runtime_root_resolver: Callable[[], str | Path] | None = None,
        provider_smoke_runtime_resolver: Callable[[], Any] | None = None,
        router_config: Any | None = None,
    ) -> None:
        if workspace_root is None and workspace_root_resolver is None:
            raise ValueError("workspace_root or workspace_root_resolver is required.")
        self._workspace_root = Path(workspace_root).resolve() if workspace_root is not None else None
        self._workspace_root_resolver = workspace_root_resolver
        self._runtime_root_resolver = runtime_root_resolver
        self._provider_smoke_runtime_resolver = provider_smoke_runtime_resolver
        self._router_config = router_config
        self._job_lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._latest_job_id: str | None = None

    def start(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("Agentic update start payload must be a dict.")
        run_contract = dict(payload.get("run_contract") or payload)
        contract = normalize_update_scope_contract(run_contract)
        run_id = _run_id_from_payload(payload)
        job_id = new_id("agentic-update-job")
        now = now_iso()
        job = {
            "schema_version": AGENTIC_UPDATE_JOB_SCHEMA_VERSION,
            "job_id": job_id,
            "run_id": run_id,
            "status": "running",
            "running": True,
            "started_at": now,
            "finished_at": None,
            "run_contract": contract,
            "summary": {},
            "artifact_paths": {},
            "error": None,
            "result": None,
        }
        with self._job_lock:
            self._jobs[job_id] = job
            self._latest_job_id = job_id
            self._prune_jobs_locked()
        try:
            self._validate_proposal_only_contract(contract)
            result = self._run_proposal_only(run_id=run_id, contract=contract, payload=payload)
            with self._job_lock:
                stored = self._jobs[job_id]
                stored["status"] = "success"
                stored["running"] = False
                stored["finished_at"] = now_iso()
                stored["summary"] = dict(result.get("summary") or {})
                stored["artifact_paths"] = dict(result.get("artifact_paths") or {})
                stored["result"] = result
                stored["error"] = None
        except Exception as exc:  # noqa: BLE001
            with self._job_lock:
                stored = self._jobs[job_id]
                stored["status"] = "failed"
                stored["running"] = False
                stored["finished_at"] = now_iso()
                stored["error"] = str(exc)[:500]
        return self.status(job_id)

    def status(self, job_id: str | None = None) -> dict[str, Any]:
        with self._job_lock:
            job = self._select_job_locked(job_id)
            if not job:
                return {
                    "schema_version": AGENTIC_UPDATE_JOB_SCHEMA_VERSION,
                    "job_id": None,
                    "run_id": None,
                    "status": "idle",
                    "running": False,
                    "latest_job_id": self._latest_job_id,
                }
            return self._job_status_view(job)

    def result(self, job_id: str | None = None) -> dict[str, Any]:
        with self._job_lock:
            job = self._select_job_locked(job_id)
            if not job:
                raise ValueError("No agentic update job is available yet.")
            if str(job.get("status")) == "failed":
                raise RuntimeError(str(job.get("error") or "Agentic update job failed."))
            result = job.get("result")
            if not isinstance(result, dict):
                raise ValueError("Agentic update job has not produced a result yet.")
            return deepcopy(result)

    def apply(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("Agentic update apply payload must be a dict.")
        proposal = self._proposal_from_payload(payload)
        run_id = str(payload.get("run_id") or proposal.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run_id is required for agentic update apply.")
        manifest = apply_metadata_only_proposal(
            workspace_root=self._workspace(),
            run_id=run_id,
            proposal=proposal,
            approval=dict(payload.get("approval") or {}),
            router_config_snapshot=_optional_dict(payload.get("router_config_snapshot")) or self._router_config_snapshot(),
            generated_catalog_snapshot=_optional_dict(payload.get("generated_catalog_snapshot")) or self._generated_catalog_snapshot(),
            isolated_state_root=payload.get("isolated_state_root"),
        )
        self._write_apply_summary(run_id=run_id, status="applied_metadata_only", manifest=manifest)
        return manifest

    def rollback(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("Agentic update rollback payload must be a dict.")
        run_id = str(payload.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run_id is required for agentic update rollback.")
        result = rollback_metadata_apply(
            workspace_root=self._workspace(),
            run_id=run_id,
            apply_manifest_path=payload.get("apply_manifest_path"),
        )
        self._write_apply_summary(run_id=run_id, status="rolled_back", manifest=result)
        return result

    def code_change_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("Agentic update code-change plan payload must be a dict.")
        proposal = self._proposal_from_payload(payload)
        run_id = str(payload.get("run_id") or proposal.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run_id is required for agentic update code-change planning.")
        manifest = plan_code_change_worktree_boundary(
            workspace_root=self._workspace(),
            run_id=run_id,
            proposal=proposal,
            approval=dict(payload.get("approval") or {}),
            boundary=_optional_dict(payload.get("boundary")) or {},
            runtime_root=self._runtime_root(),
        )
        self._write_apply_summary(run_id=run_id, status=str(manifest.get("status") or "code_change_plan"), manifest=manifest)
        return manifest

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("Agentic update validate payload must be a dict.")
        proposal = self._proposal_from_payload(payload)
        run_id = str(payload.get("run_id") or proposal.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run_id is required for agentic update validation.")
        report = run_agentic_update_validation_gates(
            workspace_root=self._workspace(),
            run_id=run_id,
            proposal=proposal,
            mode=str(payload.get("mode") or "fixture_only"),
            allow_provider_calls=payload.get("allow_provider_calls") if isinstance(payload.get("allow_provider_calls"), bool) else None,
            execute_commands=payload.get("execute_commands") if isinstance(payload.get("execute_commands"), bool) else None,
            fixture_command_results=_optional_dict(payload.get("fixture_command_results")) or {},
            configured_models=self._current_models(),
            capability_route_records=self._capability_route_records(),
            provider_runtime=self._provider_smoke_runtime(),
            credential_status=_optional_dict(payload.get("credential_status")) or self._provider_credential_status(),
        )
        self._write_validation_summary(run_id=run_id, report=report)
        return report

    def verify_kernel_candidate(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("Agentic update kernel verification payload must be a dict.")
        proposal = self._proposal_from_payload(payload)
        run_id = str(payload.get("run_id") or proposal.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run_id is required for Codex kernel candidate verification.")
        report = run_agentic_update_kernel_candidate_verification(
            workspace_root=self._workspace(),
            run_id=run_id,
            proposal=proposal,
            candidate_id=_optional_string(payload, "candidate_id"),
            candidate=_optional_dict(payload.get("candidate")),
            binary_locator=_optional_string(payload, "binary_locator"),
            version_locator=_optional_string(payload, "version_locator"),
            mode=str(payload.get("mode") or "fixture"),
            execution_host=str(payload.get("execution_host") or "windows"),
            wsl_distro=_optional_string(payload, "wsl_distro"),
            baseline=_optional_dict(payload.get("baseline")),
            fixture_smoke_report=_optional_dict(payload.get("fixture_smoke_report")),
        )
        self._write_kernel_verify_summary(run_id=run_id, report=report)
        return report

    def list_runs(self, *, limit: int = 50) -> dict[str, Any]:
        workspace = self._workspace()
        runs: dict[str, dict[str, Any]] = {}
        for item in self._artifact_run_summaries(workspace):
            run_id = str(item.get("run_id") or "").strip()
            if run_id:
                runs[run_id] = item
        with self._job_lock:
            for job in self._jobs.values():
                run_id = str(job.get("run_id") or "").strip()
                if not run_id:
                    continue
                existing = runs.get(run_id, {})
                runs[run_id] = {
                    **existing,
                    "schema_version": AGENTIC_UPDATE_JOB_SCHEMA_VERSION,
                    "job_id": job.get("job_id"),
                    "run_id": run_id,
                    "status": job.get("status"),
                    "running": bool(job.get("running")),
                    "started_at": job.get("started_at"),
                    "finished_at": job.get("finished_at"),
                    "summary": dict(job.get("summary") or existing.get("summary") or {}),
                    "artifact_paths": dict(job.get("artifact_paths") or existing.get("artifact_paths") or {}),
                    "error": job.get("error"),
                }
        ordered = sorted(
            runs.values(),
            key=lambda item: str(item.get("finished_at") or item.get("started_at") or item.get("updated_at") or ""),
            reverse=True,
        )
        return {
            "schema_version": "astrabridge-agentic-update-runs-v1",
            "generated_at": now_iso(),
            "runs": ordered[: max(1, int(limit or 50))],
            "run_count": min(len(ordered), max(1, int(limit or 50))),
            "total_known_runs": len(ordered),
            "latest_job_id": self._latest_job_id,
        }

    def _run_proposal_only(self, *, run_id: str, contract: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        workspace = self._workspace()
        layout = ensure_agentic_update_run_layout(workspace, run_id)
        write_json(Path(layout["files"]["run_contract"]), contract)
        scopes = set(contract.get("scope") or [])
        discovery_output: dict[str, Any] | None = None
        parser_output: dict[str, Any] | None = None
        kernel_output: dict[str, Any] | None = None
        if scopes.intersection(PROVIDER_DISCOVERY_SCOPES):
            discovery_output = run_agentic_update_discovery(
                workspace_root=workspace,
                run_id=run_id,
                run_contract=contract,
                provider_sources=_optional_list_of_dicts(payload.get("provider_sources")),
                fixture_sources=_optional_dict(payload.get("fixture_sources") or payload.get("provider_fixture_sources")),
            )
            parser_output = parse_agentic_update_source_pack(
                workspace_root=workspace,
                run_id=run_id,
                source_pack_path=discovery_output["artifact_paths"]["source_pack"],
            )
        if "codex_kernel" in scopes:
            kernel_output = discover_codex_kernel_candidates(
                workspace_root=workspace,
                run_id=run_id,
                run_contract=contract,
                source_records=_optional_list_of_dicts(payload.get("kernel_source_records")),
                fixture_sources=_optional_dict(payload.get("kernel_fixture_sources") or (payload.get("fixture_sources") if not parser_output else None)),
            )
        current_models = _optional_list_of_dicts(payload.get("current_models"))
        if current_models is None:
            current_models = self._current_models()
        diff = build_agentic_update_diff(
            workspace_root=workspace,
            run_id=run_id,
            run_contract=contract,
            parser_output=parser_output,
            kernel_candidate_output=kernel_output,
            current_models=current_models,
            complete_provider_snapshot=bool(payload.get("complete_provider_snapshot")),
            update_proposal=False,
        )
        proposal = self._write_proposal(
            run_id=run_id,
            contract=contract,
            layout=layout,
            discovery_output=discovery_output,
            parser_output=parser_output,
            kernel_output=kernel_output,
            diff=diff,
        )
        summary = {
            "status": "proposal_only_complete",
            "run_id": run_id,
            "scope": list(contract["scope"]),
            "proposal_status": proposal["diff"]["status"],
            "risk_class": proposal["diff"].get("risk_class"),
            "change_count": len(proposal["diff"].get("changes") or []),
            "artifact_root": layout["run_root"],
            "applied": False,
            "provider_calls_attempted": False,
            "install_attempted": False,
            "code_changes_attempted": False,
        }
        artifact_paths = {
            **dict(layout["files"]),
            "proposal_markdown": diff["artifact_paths"].get("proposal_markdown"),
        }
        result = {
            "schema_version": "astrabridge-agentic-update-proposal-only-result-v1",
            "generated_at": now_iso(),
            "run_id": run_id,
            "run_contract": contract,
            "summary": summary,
            "discovery": discovery_output,
            "parser_output": parser_output,
            "kernel_candidates": kernel_output,
            "diff": diff,
            "proposal": proposal,
            "artifact_paths": artifact_paths,
            "mutations": {
                "router_config_changed": False,
                "source_code_changed": False,
                "codex_binary_locator_changed": False,
                "provider_credentials_changed": False,
                "changed_paths": [],
            },
        }
        assert_secret_free_agentic_update_payload(result, label="agentic_update_proposal_only_result")
        write_json(Path(layout["files"]["summary"]), _summary_payload(job_status="success", result=result))
        return result

    def _write_proposal(
        self,
        *,
        run_id: str,
        contract: dict[str, Any],
        layout: dict[str, Any],
        discovery_output: dict[str, Any] | None,
        parser_output: dict[str, Any] | None,
        kernel_output: dict[str, Any] | None,
        diff: dict[str, Any],
    ) -> dict[str, Any]:
        proposal = agentic_update_proposal_template(contract, run_id=run_id)
        sources = []
        findings = []
        if discovery_output:
            sources.extend(list(discovery_output.get("sources") or []))
        if parser_output:
            findings.extend(list(parser_output.get("proposals") or []))
        if kernel_output:
            sources.extend(list(kernel_output.get("sources") or []))
            findings.extend(list(kernel_output.get("candidates") or []))
        proposal["discovery_result"] = {
            "schema_version": "astrabridge-agentic-update-discovery-result-v1",
            "generated_at": now_iso(),
            "mode": "fixture" if not contract["allow_network"] else "proposal_only",
            "sources": sources,
            "findings": findings,
            "warnings": _dedupe(
                list((discovery_output or {}).get("warnings") or [])
                + list((parser_output or {}).get("warnings") or [])
                + list((kernel_output or {}).get("warnings") or [])
            ),
        }
        proposal["diff"] = {
            "schema_version": AGENTIC_UPDATE_DIFF_SCHEMA_VERSION,
            "status": diff["status"],
            "risk_class": diff["risk_class"],
            "summary": dict(diff.get("summary") or {}),
            "changes": list(diff.get("changes") or []),
            "warnings": list(diff.get("warnings") or []),
            "artifact_paths": dict(diff.get("artifact_paths") or {}),
        }
        proposal["validation_result"]["status"] = "not_run"
        proposal["validation_result"]["warnings"] = _dedupe(
            list(proposal["validation_result"].get("warnings") or []) + ["proposal_only_service_does_not_run_validation"]
        )
        proposal["apply_manifest"]["changed_paths"] = []
        proposal["apply_manifest"]["warnings"] = _dedupe(
            list(proposal["apply_manifest"].get("warnings") or []) + ["proposal_only_service_does_not_apply_changes"]
        )
        proposal["rollback_manifest"]["warnings"] = _dedupe(
            list(proposal["rollback_manifest"].get("warnings") or []) + ["no_runtime_or_source_state_changed"]
        )
        validated = validate_update_proposal(proposal)
        write_json(Path(layout["files"]["proposal"]), validated)
        return validated

    def _validate_proposal_only_contract(self, contract: dict[str, Any]) -> None:
        if contract["apply_mode"] not in PROPOSAL_ONLY_ALLOWED_APPLY_MODES:
            raise ValueError("Proposal-only update service only supports discover_only or proposal_only apply_mode.")
        if contract["allow_provider_calls"]:
            raise ValueError("Proposal-only update service does not allow provider calls.")
        if contract["allow_install"]:
            raise ValueError("Proposal-only update service does not allow installs.")
        if contract["allow_code_changes"]:
            raise ValueError("Proposal-only update service does not allow code changes.")

    def _workspace(self) -> Path:
        if self._workspace_root_resolver is not None:
            return Path(self._workspace_root_resolver()).expanduser().resolve()
        if self._workspace_root is None:
            raise ValueError("Agentic update workspace root is unavailable.")
        return self._workspace_root

    def _runtime_root(self) -> Path | None:
        if self._runtime_root_resolver is None:
            return None
        return Path(self._runtime_root_resolver()).expanduser().resolve()

    def _current_models(self) -> list[dict[str, Any]]:
        if self._router_config is None or not hasattr(self._router_config, "models"):
            return []
        return [dict(item) for item in list(self._router_config.models() or []) if isinstance(item, dict)]

    def _capability_route_records(self) -> dict[str, Any]:
        if self._router_config is None or not hasattr(self._router_config, "capability_routes"):
            return {}
        return dict(self._router_config.capability_routes() or {})

    def _provider_smoke_runtime(self) -> Any | None:
        if self._provider_smoke_runtime_resolver is None:
            return None
        return self._provider_smoke_runtime_resolver()

    def _provider_credential_status(self) -> dict[str, Any]:
        providers = []
        if self._router_config is not None and hasattr(self._router_config, "providers"):
            providers = [dict(item) for item in list(self._router_config.providers() or []) if isinstance(item, dict)]
        records = []
        for provider in providers:
            provider_id = str(provider.get("id") or provider.get("provider_id") or "").strip()
            if not provider_id:
                continue
            sources: list[str] = []
            if provider.get("auth_key_ref"):
                sources.append("key_ref_present")
            env_key = str(provider.get("env_key") or "").strip()
            if env_key and os.environ.get(env_key):
                sources.append("environment_present")
            records.append(
                {
                    "provider_id": provider_id,
                    "available": bool(sources),
                    "sources": sources,
                }
            )
        return {"providers": records}

    def _proposal_from_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if isinstance(payload.get("proposal"), dict):
            return validate_update_proposal(dict(payload["proposal"]))
        proposal_path = payload.get("proposal_path")
        if proposal_path:
            path = Path(str(proposal_path))
            if path.is_absolute():
                raise ValueError("proposal_path must be run-relative.")
            run_id = str(payload.get("run_id") or "").strip()
            if not run_id:
                raise ValueError("run_id is required with proposal_path.")
            path = Path(ensure_agentic_update_run_layout(self._workspace(), run_id)["run_root"]) / path
            return validate_update_proposal(read_json(path, {}))
        result = self.result(str(payload.get("job_id") or payload.get("run_id") or ""))
        proposal = result.get("proposal")
        if not isinstance(proposal, dict):
            raise ValueError("The selected agentic update run does not include a proposal.")
        return validate_update_proposal(proposal)

    def _router_config_snapshot(self) -> dict[str, Any]:
        if self._router_config is None:
            return {"providers": [], "models": [], "reasoning": {}, "capability_routes": {}}
        if hasattr(self._router_config, "export_sanitized"):
            return dict(self._router_config.export_sanitized())
        if hasattr(self._router_config, "snapshot"):
            snapshot = dict(self._router_config.snapshot())
            return {
                "providers": [dict(item) for item in list(snapshot.get("providers") or []) if isinstance(item, dict)],
                "models": [dict(item) for item in list(snapshot.get("models") or []) if isinstance(item, dict)],
                "reasoning": dict(snapshot.get("reasoning") or {}),
                "capability_routes": dict(snapshot.get("capability_routes") or {}),
            }
        return {"providers": [], "models": self._current_models(), "reasoning": {}, "capability_routes": {}}

    def _generated_catalog_snapshot(self) -> dict[str, Any]:
        generated = current_generated_catalog()
        return {
            "models_lock": {
                "schema_version": generated.catalog_version,
                "generated_at": generated.generated_at,
                "models": [dict(item) for item in generated.models],
            },
            "sources_lock": {
                "schema_version": generated.catalog_version,
                "generated_at": generated.generated_at,
                "sources": [dict(item) for item in generated.sources],
                "fetch_status": [],
            },
        }

    def _write_apply_summary(self, *, run_id: str, status: str, manifest: dict[str, Any]) -> None:
        workspace = self._workspace()
        layout = ensure_agentic_update_run_layout(workspace, run_id)
        summary_payload = read_json(Path(layout["files"]["summary"]), {})
        if not isinstance(summary_payload, dict):
            summary_payload = {}
        artifact_paths = dict(summary_payload.get("artifact_paths") or {})
        artifact_paths.update(
            {
                "apply_manifest": layout["files"]["apply_manifest"],
                "rollback_manifest": layout["files"]["rollback_manifest"],
            }
        )
        summary = dict(summary_payload.get("summary") or {})
        summary.update(
            {
                "status": status,
                "run_id": run_id,
                "applied": status == "applied_metadata_only",
                "rolled_back": status == "rolled_back",
                "apply_id": manifest.get("apply_id"),
            }
        )
        write_json(
            Path(layout["files"]["summary"]),
            {
                "schema_version": AGENTIC_UPDATE_JOB_SCHEMA_VERSION,
                "updated_at": now_iso(),
                "job_id": None,
                "run_id": run_id,
                "status": status,
                "running": False,
                "summary": summary,
                "artifact_paths": artifact_paths,
                "error": None,
            },
        )

    def _write_validation_summary(self, *, run_id: str, report: dict[str, Any]) -> None:
        workspace = self._workspace()
        layout = ensure_agentic_update_run_layout(workspace, run_id)
        summary_payload = read_json(Path(layout["files"]["summary"]), {})
        if not isinstance(summary_payload, dict):
            summary_payload = {}
        artifact_paths = dict(summary_payload.get("artifact_paths") or {})
        artifact_paths.update(dict(report.get("artifact_paths") or {}))
        summary = dict(summary_payload.get("summary") or {})
        summary.update(
            {
                "status": f"validation_{report.get('status')}",
                "run_id": run_id,
                "validation_status": report.get("status"),
                "promotion_blocked": bool(report.get("promotion_blocked")),
                "validation_gate_count": report.get("gate_count"),
            }
        )
        write_json(
            Path(layout["files"]["summary"]),
            {
                "schema_version": AGENTIC_UPDATE_JOB_SCHEMA_VERSION,
                "updated_at": now_iso(),
                "job_id": None,
                "run_id": run_id,
                "status": f"validation_{report.get('status')}",
                "running": False,
                "summary": summary,
                "artifact_paths": artifact_paths,
                "error": None,
            },
        )

    def _write_kernel_verify_summary(self, *, run_id: str, report: dict[str, Any]) -> None:
        workspace = self._workspace()
        layout = ensure_agentic_update_run_layout(workspace, run_id)
        summary_payload = read_json(Path(layout["files"]["summary"]), {})
        if not isinstance(summary_payload, dict):
            summary_payload = {}
        artifact_paths = dict(summary_payload.get("artifact_paths") or {})
        artifact_paths.update(dict(report.get("artifact_paths") or {}))
        summary = dict(summary_payload.get("summary") or {})
        summary.update(
            {
                "status": f"kernel_verify_{report.get('status')}",
                "run_id": run_id,
                "kernel_verify_status": report.get("status"),
                "kernel_candidate_verified": bool(report.get("verified")),
                "rollback_required": bool(dict(report.get("rollback") or {}).get("required")),
            }
        )
        write_json(
            Path(layout["files"]["summary"]),
            {
                "schema_version": AGENTIC_UPDATE_JOB_SCHEMA_VERSION,
                "updated_at": now_iso(),
                "job_id": None,
                "run_id": run_id,
                "status": f"kernel_verify_{report.get('status')}",
                "running": False,
                "summary": summary,
                "artifact_paths": artifact_paths,
                "error": None,
            },
        )

    def _select_job_locked(self, job_id: str | None) -> dict[str, Any] | None:
        if job_id:
            text = str(job_id)
            direct = self._jobs.get(text)
            if direct is not None:
                return direct
            for job in self._jobs.values():
                if str(job.get("run_id") or "") == text:
                    return job
            return None
        if self._latest_job_id:
            return self._jobs.get(self._latest_job_id)
        return None

    def _job_status_view(self, job: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": AGENTIC_UPDATE_JOB_SCHEMA_VERSION,
            "job_id": job.get("job_id"),
            "run_id": job.get("run_id"),
            "status": job.get("status"),
            "running": bool(job.get("running")),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
            "summary": dict(job.get("summary") or {}),
            "artifact_paths": dict(job.get("artifact_paths") or {}),
            "error": job.get("error"),
            "latest_job_id": self._latest_job_id,
        }

    def _artifact_run_summaries(self, workspace: Path) -> list[dict[str, Any]]:
        runs_root = workspace / "PRIVATE" / "agentic-update-pipeline" / "runs"
        if not runs_root.exists():
            return []
        summaries: list[dict[str, Any]] = []
        for run_dir in sorted((item for item in runs_root.iterdir() if item.is_dir()), key=lambda item: item.name):
            summary_path = run_dir / "summary.json"
            payload = read_json(summary_path, {}) if summary_path.exists() else {}
            if isinstance(payload, dict) and payload:
                summaries.append(payload)
            else:
                summaries.append(
                    {
                        "schema_version": AGENTIC_UPDATE_JOB_SCHEMA_VERSION,
                        "run_id": run_dir.name,
                        "status": "artifact_only",
                        "running": False,
                        "artifact_paths": {"run_root": str(run_dir)},
                    }
                )
        return summaries

    def _prune_jobs_locked(self) -> None:
        job_ids = list(self._jobs.keys())
        if len(job_ids) <= 20:
            return
        for job_id in job_ids[:-20]:
            self._jobs.pop(job_id, None)


def _run_id_from_payload(payload: dict[str, Any]) -> str:
    run_id = str(payload.get("run_id") or "").strip()
    return run_id or new_id("agentic-update")


def _optional_dict(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def _optional_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_list_of_dicts(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    return [dict(item) for item in value if isinstance(item, dict)]


def _summary_payload(*, job_status: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": AGENTIC_UPDATE_JOB_SCHEMA_VERSION,
        "updated_at": now_iso(),
        "job_id": None,
        "run_id": result.get("run_id"),
        "status": job_status,
        "running": False,
        "summary": dict(result.get("summary") or {}),
        "artifact_paths": dict(result.get("artifact_paths") or {}),
        "error": None,
    }


def _dedupe(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for value in values:
        marker = repr(value)
        if marker not in seen:
            result.append(value)
            seen.add(marker)
    return result
