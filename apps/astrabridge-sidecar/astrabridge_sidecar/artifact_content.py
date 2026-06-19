from __future__ import annotations

import base64
import binascii
from typing import Any


def decode_artifact_content(item: dict[str, Any], label: str) -> str:
    has_text = "content" in item and item.get("content") is not None
    has_base64 = "content_base64" in item and item.get("content_base64") is not None
    allow_empty = item.get("allow_empty_content") is True
    if has_text and has_base64:
        raise ValueError(f"{label} must use either content or content_base64, not both.")
    if not has_base64:
        content = str(item.get("content") or "")
        if not content and not allow_empty:
            raise ValueError(f"{label} content must not be empty.")
        return content

    encoded = item.get("content_base64")
    if not isinstance(encoded, str):
        raise ValueError(f"{label} content_base64 must be a base64 string.")
    if not encoded and not allow_empty:
        raise ValueError(f"{label} content_base64 must not be empty.")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise ValueError(f"{label} content_base64 is not valid base64.") from exc
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} content_base64 must decode as UTF-8 text.") from exc
    if not content and not allow_empty:
        raise ValueError(f"{label} content must not be empty.")
    return content

