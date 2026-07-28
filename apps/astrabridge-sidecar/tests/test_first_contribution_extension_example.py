from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
SIDECAR_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = REPOSITORY_ROOT / "examples" / "extension-contribution" / "contributor-read-only-brief"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.agentic_updates.contracts import assert_secret_free_agentic_update_payload  # noqa: E402
from run_first_contribution_extension_example import run_first_contribution_extension_example  # noqa: E402


class FirstContributionExtensionExampleTests(unittest.TestCase):
    def test_candidate_example_validates_and_rejects_authority_widening(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence = run_first_contribution_extension_example(Path(temp_dir) / "extension-example")

        self.assertTrue((EXAMPLE_ROOT / "SKILL.md").is_file())
        self.assertTrue((EXAMPLE_ROOT / "orchestration-manifest.json").is_file())
        self.assertEqual(evidence["mode"], "deterministic_provider_free")
        self.assertEqual(evidence["provider_calls"], [])
        self.assertFalse(evidence["network_calls_attempted"])
        self.assertEqual(evidence["extension"]["classification"], "experimental_candidate")
        self.assertEqual(evidence["extension"]["skill_id"], "example.contributor-read-only-brief")
        self.assertEqual(evidence["extension"]["status"], "candidate")
        self.assertEqual(evidence["extension"]["graph_template_ref"], "supervisor_worker_synthesizer")
        self.assertEqual(evidence["validation"]["status"], "pass")
        self.assertEqual(evidence["validation"]["checks"], {"lint": "pass", "compile": "pass", "dry_run": "pass"})
        self.assertEqual(evidence["validation"]["provenance"], {"live_provider_calls": 0, "mcp_calls": 0, "agent_invocations": 0})
        self.assertEqual(evidence["failure_boundary"]["status"], "blocked")
        self.assertTrue(
            any("requested_route_widens_provider_allowlist" in item for item in evidence["failure_boundary"]["blockers"])
        )
        assert_secret_free_agentic_update_payload(evidence, label="first_contribution_extension_example")


if __name__ == "__main__":
    unittest.main()
