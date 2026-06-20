from __future__ import annotations

import mimetypes
import hashlib
import re
import shutil
from pathlib import Path
from typing import Any

from .common import WORKSPACE_STATE_DIRNAME, now_iso, read_json, slugify, write_json
from .security import SECRET_RE, SecurityError, redact_sensitive, resolve_under, scan_text_for_secrets


REGISTRY_SCHEMA_VERSION = "lcr-asset-registry-v1"
CONTEXT_SCHEMA_VERSION = "lcr-asset-context-pack-v1"


class AssetRegistryService:
    """Project-local asset memory for generated/sliced/promoted dogfood assets.

    The registry is intentionally stored under `.astrabridge/assets` and contains only
    paths, provenance, quality notes, and integration state. It never stores
    provider keys or raw Authorization-bearing request payloads.
    """

    def __init__(self, project_service, task_service=None) -> None:
        self._projects = project_service
        self._tasks = task_service

    def snapshot(self, *, rebuild_if_missing: bool = True) -> dict[str, Any]:
        path = self._registry_path()
        if rebuild_if_missing and not path.exists():
            self.rebuild()
        registry = self._normalize_registry(read_json(path, {}))
        if not path.exists():
            write_json(path, registry)
        context_pack = self.context_pack(registry=registry)
        self._write_context_pack(registry)
        self._record_context_ref(context_pack)
        return {
            "registry": registry,
            "path": str(path),
            "context_pack": context_pack,
        }

    def concise_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Return a safe default payload for UI/operator calls.

        The full registry can contain hundreds of image records. It is written
        to disk for durable memory, but default API callers only need the
        summary and context refs; returning the full list by default can flood
        agent context after a routine rebuild.
        """
        registry = self._normalize_registry(dict(response.get("registry") or {}))
        context_pack = dict(response.get("context_pack") or self.context_pack(registry=registry))
        assets = list(registry.get("assets") or [])
        return {
            "path": str(response.get("path") or self._registry_path()),
            "registry_path": str(self._registry_path()),
            "asset_count": len(assets),
            "summary": self._summary(assets),
            "context_pack": {
                "schema_version": str(context_pack.get("schema_version") or CONTEXT_SCHEMA_VERSION),
                "generated_at": str(context_pack.get("generated_at") or ""),
                "context_pack_path": str(context_pack.get("context_pack_path") or self._context_pack_path()),
                "registry_path": str(context_pack.get("registry_path") or self._registry_path()),
                "summary": dict(context_pack.get("summary") or self._summary(assets)),
            },
        }

    def rebuild(self) -> dict[str, Any]:
        workspace = self._workspace()
        generated = self._read_generated_manifest()
        sliced = self._read_sliced_manifest()
        game_manifest = self._read_game_sprite_manifest()

        entries: dict[str, dict[str, Any]] = {}
        for item in list(generated.get("assets") or []):
            if not isinstance(item, dict):
                continue
            asset_id = str(item.get("asset_id") or "").strip()
            if not asset_id:
                continue
            source_path = self._coerce_workspace_path(item.get("local_path"))
            purpose = str(item.get("purpose") or "").strip()
            validation_warnings = [str(flag) for flag in list(item.get("validation_warnings") or [])[:12]]
            transparency_failed = any(
                flag in {"transparent_contract_failed", "alpha_channel_missing", "alpha_ratio_too_low"}
                for flag in validation_warnings
            )
            kind = self._infer_kind(purpose, item.get("prompt"), source_path.name if source_path else "")
            entry = {
                "asset_id": asset_id,
                "parent_asset_id": "",
                "stage": "generated",
                "kind": kind,
                "asset_type": kind,
                "role": purpose or kind,
                "purpose": purpose,
                "status": "generated",
                "quality_status": "failed" if transparency_failed else "unreviewed",
                "integration_status": "not_promoted",
                "provider": str(item.get("provider") or ""),
                "model": str(item.get("model") or ""),
                "tool": str(item.get("tool") or ""),
                "source": str(item.get("source") or ""),
                "size": str(item.get("size") or ""),
                "format": str(item.get("format") or ""),
                "requested_background": str(item.get("requested_background") or ""),
                "actual_width": item.get("actual_width"),
                "actual_height": item.get("actual_height"),
                "actual_format": str(item.get("actual_format") or ""),
                "actual_mode": str(item.get("actual_mode") or ""),
                "has_alpha": bool(item.get("has_alpha")),
                "transparent_pixel_ratio": item.get("transparent_pixel_ratio"),
                "semi_transparent_pixel_ratio": item.get("semi_transparent_pixel_ratio"),
                "transparency_status": str(item.get("transparency_status") or ""),
                "source_url": str(item.get("source_url") or ""),
                "prompt_excerpt": self._clip(item.get("prompt"), 500),
                "source_path": self._relative_path(source_path) if source_path else "",
                "sliced_manifest_path": "",
                "promoted_path": "",
                "game_refs": [],
                "warnings": validation_warnings,
                "created_at": str(item.get("generated_at") or item.get("created") or ""),
                "updated_at": now_iso(),
            }
            if source_path and not source_path.exists():
                entry["warnings"].append("source_missing")
            entries[asset_id] = entry

        sheet_quality: dict[str, dict[str, Any]] = {}
        for sheet in list(sliced.get("sheets") or []):
            if not isinstance(sheet, dict):
                continue
            parent_id = str(sheet.get("asset_id") or "").strip()
            manifest_path = self._coerce_workspace_path(sheet.get("manifest_path"))
            quality_passed = bool(sheet.get("quality_gate_passed"))
            review_needed = bool(sheet.get("manual_review_needed"))
            sheet_quality[parent_id] = {
                "strategy": str(sheet.get("strategy") or ""),
                "manifest_path": self._relative_path(manifest_path) if manifest_path else "",
                "quality_gate_passed": quality_passed,
                "manual_review_needed": review_needed,
                "summary": str(sheet.get("summary") or ""),
            }
            if parent_id in entries:
                entries[parent_id]["sliced_manifest_path"] = sheet_quality[parent_id]["manifest_path"]
                entries[parent_id]["quality_status"] = "passed" if quality_passed and not review_needed else "needs_review"
                entries[parent_id]["status"] = "sliced"
            if manifest_path and manifest_path.exists():
                self._merge_sliced_assets(entries, parent_id, manifest_path, sheet_quality[parent_id])

        manifest_ref_map = self._game_manifest_ref_map(game_manifest)
        promoted_refs = sorted(manifest_ref_map)
        self._mark_game_references(entries, promoted_refs, manifest_ref_map, game_manifest)
        self._add_untracked_game_sprites(entries, promoted_refs, manifest_ref_map)

        registry = self._normalize_registry(
            {
                "schema_version": REGISTRY_SCHEMA_VERSION,
                "rebuilt_at": now_iso(),
                "workspace_root": str(workspace),
                "sources": {
                    "generated_manifest": self._relative_path(self._generated_manifest_path()),
                    "sliced_manifest": self._relative_path(self._sliced_manifest_path()),
                    "game_sprite_manifest": self._relative_path(self._game_sprite_manifest_path()),
                },
                "assets": sorted(entries.values(), key=lambda item: (str(item.get("kind") or ""), str(item.get("asset_id") or ""))),
            }
        )
        write_json(self._registry_path(), registry)
        context_pack = self.context_pack(registry=registry)
        self._write_context_pack(registry, context_pack=context_pack)
        self._record_context_ref(context_pack)
        return {"registry": registry, "path": str(self._registry_path()), "context_pack": context_pack}

    def mark(self, payload: dict[str, Any]) -> dict[str, Any]:
        asset_id = str(payload.get("asset_id") or "").strip()
        if not asset_id:
            raise ValueError("asset_id is required.")
        registry = self.snapshot()["registry"]
        changed = False
        for entry in registry["assets"]:
            if str(entry.get("asset_id")) != asset_id:
                continue
            for key in ("status", "quality_status", "integration_status", "role", "purpose"):
                if key in payload:
                    entry[key] = str(payload.get(key) or "").strip()
            notes = str(payload.get("notes") or "").strip()
            if notes:
                entry.setdefault("notes", [])
                entry["notes"] = [notes, *list(entry.get("notes") or [])][:20]
            entry["updated_at"] = now_iso()
            changed = True
            break
        if not changed:
            raise ValueError(f"Unknown asset_id: {asset_id}")
        self._reject_secret_like(registry)
        write_json(self._registry_path(), registry)
        context_pack = self.context_pack(registry=registry)
        self._write_context_pack(registry, context_pack=context_pack)
        self._record_context_ref(context_pack)
        return {"registry": registry, "path": str(self._registry_path()), "context_pack": context_pack}

    def promote(self, payload: dict[str, Any]) -> dict[str, Any]:
        asset_id = str(payload.get("asset_id") or "").strip()
        if not asset_id:
            raise ValueError("asset_id is required.")
        registry = self.snapshot()["registry"]
        entry = self._find_entry(registry, asset_id)
        if not entry:
            raise ValueError(f"Unknown asset_id: {asset_id}")
        source = self._source_path_for_entry(entry)
        if not source or not source.is_file():
            raise FileNotFoundError(f"Asset source file is missing for {asset_id}")
        scan_text_for_secrets(source)

        target_name = self._target_name(payload, entry, source)
        sprites_dir = self._workspace() / "assets" / "images" / "sprites"
        sprites_dir.mkdir(parents=True, exist_ok=True)
        target = resolve_under(self._workspace(), sprites_dir / target_name)
        transform = self._promote_asset_file(source, target, payload)

        ref = f"sprites/{target.name}"
        manifest = self._read_game_sprite_manifest()
        self._update_game_manifest(manifest, payload, entry, ref, transform=transform)
        write_json(self._game_sprite_manifest_path(), manifest)

        entry["promoted_path"] = self._relative_path(target)
        entry["integration_status"] = "promoted"
        entry["status"] = "promoted"
        if transform:
            entry["promote_transform"] = transform
            entry["sprite_width"] = transform.get("output_width")
            entry["sprite_height"] = transform.get("output_height")
            if transform.get("pivot"):
                entry["pivot"] = transform.get("pivot")
        refs = list(entry.get("game_refs") or [])
        if ref not in refs:
            refs.append(ref)
        entry["game_refs"] = refs
        entry["updated_at"] = now_iso()
        self._reject_secret_like(registry)
        write_json(self._registry_path(), registry)
        context_pack = self.context_pack(registry=registry)
        self._write_context_pack(registry, context_pack=context_pack)
        self._record_context_ref(context_pack)
        return {
            "asset": entry,
            "target_path": str(target),
            "game_ref": ref,
            "game_manifest_path": str(self._game_sprite_manifest_path()),
            "registry": registry,
            "context_pack": context_pack,
        }

    def context_pack(self, *, registry: dict[str, Any] | None = None) -> dict[str, Any]:
        registry = self._normalize_registry(registry or read_json(self._registry_path(), {}))
        assets = list(registry.get("assets") or [])
        promoted = [item for item in assets if item.get("integration_status") in {"promoted", "in_use"} or item.get("promoted_path")]
        approved = [
            item
            for item in assets
            if item.get("quality_status") == "passed" and item.get("integration_status") not in {"promoted", "in_use"}
        ]
        needs_review = [item for item in assets if item.get("quality_status") in {"needs_review", "failed", "unreviewed"}][:12]
        summary = self._summary(assets)
        asset_gaps = self._asset_gaps(assets)
        rules = [
            "Use .astrabridge/assets/asset_registry.json as durable asset memory; do not infer from raw runtime logs.",
            "Use promoted assets in assets/images/sprites first; promote approved generated/sliced assets before relying on them in game code.",
            "Do not use keys, doors, stairs, HUD icons, floors, or generic prop sprites as blocking walls; generate/promote dedicated tree_wall, rock_wall, ruin_wall, or forest_obstacle sprites first.",
            "Heroine movement needs distinct idle/walk_down/walk_up/walk_left/walk_right frames, at least two walk frames per direction.",
            "Use reference images for consistent heroine/monster families; use multi-asset sheets only for same-category assets with transparent background and large gutters.",
            "For checkerboard or plain backgrounds, detect the background mask and remove it before connected-component slicing.",
        ]
        text_lines = [
            "AstraBridge Asset Context Pack (auto-injected, secret-free)",
            "Freshness rule: this asset pack supersedes any older auto-injected asset summary already present in the thread history.",
            "If promoted counts, asset_type, manifest_keys, or in_use state conflict, use this newest pack and .astrabridge/assets/asset_registry.json.",
            f"Registry: {self._relative_path(self._registry_path())}",
            f"Detailed context: {self._relative_path(self._context_pack_path())}",
            "Access note: the paths above are orientation references. Do not call MCP resources/read for them; use the injected summary unless an explicit file-reading tool is available.",
            f"Summary: {summary}",
            "Current rules:",
            *[f"- {rule}" for rule in rules],
            "Only a small priority slice is auto-injected; read the registry/context files if you need the full list.",
        ]
        if asset_gaps:
            text_lines.append("Current asset gaps / hard constraints:")
            for gap in asset_gaps[:6]:
                text_lines.append(
                    f"- {gap.get('gap_id')}: {gap.get('message')} "
                    f"needed={','.join(list(gap.get('needed_kinds') or [])[:6])}"
                )
        if promoted:
            text_lines.append("Priority promoted/in-game assets:")
            for item in promoted[:10]:
                text_lines.append(
                    f"- {item.get('asset_id')} role={item.get('role')} kind={item.get('kind')} "
                    f"manifest={','.join(list(item.get('manifest_keys') or [])[:3])} "
                    f"path={item.get('promoted_path') or item.get('source_path')}"
                )
            if len(promoted) > 10:
                text_lines.append(f"- ... {len(promoted) - 10} more promoted/in-use assets in asset_registry.json")
        if approved:
            text_lines.append("Priority approved but not promoted:")
            for item in approved[:6]:
                text_lines.append(
                    f"- {item.get('asset_id')} role={item.get('role')} kind={item.get('kind')} source={item.get('source_path')}"
                )
            if len(approved) > 6:
                text_lines.append(f"- ... {len(approved) - 6} more approved assets in asset_registry.json")
        if needs_review:
            text_lines.append("Priority needs review or redraw:")
            for item in needs_review[:6]:
                text_lines.append(
                    f"- {item.get('asset_id')} role={item.get('role')} quality={item.get('quality_status')} warnings={','.join(list(item.get('warnings') or [])[:3])}"
                )
            if len(needs_review) > 6:
                text_lines.append(f"- ... {len(needs_review) - 6} more review items in asset_registry.json")
        text = "\n".join(text_lines)
        return {
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "generated_at": now_iso(),
            "registry_path": str(self._registry_path()),
            "context_pack_path": str(self._context_pack_path()),
            "summary": summary,
            "rules": rules,
            "asset_gaps": asset_gaps,
            "promoted": [self._compact_entry(item) for item in promoted[:30]],
            "approved_unpromoted": [self._compact_entry(item) for item in approved[:30]],
            "needs_review": [self._compact_entry(item) for item in needs_review[:30]],
            "text": text[:5000],
        }

    def context_inputs(self) -> list[dict[str, Any]]:
        try:
            registry = self.snapshot()["registry"]
        except Exception:
            return []
        assets = list(registry.get("assets") or [])
        if not assets:
            return []
        pack = self.context_pack(registry=registry)
        self._write_context_pack(registry, context_pack=pack)
        self._record_context_ref(pack)
        inputs: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": pack["text"],
                "text_elements": [],
            }
        ]
        return inputs

    def _merge_sliced_assets(
        self,
        entries: dict[str, dict[str, Any]],
        parent_id: str,
        manifest_path: Path,
        sheet_quality: dict[str, Any],
    ) -> None:
        manifest = read_json(manifest_path, {})
        base_dir = manifest_path.parent
        strategy = str(manifest.get("strategy") or sheet_quality.get("strategy") or "")
        quality_gate = dict(manifest.get("quality_gate") or {})
        sheet_passed = bool(quality_gate.get("passed", sheet_quality.get("quality_gate_passed")))
        review_needed = bool(manifest.get("manual_review_needed", sheet_quality.get("manual_review_needed")))
        for item in list(manifest.get("assets") or []):
            if not isinstance(item, dict):
                continue
            asset_id = str(item.get("asset_id") or "").strip()
            if not asset_id:
                continue
            file_name = str(item.get("file") or "").strip()
            source_path = base_dir / file_name if file_name else None
            role = str(item.get("class") or strategy or "").strip()
            confidence = item.get("confidence")
            warnings = [str(flag) for flag in list(item.get("quality_flags") or [])[:12]]
            entries[asset_id] = {
                "asset_id": asset_id,
                "parent_asset_id": parent_id,
                "stage": "sliced",
                "kind": self._infer_kind(role, strategy, file_name),
                "asset_type": self._infer_kind(role, strategy, file_name),
                "role": role or self._infer_kind(role, strategy, file_name),
                "purpose": str(entries.get(parent_id, {}).get("purpose") or ""),
                "status": "approved" if sheet_passed and not review_needed and not warnings else "needs_review",
                "quality_status": "passed" if sheet_passed and not review_needed and not warnings else "needs_review",
                "integration_status": "not_promoted",
                "provider": str(entries.get(parent_id, {}).get("provider") or ""),
                "model": str(entries.get(parent_id, {}).get("model") or ""),
                "tool": "sprite_slicer",
                "source": strategy,
                "size": "",
                "format": source_path.suffix.lstrip(".") if source_path else "",
                "source_url": str(entries.get(parent_id, {}).get("source_url") or ""),
                "prompt_excerpt": str(entries.get(parent_id, {}).get("prompt_excerpt") or ""),
                "source_path": self._relative_path(source_path) if source_path else "",
                "sliced_manifest_path": self._relative_path(manifest_path),
                "promoted_path": "",
                "game_refs": [],
                "warnings": warnings,
                "metrics": {
                    "confidence": confidence,
                    "pixel_count": item.get("pixel_count"),
                    "solidity": item.get("solidity"),
                    "alpha_coverage_pct": item.get("alpha_coverage_pct"),
                    "source_bbox": item.get("source_bbox"),
                },
                "created_at": str(manifest.get("generated_at") or ""),
                "updated_at": now_iso(),
            }
            if source_path and not source_path.exists():
                entries[asset_id]["warnings"].append("source_missing")

    def _mark_game_references(
        self,
        entries: dict[str, dict[str, Any]],
        refs: list[str],
        manifest_ref_map: dict[str, list[str]],
        manifest: dict[str, Any],
    ) -> None:
        source_sheets = dict(self._read_game_sprite_manifest().get("source_sheets") or {})
        for key, parent_id in source_sheets.items():
            if parent_id in entries:
                entries[parent_id]["integration_status"] = "in_use"
                entries[parent_id]["status"] = "in_use"
                entries[parent_id]["game_refs"] = sorted(set(list(entries[parent_id].get("game_refs") or []) + [f"source_sheets.{key}"]))
                entries[parent_id]["manifest_keys"] = sorted(set(list(entries[parent_id].get("manifest_keys") or []) + [f"source_sheets.{key}"]))
        promoted_assets = dict(manifest.get("promoted_assets") or {})
        for asset_id, promoted in promoted_assets.items():
            if not isinstance(promoted, dict) or asset_id not in entries:
                continue
            ref = str(promoted.get("ref") or "")
            role = str(promoted.get("role") or "")
            kind = self._infer_kind(promoted.get("kind"), role, ref, asset_id)
            entries[asset_id]["kind"] = kind
            entries[asset_id]["asset_type"] = kind
            if role:
                entries[asset_id]["role"] = role
            entries[asset_id]["integration_status"] = "in_use" if ref in refs else "promoted"
            entries[asset_id]["status"] = entries[asset_id]["integration_status"]
            entries[asset_id]["promoted_path"] = entries[asset_id].get("promoted_path") or f"assets/images/{ref}"
            entries[asset_id]["game_refs"] = sorted(set(list(entries[asset_id].get("game_refs") or []) + ([ref] if ref else [])))
            entries[asset_id]["manifest_keys"] = sorted(set(list(entries[asset_id].get("manifest_keys") or []) + manifest_ref_map.get(ref, [])))
            transform = promoted.get("transform")
            if isinstance(transform, dict) and transform:
                entries[asset_id]["promote_transform"] = transform
                if transform.get("pivot"):
                    entries[asset_id]["pivot"] = transform.get("pivot")
                entries[asset_id]["sprite_width"] = transform.get("output_width")
                entries[asset_id]["sprite_height"] = transform.get("output_height")
        for entry in entries.values():
            promoted = str(entry.get("promoted_path") or "")
            source = str(entry.get("source_path") or "")
            matches = [ref for ref in refs if promoted.endswith(ref) or source.endswith(ref) or Path(ref).name == Path(promoted or source).name]
            if matches:
                entry["integration_status"] = "in_use"
                entry["status"] = "in_use"
                entry["game_refs"] = sorted(set(list(entry.get("game_refs") or []) + matches))
                manifest_keys: list[str] = []
                for ref in matches:
                    manifest_keys.extend(manifest_ref_map.get(ref, []))
                entry["manifest_keys"] = sorted(set(list(entry.get("manifest_keys") or []) + manifest_keys))
        self._link_copied_game_assets_by_hash(entries, refs, manifest_ref_map)

    def _add_untracked_game_sprites(self, entries: dict[str, dict[str, Any]], refs: list[str], manifest_ref_map: dict[str, list[str]]) -> None:
        workspace = self._workspace()
        for ref in refs:
            if self._ref_is_already_linked(entries, ref):
                continue
            path = workspace / "assets" / "images" / ref
            if not path.is_file():
                path = workspace / "assets" / "images" / "sprites" / Path(ref).name
            if not path.is_file():
                continue
            asset_id = f"game-{Path(ref).stem}"
            if asset_id in entries:
                continue
            kind = self._infer_kind(ref, "", path.name)
            entries[asset_id] = {
                "asset_id": asset_id,
                "parent_asset_id": "",
                "stage": "game_sprite",
                "kind": kind,
                "asset_type": kind,
                "role": Path(ref).stem,
                "purpose": "existing_game_sprite",
                "status": "in_use",
                "quality_status": "unknown",
                "integration_status": "in_use",
                "provider": "",
                "model": "",
                "tool": "game_manifest_scan",
                "source": "assets/images/sprites",
                "size": "",
                "format": path.suffix.lstrip("."),
                "source_url": "",
                "prompt_excerpt": "",
                "source_path": self._relative_path(path),
                "sliced_manifest_path": "",
                "promoted_path": self._relative_path(path),
                "game_refs": [ref],
                "manifest_keys": manifest_ref_map.get(ref, []),
                "warnings": ["not_linked_to_generated_asset"],
                "created_at": "",
                "updated_at": now_iso(),
            }

    def _link_copied_game_assets_by_hash(
        self,
        entries: dict[str, dict[str, Any]],
        refs: list[str],
        manifest_ref_map: dict[str, list[str]],
    ) -> None:
        workspace = self._workspace()
        ref_hashes: dict[str, str] = {}
        for ref in refs:
            path = workspace / "assets" / "images" / ref
            if not path.is_file():
                path = workspace / "assets" / "images" / "sprites" / Path(ref).name
            digest = self._file_digest(path)
            if digest:
                ref_hashes[ref] = digest
        if not ref_hashes:
            return
        digest_to_refs: dict[str, list[str]] = {}
        for ref, digest in ref_hashes.items():
            digest_to_refs.setdefault(digest, []).append(ref)
        for entry in entries.values():
            source = self._coerce_workspace_path(entry.get("source_path"))
            source_digest = self._file_digest(source)
            if not source_digest:
                continue
            matches = digest_to_refs.get(source_digest, [])
            if not matches:
                continue
            entry["integration_status"] = "in_use"
            entry["status"] = "in_use"
            existing_refs = list(entry.get("game_refs") or [])
            entry["game_refs"] = sorted(set(existing_refs + matches))
            existing_keys = list(entry.get("manifest_keys") or [])
            manifest_keys: list[str] = []
            for ref in matches:
                manifest_keys.extend(manifest_ref_map.get(ref, []))
            entry["manifest_keys"] = sorted(set(existing_keys + manifest_keys))
            entry["promoted_path"] = entry.get("promoted_path") or f"assets/images/{matches[0]}"
            warnings = list(entry.get("warnings") or [])
            if "linked_by_content_hash" not in warnings:
                warnings.append("linked_by_content_hash")
            entry["warnings"] = warnings[:12]

    def _ref_is_already_linked(self, entries: dict[str, dict[str, Any]], ref: str) -> bool:
        for entry in entries.values():
            if ref in list(entry.get("game_refs") or []):
                return True
            promoted = str(entry.get("promoted_path") or "")
            if promoted.endswith(ref):
                return True
        return False

    def _file_digest(self, path: Path | None) -> str:
        if not path or not path.is_file():
            return ""
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _update_game_manifest(
        self,
        manifest: dict[str, Any],
        payload: dict[str, Any],
        entry: dict[str, Any],
        ref: str,
        *,
        transform: dict[str, Any] | None = None,
    ) -> None:
        manifest.setdefault("manifest_version", 1)
        manifest["updated_at"] = now_iso()
        manifest.setdefault("sprites", {})
        manifest.setdefault("tiles", {})
        manifest.setdefault("promoted_assets", {})
        section = str(payload.get("manifest_section") or "").strip().lower()
        kind = str(entry.get("kind") or "")
        role = str(payload.get("role") or entry.get("role") or "")
        if not section:
            section = "tiles" if kind in {"terrain", "door", "stairs", "key", "prop"} else "sprites"
        if section == "tiles":
            key = str(payload.get("tile_key") or payload.get("state") or role or Path(ref).stem).strip()
            manifest.setdefault("tiles", {})[slugify(key, Path(ref).stem)] = ref
        elif section == "hud":
            key = str(payload.get("state") or payload.get("hud_key") or role or Path(ref).stem).strip()
            manifest.setdefault("sprites", {}).setdefault("hud", {})[slugify(key, Path(ref).stem)] = ref
        else:
            entity = str(payload.get("entity") or self._default_entity(entry)).strip()
            state = str(payload.get("state") or self._default_state(entry)).strip()
            manifest.setdefault("sprites", {}).setdefault(slugify(entity, "asset"), {})[slugify(state, "grid")] = ref
        promoted: dict[str, Any] = {
            "ref": ref,
            "role": role,
            "kind": kind,
            "promoted_at": now_iso(),
        }
        if transform:
            promoted["transform"] = transform
            if transform.get("pivot"):
                promoted["pivot"] = transform.get("pivot")
        manifest["promoted_assets"][str(entry["asset_id"])] = promoted

    def _promote_asset_file(self, source: Path, target: Path, payload: dict[str, Any]) -> dict[str, Any]:
        crop_to_alpha = bool(payload.get("crop_to_alpha") or payload.get("crop_transparent_bounds"))
        output_size = self._parse_output_size(payload.get("output_size") or payload.get("sprite_size"))
        pivot = self._normalize_pivot(payload.get("pivot") or payload.get("anchor") or ("bottom_center" if output_size else ""))
        if not crop_to_alpha and not output_size:
            shutil.copy2(source, target)
            return {}
        try:
            from PIL import Image  # type: ignore
        except Exception as exc:  # pragma: no cover - depends on runtime packaging
            raise RuntimeError("Pillow is required for crop/resize asset promotion.") from exc

        with Image.open(source) as image:
            original_size = image.size
            working = image.convert("RGBA")
            crop_box = (0, 0, working.width, working.height)
            if crop_to_alpha:
                alpha = working.getchannel("A")
                bbox = alpha.getbbox()
                if bbox:
                    padding = self._safe_int(payload.get("padding"), default=4, minimum=0, maximum=256)
                    left = max(0, bbox[0] - padding)
                    top = max(0, bbox[1] - padding)
                    right = min(working.width, bbox[2] + padding)
                    bottom = min(working.height, bbox[3] + padding)
                    crop_box = (left, top, right, bottom)
                    working = working.crop(crop_box)
            output_width = working.width
            output_height = working.height
            if output_size:
                output_width, output_height = output_size
                canvas = Image.new("RGBA", output_size, (0, 0, 0, 0))
                scale = min(output_width / max(1, working.width), output_height / max(1, working.height))
                resized_size = (max(1, round(working.width * scale)), max(1, round(working.height * scale)))
                resample = getattr(Image, "Resampling", Image).LANCZOS
                resized = working.resize(resized_size, resample)
                x = (output_width - resized.width) // 2
                if pivot == "bottom_center":
                    y = output_height - resized.height
                else:
                    y = (output_height - resized.height) // 2
                canvas.alpha_composite(resized, (x, y))
                working = canvas
            if target.suffix.lower() not in {".png", ".webp"}:
                target = target.with_suffix(".png")
            working.save(target)
            return {
                "crop_to_alpha": crop_to_alpha,
                "crop_box": list(crop_box),
                "original_width": original_size[0],
                "original_height": original_size[1],
                "output_width": working.width,
                "output_height": working.height,
                "pivot": pivot or None,
            }

    def _parse_output_size(self, value: Any) -> tuple[int, int] | None:
        if value in (None, "", False):
            return None
        if isinstance(value, int):
            size = self._safe_int(value, default=0, minimum=1, maximum=2048)
            return (size, size)
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return (
                self._safe_int(value[0], default=0, minimum=1, maximum=2048),
                self._safe_int(value[1], default=0, minimum=1, maximum=2048),
            )
        text = str(value).strip().lower().replace(" ", "")
        if "x" in text:
            left, right = text.split("x", 1)
            return (
                self._safe_int(left, default=0, minimum=1, maximum=2048),
                self._safe_int(right, default=0, minimum=1, maximum=2048),
            )
        size = self._safe_int(text, default=0, minimum=1, maximum=2048)
        return (size, size)

    def _safe_int(self, value: Any, *, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except Exception:
            parsed = default
        if parsed < minimum:
            return minimum
        if parsed > maximum:
            return maximum
        return parsed

    def _normalize_pivot(self, value: Any) -> str:
        raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if raw in {"bottom", "bottom_center", "center_bottom"}:
            return "bottom_center"
        if raw in {"center", "middle", "center_center"}:
            return "center"
        return raw if raw else ""

    def _target_name(self, payload: dict[str, Any], entry: dict[str, Any], source: Path) -> str:
        raw = str(payload.get("target_name") or "").strip()
        if not raw:
            raw = f"{slugify(str(entry.get('role') or entry.get('asset_id') or 'asset'), 'asset')}{source.suffix or '.png'}"
        name = Path(raw).name
        if not Path(name).suffix:
            name = f"{name}{source.suffix or '.png'}"
        if not re.match(r"^[0-9A-Za-z._-]+$", name):
            name = f"{slugify(Path(name).stem, 'asset')}{Path(name).suffix or source.suffix or '.png'}"
        return name

    def _default_entity(self, entry: dict[str, Any]) -> str:
        kind = str(entry.get("kind") or "")
        role = str(entry.get("role") or "")
        if kind == "heroine":
            return "heroine"
        if kind == "monster":
            return role or "monster"
        return kind or role or "asset"

    def _default_state(self, entry: dict[str, Any]) -> str:
        role = str(entry.get("role") or "").lower()
        if "walk_down" in role:
            return "walk_down"
        if "walk_up" in role:
            return "walk_up"
        if "walk_left" in role:
            return "walk_left"
        if "walk_right" in role:
            return "walk_right"
        if "idle" in role:
            return "idle"
        if "fullbody" in role:
            return "fullbody"
        if "bust" in role:
            return "bust"
        return "grid"

    def _find_entry(self, registry: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
        for entry in list(registry.get("assets") or []):
            if str(entry.get("asset_id") or "") == asset_id:
                return entry
        return None

    def _source_path_for_entry(self, entry: dict[str, Any]) -> Path | None:
        for key in ("source_path", "promoted_path"):
            raw = str(entry.get(key) or "").strip()
            if raw:
                return self._coerce_workspace_path(raw)
        return None

    def _summary(self, assets: list[dict[str, Any]]) -> dict[str, Any]:
        by_stage: dict[str, int] = {}
        by_kind: dict[str, int] = {}
        promoted = 0
        approved_unpromoted = 0
        needs_review = 0
        for item in assets:
            by_stage[str(item.get("stage") or "unknown")] = by_stage.get(str(item.get("stage") or "unknown"), 0) + 1
            by_kind[str(item.get("kind") or "unknown")] = by_kind.get(str(item.get("kind") or "unknown"), 0) + 1
            if item.get("integration_status") in {"promoted", "in_use"} or item.get("promoted_path"):
                promoted += 1
            elif item.get("quality_status") == "passed":
                approved_unpromoted += 1
            else:
                needs_review += 1
        return {
            "total": len(assets),
            "by_stage": by_stage,
            "by_kind": by_kind,
            "promoted_or_in_use": promoted,
            "approved_unpromoted": approved_unpromoted,
            "needs_review": needs_review,
        }

    def _normalize_registry(self, payload: Any) -> dict[str, Any]:
        registry = dict(payload or {}) if isinstance(payload, dict) else {}
        assets = [dict(item) for item in list(registry.get("assets") or []) if isinstance(item, dict)]
        for item in assets:
            kind = str(item.get("kind") or item.get("asset_type") or self._infer_kind(item.get("role"), item.get("source_path"), item.get("promoted_path")))
            item["kind"] = kind
            item["asset_type"] = str(item.get("asset_type") or kind)
            item["manifest_keys"] = list(item.get("manifest_keys") or [])
            item["manifest_key"] = str(item.get("manifest_key") or (item["manifest_keys"][0] if item["manifest_keys"] else ""))
            item["game_refs"] = list(item.get("game_refs") or [])
            item["in_use"] = bool(
                item.get("in_use")
                or str(item.get("integration_status") or "").strip().lower() == "in_use"
                or str(item.get("status") or "").strip().lower() == "in_use"
            )
        registry.update(
            {
                "schema_version": str(registry.get("schema_version") or REGISTRY_SCHEMA_VERSION),
                "rebuilt_at": str(registry.get("rebuilt_at") or ""),
                "workspace_root": str(registry.get("workspace_root") or self._workspace()),
                "sources": dict(registry.get("sources") or {}),
                "assets": assets,
                "summary": self._summary(assets),
            }
        )
        self._reject_secret_like(registry)
        return registry

    def _compact_entry(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "asset_id": item.get("asset_id"),
            "kind": item.get("kind"),
            "asset_type": item.get("asset_type") or item.get("kind"),
            "role": item.get("role"),
            "status": item.get("status"),
            "quality_status": item.get("quality_status"),
            "integration_status": item.get("integration_status"),
            "in_use": bool(
                item.get("in_use")
                or str(item.get("integration_status") or "").strip().lower() == "in_use"
                or str(item.get("status") or "").strip().lower() == "in_use"
            ),
            "source_path": item.get("source_path"),
            "promoted_path": item.get("promoted_path"),
            "game_refs": item.get("game_refs") or [],
            "manifest_key": str(item.get("manifest_key") or (list(item.get("manifest_keys") or [])[:1] or [""])[0]),
            "manifest_keys": item.get("manifest_keys") or [],
            "warnings": list(item.get("warnings") or [])[:5],
        }

    def _asset_gaps(self, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []
        if assets and not any(self._is_blocking_obstacle_asset(item) for item in assets):
            gaps.append(
                {
                    "gap_id": "blocking_obstacle_sprites_missing",
                    "severity": "high",
                    "needed_kinds": ["tree_wall", "forest_obstacle", "rock_wall", "ruin_wall"],
                    "forbidden_substitutes": ["key", "door", "stairs", "hud", "floor", "heroine", "monster", "generic_prop"],
                    "message": (
                        "No dedicated blocking wall/forest/rock obstacle sprite is registered. "
                        "Do not repurpose keys, doors, stairs, HUD icons, floor tiles, or generic props as walls."
                    ),
                    "recommended_next_step": "Generate or promote transparent tree_wall/rock_wall/ruin_wall assets before replacing WALL visuals.",
                }
            )
        return gaps

    def _is_blocking_obstacle_asset(self, item: dict[str, Any]) -> bool:
        text = " ".join(
            str(item.get(key) or "")
            for key in (
                "asset_id",
                "kind",
                "asset_type",
                "role",
                "purpose",
                "source_path",
                "promoted_path",
            )
        ).lower()
        if not text.strip():
            return False
        if any(token in text for token in ("key", "door", "stairs", "stair", "hud", "icon", "heroine", "monster", "enemy")):
            return False
        return any(
            token in text
            for token in (
                "tree_wall",
                "forest_wall",
                "forest_obstacle",
                "rock_wall",
                "ruin_wall",
                "wall_obstacle",
                "wall_tile",
                "blocker",
                "blocking",
                "obstacle",
                "bush_wall",
            )
        )

    def _write_context_pack(self, registry: dict[str, Any], *, context_pack: dict[str, Any] | None = None) -> None:
        write_json(self._context_pack_path(), context_pack or self.context_pack(registry=registry))

    def _record_context_ref(self, context_pack: dict[str, Any]) -> None:
        if self._tasks is None:
            return
        ref = {
            "pack_type": "asset",
            "path": str(context_pack.get("context_pack_path") or self._context_pack_path()),
            "generated_at": str(context_pack.get("generated_at") or now_iso()),
            "summary": {
                "summary": dict(context_pack.get("summary") or {}),
            },
        }
        if self._try_record_context_ref(self._tasks, ref):
            return
        fresh_tasks = self._fresh_task_service()
        if fresh_tasks is not None and self._try_record_context_ref(fresh_tasks, ref):
            return
        raise RuntimeError("Failed to persist asset context ref into task state.")

    def _try_record_context_ref(self, task_service: Any, ref: dict[str, Any]) -> bool:
        try:
            task_service.record_context_ref(**ref)
        except Exception:
            return False
        task = task_service.current_task() if hasattr(task_service, "current_task") else None
        return self._task_has_context_ref(task, ref)

    def _task_has_context_ref(self, task: Any, ref: dict[str, Any]) -> bool:
        if not isinstance(task, dict):
            return False
        for item in list(task.get("asset_context_refs") or []):
            if not isinstance(item, dict):
                continue
            if (
                str(item.get("pack_type") or "") == str(ref.get("pack_type") or "")
                and str(item.get("path") or "") == str(ref.get("path") or "")
                and str(item.get("generated_at") or "") == str(ref.get("generated_at") or "")
            ):
                return True
        return False

    def _fresh_task_service(self) -> Any | None:
        project_file = str((self._projects.current_project or {}).get("project_file") or "").strip()
        if not project_file:
            return None
        try:
            from .project_service import ProjectService
            from .task_service import TaskService

            fresh_projects = ProjectService()
            fresh_projects.open_project(project_file)
            return TaskService(fresh_projects)
        except Exception:
            return None

    def _game_manifest_refs(self, manifest: dict[str, Any]) -> list[str]:
        return sorted(self._game_manifest_ref_map(manifest).keys())

    def _game_manifest_ref_map(self, manifest: dict[str, Any]) -> dict[str, list[str]]:
        refs: dict[str, list[str]] = {}

        def visit(value: Any, path: str) -> None:
            if isinstance(value, str) and value.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                refs.setdefault(value, [])
                refs[value].append(path)
            elif isinstance(value, dict):
                for key, child in value.items():
                    visit(child, f"{path}.{key}" if path else str(key))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, f"{path}[{index}]")

        visit(manifest.get("sprites") or {}, "sprites")
        visit(manifest.get("tiles") or {}, "tiles")
        return {key: sorted(set(paths)) for key, paths in refs.items()}

    def _legacy_game_manifest_refs(self, manifest: dict[str, Any]) -> list[str]:
        refs: list[str] = []

        def visit(value: Any) -> None:
            if isinstance(value, str) and value.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                refs.append(value)
            elif isinstance(value, dict):
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(manifest.get("sprites") or {})
        visit(manifest.get("tiles") or {})
        return sorted(set(refs))

    def _read_generated_manifest(self) -> dict[str, Any]:
        return dict(read_json(self._generated_manifest_path(), {}))

    def _read_sliced_manifest(self) -> dict[str, Any]:
        return dict(read_json(self._sliced_manifest_path(), {}))

    def _read_game_sprite_manifest(self) -> dict[str, Any]:
        return dict(read_json(self._game_sprite_manifest_path(), {}))

    def _registry_path(self) -> Path:
        return self._assets_root() / "asset_registry.json"

    def _context_pack_path(self) -> Path:
        return self._assets_root() / "asset_context_pack.json"

    def _assets_root(self) -> Path:
        return self._projects.require_shell_state_root() / "assets"

    def _generated_manifest_path(self) -> Path:
        return self._assets_root() / "generated" / "asset_manifest.json"

    def _sliced_manifest_path(self) -> Path:
        return self._assets_root() / "sliced" / "sliced_manifest.json"

    def _game_sprite_manifest_path(self) -> Path:
        return self._workspace() / "assets" / "images" / "sprites" / "sprite_manifest.json"

    def _workspace(self) -> Path:
        return self._projects.require_workspace_root()

    def _coerce_workspace_path(self, value: Any) -> Path | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        normalized = raw.replace("\\", "/")
        match = re.match(r"^/mnt/([a-zA-Z])/(.*)$", normalized)
        if match:
            return Path(f"{match.group(1).upper()}:/") / match.group(2)
        path = Path(raw)
        if not path.is_absolute():
            path = self._workspace() / path
        return path

    def _relative_path(self, path: Path | None) -> str:
        if path is None:
            return ""
        try:
            resolved = path.resolve()
            workspace = self._workspace().resolve()
            if resolved == workspace or workspace in resolved.parents:
                return resolved.relative_to(workspace).as_posix()
        except Exception:
            pass
        return str(path)

    def _infer_kind(self, *values: Any) -> str:
        text = " ".join(str(value or "") for value in values).lower()
        if any(token in text for token in ("heroine", "player", "walk_", "fullbody", "bust")):
            return "heroine"
        if any(token in text for token in ("monster", "enemy", "mushroom", "wisp", "lantern", "witch", "sprite_sheet")):
            return "monster"
        if "hud" in text:
            return "hud"
        if "door" in text:
            return "door"
        if "stairs" in text or "stair" in text:
            return "stairs"
        if "key" in text:
            return "key"
        if any(token in text for token in ("hud", "icon", "heart", "star", "shield")):
            return "hud"
        if any(token in text for token in ("crystal", "gem", "prop", "chest")):
            return "prop"
        if any(token in text for token in ("forest", "wall", "floor", "terrain", "tile", "autotile", "grass")):
            return "terrain"
        mime = mimetypes.guess_type(text)[0] or ""
        if mime.startswith("image/"):
            return "image"
        return "asset"

    def _clip(self, value: Any, limit: int) -> str:
        return str(value or "").strip()[:limit]

    def _reject_secret_like(self, payload: dict[str, Any]) -> None:
        serialized = str(redact_sensitive(payload))
        if SECRET_RE.search(serialized):
            raise SecurityError("Secret-like content is not allowed in asset registry records.")

