from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sources = json.loads(Path(args.sources).read_text(encoding="utf-8"))
    fetched = []
    for provider in sources.get("providers", []):
        for url in provider.get("urls", []):
            fetched.append(fetch_status(provider.get("provider_id"), url))
    proposal = {
        "schema_version": "lcr-metadata-proposal-v1",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "sources": sources.get("providers", []),
        "fetch_status": fetched,
        "notes": [
            "This proposal is sanitized and contains no secrets.",
            "Apply seed models through the sidecar /api/router/metadata/import-seed endpoint.",
        ],
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_status(provider_id: str, url: str) -> dict:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "AstraBridge/metadata-curator"})
        with urllib.request.urlopen(request, timeout=12) as response:
            body = response.read(200_000)
            return {"provider_id": provider_id, "url": url, "ok": True, "status": response.status, "bytes": len(body)}
    except Exception as exc:  # noqa: BLE001
        return {"provider_id": provider_id, "url": url, "ok": False, "error": str(exc)[:300]}


if __name__ == "__main__":
    main()

