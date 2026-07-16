from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.capabilities.runtime import _workspace_root


class CapabilityRuntimeWorkspaceRootTests(unittest.TestCase):
    def test_workspace_root_falls_back_to_current_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {}, clear=True):
                with patch("astrabridge_sidecar.capabilities.runtime.os.getcwd", return_value=temp_dir):
                    self.assertEqual(_workspace_root(), str(Path(temp_dir).resolve()))


if __name__ == "__main__":
    unittest.main()
