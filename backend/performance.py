"""Manual/CSV import with an explicit review, deduplication and cautious evidence."""

from collections import OrderedDict, defaultdict
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
import re
from statistics import median
import time
from uuid import uuid4
from fastapi import HTTPException
from . import (
    repository as repo,
    content_memory as memory,
    daily_ideas_store as ideas,
    nano,
)
from . import performance_store as store
from .performance_models import Measurement, METRICS, Record

NOTICE = "Indikasi deskriptif, bukan sebab-akibat atau prediksi. Minimal 5 video berbeda per kelompok/metrik untuk ringkasan; ambang ini bukan uji signifikansi."
HEADERS = list(Measurement.model_fields)


def parse_csv(text):
    if len(text.encode()) > 40000:
        raise ValueError("CSV maksimal 40 KB dan 100 baris.")
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")), strict=True)
    try:
        headers = reader.fieldnames or []
        required = {
            k for k, field in Measurement.model_fields.items() if field.is_required()
        }
        if (
            len(headers) != len(set(headers))
            or not required <= set(headers)
            or set(headers) - set(HEADERS)
        ):
            raise ValueError(
                "Header CSV tidak cocok dengan template. Jangan memetakan Views ke engaged_views atau mengubah definisi secara diam-diam."
            )
        rows = []
        for index, row in enumerate(reader, 2):
            if len(rows) >= 100 or None in row or any(v is None for v in row.values()):
                raise ValueError(f"Baris {index}: jumlah kolom/baris tidak valid.")
            values = {k: v.strip() for k, v in row.items()}
            for key in METRICS:
                value = values.get(key, "")
                if not value:
                    values[key] = None
                elif key in {
                    "average_view_duration_seconds",
                    "average_view_percentage",
                }:
                    if not re.fullmatch(r"\d+(\.\d+)?", value):
                        raise ValueError(
                            f"Baris {index}: {key} harus angka desimal bertitik, tanpa pemisah ribuan atau %."
                        )
                    values[key] = float(value)
                else:
                    if not re.fullmatch(r"\d+", value):
                        raise ValueError(
                            f"Baris {index}: {key} harus bilangan bulat tanpa pemisah ribuan."
                        )
                    values[key] = int(value)
            try:
                rows.append(Measurement.model_validate(values).model_dump())
            except ValueError as error:
                raise ValueError(f"Baris {index}: {error}") from error
        if not rows:
            raise ValueError("CSV belum berisi data.")
        return rows
    except csv.Error as error:
        raise ValueError(
            "Format CSV tidak valid; gunakan template UTF-8 dengan pemisah koma."
        ) from error


def record_id(row):
    # Capture timestamps and filenames are provenance, not a new measurement identity.
    key = [
        row.video_id,
        row.period_start,
        row.period_end,
        row.report_timezone,
        row.definition,
        row.definition_note,
    ]
    return hashlib.sha256(json.dumps(key).encode()).hexdigest()[:32]


def same_measurement(old, row):
    fields = set(Measurement.model_fields) - {"captured_at", "source"}
    return all(getattr(old, k) == getattr(row, k) for k in fields)


def latest(records):
    """One snapshot per video; never sum overlapping periods or averaged averages."""
    chosen = {}
    for row in records:
        order = (
            row.period_end,
            row.period_start,
            datetime.fromisoformat(row.captured_at),
            row.id,
        )
        old = chosen.get(row.video_id)
        if old is None or order > old[0]:
            chosen[row.video_id] = (order, row)
    return sorted(
        (item[1] for item in chosen.values()),
        key=lambda r: (r.period_end, r.id),
        reverse=True,
    )


def window(row):
    published, start, end = [
        date.fromisoformat(v)
        for v in (row.published_on, row.period_start, row.period_end)
    ]
    return (start - published).days, (end - start).days + 1


def cohorts(records):
    groups = defaultdict(list)
    for row in latest(records):
        offset, days = window(row)
        groups[
            (row.definition, row.definition_note, row.report_timezone, offset, days)
        ].append(row)
    result = []
    for (definition, note, zone, offset, days), rows in groups.items():
        values = {
            k: [getattr(r, k) for r in rows if getattr(r, k) is not None]
            for k in METRICS
        }
        result.append(
            {
                "definition": definition,
                "definition_note": note,
                "report_timezone": zone,
                "start_age_days": offset,
                "period_days": days,
                "video_count": len(rows),
                "metric_counts": {k: len(v) for k, v in values.items()},
                "medians": {
                    k: median(v) if len(v) >= 5 else None for k, v in values.items()
                },
            }
        )
    return result


def evidence_row(row):
    item = {
        k: getattr(row, k)
        for k in (
            "id",
            "project_id",
            "period_start",
            "period_end",
            "report_timezone",
            "definition",
            "definition_note",
            "source",
            "captured_at",
            *METRICS,
        )
    }
    offset, days = window(row)
    item.update(start_age_days=offset, period_days=days)
    return item


def cited_evidence(connection, catalog, cards):
    allowed = {
        r.project_id
        for r in catalog.references
        if r.included and not r.missing and r.category == "content"
    }
    cited = {rid for card in cards for rid in card.performance_ids}
    return {
        r.id: evidence_row(r)
        for r in store.read(connection).records
        if r.id in cited and r.included and r.project_id in allowed
    }


def context(connection, source_ids):
    rows = latest(
        r
        for r in store.read(connection).records
        if r.included and r.project_id in source_ids
    )
    evidence = []
    for row in rows:
        item = evidence_row(row)
        candidate = evidence + [item]
        if len(json.dumps(candidate, ensure_ascii=False)) > 3300:
            break
        evidence = candidate
        if len(evidence) == 5:
            break
    return {
        "rows": evidence,
        "notice": "User-reviewed inputs, not authenticated by YouTube. Missing is null, not zero. One latest included snapshot per video. Do not infer patterns from these few examples; propose testable hypotheses only, never causation, predicted views or trends. Compare only identical definitions, timezone, age at period start and period length. Always keep an experiment idea. Cite performance_ids and source_project_ids for any metrics used.",
    }


def invalidate(connection, revision):
    state = ideas.read(connection)
    cancelled = (
        state.active.id
        if state.active and state.active.source_mode == "history"
        else None
    )
    if cancelled:
        for attempt in state.attempts:
            if attempt.id == cancelled:
                attempt.status = "cancelled"
                attempt.message = (
                    "Data performa berubah; buat ide baru dari konteks terbaru."
                )
    if cancelled:
        state.active = None
    state.batches = [b for b in state.batches if b.source_mode == "research"]
    state.performance_revision = revision
    ideas.write(connection, state)
    return cancelled


class Service:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.reviews = OrderedDict()

    def view(self):
        with repo.LOCK:
            catalog = memory.operate()
            with memory.transaction() as connection:
                state = store.read(connection)
            projects = repo.list_projects()
            available = {p["id"] for p in projects}
            selected = {
                r.project_id
                for r in catalog.references
                if r.included and not r.missing and r.category == "content"
            }
            eligible = [
                r for r in state.records if r.included and r.project_id in available
            ]
            return {
                **state.model_dump(),
                "projects": [{"id": p["id"], "name": p["name"]} for p in projects],
                "ai_project_ids": sorted(selected),
                "latest_ids": [r.id for r in latest(eligible)],
                "cohorts": cohorts(eligible),
                "notice": NOTICE,
            }

    def plan(self, state, request):
        if state.revision != request.revision:
            raise RuntimeError(
                "Data performa berubah. Muat ulang dan tinjau ulang impor."
            )
        known = {r.id: r for r in state.records}
        mapping = {r.video_id: r.project_id for r in state.records}
        seen = set()
        actions = []
        for row in request.rows:
            if not row.project_id:
                raise ValueError("Pilih proyek untuk setiap baris sebelum pratinjau.")
            try:
                repo.load(row.project_id)
            except FileNotFoundError:
                raise HTTPException(
                    404, "Proyek tujuan tidak tersedia. Pilih proyek yang masih ada."
                )
            if row.video_id in mapping and mapping[row.video_id] != row.project_id:
                raise ValueError(
                    "Video yang sama sudah dipetakan ke proyek lain. Periksa video ID/proyek."
                )
            mapping[row.video_id] = row.project_id
            rid = record_id(row)
            if rid in seen:
                raise ValueError(
                    "Satu impor berisi video/periode/definisi yang sama lebih dari sekali."
                )
            seen.add(rid)
            old = known.get(rid)
            action = (
                "add"
                if not old
                else "duplicate"
                if same_measurement(old, row)
                else "replace"
                if request.replace_conflicts
                else "conflict"
            )
            actions.append(
                {
                    "id": rid,
                    "action": action,
                    "row": row.model_dump(),
                    "previous": old.model_dump() if old else None,
                }
            )
        if len(known) + sum(a["action"] == "add" for a in actions) > 1000:
            raise ValueError("Maksimal 1.000 pengukuran tersimpan.")
        return actions

    def preview(self, request):
        with repo.LOCK, memory.transaction() as connection:
            actions = self.plan(store.read(connection), request)
            now = self.clock()
            self.reviews = OrderedDict(
                (k, v) for k, v in self.reviews.items() if now - v["created"] < 900
            )
            while len(self.reviews) >= 8:
                self.reviews.popitem(last=False)
            rid = uuid4().hex
            self.reviews[rid] = {
                "request": request.model_copy(deep=True),
                "created": now,
                "applied": False,
            }
            return {
                "review_id": rid,
                "actions": actions,
                "can_apply": not any(a["action"] == "conflict" for a in actions),
            }

    def apply(self, review_id):
        with repo.LOCK:
            review = self.reviews.get(review_id)
            if not review or self.clock() - review["created"] >= 900:
                raise RuntimeError(
                    "Pratinjau kedaluwarsa atau aplikasi dimulai ulang; tinjau lagi."
                )
            if review["applied"]:
                return self.view()
            cancelled = None
            with memory.transaction() as connection:
                state = store.read(connection)
                request = review["request"]
                actions = self.plan(state, request)
                if any(a["action"] == "conflict" for a in actions):
                    raise ValueError(
                        "Ada konflik. Tinjau opsi penggantian sebelum menyimpan."
                    )
                records = {r.id: r for r in state.records}
                for action, row in zip(actions, request.rows):
                    if action["action"] == "duplicate":
                        continue
                    old = records.get(action["id"]) or next(
                        (r for r in records.values() if r.video_id == row.video_id),
                        None,
                    )
                    records[action["id"]] = Record(
                        **row.model_dump(),
                        id=action["id"],
                        origin=request.origin,
                        imported_at=datetime.now(timezone.utc).isoformat(),
                        included=old.included if old else True,
                        exclusion_reason=old.exclusion_reason if old else "",
                    )
                if list(records.values()) != state.records:
                    state.records = list(records.values())
                    state.revision += 1
                    store.write(connection, state)
                    cancelled = invalidate(connection, state.revision)
            review["applied"] = True
            if cancelled:
                nano.broker.cancel(cancelled)
            return self.view()

    def inclusion(self, rid, request):
        with repo.LOCK:
            cancelled = None
            with memory.transaction() as connection:
                state = store.read(connection)
                if state.revision != request.revision:
                    raise RuntimeError(
                        "Data berubah. Muat ulang sebelum mengubah pengecualian."
                    )
                row = next((r for r in state.records if r.id == rid), None)
                if row is None:
                    raise HTTPException(404, "Pengukuran tidak tersedia.")
                reason = "" if request.included else request.reason.strip()
                if not request.included and not reason:
                    raise ValueError("Isi alasan pengecualian anomali.")
                if (row.included, row.exclusion_reason) != (request.included, reason):
                    for snapshot in state.records:
                        if snapshot.video_id == row.video_id:
                            snapshot.included, snapshot.exclusion_reason = (
                                request.included,
                                reason,
                            )
                    state.revision += 1
                    store.write(connection, state)
                    cancelled = invalidate(connection, state.revision)
            if cancelled:
                nano.broker.cancel(cancelled)
            return self.view()


service = Service()
