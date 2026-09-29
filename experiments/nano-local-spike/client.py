#!/usr/bin/env python3
"""Native backend-side fixture client; only talks to the isolated loopback broker."""
import argparse
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse

parser = argparse.ArgumentParser()
parser.add_argument("connection", type=Path)
parser.add_argument("--status-only", action="store_true")
parser.add_argument("--output", type=Path)
args = parser.parse_args()
config = json.loads(args.connection.read_text())
url = urlparse(config["origin"])
if url.scheme != "http" or url.hostname != "127.0.0.1" or url.username or url.password:
    parser.error("Only a local 127.0.0.1 server is allowed.")


def request(path, body=None):
    req = Request(config["origin"] + path,
                  headers={"Content-Type": "application/json", "X-JDH-Spike-Token": config["token"]},
                  data=json.dumps(body).encode() if body is not None else None)
    try:
        with urlopen(req, timeout=5) as response:
            return json.load(response)
    except HTTPError as error:
        return {"http_status": error.code, "error": error.read().decode()[:200]}


started = time.monotonic()
if args.status_only:
    result = request("/bridge/status")
else:
    queued = request("/bridge/enqueue", {"action": "ideas_fixture"})
    if "id" not in queued:
        result = queued
    else:
        print(json.dumps({"queued_request_id": queued["id"]}), flush=True)
        while time.monotonic() - started < 115:
            state = request("/bridge/status")
            job = state.get("job")
            if job and job.get("id") == queued["id"] and job["status"] in ("completed", "failed"):
                result = state
                break
            time.sleep(1)
        else:
            result = {"error": "client_timeout"}
result["client_elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
if args.output:
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
