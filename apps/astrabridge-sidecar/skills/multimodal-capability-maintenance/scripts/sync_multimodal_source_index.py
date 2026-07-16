from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _bootstrap() -> Path:
    sidecar_root = Path(__file__).resolve().parents[3]
    if str(sidecar_root) not in sys.path:
        sys.path.insert(0, str(sidecar_root))
    return sidecar_root.parents[1]


REPO_ROOT = _bootstrap()

from astrabridge_sidecar.model_catalog.source_registry import (  # noqa: E402
    MANAGED_PROVIDER_IDS,
    default_provider_source_registry,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the canonical multimodal provider source index.")
    parser.add_argument("--workspace-root", default=str(REPO_ROOT))
    parser.add_argument("--out", required=True)
    parser.add_argument("--providers", default=",".join(MANAGED_PROVIDER_IDS))
    return parser.parse_args()


def _provider_set(raw: str) -> set[str]:
    return {item.strip() for item in str(raw or "").split(",") if item.strip()}


def _source_kind(record: dict[str, Any]) -> str:
    source_type = str(record.get("source_type") or "").strip()
    if source_type in {"api_reference", "models_catalog", "pricing", "release_notes"}:
        return source_type
    return "guide"


def _minimal_required_sources(source_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    priority_types = ("models_catalog", "api_reference", "guide")
    for source_type in priority_types:
        for record in source_records:
            record_type = str(record.get("source_type") or "").strip()
            source_id = str(record.get("source_id") or "").strip()
            if record_type != source_type or source_id in seen:
                continue
            selected.append(
                {
                    "source_id": source_id,
                    "url": record.get("url"),
                    "source_type": record_type,
                    "capability_categories": list(record.get("capability_categories") or []),
                }
            )
            seen.add(source_id)
    return selected


def main() -> None:
    args = _parse_args()
    selected_providers = _provider_set(args.providers)
    records = [
        item
        for item in default_provider_source_registry()
        if str(item.get("provider_id") or "") in selected_providers
    ]
    payload = {
        "schema_version": "astrabridge-multimodal-source-index-v1",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "workspace_root": str(Path(args.workspace_root).resolve()),
        "source_pack_path": str((REPO_ROOT / "PLAN" / "MULTIMODAL_PROVIDER_OFFICIAL_SOURCE_PACK.md").resolve()),
        "provider_ids": [str(item.get("provider_id") or "") for item in records],
        "providers": [],
    }
    for item in records:
        source_records = list(item.get("source_records") or [])
        payload["providers"].append(
            {
                "provider_id": item.get("provider_id"),
                "display_name": item.get("display_name"),
                "source_status": item.get("source_status"),
                "trust_level": item.get("trust_level"),
                "promotion_policy": dict(item.get("promotion_policy") or {}),
                "source_count": len(source_records),
                "primary_urls": [record.get("url") for record in source_records if str(record.get("source_role") or "") == "primary_source"],
                "minimal_required_sources": _minimal_required_sources(source_records),
                "source_records": [
                    {
                        "source_id": record.get("source_id"),
                        "url": record.get("url"),
                        "source_kind": _source_kind(record),
                        "source_type": record.get("source_type"),
                        "trust_level": record.get("trust_level"),
                        "channel": record.get("channel"),
                        "parser_strategy": record.get("parser_strategy"),
                        "retrieved_on": record.get("retrieved_on"),
                        "stale_after_days": record.get("stale_after_days"),
                        "capability_categories": list(record.get("capability_categories") or []),
                        "promotable": bool(record.get("promotable")),
                        "requires_manual_review": bool(record.get("requires_manual_review")),
                    }
                    for record in source_records
                ],
            }
        )
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
