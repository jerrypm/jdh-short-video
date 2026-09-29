import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from .models import Project, NewProject

ROOT = Path(
    os.environ.get("JDH_DATA_DIR", Path(__file__).resolve().parents[1] / "data")
).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
LOCK = threading.RLock()


def project_dir(pid: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", pid):
        raise ValueError("ID proyek tidak valid.")
    path = ROOT / pid
    if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
        raise ValueError("Path proyek tidak valid.")
    return path


def contained(directory: Path, name: str) -> Path:
    result = directory / name
    if result.is_symlink() or not result.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Path media tidak valid.")
    return result


def media_dir(pid: str) -> Path:
    return contained(project_dir(pid), "media")


def atomic_json(path: Path, value: dict):
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load(pid: str) -> Project:
    path = contained(project_dir(pid), "project.json")
    try:
        return Project.model_validate_json(path.read_text())
    except (json.JSONDecodeError, ValueError):
        backup = path.with_name("project.backup.json")
        if backup.exists():
            return Project.model_validate_json(backup.read_text())
        raise


def save(project: Project, expected: int | None = None) -> Project:
    with LOCK:
        directory = project_dir(project.id)
        directory.mkdir(exist_ok=True)
        path = contained(directory, "project.json")
        if path.exists():
            previous = load(project.id)
            if expected is not None and previous.revision != expected:
                raise RuntimeError(
                    "Proyek berubah di tab lain. Muat ulang sebelum menyimpan."
                )
            atomic_json(directory / "project.backup.json", previous.model_dump())
            project.revision = previous.revision + 1
        project.updated_at = datetime.now(timezone.utc).isoformat()
        atomic_json(path, project.model_dump())
        return project


def create(data: NewProject) -> Project:
    return save(Project(id=uuid4().hex, **data.model_dump()))


def list_projects() -> list[dict]:
    result = []
    for path in ROOT.iterdir():
        if path.is_dir() and re.fullmatch(r"[a-f0-9]{32}", path.name):
            try:
                result.append(load(path.name).model_dump())
            except (ValueError, OSError):
                continue
    return sorted(result, key=lambda p: p["updated_at"], reverse=True)


def asset_path(project: Project, aid: str) -> Path:
    asset = next((a for a in project.assets if a.id == aid), None)
    if asset is None:
        raise ValueError("Media tidak terdaftar di proyek.")
    directory = project_dir(project.id) / "media"
    if directory.is_symlink() or not directory.resolve().is_relative_to(
        project_dir(project.id).resolve()
    ):
        raise ValueError("Direktori media tidak valid.")
    return contained(directory, asset.file)
