from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .app_server_client import JsonRpcError
from .codex_app_server_probe import ProbeClientFactory
from .common import app_runtime_dir, new_id, now_iso, write_json
from .security import redact_sensitive


def probe_skill_discovery(
    *,
    codex_home: Path,
    client_factory: ProbeClientFactory | None = None,
    local_search_roots: list[Path] | None = None,
    artifact_root: Path | None = None,
    request_timeout: float = 20.0,
) -> dict[str, Any]:
    probe_id = new_id("codex-skill-probe")
    generated_at = now_iso()
    artifact_dir = (artifact_root or app_runtime_dir("kernel-probes")).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report_path = artifact_dir / f"{probe_id}.json"
    codex_home_path = Path(codex_home).resolve()
    search_roots = _resolve_search_roots(codex_home_path, local_search_roots)
    warnings: list[str] = []

    plugin_context = _scan_local_plugin_context(search_roots)
    warnings.extend(plugin_context["warnings"])

    status = {
        "list_status": "not_checked",
        "extra_roots_status": "declared",
        "config_write_status": "declared",
        "change_notification_status": "declared",
    }
    discovered_by_key: dict[str, dict[str, Any]] = {}
    discovered_roots: list[str] = [str(root) for root in search_roots]
    list_errors: list[dict[str, str]] = []

    if client_factory is not None:
        client = client_factory(lambda method, params: None, lambda method, params: {})
        try:
            client.start()
            try:
                result = client.request(
                    "skills/list",
                    {"cwds": [str(root) for root in search_roots], "forceReload": True},
                    timeout=request_timeout,
                )
                if isinstance(result, dict) and isinstance(result.get("data"), list):
                    status["list_status"] = "supported"
                    for entry in list(result.get("data") or []):
                        if not isinstance(entry, dict):
                            continue
                        cwd = str(entry.get("cwd") or "").strip()
                        if cwd:
                            discovered_roots.append(cwd)
                        for error in list(entry.get("errors") or []):
                            if not isinstance(error, dict):
                                continue
                            list_errors.append(
                                {
                                    "path": str(error.get("path") or "").strip(),
                                    "message": str(error.get("message") or "").strip()[:240],
                                }
                            )
                        for skill in list(entry.get("skills") or []):
                            if not isinstance(skill, dict):
                                continue
                            record = _runtime_skill_record(skill, plugin_context["plugin_roots"])
                            _merge_skill_record(discovered_by_key, record)
                else:
                    status["list_status"] = "incompatible_response"
                    warnings.append("skills/list returned an incompatible response shape.")
            except TimeoutError:
                status["list_status"] = "timeout"
                warnings.append("skills/list timed out.")
            except JsonRpcError as exc:
                status["list_status"] = _skill_command_status(exc)
                if status["list_status"] != "unsupported":
                    warnings.append(f"skills/list returned JSON-RPC error code {exc.code}.")
            except Exception as exc:  # noqa: BLE001
                status["list_status"] = "error"
                warnings.append(f"skills/list failed: {str(exc)[:240]}")
        finally:
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass

    fallback = _scan_local_skill_manifests(search_roots, plugin_context["plugin_roots"])
    warnings.extend(fallback["warnings"])
    list_errors.extend(fallback["errors"])
    for record in fallback["skills"]:
        _merge_skill_record(discovered_by_key, record)
    discovered_roots.extend(fallback["discovered_roots"])

    discovered_skills = sorted(discovered_by_key.values(), key=lambda item: (str(item.get("skill_name") or ""), str(item.get("path") or "")))
    duplicate_skill_names = _duplicate_skill_names(discovered_skills)
    missing_description_paths = sorted(
        {
            str(item.get("path") or "")
            for item in discovered_skills
            if str(item.get("description_status") or "") == "missing" and str(item.get("path") or "").strip()
        }
    )
    malformed_skill_paths = sorted(
        {
            str(item.get("path") or "")
            for item in discovered_skills
            if str(item.get("manifest_status") or "") == "malformed" and str(item.get("path") or "").strip()
        }
    )
    if duplicate_skill_names:
        warnings.append(f"Duplicate skill names were discovered: {', '.join(duplicate_skill_names)}")
    if missing_description_paths:
        warnings.append(f"Skill manifests missing descriptions: {', '.join(missing_description_paths)}")

    report = {
        "schema_version": "codex-skill-probe-v1",
        "generated_at": generated_at,
        "probe_id": probe_id,
        "report_path": str(report_path),
        "skill": {
            **status,
            "codex_home": str(codex_home_path),
            "discovered_roots": sorted({root for root in discovered_roots if str(root).strip()}),
            "discovered_skills": discovered_skills,
            "duplicate_skill_names": duplicate_skill_names,
            "malformed_skill_paths": malformed_skill_paths,
            "missing_description_paths": missing_description_paths,
            "errors": _dedupe_errors(list_errors),
            "notes": _skill_notes(discovered_skills, duplicate_skill_names, malformed_skill_paths, missing_description_paths),
        },
        "known_warnings": _dedupe_preserve_order(warnings),
    }
    sanitized = redact_sensitive(report)
    write_json(report_path, sanitized)
    return sanitized


def _resolve_search_roots(codex_home: Path, local_search_roots: list[Path] | None) -> list[Path]:
    roots = [codex_home]
    for root in list(local_search_roots or []):
        candidate = Path(root).resolve()
        if candidate not in roots:
            roots.append(candidate)
    return roots


def _skill_command_status(exc: JsonRpcError) -> str:
    if int(exc.code or 0) == -32601:
        return "unsupported"
    return "error_response"


def _scan_local_plugin_context(search_roots: list[Path]) -> dict[str, Any]:
    plugin_roots: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen_roots: set[Path] = set()

    for root in search_roots:
        for marketplace_path in sorted(root.rglob("marketplace.json")):
            payload = _read_json_file(marketplace_path)
            if not isinstance(payload, dict):
                continue
            marketplace_name = str(payload.get("name") or marketplace_path.stem).strip() or marketplace_path.stem
            for entry in list(payload.get("plugins") or []):
                if not isinstance(entry, dict):
                    continue
                plugin_name = str(entry.get("name") or "").strip()
                source = entry.get("source")
                source_payload = source if isinstance(source, dict) else {}
                source_type = str(source_payload.get("source") or source_payload.get("type") or "").strip()
                if source_type != "local":
                    continue
                relative_path = str(source_payload.get("path") or "").strip()
                if not plugin_name or not relative_path:
                    continue
                plugin_root = (marketplace_path.parent / relative_path).resolve()
                if plugin_root in seen_roots:
                    continue
                seen_roots.add(plugin_root)
                manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
                manifest = _read_json_file(manifest_path)
                version = str((manifest or {}).get("version") or "").strip() if isinstance(manifest, dict) else ""
                plugin_roots.append(
                    {
                        "plugin_id": plugin_name,
                        "plugin_root": str(plugin_root),
                        "marketplace_name": marketplace_name,
                        "marketplace_path": str(marketplace_path.resolve()),
                        "version_hint": version or None,
                    }
                )

        for manifest_path in sorted(root.rglob("plugin.json")):
            if manifest_path.parent.name != ".codex-plugin":
                continue
            plugin_root = manifest_path.parent.parent.resolve()
            if plugin_root in seen_roots:
                continue
            seen_roots.add(plugin_root)
            manifest = _read_json_file(manifest_path)
            if not isinstance(manifest, dict):
                warnings.append(f"Plugin manifest is malformed while scanning skill ownership: {manifest_path}")
                continue
            plugin_roots.append(
                {
                    "plugin_id": str(manifest.get("name") or plugin_root.name).strip() or plugin_root.name,
                    "plugin_root": str(plugin_root),
                    "marketplace_name": None,
                    "marketplace_path": None,
                    "version_hint": str(manifest.get("version") or "").strip() or None,
                }
            )

    return {"plugin_roots": plugin_roots, "warnings": warnings}


def _runtime_skill_record(skill: dict[str, Any], plugin_roots: list[dict[str, Any]]) -> dict[str, Any]:
    path = str(skill.get("path") or "").strip()
    skill_name = str(skill.get("name") or Path(path).parent.name or "").strip()
    description = str(skill.get("description") or "").strip()
    interface = skill.get("interface")
    interface_payload = interface if isinstance(interface, dict) else {}
    owner = _skill_owner(Path(path), plugin_roots) if path else None
    scope = str(skill.get("scope") or "").strip()
    source_kind = _source_kind(path, scope, owner)
    trigger_hints = _trigger_hints(
        description=description or None,
        short_description=str(skill.get("shortDescription") or interface_payload.get("shortDescription") or "").strip() or None,
        default_prompt=str(interface_payload.get("defaultPrompt") or "").strip() or None,
        skill_name=skill_name,
    )
    return {
        "skill_name": skill_name,
        "display_name": str(interface_payload.get("displayName") or skill_name).strip() or skill_name,
        "description": description or None,
        "description_status": "present" if description else "missing",
        "source_kind": source_kind,
        "owner_plugin_id": owner.get("plugin_id") if owner else None,
        "enablement": "enabled" if bool(skill.get("enabled", False)) else "disabled",
        "path": path or None,
        "scope": scope or None,
        "trigger_hints": trigger_hints,
        "version_hint": owner.get("version_hint") if owner else None,
        "content_sha256": _file_sha256(Path(path)) if path else None,
        "manifest_status": "ok" if path else "not_checked",
        "dependency_tools": _dependency_tools(skill.get("dependencies")),
        "icon_small": str(interface_payload.get("iconSmall") or "").strip() or None,
        "icon_large": str(interface_payload.get("iconLarge") or "").strip() or None,
        "brand_color": str(interface_payload.get("brandColor") or "").strip() or None,
    }


def _scan_local_skill_manifests(search_roots: list[Path], plugin_roots: list[dict[str, Any]]) -> dict[str, Any]:
    skills: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[dict[str, str]] = []
    discovered_roots: list[str] = []
    seen_paths: set[Path] = set()

    for root in search_roots:
        for skill_path in sorted(root.rglob("SKILL.md")):
            resolved = skill_path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            record, error, note = _skill_record_from_file(resolved, plugin_roots)
            discovered_roots.append(str(root))
            if note:
                warnings.append(note)
            if error:
                errors.append(error)
            if record is not None:
                skills.append(record)

    return {
        "skills": skills,
        "warnings": warnings,
        "errors": errors,
        "discovered_roots": discovered_roots,
    }


def _skill_record_from_file(skill_path: Path, plugin_roots: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, str] | None, str | None]:
    text = skill_path.read_text(encoding="utf-8")
    parsed = _parse_frontmatter(text)
    owner = _skill_owner(skill_path, plugin_roots)
    source_kind = _source_kind(str(skill_path), None, owner)
    description = str(parsed.get("description") or "").strip()
    skill_name = str(parsed.get("name") or skill_path.parent.name).strip() or skill_path.parent.name
    short_description = _nested_string(parsed, "metadata", "short-description") or _nested_string(parsed, "metadata", "short_description")
    default_prompt = _nested_string(parsed, "metadata", "default-prompt") or _nested_string(parsed, "metadata", "default_prompt")
    icon_small = _nested_string(parsed, "metadata", "icon-small") or _nested_string(parsed, "metadata", "icon_small")
    icon_large = _nested_string(parsed, "metadata", "icon-large") or _nested_string(parsed, "metadata", "icon_large")
    brand_color = _nested_string(parsed, "metadata", "brand-color") or _nested_string(parsed, "metadata", "brand_color")
    manifest_status = "ok"
    error: dict[str, str] | None = None
    note: str | None = None

    if parsed.get("_malformed"):
        manifest_status = "malformed"
        error = {"path": str(skill_path), "message": str(parsed.get("_malformed") or "Malformed SKILL.md frontmatter.")}
        note = f"Malformed skill manifest discovered: {skill_path}"
    elif not description:
        error = {"path": str(skill_path), "message": "Skill manifest is missing frontmatter description."}

    record = {
        "skill_name": skill_name,
        "display_name": skill_name,
        "description": description or None,
        "description_status": "present" if description else "missing",
        "source_kind": source_kind,
        "owner_plugin_id": owner.get("plugin_id") if owner else None,
        "enablement": "unknown",
        "path": str(skill_path),
        "scope": None,
        "trigger_hints": _trigger_hints(
            description=description or None,
            short_description=short_description,
            default_prompt=default_prompt,
            skill_name=skill_name,
        ),
        "version_hint": owner.get("version_hint") if owner else None,
        "content_sha256": _sha256_text(text),
        "manifest_status": manifest_status,
        "dependency_tools": [],
        "icon_small": icon_small,
        "icon_large": icon_large,
        "brand_color": brand_color,
    }
    return record, error, note


def _skill_owner(skill_path: Path, plugin_roots: list[dict[str, Any]]) -> dict[str, Any] | None:
    resolved = skill_path.resolve()
    for item in plugin_roots:
        plugin_root = Path(str(item.get("plugin_root") or "")).resolve()
        skills_root = plugin_root / "skills"
        if resolved == skills_root or skills_root in resolved.parents:
            return item
    return None


def _source_kind(path: str | None, scope: str | None, owner: dict[str, Any] | None) -> str:
    if owner is not None:
        return "plugin"
    if str(scope or "").strip() == "repo":
        return "project_root"
    if str(scope or "").strip() == "system" and not path:
        return "remote_catalog"
    return "local_skill_root"


def _dependency_tools(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    tools = value.get("tools")
    if not isinstance(tools, list):
        return []
    names: list[str] = []
    for item in tools:
        if not isinstance(item, dict):
            continue
        text = str(item.get("name") or "").strip()
        if text:
            names.append(text)
    return sorted(set(names))


def _merge_skill_record(discovered_by_key: dict[str, dict[str, Any]], record: dict[str, Any]) -> None:
    key = str(record.get("path") or f"name::{record.get('skill_name') or ''}").strip()
    if not key:
        return
    existing = discovered_by_key.get(key)
    if existing is None:
        discovered_by_key[key] = record
        return
    merged = {**existing}
    for field in (
        "display_name",
        "description",
        "description_status",
        "source_kind",
        "owner_plugin_id",
        "enablement",
        "scope",
        "trigger_hints",
        "version_hint",
        "content_sha256",
        "manifest_status",
        "dependency_tools",
        "icon_small",
        "icon_large",
        "brand_color",
    ):
        value = record.get(field)
        if value is None:
            continue
        if isinstance(value, str) and value in {"", "unknown", "not_checked"}:
            continue
        if isinstance(value, list) and not value:
            continue
        merged[field] = value
    discovered_by_key[key] = merged


def _duplicate_skill_names(records: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    for item in records:
        name = str(item.get("skill_name") or "").strip()
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1
    return sorted(name for name, count in counts.items() if count > 1)


def _skill_notes(
    records: list[dict[str, Any]],
    duplicate_skill_names: list[str],
    malformed_skill_paths: list[str],
    missing_description_paths: list[str],
) -> list[str]:
    notes: list[str] = []
    if any(str(item.get("source_kind") or "") == "plugin" for item in records):
        notes.append("plugin_skills_detected")
    if any(str(item.get("source_kind") or "") == "local_skill_root" for item in records):
        notes.append("local_skill_roots_detected")
    if duplicate_skill_names:
        notes.append("duplicate_skill_names_detected")
    if malformed_skill_paths:
        notes.append("malformed_skill_manifests_detected")
    if missing_description_paths:
        notes.append("missing_skill_descriptions_detected")
    return notes


def _parse_frontmatter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines:
        return {"_malformed": "Empty SKILL.md file."}
    if lines[0].strip() != "---":
        return {"_malformed": "Missing YAML frontmatter start delimiter."}
    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        return {"_malformed": "Missing YAML frontmatter closing delimiter."}
    frontmatter_lines = lines[1:end_index]
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(0, root)]
    for raw_line in frontmatter_lines:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            return {"_malformed": f"Invalid frontmatter line: {line}"}
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        while len(stack) > 1 and indent < stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if not value:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent + 2, child))
            continue
        parent[key] = _yaml_scalar(value)
    return root


def _yaml_scalar(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _nested_string(payload: dict[str, Any], parent_key: str, child_key: str) -> str | None:
    parent = payload.get(parent_key)
    if not isinstance(parent, dict):
        return None
    text = str(parent.get(child_key) or "").strip()
    return text or None


def _trigger_hints(
    *,
    description: str | None,
    short_description: str | None,
    default_prompt: str | None,
    skill_name: str,
) -> list[str]:
    hints: list[str] = []
    for value in (short_description, default_prompt, _first_sentence(description), skill_name):
        text = str(value or "").strip()
        if text:
            hints.append(text[:200])
    return _dedupe_preserve_order(hints)


def _first_sentence(text: str | None) -> str | None:
    value = str(text or "").strip()
    if not value:
        return None
    for separator in (". ", "\n", "。", "; "):
        if separator in value:
            return value.split(separator, 1)[0].strip()
    return value


def _file_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _dedupe_errors(values: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for item in values:
        key = (str(item.get("path") or ""), str(item.get("message") or ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return sorted(result, key=lambda item: (str(item.get("path") or ""), str(item.get("message") or "")))


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
