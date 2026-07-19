from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SIDECAR_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar import release_identity as release_identity_module  # noqa: E402
from astrabridge_sidecar.release_identity import (  # noqa: E402
    collect_release_bindings,
    compare_staging_runs,
    desktop_update_status,
    expected_formal_sidecar_bundle,
    expected_tauri_updater_config,
    evaluate_updater_contract,
    evaluate_release_bindings,
    load_release_identity,
    run_windows_update_rehearsal,
    stage_release_workspace,
)


class ReleaseIdentityTests(unittest.TestCase):
    def test_current_repo_release_identity_bindings_pass(self) -> None:
        identity = load_release_identity()
        bindings = collect_release_bindings(REPO_ROOT, identity)
        result = evaluate_release_bindings(bindings)

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["mismatch_count"], 0)
        self.assertGreaterEqual(result["binding_count"], 10)

    def test_evaluate_release_bindings_flags_drift(self) -> None:
        result = evaluate_release_bindings(
            [
                {"binding_id": "desktop.package.json.version", "path": "package.json", "expected": "0.1.0", "actual": "0.1.0"},
                {"binding_id": "sidecar.pyproject.version", "path": "pyproject.toml", "expected": "0.1.0", "actual": "0.1.1"},
            ]
        )

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["mismatch_count"], 1)
        self.assertEqual(result["mismatches"][0]["binding_id"], "sidecar.pyproject.version")

    def test_evaluate_updater_contract_requires_structured_channels_and_kill_switch(self) -> None:
        identity = {
            "updater": {
                "manifest_version": "astrabridge-updater-release-v1",
                "create_updater_artifacts": True,
                "pubkey": "untrusted comment: AstraBridge updater public key\nRWQk7T1LE8n6v2JixL5E0lCdj8m5wXyS4z6QyQwQ4lJ3Y7mQzW1S7V8n",
                "windows": {
                    "install_mode": "passive",
                },
                "default_channel": "stable",
                "kill_switch": {
                    "manifest_path": "release/updater/kill-switch.json",
                    "default_mode": "allow",
                    "allow_disable_updates": True,
                },
                "channels": [
                    {
                        "channel": "stable",
                        "manifest_path": "release/updater/stable.json",
                        "endpoint": "https://updates.astrabridge.app/stable/{{target}}/{{arch}}/{{current_version}}",
                        "rollout": "general_availability",
                    },
                    {
                        "channel": "beta",
                        "manifest_path": "release/updater/beta.json",
                        "endpoint": "https://updates.astrabridge.app/beta/{{target}}/{{arch}}/{{current_version}}",
                        "rollout": "release_candidate",
                    },
                    {
                        "channel": "canary",
                        "manifest_path": "release/updater/canary.json",
                        "endpoint": "https://updates.astrabridge.app/canary/{{target}}/{{arch}}/{{current_version}}",
                        "rollout": "internal_preview",
                    },
                ],
            }
        }

        result = evaluate_updater_contract(identity)

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["default_channel"], "stable")
        self.assertEqual(result["channel_count"], 3)
        self.assertFalse(result["errors"])
        self.assertEqual(result["tauri_updater"]["endpoints"], ["https://updates.astrabridge.app/stable/{{target}}/{{arch}}/{{current_version}}"])
        self.assertEqual(result["tauri_updater"]["windows_install_mode"], "passive")

    def test_evaluate_updater_contract_fails_open_or_incomplete_channel_contract(self) -> None:
        identity = {
            "updater": {
                "manifest_version": "astrabridge-updater-release-v1",
                "create_updater_artifacts": False,
                "pubkey": "",
                "windows": {
                    "install_mode": "passive",
                },
                "default_channel": "stable",
                "kill_switch": {
                    "manifest_path": "release/updater/bad-switch.json",
                    "default_mode": "",
                    "allow_disable_updates": "yes",
                },
                "channels": [
                    {
                        "channel": "stable",
                        "manifest_path": "release/updater/stable.json",
                        "endpoint": "http://updates.astrabridge.app/stable/{{target}}",
                        "rollout": "",
                    },
                ],
            }
        }

        result = evaluate_updater_contract(identity)

        self.assertEqual(result["status"], "fail")
        self.assertGreaterEqual(len(result["errors"]), 4)
        self.assertTrue(any("stable/beta/canary" in error for error in result["errors"]))
        self.assertTrue(any("pubkey" in error for error in result["errors"]))
        self.assertTrue(any("create_updater_artifacts" in error for error in result["errors"]))

    def test_expected_tauri_updater_config_uses_default_channel_endpoint(self) -> None:
        config = expected_tauri_updater_config(
            {
                "updater": {
                    "create_updater_artifacts": True,
                    "pubkey": "untrusted comment: AstraBridge updater public key\nRWQtest",
                    "windows": {"install_mode": "passive"},
                    "default_channel": "beta",
                    "channels": [
                        {
                            "channel": "stable",
                            "manifest_path": "release/updater/stable.json",
                            "endpoint": "https://updates.astrabridge.app/stable/{{target}}/{{arch}}/{{current_version}}",
                            "rollout": "general_availability",
                        },
                        {
                            "channel": "beta",
                            "manifest_path": "release/updater/beta.json",
                            "endpoint": "https://updates.astrabridge.app/beta/{{target}}/{{arch}}/{{current_version}}",
                            "rollout": "release_candidate",
                        },
                    ],
                }
            }
        )

        self.assertEqual(config["create_updater_artifacts"], True)
        self.assertEqual(config["endpoints"], ["https://updates.astrabridge.app/beta/{{target}}/{{arch}}/{{current_version}}"])
        self.assertEqual(config["windows_install_mode"], "passive")

    def test_expected_formal_sidecar_bundle_reads_declared_contract(self) -> None:
        config = expected_formal_sidecar_bundle(
            {
                "sidecar": {
                    "formal_bundle": {
                        "schema_version": "astrabridge-sidecar-formal-bundle-v1",
                        "resource_path": "release/desktop-sidecar/windows-x64/astrabridge-sidecar",
                        "tauri_resource_source": "../../../release/desktop-sidecar/windows-x64/astrabridge-sidecar",
                        "resource_destination": "astrabridge-sidecar",
                        "launcher_path": "python-runtime/python.exe",
                        "launch_arguments": ["-m", "astrabridge_sidecar.server"],
                        "pythonpath_entry": ".",
                        "package_root": "astrabridge_sidecar",
                        "skills_root": "skills",
                        "origin": "app_managed",
                        "launcher_mode": "desktop-app-managed",
                        "allow_source_fallback_in_formal_package": False,
                    }
                }
            }
        )

        self.assertEqual(config["launcher_path"], "python-runtime/python.exe")
        self.assertEqual(config["launch_arguments"], ["-m", "astrabridge_sidecar.server"])
        self.assertEqual(config["origin"], "app_managed")
        self.assertFalse(config["allow_source_fallback_in_formal_package"])

    def test_stage_workspace_generates_formal_sidecar_bundle_without_editable_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            python_home = root / "python-home"
            (python_home / "Lib").mkdir(parents=True, exist_ok=True)
            (python_home / "python.exe").write_bytes(b"python-runtime")
            (python_home / "python311.dll").write_bytes(b"dll")
            (python_home / "Lib" / "os.py").write_text("VALUE = 1\n", encoding="utf-8")

            source_venv = root / "apps" / "astrabridge-sidecar" / ".venv"
            site_packages = source_venv / "Lib" / "site-packages"
            dist_info = site_packages / "astrabridge_sidecar-0.1.0.dist-info"
            dist_info.mkdir(parents=True, exist_ok=True)
            (source_venv / "pyvenv.cfg").write_text(
                f"home = {python_home}\nversion_info = 3.11.15\n",
                encoding="utf-8",
            )
            (site_packages / "__editable__.astrabridge_sidecar-0.1.0.pth").write_text(
                "D:/AstraBridge/apps/astrabridge-sidecar\n",
                encoding="utf-8",
            )
            (dist_info / "direct_url.json").write_text(
                "{\"url\":\"file:///D:/AstraBridge/apps/astrabridge-sidecar\"}\n",
                encoding="utf-8",
            )
            (dist_info / "uv_build.json").write_text("{\"source\":\"local\"}\n", encoding="utf-8")
            (site_packages / "requests").mkdir(parents=True, exist_ok=True)
            (site_packages / "requests" / "__init__.py").write_text("VERSION = 'ok'\n", encoding="utf-8")

            package_root = root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar"
            skills_root = root / "apps" / "astrabridge-sidecar" / "skills"
            package_root.mkdir(parents=True, exist_ok=True)
            skills_root.mkdir(parents=True, exist_ok=True)
            (package_root / "__init__.py").write_text("__version__ = '0.1.0'\n", encoding="utf-8")
            (package_root / "server.py").write_text("def main():\n    return 0\n", encoding="utf-8")
            (skills_root / "README.md").write_text("skill\n", encoding="utf-8")

            identity = {
                "schema_version": "astrabridge-release-identity-v1",
                "product_name": "AstraBridge",
                "package_identifier": "app.astrabridge.desktop",
                "release_version": "0.1.0",
                "sidecar": {
                    "package_name": "astrabridge-sidecar",
                    "package_version": "0.1.0",
                    "python_entry": "astrabridge_sidecar.server:main",
                    "formal_bundle": {
                        "schema_version": "astrabridge-sidecar-formal-bundle-v1",
                        "resource_path": "release/desktop-sidecar/windows-x64/astrabridge-sidecar",
                        "tauri_resource_source": "../../../release/desktop-sidecar/windows-x64/astrabridge-sidecar",
                        "resource_destination": "astrabridge-sidecar",
                        "launcher_path": "python-runtime/python.exe",
                        "launch_arguments": ["-m", "astrabridge_sidecar.server"],
                        "pythonpath_entry": ".",
                        "package_root": "astrabridge_sidecar",
                        "skills_root": "skills",
                        "origin": "app_managed",
                        "launcher_mode": "desktop-app-managed",
                        "allow_source_fallback_in_formal_package": False,
                    },
                },
                "protocol": {"schema_version": "astrabridge-protocol-v1"},
                "updater": {
                    "manifest_version": "astrabridge-updater-release-v1",
                    "create_updater_artifacts": True,
                    "pubkey": "untrusted comment: AstraBridge updater public key\nRWQtest",
                    "windows": {"install_mode": "passive"},
                    "default_channel": "stable",
                    "kill_switch": {
                        "manifest_path": "release/updater/kill-switch.json",
                        "default_mode": "allow",
                        "allow_disable_updates": True,
                    },
                    "channels": [
                        {
                            "channel": "stable",
                            "manifest_path": "release/updater/stable.json",
                            "endpoint": "https://updates.astrabridge.app/stable/{{target}}/{{arch}}/{{current_version}}",
                            "rollout": "general_availability",
                        }
                    ],
                },
                "staging": {"forbidden_paths": ["tests", ".venv", "PRIVATE", "__pycache__"]},
            }
            (root / "release").mkdir(parents=True, exist_ok=True)
            (root / "release" / "astrabridge-release-identity.json").write_text(
                json.dumps(identity, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            rules = (
                {"kind": "file", "path": "release/astrabridge-release-identity.json"},
                {"kind": "tree", "path": "apps/astrabridge-sidecar/astrabridge_sidecar"},
            )

            with patch.object(release_identity_module, "_STAGING_INCLUDE_RULES", rules), patch.object(
                release_identity_module,
                "_git_output",
                return_value="",
            ):
                stage = stage_release_workspace(
                    repo_root=root,
                    output_root=root / "artifacts",
                    stage_name="stage-a",
                    identity=identity,
                )

            self.assertEqual(stage["status"], "pass")
            bundle = dict(stage["sidecar_bundle"])
            self.assertEqual(bundle["status"], "pass")
            bundle_root = Path(bundle["bundle_root"])
            self.assertTrue((bundle_root / "python-runtime" / "python.exe").exists())
            self.assertTrue((bundle_root / "astrabridge_sidecar" / "server.py").exists())
            self.assertFalse((bundle_root / "python-runtime" / "Lib" / "site-packages" / "__editable__.astrabridge_sidecar-0.1.0.pth").exists())
            self.assertFalse(
                (
                    bundle_root
                    / "python-runtime"
                    / "Lib"
                    / "site-packages"
                    / "astrabridge_sidecar-0.1.0.dist-info"
                    / "direct_url.json"
                ).exists()
            )

    def test_stage_workspace_is_deterministic_and_excludes_forbidden_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            (root / "release").mkdir(parents=True, exist_ok=True)
            (root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar").mkdir(parents=True, exist_ok=True)
            (root / "apps" / "astrabridge-sidecar" / "tests").mkdir(parents=True, exist_ok=True)
            (root / "apps" / "astrabridge-sidecar" / ".venv").mkdir(parents=True, exist_ok=True)
            identity = {
                "schema_version": "astrabridge-release-identity-v1",
                "product_name": "AstraBridge",
                "package_identifier": "app.astrabridge.desktop",
                "release_version": "0.1.0",
                "protocol": {"schema_version": "astrabridge-protocol-v1"},
                "updater": {
                    "manifest_version": "astrabridge-updater-release-v1",
                    "create_updater_artifacts": True,
                    "pubkey": "untrusted comment: AstraBridge updater public key\nRWQk7T1LE8n6v2JixL5E0lCdj8m5wXyS4z6QyQwQ4lJ3Y7mQzW1S7V8n",
                    "windows": {
                        "install_mode": "passive",
                    },
                    "default_channel": "stable",
                    "kill_switch": {
                        "manifest_path": "release/updater/kill-switch.json",
                        "default_mode": "allow",
                        "allow_disable_updates": True,
                    },
                    "channels": [
                        {
                            "channel": "stable",
                            "manifest_path": "release/updater/stable.json",
                            "endpoint": "https://updates.astrabridge.app/stable/{{target}}/{{arch}}/{{current_version}}",
                            "rollout": "general_availability",
                        }
                    ],
                },
                "staging": {"forbidden_paths": ["tests", ".venv", "PRIVATE", "__pycache__"]},
            }
            (root / "release" / "astrabridge-release-identity.json").write_text(
                json.dumps(identity, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar" / "__init__.py").write_text(
                "__version__ = '0.1.0'\n",
                encoding="utf-8",
            )
            (root / "apps" / "astrabridge-sidecar" / "astrabridge_sidecar" / "runtime.py").write_text(
                "VALUE = 1\n",
                encoding="utf-8",
            )
            (root / "apps" / "astrabridge-sidecar" / "tests" / "test_runtime.py").write_text(
                "VALUE = 'should stay out'\n",
                encoding="utf-8",
            )
            (root / "apps" / "astrabridge-sidecar" / ".venv" / "ignored.txt").write_text(
                "ignore\n",
                encoding="utf-8",
            )
            rules = (
                {"kind": "file", "path": "release/astrabridge-release-identity.json"},
                {"kind": "tree", "path": "apps/astrabridge-sidecar/astrabridge_sidecar"},
                {"kind": "tree", "path": "apps/astrabridge-sidecar/tests"},
                {"kind": "tree", "path": "apps/astrabridge-sidecar/.venv"},
            )

            with patch.object(release_identity_module, "_STAGING_INCLUDE_RULES", rules), patch.object(
                release_identity_module,
                "_git_output",
                return_value="",
            ):
                first = stage_release_workspace(
                    repo_root=root,
                    output_root=root / "artifacts",
                    stage_name="stage-a",
                    identity=identity,
                )
                second = stage_release_workspace(
                    repo_root=root,
                    output_root=root / "artifacts",
                    stage_name="stage-b",
                    identity=identity,
                )

            self.assertEqual(first["status"], "pass")
            copied_paths = [item["path"] for item in first["copied_files"]]
            self.assertIn("apps/astrabridge-sidecar/astrabridge_sidecar/runtime.py", copied_paths)
            self.assertNotIn("apps/astrabridge-sidecar/tests/test_runtime.py", copied_paths)
            self.assertFalse(first["forbidden_path_violations"])
            normalized_manifest_paths = [str(path).replace("\\", "/") for path in first["updater_manifests"]]
            self.assertTrue(any(path.endswith("release/updater/stable.json") for path in normalized_manifest_paths))
            self.assertTrue(any(path.endswith("release/updater/kill-switch.json") for path in normalized_manifest_paths))

            comparison = compare_staging_runs(first, second)
            self.assertEqual(comparison["status"], "pass")
            self.assertEqual(comparison["differing_paths"], [])

    def test_desktop_update_status_uses_project_channel_and_latest_rehearsal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            bundle_root = root / "release" / "desktop-sidecar" / "windows-x64" / "astrabridge-sidecar"
            (bundle_root / "python-runtime").mkdir(parents=True, exist_ok=True)
            (bundle_root / "astrabridge_sidecar").mkdir(parents=True, exist_ok=True)
            (bundle_root / "skills").mkdir(parents=True, exist_ok=True)
            (bundle_root / "python-runtime" / "python.exe").write_bytes(b"py")
            (bundle_root / "bundle-manifest.json").write_text("{\"status\":\"ok\"}\n", encoding="utf-8")
            identity = {
                "schema_version": "astrabridge-release-identity-v1",
                "product_name": "AstraBridge",
                "package_identifier": "app.astrabridge.desktop",
                "release_version": "0.1.0",
                "sidecar": {
                    "formal_bundle": {
                        "schema_version": "astrabridge-sidecar-formal-bundle-v1",
                        "resource_path": "release/desktop-sidecar/windows-x64/astrabridge-sidecar",
                        "tauri_resource_source": "../../../release/desktop-sidecar/windows-x64/astrabridge-sidecar",
                        "resource_destination": "astrabridge-sidecar",
                        "launcher_path": "python-runtime/python.exe",
                        "launch_arguments": ["-m", "astrabridge_sidecar.server"],
                        "pythonpath_entry": ".",
                        "package_root": "astrabridge_sidecar",
                        "skills_root": "skills",
                        "origin": "app_managed",
                        "launcher_mode": "desktop-app-managed",
                        "allow_source_fallback_in_formal_package": False,
                    }
                },
                "protocol": {"schema_version": "astrabridge-protocol-v1"},
                "updater": {
                    "manifest_version": "astrabridge-updater-release-v1",
                    "create_updater_artifacts": True,
                    "pubkey": "untrusted comment: AstraBridge updater public key\nRWQtest",
                    "windows": {"install_mode": "passive"},
                    "default_channel": "stable",
                    "kill_switch": {
                        "manifest_path": "release/updater/kill-switch.json",
                        "default_mode": "allow",
                        "allow_disable_updates": True,
                    },
                    "channels": [
                        {
                            "channel": "stable",
                            "manifest_path": "release/updater/stable.json",
                            "endpoint": "https://updates.astrabridge.app/stable/{{target}}/{{arch}}/{{current_version}}",
                            "rollout": "general_availability",
                        },
                        {
                            "channel": "beta",
                            "manifest_path": "release/updater/beta.json",
                            "endpoint": "https://updates.astrabridge.app/beta/{{target}}/{{arch}}/{{current_version}}",
                            "rollout": "release_candidate",
                        },
                        {
                            "channel": "canary",
                            "manifest_path": "release/updater/canary.json",
                            "endpoint": "https://updates.astrabridge.app/canary/{{target}}/{{arch}}/{{current_version}}",
                            "rollout": "internal_preview",
                        },
                    ],
                },
                "staging": {"forbidden_paths": ["tests", ".venv", "PRIVATE", "__pycache__"]},
            }
            (root / "release").mkdir(parents=True, exist_ok=True)
            (root / "release" / "astrabridge-release-identity.json").write_text(
                json.dumps(identity, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            rehearsal_root = root / "PRIVATE" / "release-readiness" / "demo-run" / "windows-update-rehearsal"
            rehearsal_root.mkdir(parents=True, exist_ok=True)
            (rehearsal_root / "summary.json").write_text(
                json.dumps(
                    {
                        "run_id": "demo-run",
                        "created_at": "2026-07-18T02:00:00Z",
                        "status": "pass",
                        "selected_channel": "canary",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            status = desktop_update_status(
                repo_root=root,
                project={"ui_preferences": {"update_channel": "canary"}},
            )

            self.assertEqual(status["selected_channel"], "canary")
            self.assertEqual(status["default_channel"], "stable")
            self.assertEqual(status["latest_rehearsal"]["run_id"], "demo-run")
            self.assertEqual(status["formal_bundle"]["status"], "ready")

    def test_run_windows_update_rehearsal_records_clean_install_update_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            run_root = root / "PRIVATE" / "release-readiness" / "demo-run"
            stage_workspace = run_root / "stages" / "stage-a" / "workspace"
            updater_root = stage_workspace / "release" / "updater"
            bundle_root = stage_workspace / "release" / "desktop-sidecar" / "windows-x64" / "astrabridge-sidecar"
            (updater_root).mkdir(parents=True, exist_ok=True)
            (bundle_root / "python-runtime").mkdir(parents=True, exist_ok=True)
            (bundle_root / "astrabridge_sidecar").mkdir(parents=True, exist_ok=True)
            (bundle_root / "skills").mkdir(parents=True, exist_ok=True)
            (bundle_root / "python-runtime" / "python.exe").write_bytes(b"py")
            (bundle_root / "bundle-manifest.json").write_text("{\"status\":\"ok\"}\n", encoding="utf-8")
            (updater_root / "stable.json").write_text("{\"channel\":\"stable\"}\n", encoding="utf-8")
            (updater_root / "beta.json").write_text("{\"channel\":\"beta\"}\n", encoding="utf-8")
            (updater_root / "canary.json").write_text("{\"channel\":\"canary\"}\n", encoding="utf-8")
            (updater_root / "kill-switch.json").write_text("{\"default_mode\":\"allow\"}\n", encoding="utf-8")

            identity = {
                "schema_version": "astrabridge-release-identity-v1",
                "product_name": "AstraBridge",
                "package_identifier": "app.astrabridge.desktop",
                "release_version": "0.1.0",
                "sidecar": {
                    "formal_bundle": {
                        "schema_version": "astrabridge-sidecar-formal-bundle-v1",
                        "resource_path": "release/desktop-sidecar/windows-x64/astrabridge-sidecar",
                        "tauri_resource_source": "../../../release/desktop-sidecar/windows-x64/astrabridge-sidecar",
                        "resource_destination": "astrabridge-sidecar",
                        "launcher_path": "python-runtime/python.exe",
                        "launch_arguments": ["-m", "astrabridge_sidecar.server"],
                        "pythonpath_entry": ".",
                        "package_root": "astrabridge_sidecar",
                        "skills_root": "skills",
                        "origin": "app_managed",
                        "launcher_mode": "desktop-app-managed",
                        "allow_source_fallback_in_formal_package": False,
                    }
                },
                "protocol": {"schema_version": "astrabridge-protocol-v1"},
                "updater": {
                    "manifest_version": "astrabridge-updater-release-v1",
                    "create_updater_artifacts": True,
                    "pubkey": "untrusted comment: AstraBridge updater public key\nRWQtest",
                    "windows": {"install_mode": "passive"},
                    "default_channel": "stable",
                    "kill_switch": {
                        "manifest_path": "release/updater/kill-switch.json",
                        "default_mode": "allow",
                        "allow_disable_updates": True,
                    },
                    "channels": [
                        {
                            "channel": "stable",
                            "manifest_path": "release/updater/stable.json",
                            "endpoint": "https://updates.astrabridge.app/stable/{{target}}/{{arch}}/{{current_version}}",
                            "rollout": "general_availability",
                        },
                        {
                            "channel": "beta",
                            "manifest_path": "release/updater/beta.json",
                            "endpoint": "https://updates.astrabridge.app/beta/{{target}}/{{arch}}/{{current_version}}",
                            "rollout": "release_candidate",
                        },
                        {
                            "channel": "canary",
                            "manifest_path": "release/updater/canary.json",
                            "endpoint": "https://updates.astrabridge.app/canary/{{target}}/{{arch}}/{{current_version}}",
                            "rollout": "internal_preview",
                        },
                    ],
                },
                "staging": {"forbidden_paths": ["tests", ".venv", "PRIVATE", "__pycache__"]},
            }
            (root / "release").mkdir(parents=True, exist_ok=True)
            (root / "release" / "astrabridge-release-identity.json").write_text(
                json.dumps(identity, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            readiness_summary = {
                "status": "pass",
                "artifact_paths": {
                    "run_root": str(run_root),
                    "summary_json": str(run_root / "reports" / "summary.json"),
                },
                "staging_runs": {
                    "stage_a": {
                        "stage_workspace": str(stage_workspace),
                    }
                },
            }
            with patch.object(release_identity_module, "run_release_readiness_gate", return_value=readiness_summary):
                summary = run_windows_update_rehearsal(
                    repo_root=root,
                    artifact_root=root / "PRIVATE" / "release-readiness",
                    project={"ui_preferences": {"update_channel": "beta"}},
                    run_id="demo-run",
                )

            self.assertEqual(summary["status"], "pass")
            self.assertEqual(summary["selected_channel"], "beta")
            self.assertEqual(summary["clean_install_check"]["status"], "pass")
            self.assertEqual(summary["update_check"]["status"], "pass")
            self.assertEqual(summary["rollback_check"]["status"], "pass")
            self.assertEqual(summary["transaction"]["status"], "committed")
            self.assertEqual(summary["transaction"]["current_stage"], "committed")
            self.assertEqual(summary["recovery_matrix"]["status"], "pass")
            self.assertEqual(summary["recovery_matrix"]["scenario_count"], 4)
            scenarios = {
                item["interrupted_stage"]: item
                for item in summary["recovery_matrix"]["scenarios"]
            }
            self.assertEqual(
                scenarios["activation_written"]["final_status"],
                "rolled_back",
            )
            self.assertEqual(
                scenarios["activation_written"]["pointer_generation_id"],
                "generation-0000-prior",
            )
            self.assertEqual(
                scenarios["healthcheck_passed"]["final_status"],
                "committed",
            )
            self.assertEqual(
                scenarios["healthcheck_passed"]["pointer_generation_id"],
                "generation-0001-candidate",
            )
            self.assertTrue(Path(summary["artifact_paths"]["summary_json"]).exists())
            self.assertTrue(
                Path(summary["artifact_paths"]["transaction_recovery_matrix_json"]).exists()
            )


if __name__ == "__main__":
    unittest.main()
