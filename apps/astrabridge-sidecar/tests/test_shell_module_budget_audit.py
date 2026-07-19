from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_local_gate import quick_command_specs  # noqa: E402
from scripts.shell_module_budget_audit import (  # noqa: E402
    SHELL_MODULE_BUDGET_AUDIT_SCHEMA_VERSION,
    TARGET_SHELL_MODULES,
    audit_shell_module_budgets,
)


class ShellModuleBudgetAuditTests(unittest.TestCase):
    def test_current_shell_module_budgets_pass(self) -> None:
        report = audit_shell_module_budgets()

        self.assertEqual(report["schema_version"], SHELL_MODULE_BUDGET_AUDIT_SCHEMA_VERSION)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["summary"]["error_count"], 0)
        self.assertEqual(report["summary"]["check_count"], 4)
        self.assertTrue(all(check["status"] == "pass" for check in report["checks"]))
        self.assertTrue(all(isinstance(check["budget_headroom"], int) for check in report["checks"]))
        self.assertTrue(all(check["budget_headroom"] >= 0 for check in report["checks"]))
        self.assertTrue(all(check["responsible_owners"] for check in report["checks"]))

    def test_budget_violation_is_reported(self) -> None:
        from scripts import shell_module_budget_audit as audit_module

        first = dict(TARGET_SHELL_MODULES[0])
        first["max_lines"] = 1
        with patch.object(audit_module, "TARGET_SHELL_MODULES", (first, *TARGET_SHELL_MODULES[1:])):
            report = audit_module.audit_shell_module_budgets()

        first_check = next(check for check in report["checks"] if check["module_id"] == first["module_id"])
        self.assertEqual(report["status"], "fail")
        self.assertEqual(first_check["status"], "fail")
        self.assertIn("line budget exceeded", first_check["message"])
        self.assertLess(first_check["budget_headroom"], 0)

    def test_quick_local_gate_projects_shell_module_budget_audit(self) -> None:
        check_ids = [item["check_id"] for item in quick_command_specs()]

        self.assertIn("shell_module_budget_audit", check_ids)
        self.assertIn("shell_module_budget_audit_tests", check_ids)


if __name__ == "__main__":
    unittest.main()
