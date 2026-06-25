from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_skill_probe import probe_skill_discovery


class _FakeSkillProbeClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.requests: list[str] = []
        self.closed = False

    def start(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    def request(self, method: str, params=None, timeout: float = 120.0):  # noqa: ARG002
        self.requests.append(method)
        if method == "skills/list":
            return self._payload
        raise AssertionError(f"Unexpected method: {method}")


class CodexSkillProbeTests(unittest.TestCase):
    def test_probe_discovers_plugin_provided_skill_and_owner_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / "codex-home"
            codex_home.mkdir()
            search_root = root / "isolated"
            skill_path = _write_plugin_skill(search_root, plugin_name="demo-plugin", skill_name="demo-plugin-skill")

            payload = {
                "data": [
                    {
                        "cwd": str(search_root),
                        "skills": [
                            {
                                "name": "demo-plugin-skill",
                                "description": "Use this skill when the plugin should handle demo tasks.",
                                "shortDescription": "Handle demo tasks",
                                "path": str(skill_path),
                                "scope": "user",
                                "enabled": True,
                                "interface": {"displayName": "Demo Plugin Skill", "defaultPrompt": "Run the demo plugin skill."},
                                "dependencies": {"tools": [{"name": "tool_search"}]},
                            }
                        ],
                        "errors": [],
                    }
                ]
            }

            report = probe_skill_discovery(
                codex_home=codex_home,
                client_factory=lambda on_notification, on_server_request: _FakeSkillProbeClient(payload),
                local_search_roots=[search_root],
                artifact_root=root / "artifacts",
                request_timeout=1.0,
            )

            self.assertEqual(report["skill"]["list_status"], "supported")
            skill = report["skill"]["discovered_skills"][0]
            self.assertEqual(skill["skill_name"], "demo-plugin-skill")
            self.assertEqual(skill["source_kind"], "plugin")
            self.assertEqual(skill["owner_plugin_id"], "demo-plugin")
            self.assertEqual(skill["enablement"], "enabled")
            self.assertEqual(skill["version_hint"], "1.2.3")
            self.assertEqual(skill["dependency_tools"], ["tool_search"])

    def test_probe_discovers_local_skill_and_content_hash_from_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / "codex-home"
            codex_home.mkdir()
            local_root = root / "workspace"
            skill_path = _write_skill(
                local_root / "skills" / "local-skill" / "SKILL.md",
                frontmatter='---\nname: local-skill\ndescription: Use this skill when local skill routing is needed.\n---\n\n# Local Skill\n',
            )

            report = probe_skill_discovery(
                codex_home=codex_home,
                local_search_roots=[local_root],
                artifact_root=root / "artifacts",
            )

            skill = next(item for item in report["skill"]["discovered_skills"] if item["skill_name"] == "local-skill")
            self.assertEqual(skill["source_kind"], "local_skill_root")
            self.assertEqual(skill["description_status"], "present")
            self.assertTrue(skill["content_sha256"])
            self.assertIn("Use this skill when local skill routing is needed", skill["trigger_hints"][0])
            self.assertEqual(report["skill"]["duplicate_skill_names"], [])

    def test_probe_reports_duplicate_skill_names_across_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / "codex-home"
            codex_home.mkdir()
            root_a = root / "workspace-a"
            root_b = root / "workspace-b"
            _write_skill(
                root_a / "skills" / "one" / "SKILL.md",
                frontmatter='---\nname: duplicate-skill\ndescription: First copy.\n---\n',
            )
            _write_skill(
                root_b / "skills" / "two" / "SKILL.md",
                frontmatter='---\nname: duplicate-skill\ndescription: Second copy.\n---\n',
            )

            report = probe_skill_discovery(
                codex_home=codex_home,
                local_search_roots=[root_a, root_b],
                artifact_root=root / "artifacts",
            )

            self.assertEqual(report["skill"]["duplicate_skill_names"], ["duplicate-skill"])
            self.assertEqual(len(report["skill"]["discovered_skills"]), 2)
            self.assertIn("duplicate_skill_names_detected", report["skill"]["notes"])

    def test_probe_reports_malformed_skill_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / "codex-home"
            codex_home.mkdir()
            local_root = root / "workspace"
            skill_path = _write_skill(
                local_root / "skills" / "broken-skill" / "SKILL.md",
                frontmatter='---\nname: broken-skill\ndescription: Broken skill without closing delimiter.\n',
            )

            report = probe_skill_discovery(
                codex_home=codex_home,
                local_search_roots=[local_root],
                artifact_root=root / "artifacts",
            )

            self.assertIn(str(skill_path), report["skill"]["malformed_skill_paths"])
            broken = next(item for item in report["skill"]["discovered_skills"] if item["skill_name"] == "broken-skill")
            self.assertEqual(broken["manifest_status"], "malformed")

    def test_probe_reports_missing_skill_description(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / "codex-home"
            codex_home.mkdir()
            local_root = root / "workspace"
            skill_path = _write_skill(
                local_root / "skills" / "no-description" / "SKILL.md",
                frontmatter='---\nname: no-description\n---\n\n# No Description\n',
            )

            report = probe_skill_discovery(
                codex_home=codex_home,
                local_search_roots=[local_root],
                artifact_root=root / "artifacts",
            )

            self.assertIn(str(skill_path), report["skill"]["missing_description_paths"])
            skill = next(item for item in report["skill"]["discovered_skills"] if item["skill_name"] == "no-description")
            self.assertEqual(skill["description_status"], "missing")
            self.assertIn("missing_skill_descriptions_detected", report["skill"]["notes"])


def _write_plugin_skill(root: Path, *, plugin_name: str, skill_name: str) -> Path:
    marketplace_path = root / ".agents" / "plugins" / "marketplace.json"
    plugin_root = marketplace_path.parent / "plugins" / plugin_name
    (plugin_root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    skill_path = plugin_root / "skills" / skill_name / "SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text(
        '{"name":"personal","plugins":[{"name":"' + plugin_name + '","source":{"source":"local","path":"./plugins/' + plugin_name + '"},"policy":{"installation":"AVAILABLE","authentication":"ON_INSTALL"},"category":"Productivity"}]}',
        encoding="utf-8",
    )
    (plugin_root / ".codex-plugin" / "plugin.json").write_text(
        '{"name":"' + plugin_name + '","version":"1.2.3"}',
        encoding="utf-8",
    )
    skill_path.write_text(
        '---\nname: ' + skill_name + '\ndescription: Use this skill when the plugin should handle demo tasks.\n---\n',
        encoding="utf-8",
    )
    return skill_path.resolve()


def _write_skill(path: Path, *, frontmatter: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frontmatter, encoding="utf-8")
    return path.resolve()


if __name__ == "__main__":
    unittest.main()
