from __future__ import annotations

import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agentic_updates import AGENTIC_UPDATE_DISCOVERY_SCHEMA_VERSION, run_agentic_update_discovery


class AgenticUpdateDiscoveryTests(unittest.TestCase):
    def test_fixture_discovery_writes_complete_source_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = _provider_source(
                [
                    {
                        "source_id": "qwen-models",
                        "url": "https://example.test/qwen-models",
                        "source_type": "models_catalog",
                    }
                ]
            )

            result = run_agentic_update_discovery(
                workspace_root=Path(temp_dir),
                run_id="fixture-run",
                run_contract={"scope": "provider_metadata", "providers": ["qwen"], "allow_network": False},
                provider_sources=[source],
                fixture_sources={"qwen-models": {"body": "<html><body>Qwen model table</body></html>", "content_type": "text/html"}},
            )

            self.assertEqual(result["schema_version"], AGENTIC_UPDATE_DISCOVERY_SCHEMA_VERSION)
            self.assertEqual(result["mode"], "fixture")
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["summary"]["ok_sources"], 1)
            index_path = Path(result["artifact_paths"]["source_index"])
            pack_path = Path(result["artifact_paths"]["source_pack"])
            self.assertTrue(index_path.exists())
            self.assertTrue(pack_path.exists())
            index = json.loads(index_path.read_text(encoding="utf-8"))
            pack_records = _read_jsonl(pack_path)
            self.assertEqual(index["summary"]["total_sources"], 1)
            self.assertEqual(len(pack_records), 1)
            self.assertEqual(pack_records[0]["classification"], "ok")
            self.assertTrue(str(pack_records[0]["content_hash"]).startswith("sha256:"))
            self.assertIn("Qwen model table", pack_records[0]["excerpt"])

    def test_network_discovery_records_metadata_without_full_dump_or_secrets(self) -> None:
        def fake_fetch(url: str, timeout_sec: int, max_bytes: int) -> dict[str, object]:
            body = ("Authorization: Bearer abcdefghijklmnopqrstuvwxyz\n" + ("Visible source text.\n" * 200)).encode()
            return {
                "url": url,
                "status_code": 200,
                "content_type": "text/plain; charset=utf-8",
                "content_length": len(body),
                "body": body[:max_bytes],
                "body_truncated": False,
                "started_at": "2026-07-18T00:00:00+00:00",
                "finished_at": "2026-07-18T00:00:01+00:00",
                "duration_ms": 20,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            url = "https://official.example.test/models"
            result = run_agentic_update_discovery(
                workspace_root=Path(temp_dir),
                run_id="network-run",
                run_contract={"scope": "provider_metadata", "providers": ["qwen"], "allow_network": True},
                provider_sources=[_provider_source([{"source_id": "qwen-public", "url": url}])],
                fetcher=fake_fetch,
                max_bytes_per_source=6000,
                max_excerpt_chars=160,
                timeout_sec=2,
            )
            pack_records = _read_jsonl(Path(result["artifact_paths"]["source_pack"]))
            text = Path(result["artifact_paths"]["source_pack"]).read_text(encoding="utf-8")

            self.assertEqual(result["mode"], "network")
            self.assertEqual(result["status"], "pass")
            self.assertEqual(pack_records[0]["status_code"], 200)
            self.assertEqual(pack_records[0]["content_length"], len(("Authorization: Bearer abcdefghijklmnopqrstuvwxyz\n" + ("Visible source text.\n" * 200)).encode()))
            self.assertFalse(pack_records[0]["body_truncated"])
            self.assertLessEqual(pack_records[0]["excerpt_chars"], 172)
            self.assertNotIn("abcdefghijklmnopqrstuvwxyz", text)
            self.assertNotIn("Visible source text." * 30, text)

    def test_timeout_and_failed_fetch_are_classified(self) -> None:
        def fake_fetch(url: str, timeout_sec: int, max_bytes: int) -> dict[str, object]:
            if "timeout" in url:
                raise TimeoutError("timed out")
            raise urllib.error.URLError("connection refused")

        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_agentic_update_discovery(
                workspace_root=Path(temp_dir),
                run_id="failure-run",
                run_contract={"scope": "provider_metadata", "providers": ["qwen"], "allow_network": True},
                provider_sources=[
                    _provider_source(
                        [
                            {"source_id": "timeout", "url": "https://example.test/timeout"},
                            {"source_id": "failed", "url": "https://example.test/failed"},
                        ]
                    )
                ],
                fetcher=fake_fetch,
            )

            classifications = {item["classification"] for item in result["sources"]}
            self.assertEqual(result["status"], "blocked")
            self.assertIn("timeout", classifications)
            self.assertIn("fetch_failed", classifications)

    def test_untrusted_and_duplicate_sources_are_recorded_without_fetching(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_agentic_update_discovery(
                workspace_root=Path(temp_dir),
                run_id="untrusted-duplicate-run",
                run_contract={"scope": "provider_metadata", "providers": ["qwen"], "allow_network": False},
                provider_sources=[
                    _provider_source(
                        [
                            {"source_id": "official-a", "url": "https://example.test/official"},
                            {"source_id": "official-duplicate", "url": "https://example.test/official"},
                            {
                                "source_id": "untrusted-a",
                                "url": "https://example.test/untrusted",
                                "trust_level": "untrusted",
                                "channel": "manual_seed",
                                "parser_strategy": "manual_review",
                            },
                        ]
                    )
                ],
                fixture_sources={"official-a": "official fixture"},
            )

            classifications = [item["classification"] for item in result["sources"]]
            self.assertEqual(classifications, ["ok", "duplicate", "untrusted_source"])
            self.assertEqual(result["summary"]["classifications"]["duplicate"], 1)
            self.assertEqual(result["summary"]["classifications"]["untrusted_source"], 1)
            pack_records = _read_jsonl(Path(result["artifact_paths"]["source_pack"]))
            untrusted = next(item for item in pack_records if item["classification"] == "untrusted_source")
            self.assertFalse(untrusted["promotable"])
            self.assertTrue(untrusted["requires_manual_review"])

    def test_source_limit_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_agentic_update_discovery(
                workspace_root=Path(temp_dir),
                run_id="limit-run",
                run_contract={"scope": "provider_metadata", "providers": ["qwen"], "allow_network": False},
                provider_sources=[
                    _provider_source(
                        [
                            {"source_id": "one", "url": "https://example.test/one"},
                            {"source_id": "two", "url": "https://example.test/two"},
                            {"source_id": "three", "url": "https://example.test/three"},
                        ]
                    )
                ],
                fixture_sources={"one": "one", "two": "two", "three": "three"},
                max_sources=2,
            )

            self.assertIn("source_limit_reached", result["warnings"])
            self.assertEqual(result["summary"]["total_sources"], 2)
            self.assertEqual(len(_read_jsonl(Path(result["artifact_paths"]["source_pack"]))), 2)

    def test_private_redirect_wrong_host_wrong_type_oversized_decompression_and_replay_sources_reject(self) -> None:
        def fake_fetch(url: str, timeout_sec: int, max_bytes: int) -> dict[str, object]:
            responses = {
                "https://official.example.test/redirect": {
                    "url": "https://official.example.test/canonical",
                    "status_code": 200,
                    "content_type": "text/html; charset=utf-8",
                    "body": "<html>redirected</html>",
                },
                "https://official.example.test/wrong-host": {
                    "url": "https://attacker.example.test/models",
                    "status_code": 200,
                    "content_type": "text/html; charset=utf-8",
                    "body": "<html>wrong host</html>",
                },
                "https://official.example.test/wrong-type": {
                    "url": "https://official.example.test/wrong-type",
                    "status_code": 200,
                    "content_type": "image/png",
                    "body": b"\x89PNG\r\n",
                },
                "https://official.example.test/oversized": {
                    "url": "https://official.example.test/oversized",
                    "status_code": 200,
                    "content_type": "text/plain; charset=utf-8",
                    "content_length": max_bytes + 50,
                    "body": ("x" * max_bytes).encode(),
                    "body_truncated": True,
                },
                "https://official.example.test/decompression": {
                    "url": "https://official.example.test/decompression",
                    "status_code": 200,
                    "content_type": "text/html; charset=utf-8",
                    "content_encoding": "gzip",
                    "body": "<html>gzip</html>",
                },
                "https://official.example.test/replay-a": {
                    "url": "https://official.example.test/replay-a",
                    "status_code": 200,
                    "content_type": "application/json",
                    "body": '{"models":["same"]}',
                },
                "https://official.example.test/replay-b": {
                    "url": "https://official.example.test/replay-b",
                    "status_code": 200,
                    "content_type": "application/json",
                    "body": '{"models":["same"]}',
                },
            }
            payload = dict(responses[url])
            payload.setdefault("content_length", len(payload["body"]) if isinstance(payload["body"], bytes) else len(str(payload["body"]).encode()))
            payload.setdefault("body_truncated", False)
            payload.setdefault("started_at", "2026-07-18T00:00:00+00:00")
            payload.setdefault("finished_at", "2026-07-18T00:00:01+00:00")
            payload.setdefault("duration_ms", 5)
            return payload

        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_agentic_update_discovery(
                workspace_root=Path(temp_dir),
                run_id="unsafe-boundary-run",
                run_contract={"scope": "provider_metadata", "providers": ["qwen"], "allow_network": True},
                provider_sources=[
                    _provider_source(
                        [
                            {"source_id": "private-source", "url": "http://127.0.0.1/private"},
                            {"source_id": "redirect-source", "url": "https://official.example.test/redirect"},
                            {"source_id": "wrong-host-source", "url": "https://official.example.test/wrong-host"},
                            {"source_id": "wrong-type-source", "url": "https://official.example.test/wrong-type"},
                            {"source_id": "oversized-source", "url": "https://official.example.test/oversized"},
                            {"source_id": "decompression-source", "url": "https://official.example.test/decompression"},
                            {"source_id": "replay-a-source", "url": "https://official.example.test/replay-a"},
                            {"source_id": "replay-b-source", "url": "https://official.example.test/replay-b"},
                        ]
                    )
                ],
                fetcher=fake_fetch,
                max_bytes_per_source=64,
            )

            self.assertEqual(result["status"], "partial")
            records = {item["source_id"]: item for item in _read_jsonl(Path(result["artifact_paths"]["source_pack"]))}
            self.assertEqual(records["private-source"]["classification"], "private_address_blocked")
            self.assertEqual(records["redirect-source"]["classification"], "redirect_blocked")
            self.assertEqual(records["wrong-host-source"]["classification"], "wrong_host_response")
            self.assertEqual(records["wrong-type-source"]["classification"], "wrong_content_type")
            self.assertEqual(records["oversized-source"]["classification"], "oversized_response")
            self.assertEqual(records["decompression-source"]["classification"], "decompression_blocked")
            self.assertEqual(records["replay-a-source"]["classification"], "ok")
            self.assertEqual(records["replay-b-source"]["classification"], "replayed_source")


def _provider_source(source_records: list[dict[str, object]]) -> dict[str, object]:
    normalized_records = []
    for index, record in enumerate(source_records):
        normalized_records.append(
            {
                "source_id": record.get("source_id") or f"source-{index + 1}",
                "url": record["url"],
                "source_type": record.get("source_type") or "models_catalog",
                "trust_level": record.get("trust_level") or "official",
                "channel": record.get("channel") or "stable_docs",
                "parser_strategy": record.get("parser_strategy") or "html_document",
                "stale_after_days": record.get("stale_after_days") or 7,
            }
        )
    return {
        "provider_id": "qwen",
        "display_name": "Qwen",
        "source_status": "official_docs",
        "source_type": "models_catalog",
        "trust_level": "official",
        "channel": "stable_docs",
        "parser_strategy": "html_document",
        "stale_after_days": 7,
        "source_records": normalized_records,
    }


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    unittest.main()
