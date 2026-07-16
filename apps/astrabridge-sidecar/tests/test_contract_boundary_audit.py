from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.contract_boundary_audit import (  # noqa: E402
    ACTIVE_PROVIDER_FAMILY_TRANSPORTS,
    CONTRACT_BOUNDARY_AUDIT_SCHEMA_VERSION,
    audit_contract_boundaries,
)


class ContractBoundaryAuditTests(unittest.TestCase):
    def test_current_provider_and_graph_contract_boundaries_pass(self) -> None:
        report = audit_contract_boundaries()

        self.assertEqual(report["schema_version"], CONTRACT_BOUNDARY_AUDIT_SCHEMA_VERSION)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["summary"]["error_count"], 0)
        self.assertEqual(report["summary"]["task_graph_fixture_count"], 7)
        self.assertEqual(report["summary"]["orchestration_example_count"], 6)
        self.assertTrue(all(check["status"] == "pass" for check in report["checks"]))

    def test_provider_registry_drift_is_reported(self) -> None:
        with patch.dict(ACTIVE_PROVIDER_FAMILY_TRANSPORTS, {}, clear=True):
            report = audit_contract_boundaries()

        provider_check = next(check for check in report["checks"] if check["contract"] == "provider_transport_selection")
        self.assertEqual(report["status"], "fail")
        self.assertEqual(provider_check["status"], "fail")
        self.assertIn("active provider transport registry drifted", provider_check["errors"][0])

    def test_graph_identity_drift_during_lowering_is_reported(self) -> None:
        from scripts import contract_boundary_audit as audit_module

        original_lower = audit_module.lower_agent_orchestration_graph_to_task_graph

        def lower_with_drift(graph: dict) -> dict:
            lowered = original_lower(graph)
            lowered["graph_id"] = "drifted_graph_id"
            return lowered

        with patch.object(audit_module, "lower_agent_orchestration_graph_to_task_graph", side_effect=lower_with_drift):
            report = audit_contract_boundaries()

        self.assertEqual(report["status"], "fail")
        self.assertTrue(any("contract field drift" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
