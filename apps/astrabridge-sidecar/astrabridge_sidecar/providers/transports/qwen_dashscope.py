from __future__ import annotations

from typing import Any

from .base import ResponsesTransport


QWEN_THINKING_ENABLED_EFFORTS = {"minimal", "low", "medium", "high", "xhigh", "max"}


class QwenResponsesTransport(ResponsesTransport):
    def supports_local_image_input(self) -> bool:
        return True

    def convert_messages(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        """Keep App Server text plus an adjacent local image in one user turn.

        The App Server emits attachments as top-level ``localImage`` entries
        after the corresponding ``text`` item. Qwen treats separate user
        messages as separate turns, so splitting those entries can make the
        image arrive without its output constraint. Preserve that user turn by
        combining only adjacent top-level user text and image items.
        """
        raw_input = payload.get("input")
        if not isinstance(raw_input, list):
            return super().convert_messages(payload)

        converted: list[dict[str, Any]] = []
        pending_user_content: list[dict[str, Any]] = []

        def flush_pending_user_content() -> None:
            if pending_user_content:
                converted.append(
                    {
                        "type": "message",
                        "role": "user",
                        "content": list(pending_user_content),
                    }
                )
                pending_user_content.clear()

        for item in raw_input:
            if isinstance(item, dict):
                item_type = str(item.get("type") or "")
                if item_type in {"text", "input_text"}:
                    text = str(item.get("text") or "")
                    if text:
                        pending_user_content.append({"type": "input_text", "text": text})
                    continue
                if item_type in {"localImage", "image"}:
                    pending_user_content.append(self._qwen_input_image_part(item))
                    continue
            flush_pending_user_content()
            converted.extend(self._convert_responses_input_item(item))

        flush_pending_user_content()
        return converted

    def _convert_responses_input_item(self, item: Any) -> list[dict[str, Any]]:
        if not isinstance(item, dict):
            return super()._convert_responses_input_item(item)
        item_type = str(item.get("type") or "")
        if item_type == "localImage":
            return [
                {
                    "type": "message",
                    "role": "user",
                    "content": [self._qwen_input_image_part(item)],
                }
            ]
        if item_type != "message" or not isinstance(item.get("content"), list):
            return super()._convert_responses_input_item(item)
        content: list[dict[str, Any]] = []
        changed = False
        for part in item["content"]:
            if not isinstance(part, dict):
                content.append(part)
                continue
            part_type = str(part.get("type") or "")
            if part_type == "localImage":
                content.append(self._qwen_input_image_part(part))
                changed = True
            elif part_type == "image":
                content.append(self._qwen_input_image_part(part))
                changed = True
            else:
                content.append(part)
        if not changed:
            return super()._convert_responses_input_item(item)
        return [{**item, "content": content}]

    def _qwen_input_image_part(self, item: dict[str, Any]) -> dict[str, Any]:
        raw_url = str(item.get("url") or item.get("image_url") or "").strip()
        if raw_url:
            image_url = raw_url
        else:
            image_url = self._local_image_data_url(str(item.get("path") or ""))
        part: dict[str, Any] = {"type": "input_image", "image_url": image_url}
        detail = str(item.get("detail") or "").strip()
        if detail:
            part["detail"] = detail
        return part

    def build_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        upstream_payload = super().build_request(payload)
        force_final = bool(payload.get("astrabridge_probe_force_final"))
        effort = self._resolved_reasoning_effort(payload)
        if force_final or effort == "off":
            upstream_payload["enable_thinking"] = False
        elif effort == "auto":
            upstream_payload.pop("enable_thinking", None)
        elif effort in QWEN_THINKING_ENABLED_EFFORTS:
            upstream_payload["enable_thinking"] = True
        upstream_payload.pop("reasoning", None)
        for key in ("top_p", "service_tier", "astrabridge_probe_force_final"):
            upstream_payload.pop(key, None)
        extra_defaults = self.profile.get("extra_body_defaults")
        if isinstance(extra_defaults, dict):
            for key, value in extra_defaults.items():
                upstream_payload.setdefault(str(key), value)
        return upstream_payload

    def describe(self) -> str:
        return "qwen_responses"
