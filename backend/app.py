import io
import os
import secrets
import shutil
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, Request, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from PIL import UnidentifiedImageError
from . import repository as repo, media, captions, render, jobs, tts, nano
from .models import NewProject, Project, RenderRequest, TTSRequest, Asset
from .storyboard_routes import router as storyboard_router
from .pacing_routes import router as pacing_router
from .quality_routes import router as quality_router
from . import quality
from . import storyboards
from .daily_ideas_routes import router as ideas_router
from . import daily_ideas
from .nano_routes import router as nano_router
from .content_memory_routes import router as memory_router
from .performance_routes import router as performance_router
from .research_routes import router as research_router

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
SESSION = secrets.token_urlsafe(32)
CSRF = secrets.token_urlsafe(32)
PORT = os.environ.get("JDH_PORT", "8741")
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}", "testserver"}
DESKTOP_TOKEN = os.environ.get("JDH_DESKTOP_TOKEN", "")


@app.middleware("http")
async def local_security(request: Request, call_next):
    host = request.headers.get("host", "")
    if host not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "Host ditolak."}, status_code=403)
    origin = request.headers.get("origin")
    if origin and origin != f"http://{host}":
        return JSONResponse({"detail": "Origin ditolak."}, status_code=403)
    if request.headers.get("sec-fetch-site") == "cross-site":
        return JSONResponse(
            {"detail": "Permintaan lintas situs ditolak."}, status_code=403
        )
    desktop_health = request.url.path == "/api/desktop/health"
    if desktop_health and (
        not DESKTOP_TOKEN
        or not secrets.compare_digest(
            request.headers.get("x-jdh-desktop", ""), DESKTOP_TOKEN
        )
    ):
        return JSONResponse({"detail": "Desktop session required."}, status_code=403)
    if (
        request.url.path.startswith("/api/")
        and request.url.path != "/api/session"
        and not desktop_health
    ):
        if not secrets.compare_digest(request.cookies.get("jdh_session", ""), SESSION):
            return JSONResponse(
                {"detail": "Sesi berakhir. Muat ulang aplikasi."}, status_code=401
            )
        if request.method not in {"GET", "HEAD"} and not secrets.compare_digest(
            request.headers.get("x-jdh-csrf", ""), CSRF
        ):
            return JSONResponse({"detail": "Token sesi tidak valid."}, status_code=403)
    try:
        content_length = int(request.headers.get("content-length", "0"))
    except ValueError:
        return JSONResponse({"detail": "Ukuran request tidak valid."}, status_code=400)
    if content_length < 0:
        return JSONResponse({"detail": "Ukuran request tidak valid."}, status_code=400)
    bounded_request = request.url.path.startswith(
        (
            "/api/ai/",
            "/nano/api/",
            "/api/memory",
            "/api/ideas",
            "/api/storyboards",
            "/api/pacing",
            "/api/quality",
            "/api/performance",
            "/api/research",
            "/api/callout-preview",
            "/api/caption-preview",
        )
    )
    if bounded_request:
        if content_length > 65536:
            return JSONResponse(
                {"detail": "Permintaan terlalu besar."}, status_code=413
            )
        if request.method in {"POST", "PUT"}:
            chunks, size = [], 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > 65536:
                    return JSONResponse(
                        {"detail": "Permintaan terlalu besar."}, status_code=413
                    )
                chunks.append(chunk)
            # BaseHTTPMiddleware replays this cached body to FastAPI's validator.
            request._body = b"".join(chunks)
    if content_length > media.MAX_UPLOAD + 1048576:
        return JSONResponse({"detail": "File maksimal 512 MB."}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith(("/api/", "/nano/")):
        response.headers["Cache-Control"] = "no-store"
    if request.url.path.startswith("/nano/"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
    return response


@app.exception_handler(ValueError)
async def value_error(request, error):
    return JSONResponse({"detail": str(error)}, status_code=422)


@app.exception_handler(UnidentifiedImageError)
async def invalid_image(request, error):
    return JSONResponse(
        {"detail": "File gambar rusak atau format tidak cocok."}, status_code=422
    )


@app.exception_handler(zipfile.BadZipFile)
async def invalid_zip(request, error):
    return JSONResponse(
        {"detail": "Paket ZIP rusak atau tidak valid."}, status_code=422
    )


@app.exception_handler(FileNotFoundError)
async def missing_error(request, error):
    return JSONResponse(
        {"detail": "File atau proyek tidak ditemukan."}, status_code=404
    )


@app.exception_handler(RuntimeError)
async def conflict_error(request, error):
    return JSONResponse({"detail": str(error)}, status_code=409)


@app.get("/api/session")
def session():
    response = JSONResponse({"csrf": CSRF})
    response.set_cookie("jdh_session", SESSION, httponly=True, samesite="strict")
    return response


@app.get("/api/desktop/health")
def desktop_health():
    return {
        "ready": True,
        "busy": any(job.status in {"queued", "running"} for job in jobs.JOBS.values())
        or nano.broker.status()["busy"],
    }


@app.get("/api/capabilities")
def capabilities():
    return {
        "ffmpeg": bool(media.FFMPEG),
        "ffprobe": bool(media.FFPROBE),
        "caption": captions.FONT.is_file(),
        "tts": tts.capability(),
        "storage": str(repo.ROOT),
        "free_bytes": shutil.disk_usage(repo.ROOT).free,
        "desktop": os.environ.get("JDH_DESKTOP") == "1",
    }


@app.get("/api/projects")
def projects():
    return repo.list_projects()


@app.post("/api/projects")
def create(data: NewProject):
    return repo.create(data)


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    return repo.load(pid)


@app.put("/api/projects/{pid}")
def save_project(pid: str, project: Project):
    if project.id != pid:
        raise ValueError("ID tidak cocok.")
    with repo.LOCK:
        current = repo.load(pid)
        # Media paths are owned by the importer, never accepted from editable JSON.
        project.assets = current.assets
        return repo.save(project, expected=project.revision)


@app.post("/api/projects/{pid}/media")
async def import_media(pid: str, file: UploadFile):
    repo.load(pid)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in media.EXTENSIONS:
        raise ValueError("Format file tidak didukung.")
    directory = repo.media_dir(pid)
    directory.mkdir(exist_ok=True)
    tmp = directory / f"{uuid4().hex}{suffix}"
    try:
        size = 0
        with tmp.open("xb") as stream:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > media.MAX_UPLOAD:
                    raise ValueError("File maksimal 512 MB.")
                stream.write(chunk)
        asset = await run_in_threadpool(
            media.inspect_media, tmp, file.filename or "Media"
        )
        if asset.has_audio:
            asset.peaks = await run_in_threadpool(media.make_peaks, tmp)
        final = directory / asset.file
        tmp.rename(final)
        with repo.LOCK:
            project = repo.load(pid)
            if len(project.assets) >= 200:
                final.unlink()
                raise ValueError("Maksimal 200 media per proyek.")
            project.assets.append(asset)
            repo.save(project)
        return {"asset": asset, "project": project}
    finally:
        tmp.unlink(missing_ok=True)
        await file.close()


@app.get("/api/projects/{pid}/media/{aid}")
def get_media(pid: str, aid: str):
    project = repo.load(pid)
    path = repo.asset_path(project, aid)
    return FileResponse(path)


@app.post("/api/caption-preview")
def caption_preview(data: dict):
    from .models import CaptionStyle

    text = data.get("text", "")
    if not isinstance(text, str) or len(text) > 400:
        raise ValueError("Caption tidak valid.")
    style = CaptionStyle.model_validate(data.get("style", {}))
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "caption.png"
        captions.caption_image(text, style, path)
        return Response(path.read_bytes(), media_type="image/png")


@app.get("/api/projects/{pid}/preflight")
def preflight(pid: str):
    project = repo.load(pid)
    errors = render.issues(project)
    for i, scene in enumerate(project.scenes):
        try:
            with tempfile.TemporaryDirectory() as directory:
                captions.caption_image(
                    scene.caption, project.caption_style, Path(directory) / "c.png"
                )
                captions.callout_image(
                    scene.motion.callout, Path(directory) / "callout.png"
                )
        except (ValueError, OSError) as error:
            errors.append(f"Scene {i + 1}: {error}")
    if not media.FFMPEG:
        errors.append("FFmpeg belum terpasang.")
    return {"issues": errors, "frames": sum(s.duration for s in project.scenes)}


@app.post("/api/callout-preview")
def callout_preview(data: dict):
    from .motion import Callout

    callout = Callout.model_validate(data)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "callout.png"
        captions.callout_image(callout, path)
        return Response(path.read_bytes(), media_type="image/png")


@app.post("/api/projects/{pid}/render")
def start_render(pid: str, data: RenderRequest):
    with repo.LOCK:
        project = repo.load(pid)
        errors = render.issues(project)
        if errors:
            raise ValueError(" ".join(errors))
        report = (
            quality.service.export_report(pid, data.check_id, data.preset)
            if data.check_id
            else None
        )
        daily_ideas.service.defer()
        storyboards.service.defer()
        quality.service.defer()
        files = quality.signatures(project)

        def work(job):
            if quality.signatures(project) != files:
                raise RuntimeError("Media berubah sebelum ekspor. Periksa ulang.")
            render.render(project, data.preset, job, report)
            if quality.signatures(project) != files:
                raise RuntimeError("Media berubah selama ekspor. Periksa ulang.")

        return jobs.submit(pid, "render", work)


@app.post("/api/projects/{pid}/tts")
def start_tts(pid: str, data: TTSRequest):
    project = repo.load(pid)
    if not any(s.id == data.scene_id for s in project.scenes):
        raise ValueError("Scene tidak ditemukan.")
    if not tts.capability()["available"]:
        raise ValueError(tts.capability()["message"])
    with repo.LOCK:
        daily_ideas.service.defer()
        storyboards.service.defer()
        quality.service.defer()
        return jobs.submit(pid, "tts", lambda job: tts.generate(project, data, job))


@app.get("/api/jobs/{jid}")
def job_status(jid: str):
    return jobs.read(jid)


@app.post("/api/projects/{pid}/tts/{jid}/apply")
def apply_tts(pid: str, jid: str, data: dict):
    job = jobs.read(jid)
    if job["project_id"] != pid or job["kind"] != "tts" or job["status"] != "completed":
        raise ValueError("Hasil narasi belum tersedia untuk proyek ini.")
    result = job["result"]
    with repo.LOCK:
        project = repo.load(pid)
        if data.get("revision") != project.revision:
            raise RuntimeError("Proyek berubah. Muat ulang sebelum menerapkan narasi.")
        scene = next((s for s in project.scenes if s.id == result["scene_id"]), None)
        if not scene or scene.narration != result["text"]:
            raise ValueError(
                "Naskah scene berubah. Buat ulang narasi untuk teks terbaru."
            )
        asset = Asset.model_validate(result["asset"])
        if len(project.assets) >= 200:
            raise ValueError("Maksimal 200 media per proyek.")
        if asset.frames > 1800:
            raise ValueError("Narasi lebih dari 60 detik. Pecah naskah dahulu.")
        directory = repo.media_dir(pid)
        directory.mkdir(exist_ok=True)
        shutil.copy2(
            repo.contained(jobs.JOB_DIR / jid, "narration.wav"),
            repo.contained(directory, asset.file),
        )
        if not any(a.id == asset.id for a in project.assets):
            project.assets.append(asset)
        scene.audio_id = asset.id
        scene.audio_text = result["text"]
        scene.audio_in = 0
        scene.duration = max(scene.duration, asset.frames)
        return repo.save(
            Project.model_validate(project.model_dump()), expected=project.revision
        )


@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: str):
    job = jobs.JOBS.get(jid)
    if job and job.status in {"queued", "running"}:
        job.cancelled.set()
    return jobs.read(jid)


@app.get("/api/jobs/{jid}/files/{name}")
def download(jid: str, name: str):
    job = jobs.read(jid)
    if job["status"] != "completed" or name not in job["files"]:
        raise HTTPException(404, "Output belum tersedia.")
    return FileResponse(
        repo.contained(jobs.JOB_DIR / jid, name),
        filename=name,
        content_disposition_type="inline" if name.endswith(".mp4") else "attachment",
    )


@app.post("/api/import-project")
async def import_project(file: UploadFile):
    content = await file.read(media.MAX_UPLOAD + 1)
    await file.close()
    if len(content) > media.MAX_UPLOAD:
        raise ValueError("Paket maksimal 512 MB.")
    pid = uuid4().hex
    destination = repo.project_dir(pid)
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if (
                sum(e.file_size for e in entries) > media.MAX_UPLOAD
                or len(entries) > 202
            ):
                raise ValueError("Paket terlalu besar.")
            manifest = archive.read("project.json")
            project = Project.model_validate_json(manifest)
            expected = {"project.json"} | {"media/" + a.file for a in project.assets}
            if {e.filename for e in entries} != expected or len(entries) != len(
                expected
            ):
                raise ValueError("Isi paket tidak cocok dengan manifest.")
            destination.mkdir()
            (destination / "media").mkdir()
            for asset in project.assets:
                raw = archive.read("media/" + asset.file)
                path = repo.contained(destination / "media", asset.file)
                path.write_bytes(raw)
                checked = await run_in_threadpool(media.inspect_media, path, asset.name)
                if checked.kind != asset.kind:
                    raise ValueError("Jenis media tidak cocok.")
                asset.frames = checked.frames
                asset.width = checked.width
                asset.height = checked.height
                asset.has_audio = checked.has_audio
                asset.peaks = (
                    await run_in_threadpool(media.make_peaks, path)
                    if checked.has_audio
                    else []
                )
            project.id = pid
            project.revision = 0
            return repo.save(project)
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        raise


app.include_router(storyboard_router)
app.include_router(pacing_router)
app.include_router(quality_router)
app.include_router(nano_router)
app.include_router(memory_router)
app.include_router(performance_router)
app.include_router(research_router)
app.include_router(ideas_router)

STATIC = Path(__file__).resolve().parents[1] / "web/out"
if STATIC.exists():
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="web")
