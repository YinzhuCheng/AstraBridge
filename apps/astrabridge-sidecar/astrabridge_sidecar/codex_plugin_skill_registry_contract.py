from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


PLUGIN_SKILL_REGISTRY_SCHEMA_VERSION = "astrabridge-plugin-skill-registry-v1"
PLUGIN_SKILL_SOURCE_CATALOG_SCHEMA_VERSION = "astrabridge-plugin-skill-source-catalog-v1"
PLUGIN_SKILL_PROVENANCE_SCHEMA_VERSION = "astrabridge-plugin-skill-provenance-v1"
PLUGIN_SKILL_ICON_SCHEMA_VERSION = "astrabridge-plugin-skill-icon-v1"
PLUGIN_SKILL_WARNING_SCHEMA_VERSION = "astrabridge-plugin-skill-warning-v1"
PLUGIN_REGISTRY_RECORD_SCHEMA_VERSION = "astrabridge-plugin-registry-record-v1"
SKILL_REGISTRY_RECORD_SCHEMA_VERSION = "astrabridge-skill-registry-record-v1"

RegistrySourceKind = Literal["official", "curated", "local", "project_local", "manual"]
RegistryInstallStatus = Literal[
    "installed",
    "available",
    "update_available",
    "incompatible",
    "malformed",
    "unavailable",
    "unknown",
]
RegistryEnablementStatus = Literal["enabled", "disabled", "inherited", "blocked", "unknown"]
RegistryCompatibilityStatus = Literal["compatible", "warning", "incompatible", "unknown"]
RegistryIconProvenanceKind = Literal["official", "bundled_local", "generated_fallback", "none"]
RegistryWarningSeverity = Literal["info", "warning", "error"]

_SOURCE_KINDS = {"official", "curated", "local", "project_local", "manual"}
_INSTALL_STATUSES = {"installed", "available", "update_available", "incompatible", "malformed", "unavailable", "unknown"}
_ENABLEMENT_STATUSES = {"enabled", "disabled", "inherited", "blocked", "unknown"}
_COMPATIBILITY_STATUSES = {"compatible", "warning", "incompatible", "unknown"}
_ICON_PROVENANCE_KINDS = {"official", "bundled_local", "generated_fallback", "none"}
_WARNING_SEVERITIES = {"info", "warning", "error"}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _optional_text(value: Any) -> str | None:
    text = _clean_text(value)
    return text or None


def _clean_string_list(values: Any) -> list[str]:
    items = values if isinstance(values, (list, tuple)) else [values]
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(item)
        if not text or text in seen:
            continue
        out.append(text)
        seen.add(text)
    return out


def _validate_enum(name: str, value: str, allowed: set[str]) -> str:
    if value not in allowed:
        raise ValueError(f"{name} has unsupported value: {value or '<missing>'}.")
    return value


@dataclass(frozen=True)
class RegistrySourceCatalog:
    source_catalog_id: str
    kind: RegistrySourceKind
    display_name: str
    description: str | None = None
    source_url: str | None = None
    source_path: str | None = None
    catalog_path: str | None = None
    catalog_version: str | None = None
    checksum_algorithm: str | None = None
    checksum_value: str | None = None
    writable: bool = False
    schema_version: str = PLUGIN_SKILL_SOURCE_CATALOG_SCHEMA_VERSION
    notes: tuple[str, ...] = ()

    @classmethod
    def from_any(cls, payload: Any) -> "RegistrySourceCatalog":
        if isinstance(payload, RegistrySourceCatalog):
            return payload
        if not isinstance(payload, dict):
            raise TypeError("Registry source catalog payload must be a dict.")
        source_catalog_id = _clean_text(payload.get("source_catalog_id") or payload.get("catalog_id") or payload.get("id"))
        kind = _clean_text(payload.get("kind") or payload.get("source_kind"))
        if not source_catalog_id:
            raise ValueError("Registry source catalog requires source_catalog_id.")
        _validate_enum("Registry source catalog kind", kind, _SOURCE_KINDS)
        return cls(
            source_catalog_id=source_catalog_id,
            kind=kind,  # type: ignore[arg-type]
            display_name=_clean_text(payload.get("display_name") or payload.get("label") or source_catalog_id),
            description=_optional_text(payload.get("description")),
            source_url=_optional_text(payload.get("source_url")),
            source_path=_optional_text(payload.get("source_path")),
            catalog_path=_optional_text(payload.get("catalog_path")),
            catalog_version=_optional_text(payload.get("catalog_version") or payload.get("version")),
            checksum_algorithm=_optional_text(payload.get("checksum_algorithm")),
            checksum_value=_optional_text(payload.get("checksum_value")),
            writable=bool(payload.get("writable", False)),
            schema_version=_clean_text(payload.get("schema_version") or PLUGIN_SKILL_SOURCE_CATALOG_SCHEMA_VERSION),
            notes=tuple(_clean_string_list(payload.get("notes"))),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "source_catalog_id": self.source_catalog_id,
            "kind": self.kind,
            "display_name": self.display_name,
            "writable": self.writable,
        }
        if self.description:
            payload["description"] = self.description
        if self.source_url:
            payload["source_url"] = self.source_url
        if self.source_path:
            payload["source_path"] = self.source_path
        if self.catalog_path:
            payload["catalog_path"] = self.catalog_path
        if self.catalog_version:
            payload["catalog_version"] = self.catalog_version
        if self.checksum_algorithm:
            payload["checksum_algorithm"] = self.checksum_algorithm
        if self.checksum_value:
            payload["checksum_value"] = self.checksum_value
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


@dataclass(frozen=True)
class RegistryProvenance:
    source_path: str | None = None
    source_url: str | None = None
    manifest_path: str | None = None
    relative_root: str | None = None
    checksum_algorithm: str | None = None
    checksum_value: str | None = None
    last_verified_at: str | None = None
    schema_version: str = PLUGIN_SKILL_PROVENANCE_SCHEMA_VERSION
    notes: tuple[str, ...] = ()

    @classmethod
    def from_any(cls, payload: Any) -> "RegistryProvenance":
        if isinstance(payload, RegistryProvenance):
            return payload
        if payload in (None, "", False):
            return cls()
        if not isinstance(payload, dict):
            raise TypeError("Registry provenance payload must be a dict.")
        return cls(
            source_path=_optional_text(payload.get("source_path")),
            source_url=_optional_text(payload.get("source_url")),
            manifest_path=_optional_text(payload.get("manifest_path")),
            relative_root=_optional_text(payload.get("relative_root")),
            checksum_algorithm=_optional_text(payload.get("checksum_algorithm")),
            checksum_value=_optional_text(payload.get("checksum_value")),
            last_verified_at=_optional_text(payload.get("last_verified_at")),
            schema_version=_clean_text(payload.get("schema_version") or PLUGIN_SKILL_PROVENANCE_SCHEMA_VERSION),
            notes=tuple(_clean_string_list(payload.get("notes"))),
        )

    def is_empty(self) -> bool:
        return not any(
            (
                self.source_path,
                self.source_url,
                self.manifest_path,
                self.relative_root,
                self.checksum_algorithm,
                self.checksum_value,
                self.last_verified_at,
                self.notes,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {"schema_version": self.schema_version}
        if self.source_path:
            payload["source_path"] = self.source_path
        if self.source_url:
            payload["source_url"] = self.source_url
        if self.manifest_path:
            payload["manifest_path"] = self.manifest_path
        if self.relative_root:
            payload["relative_root"] = self.relative_root
        if self.checksum_algorithm:
            payload["checksum_algorithm"] = self.checksum_algorithm
        if self.checksum_value:
            payload["checksum_value"] = self.checksum_value
        if self.last_verified_at:
            payload["last_verified_at"] = self.last_verified_at
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


@dataclass(frozen=True)
class RegistryIconMetadata:
    provenance_kind: RegistryIconProvenanceKind = "none"
    label: str | None = None
    asset_path: str | None = None
    asset_url: str | None = None
    mime_type: str | None = None
    checksum_algorithm: str | None = None
    checksum_value: str | None = None
    validated: bool = False
    schema_version: str = PLUGIN_SKILL_ICON_SCHEMA_VERSION
    notes: tuple[str, ...] = ()

    @classmethod
    def from_any(cls, payload: Any) -> "RegistryIconMetadata":
        if isinstance(payload, RegistryIconMetadata):
            return payload
        if payload in (None, "", False):
            return cls()
        if not isinstance(payload, dict):
            raise TypeError("Registry icon metadata payload must be a dict.")
        provenance_kind = _clean_text(payload.get("provenance_kind") or payload.get("kind") or "none")
        _validate_enum("Registry icon provenance_kind", provenance_kind, _ICON_PROVENANCE_KINDS)
        return cls(
            provenance_kind=provenance_kind,  # type: ignore[arg-type]
            label=_optional_text(payload.get("label")),
            asset_path=_optional_text(payload.get("asset_path")),
            asset_url=_optional_text(payload.get("asset_url")),
            mime_type=_optional_text(payload.get("mime_type")),
            checksum_algorithm=_optional_text(payload.get("checksum_algorithm")),
            checksum_value=_optional_text(payload.get("checksum_value")),
            validated=bool(payload.get("validated", False)),
            schema_version=_clean_text(payload.get("schema_version") or PLUGIN_SKILL_ICON_SCHEMA_VERSION),
            notes=tuple(_clean_string_list(payload.get("notes"))),
        )

    def is_empty(self) -> bool:
        return (
            self.provenance_kind == "none"
            and not any(
                (
                    self.label,
                    self.asset_path,
                    self.asset_url,
                    self.mime_type,
                    self.checksum_algorithm,
                    self.checksum_value,
                    self.notes,
                )
            )
            and not self.validated
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "provenance_kind": self.provenance_kind,
            "validated": self.validated,
        }
        if self.label:
            payload["label"] = self.label
        if self.asset_path:
            payload["asset_path"] = self.asset_path
        if self.asset_url:
            payload["asset_url"] = self.asset_url
        if self.mime_type:
            payload["mime_type"] = self.mime_type
        if self.checksum_algorithm:
            payload["checksum_algorithm"] = self.checksum_algorithm
        if self.checksum_value:
            payload["checksum_value"] = self.checksum_value
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


@dataclass(frozen=True)
class RegistryCompatibilityWarning:
    code: str
    severity: RegistryWarningSeverity
    message: str
    field: str | None = None
    documentation_url: str | None = None
    schema_version: str = PLUGIN_SKILL_WARNING_SCHEMA_VERSION

    @classmethod
    def from_any(cls, payload: Any) -> "RegistryCompatibilityWarning":
        if isinstance(payload, RegistryCompatibilityWarning):
            return payload
        if not isinstance(payload, dict):
            raise TypeError("Registry compatibility warning payload must be a dict.")
        code = _clean_text(payload.get("code"))
        message = _clean_text(payload.get("message"))
        severity = _clean_text(payload.get("severity") or "warning")
        if not code:
            raise ValueError("Registry compatibility warning requires code.")
        if not message:
            raise ValueError(f"Registry compatibility warning {code} requires message.")
        _validate_enum("Registry warning severity", severity, _WARNING_SEVERITIES)
        return cls(
            code=code,
            severity=severity,  # type: ignore[arg-type]
            message=message,
            field=_optional_text(payload.get("field")),
            documentation_url=_optional_text(payload.get("documentation_url")),
            schema_version=_clean_text(payload.get("schema_version") or PLUGIN_SKILL_WARNING_SCHEMA_VERSION),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }
        if self.field:
            payload["field"] = self.field
        if self.documentation_url:
            payload["documentation_url"] = self.documentation_url
        return payload


@dataclass(frozen=True)
class PluginRegistryRecord:
    record_id: str
    plugin_id: str
    source_catalog_id: str
    display_name: str
    install_status: RegistryInstallStatus
    enablement_status: RegistryEnablementStatus
    compatibility_status: RegistryCompatibilityStatus
    version: str | None = None
    installed_version: str | None = None
    available_version: str | None = None
    description: str | None = None
    remote_plugin_id: str | None = None
    install_root: str | None = None
    keywords: tuple[str, ...] = ()
    declared_app_ids: tuple[str, ...] = ()
    declared_hook_keys: tuple[str, ...] = ()
    declared_mcp_servers: tuple[str, ...] = ()
    permission_hints: tuple[str, ...] = ()
    provenance: RegistryProvenance = RegistryProvenance()
    icon: RegistryIconMetadata = RegistryIconMetadata()
    compatibility_warnings: tuple[RegistryCompatibilityWarning, ...] = ()
    schema_version: str = PLUGIN_REGISTRY_RECORD_SCHEMA_VERSION
    notes: tuple[str, ...] = ()

    @classmethod
    def from_any(cls, payload: Any) -> "PluginRegistryRecord":
        if isinstance(payload, PluginRegistryRecord):
            return payload
        if not isinstance(payload, dict):
            raise TypeError("Plugin registry record payload must be a dict.")
        record_id = _clean_text(payload.get("record_id") or payload.get("id"))
        plugin_id = _clean_text(payload.get("plugin_id") or payload.get("plugin_name") or payload.get("name"))
        source_catalog_id = _clean_text(payload.get("source_catalog_id"))
        if not record_id:
            raise ValueError("Plugin registry record requires record_id.")
        if not plugin_id:
            raise ValueError("Plugin registry record requires plugin_id.")
        if not source_catalog_id:
            raise ValueError(f"Plugin registry record {record_id} requires source_catalog_id.")
        install_status = _clean_text(payload.get("install_status") or payload.get("availability") or "unknown")
        enablement_status = _clean_text(payload.get("enablement_status") or payload.get("enablement") or "unknown")
        if enablement_status == "unknown" and "enabled" in payload:
            enablement_status = "enabled" if bool(payload.get("enabled")) else "disabled"
        compatibility_status = _clean_text(payload.get("compatibility_status") or "unknown")
        _validate_enum("Plugin install_status", install_status, _INSTALL_STATUSES)
        _validate_enum("Plugin enablement_status", enablement_status, _ENABLEMENT_STATUSES)
        _validate_enum("Plugin compatibility_status", compatibility_status, _COMPATIBILITY_STATUSES)
        version = _optional_text(payload.get("version"))
        installed_version = _optional_text(payload.get("installed_version")) or (version if install_status == "installed" else None)
        available_version = _optional_text(payload.get("available_version")) or (version if install_status in {"available", "update_available"} else None)
        if install_status == "update_available" and not available_version:
            raise ValueError(f"Plugin registry record {record_id} requires available_version for update_available status.")
        return cls(
            record_id=record_id,
            plugin_id=plugin_id,
            source_catalog_id=source_catalog_id,
            display_name=_clean_text(payload.get("display_name") or payload.get("label") or plugin_id),
            install_status=install_status,  # type: ignore[arg-type]
            enablement_status=enablement_status,  # type: ignore[arg-type]
            compatibility_status=compatibility_status,  # type: ignore[arg-type]
            version=version or installed_version or available_version,
            installed_version=installed_version,
            available_version=available_version,
            description=_optional_text(payload.get("description")),
            remote_plugin_id=_optional_text(payload.get("remote_plugin_id")),
            install_root=_optional_text(payload.get("install_root")),
            keywords=tuple(_clean_string_list(payload.get("keywords"))),
            declared_app_ids=tuple(_clean_string_list(payload.get("declared_app_ids") or payload.get("apps"))),
            declared_hook_keys=tuple(_clean_string_list(payload.get("declared_hook_keys") or payload.get("hooks"))),
            declared_mcp_servers=tuple(_clean_string_list(payload.get("declared_mcp_servers") or payload.get("mcp_servers"))),
            permission_hints=tuple(_clean_string_list(payload.get("permission_hints"))),
            provenance=RegistryProvenance.from_any(payload.get("provenance")),
            icon=RegistryIconMetadata.from_any(payload.get("icon")),
            compatibility_warnings=tuple(
                RegistryCompatibilityWarning.from_any(item) for item in list(payload.get("compatibility_warnings") or payload.get("warnings") or [])
            ),
            schema_version=_clean_text(payload.get("schema_version") or PLUGIN_REGISTRY_RECORD_SCHEMA_VERSION),
            notes=tuple(_clean_string_list(payload.get("notes"))),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "record_id": self.record_id,
            "plugin_id": self.plugin_id,
            "source_catalog_id": self.source_catalog_id,
            "display_name": self.display_name,
            "install_status": self.install_status,
            "enablement_status": self.enablement_status,
            "compatibility_status": self.compatibility_status,
        }
        if self.version:
            payload["version"] = self.version
        if self.installed_version:
            payload["installed_version"] = self.installed_version
        if self.available_version:
            payload["available_version"] = self.available_version
        if self.description:
            payload["description"] = self.description
        if self.remote_plugin_id:
            payload["remote_plugin_id"] = self.remote_plugin_id
        if self.install_root:
            payload["install_root"] = self.install_root
        if self.keywords:
            payload["keywords"] = list(self.keywords)
        if self.declared_app_ids:
            payload["declared_app_ids"] = list(self.declared_app_ids)
        if self.declared_hook_keys:
            payload["declared_hook_keys"] = list(self.declared_hook_keys)
        if self.declared_mcp_servers:
            payload["declared_mcp_servers"] = list(self.declared_mcp_servers)
        if self.permission_hints:
            payload["permission_hints"] = list(self.permission_hints)
        if not self.provenance.is_empty():
            payload["provenance"] = self.provenance.to_dict()
        if not self.icon.is_empty():
            payload["icon"] = self.icon.to_dict()
        if self.compatibility_warnings:
            payload["compatibility_warnings"] = [warning.to_dict() for warning in self.compatibility_warnings]
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


@dataclass(frozen=True)
class SkillRegistryRecord:
    record_id: str
    skill_name: str
    source_catalog_id: str
    display_name: str
    install_status: RegistryInstallStatus
    enablement_status: RegistryEnablementStatus
    compatibility_status: RegistryCompatibilityStatus
    owner_plugin_id: str | None = None
    description: str | None = None
    short_description: str | None = None
    owning_plugin_version: str | None = None
    trigger_hints: tuple[str, ...] = ()
    permission_hints: tuple[str, ...] = ()
    provenance: RegistryProvenance = RegistryProvenance()
    icon: RegistryIconMetadata = RegistryIconMetadata()
    compatibility_warnings: tuple[RegistryCompatibilityWarning, ...] = ()
    schema_version: str = SKILL_REGISTRY_RECORD_SCHEMA_VERSION
    notes: tuple[str, ...] = ()

    @classmethod
    def from_any(cls, payload: Any) -> "SkillRegistryRecord":
        if isinstance(payload, SkillRegistryRecord):
            return payload
        if not isinstance(payload, dict):
            raise TypeError("Skill registry record payload must be a dict.")
        record_id = _clean_text(payload.get("record_id") or payload.get("id"))
        skill_name = _clean_text(payload.get("skill_name") or payload.get("name"))
        source_catalog_id = _clean_text(payload.get("source_catalog_id"))
        if not record_id:
            raise ValueError("Skill registry record requires record_id.")
        if not skill_name:
            raise ValueError("Skill registry record requires skill_name.")
        if not source_catalog_id:
            raise ValueError(f"Skill registry record {record_id} requires source_catalog_id.")
        install_status = _clean_text(payload.get("install_status") or payload.get("availability") or "unknown")
        enablement_status = _clean_text(payload.get("enablement_status") or payload.get("enablement") or "unknown")
        if enablement_status == "unknown" and "enabled" in payload:
            enablement_status = "enabled" if bool(payload.get("enabled")) else "disabled"
        compatibility_status = _clean_text(payload.get("compatibility_status") or "unknown")
        _validate_enum("Skill install_status", install_status, _INSTALL_STATUSES)
        _validate_enum("Skill enablement_status", enablement_status, _ENABLEMENT_STATUSES)
        _validate_enum("Skill compatibility_status", compatibility_status, _COMPATIBILITY_STATUSES)
        return cls(
            record_id=record_id,
            skill_name=skill_name,
            source_catalog_id=source_catalog_id,
            display_name=_clean_text(payload.get("display_name") or payload.get("label") or skill_name),
            install_status=install_status,  # type: ignore[arg-type]
            enablement_status=enablement_status,  # type: ignore[arg-type]
            compatibility_status=compatibility_status,  # type: ignore[arg-type]
            owner_plugin_id=_optional_text(payload.get("owner_plugin_id")),
            description=_optional_text(payload.get("description")),
            short_description=_optional_text(payload.get("short_description")),
            owning_plugin_version=_optional_text(payload.get("owning_plugin_version")),
            trigger_hints=tuple(_clean_string_list(payload.get("trigger_hints"))),
            permission_hints=tuple(_clean_string_list(payload.get("permission_hints"))),
            provenance=RegistryProvenance.from_any(payload.get("provenance")),
            icon=RegistryIconMetadata.from_any(payload.get("icon")),
            compatibility_warnings=tuple(
                RegistryCompatibilityWarning.from_any(item) for item in list(payload.get("compatibility_warnings") or payload.get("warnings") or [])
            ),
            schema_version=_clean_text(payload.get("schema_version") or SKILL_REGISTRY_RECORD_SCHEMA_VERSION),
            notes=tuple(_clean_string_list(payload.get("notes"))),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "record_id": self.record_id,
            "skill_name": self.skill_name,
            "source_catalog_id": self.source_catalog_id,
            "display_name": self.display_name,
            "install_status": self.install_status,
            "enablement_status": self.enablement_status,
            "compatibility_status": self.compatibility_status,
        }
        if self.owner_plugin_id:
            payload["owner_plugin_id"] = self.owner_plugin_id
        if self.description:
            payload["description"] = self.description
        if self.short_description:
            payload["short_description"] = self.short_description
        if self.owning_plugin_version:
            payload["owning_plugin_version"] = self.owning_plugin_version
        if self.trigger_hints:
            payload["trigger_hints"] = list(self.trigger_hints)
        if self.permission_hints:
            payload["permission_hints"] = list(self.permission_hints)
        if not self.provenance.is_empty():
            payload["provenance"] = self.provenance.to_dict()
        if not self.icon.is_empty():
            payload["icon"] = self.icon.to_dict()
        if self.compatibility_warnings:
            payload["compatibility_warnings"] = [warning.to_dict() for warning in self.compatibility_warnings]
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


@dataclass(frozen=True)
class PluginSkillRegistrySnapshot:
    generated_at: str
    source_catalogs: tuple[RegistrySourceCatalog, ...]
    plugins: tuple[PluginRegistryRecord, ...]
    skills: tuple[SkillRegistryRecord, ...]
    schema_version: str = PLUGIN_SKILL_REGISTRY_SCHEMA_VERSION
    notes: tuple[str, ...] = ()

    @classmethod
    def from_any(cls, payload: Any) -> "PluginSkillRegistrySnapshot":
        if isinstance(payload, PluginSkillRegistrySnapshot):
            return payload
        if not isinstance(payload, dict):
            raise TypeError("Plugin skill registry snapshot payload must be a dict.")
        source_catalogs = tuple(RegistrySourceCatalog.from_any(item) for item in list(payload.get("source_catalogs") or payload.get("catalogs") or []))
        plugins = tuple(PluginRegistryRecord.from_any(item) for item in list(payload.get("plugins") or payload.get("plugin_records") or []))
        skills = tuple(SkillRegistryRecord.from_any(item) for item in list(payload.get("skills") or payload.get("skill_records") or []))
        catalog_index = source_catalog_index(source_catalogs)
        for record in [*plugins, *skills]:
            if record.source_catalog_id not in catalog_index:
                raise ValueError(
                    f"Registry record {record.record_id} references missing source_catalog_id {record.source_catalog_id}."
                )
        plugin_record_index(plugins)
        skill_record_index(skills)
        return cls(
            generated_at=_clean_text(payload.get("generated_at")),
            source_catalogs=source_catalogs,
            plugins=plugins,
            skills=skills,
            schema_version=_clean_text(payload.get("schema_version") or PLUGIN_SKILL_REGISTRY_SCHEMA_VERSION),
            notes=tuple(_clean_string_list(payload.get("notes"))),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "source_catalogs": [catalog.to_dict() for catalog in self.source_catalogs],
            "plugins": [record.to_dict() for record in self.plugins],
            "skills": [record.to_dict() for record in self.skills],
        }
        if self.notes:
            payload["notes"] = list(self.notes)
        return payload


def source_catalog_index(catalogs: list[RegistrySourceCatalog] | tuple[RegistrySourceCatalog, ...]) -> dict[str, RegistrySourceCatalog]:
    index: dict[str, RegistrySourceCatalog] = {}
    for catalog in catalogs:
        if catalog.source_catalog_id in index:
            raise ValueError(f"Duplicate source_catalog_id in plugin/skill registry: {catalog.source_catalog_id}.")
        index[catalog.source_catalog_id] = catalog
    return index


def plugin_record_index(records: list[PluginRegistryRecord] | tuple[PluginRegistryRecord, ...]) -> dict[str, PluginRegistryRecord]:
    index: dict[str, PluginRegistryRecord] = {}
    for record in records:
        if record.record_id in index:
            raise ValueError(f"Duplicate plugin record_id in plugin/skill registry: {record.record_id}.")
        index[record.record_id] = record
    return index


def skill_record_index(records: list[SkillRegistryRecord] | tuple[SkillRegistryRecord, ...]) -> dict[str, SkillRegistryRecord]:
    index: dict[str, SkillRegistryRecord] = {}
    for record in records:
        if record.record_id in index:
            raise ValueError(f"Duplicate skill record_id in plugin/skill registry: {record.record_id}.")
        index[record.record_id] = record
    return index


def normalize_source_catalog(payload: Any) -> RegistrySourceCatalog:
    return RegistrySourceCatalog.from_any(payload)


def normalize_provenance(payload: Any) -> RegistryProvenance:
    return RegistryProvenance.from_any(payload)


def normalize_icon_metadata(payload: Any) -> RegistryIconMetadata:
    return RegistryIconMetadata.from_any(payload)


def normalize_compatibility_warning(payload: Any) -> RegistryCompatibilityWarning:
    return RegistryCompatibilityWarning.from_any(payload)


def normalize_plugin_registry_record(payload: Any) -> PluginRegistryRecord:
    return PluginRegistryRecord.from_any(payload)


def normalize_skill_registry_record(payload: Any) -> SkillRegistryRecord:
    return SkillRegistryRecord.from_any(payload)


def normalize_plugin_skill_registry_snapshot(payload: Any) -> PluginSkillRegistrySnapshot:
    return PluginSkillRegistrySnapshot.from_any(payload)
