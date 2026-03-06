"""
Unified launcher for AI Drone Emergency Response System.
Starts the FastAPI backend and the Streamlit dashboard.
"""

import subprocess
import time
import sys
import os
from pathlib import Path


def run_services():
    print("AI Drone Emergency Response System - Unified Launcher")
    print("=====================================================")

    # Ensure we are in the project root
    ROOT_DIR = Path(__file__).parent.absolute()
    os.chdir(ROOT_DIR)

    # Check for .env
    env_path = ROOT_DIR / "backend" / ".env"
    if not env_path.exists():
        print(f"WARNING: {env_path} not found!")
    else:
        with open(env_path, "r") as f:
            if "your_telegram_bot_token_here" in f.read():
                print("WARNING: Telegram token not set in backend/.env")

    # Kill any existing processes on our ports
    print("Cleaning up existing processes...")
    subprocess.run(["fuser", "-k", "10000/tcp"], capture_output=True)
    subprocess.run(["fuser", "-k", "8501/tcp"], capture_output=True)

    print("Ensuring WebSocket support (uvicorn[standard])...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "uvicorn[standard]", "websockets"],
        capture_output=True,
    )

    time.sleep(1)

    # 1. Start Backend (FastAPI + Telegram Bot)
    print("Starting backend (FastAPI + Telegram bot)...")
    backend_process = subprocess.Popen(
        [sys.executable, "backend/main.py"],
        cwd=ROOT_DIR,
    )

    # Wait for backend to bind port
    time.sleep(4)

    # 2. Start Dashboard (Streamlit)
    print("Starting rescue dashboard (Streamlit)...")
    dashboard_process = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            "dashboard/rescue_dashboard.py",
            "--server.port", "8501",
            "--server.headless", "true",
        ],
        cwd=ROOT_DIR,
    )

    print()
    print("SYSTEM IS LIVE")
    print("-----------------------------------------------------")
    print("  Backend:    http://localhost:10000")
    print("  Dashboard:  http://localhost:8501")
    print("  Map:        file://" + str(ROOT_DIR / "frontend" / "map.html"))
    print("-----------------------------------------------------")
    print("Tip: Use the Telegram bot to report an incident.")
    print("Press Ctrl+C to stop all services.")
    print()

    try:
        while True:
            time.sleep(1)
            if backend_process.poll() is not None:
                print("Backend stopped unexpectedly.")
                break
            if dashboard_process.poll() is not None:
                print("Dashboard stopped unexpectedly.")
                break
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        backend_process.terminate()
        dashboard_process.terminate()


if __name__ == "__main__":
    run_services()
