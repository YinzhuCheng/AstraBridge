from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.usage_signal import normalize_usage_signal, usage_not_available


class UsageSignalTests(unittest.TestCase):
    def test_usage_signal_marks_not_available_with_reason(self) -> None:
        signal = usage_not_available(
            source="router_preview",
            reason="preview_only_no_provider_call",
            provider_id="deepseek",
            model="deepseek/deepseek-v4-pro",
        )

        self.assertEqual(signal["schema_version"], "astrabridge-usage-signal-v1")
        self.assertEqual(signal["status"], "not_available")
        self.assertEqual(signal["reason"], "preview_only_no_provider_call")
        self.assertEqual(signal["cost"]["status"], "not_available")
        self.assertEqual(signal["cost"]["reason"], "usage_not_available")

    def test_usage_signal_estimates_cost_from_openai_style_usage(self) -> None:
        signal = normalize_usage_signal(
            source="router_provider_health",
            provider_id="qwen",
            model="qwen/qwen3.7-plus",
            usage={
                "prompt_tokens": 1_000,
                "completion_tokens": 500,
                "total_tokens": 1_500,
                "completion_tokens_details": {"reasoning_tokens": 120},
            },
            pricing={
                "pricing_currency": "CNY",
                "pricing_input_per_mtok": 2,
                "pricing_output_per_mtok": 8,
                "pricing_status": "official_docs",
                "pricing_source_url": "https://example.invalid/pricing",
            },
        )

        self.assertEqual(signal["status"], "available")
        self.assertEqual(signal["tokens"]["input_tokens"], 1000)
        self.assertEqual(signal["tokens"]["output_tokens"], 500)
        self.assertEqual(signal["tokens"]["reasoning_tokens"], 120)
        self.assertEqual(signal["tokens"]["total_tokens"], 1500)
        self.assertEqual(signal["cost"]["status"], "estimated")
        self.assertEqual(signal["cost"]["currency"], "CNY")
        self.assertEqual(signal["cost"]["total_cost"], 0.006)


if __name__ == "__main__":
    unittest.main()
