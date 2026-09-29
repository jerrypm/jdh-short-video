import os
import shutil
import signal
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from .repository import ROOT, atomic_json

JOB_DIR = ROOT / "_jobs"
JOB_DIR.mkdir(exist_ok=True)
POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jdh-worker")
JOBS = {}
LOCK = threading.RLock()


def cancel_all():
    with LOCK:
        for job in JOBS.values():
            if job.status in {"queued", "running"}:
                job.cancelled.set()


class Cancelled(Exception):
    pass


class Job:
    def __init__(self, project_id, kind):
        self.id = uuid4().hex
        self.project_id = project_id
        self.kind = kind
        self.status = "queued"
        self.progress = 0
        self.message = "Menunggu worker lokal"
        self.files = []
        self.result = None
        self.cancelled = threading.Event()
        self.directory = JOB_DIR / self.id
        self.directory.mkdir()
        self.persist()

    def public(self):
        return {
            k: getattr(self, k)
            for k in [
                "id",
                "project_id",
                "kind",
                "status",
                "progress",
                "message",
                "files",
                "result",
            ]
        }

    def persist(self):
        atomic_json(self.directory / "job.json", self.public())

    def update(self, progress, message):
        self.check()
        self.progress = round(progress)
        self.message = message
        self.persist()

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled()

    def process(self, args, start=0, end=100, seconds=1):
        self.check()
        log = self.directory / "worker.log"
        with log.open("ab") as errors:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=errors,
                text=True,
                start_new_session=True,
            )

            def cancel_watch():
                deadline = time.monotonic() + 900
                while process.poll() is None:
                    if self.cancelled.wait(0.15) or time.monotonic() > deadline:
                        try:
                            os.killpg(process.pid, signal.SIGTERM)
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        return

            thread = threading.Thread(target=cancel_watch, daemon=True)
            thread.start()
            for line in process.stdout:
                if line.startswith("out_time_us="):
                    try:
                        percent = min(
                            1, float(line.split("=")[1]) / 1e6 / max(seconds, 0.01)
                        )
                        self.update(start + (end - start) * percent, self.message)
                    except ValueError:
                        pass
            code = process.wait()
            thread.join(timeout=1)
            self.check()
            if code:
                raise ValueError(
                    "Pemrosesan media gagal. " + log.read_text(errors="replace")[-1000:]
                )


def submit(project_id, kind, action):
    with LOCK:
        if any(j.status in {"queued", "running"} for j in JOBS.values()):
            raise RuntimeError(
                "Satu pekerjaan berat sedang berjalan. Tunggu atau batalkan dahulu."
            )
        job = Job(project_id, kind)
        JOBS[job.id] = job

    def work():
        try:
            job.check()
            job.status = "running"
            job.persist()
            action(job)
            job.check()
            job.status, job.progress, job.message = "completed", 100, "Selesai"
        except Cancelled:
            job.status, job.message = "cancelled", "Dibatalkan — proyek tetap tersimpan"
            job.files = []
        except Exception as error:
            job.status, job.message = "failed", str(error)
            job.files = []
        finally:
            shutil.rmtree(job.directory / "temp", ignore_errors=True)
            if job.status != "completed":
                for path in job.directory.iterdir():
                    if path.suffix in {".mp4", ".wav", ".zip", ".srt"}:
                        path.unlink(missing_ok=True)
            job.persist()

    POOL.submit(work)
    return job.public()


def read(jid):
    import json

    if not __import__("re").fullmatch("[a-f0-9]{32}", jid):
        raise ValueError("ID pekerjaan tidak valid.")
    if jid in JOBS:
        return JOBS[jid].public()
    path = JOB_DIR / jid / "job.json"
    data = json.loads(path.read_text())
    if data["status"] in {"queued", "running"}:
        data.update(
            status="failed",
            message="Layanan berhenti saat pekerjaan berjalan. Silakan coba lagi.",
            files=[],
        )
        atomic_json(path, data)
    return data
