"""Adapt the managed preview launch flags to Uvicorn without changing application code."""

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run the local AirLedger preview")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    # Uvicorn already exits when the selected port is occupied.
    parser.add_argument("--strictPort", action="store_true")
    args = parser.parse_args()
    os.chdir(Path(__file__).resolve().parent.parent)
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            args.host,
            "--port",
            str(args.port),
        ],
    )


if __name__ == "__main__":
    main()
