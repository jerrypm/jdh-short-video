"""Explicit one-time online setup. Runtime never calls this script."""

import hashlib
import json
import os
from pathlib import Path
from huggingface_hub import hf_hub_download

root = Path(__file__).resolve().parents[1]
destination = Path(os.environ.get("JDH_KOKORO_DIR", root / "data/models/kokoro"))
destination.mkdir(parents=True, exist_ok=True)
repository = "hexgrad/Kokoro-82M"
revision = "f3ff3571791e39611d31c381e3a41a3af07b4987"
files = ["config.json", "kokoro-v1_0.pth", "README.md", "VOICES.md"]
files += [
    f"voices/{voice}.pt" for voice in ["af_heart", "af_bella", "am_adam", "am_michael"]
]
manifest = {"repository": repository, "revision": revision, "files": {}}
for name in files:
    print(f"Downloading {name}", flush=True)
    path = Path(
        hf_hub_download(repository, name, revision=revision, local_dir=destination)
    )
    manifest["files"][name] = {
        "bytes": path.stat().st_size,
        "sha256": hashlib.file_digest(path.open("rb"), "sha256").hexdigest(),
    }
(destination / "download-manifest.json").write_text(json.dumps(manifest, indent=2))
print(f"Model ready: {destination}", flush=True)
