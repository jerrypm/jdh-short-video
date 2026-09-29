"""Task 10 packaged-sidecar QA using disposable measurements and fake Nano transport."""

import argparse
import csv
import io
import json
from pathlib import Path
import tempfile
from uuid import uuid4
from verify_content_memory_runtime import runtime, call, ROOT


def main(app, report):
    checks = []
    resources = app.resolve() / "Contents/Resources"
    with tempfile.TemporaryDirectory(prefix="jdh-performance-runtime-") as temporary:
        directory = Path(temporary)
        with runtime(resources, directory) as client:
            project = call(
                client,
                "POST",
                "/projects",
                json={
                    "name": "Performance runtime lesson",
                    "language": "en",
                    "script": "Explain one small SwiftUI example.",
                },
            )
            pid = project["id"]
            catalog = call(client, "GET", "/memory")["catalog"]
            call(
                client,
                "POST",
                "/memory/references",
                json={"revision": catalog["revision"], "project_ids": [pid]},
            )
            row = {
                "project_id": pid,
                "video_id": "qaVideo0001",
                "published_on": "2024-01-01",
                "period_start": "2024-01-01",
                "period_end": "2024-01-07",
                "report_timezone": "America/Los_Angeles",
                "captured_at": "2024-01-09T00:00:00+00:00",
                "definition": "youtube_engaged_views_v1",
                "definition_note": "",
                "source": "Runtime fixture only",
                "engaged_views": 0,
                "average_view_duration_seconds": 20.5,
                "average_view_percentage": 110.0,
                "likes": None,
                "comments": 0,
                "shares": 1,
            }
            text = io.StringIO()
            writer = csv.DictWriter(text, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
            rows = call(
                client, "POST", "/performance/parse", json={"csv": text.getvalue()}
            )["rows"]
            assert rows[0]["likes"] is None and rows[0]["engaged_views"] == 0
            checks.append("CSV null/zero and >100 percent preserved")

            def preview(values, revision, replace=False):
                return call(
                    client,
                    "POST",
                    "/performance/preview",
                    json={
                        "rows": values,
                        "revision": revision,
                        "origin": "csv",
                        "replace_conflicts": replace,
                    },
                )

            def apply(review):
                return call(
                    client,
                    "POST",
                    "/performance/apply",
                    json={"review_id": review["review_id"], "reviewed": True},
                )

            reviewed = preview(rows, 0)
            assert call(client, "GET", "/performance")["records"] == []
            saved = apply(reviewed)
            assert apply(reviewed) == saved
            rid = saved["records"][0]["id"]
            duplicate = preview(rows, 1)
            assert (
                duplicate["actions"][0]["action"] == "duplicate"
                and apply(duplicate)["revision"] == 1
            )
            checks += [
                "preview does not write",
                "reviewed CSV apply",
                "receipt retry idempotent",
                "duplicate import skipped",
            ]
            changed = [{**row, "engaged_views": 500}]
            conflict = preview(changed, 1)
            assert not conflict["can_apply"]
            assert (
                client.post(
                    "/api/performance/apply",
                    json={"review_id": conflict["review_id"], "reviewed": True},
                ).status_code
                == 422
            )
            replacement = apply(preview(changed, 1, True))
            assert replacement["records"][0]["engaged_views"] == 500
            assert replacement["cohorts"][0]["medians"]["engaged_views"] is None
            checks += [
                "conflicting snapshot rejected",
                "explicit correction applied",
                "small sample has no summary median",
            ]
            # Fake transport solely verifies prompt/evidence plumbing in the packaged Python runtime.
            doc = str(uuid4())
            code = call(client, "POST", "/ai/pair", json={})["code"]
            headers = {"Origin": str(client.base_url).rstrip("/")}
            paired = client.post(
                "/nano/api/pair",
                headers=headers,
                json={"code": code, "document_id": doc},
            )
            paired.raise_for_status()
            headers["X-JDH-Nano"] = paired.json()["token"]

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
            request_id = str(uuid4())
            generated = call(
                client,
                "POST",
                "/ideas/generate",
                json={"id": request_id, "timezone": "Asia/Jakarta", "automatic": False},
            )
            assert generated["active_id"] == request_id
            job = poll()["job"]
            context = json.loads(job["input"])
            assert context["performance"]["rows"][0]["engaged_views"] == 500
            cards = [
                {
                    "category": category,
                    "title": f"QA FIXTURE {category}",
                    "hook": f"Fixture {category} example.",
                    "concept": "Transport fixture, not inference.",
                    "reason": "500 engaged views in January 1–7 is an observation; test a follow-up, not a causal claim.",
                    "difference": "A different example.",
                    "estimated_seconds": 30,
                    "media_needs": ["New example"],
                    "source_project_ids": [pid],
                    "performance_ids": [rid] if index == 0 else [],
                }
                for index, category in enumerate(["series", "new_angle", "experiment"])
            ]
            response = client.post(
                "/nano/api/result",
                headers=headers,
                json={
                    "document_id": doc,
                    "id": request_id,
                    "status": "completed",
                    "ideas": cards,
                },
            )
            response.raise_for_status()
            status = call(
                client, "GET", "/ideas/status", params={"timezone": "Asia/Jakarta"}
            )
            assert status["performance_evidence"][rid]["engaged_views"] == 500
            assert status["batch"]["cards"][2]["category"] == "experiment"
            card_id = status["batch"]["cards"][0]["id"]
            call(
                client,
                "PUT",
                f"/ideas/cards/{card_id}/feedback",
                json={
                    "timezone": "Asia/Jakarta",
                    "verdict": "saved",
                    "reason": "Keep fixture",
                },
            )
            excluded = call(
                client,
                "PUT",
                f"/performance/{rid}/inclusion",
                json={"revision": 2, "included": False, "reason": "Fixture anomaly"},
            )
            assert excluded["latest_ids"] == [] and excluded["cohorts"] == []
            status = call(
                client, "GET", "/ideas/status", params={"timezone": "Asia/Jakarta"}
            )
            assert (
                status["batch"] is None and status["feedback"][0]["performance_stale"]
            )
            assert status["performance_evidence"] == {}
            assert call(client, "GET", f"/projects/{pid}") == project
            checks += [
                "bounded evidence in local broker input",
                "fixture result accepted with cited evidence",
                "experiment retained",
                "video anomaly excluded",
                "saved idea marked stale",
                "stale evidence removed",
                "project manifest unchanged",
            ]
            pending = preview([{**row, "video_id": "qaVideo0002"}], 3)
        with runtime(resources, directory) as client:
            restored = call(client, "GET", "/performance")
            assert restored == excluded
            assert (
                client.post(
                    "/api/performance/apply",
                    json={"review_id": pending["review_id"], "reviewed": True},
                ).status_code
                == 409
            )
            assert call(
                client, "GET", "/ideas/status", params={"timezone": "Asia/Jakarta"}
            )["feedback"][0]["performance_stale"]
            checks += [
                "real sidecar restart preserves snapshots/exclusion",
                "ephemeral review expires on restart",
                "saved stale marker survives restart",
            ]
    result = {
        "checks": checks,
        "passed": len(checks),
        "app": str(app),
        "nano": "Fake companion transport only; real integrated inference remains unverified",
        "data": "Disposable temporary directory removed after verification",
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
        default=ROOT / "dist/JDH-Shorts-Studio-0.2.10-performance-check.json",
    )
    args = parser.parse_args()
    main(args.app, args.report)
