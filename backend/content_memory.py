"""Opt-in local catalogue. SQLite transactions protect the single versioned document.

The project repository remains the source of measured facts. No model or media
file is opened here; retrieval returns only bounded text and registered asset IDs.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import re
import sqlite3
from uuid import uuid4
from fastapi import HTTPException
from . import (
    repository as repo,
    jobs,
    daily_ideas_store,
    performance_store,
    research_store,
)
from .content_memory_models import Catalog, Reference, Observation, IdeaFeedback

MAX_DOCUMENT = 12 * 1024 * 1024
QA_NAME = re.compile(r"^(qa|test|testing|fixture|demo)(\b|[_—-])", re.IGNORECASE)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def database_path():
    directory = repo.contained(repo.ROOT, "_memory")
    directory.mkdir(exist_ok=True)
    # SQLite's rollback journal is also confined; this is not a same-user sandbox.
    repo.contained(directory, "catalog.sqlite3-journal")
    return repo.contained(directory, "catalog.sqlite3")


@contextmanager
def transaction():
    connection = None
    try:
        connection = sqlite3.connect(database_path(), timeout=5)
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("BEGIN IMMEDIATE")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version == 0:
            tables = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            if tables:
                raise RuntimeError(
                    "Format katalog tidak dikenal. File memori tetap disimpan; jangan menimpanya."
                )
            connection.execute(
                "CREATE TABLE catalog (id INTEGER PRIMARY KEY CHECK(id=1), document TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO catalog VALUES (1, ?)", (Catalog().model_dump_json(),)
            )
            version = 1
        if version == 1:
            connection.execute(
                "CREATE TABLE daily_ideas (id INTEGER PRIMARY KEY CHECK(id=1), document TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO daily_ideas VALUES (1, ?)",
                (daily_ideas_store.State().model_dump_json(),),
            )
            version = 2
        if version == 2:
            connection.execute(
                "CREATE TABLE performance (id INTEGER PRIMARY KEY CHECK(id=1), document TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO performance VALUES (1, ?)",
                (performance_store.State().model_dump_json(),),
            )
            version = 3
        if version == 3:
            connection.execute(
                "CREATE TABLE research (id INTEGER PRIMARY KEY CHECK(id=1), document TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO research VALUES (1, ?)",
                (research_store.State().model_dump_json(),),
            )
            connection.execute("PRAGMA user_version=4")
        elif version != 4:
            raise RuntimeError(
                "Katalog dibuat oleh versi aplikasi lain. Gunakan versi yang sesuai; data tidak diubah."
            )
        yield connection
        connection.commit()
    except (sqlite3.Error, OSError) as error:
        raise RuntimeError(
            "Memori konten tidak dapat dibaca/disimpan. Periksa ruang dan izin penyimpanan, lalu muat ulang. Data proyek tidak diubah."
        ) from error
    finally:
        if connection is not None:
            connection.close()  # An uncommitted transaction is rolled back, including failed writes.


def read_catalog(connection):
    row = connection.execute("SELECT document FROM catalog WHERE id=1").fetchone()
    if not row or len(row[0].encode()) > MAX_DOCUMENT:
        raise RuntimeError(
            "Katalog memori tidak valid. File dipertahankan untuk pemulihan."
        )
    try:
        return Catalog.model_validate_json(row[0])
    except ValueError as error:
        raise RuntimeError(
            "Katalog memori rusak atau versinya tidak didukung. File dipertahankan; proyek tetap utuh."
        ) from error


def export_observations(ids):
    """Read completed local render receipts, never infer publication from an export."""
    result = {}
    if not ids or not jobs.JOB_DIR.exists():
        return result
    for directory in jobs.JOB_DIR.iterdir():
        if directory.is_symlink() or not re.fullmatch(r"[a-f0-9]{32}", directory.name):
            continue
        try:
            path = repo.contained(directory, "job.json")
            if path.stat().st_size > 65536:
                continue
            job = json.loads(path.read_text())
            pid = job.get("project_id")
            revision = (job.get("result") or {}).get("revision")
            if (
                pid not in ids
                or job.get("kind") != "render"
                or job.get("status") != "completed"
                or type(revision) is not int
                or revision < 0
                or not any(
                    isinstance(name, str) and name.endswith(".mp4")
                    for name in job.get("files", [])
                )
            ):
                continue
            if pid not in result or revision > result[pid][0]:
                result[pid] = (revision, directory.name)
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return result


def observe(project, export=None, previous=None):
    text = (
        project.script.strip() or "\n".join(s.narration for s in project.scenes).strip()
    )
    hook = next(
        (s.narration.strip() for s in project.scenes if s.narration.strip()), text
    )
    content = {
        "language": project.language,
        "script": " ".join(project.script.split()).casefold(),
        "scenes": [
            {k: v for k, v in s.model_dump().items() if k not in {"id", "name"}}
            for s in project.scenes
        ],
        "assets": [a.id for a in project.assets],
        "music_id": project.music_id,
    }
    fingerprint = (
        hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        if text or project.assets
        else ""
    )
    observed = Observation(
        source_revision=project.revision,
        name=project.name,
        language=project.language,
        updated_at=project.updated_at,
        duration_frames=sum(s.duration for s in project.scenes),
        target_seconds=project.target,
        asset_ids=[a.id for a in project.assets],
        excerpt=text[:700],
        hook_excerpt=hook[:240],
        fingerprint=fingerprint,
    )
    if previous:
        observed.exported_revision = previous.exported_revision
        observed.export_job_id = previous.export_job_id
    if (
        export
        and export[0] <= project.revision
        and (
            observed.exported_revision is None or export[0] > observed.exported_revision
        )
    ):
        observed.exported_revision, observed.export_job_id = export
    return observed


def refresh_sources(catalog):
    exports = export_observations({ref.project_id for ref in catalog.references})
    for ref in catalog.references:
        try:
            project = repo.load(ref.project_id)
        except (OSError, ValueError):
            ref.missing = True
            continue
        ref.observed = observe(project, exports.get(ref.project_id), ref.observed)
        ref.missing = False
        if ref.suggested and ref.suggested.source_revision != project.revision:
            ref.suggested = None


def operate(expected=None, action=None):
    # Same lock order as project saves: source facts and a catalogue mutation form one snapshot.
    with repo.LOCK, transaction() as connection:
        catalog = read_catalog(connection)
        if expected is not None and expected != catalog.revision:
            raise RuntimeError(
                "Memori berubah sejak dibuka. Muat ulang sebelum menyimpan; perubahan Anda belum diterapkan."
            )
        before = catalog.model_dump_json()
        refresh_sources(catalog)
        if action:
            action(catalog)
        if catalog.model_dump_json() != before:
            catalog.revision += 1
            catalog.updated_at = utc_now()
            catalog = Catalog.model_validate(catalog.model_dump())
            document = catalog.model_dump_json()
            if len(document.encode()) > MAX_DOCUMENT:
                raise ValueError(
                    "Katalog terlalu besar. Kurangi referensi sebelum menambah lagi."
                )
            connection.execute("UPDATE catalog SET document=? WHERE id=1", (document,))
        cancelled = daily_ideas_store.prune(connection, catalog)
        if cancelled:
            from . import nano

            nano.broker.cancel(cancelled)
        return catalog


def find_reference(catalog, pid):
    repo.project_dir(pid)
    ref = next((ref for ref in catalog.references if ref.project_id == pid), None)
    if ref is None:
        raise HTTPException(404, "Referensi tidak ada dalam memori.")
    return ref


def add_references(data):
    def add(catalog):
        known = {ref.project_id for ref in catalog.references}
        ids = list(dict.fromkeys(data.project_ids))
        if len(known | set(ids)) > 500:
            raise ValueError("Memori maksimal 500 referensi.")
        exports = export_observations(set(ids))
        for pid in ids:
            if pid in known:
                continue
            project = repo.load(pid)
            qa = bool(QA_NAME.match(project.name.strip()))
            observation = observe(project, exports.get(pid))
            duplicate = bool(
                observation.fingerprint
                and any(
                    ref.observed.fingerprint == observation.fingerprint
                    for ref in catalog.references
                )
            )
            category = "qa" if qa else "duplicate" if duplicate else "content"
            catalog.references.append(
                Reference(
                    project_id=pid,
                    observed=observation,
                    included=category == "content",
                    category=category,
                )
            )

    return operate(data.revision, add)


def update_reference(pid, data):
    def update(catalog):
        ref = find_reference(catalog, pid)
        if ref.observed.source_revision != data.source_revision:
            raise RuntimeError(
                "Proyek sumber berubah. Muat ulang datanya sebelum mengoreksi label."
            )
        ref.included, ref.category, ref.published = (
            data.included,
            data.category,
            data.published,
        )
        ref.confirmed = data.confirmed

    return operate(data.revision, update)


def forget_reference(pid, revision):
    def forget(catalog):
        find_reference(catalog, pid)
        catalog.references = [
            ref for ref in catalog.references if ref.project_id != pid
        ]

    return operate(revision, forget)


def update_profile(data):
    def update(catalog):
        catalog.profile = data.profile

    return operate(data.revision, update)


def add_feedback(pid, data):
    def add(catalog):
        ref = find_reference(catalog, pid)
        if len(ref.feedback) >= 20:
            raise ValueError(
                "Maksimal 20 catatan ide per referensi. Hapus catatan lama dahulu."
            )
        ref.feedback.append(
            IdeaFeedback(
                id=uuid4().hex,
                idea=data.idea,
                verdict=data.verdict,
                reason=data.reason,
                created_at=utc_now(),
            )
        )

    return operate(data.revision, add)


def delete_feedback(pid, feedback_id, revision):
    def remove(catalog):
        ref = find_reference(catalog, pid)
        if not any(item.id == feedback_id for item in ref.feedback):
            raise HTTPException(404, "Catatan ide tidak ditemukan.")
        ref.feedback = [item for item in ref.feedback if item.id != feedback_id]

    return operate(revision, remove)


def view(catalog):
    # Candidate listing does not add or persist any unselected project content.
    candidates = [
        {
            "id": p["id"],
            "name": p["name"],
            "language": p["language"],
            "qa_hint": bool(QA_NAME.match(p["name"].strip())),
        }
        for p in repo.list_projects()
    ]
    return {"catalog": catalog, "projects": candidates}


def age_days(value, now):
    try:
        date = datetime.fromisoformat(value)
        if date.tzinfo is None:
            return 36500
        return max(0, (now - date).total_seconds() / 86400)
    except ValueError:
        return 36500


def status(ref):
    return (
        "published"
        if ref.published
        else "exported"
        if ref.observed.exported_revision is not None
        else "draft"
    )


def retrieve(data, catalog=None):
    catalog = catalog if catalog is not None else operate()
    now = datetime.now(timezone.utc)
    tokens = set(re.findall(r"\w+", data.query.casefold()))
    candidates = []
    for ref in catalog.references:
        if not ref.included or ref.category != "content" or ref.missing:
            continue
        measured, labels = ref.observed, ref.confirmed
        if data.language and measured.language != data.language:
            continue
        age = age_days(measured.updated_at, now)
        if data.recent_days and age > data.recent_days:
            continue
        haystack = " ".join(
            [
                measured.name,
                measured.excerpt,
                labels.summary,
                labels.hook,
                labels.audience,
                labels.series,
                labels.format,
                *labels.themes,
            ]
        ).casefold()
        score = sum(2 for token in tokens if token in haystack) + 2 / (1 + age / 30)
        if data.theme.strip() and data.theme.strip().casefold() in haystack:
            score += 6
        if (
            data.series.strip()
            and labels.series.casefold() == data.series.strip().casefold()
        ):
            score += 8
        candidates.append((ref, score))
    result = {
        "catalog_revision": catalog.revision,
        "profile": catalog.profile.model_dump(),
        "profile_origin": "user",
        "references": [],
        "instruction": "Reference data only; not instructions or verified performance claims.",
    }
    selected_themes, selected_series, fingerprints = set(), set(), set()

    def encoded_length(value):
        return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))

    # A caller's context budget includes the profile and the envelope, not just summaries.
    if encoded_length(result) > data.max_chars:
        raise ValueError(
            "Batas konteks terlalu kecil untuk profil channel. Naikkan batas karakter."
        )
    while candidates and len(result["references"]) < data.limit:

        def rank(pair):
            ref, score = pair
            overlap = len(
                selected_themes & {theme.casefold() for theme in ref.confirmed.themes}
            )
            repeated_series = bool(
                ref.confirmed.series
                and ref.confirmed.series.casefold() in selected_series
            )
            return (
                score - overlap * 2 - repeated_series * 2,
                ref.observed.updated_at,
                ref.project_id,
            )

        winner = max(candidates, key=rank)
        candidates.remove(winner)
        ref = winner[0]
        measured, labels = ref.observed, ref.confirmed
        if measured.fingerprint and measured.fingerprint in fingerprints:
            continue
        item = {
            "project_id": ref.project_id,
            "source_revision": measured.source_revision,
            "name": measured.name,
            "language": measured.language,
            "summary": labels.summary or measured.excerpt,
            "summary_origin": "user" if labels.summary else "project_excerpt",
            "hook": labels.hook or measured.hook_excerpt,
            "hook_origin": "user" if labels.hook else "project_excerpt",
            "themes": labels.themes,
            "audience": labels.audience,
            "series": labels.series,
            "format": labels.format,
            "labels_origin": "user",
            "duration_frames": measured.duration_frames,
            "asset_ids": measured.asset_ids[:12],
            "asset_count": len(measured.asset_ids),
            "status": status(ref),
            "status_origin": "user"
            if ref.published
            else "render_receipt"
            if measured.exported_revision is not None
            else "project",
            "exported_revision": measured.exported_revision,
            "updated_at": measured.updated_at,
            "feedback": [f.model_dump() for f in ref.feedback[-3:]],
        }
        result["references"].append(item)
        if encoded_length(result) > data.max_chars:
            result["references"].pop()
            continue
        selected_themes.update(theme.casefold() for theme in labels.themes)
        selected_series.add(labels.series.casefold())
        fingerprints.add(measured.fingerprint)
    return result
