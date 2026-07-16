from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import html
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

from .common import app_data_dir, now_iso, read_json, write_json
from .model_catalog import (
    GeneratedCatalog,
    SOURCE_REGISTRY_SCHEMA_VERSION,
    build_generated_catalog,
    catalog_entry_from_record,
    current_generated_catalog,
    default_catalog_sources,
    default_seed_models,
    default_seed_providers,
    effective_model_records,
    known_context_window,
    normalize_provider_source_records,
)


class MetadataService:
    def __init__(self, router_config, router, store_path: Path | None = None, report_root: Path | None = None) -> None:
        self._router_config = router_config
        self._router = router
        self.store_path = store_path or (app_data_dir() / "metadata_sources.json")
        self.report_root = report_root or _default_report_root()
        self._job_lock = threading.Lock()
        self._refresh_jobs: dict[str, dict[str, Any]] = {}
        self._latest_refresh_job_id: str | None = None

    def sources(self) -> dict[str, Any]:
        payload = read_json(self.store_path, {})
        defaults = [dict(item) for item in default_catalog_sources()]
        if not isinstance(payload, dict) or not payload.get("providers"):
            providers = normalize_provider_source_records(defaults)
            payload = {
                "providers": providers,
                "updated_at": now_iso(),
                "catalog_schema": "astrabridge-generated-catalog-v1",
                "source_registry_schema": SOURCE_REGISTRY_SCHEMA_VERSION,
            }
            write_json(self.store_path, payload)
            return payload
        existing = [dict(item) for item in list(payload.get("providers") or []) if isinstance(item, dict)]
        existing_by_id = {str(item.get("provider_id") or ""): item for item in existing}
        merged: list[dict[str, Any]] = []
        for default in defaults:
            provider_id = str(default.get("provider_id") or "")
            merged.append({**default, **existing_by_id.get(provider_id, {})})
        known_ids = {str(item.get("provider_id") or "") for item in defaults}
        for item in existing:
            provider_id = str(item.get("provider_id") or "")
            if provider_id and provider_id not in known_ids:
                merged.append(item)
        normalized_providers = normalize_provider_source_records(merged)
        normalized = {
            "providers": normalized_providers,
            "updated_at": payload.get("updated_at") or now_iso(),
            "catalog_schema": "astrabridge-generated-catalog-v1",
            "source_registry_schema": SOURCE_REGISTRY_SCHEMA_VERSION,
        }
        if normalized != payload:
            normalized["updated_at"] = now_iso()
            write_json(self.store_path, normalized)
        return normalized

    def save_sources(self, payload: dict[str, Any]) -> dict[str, Any]:
        providers = normalize_provider_source_records([dict(item) for item in list(payload.get("providers") or []) if isinstance(item, dict)])
        saved = {
            "providers": providers,
            "updated_at": now_iso(),
            "catalog_schema": "astrabridge-generated-catalog-v1",
            "source_registry_schema": SOURCE_REGISTRY_SCHEMA_VERSION,
        }
        write_json(self.store_path, saved)
        return saved

    def import_seed(self, *, apply: bool = True) -> dict[str, Any]:
        catalog = build_generated_catalog(
            sources=self.sources().get("providers") or default_catalog_sources(),
            providers=default_seed_providers(),
            models=default_seed_models(),
        )
        providers = [_provider_seed(item) for item in catalog.providers]
        models = [_model_seed(item) for item in catalog.models]
        if apply:
            managed_provider_ids = {str(item.get("id") or item.get("provider_id") or "") for item in providers}
            self._router_config.apply_catalog_seed(
                providers,
                models,
                managed_provider_ids=managed_provider_ids,
            )
            self.sources()
        return {
            "applied": apply,
            "providers": providers,
            "models": models,
            "model_count": len(models),
            "catalog_version": catalog.catalog_version,
            "generated_at": catalog.generated_at,
        }

    def refresh(self, *, apply: bool = False) -> dict[str, Any]:
        return self._run_refresh(apply=apply)

    def start_refresh(self, *, apply: bool = False) -> dict[str, Any]:
        job_id = f"refresh-{uuid4().hex[:12]}"
        job = {
            "job_id": job_id,
            "apply": apply,
            "status": "running",
            "started_at": now_iso(),
            "finished_at": None,
            "result": None,
            "error": None,
        }
        with self._job_lock:
            self._refresh_jobs[job_id] = job
            self._latest_refresh_job_id = job_id
            self._prune_jobs_locked()
        worker = threading.Thread(target=self._run_refresh_job, args=(job_id, apply), daemon=True, name=f"AstraBridgeMetadataRefresh-{job_id}")
        worker.start()
        return {
            "job_id": job_id,
            "status": "running",
            "apply": apply,
            "started_at": job["started_at"],
        }

    def refresh_status(self, job_id: str | None = None) -> dict[str, Any]:
        with self._job_lock:
            target = self._select_job_locked(job_id)
            if not target:
                return {"job_id": None, "status": "idle", "running": False, "latest_job_id": self._latest_refresh_job_id}
            result = target.get("result") if isinstance(target.get("result"), dict) else {}
            fetched = [dict(item) for item in list(result.get("fetched") or []) if isinstance(item, dict)]
            return {
                "job_id": target.get("job_id"),
                "status": target.get("status"),
                "running": str(target.get("status")) == "running",
                "apply": bool(target.get("apply")),
                "started_at": target.get("started_at"),
                "finished_at": target.get("finished_at"),
                "error": target.get("error"),
                "summary": result.get("summary") or {},
                "source_results": fetched,
                "artifact_paths": result.get("artifact_paths") or {},
                "latest_job_id": self._latest_refresh_job_id,
            }

    def refresh_result(self, job_id: str | None = None) -> dict[str, Any]:
        with self._job_lock:
            target = self._select_job_locked(job_id)
            if not target:
                raise ValueError("No metadata refresh job is available yet.")
            if str(target.get("status")) == "failed":
                raise RuntimeError(str(target.get("error") or "Metadata refresh failed."))
            result = target.get("result")
            if not isinstance(result, dict):
                raise ValueError("Metadata refresh job has not produced a result yet.")
            return result

    def effective_catalog(self, model_id: str | None = None) -> dict[str, Any]:
        generated = current_generated_catalog()
        models = []
        for effective in effective_model_records(self._router_config.models(), include_disabled=False):
            if model_id and str(effective.get("id")) != model_id:
                continue
            if not bool(effective.get("codex_agent_enabled", True)):
                continue
            models.append(catalog_entry_from_record(effective))
        return {
            "models": models,
            "model_count": len(models),
            "generated_at": generated.generated_at,
            "catalog_version": generated.catalog_version,
            "review_path": generated.review_path,
            "models_lock_path": generated.models_lock_path,
            "sources_lock_path": generated.sources_lock_path,
        }

    def test_matrix(self, payload: dict[str, Any]) -> dict[str, Any]:
        key_files = dict(payload.get("key_files") or _default_key_files())
        model_ids = [str(item) for item in list(payload.get("model_ids") or []) if str(item).strip()]
        efforts = [str(item) for item in list(payload.get("efforts") or ["low", "medium", "high", "xhigh"]) if str(item).strip()]
        temperatures = [_coerce_float(item) for item in list(payload.get("temperatures") or [0, 0.7, 1, 2])]
        temperatures = [item for item in temperatures if item is not None]
        max_cases = int(payload.get("max_cases") or 96)
        stop_after_errors = int(payload.get("stop_after_errors") or 3)
        results = []
        consecutive_errors = 0
        original_env: dict[str, str | None] = {}
        cases = 0
        try:
            providers = {str(item.get("id")): item for item in self._router_config.providers()}
            for model in self._router_config.models():
                model_id = str(model.get("id") or "")
                if model_ids and model_id not in model_ids:
                    continue
                if not model.get("enabled", True) or not model.get("codex_agent_enabled", True):
                    results.append(_skip_result(model_id, "Model is disabled or not exposed as Codex agent model."))
                    continue
                provider_id = str(model.get("provider") or "")
                provider = providers.get(provider_id)
                if not provider:
                    results.append(_skip_result(model_id, "Provider is not configured."))
                    continue
                env_key = str(provider.get("env_key") or "")
                if env_key not in original_env:
                    original_env[env_key] = os.environ.get(env_key)
                loaded = _load_key_for_provider(provider_id, key_files)
                if loaded:
                    os.environ[env_key] = loaded
                elif not os.environ.get(env_key):
                    results.append(_skip_result(model_id, f"No key file or environment value for {env_key}."))
                    continue
                model_efforts = list(model.get("supported_reasoning_levels") or efforts) or efforts
                for effort in model_efforts:
                    for temperature in temperatures:
                        if cases >= max_cases:
                            break
                        try:
                            result = self._router.test_model_case(
                                provider_id=provider_id,
                                model_id=model_id,
                                effort=str(effort),
                                temperature=float(temperature),
                                stream=False,
                            )
                            consecutive_errors = 0 if result.get("ok") else consecutive_errors + 1
                            results.append(result)
                        except Exception as exc:  # noqa: BLE001
                            consecutive_errors += 1
                            results.append({"ok": False, "provider": provider_id, "model": model_id, "effort": effort, "temperature": temperature, "error": str(exc)})
                        cases += 1
                        if consecutive_errors >= stop_after_errors:
                            return self._write_test_report(results, stopped_early=True)
                    if cases >= max_cases:
                        break
        finally:
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        return self._write_test_report(results, stopped_early=False)

    def metadata_report(self) -> dict[str, Any]:
        return self._write_report(self._test_payload_for_report())

    def _run_refresh_job(self, job_id: str, apply: bool) -> None:
        try:
            result = self._run_refresh(apply=apply)
            with self._job_lock:
                job = self._refresh_jobs.get(job_id)
                if job is not None:
                    job["status"] = "success" if result.get("summary", {}).get("status") == "success" else "partial"
                    job["finished_at"] = now_iso()
                    job["result"] = result
                    job["error"] = None
        except Exception as exc:  # noqa: BLE001
            with self._job_lock:
                job = self._refresh_jobs.get(job_id)
                if job is not None:
                    job["status"] = "failed"
                    job["finished_at"] = now_iso()
                    job["error"] = str(exc)[:500]

    def _run_refresh(self, *, apply: bool) -> dict[str, Any]:
        sources = self.sources()
        fetched = self._fetch_sources(sources)
        catalog = build_generated_catalog(
            sources=sources.get("providers") or default_catalog_sources(),
            providers=default_seed_providers(),
            models=default_seed_models(),
            fetched=fetched,
        )
        proposed = self.import_seed(apply=apply)
        artifact_paths = self._write_refresh_artifacts(
            fetched=fetched,
            proposed=proposed,
            catalog=catalog,
            applied=apply,
        )
        summary = _refresh_summary(fetched)
        return {
            "applied": apply,
            "fetched": fetched,
            "source_results": fetched,
            "summary": summary,
            "proposed": proposed,
            "updated_at": now_iso(),
            "catalog_version": catalog.catalog_version,
            "review_path": catalog.review_path,
            "models_lock_path": catalog.models_lock_path,
            "sources_lock_path": catalog.sources_lock_path,
            "artifact_paths": artifact_paths,
        }

    def _fetch_sources(self, sources: dict[str, Any]) -> list[dict[str, Any]]:
        fetch_jobs = [
            (str(provider.get("provider_id") or ""), str(url))
            for provider in sources.get("providers") or []
            for url in list(provider.get("urls") or [])
        ]
        if not fetch_jobs:
            return []
        fetched: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(8, max(1, len(fetch_jobs)))) as executor:
            future_map = {
                executor.submit(_fetch_source_status, provider_id, url): (provider_id, url)
                for provider_id, url in fetch_jobs
            }
            for future in as_completed(future_map):
                provider_id, url = future_map[future]
                try:
                    fetched.append(future.result())
                except Exception as exc:  # noqa: BLE001
                    fetched.append(_classified_fetch_error(provider_id, url, exc))
        return sorted(fetched, key=lambda item: (str(item.get("provider_id") or ""), str(item.get("url") or "")))

    def _write_refresh_artifacts(
        self,
        *,
        fetched: list[dict[str, Any]],
        proposed: dict[str, Any],
        catalog: GeneratedCatalog,
        applied: bool,
    ) -> dict[str, str]:
        self.report_root.mkdir(parents=True, exist_ok=True)
        fetch_payload = {
            "generated_at": now_iso(),
            "applied": applied,
            "summary": _refresh_summary(fetched),
            "results": fetched,
        }
        proposal_payload = {
            "generated_at": now_iso(),
            "applied": applied,
            "catalog_version": catalog.catalog_version,
            "proposed": proposed,
        }
        diff_payload = {
            "generated_at": now_iso(),
            "applied": applied,
            "catalog_version": catalog.catalog_version,
            "summary": _diff_summary(fetched, proposed),
        }
        fetch_path = self.report_root / "fetch-results.json"
        proposal_path = self.report_root / "proposal.json"
        diff_path = self.report_root / "diff-summary.json"
        write_json(fetch_path, fetch_payload)
        write_json(proposal_path, proposal_payload)
        write_json(diff_path, diff_payload)
        return {
            "fetch_results_path": str(fetch_path),
            "proposal_path": str(proposal_path),
            "diff_summary_path": str(diff_path),
            "review_path": str(catalog.review_path or ""),
            "models_lock_path": str(catalog.models_lock_path or ""),
            "sources_lock_path": str(catalog.sources_lock_path or ""),
        }

    def _select_job_locked(self, job_id: str | None) -> dict[str, Any] | None:
        if job_id:
            return self._refresh_jobs.get(str(job_id))
        if self._latest_refresh_job_id:
            return self._refresh_jobs.get(self._latest_refresh_job_id)
        return None

    def _prune_jobs_locked(self) -> None:
        job_ids = list(self._refresh_jobs.keys())
        if len(job_ids) <= 12:
            return
        removable = job_ids[:-12]
        for job_id in removable:
            self._refresh_jobs.pop(job_id, None)

    def _write_test_report(self, results: list[dict[str, Any]], *, stopped_early: bool) -> dict[str, Any]:
        payload = {"generated_at": now_iso(), "stopped_early": stopped_early, "results": results}
        write_json(self.report_root / "latest-test-results.json", payload)
        history = read_json(self.report_root / "test-history.json", {"runs": []})
        runs = list(history.get("runs") or []) if isinstance(history, dict) else []
        runs.append(payload)
        write_json(self.report_root / "test-history.json", {"runs": runs[-20:], "updated_at": payload["generated_at"]})
        report = self._write_report(self._test_payload_for_report())
        return {"generated_at": payload["generated_at"], "stopped_early": stopped_early, "results": results, "report": report}

    def _test_payload_for_report(self) -> dict[str, Any]:
        history = read_json(self.report_root / "test-history.json", {"runs": []})
        latest = read_json(self.report_root / "latest-test-results.json", {"results": []})
        combined: list[dict[str, Any]] = []
        if isinstance(history, dict):
            for run in list(history.get("runs") or []):
                if isinstance(run, dict):
                    combined.extend([dict(item) for item in list(run.get("results") or []) if isinstance(item, dict)])
        if not combined and isinstance(latest, dict):
            combined.extend([dict(item) for item in list(latest.get("results") or []) if isinstance(item, dict)])
        return {"generated_at": now_iso(), "results": combined}

    def _write_report(self, test_payload: dict[str, Any]) -> dict[str, Any]:
        self.report_root.mkdir(parents=True, exist_ok=True)
        sources = self.sources()
        config = self._router_config.snapshot()
        catalog = self.effective_catalog()
        fetch_results = read_json(self.report_root / "fetch-results.json", {"results": []})
        write_json(self.report_root / "router-config.json", config)
        write_json(self.report_root / "effective-catalog.json", catalog)
        rows = []
        for model in config["models"]:
            rows.append(
                "<tr>"
                f"<td>{html.escape(str(model.get('id')))}</td>"
                f"<td>{html.escape(str(model.get('display_name')))}</td>"
                f"<td>{html.escape(str(model.get('provider')))}</td>"
                f"<td>{html.escape(str(model.get('advertised_context_window')))}</td>"
                f"<td>{html.escape(', '.join(list(model.get('input_modalities') or [])))}</td>"
                f"<td>{html.escape(str(model.get('temperature_adapter_policy')))}</td>"
                f"<td>{html.escape(_pricing_label(model))}</td>"
                f"<td>{html.escape(str(model.get('source_status')))}</td>"
                f"<td>{html.escape(str(model.get('recommended', False)))}</td>"
                f"<td>{html.escape(str(model.get('deprecated', False)))}</td>"
                f"<td>{html.escape(str(model.get('confidence') or ''))}</td>"
                "</tr>"
            )
        result_rows = []
        for result in list(test_payload.get("results") or []):
            result_rows.append(
                "<tr>"
                f"<td>{'PASS' if result.get('ok') else 'WARN' if result.get('skipped') else 'FAIL'}</td>"
                f"<td>{html.escape(str(result.get('provider') or ''))}</td>"
                f"<td>{html.escape(str(result.get('model') or ''))}</td>"
                f"<td>{html.escape(str(result.get('effort') or ''))}</td>"
                f"<td>{html.escape(str(result.get('temperature') or ''))}</td>"
                f"<td>{html.escape(str(result.get('status') or result.get('reason') or result.get('error') or ''))}</td>"
                "</tr>"
            )
        source_cards = []
        for provider in sources.get("providers") or []:
            links = "".join(f"<li><a href=\"{html.escape(str(url))}\">{html.escape(str(url))}</a></li>" for url in list(provider.get("urls") or []))
            policy = dict(provider.get("promotion_policy") or {})
            source_cards.append(
                f"<section><h2>{html.escape(str(provider.get('display_name') or provider.get('provider_id')))}</h2>"
                f"<p>{html.escape(str(provider.get('notes') or ''))}</p>"
                f"<p class=\"muted\">status={html.escape(str(provider.get('source_status') or 'unknown'))} "
                f"trust={html.escape(str(provider.get('trust_level') or 'unknown'))} "
                f"channel={html.escape(str(provider.get('channel') or 'unknown'))} "
                f"parser={html.escape(str(provider.get('parser_strategy') or 'unknown'))} "
                f"promotable={html.escape(str(policy.get('promotable', False)))}</p><ul>{links}</ul></section>"
            )
        fetch_rows = []
        for result in list(fetch_results.get("results") or []):
            fetch_rows.append(
                "<tr>"
                f"<td>{html.escape(str(result.get('provider_id') or ''))}</td>"
                f"<td><a href=\"{html.escape(str(result.get('url') or ''))}\">{html.escape(str(result.get('classification') or result.get('status_label') or 'unknown'))}</a></td>"
                f"<td>{html.escape(str(result.get('status_code') or result.get('status') or ''))}</td>"
                f"<td>{html.escape(str(result.get('duration_ms') or ''))}</td>"
                f"<td>{html.escape(str(result.get('bytes') or ''))}</td>"
                f"<td>{html.escape(str(result.get('error_summary') or result.get('error') or ''))}</td>"
                "</tr>"
            )
        html_text = f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>AstraBridge Catalog Report</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:28px;background:#f6f2eb;color:#23272f}}a{{color:#2459b8}}table{{border-collapse:collapse;width:100%;background:#fff}}td,th{{border:1px solid #ddd;padding:8px;text-align:left}}th{{background:#f0ede7}}section{{background:#fff;border:1px solid #ddd;border-radius:14px;padding:16px;margin:14px 0}}.muted{{color:#68707d}}
</style></head>
<body><h1>AstraBridge Catalog Report</h1><p class="muted">Generated at {html.escape(now_iso())}. Secrets are not included.</p>
<nav><a href="#sources">Sources</a> | <a href="#fetch">Fetch</a> | <a href="#models">Models</a> | <a href="#tests">Health</a> | <a href="effective-catalog.json">Effective catalog JSON</a></nav>
<h2 id="sources">Sources</h2>{''.join(source_cards)}
<h2 id="fetch">Fetch results</h2><table><thead><tr><th>Provider</th><th>Status</th><th>HTTP</th><th>Duration ms</th><th>Bytes</th><th>Detail</th></tr></thead><tbody>{''.join(fetch_rows)}</tbody></table>
<h2 id="models">Models</h2><table><thead><tr><th>ID</th><th>Name</th><th>Provider</th><th>Context</th><th>Input</th><th>Temp policy</th><th>Pricing</th><th>Source</th><th>Recommended</th><th>Deprecated</th><th>Confidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2 id="tests">Health</h2><table><thead><tr><th>Status</th><th>Provider</th><th>Model</th><th>Effort</th><th>Temp</th><th>Detail</th></tr></thead><tbody>{''.join(result_rows)}</tbody></table>
</body></html>"""
        target = self.report_root / "index.html"
        target.write_text(html_text, encoding="utf-8", newline="\n")
        catalog_meta = current_generated_catalog()
        return {
            "path": str(target),
            "catalog_path": str(self.report_root / "effective-catalog.json"),
            "config_path": str(self.report_root / "router-config.json"),
            "review_path": catalog_meta.review_path,
            "models_lock_path": catalog_meta.models_lock_path,
            "sources_lock_path": catalog_meta.sources_lock_path,
        }


def _provider_seed(provider: dict[str, Any]) -> dict[str, Any]:
    return {"request_timeout_ms": 300000, "stream_idle_timeout_ms": 300000, "auth_key_ref": None, **provider}


def _model_seed(model: dict[str, Any]) -> dict[str, Any]:
    provider = str(model.get("provider") or model.get("provider_id") or "").strip()
    native = str(model.get("native_model") or "").strip()
    if not provider and "/" in str(model.get("id") or ""):
        provider = str(model.get("id") or "").split("/", 1)[0]
    if not native and "/" in str(model.get("id") or ""):
        parts = str(model.get("id") or "").split("/", 1)
        if len(parts) == 2:
            native = parts[1]
    context_window = int(model.get("advertised_context_window") or known_context_window(provider, native) or 128_000)
    return {
        "enabled": True,
        "advertised_context_window": context_window,
        "ui_context_hint_only": True,
        "adapter_profile": "default",
        "input_modalities": ["text"],
        "temperature_default": 0,
        "temperature_ui_min": 0,
        "temperature_ui_max": 2,
        "provider_temperature_min": 0,
        "provider_temperature_max": 2,
        "temperature_adapter_policy": "pass_through_0_2",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **model,
    }


def _fetch_source_status(provider_id: str, url: str) -> dict[str, Any]:
    started = now_iso()
    started_monotonic = time.monotonic()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "AstraBridge/metadata-curator"})
        with urllib.request.urlopen(request, timeout=4) as response:
            body = response.read(120_000)
            finished = now_iso()
            duration_ms = int(max(0.0, time.monotonic() - started_monotonic) * 1000)
            return {
                "provider_id": provider_id,
                "url": url,
                "ok": True,
                "classification": "ok",
                "status_label": "ok",
                "status_code": getattr(response, "status", None),
                "bytes": len(body),
                "started_at": started,
                "finished_at": finished,
                "duration_ms": duration_ms,
            }
    except Exception as exc:  # noqa: BLE001
        return _classified_fetch_error(provider_id, url, exc, started_at=started, started_elapsed=started_monotonic)


def _default_key_files() -> dict[str, str]:
    desktop = Path.home() / "Desktop"
    return {
        "yunwu": str(desktop / "gptimg2.txt"),
        "deepseek": str(desktop / "dskeynew.txt"),
        "qwen": str(desktop / "ali.txt"),
        "kimi": str(desktop / "kimi.txt"),
        "glm": str(desktop / "glm.txt"),
    }


def _load_key_for_provider(provider_id: str, key_files: dict[str, Any]) -> str | None:
    path = key_files.get(provider_id)
    if not path:
        return None
    candidate = Path(str(path)).expanduser()
    if not candidate.exists() or not candidate.is_file():
        return None
    value = candidate.read_text(encoding="utf-8-sig").strip().splitlines()[0].strip()
    return value if len(value) >= 8 else None


def _skip_result(model_id: str, reason: str) -> dict[str, Any]:
    provider = model_id.split("/", 1)[0] if "/" in model_id else ""
    return {"ok": False, "skipped": True, "provider": provider, "model": model_id, "reason": reason}


def _pricing_label(model: dict[str, Any]) -> str:
    currency = str(model.get("pricing_currency") or "").strip()
    input_price = model.get("pricing_input_per_mtok")
    output_price = model.get("pricing_output_per_mtok")
    cached = model.get("pricing_cached_input_per_mtok")
    status = str(model.get("pricing_status") or "unknown")
    if input_price in {None, ""} and output_price in {None, ""}:
        return status
    parts = [currency] if currency else []
    parts.append(f"in {input_price}/M" if input_price not in {None, ""} else "in n/a")
    parts.append(f"out {output_price}/M" if output_price not in {None, ""} else "out n/a")
    if cached not in {None, ""}:
        parts.append(f"cached {cached}/M")
    parts.append(status)
    return " | ".join(parts)


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _default_report_root() -> Path:
    workflow = Path("D:/workflow")
    if workflow.exists():
        return workflow / "astrabridge-catalog-report"
    return app_data_dir() / "catalog-report"


def _classified_fetch_error(
    provider_id: str,
    url: str,
    exc: Exception,
    *,
    started_at: str | None = None,
    started_elapsed: float | None = None,
) -> dict[str, Any]:
    classification = "unknown"
    status_code = None
    error_summary = str(exc)[:300]
    if isinstance(exc, (TimeoutError, socket.timeout)):
        classification = "timeout"
    elif isinstance(exc, urllib.error.HTTPError):
        classification = "http_error"
        status_code = exc.code
    elif isinstance(exc, urllib.error.URLError):
        reason = str(exc.reason or "").lower()
        if "ssl" in reason or "certificate" in reason:
            classification = "ssl_error"
        elif "timed out" in reason or "timeout" in reason:
            classification = "timeout"
        elif "redirect" in reason:
            classification = "redirect_loop"
        else:
            classification = "blocked"
    finished = now_iso()
    duration_ms = int(max(0.0, (time.monotonic() - started_elapsed) if started_elapsed is not None else 0.0) * 1000)
    return {
        "provider_id": provider_id,
        "url": url,
        "ok": False,
        "classification": classification,
        "status_label": classification,
        "status_code": status_code,
        "bytes": 0,
        "started_at": started_at or finished,
        "finished_at": finished,
        "duration_ms": duration_ms,
        "error_summary": error_summary,
    }


def _refresh_summary(fetched: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(fetched)
    ok_count = sum(1 for item in fetched if item.get("ok"))
    failed = total - ok_count
    if total == 0:
        status = "idle"
    elif failed == 0:
        status = "success"
    elif ok_count == 0:
        status = "failed"
    else:
        status = "partial"
    by_classification: dict[str, int] = {}
    for item in fetched:
        key = str(item.get("classification") or ("ok" if item.get("ok") else "unknown"))
        by_classification[key] = by_classification.get(key, 0) + 1
    return {
        "status": status,
        "total_sources": total,
        "ok_sources": ok_count,
        "failed_sources": failed,
        "by_classification": by_classification,
    }


def _diff_summary(fetched: list[dict[str, Any]], proposed: dict[str, Any]) -> dict[str, Any]:
    providers = list(proposed.get("providers") or [])
    models = list(proposed.get("models") or [])
    return {
        "providers": len(providers),
        "models": len(models),
        "model_count": int(proposed.get("model_count") or len(models)),
        "ok_sources": sum(1 for item in fetched if item.get("ok")),
        "failed_sources": sum(1 for item in fetched if not item.get("ok")),
    }
