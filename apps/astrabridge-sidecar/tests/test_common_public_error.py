from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.common import public_error


class PublicErrorTests(unittest.TestCase):
    def test_public_error_redacts_public_payload_without_secondary_failure(self) -> None:
        exc = RuntimeError("thread start failed")
        exc.public_payload = {  # type: ignore[attr-defined]
            "api_key": "secret-value",
            "note": r"C:\Users\cyz19\Desktop\key.txt should never be persisted",
        }

        payload = public_error(exc)

        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["error"], "thread start failed")
        self.assertEqual(payload["api_key"], "[REDACTED]")
        self.assertEqual(payload["note"], "[REDACTED_DESKTOP_SECRET_PATH] should never be persisted")


if __name__ == "__main__":
    unittest.main()
