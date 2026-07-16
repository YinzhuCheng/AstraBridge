from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.metadata_service import MetadataService
from astrabridge_sidecar.model_catalog import (
    MANAGED_PROVIDER_IDS,
    SOURCE_REGISTRY_SCHEMA_VERSION,
    build_generated_catalog,
    default_catalog_sources,
    normalize_provider_source_record,
    provider_source_registry_schema,
)
from astrabridge_sidecar.profile_service import ProfileService
from astrabridge_sidecar.router_config_service import RouterConfigService
from astrabridge_sidecar.router_service import RouterService
from astrabridge_sidecar.security import SecurityError


class ProviderSourceRegistryTests(unittest.TestCase):
    def test_default_registry_covers_managed_providers_with_source_metadata(self) -> None:
        sources = default_catalog_sources()
        by_provider = {item["provider_id"]: item for item in sources}

        self.assertTrue(set(MANAGED_PROVIDER_IDS).issubset(set(by_provider)))
        self.assertIn("openrouter", by_provider)
        for provider_id in MANAGED_PROVIDER_IDS:
            with self.subTest(provider_id=provider_id):
                source = by_provider[provider_id]
                self.assertEqual(source["source_registry_schema"], SOURCE_REGISTRY_SCHEMA_VERSION)
                self.assertTrue(source["urls"])
                self.assertTrue(source["source_records"])
                self.assertIn(source["trust_level"], provider_source_registry_schema()["trust_levels"])
                self.assertIn(source["channel"], provider_source_registry_schema()["channels"])
                self.assertIn(source["parser_strategy"], provider_source_registry_schema()["parser_strategies"])
                self.assertTrue(source["capability_categories"])
                self.assertIn(source["source_stability"], provider_source_registry_schema()["source_stability_levels"])
                self.assertIn(source["source_role"], provider_source_registry_schema()["source_roles"])
                self.assertRegex(source["retrieved_on"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertGreater(source["stale_after_days"], 0)
                self.assertIsInstance(source["promotion_policy"], dict)
                self.assertEqual(source["source_provenance"]["provider_id"], provider_id)
                self.assertTrue(
                    all(record.get("capability_categories") for record in source["source_records"])
                )

        openrouter = by_provider["openrouter"]
        self.assertEqual(openrouter["source_role"], "secondary_context")
        self.assertFalse(openrouter["promotion_policy"]["promotable"])

    def test_screenshot_and_untrusted_sources_are_non_promotable(self) -> None:
        yunwu = next(item for item in default_catalog_sources() if item["provider_id"] == "yunwu")
        self.assertEqual(yunwu["source_status"], "screenshot_seed")
        self.assertEqual(yunwu["trust_level"], "screenshot_seed")
        self.assertFalse(yunwu["promotion_policy"]["promotable"])
        self.assertTrue(yunwu["promotion_policy"]["requires_manual_review"])
        self.assertTrue(all(not record["promotable"] for record in yunwu["source_records"]))
        self.assertEqual(yunwu["source_role"], "secondary_context")

        custom = normalize_provider_source_record(
            {
                "provider_id": "custom",
                "display_name": "Custom Provider",
                "urls": ["https://example.test/provider-models"],
            }
        )
        self.assertEqual(custom["trust_level"], "untrusted")
        self.assertFalse(custom["promotion_policy"]["promotable"])
        self.assertTrue(custom["promotion_policy"]["requires_manual_review"])
        self.assertEqual(custom["source_role"], "secondary_context")
        self.assertEqual(custom["source_stability"], "likely_to_change")
        self.assertEqual(custom["retrieved_on"], "2026-07-06")
        self.assertEqual(custom["source_records"][0]["capability_categories"], ["protocol_reference"])

    def test_registry_rejects_secret_like_sources(self) -> None:
        with self.assertRaises(SecurityError):
            normalize_provider_source_record(
                {
                    "provider_id": "bad",
                    "display_name": "Bad",
                    "urls": ["https://example.test/models?api_key=secret-value"],
                }
            )

    def test_generated_catalog_writes_source_registry_schema_and_model_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            catalog = build_generated_catalog(output_root=Path(temp_dir))

            sources_lock = json.loads(Path(catalog.sources_lock_path).read_text(encoding="utf-8"))
            self.assertEqual(sources_lock["source_registry_schema"], SOURCE_REGISTRY_SCHEMA_VERSION)
            self.assertTrue(all("source_records" in item for item in sources_lock["sources"]))

            kimi = next(item for item in catalog.models if item["id"] == "kimi/kimi-k2.7-code")
            self.assertEqual(kimi["source_provenance"]["source_registry_schema"], SOURCE_REGISTRY_SCHEMA_VERSION)
            self.assertEqual(kimi["source_provenance"]["trust_level"], "official")
            self.assertTrue(kimi["source_provenance"]["promotable"])
            self.assertIn("tool_calling", kimi["source_provenance"]["capability_categories"])

            yunwu = next(item for item in catalog.models if item["id"] == "yunwu/gpt-5.5")
            self.assertEqual(yunwu["source_provenance"]["trust_level"], "screenshot_seed")
            self.assertFalse(yunwu["source_provenance"]["promotable"])
            self.assertEqual(yunwu["source_provenance"]["source_role"], "secondary_context")

            qwen_plus = next(item for item in catalog.models if item["id"] == "qwen/qwen3.7-plus")
            qwen_flash = next(item for item in catalog.models if item["id"] == "qwen/qwen3.6-flash")
            self.assertEqual(qwen_plus["input_modalities"], ["text", "image"])
            self.assertEqual(qwen_flash["input_modalities"], ["text", "image"])

    def test_metadata_service_sources_exposes_normalized_registry_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profiles = ProfileService(root / "profiles.json")
            config = RouterConfigService(profiles, root / "router.json")
            router = RouterService(profiles, config, port=0)
            metadata = MetadataService(config, router, root / "sources.json", root / "report")

            sources = metadata.sources()
            by_provider = {item["provider_id"]: item for item in sources["providers"]}

            self.assertEqual(sources["source_registry_schema"], SOURCE_REGISTRY_SCHEMA_VERSION)
            self.assertTrue(set(MANAGED_PROVIDER_IDS).issubset(set(by_provider)))
            self.assertIn("openrouter", by_provider)
            self.assertEqual(by_provider["deepseek"]["trust_level"], "official")
            self.assertIn("source_records", by_provider["deepseek"])
            self.assertIn("capability_categories", by_provider["deepseek"])
            self.assertFalse(by_provider["yunwu"]["promotion_policy"]["promotable"])
            self.assertEqual(by_provider["openrouter"]["source_role"], "secondary_context")

            saved = metadata.save_sources(
                {
                    "providers": [
                        {
                            "provider_id": "custom",
                            "display_name": "Custom Provider",
                            "urls": ["https://example.test/custom-models"],
                        }
                    ]
                }
            )
            custom = next(item for item in saved["providers"] if item["provider_id"] == "custom")
            self.assertEqual(custom["trust_level"], "untrusted")
            self.assertFalse(custom["promotion_policy"]["promotable"])
            self.assertEqual(custom["source_role"], "secondary_context")


if __name__ == "__main__":
    unittest.main()
