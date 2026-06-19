from __future__ import annotations

import html
import json
import os
import urllib.request
from pathlib import Path
from typing import Any

from .common import app_data_dir, now_iso, read_json, write_json
from .model_catalog import known_context_window, model_catalog_entry


DEFAULT_PROVIDER_SOURCES: list[dict[str, Any]] = [
    {
        "provider_id": "yunwu",
        "display_name": "Yunwu",
        "urls": [
            "https://yunwu.apifox.cn/api-232421952",
            "https://yunwu.apifox.cn/api-425475208",
            "https://yunwu.apifox.cn/api-425481728",
            "https://yunwu.ai/pricing?group=Codex%E4%B8%93%E5%B1%9E",
        ],
        "source_status": "screenshot_seed",
        "notes": "Apifox pages were not readable through the current fetcher; seed from user screenshot.",
    },
    {
        "provider_id": "deepseek",
        "display_name": "DeepSeek",
        "urls": ["https://api-docs.deepseek.com/zh-cn/"],
        "source_status": "official_docs",
        "notes": "OpenAI-compatible Chat Completions upstream; LCR exposes Responses to Codex.",
    },
    {
        "provider_id": "kimi",
        "display_name": "Kimi",
        "urls": [
            "https://platform.kimi.com/docs/overview",
            "https://platform.kimi.com/docs/models",
            "https://platform.kimi.com/docs/guide/kimi-k2-6-quickstart",
        ],
        "source_status": "official_docs",
        "notes": "K2.6/K2.5 are provider multimodal. Kimi image input must be sent as base64 data URL image_url content, not local paths or remote image URLs.",
    },
    {
        "provider_id": "qwen",
        "display_name": "Qwen / DashScope",
        "urls": [
            "https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions",
            "https://help.aliyun.com/zh/model-studio/models",
            "https://help.aliyun.com/zh/model-studio/newly-released-models",
            "https://help.aliyun.com/zh/model-studio/qwen-api-via-dashscope",
            "https://qwen.ai/blog?id=qwen3.7",
            "https://qwen.ai/apiplatform",
        ],
        "source_status": "official_docs",
        "notes": "DashScope OpenAI-compatible endpoints use provider-specific sampling ranges.",
    },
]


SEED_PROVIDERS: list[dict[str, Any]] = [
    {
        "id": "yunwu",
        "display_name": "Yunwu",
        "enabled": True,
        "adapter_type": "responses",
        "base_url": "https://yunwu.ai/v1",
        "default_model": "gpt-5.5",
        "env_key": "YUNWU_API_KEY",
        "auth_mode": "env_ref",
        "proxy_mode": "direct",
        "proxy_url": "",
    },
    {
        "id": "deepseek",
        "display_name": "DeepSeek",
        "enabled": True,
        "adapter_type": "chat",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-v4-pro",
        "env_key": "DEEPSEEK_API_KEY",
        "auth_mode": "env_ref",
        "proxy_mode": "direct",
        "proxy_url": "",
    },
    {
        "id": "kimi",
        "display_name": "Kimi",
        "enabled": True,
        "adapter_type": "chat",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "kimi-k2.6",
        "env_key": "KIMI_API_KEY",
        "auth_mode": "env_ref",
        "proxy_mode": "direct",
        "proxy_url": "",
    },
    {
        "id": "qwen",
        "display_name": "Qwen / DashScope",
        "enabled": True,
        "adapter_type": "chat",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen3.7-max-2026-06-08",
        "env_key": "DASHSCOPE_API_KEY",
        "auth_mode": "env_ref",
        "proxy_mode": "direct",
        "proxy_url": "",
    },
]


def _source_urls(provider_id: str) -> list[str]:
    for source in DEFAULT_PROVIDER_SOURCES:
        if source["provider_id"] == provider_id:
            return list(source["urls"])
    return []


SEED_MODELS: list[dict[str, Any]] = [
    {
        "id": "yunwu/gpt-image-2",
        "provider": "yunwu",
        "native_model": "gpt-image-2",
        "display_name": "GPT Image 2",
        "enabled": False,
        "model_kind": "image_generation",
        "codex_agent_enabled": False,
        "advertised_context_window": 0,
        "input_modalities": ["text", "image"],
        "experimental_supported_tools": ["mcp:yunwu_image.yunwu_image_generate", "mcp:yunwu_image.yunwu_image_edit"],
        "mcp_verified_servers": ["yunwu_image"],
        "mcp_smoke_status": "pass",
        "modality_limits": {
            "codex_agent_model": False,
            "image_generation": "tool_only_via_yunwu_image_mcp",
            "default_generation_model": "gpt-image-2",
            "gpt-image-2-all": "smoke_503_no_available_channel_on_2026-06-12",
        },
        "source_status": "screenshot_seed",
        "verification_notes": "Stored as tool-only image workflow metadata; not exposed as Codex chat agent model. Real Yunwu smoke passed for gpt-image-2 on 2026-06-12; gpt-image-2-all returned 503 no available channel.",
    },
    *[
        {
            "id": f"yunwu/{model}",
            "provider": "yunwu",
            "native_model": model,
            "display_name": display,
            "enabled": True,
            "advertised_context_window": 1_000_000 if model not in {"gpt-5"} else 400_000,
            "supported_reasoning_levels": ["none", "low", "medium", "high", "xhigh"] if model in {"gpt-5.5", "gpt-5.4"} else ["minimal", "low", "medium", "high"],
            "default_reasoning_level": "high",
            "source_status": "screenshot_seed",
            "verification_notes": "Seeded from user screenshot; model capabilities inferred from OpenAI same-name or nearest-name docs where available.",
        }
        for model, display in [
            ("gpt-5.5", "GPT-5.5"),
            ("gpt-5.4", "GPT-5.4"),
            ("gpt-5.4-mini", "GPT-5.4 mini"),
            ("gpt-5.3-codex-spark", "GPT-5.3 Codex Spark"),
            ("gpt-5.1", "GPT-5.1"),
            ("gpt-5", "GPT-5"),
            ("gpt-5-codex", "GPT-5 Codex"),
            ("gpt-5.1-codex", "GPT-5.1 Codex"),
        ]
    ],
    {
        "id": "deepseek/deepseek-v4-pro",
        "provider": "deepseek",
        "native_model": "deepseek-v4-pro",
        "display_name": "DeepSeek V4 Pro",
        "enabled": True,
        "advertised_context_window": 1_000_000,
        "supported_reasoning_levels": ["high", "xhigh", "max"],
        "default_reasoning_level": "xhigh",
        "supports_mcp_tools": True,
        "mcp_tool_call_policy": "conservative",
        "mcp_verified_servers": ["lcr_web"],
        "mcp_smoke_status": "pass_direct_tool_call",
        "mcp_tool_argument_validation": "router_repair",
        "tool_web_search_support": "verified",
        "mcp_web_support": "verified_lcr_web",
        "web_smoke_status": "pass_direct_tool_call",
        "citation_quality": "requires_explicit_url_instruction",
        "source_status": "official_docs",
        "verification_notes": "Uses thinking enabled and reasoning_effort for upstream Chat Completions. LCR direct mcpServer/tool/call smoke passed for lcr_web_research_brief on 2026-06-15; keep arbitrary external MCP tools conservative until model-initiated smoke passes.",
    },
    {
        "id": "deepseek/deepseek-v4-flash",
        "provider": "deepseek",
        "native_model": "deepseek-v4-flash",
        "display_name": "DeepSeek V4 Flash",
        "enabled": True,
        "advertised_context_window": 1_000_000,
        "supported_reasoning_levels": ["off", "high"],
        "default_reasoning_level": "high",
        "source_status": "official_docs",
    },
    {
        "id": "kimi/kimi-k2.6",
        "provider": "kimi",
        "native_model": "kimi-k2.6",
        "display_name": "Kimi K2.6",
        "enabled": True,
        "advertised_context_window": 256_000,
        "input_modalities": ["text", "image", "video"],
        "supported_reasoning_levels": ["low", "medium", "high", "xhigh"],
        "default_reasoning_level": "high",
        "provider_temperature_min": 1.0,
        "provider_temperature_max": 1.0,
        "temperature_adapter_policy": "kimi_only_temperature_1",
        "modality_limits": {
            "image_transport": "chat_completions_base64_image_url",
            "remote_image_url_supported": False,
            "supported_image_formats": ["png", "jpeg", "webp", "gif"],
            "request_body_limit_mb": 100,
            "video_input": "provider_supported_unverified_in_lcr",
        },
        "source_urls": [
            "https://platform.kimi.com/docs/overview",
            "https://platform.kimi.com/docs/models",
            "https://platform.kimi.com/docs/guide/kimi-k2-6-quickstart",
        ],
        "source_status": "official_docs",
        "verification_notes": "K2.6 accepts image input through Chat Completions content parts when local images are converted to base64 data URLs. Real smoke test returned provider error unless temperature is omitted or exactly 1.",
    },
    {
        "id": "kimi/kimi-k2.5",
        "provider": "kimi",
        "native_model": "kimi-k2.5",
        "display_name": "Kimi K2.5",
        "enabled": True,
        "advertised_context_window": 256_000,
        "input_modalities": ["text", "image", "video"],
        "supported_reasoning_levels": ["low", "medium", "high", "xhigh"],
        "default_reasoning_level": "high",
        "provider_temperature_min": 1.0,
        "provider_temperature_max": 1.0,
        "temperature_adapter_policy": "kimi_only_temperature_1",
        "modality_limits": {
            "image_transport": "chat_completions_base64_image_url",
            "remote_image_url_supported": False,
            "supported_image_formats": ["png", "jpeg", "webp", "gif"],
            "request_body_limit_mb": 100,
            "video_input": "provider_supported_unverified_in_lcr",
        },
        "source_urls": [
            "https://platform.kimi.com/docs/overview",
            "https://platform.kimi.com/docs/models",
            "https://platform.kimi.com/docs/guide/kimi-k2-6-quickstart",
        ],
        "source_status": "official_docs",
        "verification_notes": "K2 generation controls are provider-specific; adapter omits non-1 temperature values.",
    },
    {
        "id": "kimi/moonshot-v1-32k",
        "provider": "kimi",
        "native_model": "moonshot-v1-32k",
        "display_name": "Moonshot V1 32K",
        "enabled": True,
        "advertised_context_window": 32_768,
        "supported_reasoning_levels": ["off"],
        "default_reasoning_level": "off",
        "source_status": "official_docs",
    },
    {
        "id": "qwen/qwen3.7-max-2026-06-08",
        "provider": "qwen",
        "native_model": "qwen3.7-max-2026-06-08",
        "display_name": "Qwen3.7 Max 2026-06-08",
        "enabled": True,
        "advertised_context_window": 1_000_000,
        "supported_reasoning_levels": ["low", "medium", "high", "xhigh"],
        "default_reasoning_level": "high",
        "provider_temperature_min": 0.00001,
        "provider_temperature_max": 1.0,
        "temperature_adapter_policy": "qwen_omit_zero_clamp_1",
        "source_status": "official_docs",
    },
    {
        "id": "qwen/qwen3.7-plus",
        "provider": "qwen",
        "native_model": "qwen3.7-plus",
        "display_name": "Qwen3.7 Plus",
        "enabled": True,
        "advertised_context_window": 1_000_000,
        "supported_reasoning_levels": ["low", "medium", "high", "xhigh"],
        "default_reasoning_level": "high",
        "provider_temperature_min": 0.00001,
        "provider_temperature_max": 1.0,
        "temperature_adapter_policy": "qwen_omit_zero_clamp_1",
        "source_status": "official_docs",
    },
    {
        "id": "qwen/qwen3.6-flash",
        "provider": "qwen",
        "native_model": "qwen3.6-flash",
        "display_name": "Qwen3.6 Flash",
        "enabled": True,
        "advertised_context_window": 1_000_000,
        "supported_reasoning_levels": ["low", "medium", "high"],
        "default_reasoning_level": "medium",
        "provider_temperature_min": 0.00001,
        "provider_temperature_max": 1.0,
        "temperature_adapter_policy": "qwen_omit_zero_clamp_1",
        "source_status": "official_docs",
    },
]


class MetadataService:
    def __init__(self, router_config, router, store_path: Path | None = None, report_root: Path | None = None) -> None:
        self._router_config = router_config
        self._router = router
        self.store_path = store_path or (app_data_dir() / "metadata_sources.json")
        self.report_root = report_root or _default_report_root()

    def sources(self) -> dict[str, Any]:
        payload = read_json(self.store_path, {})
        if not isinstance(payload, dict) or not payload.get("providers"):
            payload = {"providers": DEFAULT_PROVIDER_SOURCES, "updated_at": now_iso()}
            write_json(self.store_path, payload)
        return payload

    def save_sources(self, payload: dict[str, Any]) -> dict[str, Any]:
        providers = [dict(item) for item in list(payload.get("providers") or []) if isinstance(item, dict)]
        saved = {"providers": providers, "updated_at": now_iso()}
        write_json(self.store_path, saved)
        return saved

    def import_seed(self, *, apply: bool = True) -> dict[str, Any]:
        providers = [_provider_seed(item) for item in SEED_PROVIDERS]
        models = [_model_seed(item) for item in SEED_MODELS]
        if apply:
            for provider in providers:
                self._router_config.upsert_provider(provider)
            for model in models:
                self._router_config.upsert_model(model)
            self.sources()
        return {"applied": apply, "providers": providers, "models": models, "model_count": len(models)}

    def refresh(self, *, apply: bool = False) -> dict[str, Any]:
        sources = self.sources()
        fetched = []
        for provider in sources.get("providers") or []:
            for url in list(provider.get("urls") or []):
                fetched.append(_fetch_source_status(str(provider.get("provider_id") or ""), str(url)))
        seed = self.import_seed(apply=apply)
        return {"applied": apply, "fetched": fetched, "proposed": seed, "updated_at": now_iso()}

    def effective_catalog(self, model_id: str | None = None) -> dict[str, Any]:
        models = []
        for model in self._router_config.models():
            if model_id and str(model.get("id")) != model_id:
                continue
            if not bool(model.get("codex_agent_enabled", True)):
                continue
            provider = str(model.get("provider") or "")
            native = str(model.get("native_model") or "")
            context_window = int(model.get("advertised_context_window") or known_context_window(provider, native) or 128_000)
            models.append(
                model_catalog_entry(
                    model_id=str(model.get("id") or f"{provider}/{native}"),
                    provider_id=provider,
                    native_model=native,
                    display_name=str(model.get("display_name") or native),
                    context_window=context_window,
                    configured_model=model,
                    auto_compact_token_limit=_optional_positive_int(model.get("auto_compact_token_limit")),
                )
            )
        return {"models": models, "model_count": len(models), "generated_at": now_iso()}

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
                f"<td>{html.escape(str(model.get('mcp_tool_call_policy') or 'unsupported'))}</td>"
                f"<td>{html.escape(str(model.get('mcp_smoke_status') or 'untested'))}</td>"
                f"<td>{html.escape(str(model.get('native_web_search_support') or 'unverified'))}</td>"
                f"<td>{html.escape(str(model.get('tool_web_search_support') or 'unverified'))}</td>"
                f"<td>{html.escape(str(model.get('web_smoke_status') or 'untested'))}</td>"
                f"<td>{html.escape(str((model.get('context_compaction_support') or {}).get('structured_summary_quality') if isinstance(model.get('context_compaction_support'), dict) else 'untested'))}</td>"
                f"<td>{html.escape(str(model.get('source_status')))}</td>"
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
                f"<td>{html.escape(str(result.get('web_smoke_status') or ''))}</td>"
                f"<td>{html.escape(str(result.get('status') or result.get('reason') or result.get('error') or ''))}</td>"
                "</tr>"
            )
        source_cards = []
        for provider in sources.get("providers") or []:
            links = "".join(f"<li><a href=\"{html.escape(str(url))}\">{html.escape(str(url))}</a></li>" for url in list(provider.get("urls") or []))
            source_cards.append(f"<section><h2>{html.escape(str(provider.get('display_name') or provider.get('provider_id')))}</h2><p>{html.escape(str(provider.get('notes') or ''))}</p><ul>{links}</ul></section>")
        html_text = f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>LCR Model Metadata Report</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:28px;background:#f6f2eb;color:#23272f}}a{{color:#2459b8}}table{{border-collapse:collapse;width:100%;background:#fff}}td,th{{border:1px solid #ddd;padding:8px;text-align:left}}th{{background:#f0ede7}}section{{background:#fff;border:1px solid #ddd;border-radius:14px;padding:16px;margin:14px 0}}.muted{{color:#68707d}}
</style></head>
<body><h1>AstraBridge Model Metadata Report</h1><p class="muted">Generated at {html.escape(now_iso())}. Secrets are not included.</p>
<nav><a href="#sources">Sources</a> · <a href="#models">Models</a> · <a href="#tests">Smoke Tests</a> · <a href="effective-catalog.json">Effective Codex catalog JSON</a></nav>
<h2 id="sources">Sources</h2>{''.join(source_cards)}
<h2 id="models">Models</h2><table><thead><tr><th>ID</th><th>Name</th><th>Provider</th><th>Context</th><th>Input</th><th>Temperature policy</th><th>Pricing</th><th>MCP policy</th><th>MCP smoke</th><th>Native web</th><th>Tool web</th><th>Web smoke</th><th>Compact quality</th><th>Source</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2 id="tests">Smoke Tests</h2><table><thead><tr><th>Status</th><th>Provider</th><th>Model</th><th>Effort</th><th>Temp</th><th>Web</th><th>Detail</th></tr></thead><tbody>{''.join(result_rows)}</tbody></table>
</body></html>"""
        target = self.report_root / "index.html"
        target.write_text(html_text, encoding="utf-8", newline="\n")
        return {"path": str(target), "catalog_path": str(self.report_root / "effective-catalog.json"), "config_path": str(self.report_root / "router-config.json")}


def _provider_seed(provider: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_timeout_ms": 300000,
        "stream_idle_timeout_ms": 300000,
        "auth_key_ref": None,
        **provider,
    }


def _model_seed(model: dict[str, Any]) -> dict[str, Any]:
    provider = str(model.get("provider") or "")
    native = str(model.get("native_model") or "")
    context_window = int(model.get("advertised_context_window") or known_context_window(provider, native) or 128_000)
    return {
        "enabled": True,
        "advertised_context_window": context_window,
        "ui_context_hint_only": True,
        "adapter_profile": "default",
        "input_modalities": ["text"],
        "source_urls": _source_urls(provider),
        "temperature_default": 0,
        "temperature_ui_min": 0,
        "temperature_ui_max": 2,
        "provider_temperature_min": 0,
        "provider_temperature_max": 2,
        "temperature_adapter_policy": "pass_through_0_2",
        **_pricing_seed(provider, native),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        **model,
    }


def _pricing_seed(provider: str, native: str) -> dict[str, Any]:
    key = (provider.lower(), native.lower())
    pricing: dict[tuple[str, str], dict[str, Any]] = {
        ("deepseek", "deepseek-v4-pro"): {
            "pricing_currency": "USD",
            "pricing_cached_input_per_mtok": 0.003625,
            "pricing_input_per_mtok": 0.435,
            "pricing_output_per_mtok": 0.87,
            "pricing_source_url": "https://api-docs.deepseek.com/quick_start/pricing",
            "pricing_status": "official_docs",
        },
        ("deepseek", "deepseek-v4-flash"): {
            "pricing_currency": "USD",
            "pricing_cached_input_per_mtok": 0.0028,
            "pricing_input_per_mtok": 0.14,
            "pricing_output_per_mtok": 0.28,
            "pricing_source_url": "https://api-docs.deepseek.com/quick_start/pricing",
            "pricing_status": "official_docs",
        },
        ("kimi", "kimi-k2.6"): {
            "pricing_currency": "USD",
            "pricing_cached_input_per_mtok": 0.16,
            "pricing_input_per_mtok": 0.95,
            "pricing_output_per_mtok": 4.0,
            "pricing_source_url": "https://platform.moonshot.ai/",
            "pricing_status": "official_platform",
        },
        ("kimi", "kimi-k2.5"): {
            "pricing_currency": "USD",
            "pricing_cached_input_per_mtok": 0.10,
            "pricing_input_per_mtok": 0.60,
            "pricing_output_per_mtok": 3.0,
            "pricing_source_url": "https://platform.moonshot.ai/",
            "pricing_status": "official_platform",
        },
        ("yunwu", "gpt-5.5"): {
            "pricing_currency": "CNY",
            "pricing_input_per_mtok": 4.0,
            "pricing_output_per_mtok": 24.0,
            "pricing_source_url": "https://yunwu.ai/pricing?group=Codex%E4%B8%93%E5%B1%9E",
            "pricing_status": "screenshot_seed",
        },
        ("yunwu", "gpt-5.4"): {
            "pricing_currency": "CNY",
            "pricing_input_per_mtok": 2.0,
            "pricing_output_per_mtok": 12.0,
            "pricing_cached_input_per_mtok": 0.2,
            "pricing_source_url": "https://yunwu.ai/pricing?group=Codex%E4%B8%93%E5%B1%9E",
            "pricing_status": "screenshot_seed",
        },
    }
    return dict(pricing.get(key) or {"pricing_currency": "", "pricing_status": "unknown"})


def _fetch_source_status(provider_id: str, url: str) -> dict[str, Any]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "AstraBridge/metadata-curator"})
        with urllib.request.urlopen(request, timeout=12) as response:
            body = response.read(200_000)
            return {"provider_id": provider_id, "url": url, "ok": True, "status": response.status, "bytes": len(body)}
    except Exception as exc:  # noqa: BLE001
        return {"provider_id": provider_id, "url": url, "ok": False, "error": str(exc)[:300]}


def _default_key_files() -> dict[str, str]:
    desktop = Path.home() / "Desktop"
    return {
        "yunwu": str(desktop / "gptimg2.txt"),
        "deepseek": str(desktop / "dskeynew.txt"),
        "qwen": str(desktop / "ali.txt"),
        "kimi": str(desktop / "kimi.txt"),
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
        return workflow / "lcr-model-metadata-report"
    return app_data_dir() / "model-metadata-report"

