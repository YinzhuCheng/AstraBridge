from __future__ import annotations

import json
import os
import threading
import time
import unittest
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from astrabridge_sidecar.modal_service import ModalService
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.runtime_config_service import RuntimeConfigService
from astrabridge_sidecar.runtime_client_pool import RuntimeClientPool
from astrabridge_sidecar.runtime_service import RuntimeService


class _FakeClient:
    def __init__(self, label: str) -> None:
        self.label = label
        self.closed = False
        self.close_count = 0

    def is_running(self) -> bool:
        return not self.closed

    def close(self) -> None:
        self.closed = True
        self.close_count += 1


class RuntimeClientPoolTests(unittest.TestCase):
    def test_runtime_service_keeps_different_provider_clients_alive(self) -> None:
        class FakeRuntimeConfig:
            def runtime_signature(self, status: dict[str, Any]) -> tuple[Any, ...]:
                return (status.get("provider_id"), status.get("model"))

            def status(self) -> dict[str, Any]:
                return {"configured": False}

        class FakeAppServerClient(_FakeClient):
            instances: list["FakeAppServerClient"] = []

            def __init__(self, **_kwargs: Any) -> None:
                super().__init__(str(len(self.instances)))
                self.instances.append(self)

            def start(self) -> None:
                self.closed = False

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "projects.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            runtime = RuntimeService(
                projects,
                ModalService(projects.require_shell_state_root),
                runtime_config=FakeRuntimeConfig(),  # type: ignore[arg-type]
            )
            runtime._resolve_launch_target = lambda _status: {  # type: ignore[method-assign]
                "codex_executable": "codex",
                "launch_command": ["codex"],
                "cwd": workspace,
                "env_updates": {},
            }
            with patch("astrabridge_sidecar.runtime_service.AppServerClient", FakeAppServerClient):
                first = runtime._ensure_client({"provider_id": "qwen", "model": "qwen-model"})  # type: ignore[attr-defined]
                second = runtime._ensure_client({"provider_id": "kimi", "model": "kimi-model"})  # type: ignore[attr-defined]
                same_first = runtime._ensure_client({"provider_id": "qwen", "model": "qwen-model"})  # type: ignore[attr-defined]
            self.assertIs(first, same_first)
            self.assertIsNot(first, second)
            self.assertFalse(first.closed)
            self.assertFalse(second.closed)
            self.assertEqual(len(FakeAppServerClient.instances), 2)
            runtime.shutdown()
            self.assertTrue(first.closed)
            self.assertTrue(second.closed)

    def test_runtime_config_uses_private_environment_without_global_mutation(self) -> None:
        from astrabridge_sidecar.runtime_config_service import ROUTER_ENV_KEY

        profile = {
            "profile_id": "private-env-provider",
            "provider_id": "private-env-provider",
            "base_url": "https://example.com/v1",
            "model": "private-model",
            "wire_api": "responses",
            "env_key": "PRIVATE_ENV_TEST_KEY",
            "auth_mode": "env_ref",
            "proxy_mode": "direct",
            "proxy_url": "",
        }
        old_router = os.environ.get("ASTRABRIDGE_BASE_URL")
        old_key = os.environ.get("PRIVATE_ENV_TEST_KEY")
        try:
            os.environ.pop("ASTRABRIDGE_BASE_URL", None)
            os.environ.pop("PRIVATE_ENV_TEST_KEY", None)
            private_environment = {
                "ASTRABRIDGE_BASE_URL": "http://127.0.0.1:45678/v1",
                ROUTER_ENV_KEY: "router-token-must-stay-private",
                "PRIVATE_ENV_TEST_KEY": "private-key-value",
            }
            with tempfile.TemporaryDirectory() as temp:
                config = RuntimeConfigService(Path(temp) / "codex-home")
                status = config.prepare_profile(
                    profile,
                    require_secret=True,
                    environment=private_environment,
                    codex_home=Path(temp) / "lane-home",
                )
                self.assertEqual(status["codex_home"], str((Path(temp) / "lane-home").resolve()))
                self.assertEqual(os.environ.get("ASTRABRIDGE_BASE_URL"), None)
                self.assertEqual(os.environ.get("PRIVATE_ENV_TEST_KEY"), None)
                config_text = (Path(temp) / "lane-home" / "config.toml").read_text(encoding="utf-8")
                self.assertIn("http://127.0.0.1:45678/v1", config_text)
                self.assertEqual(private_environment[ROUTER_ENV_KEY], "router-token-must-stay-private")
        finally:
            if old_router is None:
                os.environ.pop("ASTRABRIDGE_BASE_URL", None)
            else:
                os.environ["ASTRABRIDGE_BASE_URL"] = old_router
            if old_key is None:
                os.environ.pop("PRIVATE_ENV_TEST_KEY", None)
            else:
                os.environ["PRIVATE_ENV_TEST_KEY"] = old_key

    def test_different_lanes_progress_concurrently_and_close_is_scoped(self) -> None:
        pool = RuntimeClientPool(max_lanes=4, concurrency_limit=4)
        clients: dict[str, _FakeClient] = {}
        entered = {"qwen": threading.Event(), "kimi": threading.Event()}
        release = threading.Event()
        errors: list[BaseException] = []

        def worker(provider: str) -> None:
            try:
                signature = (provider, "model", "secret-fingerprint")
                lease = pool.acquire(signature, lambda: clients.setdefault(provider, _FakeClient(provider)), timeout=2)
                with lease:
                    entered[provider].set()
                    if not entered["qwen"].wait(2) or not entered["kimi"].wait(2):
                        raise AssertionError("provider lanes did not overlap")
                    release.wait(2)
            except BaseException as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(provider,)) for provider in ("qwen", "kimi")]
        for thread in threads:
            thread.start()
        self.assertTrue(entered["qwen"].wait(2))
        self.assertTrue(entered["kimi"].wait(2))
        pool.close_lane(("qwen", "model", "secret-fingerprint"), force=True)
        self.assertTrue(clients["qwen"].closed)
        self.assertFalse(clients["kimi"].closed)
        release.set()
        for thread in threads:
            thread.join(2)
        self.assertFalse(errors)
        pool.shutdown()

    def test_four_same_signature_acquisitions_create_one_client(self) -> None:
        pool = RuntimeClientPool(max_lanes=2, concurrency_limit=4)
        factory_calls = 0
        factory_lock = threading.Lock()
        client = _FakeClient("same")
        barrier = threading.Barrier(4)
        acquired: list[int] = []
        errors: list[BaseException] = []

        def factory() -> _FakeClient:
            nonlocal factory_calls
            with factory_lock:
                factory_calls += 1
            return client

        def worker() -> None:
            try:
                barrier.wait(2)
                with pool.acquire(("qwen", "same-model"), factory, timeout=2) as lease:
                    acquired.append(id(lease.client))
                    time.sleep(0.02)
            except BaseException as exc:  # pragma: no cover - surfaced below
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(3)
        self.assertFalse(errors)
        self.assertEqual(factory_calls, 1)
        self.assertEqual(len(acquired), 4)
        self.assertEqual(set(acquired), {id(client)})

    def test_idle_reaping_respects_active_leases_and_shutdown_closes_all(self) -> None:
        pool = RuntimeClientPool(max_lanes=4, idle_ttl_seconds=1, concurrency_limit=2)
        clients: dict[str, _FakeClient] = {}

        def factory(label: str):
            return lambda: clients.setdefault(label, _FakeClient(label))

        active = pool.acquire(("qwen",), factory("qwen"))
        active_snapshot = pool.snapshots()[0]
        self.assertEqual(pool.reap_idle(now=active_snapshot["last_used_at"] + 5), [])
        self.assertFalse(clients["qwen"].closed)
        active.release()
        reaped = pool.reap_idle(now=active_snapshot["last_used_at"] + 5)
        self.assertEqual(reaped, [pool.lane_id_for(("qwen",))])
        self.assertTrue(clients["qwen"].closed)

        pool.get_or_create(("kimi",), factory("kimi"))
        pool.get_or_create(("deepseek",), factory("deepseek"))
        closed = pool.shutdown()
        self.assertEqual(set(closed), {pool.lane_id_for(("kimi",)), pool.lane_id_for(("deepseek",))})
        self.assertTrue(clients["kimi"].closed)
        self.assertTrue(clients["deepseek"].closed)

    def test_lane_snapshots_never_include_signature_or_credential_values(self) -> None:
        secret = "super-secret-value-should-never-be-observable"
        pool = RuntimeClientPool()
        pool.get_or_create(("qwen", "model", secret), lambda: _FakeClient("qwen"))
        rendered = json.dumps(pool.snapshots(), ensure_ascii=False)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("model", rendered)
        self.assertIn("lane-", rendered)

    def test_restart_limit_is_bounded_per_lane(self) -> None:
        pool = RuntimeClientPool(max_restarts=1)
        created: list[_FakeClient] = []

        def factory() -> _FakeClient:
            client = _FakeClient(str(len(created)))
            created.append(client)
            return client

        signature = ("qwen", "bounded")
        first = pool.get_or_create(signature, factory)
        first.close()
        second = pool.get_or_create(signature, factory)
        self.assertIsNot(first, second)
        second.close()
        with self.assertRaisesRegex(RuntimeError, "restart_limit"):
            pool.get_or_create(signature, factory)


if __name__ == "__main__":
    unittest.main()
