from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.browser_workbench_service import BrowserWorkbenchService


class _FakeProjects:
    def __init__(self, root: Path) -> None:
        self.root = root

    def require_shell_subdir(self, *parts: str) -> Path:
        path = self.root.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def require_shell_state_root(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root


class _FakeSession:
    def __init__(self, session_id: str, role: str, session_dir: Path) -> None:
        self.id = session_id
        self.role = role
        self.title = f"AstraBridge Browser - {role}"
        self.session_dir = session_dir
        self.screenshot_path = self.session_dir / "frame.png"
        self.state = {
            "id": session_id,
            "role": role,
            "title": self.title,
            "url": "",
            "status": "idle",
            "error": None,
            "preview_mode": "remote",
            "viewport_width": 1365,
            "viewport_height": 900,
            "layout_mode": "desktop",
            "layout_reason": "desktop",
            "mobile_optimized": None,
            "mobile_strategy": "desktop_viewport",
            "responsive_fit_score": None,
            "updated_at": "2026-06-28T00:00:00Z",
        }
        self.closed = False

    def snapshot(self) -> dict[str, object]:
        return dict(self.state)

    def request(self, method: str, params: dict[str, object], *, timeout: float = 35.0) -> dict[str, object]:
        del timeout
        if method == "create":
            mode = str(params.get("layout_mode") or "desktop")
            viewport = {"width": 390, "height": 844} if mode == "mobile" else {"width": 1365, "height": 900}
            self.state.update(
                {
                    "url": str(params.get("url") or ""),
                    "status": "open",
                    "page_title": "Example Domain",
                    "layout_mode": mode,
                    "layout_reason": str(params.get("layout_reason") or ""),
                    "viewport_width": viewport["width"],
                    "viewport_height": viewport["height"],
                    "mobile_strategy": "mobile_user_agent_viewport" if mode == "mobile" else "desktop_viewport",
                }
            )
            self.screenshot_path.write_bytes(b"png")
            return self.snapshot()
        if method == "navigate":
            next_state = {"url": str(params.get("url") or ""), "status": "open"}
            mode = str(params.get("layout_mode") or "").strip()
            if mode:
                viewport = {"width": 390, "height": 844} if mode == "mobile" else {"width": 1365, "height": 900}
                next_state.update(
                    {
                        "layout_mode": mode,
                        "layout_reason": str(params.get("layout_reason") or ""),
                        "viewport_width": viewport["width"],
                        "viewport_height": viewport["height"],
                        "mobile_strategy": "mobile_user_agent_viewport" if mode == "mobile" else "desktop_viewport",
                    }
                )
            self.state.update(next_state)
            return self.snapshot()
        if method == "layout":
            mode = str(params.get("layout_mode") or "desktop")
            viewport = {"width": 390, "height": 844} if mode == "mobile" else {"width": 1365, "height": 900}
            self.state.update(
                {
                    "layout_mode": mode,
                    "layout_reason": str(params.get("layout_reason") or ""),
                    "viewport_width": viewport["width"],
                    "viewport_height": viewport["height"],
                    "mobile_optimized": mode == "mobile",
                    "mobile_strategy": "mobile_user_agent_viewport" if mode == "mobile" else "desktop_viewport",
                    "responsive_fit_score": 96 if mode == "mobile" else None,
                }
            )
            return self.snapshot()
        if method == "action":
            self.state.update({"status": "open", "last_action": str(params.get("action") or "")})
            return self.snapshot()
        if method == "snapshot":
            return self.snapshot()
        if method == "close":
            self.closed = True
            self.state.update({"status": "closed"})
            return self.snapshot()
        raise AssertionError(f"Unexpected method: {method}")

    def close(self) -> None:
        self.closed = True
        self.state.update({"status": "closed"})


class BrowserWorkbenchServiceTests(unittest.TestCase):
    def test_create_navigate_action_and_close_remote_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = BrowserWorkbenchService(_FakeProjects(Path(temp_dir)), session_factory=_FakeSession)

            created = service.create_session({"role": "Example", "url": "example.com"})
            self.assertEqual(created["status"], "open")
            self.assertEqual(created["preview_mode"], "remote")
            self.assertEqual(created["url"], "https://example.com")

            sessions = service.list_sessions()
            self.assertEqual(len(sessions), 1)
            self.assertEqual(sessions[0]["id"], created["id"])

            navigated = service.navigate({"id": created["id"], "url": "https://example.org/"})
            self.assertEqual(navigated["url"], "https://example.org/")

            clicked = service.action({"id": created["id"], "action": "click", "x": 10, "y": 20})
            self.assertEqual(clicked["last_action"], "click")

            mobile = service.layout({"id": created["id"], "layout_mode": "mobile", "layout_reason": "test tall panel"})
            self.assertEqual(mobile["layout_mode"], "mobile")
            self.assertEqual(mobile["viewport_width"], 390)
            self.assertTrue(mobile["mobile_optimized"])
            self.assertEqual(mobile["mobile_strategy"], "mobile_user_agent_viewport")
            self.assertEqual(mobile["responsive_fit_score"], 96)

            frame_path = service.frame_path(str(created["id"]))
            self.assertTrue(frame_path.is_file())

            remaining = service.close(str(created["id"]))
            self.assertEqual(remaining, [])

    def test_mobile_layout_uses_known_mobile_entry_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = BrowserWorkbenchService(_FakeProjects(Path(temp_dir)), session_factory=_FakeSession)

            created = service.create_session({
                "role": "YouTube",
                "url": "https://www.youtube.com/results?search_query=astrabridge",
                "layout_mode": "mobile",
            })

            self.assertEqual(created["url"], "https://m.youtube.com/results?search_query=astrabridge")
            self.assertEqual(created["layout_mode"], "mobile")
            self.assertEqual(created["mobile_strategy"], "mobile_host_rewrite_viewport")

            navigated = service.navigate({
                "id": created["id"],
                "url": "https://youtu.be/dQw4w9WgXcQ?feature=shared",
                "layout_mode": "mobile",
            })
            self.assertEqual(navigated["url"], "https://m.youtube.com/watch?v=dQw4w9WgXcQ&feature=shared")
            self.assertEqual(navigated["mobile_strategy"], "mobile_host_rewrite_viewport")

    def test_mobile_layout_uses_google_embed_entry_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = BrowserWorkbenchService(_FakeProjects(Path(temp_dir)), session_factory=_FakeSession)

            created = service.create_session({
                "role": "Google",
                "url": "https://www.google.com/search?q=astrabridge",
                "layout_mode": "mobile",
            })

            self.assertEqual(created["url"], "https://www.google.com/search?q=astrabridge&igu=1")
            self.assertEqual(created["mobile_strategy"], "mobile_host_rewrite_viewport")

            desktop_search = service.layout({"id": created["id"], "layout_mode": "desktop", "layout_reason": "wide inspector"})
            self.assertEqual(desktop_search["url"], "https://www.google.com/search?q=astrabridge")
            self.assertEqual(desktop_search["mobile_strategy"], "desktop_viewport")

            news = service.navigate({
                "id": created["id"],
                "url": "https://news.google.com/search?q=astrabridge&hl=en-US&gl=US&ceid=US:en",
                "layout_mode": "mobile",
            })
            self.assertEqual(news["url"], "https://news.google.com/search?q=astrabridge&hl=en-US&gl=US&ceid=US:en")
            self.assertEqual(news["mobile_strategy"], "mobile_user_agent_viewport")

    def test_mobile_layout_rewrites_language_wikipedia_hosts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = BrowserWorkbenchService(_FakeProjects(Path(temp_dir)), session_factory=_FakeSession)

            created = service.create_session({
                "role": "Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Astra_(satellite)",
                "layout_mode": "mobile",
            })

            self.assertEqual(created["url"], "https://en.m.wikipedia.org/wiki/Astra_(satellite)")
            self.assertEqual(created["mobile_strategy"], "mobile_host_rewrite_viewport")

            desktop = service.layout({"id": created["id"], "layout_mode": "desktop", "layout_reason": "wide inspector"})
            self.assertEqual(desktop["url"], "https://en.wikipedia.org/wiki/Astra_(satellite)")
            self.assertEqual(desktop["mobile_strategy"], "desktop_viewport")

    def test_layout_switch_rewrites_between_desktop_and_mobile_hosts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = BrowserWorkbenchService(_FakeProjects(Path(temp_dir)), session_factory=_FakeSession)

            created = service.create_session({
                "role": "YouTube",
                "url": "https://www.youtube.com/results?search_query=astrabridge",
                "layout_mode": "desktop",
            })
            self.assertEqual(created["url"], "https://www.youtube.com/results?search_query=astrabridge")

            mobile = service.layout({"id": created["id"], "layout_mode": "mobile", "layout_reason": "tall inspector"})
            self.assertEqual(mobile["url"], "https://m.youtube.com/results?search_query=astrabridge")
            self.assertEqual(mobile["layout_mode"], "mobile")
            self.assertEqual(mobile["mobile_strategy"], "mobile_host_rewrite_viewport")

            desktop = service.layout({"id": created["id"], "layout_mode": "desktop", "layout_reason": "wide inspector"})
            self.assertEqual(desktop["url"], "https://www.youtube.com/results?search_query=astrabridge")
            self.assertEqual(desktop["layout_mode"], "desktop")
            self.assertEqual(desktop["mobile_strategy"], "desktop_viewport")


if __name__ == "__main__":
    unittest.main()
