from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.profile_service import ProfileService
from astrabridge_sidecar.reasoning_policy import (
    normalize_reasoning_effort,
    normalize_reasoning_efforts,
    resolve_reasoning_state_visibility,
)
from astrabridge_sidecar.router_service import RouterService


class ReasoningPolicyNormalizationTests(unittest.TestCase):
    def test_reasoning_policy_helpers_normalize_aliases_and_visibility(self) -> None:
        self.assertEqual(normalize_reasoning_effort("none"), "off")
        self.assertEqual(normalize_reasoning_effort("max"), "xhigh")
        self.assertEqual(normalize_reasoning_effort("HIGH"), "high")
        self.assertIsNone(normalize_reasoning_effort("ultra"))
        self.assertEqual(normalize_reasoning_efforts(["none", "max", "high"]), ["off", "xhigh", "high"])
        self.assertEqual(resolve_reasoning_state_visibility("reasoning_content"), "visible_summary_only")
        self.assertEqual(resolve_reasoning_state_visibility("openai_responses"), "visible_summary_only")
        self.assertEqual(resolve_reasoning_state_visibility("enable_thinking", supports_reasoning_replay=True), "replayable")
        self.assertEqual(resolve_reasoning_state_visibility("none"), "provider_private")

    def test_preview_normalizes_reasoning_for_current_managed_provider_families(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            router = RouterService(profiles, port=0)

            yunwu = router.preview_payload(
                {
                    "model": "yunwu/gpt-5.5",
                    "input": "hello",
                    "stream": False,
                    "reasoning": {"effort": "max"},
                }
            )
            self.assertEqual(yunwu["upstream_payload"]["reasoning"]["effort"], "xhigh")
            self.assertTrue(any("normalized to 'xhigh'" in item for item in yunwu["warnings"]))

            qwen = router.preview_payload(
                {
                    "model": "qwen/qwen3.7-plus",
                    "input": "hello",
                    "stream": False,
                    "reasoning": {"effort": "none"},
                }
            )
            self.assertEqual(qwen["upstream_payload"]["enable_thinking"], False)
            self.assertNotIn("reasoning", qwen["upstream_payload"])
            self.assertTrue(any("normalized to 'off'" in item for item in qwen["warnings"]))

            deepseek = router.preview_payload(
                {
                    "model": "deepseek/deepseek-v4-pro",
                    "input": "hello",
                    "stream": False,
                    "reasoning": {"effort": "minimal"},
                    "temperature": 0.7,
                }
            )
            self.assertEqual(deepseek["upstream_payload"]["thinking"], {"type": "enabled"})
            self.assertEqual(deepseek["upstream_payload"]["reasoning_effort"], "high")
            self.assertNotIn("temperature", deepseek["upstream_payload"])

            kimi = router.preview_payload(
                {
                    "model": "kimi/kimi-k2.7-code",
                    "input": "hello",
                    "stream": False,
                    "reasoning": {"effort": "max"},
                }
            )
            self.assertEqual(kimi["upstream_payload"]["thinking"], {"type": "enabled", "keep": "all"})
            self.assertGreaterEqual(int(kimi["upstream_payload"]["max_tokens"]), 32768)
            self.assertTrue(any("normalized to 'xhigh'" in item for item in kimi["warnings"]))

            glm = router.preview_payload(
                {
                    "model": "glm/glm-5.2",
                    "input": "hello",
                    "stream": False,
                    "reasoning": {"effort": "ultra"},
                }
            )
            self.assertEqual(glm["upstream_payload"]["reasoning_effort"], "max")
            self.assertTrue(any("Unsupported reasoning effort 'ultra'" in item for item in glm["warnings"]))

            glm_max = router.preview_payload(
                {
                    "model": "glm/glm-5.2",
                    "input": "hello",
                    "stream": False,
                    "reasoning": {"effort": "xhigh"},
                }
            )
            self.assertEqual(glm_max["upstream_payload"]["reasoning_effort"], "max")

    def test_kimi_k27_rejects_off_reasoning_but_k26_still_allows_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "kimi-k26",
                    "label": "Kimi K2.6",
                    "type": "custom_provider",
                    "provider_id": "kimi",
                    "base_url": "https://api.moonshot.cn/v1",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "high",
                    "wire_api": "chat",
                    "env_key": "KIMI_API_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            profiles.upsert_profile(
                {
                    "profile_id": "kimi-k27",
                    "label": "Kimi K2.7 Code",
                    "type": "custom_provider",
                    "provider_id": "kimi",
                    "base_url": "https://api.moonshot.cn/v1",
                    "model": "kimi-k2.7-code",
                    "reasoning_effort": "high",
                    "wire_api": "chat",
                    "env_key": "KIMI_API_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)

            kimi_k26 = router.preview_payload(
                {
                    "model": "kimi/kimi-k2.6",
                    "input": "hello",
                    "stream": False,
                    "reasoning": {"effort": "off"},
                }
            )
            self.assertEqual(kimi_k26["upstream_payload"]["thinking"], {"type": "disabled"})

            with self.assertRaisesRegex(ValueError, "does not support reasoning effort 'off'"):
                router.preview_payload(
                    {
                        "model": "kimi/kimi-k2.7-code",
                        "input": "hello",
                        "stream": False,
                        "reasoning": {"effort": "off"},
                    }
                )

    def test_kimi_preview_rejects_invalid_fixed_parameters_in_thinking_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            profiles = ProfileService(Path(temp) / "profiles.json")
            profiles.upsert_profile(
                {
                    "profile_id": "kimi-k26",
                    "label": "Kimi K2.6",
                    "type": "custom_provider",
                    "provider_id": "kimi",
                    "base_url": "https://api.moonshot.cn/v1",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "high",
                    "wire_api": "chat",
                    "env_key": "KIMI_API_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                }
            )
            router = RouterService(profiles, port=0)

            with self.assertRaisesRegex(ValueError, "tool_choice 'auto' or 'none'"):
                router.preview_payload(
                    {
                        "model": "kimi/kimi-k2.6",
                        "input": "hello",
                        "stream": False,
                        "tool_choice": "required",
                    }
                )
            with self.assertRaisesRegex(ValueError, "top_p=0.95"):
                router.preview_payload(
                    {
                        "model": "kimi/kimi-k2.6",
                        "input": "hello",
                        "stream": False,
                        "top_p": 0.8,
                    }
                )
            with self.assertRaisesRegex(ValueError, "n=1"):
                router.preview_payload(
                    {
                        "model": "kimi/kimi-k2.6",
                        "input": "hello",
                        "stream": False,
                        "n": 2,
                    }
                )

            preview = router.preview_payload(
                {
                    "model": "kimi/kimi-k2.6",
                    "input": "hello",
                    "stream": False,
                    "tool_choice": "auto",
                    "top_p": 0.95,
                    "n": 1,
                    "presence_penalty": 0,
                    "frequency_penalty": 0,
                }
            )
            self.assertEqual(preview["upstream_payload"]["thinking"], {"type": "enabled"})
            self.assertEqual(preview["upstream_payload"]["tool_choice"], "auto")


if __name__ == "__main__":
    unittest.main()
