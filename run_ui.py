"""Launcher script for the Salesforce Agentic Support UI.

Run with:
    python run_ui.py
or:
    streamlit run app/ui/streamlit_app.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app" / "ui" / "streamlit_app.py"

if __name__ == "__main__":
    print(f"Starting Streamlit UI from {APP_FILE}...")
    cmd = [sys.executable, "-m", "streamlit", "run", str(APP_FILE), "--server.port=8501", "--server.headless=true"]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nStreamlit server stopped.")
