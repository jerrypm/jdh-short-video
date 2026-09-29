"""Optional Kokoro adapter. Runtime only reads pre-installed local weights."""

import hashlib
import importlib.util
import os
from pathlib import Path
from . import media, repository
from .models import TTSRequest

MODEL_DIR = Path(os.environ.get("JDH_KOKORO_DIR", repository.ROOT / "models/kokoro"))
VOICES = ["af_heart", "af_bella", "am_adam", "am_michael"]


def capability():
    required = [MODEL_DIR / "kokoro-v1_0.pth", MODEL_DIR / "config.json"]
    voices = [v for v in VOICES if (MODEL_DIR / "voices" / f"{v}.pt").is_file()]
    ready = (
        all(
            importlib.util.find_spec(package)
            for package in ("kokoro", "en_core_web_sm")
        )
        and all(p.is_file() for p in required)
        and bool(voices)
    )
    return {
        "available": ready,
        "voices": voices if ready else [],
        "message": "Kokoro · English · CPU"
        if ready
        else "Kokoro belum disiapkan. Narasi impor tetap tersedia.",
        "model_dir": str(MODEL_DIR),
    }


def generate(project, request: TTSRequest, job):
    if not capability()["available"]:
        raise ValueError("Kokoro belum terpasang. Jalankan scripts/setup-kokoro.sh.")
    if project.language != "en":
        raise ValueError(
            "Provider ini hanya diaktifkan untuk English. Impor narasi untuk Indonesia."
        )
    scene = next(s for s in project.scenes if s.id == request.scene_id)
    if not scene.narration.strip():
        raise ValueError("Naskah scene masih kosong.")
    job.update(5, "Memuat Kokoro lokal (CPU)")
    # Ensure no implicit runtime downloads; setup is a separate explicit command.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from kokoro import KModel, KPipeline

    if os.environ.get("JDH_ESPEAK_DIR"):
        # eSpeak's packaged C runtime cannot reliably resolve the deeply nested
        # site-packages path inside an app bundle. Use the shallow resource copy.
        from phonemizer.backend.espeak.wrapper import EspeakWrapper

        EspeakWrapper.set_data_path(os.environ["JDH_ESPEAK_DIR"])
    import numpy as np
    import soundfile as sf

    model = (
        KModel(
            config=str(MODEL_DIR / "config.json"),
            model=str(MODEL_DIR / "kokoro-v1_0.pth"),
        )
        .to("cpu")
        .eval()
    )
    pipeline = KPipeline(lang_code="a", model=model, device="cpu")
    fingerprint = hashlib.sha256()
    for file in ["config.json", "kokoro-v1_0.pth", f"voices/{request.voice}.pt"]:
        with (MODEL_DIR / file).open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                fingerprint.update(chunk)
    key = hashlib.sha256(
        f"{scene.narration}|{request.voice}|{request.speed}|{fingerprint.hexdigest()}|kokoro-0.9.4".encode()
    ).hexdigest()
    cache = repository.ROOT / "_tts_cache"
    cache.mkdir(exist_ok=True)
    cached = cache / f"{key}.wav"
    if not cached.exists():
        chunks = []
        for _, _, audio in pipeline(
            scene.narration,
            voice=str(MODEL_DIR / "voices" / f"{request.voice}.pt"),
            speed=request.speed,
        ):
            job.check()
            chunks.append(np.asarray(audio))
        if not chunks:
            raise ValueError("Kokoro tidak menghasilkan audio.")
        sf.write(cached, np.concatenate(chunks), 24000)
    job.check()
    asset = media.inspect_media(cached, f"{scene.name} — {request.voice}.wav")
    asset.peaks = media.make_peaks(cached)
    import shutil

    # Review output is staged with the job. Generation never changes the project
    # revision while the user is editing. Applying it is a separate transaction.
    shutil.copy2(cached, job.directory / "narration.wav")
    job.files = ["narration.wav"]
    job.result = {
        "asset": asset.model_dump(),
        "scene_id": scene.id,
        "text": scene.narration,
        "frames": asset.frames,
    }
    job.update(100, "Narasi tersedia — tinjau lalu terapkan")
