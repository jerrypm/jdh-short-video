"""Private sidecar: bind an unused loopback port and stop with the desktop host."""

import os
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    os.environ["JDH_PORT"] = str(port)
    os.environ["JDH_DESKTOP"] = "1"
    if not os.environ.get("JDH_DESKTOP_TOKEN"):
        raise RuntimeError("Desktop launcher token is required.")
    import uvicorn
    from backend import jobs, nano
    from backend.app import app

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    stopping = threading.Event()

    def stop():
        if stopping.is_set():
            return
        stopping.set()
        nano.broker.disconnect()
        jobs.cancel_all()
        server.should_exit = True

        # A model inference cannot be interrupted inside a Torch operation.
        # FFmpeg process groups are cancelled first; a stale TTS job recovers on restart.
        def deadline():
            time.sleep(12)
            os._exit(0)

        threading.Thread(target=deadline, daemon=True).start()

    def watch_input():
        sys.stdin.buffer.read()
        stop()

    parent = os.getppid()

    def watch_parent():
        while not stopping.wait(0.5):
            if os.getppid() != parent:
                stop()

    threading.Thread(target=watch_input, daemon=True).start()
    threading.Thread(target=watch_parent, daemon=True).start()
    print(f"JDH_PORT={port}", flush=True)
    try:
        server.run(sockets=[listener])
    finally:
        nano.broker.disconnect()
        jobs.cancel_all()
        listener.close()


if __name__ == "__main__":
    main()
