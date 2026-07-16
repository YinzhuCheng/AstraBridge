from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.common import (  # noqa: E402
    DEFAULT_WINDOWS_RUNTIME_ROOT,
    app_data_dir,
    app_runtime_root,
    default_codex_home,
)
from astrabridge_sidecar.project_service import ProjectService  # noqa: E402


class RuntimeStorageIsolationTests(unittest.TestCase):
    _ENV_KEYS = (
        "ASTRABRIDGE_APPDATA",
        "ASTRABRIDGE_CODEX_HOME",
        "ASTRABRIDGE_RUNTIME_ROOT",
        "USERPROFILE",
    )

    def setUp(self) -> None:
        self._environment = {key: os.environ.get(key) for key in self._ENV_KEYS}
        for key in self._ENV_KEYS:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self._environment.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_windows_default_runtime_root_is_on_d_drive(self) -> None:
        self.assertEqual(str(DEFAULT_WINDOWS_RUNTIME_ROOT).replace("\\", "/"), "D:/AstraBridgeRuntime")
        if os.name == "nt" and Path("D:/").is_dir():
            self.assertEqual(app_runtime_root(), DEFAULT_WINDOWS_RUNTIME_ROOT.resolve())
            self.assertEqual(
                default_codex_home(),
                (DEFAULT_WINDOWS_RUNTIME_ROOT / "embedded_codex_home").resolve(),
            )

    def test_explicit_runtime_root_owns_project_runtime_and_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime_root = root / "d-runtime"
            os.environ["ASTRABRIDGE_APPDATA"] = str(root / "appdata")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = str(runtime_root)
            workspace = root / "workspace"
            workspace.mkdir()

            projects = ProjectService(root / "projects.json", root / "current-project.json")
            projects.create_project(
                "Isolation",
                root / "isolation.abproj",
                workspace_root=workspace,
                entry_mode="existing",
            )

            roots = projects.current_runtime_roots()
            for name, path in roots.items():
                with self.subTest(name=name):
                    Path(path).resolve().relative_to(runtime_root.resolve())
            policy = json.loads(
                (workspace / ".astrabridge" / "storage_policy.json").read_text(encoding="utf-8")
            )
            self.assertEqual(Path(policy["runtime"]["project_runtime_root"]), roots["project_runtime_root"])
            self.assertEqual(default_codex_home(), (runtime_root / "embedded_codex_home").resolve())

    def test_explicit_appdata_keeps_test_and_demo_runtime_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            appdata = Path(temp) / "clean-user"
            os.environ["ASTRABRIDGE_APPDATA"] = str(appdata)

            self.assertEqual(app_data_dir(), appdata.resolve())
            self.assertEqual(app_runtime_root(), (appdata / "runtime").resolve())
            self.assertEqual(default_codex_home(), (appdata / "runtime" / "embedded_codex_home").resolve())

    def test_official_codex_home_overlap_is_rejected_for_every_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            user_profile = Path(temp) / "user"
            official_home = user_profile / ".codex"
            os.environ["USERPROFILE"] = str(user_profile)

            cases = (
                ("ASTRABRIDGE_APPDATA", official_home, app_data_dir),
                ("ASTRABRIDGE_RUNTIME_ROOT", official_home / "runtime", app_runtime_root),
                ("ASTRABRIDGE_CODEX_HOME", official_home, default_codex_home),
            )
            for env_key, unsafe_path, resolver in cases:
                with self.subTest(env_key=env_key):
                    for key in ("ASTRABRIDGE_APPDATA", "ASTRABRIDGE_RUNTIME_ROOT", "ASTRABRIDGE_CODEX_HOME"):
                        os.environ.pop(key, None)
                    os.environ[env_key] = str(unsafe_path)
                    with self.assertRaisesRegex(ValueError, "official Codex home"):
                        resolver()


if __name__ == "__main__":
    unittest.main()
