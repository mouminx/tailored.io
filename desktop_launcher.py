from __future__ import annotations

import os
import threading
import time
import webbrowser

import requests
import uvicorn

HOST = "127.0.0.1"
PORT = int(os.getenv("RESUME_ADJUSTER_PORT", "8765"))
URL = f"http://{HOST}:{PORT}"


def run_server() -> None:
    config = uvicorn.Config("app.main:app", host=HOST, port=PORT, log_level="info")
    server = uvicorn.Server(config)
    server.run()


def wait_for_server(timeout_seconds: int = 30) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(URL, timeout=1.5)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(0.5)
    return False


def main() -> int:
    print("Starting Resume Adjuster desktop app...")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    if not wait_for_server():
        print("Server did not start in time.")
        return 1

    print(f"App is ready at {URL}")
    webbrowser.open(URL)

    try:
        while server_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
