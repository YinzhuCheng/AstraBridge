from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


SIDECAR_ROOT = Path(__file__).resolve().parents[3]
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.agentic_updates import parse_agentic_update_source_pack, run_agentic_update_discovery  # noqa: E402
from astrabridge_sidecar.agentic_updates.artifacts import ensure_agentic_update_run_layout  # noqa: E402
from astrabridge_sidecar.agentic_updates.contracts import assert_secret_free_agentic_update_payload  # noqa: E402
from astrabridge_sidecar.common import now_iso, write_json  # noqa: E402


PROVIDERS = ("qwen", "deepseek", "kimi", "glm")


def run_coverage(*, workspace_root: Path, run_id: str) -> dict[str, Any]:
    provider_sources, fixture_sources = _fixtures()
    contract = {
        "scope": "provider_metadata",
        "providers": list(PROVIDERS),
        "allow_network": False,
    }
    discovery = run_agentic_update_discovery(
        workspace_root=workspace_root,
        run_id=run_id,
        run_contract=contract,
        provider_sources=provider_sources,
        fixture_sources=fixture_sources,
        max_sources=8,
    )
    first = parse_agentic_update_source_pack(
        workspace_root=workspace_root,
        run_id=run_id,
        source_pack_path=discovery["artifact_paths"]["source_pack"],
    )
    second = parse_agentic_update_source_pack(
        workspace_root=workspace_root,
        run_id=run_id,
        source_pack_path=discovery["artifact_paths"]["source_pack"],
    )
    proposals = list(first.get("proposals") or [])
    by_provider = {
        provider_id: sorted(str(item.get("model_id") or "") for item in proposals if item.get("provider_id") == provider_id)
        for provider_id in PROVIDERS
    }
    deterministic = first.get("proposals") == second.get("proposals") and first.get("warnings") == second.get("warnings")
    complete = all(by_provider.values())
    layout = ensure_agentic_update_run_layout(workspace_root, run_id)
    report_path = Path(layout["run_root"]) / "validation" / "four-provider-coverage.json"
    report = {
        "schema_version": "astrabridge-four-provider-parser-coverage-v1",
        "generated_at": now_iso(),
        "run_id": run_id,
        "status": "pass" if complete and deterministic else "blocked",
        "provider_calls_attempted": False,
        "network_calls_attempted": False,
        "apply_attempted": False,
        "providers": by_provider,
        "source_count": discovery.get("summary", {}).get("total_sources"),
        "proposal_count": len(proposals),
        "deterministic": deterministic,
        "parser_implementations": {
            provider_id: first.get("parser_stubs", {}).get(provider_id, {}).get("implementation")
            for provider_id in PROVIDERS
        },
        "artifact_paths": {
            "source_pack": discovery["artifact_paths"]["source_pack"],
            "parser_output": first["artifact_paths"]["parser_output"],
            "coverage_report": str(report_path),
        },
    }
    assert_secret_free_agentic_update_payload(report, label="four_provider_parser_coverage")
    write_json(report_path, report)
    return report


def _provider_source(
    provider_id: str,
    source_id: str,
    url: str,
    parser_strategy: str,
    *,
    platform_id: str | None = None,
) -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "display_name": provider_id.title(),
        "source_status": "official_docs",
        "source_type": "models_catalog",
        "trust_level": "official",
        "channel": "stable_docs",
        "parser_strategy": parser_strategy,
        "stale_after_days": 7,
        "source_records": [
            {
                "source_id": source_id,
                "url": url,
                "platform_id": platform_id,
                "source_type": "models_catalog",
                "trust_level": "official",
                "channel": "stable_docs",
                "parser_strategy": parser_strategy,
                "stale_after_days": 7,
            }
        ],
    }


def _fixtures() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    providers = [
        _provider_source("qwen", "qwen-official", "https://help.aliyun.com/zh/model-studio/text-generation-model/", "html_table"),
        _provider_source("deepseek", "deepseek-official", "https://api-docs.deepseek.com/quick_start/pricing/", "html_table"),
        _provider_source(
            "kimi",
            "kimi-official",
            "https://platform.kimi.com/docs/models.md",
            "markdown_table",
            platform_id="platform.kimi.com",
        ),
        _provider_source("glm", "glm-official", "https://docs.z.ai/guides/llm/glm-5.2.md", "markdown_document"),
    ]
    fixtures = {
        "qwen-official": {
            "content_type": "text/html; charset=utf-8",
            "body": "<table><tr><td>qwen3.7-plus</td><td>1,000,000 tokens</td><td>text and image input</td></tr></table>",
        },
        "deepseek-official": {
            "content_type": "text/html; charset=utf-8",
            "body": (
                "<table><tr><td>deepseek-v4-pro</td><td>$0.003625</td><td>$0.435</td><td>$0.87</td></tr></table>"
                "<p>deepseek-v4-pro has a 1,000,000 token context, tool calls, and reasoning_effort values 'high' and 'max'.</p>"
            ),
        },
        "kimi-official": {
            "content_type": "text/markdown; charset=utf-8",
            "body": (
                "| Model Name | Description |\n| --- | --- |\n"
                "| `kimi-k3` | 1,048,576 tokens; text, image, and video input; ToolCalls; reasoning_effort 'low', 'high', 'max', default 'max'. |\n"
            ),
        },
        "glm-official": {
            "content_type": "text/markdown; charset=utf-8",
            "body": (
                "# GLM-5.2\n`glm-5.2` has a 1,000,000-token context and function calling. "
                "`reasoning_effort` accepts `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, and `max`; default `max`."
            ),
        },
    }
    return providers, fixtures


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic provider-free parser coverage for Qwen, DeepSeek, Kimi, and GLM.")
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    report = run_coverage(workspace_root=args.workspace_root.resolve(), run_id=str(args.run_id))
    print({"status": report["status"], "providers": report["providers"], "report": report["artifact_paths"]["coverage_report"]})
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
