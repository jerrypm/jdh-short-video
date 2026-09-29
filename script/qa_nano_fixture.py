"""Explicit fake companion for UI QA. Never use as evidence of Nano inference.

Requires the native --isolated-qa app. Refuses normal project storage.
Only returns labelled fixtures; does not send source text to any model.
"""

import argparse
import json
from pathlib import Path
import time
from urllib.parse import urlparse
from uuid import uuid4

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("origin")
    parser.add_argument("--delay", type=float, default=12)
    parser.add_argument("--seconds", type=int, default=600)
    args = parser.parse_args()
    url = urlparse(args.origin)
    if url.scheme != "http" or url.hostname != "127.0.0.1" or url.path or not url.port:
        raise SystemExit("Use the isolated QA app's loopback origin.")
    with (
        httpx.Client(base_url=args.origin, timeout=8, trust_env=False) as editor,
        httpx.Client(base_url=args.origin, timeout=8, trust_env=False) as companion,
    ):
        editor.headers["X-JDH-CSRF"] = editor.get("/api/session").json()["csrf"]
        capability = editor.get("/api/capabilities").json()
        root = Path(capability["storage"])
        if root.name != "Projects" or not root.parent.name.startswith(
            "JDHShortsStudio-QA-"
        ):
            raise SystemExit("Refusing to attach fixture to non-QA data.")
        doc = str(uuid4())
        companion.headers["Origin"] = args.origin
        code = editor.post("/api/ai/pair", json={}).json()["code"]
        paired = companion.post(
            "/nano/api/pair", json={"code": code, "document_id": doc}
        )
        paired.raise_for_status()
        companion.headers["X-JDH-Nano"] = paired.json()["token"]
        print(json.dumps({"fixture": True, "qa_storage": str(root)}), flush=True)
        active = None
        until = time.monotonic() + args.seconds
        try:
            while time.monotonic() < until:
                response = companion.post(
                    "/nano/api/poll",
                    json={
                        "document_id": doc,
                        "english": "available",
                        "indonesian": "unavailable",
                        "accept_job": active is None,
                        "wait": True,
                        "running_id": active["id"] if active else None,
                    },
                )
                if response.status_code == 401:
                    print(json.dumps({"stopped": "QA pairing revoked"}), flush=True)
                    break
                response.raise_for_status()
                reply = response.json()
                if active and reply["active_id"] != active["id"]:
                    print(json.dumps({"cancelled": active["id"]}), flush=True)
                    active = None
                if reply["job"]:
                    active = reply["job"]
                    active["ready_at"] = time.monotonic() + args.delay
                    print(
                        json.dumps(
                            {"received": active["id"], "operation": active["operation"]}
                        ),
                        flush=True,
                    )
                if active and time.monotonic() >= active["ready_at"]:
                    suggestions = ["QA FIXTURE: One idea becomes one short."]
                    if active["operation"] == "hooks":
                        suggestions += [
                            "QA FIXTURE: Build a simple counter.",
                            "QA FIXTURE: Show one small improvement.",
                        ]
                    output = {"suggestions": suggestions}
                    if active["operation"] == "ideas":
                        context = json.loads(active["input"])
                        sources = [
                            r["project_id"] for r in context["history"]["references"]
                        ][:1]
                        output = {
                            "ideas": [
                                {
                                    "category": category,
                                    "title": "QA FIXTURE — " + category,
                                    "hook": "Show a reset button: " + category + ".",
                                    "concept": "Fixture concept for local UI QA, not model output.",
                                    "reason": "Tests selected source transport.",
                                    "difference": "Adds a reset demonstration.",
                                    "estimated_seconds": 30,
                                    "media_needs": ["New counter screenshot"],
                                    "source_project_ids": sources,
                                }
                                for category in ["series", "new_angle", "experiment"]
                            ]
                        }
                    if active["operation"] == "storyboard":
                        context = json.loads(active["input"])
                        sources = [r["project_id"] for r in context["references"]][:1]
                        output = {
                            "storyboard": {
                                "hook": "QA FIXTURE: Show reset.",
                                "scenes": [
                                    {
                                        "name": "QA FIXTURE " + str(i + 1),
                                        "narration": text,
                                        "caption": "Reset counter"
                                        if i == 0
                                        else "Try it",
                                        "estimated_frames": 150,
                                        "visual_need": "New screenshot of the counter",
                                        "media_id": None,
                                        "media_status": "missing",
                                        "audio_id": None,
                                        "effect": "static",
                                        "motion_intent": "Center the button.",
                                        "source_project_ids": sources,
                                    }
                                    for i, text in enumerate(
                                        [
                                            "QA FIXTURE: Show reset. Keep one idea clear.",
                                            "QA FIXTURE: Tap reset and show the result.",
                                        ]
                                    )
                                ],
                            }
                        }
                    result = companion.post(
                        "/nano/api/result",
                        json={
                            "document_id": doc,
                            "id": active["id"],
                            "status": "completed",
                            **output,
                        },
                    )
                    print(
                        json.dumps(
                            {
                                "returned": active["id"],
                                "http_status": result.status_code,
                            }
                        ),
                        flush=True,
                    )
                    active = None
        finally:
            try:
                companion.post("/nano/api/disconnect", json={})
            except httpx.HTTPError:
                pass


if __name__ == "__main__":
    main()
