"""Disposable analytics fixtures; all Nano outputs are contract fixtures, not inference."""

import csv
import io
import json
import sqlite3
import pytest
from backend.tests.test_daily_ideas import env as env
from backend import performance, performance_store, daily_ideas_store, storyboards
from backend.performance_models import Measurement, Record
from backend.idea_contract import validate_ideas
from backend.tests.test_daily_ideas import (
    call,
    selected,
    start,
    dispatch,
    finish,
    ideas,
    status,
    complete,
)  # noqa: F401


def measurement(pid, **values):
    return {
        "project_id": pid,
        "video_id": "qaVideo0001",
        "published_on": "2024-01-01",
        "period_start": "2024-01-01",
        "period_end": "2024-01-07",
        "report_timezone": "America/Los_Angeles",
        "captured_at": "2024-01-09T00:00:00+00:00",
        "definition": "youtube_engaged_views_v1",
        "definition_note": "",
        "source": "Disposable QA export",
        "engaged_views": 0,
        "average_view_duration_seconds": None,
        "average_view_percentage": 120.5,
        "likes": None,
        "comments": 0,
        "shares": 2,
        **values,
    }


@pytest.fixture
def perf(env, monkeypatch):
    monkeypatch.setattr(performance, "service", performance.Service())
    return env, selected(env)


def preview(env, rows, replace=False):
    state = call(env, "GET", "/performance")
    return call(
        env,
        "POST",
        "/performance/preview",
        json={
            "revision": state["revision"],
            "rows": rows,
            "origin": "manual",
            "replace_conflicts": replace,
        },
    )


def apply(env, review):
    return call(
        env,
        "POST",
        "/performance/apply",
        json={"review_id": review["review_id"], "reviewed": True},
    )


def csv_text(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=performance.HEADERS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def test_review_is_required_atomic_and_retry_is_idempotent(perf):
    env, project = perf
    review = preview(env, [measurement(project.id)])
    assert call(env, "GET", "/performance")["records"] == []
    assert (
        env.client.post(
            "/api/performance/apply",
            json={"review_id": review["review_id"], "reviewed": False},
        ).status_code
        == 422
    )
    result = apply(env, review)
    assert result["revision"] == 1
    row = result["records"][0]
    assert row["engaged_views"] == 0 and row["likes"] is None
    assert row["average_view_percentage"] == 120.5
    assert row["source"] == "Disposable QA export" and row["imported_at"]
    assert apply(env, review) == result
    newer = measurement(
        project.id, captured_at="2024-01-10T00:00:00+00:00", source="another filename"
    )
    duplicate = preview(env, [newer])
    assert duplicate["actions"][0]["action"] == "duplicate"
    assert apply(env, duplicate) == result


def test_correction_conflict_and_optimistic_concurrency(perf):
    env, project = perf
    apply(env, preview(env, [measurement(project.id)]))
    correction = measurement(project.id, engaged_views=200)
    conflict = preview(env, [correction])
    assert not conflict["can_apply"]
    assert (
        env.client.post(
            "/api/performance/apply",
            json={"review_id": conflict["review_id"], "reviewed": True},
        ).status_code
        == 422
    )
    ready = preview(env, [correction], replace=True)
    stale = preview(env, [measurement(project.id, video_id="qaVideo0002")])
    result = apply(env, ready)
    assert len(result["records"]) == 1 and result["records"][0]["engaged_views"] == 200
    assert (
        env.client.post(
            "/api/performance/apply",
            json={"review_id": stale["review_id"], "reviewed": True},
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"engaged_views": -1},
        {"engaged_views": True},
        {"engaged_views": 1.5},
        {"average_view_percentage": float("inf")},
        {"average_view_duration_seconds": float("nan")},
        {"video_id": "https://youtube.com/example"},
        {"report_timezone": "bad/timezone"},
        {"published_on": "2024-01-08"},
        {"period_end": "2024-01-10"},
        {"captured_at": "2024-01-09T00:00:00"},
        {"definition": "custom"},
        {"published_on": "20240101"},
        {"source": " "},
    ],
)
def test_invalid_numbers_dates_and_definitions_are_rejected(patch):
    with pytest.raises(ValueError):
        Measurement.model_validate(measurement("a" * 32, **patch))


def test_missing_not_zero_and_csv_strict_headers(perf):
    env, project = perf
    text = csv_text([measurement("", likes=None, engaged_views=0)])
    rows = call(env, "POST", "/performance/parse", json={"csv": "\ufeff" + text})[
        "rows"
    ]
    assert (
        rows[0]["project_id"] == ""
        and rows[0]["likes"] is None
        and rows[0]["engaged_views"] == 0
    )
    assert (
        env.client.post(
            "/api/performance/preview",
            json={"revision": 0, "rows": rows, "origin": "csv"},
        ).status_code
        == 422
    )
    rows[0]["project_id"] = project.id
    assert len(apply(env, preview(env, rows))["records"]) == 1
    for invalid in [
        text.replace("engaged_views,", "views,"),
        text.replace("likes,", "shares,"),
        text + ",bad",
        csv_text([measurement(project.id, engaged_views="1,000")]),
    ]:
        with pytest.raises(ValueError):
            performance.parse_csv(invalid)
    with pytest.raises(ValueError):
        performance.parse_csv(csv_text([measurement(project.id)] * 101))


def test_mapping_duplicate_rows_missing_project_and_unknown_fields(perf):
    env, project = perf
    apply(env, preview(env, [measurement(project.id)]))
    other = selected(env)
    assert (
        env.client.post(
            "/api/performance/preview",
            json={"revision": 1, "origin": "csv", "rows": [measurement(other.id)]},
        ).status_code
        == 422
    )
    assert (
        env.client.post(
            "/api/performance/preview",
            json={
                "revision": 1,
                "origin": "csv",
                "rows": [measurement(project.id)] * 2,
            },
        ).status_code
        == 422
    )
    assert (
        env.client.post(
            "/api/performance/preview",
            json={"revision": 1, "origin": "csv", "rows": [measurement("f" * 32)]},
        ).status_code
        == 404
    )
    assert (
        env.client.post(
            "/api/performance/preview",
            json={
                "revision": 1,
                "origin": "csv",
                "rows": [measurement(project.id, views=40)],
            },
        ).status_code
        == 422
    )


def test_excluding_video_excludes_all_periods_and_future_imports(perf):
    env, project = perf
    result = apply(
        env,
        preview(
            env,
            [measurement(project.id), measurement(project.id, period_end="2024-01-08")],
        ),
    )
    rid = result["records"][0]["id"]
    result = call(
        env,
        "PUT",
        f"/performance/{rid}/inclusion",
        json={"revision": 1, "included": False, "reason": "Paid traffic anomaly"},
    )
    assert not result["cohorts"] and not result["latest_ids"]
    assert all(not r["included"] for r in result["records"])
    result = apply(
        env,
        preview(
            env,
            [
                measurement(
                    project.id,
                    period_end="2024-01-09",
                    captured_at="2024-01-11T00:00:00+00:00",
                )
            ],
        ),
    )
    assert all(not r["included"] for r in result["records"])
    result = call(
        env,
        "PUT",
        f"/performance/{rid}/inclusion",
        json={"revision": 3, "included": True},
    )
    assert all(r["included"] for r in result["records"])
    assert len(result["latest_ids"]) == 1
    assert result["cohorts"][0]["video_count"] == 1


def test_small_samples_and_incompatible_periods_never_aggregate():
    rows = []
    for i in range(6):
        row = Measurement.model_validate(
            measurement(
                "a" * 32,
                video_id=f"qaVideo{i:04d}",
                engaged_views=i * 100,
                likes=None if i < 2 else i,
            )
        )
        rows.append(
            Record(
                **row.model_dump(),
                id=performance.record_id(row),
                origin="manual",
                imported_at="2024-01-10T00:00:00+00:00",
            )
        )
    assert performance.cohorts(rows[:4])[0]["medians"]["engaged_views"] is None
    cohort = performance.cohorts(rows)[0]
    assert cohort["medians"]["engaged_views"] == 250
    assert cohort["medians"]["likes"] is None and cohort["metric_counts"]["likes"] == 4
    rows[0].published_on = "2023-12-01"
    rows[1].report_timezone = "UTC"
    rows[2].definition = "custom"
    rows[2].definition_note = "Different report definition"
    rows[3].period_end = "2024-01-06"
    cohorts = performance.cohorts(rows)
    assert len(cohorts) == 5 and all(
        c["medians"]["engaged_views"] is None for c in cohorts
    )


def test_transaction_rollback_preserves_metrics_and_idea_state(perf, monkeypatch):
    env, project = perf
    review = preview(env, [measurement(project.id)])

    def fail(*args):
        raise RuntimeError("fixture write failure")

    monkeypatch.setattr(daily_ideas_store, "write", fail)
    assert (
        env.client.post(
            "/api/performance/apply",
            json={"review_id": review["review_id"], "reviewed": True},
        ).status_code
        == 409
    )
    assert call(env, "GET", "/performance")["records"] == []
    with performance.memory.transaction() as connection:
        assert daily_ideas_store.read(connection).performance_revision == 0


def test_context_is_opt_in_bounded_and_cited(perf):
    env, project = perf
    result = apply(env, preview(env, [measurement(project.id)]))
    rid = result["records"][0]["id"]
    with performance.memory.transaction() as connection:
        assert not performance.context(connection, set())["rows"]
        evidence = performance.context(connection, {project.id})["rows"]
    assert len(evidence) == 1 and evidence[0]["engaged_views"] == 0
    value = ideas([project.id])
    with pytest.raises(ValueError):
        validate_ideas(value, [project.id], evidence)
    value[0]["performance_ids"] = [rid]
    assert validate_ideas(value, [project.id], evidence)[2]["category"] == "experiment"
    value[0]["performance_ids"] = ["f" * 32]
    with pytest.raises(ValueError):
        validate_ideas(value, [project.id], evidence)
    assert start(env)["active_id"]
    job = dispatch(env)
    context = json.loads(job["input"])
    assert context["performance"]["rows"][0]["id"] == rid
    assert len(job["input"]) < 12000
    value[0]["performance_ids"] = [rid]
    assert finish(env, job, value=value).status_code == 200
    assert status(env)["performance_evidence"][rid]["source"] == "Disposable QA export"


def test_performance_change_cancels_inference_and_stales_saved_ideas(perf):
    env, project = perf
    batch = complete(env)["batch"]
    card = batch["cards"][0]
    call(
        env,
        "PUT",
        f"/ideas/cards/{card['id']}/feedback",
        json={"timezone": "Asia/Jakarta", "verdict": "saved", "reason": "Keep"},
    )
    from datetime import timedelta

    env.now[0] += timedelta(seconds=31)
    active = start(env)["active_id"]
    assert active
    apply(env, preview(env, [measurement(project.id)]))
    assert env.broker.read(active)["status"] == "cancelled"
    state = status(env)
    assert state["batch"] is None and state["feedback"][0]["performance_stale"]
    with pytest.raises(Exception) as error:
        storyboards.service.idea(card["id"])
    assert error.value.status_code == 409


def test_restart_retains_data_but_expires_review(perf, monkeypatch):
    env, project = perf
    saved = apply(env, preview(env, [measurement(project.id)]))
    review = preview(env, [measurement(project.id, video_id="qaVideo0002")])
    monkeypatch.setattr(performance, "service", performance.Service())
    assert call(env, "GET", "/performance") == saved
    assert (
        env.client.post(
            "/api/performance/apply",
            json={"review_id": review["review_id"], "reviewed": True},
        ).status_code
        == 409
    )


def test_v2_migration_preserves_documents(perf):
    env, _ = perf
    path = performance.memory.database_path()
    with sqlite3.connect(path) as connection:
        catalog = connection.execute("SELECT document FROM catalog").fetchone()[0]
        daily = connection.execute("SELECT document FROM daily_ideas").fetchone()[0]
        connection.execute("DROP TABLE research")
        connection.execute("DROP TABLE performance")
        connection.execute("PRAGMA user_version=2")
    with performance.memory.transaction() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
        assert (
            connection.execute("SELECT document FROM catalog").fetchone()[0] == catalog
        )
        assert (
            connection.execute("SELECT document FROM daily_ideas").fetchone()[0]
            == daily
        )
        assert performance_store.read(connection).records == []


def test_api_security_and_body_bounds(env):
    assert (
        env.client.post(
            "/api/performance/parse",
            json={"csv": "x"},
            headers={"Origin": "https://example.com"},
        ).status_code
        == 403
    )
    assert (
        env.client.post("/api/performance/parse", content=b"x" * 65537).status_code
        == 413
    )
    assert env.client.get("/api/performance/template").text.startswith(
        "project_id,video_id,"
    )
