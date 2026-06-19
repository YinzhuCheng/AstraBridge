from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sidecar", default="http://127.0.0.1:8790")
    parser.add_argument("--admin-token", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-cases", type=int, default=96)
    args = parser.parse_args()
    payload = {"max_cases": args.max_cases}
    request = urllib.request.Request(
        f"{args.sidecar.rstrip('/')}/api/router/models/test-matrix",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Admin-Token": args.admin_token},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        result = json.loads(response.read().decode("utf-8"))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

