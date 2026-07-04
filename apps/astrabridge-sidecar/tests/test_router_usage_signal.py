from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.profile_service import ProfileService
from astrabridge_sidecar.router_service import RouterService


class RouterUsageSignalTests(unittest.TestCase):
    def test_preview_and_provider_health_expose_usage_signal(self) -> None:
        class UpstreamHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                body = json.dumps(
                    {
                        "id": "resp_usage_signal",
                        "object": "response",
                        "model": "gpt-5.5",
                        "output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}],
                        "usage": {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
                    }
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

        upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        thread.start()
        original = os.environ.get("TEST_ROUTER_USAGE_KEY")
        try:
            with tempfile.TemporaryDirectory() as temp:
                profiles = ProfileService(Path(temp) / "profiles.json")
                profiles.upsert_profile(
                    {
                        "profile_id": "router-openai",
                        "label": "Router OpenAI",
                        "type": "custom_provider",
                        "provider_id": "openai",
                        "base_url": f"http://127.0.0.1:{upstream.server_address[1]}",
                        "model": "gpt-5.5",
                        "reasoning_effort": "high",
                        "wire_api": "responses",
                        "env_key": "TEST_ROUTER_USAGE_KEY",
                        "auth_mode": "env_ref",
                        "proxy_mode": "direct",
                        "proxy_url": "",
                    }
                )
                os.environ["TEST_ROUTER_USAGE_KEY"] = "unit_secret_provider_test"
                router = RouterService(profiles, port=0)

                preview = router.preview_payload({"model": "openai/gpt-5.5", "input": "hello", "stream": False})
                self.assertEqual(preview["usage_signal"]["status"], "not_available")
                self.assertEqual(preview["usage_signal"]["reason"], "preview_only_no_provider_call")

                health = router.test_provider("openai", "gpt-5.5", stream=False)
                self.assertTrue(health["ok"])
                self.assertEqual(health["usage_signal"]["status"], "available")
                self.assertEqual(health["usage_signal"]["tokens"]["input_tokens"], 11)
                self.assertEqual(health["usage_signal"]["tokens"]["output_tokens"], 7)
                self.assertEqual(health["usage_signal"]["tokens"]["total_tokens"], 18)
                self.assertEqual(health["usage_signal"]["cost"]["status"], "not_available")
                self.assertEqual(health["usage_signal"]["cost"]["reason"], "pricing_not_configured")
        finally:
            upstream.shutdown()
            upstream.server_close()
            if original is None:
                os.environ.pop("TEST_ROUTER_USAGE_KEY", None)
            else:
                os.environ["TEST_ROUTER_USAGE_KEY"] = original


if __name__ == "__main__":
    unittest.main()
