"""Generate a real English sample while denying all outbound Python sockets."""

import json
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import jobs, tts
from backend.models import TTSRequest, Project, Scene


def denied(*args, **kwargs):
    raise RuntimeError("Offline verification detected a network attempt")


socket.socket.connect = denied
socket.socket.connect_ex = denied
socket.create_connection = denied
project = Project(
    id="0" * 32,
    name="Offline verification",
    language="en",
    scenes=[
        Scene(
            id="verification",
            narration="One idea. One short. Start with one clear message.",
        )
    ],
)
job = jobs.Job(project.id, "tts")
tts.generate(
    project, TTSRequest(scene_id=project.scenes[0].id, voice="af_heart", speed=1), job
)
job.status = "completed"
job.persist()
print(
    json.dumps(
        {
            "job_id": job.id,
            "audio": str(job.directory / "narration.wav"),
            "frames": job.result["frames"],
            "network": "Python sockets denied",
        },
        indent=2,
    )
)
