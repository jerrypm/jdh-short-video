"""Packaged research workflow in disposable storage; fixture Nano transport only."""

import argparse
from datetime import date
import json
from pathlib import Path
import tempfile
from uuid import uuid4
from verify_content_memory_runtime import runtime, call, ROOT


def main(app, report):
    checks = []
    resources = app.resolve() / "Contents/Resources"
    with tempfile.TemporaryDirectory(prefix="jdh-research-runtime-") as temporary:
        directory = Path(temporary)
        with runtime(resources, directory) as client:
            project = call(
                client,
                "POST",
                "/projects",
                json={
                    "name": "QA research fixture",
                    "language": "en",
                    "script": "Do not change this project.",
                },
            )
            source = {
                "title": "QA source, not research",
                "url": "https://example.com/reference",
                "text": "A counter example illustrates local state changes. This is disposable test content, not an article or Nano output.",
                "published_on": "",
                "accessed_on": date.today().isoformat(),
                "kind": "summary",
                "included": True,
                "conflict_with": "",
                "caution": "Fixture only",
            }
            assert (
                client.post(
                    "/api/research/fetch", json={"url": "https://127.0.0.1/private"}
                ).status_code
                == 422
            )
            assert call(client, "GET", "/research")["sources"] == []
            assert (
                client.post(
                    "/api/research/sources",
                    json={"revision": 0, "source": source, "reviewed": False},
                ).status_code
                == 422
            )
            library = call(
                client,
                "POST",
                "/research/sources",
                json={"revision": 0, "source": source, "reviewed": True},
            )
            sid = library["sources"][0]["id"]
            assert (
                library["eligible_count"] == 1
                and library["sources"][0]["publication_unknown"]
            )
            assert (
                client.post(
                    "/api/research/sources",
                    json={
                        "revision": 1,
                        "source": {**source, "url": source["url"] + "#duplicate"},
                        "reviewed": True,
                    },
                ).status_code
                == 422
            )
            checks += [
                "private URL rejected before connection",
                "fetch rejection does not write",
                "review required",
                "manual source and unknown date persisted",
                "canonical URL duplicate rejected",
            ]

            def status():
                return call(
                    client, "GET", "/ideas/status", params={"timezone": "Asia/Jakarta"}
                )

            state = status()
            state = call(
                client,
                "PUT",
                "/ideas/preferences",
                json={
                    "timezone": "Asia/Jakarta",
                    "revision": state["settings_revision"],
                    "preferences": {**state["preferences"], "source_mode": "research"},
                },
            )
            assert not state["auto_due"] and state["research_source_count"] == 1
            doc = str(uuid4())
            code = call(client, "POST", "/ai/pair", json={})["code"]
            headers = {"Origin": str(client.base_url).rstrip("/")}
            response = client.post(
                "/nano/api/pair",
                headers=headers,
                json={"code": code, "document_id": doc},
            )
            response.raise_for_status()
            headers["X-JDH-Nano"] = response.json()["token"]

            def poll():
                response = client.post(
                    "/nano/api/poll",
                    headers=headers,
                    json={
                        "document_id": doc,
                        "english": "available",
                        "indonesian": "unavailable",
                    },
                )
                response.raise_for_status()
                return response.json()

            poll()
            automatic = call(
                client,
                "POST",
                "/ideas/generate",
                json={
                    "id": str(uuid4()),
                    "timezone": "Asia/Jakarta",
                    "automatic": True,
                },
            )
            assert automatic["active_id"] is None
            rid = str(uuid4())
            assert (
                call(
                    client,
                    "POST",
                    "/ideas/generate",
                    json={"id": rid, "timezone": "Asia/Jakarta", "automatic": False},
                )["active_id"]
                == rid
            )
            job = poll()["job"]
            context = json.loads(job["input"])
            assert (
                context["history"]["references"] == []
                and context["performance"]["rows"] == []
            )
            assert (
                context["research"]["sources"][0]["id"] == sid
                and len(job["input"]) < 12000
            )
            cards = [
                {
                    "category": category,
                    "title": f"QA fixture {category}",
                    "hook": f"Fixture hook {category}.",
                    "concept": "A proposed example, not inference.",
                    "reason": "Based on the supplied fixture note.",
                    "difference": "A different example.",
                    "estimated_seconds": 30,
                    "media_needs": ["New example recording"],
                    "source_project_ids": [],
                    "performance_ids": [],
                    "research_claims": [
                        {
                            "claim": "The supplied note describes a state example.",
                            "source_id": sid,
                            "quote": source["text"][:48],
                        }
                    ],
                }
                for category in ["series", "new_angle", "experiment"]
            ]
            response = client.post(
                "/nano/api/result",
                headers=headers,
                json={
                    "document_id": doc,
                    "id": rid,
                    "status": "completed",
                    "ideas": cards,
                },
            )
            response.raise_for_status()
            state = status()
            assert (
                state["batch"]["source_mode"] == "research"
                and state["research_evidence"][sid]["url"] == source["url"]
            )
            card = state["batch"]["cards"][0]
            call(
                client,
                "PUT",
                f"/ideas/cards/{card['id']}/feedback",
                json={
                    "timezone": "Asia/Jakarta",
                    "verdict": "saved",
                    "reason": "Keep QA fixture",
                },
            )
            checks += [
                "research mode never auto-generates",
                "bounded local broker input without history/performance",
                "citation accepted by packaged broker",
                "source metadata attached to card",
                "reviewed card saved",
            ]
            changed = call(
                client,
                "POST",
                "/research/sources",
                json={
                    "revision": 1,
                    "id": sid,
                    "source": {**source, "included": False},
                    "reviewed": True,
                },
            )
            state = status()
            assert state["batch"] is None and state["feedback"][0]["research_stale"]
            assert state["research_evidence"][sid]["status"] == "excluded"
            assert call(client, "GET", f"/projects/{project['id']}") == project
            checks += [
                "source exclusion invalidates cached research",
                "saved card remains marked stale",
                "project manifest unchanged",
            ]
        with runtime(resources, directory) as client:
            assert call(client, "GET", "/research") == changed
            state = call(
                client, "GET", "/ideas/status", params={"timezone": "Asia/Jakarta"}
            )
            assert (
                state["preferences"]["source_mode"] == "research"
                and state["feedback"][0]["research_stale"]
            )
            assert state["active_id"] is None and not state["auto_due"]
            checks += [
                "real process restart preserves sources",
                "mode and stale feedback survive restart without auto-generation",
            ]
    result = {
        "checks": checks,
        "passed": len(checks),
        "app": str(app),
        "nano": "Fixture companion transport only; no real model inference claimed",
        "data": "Disposable temporary directory removed",
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, default=ROOT / "dist/JDH Shorts Studio.app")
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "dist/JDH-Shorts-Studio-0.2.11-research-check.json",
    )
    args = parser.parse_args()
    main(args.app, args.report)
