#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from datetime import datetime, timezone
from typing import Any


def _json_line(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\n"


def _send_json_line(sock: socket.socket, payload: dict[str, Any]) -> None:
    sock.sendall(_json_line(payload))


def emit_final(data: dict[str, Any]) -> None:
    """Emit the final LAT result on Windows TCP or Unix fd 3.

    LAT Agent reads final results from LAT_RESULT_CHANNEL=tcp on Windows and
    from file descriptor 3 on Unix/Linux. The stdout fallback keeps local
    testing friendly when running this script outside LAT.
    """
    if os.getenv("LAT_RESULT_CHANNEL") == "tcp":
        host = os.environ["LAT_RESULT_HOST"]
        port = int(os.environ["LAT_RESULT_PORT"])
        token = os.environ["LAT_RESULT_TOKEN"]

        with socket.create_connection((host, port), timeout=10) as sock:
            _send_json_line(sock, {"token": token})
            _send_json_line(sock, {"type": "final", "data": data})
            try:
                sock.shutdown(socket.SHUT_WR)
            except OSError:
                pass
        return

    try:
        os.write(3, json.dumps(data, ensure_ascii=False).encode("utf-8"))
    except OSError:
        print(json.dumps(data, ensure_ascii=False), flush=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_action(action: str, message: str) -> dict[str, Any]:
    if action == "health":
        return {
            "status": "ok",
            "plugin_id": "lat-plugin-template",
            "timestamp": utc_now(),
        }

    if action == "echo":
        return {
            "status": "ok",
            "message": message,
            "length": len(message),
            "timestamp": utc_now(),
        }

    raise ValueError(f"Unsupported action: {action}")


def main() -> int:
    parser = argparse.ArgumentParser(description="LAT plugin template entrypoint")
    parser.add_argument("--action", required=True)
    parser.add_argument("--message", default="")
    args = parser.parse_args()

    print(f"[lat-plugin-template] action={args.action}", flush=True)
    result = run_action(args.action, args.message)
    emit_final(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[lat-plugin-template] ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
