from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


DEFAULT_APP_SERVER_COMMAND = [
    "app-server",
    "--listen",
    "stdio://",
    "--disable",
    "plugins",
    "--disable",
    "plugin_sharing",
    "--disable",
    "remote_plugin",
]


def app_server_command(*, listen: str = "stdio://", allow_plugins: bool = False) -> list[str]:
    command = ["app-server", "--listen", listen]
    if not allow_plugins:
        command.extend(["--disable", "plugins"])
    command.extend(["--disable", "plugin_sharing", "--disable", "remote_plugin"])
    return command


class JsonRpcError(RuntimeError):
    def __init__(self, message: str, code: int | None = None, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


@dataclass
class _PendingRequest:
    event: threading.Event = field(default_factory=threading.Event)
    result: Any | None = None
    error: Exception | None = None


class AppServerClient:
    def __init__(
        self,
        *,
        codex_executable: str | None = None,
        launch_command: list[str] | None = None,
        ws_url: str | None = None,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        allow_plugins: bool = False,
        on_notification: Callable[[str, Any], None] | None = None,
        on_server_request: Callable[[str, Any], Any] | None = None,
        on_stderr: Callable[[str], None] | None = None,
    ) -> None:
        self.codex_executable = codex_executable or shutil.which("codex") or "codex"
        self.launch_command = list(launch_command) if launch_command else None
        self.ws_url = ws_url
        self.env = env
        self.cwd = cwd
        self.allow_plugins = allow_plugins
        self.on_notification = on_notification
        self.on_server_request = on_server_request
        self.on_stderr = on_stderr
        self._process: subprocess.Popen[str] | None = None
        self._socket: socket.socket | None = None
        self._reader_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._write_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending: dict[int, _PendingRequest] = {}
        self._request_id = 0
        self._closed = threading.Event()
        self._disconnected = threading.Event()

    def start(self) -> None:
        if self._process and self._process.poll() is None:
            return
        self._closed.clear()
        self._disconnected.clear()
        launch_command = self.launch_command or [self.codex_executable, *app_server_command(allow_plugins=self.allow_plugins)]
        if self.ws_url:
            self._process = subprocess.Popen(
                launch_command,
                cwd=str(self.cwd) if self.cwd else None,
                env=self.env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            self._connect_websocket_with_retry()
            self._reader_thread = threading.Thread(target=self._websocket_reader_loop, name="codex-app-ws-reader", daemon=True)
        else:
            self._process = subprocess.Popen(
                launch_command,
                cwd=str(self.cwd) if self.cwd else None,
                env=self.env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            self._reader_thread = threading.Thread(target=self._reader_loop, name="codex-app-reader", daemon=True)
        self._stderr_thread = threading.Thread(target=self._stderr_loop, name="codex-app-stderr", daemon=True)
        self._reader_thread.start()
        self._stderr_thread.start()
        self.request(
            "initialize",
            {
                "clientInfo": {"name": "astrabridge-desktop", "version": "0.1.0"},
                "capabilities": {"experimentalApi": True, "requestAttestation": False},
            },
        )
        self.notify("initialized")

    def close(self) -> None:
        self._closed.set()
        self._disconnected.set()
        sock = self._socket
        self._socket = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            process.kill()
        except OSError:
            pass
        self._fail_all_pending(RuntimeError("codex_app_server_closed"))

    def is_running(self) -> bool:
        process_running = self._process is not None and self._process.poll() is None
        if self.ws_url:
            return self._socket is not None and not self._disconnected.is_set() and (process_running or self._process is not None)
        return process_running and not self._disconnected.is_set()

    def request(self, method: str, params: Any | None = None, timeout: float = 120.0) -> Any:
        request_id = self._next_request_id()
        pending = _PendingRequest()
        with self._pending_lock:
            self._pending[request_id] = pending
        self._send({"id": request_id, "method": method, "params": params})
        if not pending.event.wait(timeout):
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise TimeoutError(f"Timed out waiting for app-server response: {method}")
        if pending.error is not None:
            raise pending.error
        return pending.result

    def notify(self, method: str, params: Any | None = None) -> None:
        self._send({"method": method, "params": params})

    def _next_request_id(self) -> int:
        with self._pending_lock:
            self._request_id += 1
            return self._request_id

    def _send(self, payload: dict[str, Any]) -> None:
        process = self._process
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if self.ws_url:
            self._websocket_send_text(line)
            return
        if process is None or process.stdin is None:
            raise RuntimeError("codex_app_server_not_running")
        with self._write_lock:
            try:
                process.stdin.write(line + "\n")
                process.stdin.flush()
            except Exception as exc:  # noqa: BLE001
                self._disconnected.set()
                self._emit_notification("runtime/write_failed", {"error": str(exc), "method": payload.get("method")})
                raise

    def _reader_loop(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        reader_error: str | None = None
        try:
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError as exc:
                    self._emit_notification("error", {"message": "Invalid JSON from app-server", "raw": line, "detail": str(exc)})
                    continue
                self._handle_message(message)
        except Exception as exc:  # noqa: BLE001
            reader_error = str(exc)
            self._emit_notification("runtime/reader_error", {"error": reader_error, "transport": "stdio"})
        finally:
            self._disconnected.set()
            self._emit_notification(
                "runtime/disconnected",
                {
                    "exit_code": process.poll(),
                    "closed": self._closed.is_set(),
                    "pid": getattr(process, "pid", None),
                    "reader_error": reader_error,
                },
            )
            self._fail_all_pending(RuntimeError("codex_app_server_disconnected"))

    def _websocket_reader_loop(self) -> None:
        process = self._process
        reader_error: str | None = None
        try:
            while not self._closed.is_set():
                message = self._websocket_recv_text()
                if message is None:
                    break
                for line in message.splitlines():
                    if not line.strip():
                        continue
                    try:
                        parsed = json.loads(line)
                    except json.JSONDecodeError as exc:
                        self._emit_notification("error", {"message": "Invalid JSON from app-server websocket", "raw": line, "detail": str(exc)})
                        continue
                    self._handle_message(parsed)
        except Exception as exc:  # noqa: BLE001
            reader_error = str(exc)
            self._emit_notification("runtime/reader_error", {"error": reader_error, "transport": "websocket"})
        finally:
            self._disconnected.set()
            self._emit_notification(
                "runtime/disconnected",
                {
                    "exit_code": process.poll() if process else None,
                    "closed": self._closed.is_set(),
                    "pid": getattr(process, "pid", None),
                    "transport": "websocket",
                    "reader_error": reader_error,
                },
            )
            self._fail_all_pending(RuntimeError("codex_app_server_disconnected"))

    def _stderr_loop(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        for raw_line in process.stderr:
            line = raw_line.rstrip()
            if not line:
                continue
            if self.on_stderr is not None:
                self.on_stderr(line)

    def _handle_message(self, message: dict[str, Any]) -> None:
        if "method" in message and "id" in message and "result" not in message and "error" not in message:
            self._emit_notification("runtime/server_request", {"method": str(message.get("method") or ""), "id": message.get("id")})
            threading.Thread(target=self._resolve_server_request, args=(message,), daemon=True).start()
            return
        if "id" in message and ("result" in message or "error" in message):
            self._resolve_response(message)
            return
        if "method" in message:
            self._emit_notification(str(message["method"]), message.get("params"))

    def _resolve_server_request(self, message: dict[str, Any]) -> None:
        request_id = int(message["id"])
        method = str(message["method"])
        params = message.get("params")
        try:
            if self.on_server_request is None:
                raise JsonRpcError(f"Unhandled server request: {method}")
            result = self.on_server_request(method, params)
            self._send({"id": request_id, "result": result})
        except Exception as exc:  # noqa: BLE001
            error = {"code": getattr(exc, "code", -32000), "message": str(exc)}
            data = getattr(exc, "data", None)
            if data is not None:
                error["data"] = data
            self._emit_notification("runtime/server_request_failed", {"method": method, "error": str(exc)})
            self._send({"id": request_id, "error": error})

    def _resolve_response(self, message: dict[str, Any]) -> None:
        request_id = int(message["id"])
        with self._pending_lock:
            pending = self._pending.pop(request_id, None)
        if pending is None:
            return
        if "error" in message:
            error = message["error"] or {}
            pending.error = JsonRpcError(str(error.get("message") or "JSON-RPC error"), code=error.get("code"), data=error.get("data"))
        else:
            pending.result = message.get("result")
        pending.event.set()

    def _emit_notification(self, method: str, params: Any) -> None:
        if self.on_notification is not None:
            try:
                self.on_notification(method, params)
            except Exception:
                # Notification handlers update UI caches and project-side state. They
                # must never bring down the app-server transport reader.
                pass

    def _fail_all_pending(self, error: Exception) -> None:
        with self._pending_lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for item in pending:
            item.error = error
            item.event.set()

    def _connect_websocket_with_retry(self) -> None:
        deadline = time.time() + 15.0
        last_error: Exception | None = None
        while time.time() < deadline:
            process = self._process
            if process is not None and process.poll() is not None:
                break
            try:
                self._connect_websocket()
                return
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                time.sleep(0.2)
        raise RuntimeError(f"codex_app_server_websocket_connect_failed: {last_error}")

    def _connect_websocket(self) -> None:
        if not self.ws_url:
            raise RuntimeError("websocket URL is not configured")
        parsed = urllib.parse.urlparse(self.ws_url)
        if parsed.scheme != "ws":
            raise RuntimeError(f"Unsupported app-server websocket URL: {self.ws_url}")
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port
        if port is None:
            raise RuntimeError(f"Websocket URL must include a port: {self.ws_url}")
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
        sock = socket.create_connection((host, port), timeout=2.0)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if len(response) > 65536:
                raise RuntimeError("Websocket handshake response is too large.")
        header = response.decode("iso-8859-1", errors="replace")
        if " 101 " not in header.split("\r\n", 1)[0]:
            raise RuntimeError(f"Websocket handshake failed: {header.splitlines()[0] if header else 'empty response'}")
        expected_accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()).decode("ascii")
        if f"Sec-WebSocket-Accept: {expected_accept}".lower() not in header.lower():
            raise RuntimeError("Websocket handshake returned an invalid accept key.")
        sock.settimeout(None)
        self._socket = sock

    def _websocket_send_text(self, text: str) -> None:
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length <= 0xFFFF:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        with self._write_lock:
            sock = self._socket
            if sock is None:
                raise RuntimeError("codex_app_server_not_running")
            try:
                sock.sendall(bytes(header) + masked)
            except Exception as exc:  # noqa: BLE001
                self._disconnected.set()
                self._emit_notification("runtime/write_failed", {"error": str(exc), "transport": "websocket"})
                raise

    def _websocket_recv_text(self) -> str | None:
        fragments: list[bytes] = []
        expecting_continuation = False
        while True:
            frame = self._websocket_recv_frame()
            if frame is None:
                return None
            fin, opcode, payload = frame
            if opcode == 0x8:
                close_code = struct.unpack("!H", payload[:2])[0] if len(payload) >= 2 else None
                close_reason = payload[2:].decode("utf-8", errors="replace") if len(payload) > 2 else ""
                self._emit_notification("runtime/websocket_close", {"code": close_code, "reason": close_reason})
                return None
            if opcode == 0x9:
                self._websocket_send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            if opcode == 0x1:
                fragments = [payload]
                expecting_continuation = not fin
                if fin:
                    return payload.decode("utf-8", errors="replace")
                continue
            if opcode == 0x0 and expecting_continuation:
                fragments.append(payload)
                if fin:
                    return b"".join(fragments).decode("utf-8", errors="replace")
                continue
            self._emit_notification("runtime/websocket_ignored_frame", {"opcode": opcode, "fin": fin, "length": len(payload)})

    def _websocket_recv_frame(self) -> tuple[bool, int, bytes] | None:
        header = self._socket_recv_exact(2)
        if header is None:
            return None
        first, second = header[0], header[1]
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            extended = self._socket_recv_exact(2)
            if extended is None:
                return None
            length = struct.unpack("!H", extended)[0]
        elif length == 127:
            extended = self._socket_recv_exact(8)
            if extended is None:
                return None
            length = struct.unpack("!Q", extended)[0]
        mask = self._socket_recv_exact(4) if masked else b""
        payload = self._socket_recv_exact(length) if length else b""
        if payload is None:
            return None
        if masked and mask:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return fin, opcode, payload

    def _websocket_send_frame(self, opcode: int, payload: bytes) -> None:
        header = bytearray([0x80 | (opcode & 0x0F)])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length <= 0xFFFF:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        sock = self._socket
        if sock is not None:
            sock.sendall(bytes(header) + masked)

    def _socket_recv_exact(self, length: int) -> bytes | None:
        sock = self._socket
        if sock is None:
            return None
        chunks = bytearray()
        while len(chunks) < length:
            chunk = sock.recv(length - len(chunks))
            if not chunk:
                return None
            chunks.extend(chunk)
        return bytes(chunks)

