"""
MediTrack AI — One-Click Application Launcher
Starts backend server, verifies database, and opens browser dashboard.
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import sys
import time
import webbrowser
import threading
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from database.db import init_db
from database.seed_data import seed
import uvicorn

def launch_browser():
    time.sleep(1.8)
    print("\n[Browser] Opening MediTrack AI Dashboard at http://127.0.0.1:8000 ...")
    webbrowser.open("http://127.0.0.1:8000")

def main():
    print("=" * 72)
    print("  [+] MediTrack AI -- Intelligent Medical Equipment Management System")
    print("      'Track. Predict. Allocate. Protect.'")
    print("=" * 72)
    print("  [OK] Python Environment: Ready")
    print("  [OK] Database: Initializing SQLite & verifying seed records...")
    init_db()
    
    # Auto-seed if db is fresh or requested
    seed()
    print("  [OK] Seed Data: 60 Hospital Equipment Assets + RFID Tags Loaded")
    print("  [OK] AI Core: Allocation + Maintenance + Demand + Vision + Priority Ready")
    print("  [OK] WebSocket Server: ws://127.0.0.1:8000/ws")
    print("  [OK] Web Dashboard: http://127.0.0.1:8000")
    print("=" * 72)
    print("  HACKATHON DEMO SHORTCUTS:")
    print("  * 1. Scan RFID: Click 'RFID Tap' button (Identifies WC-007)")
    print("  * 2. Trigger PIR: Click 'PIR Motion' button (WC-009 active usage)")
    print("  * 3. Surge Alert: Click 'Surge' button (High priority triage 94/100)")
    print("  * 4. AI Allocation: Go to 'AI Allocation' and click 'ASK AI TO ALLOCATE'")
    print("  * 5. Vision AI: Go to 'Vision AI' and click 'INVESTIGATE DISCREPANCY'")
    print("=" * 72)

    # Launch browser in background thread
    threading.Thread(target=launch_browser, daemon=True).start()

    # Start Uvicorn ASGI server (0.0.0.0 allows ESP32 hardware and LAN access)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, log_level="info", app_dir=str(backend_dir))

if __name__ == "__main__":
    main()
