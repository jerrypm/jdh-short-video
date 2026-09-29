#!/usr/bin/env python3
"""Isolated loopback-only Nano capability test. No app data or cloud calls."""
import argparse
import hmac
import json
import mimetypes
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]


def run(port: int) -> None:
    token = secrets.token_hex(32)
    origin = f"http://127.0.0.1:{port}"
    output = PROJECT / "docs" / "qa" / "nano-local-spike-browser.json"
    files = {
        "/": ROOT / "index.html",
        "/style.css": ROOT / "style.css",
        "/spike.js": ROOT / "spike.js",
        "/validation.mjs": ROOT / "validation.mjs",
        "/fixture.mp4": PROJECT / "docs" / "qa" / "macos-output.mp4",
    }
    lock = threading.Lock()
    bridge = {"last_seen": 0.0, "job": None}
    runtime = tempfile.TemporaryDirectory(prefix="jdh-nano-spike-")
    config = Path(runtime.name) / "connection.json"
    config.write_text(json.dumps({"origin": origin, "token": token}))
    config.chmod(0o600)

    def refresh_job():
        job = bridge["job"]
        if job and job["status"] in ("queued", "running"):
            if time.monotonic() > job["deadline"]:
                job.update(status="failed", error="request_timeout")
            elif time.monotonic() - bridge["last_seen"] > 6:
                job.update(status="failed", error="companion_disconnected")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def allowed(self):
            return self.headers.get("Host") == f"127.0.0.1:{port}" and (
                self.headers.get("Origin") in (None, origin)
            )

        def reply(self, status, body=b"", content_type="text/plain; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'self'; style-src 'self'; "
                             "connect-src 'self'; media-src 'self'; img-src 'self'; "
                             "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.allowed():
                return self.reply(403)
            if self.path in ("/bridge/poll", "/bridge/status"):
                if not hmac.compare_digest(self.headers.get("X-JDH-Spike-Token", ""), token):
                    return self.reply(403)
                with lock:
                    refresh_job()
                    if self.path == "/bridge/poll":
                        bridge["last_seen"] = time.monotonic()
                        job = bridge["job"]
                        payload = None
                        if job and job["status"] == "queued":
                            job["status"] = "running"
                            payload = {"id": job["id"], "action": job["action"]}
                        result = {"job": payload}
                    else:
                        result = {
                            "connected": time.monotonic() - bridge["last_seen"] <= 6,
                            "job": bridge["job"],
                        }
                    return self.reply(200, json.dumps(result).encode(), "application/json")
            path = files.get(self.path)
            if path is None or not path.is_file():
                return self.reply(404)
            body = path.read_bytes()
            if self.path == "/":
                body = body.replace(b"__SPIKE_TOKEN__", token.encode())
            mime = "text/javascript" if path.suffix in (".js", ".mjs") else mimetypes.guess_type(path.name)[0]
            self.reply(200, body, mime or "application/octet-stream")

        def do_POST(self):
            if (not self.allowed()
                    or not hmac.compare_digest(self.headers.get("X-JDH-Spike-Token", ""), token)):
                return self.reply(403)
            if self.path not in ("/report", "/bridge/enqueue", "/bridge/result"):
                return self.reply(404)
            if self.path != "/bridge/enqueue" and self.headers.get("Origin") != origin:
                return self.reply(403)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 131072:
                    return self.reply(413)
                result = json.loads(self.rfile.read(length))
                if self.path.startswith("/bridge/"):
                    if not isinstance(result, dict):
                        return self.reply(400)
                    with lock:
                        refresh_job()
                        if self.path == "/bridge/enqueue":
                            if result != {"action": "ideas_fixture"}:
                                return self.reply(400)
                            if time.monotonic() - bridge["last_seen"] > 6:
                                return self.reply(503, b"companion_disconnected")
                            previous = bridge["job"]
                            if previous and previous["status"] in ("queued", "running"):
                                return self.reply(409, b"busy")
                            job = {"id": str(uuid.uuid4()), "action": "ideas_fixture",
                                   "status": "queued", "deadline": time.monotonic() + 110}
                            bridge["job"] = job
                            return self.reply(202, json.dumps({"id": job["id"]}).encode(), "application/json")
                        job = bridge["job"]
                        if not job or result.get("id") != job["id"] or job["status"] != "running":
                            return self.reply(409)
                        if result.get("status") not in ("completed", "failed"):
                            return self.reply(400)
                        if result["status"] == "completed":
                            output_data = result.get("output")
                            ideas = output_data.get("ideas") if isinstance(output_data, dict) else None
                            if (not isinstance(output_data, dict) or set(output_data) != {"ideas"}
                                    or not isinstance(ideas, list) or len(ideas) != 3):
                                return self.reply(400)
                            titles = set()
                            for idea in ideas:
                                if not isinstance(idea, dict) or set(idea) != {"title", "hook"}:
                                    return self.reply(400)
                                for key, limit in (("title", 120), ("hook", 240)):
                                    value = idea[key]
                                    if not isinstance(value, str) or not value.strip() or len(value) > limit:
                                        return self.reply(400)
                                title = idea["title"].strip().casefold()
                                if title in titles:
                                    return self.reply(400)
                                titles.add(title)
                        job.update(status=result["status"], output=result.get("output"),
                                   error=result.get("error"), elapsed_ms=result.get("elapsed_ms"))
                        return self.reply(200, b'{"saved":true}', "application/json")
                if not isinstance(result, dict) or result.get("provider") != "chrome-gemini-nano":
                    return self.reply(400)
                result["recorded_at"] = datetime.now(timezone.utc).isoformat()
                output.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode="w", dir=output.parent, delete=False) as stream:
                    json.dump(result, stream, indent=2)
                    stream.write("\n")
                    temporary = stream.name
                os.replace(temporary, output)
            except (ValueError, OSError):
                return self.reply(400)
            self.reply(200, b'{"saved":true}', "application/json")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Nano local spike: {origin}", flush=True)
    print(f"Report: {output}", flush=True)
    print(f"Native client connection: {config}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        runtime.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8769)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port between 1024 and 65535.")
    run(args.port)
