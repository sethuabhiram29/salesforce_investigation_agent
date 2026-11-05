"""Launcher script for the Salesforce Agentic Support UI.

Run with:
    python run_ui.py            # defaults to port 8501
    python run_ui.py 8502       # runs on port 8502
    python run_ui.py --port 8502
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app" / "ui" / "streamlit_app.py"


def main():
    parser = argparse.ArgumentParser(description="Launch Salesforce Agentic Support UI")
    parser.add_argument("port_pos", nargs="?", type=int, default=None, help="Port (positional, e.g. 8501 or 8502)")
    parser.add_argument("--port", "-p", type=int, default=8501, help="Port (default: 8501)")
    args = parser.parse_args()

    port = args.port_pos if args.port_pos is not None else args.port

    print("=" * 60)
    print(f"  Starting Streamlit UI on port {port}...")
    print(f"  App file: {APP_FILE}")
    print(f"  URL: http://localhost:{port}")
    print("=" * 60)

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP_FILE),
        f"--server.port={port}",
        "--server.headless=true",
        "--server.address=0.0.0.0",
    ]

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print(f"\nStreamlit server on port {port} stopped.")


if __name__ == "__main__":
    main()
