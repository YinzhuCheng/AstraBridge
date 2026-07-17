from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


class McpStdioServerScriptTests(unittest.TestCase):
    def test_astrabridge_web_wrapper_initializes_when_launched_as_script(self) -> None:
        server_path = Path(__file__).resolve().parents[1] / "astrabridge_sidecar" / "astrabridge_web_mcp_server.py"
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-11-25"},
        }

        proc = subprocess.Popen(
            [sys.executable, "-u", str(server_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            stdout, stderr = proc.communicate(json.dumps(request, separators=(",", ":")) + "\n", timeout=10)
        finally:
            if proc.poll() is None:
                proc.kill()

        self.assertEqual(proc.returncode, 0, stderr[-1000:])
        response = json.loads(stdout.strip().splitlines()[0])
        self.assertEqual(response["id"], 1)
        self.assertEqual(response["result"]["serverInfo"]["name"], "astrabridge-web-tools")
        self.assertEqual(response["result"]["protocolVersion"], "2025-11-25")


if __name__ == "__main__":
    unittest.main()
