from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
AUTHORING = REPO_ROOT / "docs" / "SKILL_FIRST_ORCHESTRATION_AUTHORING_RUNBOOK.md"
OPERATOR = REPO_ROOT / "docs" / "SKILL_FIRST_ORCHESTRATION_OPERATOR_RUNBOOK.md"


class SkillFirstRunbookContractTests(unittest.TestCase):
    def test_authoring_and_operator_runbooks_exist_with_canonical_ownership_links(self) -> None:
        self.assertTrue(AUTHORING.is_file())
        self.assertTrue(OPERATOR.is_file())
        authoring = AUTHORING.read_text(encoding="utf-8")
        operator = OPERATOR.read_text(encoding="utf-8")

        for text in (authoring, operator):
            self.assertIn("ASTRABRIDGE_SKILL_FIRST_ORCHESTRATION_BOUNDARY_CONTRACT.md", text)
            self.assertIn("ASTRABRIDGE_SKILL_TO_GRAPH_CONTRACT.md", text)
            self.assertIn("ASTRABRIDGE_SKILL_BACKED_ORCHESTRATION_MCP_SURFACE_CONTRACT.md", text)
            self.assertIn("astrabridge-orchestration", text)
            self.assertIn("no-new-GUI", text)
            self.assertIn("allow_nested_subagents=false", text)
            self.assertIn("allow_direct_teammate_messages=false", text)

        for heading in (
            "## 初始 pattern 选择",
            "## Skill 包结构",
            "## Manifest authoring checklist",
            "## 一次 authoring 流程",
            "## 生命周期和证据门槛",
            "## 不支持路径与升级请求",
        ):
            self.assertIn(heading, authoring)
        for heading in (
            "## 运行前检查",
            "## Canonical MCP 生命周期",
            "## 状态和 guardrail 解释",
            "## 证据、目录和无 provider 操作",
            "## 明确不支持的操作",
            "## 交接模板",
        ):
            self.assertIn(heading, operator)

    def test_runbook_local_markdown_links_resolve(self) -> None:
        for document in (AUTHORING, OPERATOR):
            text = document.read_text(encoding="utf-8")
            links = re.findall(r"\]\((\.\.?/[^)#]+)(?:#[^)]+)?\)", text)
            self.assertGreaterEqual(len(links), 8)
            for link in links:
                target = (document.parent / link).resolve()
                self.assertTrue(target.exists(), f"broken runbook link: {document} -> {link}")


if __name__ == "__main__":
    unittest.main()
