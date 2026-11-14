"""Run on the user's own computer and open the browser only once AirLedger responds."""

import argparse
import json
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def open_when_ready(url: str):
    for _ in range(100):
        try:
            with urllib.request.urlopen(url + "/api/status", timeout=1) as response:
                if json.load(response).get("name") == "AirLedger":
                    webbrowser.open(url)
                    return
        except (OSError, ValueError, urllib.error.URLError):
            pass
        time.sleep(0.2)


def main():
    parser = argparse.ArgumentParser(description="Run AirLedger on your own computer")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port between 1024 and 65535.")
    url = f"http://127.0.0.1:{args.port}"
    # Keep runtime data relative to the project even when invoked from another directory.
    import os

    os.chdir(ROOT)
    print(f"AirLedger: {url}\nKeep this terminal open. Press Ctrl+C to stop.", flush=True)
    threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
