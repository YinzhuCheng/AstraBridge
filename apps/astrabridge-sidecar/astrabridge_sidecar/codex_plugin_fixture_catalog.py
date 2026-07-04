from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable

from .security import resolve_under


CopyTreeFn = Callable[..., Any]
RemoveTreeFn = Callable[..., Any]

_FIXTURE_RELATIVE_ROOT = Path("fixtures") / "plugin-fixture-catalog"
_TRACKED_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "plugin_fixture_catalog"


def materialize_controlled_plugin_fixture_catalog(
    shell_state_root: Path,
    *,
    source_root: Path | None = None,
    copytree_fn: CopyTreeFn = shutil.copytree,
    rmtree_fn: RemoveTreeFn = shutil.rmtree,
) -> dict[str, Any]:
    shell_state_root = Path(shell_state_root).expanduser().resolve()
    tracked_root = Path(source_root or _TRACKED_FIXTURE_ROOT).expanduser().resolve()
    contract_path = tracked_root / "fixture-contract.json"
    target_root = resolve_under(shell_state_root, _FIXTURE_RELATIVE_ROOT)
    target_contract_path = target_root / "fixture-contract.json"

    if not contract_path.exists():
        return {
            "status": "source_missing",
            "search_root": None,
            "fixture_root": None,
            "marketplace_path": None,
            "plugin_ids": [],
        }

    contract_text = contract_path.read_text(encoding="utf-8")
    contract = json.loads(contract_text)
    source = dict(contract.get("source") or {})
    plugin = dict(contract.get("plugin") or {})
    marketplace_rel = Path(str(source.get("marketplace_path_rel") or ".agents/plugins/marketplace.json"))

    status = "reused"
    if not target_contract_path.exists() or target_contract_path.read_text(encoding="utf-8") != contract_text:
        if target_root.exists():
            rmtree_fn(target_root)
        target_root.parent.mkdir(parents=True, exist_ok=True)
        copytree_fn(tracked_root, target_root)
        status = "materialized"

    plugin_id = str(plugin.get("plugin_id") or "").strip()
    return {
        "status": status,
        "search_root": str(target_root),
        "fixture_root": str(target_root),
        "marketplace_path": str((target_root / marketplace_rel).resolve()),
        "plugin_ids": [plugin_id] if plugin_id else [],
    }


def is_managed_plugin_fixture_path(path: Path) -> bool:
    candidate = Path(path).expanduser().resolve()
    candidate_parts = [part.lower() for part in candidate.parts]
    marker_parts = [part.lower() for part in _FIXTURE_RELATIVE_ROOT.parts]
    width = len(marker_parts)
    return any(candidate_parts[index : index + width] == marker_parts for index in range(0, len(candidate_parts) - width + 1))
