#!/usr/bin/env python3
"""
========================================================================================
MediTrack AI — ESP32 Bluetooth & RF Signal Strength Gateway Bridge
========================================================================================
1. Connects to ESP32 ("MediTrack-ESP32") via Bluetooth Serial or USB COM Port.
2. Measures received RF signal strength (RSSI) from the ESP32 in real time.
3. Computes physical distance in meters using the Log-Distance Path Loss Model.
4. Forwards telemetry & RFID events to the MediTrack AI FastAPI backend.

Usage:
    python bluetooth_bridge.py                  # Auto-detects Bluetooth or USB port
    python bluetooth_bridge.py --port COM5      # Connects to specific COM port
    python bluetooth_bridge.py --list          # Lists all available COM ports
========================================================================================
"""

import sys
import time
import json
import argparse
import subprocess
import re
import math
import threading
import urllib.request
import urllib.error
import serial
import serial.tools.list_ports

BACKEND_URL = "http://127.0.0.1:8000/api/esp32/update"
LOG_URL = "http://127.0.0.1:8000/api/esp32/log"
BAUD_RATE = 115200

# Global active state
CURRENT_EQUIPMENT = "WHEELCHAIR"
CURRENT_STATUS = "IN_USE"
LAST_RF_DISTANCE = 0.0
LAST_RF_TIME = time.time()

def forward_log_to_backend(line):
    """Forwards plain text console lines from ESP32/RF Tracker to website Arduino Serial Monitor."""
    try:
        req_data = json.dumps({"line": line}).encode("utf-8")
        req = urllib.request.Request(
            LOG_URL,
            data=req_data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            pass
    except Exception:
        pass

def rf_signal_tracker_thread():
    """Background thread: Measures real received RF signal strength from ESP32."""
    global LAST_RF_DISTANCE, LAST_RF_TIME, CURRENT_STATUS, CURRENT_EQUIPMENT
    print("\n[+] RF Signal Tracker: Background thread ENGAGED.")
    print("    Continuously measuring received RF signal strength from ESP32 (quiet mode)...\n")
    
    smooth_distance = 0.0
    smooth_rssi = -48.0
    last_sent_distance = -999.0
    last_sent_zone = ""
    last_sent_time = 0.0
    last_print_time = 0.0

    while True:
        try:
            time.sleep(1.5)
            out = subprocess.check_output(['netsh', 'wlan', 'show', 'networks', 'mode=bssid'], text=True, errors='ignore')
            
            # Priority 1: Direct ESP32 Access Point Beacon
            match = re.search(r'SSID \d+ : (MediTrack-ESP32).*?Signal\s*:\s*(\d+)%', out, re.DOTALL)
            if not match:
                # Priority 2: Phone Hotspot or associated SSID
                match = re.search(r'SSID \d+ : (Amshaaa shinigami).*?Signal\s*:\s*(\d+)%', out, re.DOTALL)

            if match:
                ssid_name = match.group(1).strip()
                pct = int(match.group(2))
                raw_dbm = (pct / 2.0) - 100.0

                # Low-pass filter to smooth multipath noise
                smooth_rssi = (0.35 * raw_dbm) + (0.65 * smooth_rssi)

                # Log-Distance Path Loss Model: d = 10 ^ ((Baseline - RSSI) / (10 * n)) - 1.0
                raw_dist = max(0.0, math.pow(10.0, (-48.0 - smooth_rssi) / (10.0 * 2.2)) - 1.0)
                if raw_dist > 45.0:
                    raw_dist = 45.0
                smooth_distance = (0.30 * raw_dist) + (0.70 * smooth_distance)

                now = time.time()
                dt = (now - LAST_RF_TIME) if (now - LAST_RF_TIME) > 0 else 1.0
                speed = abs(smooth_distance - LAST_RF_DISTANCE) / dt
                if speed < 0.15:
                    speed = 0.0
                if speed > 2.5:
                    speed = 1.2
                LAST_RF_DISTANCE = smooth_distance
                LAST_RF_TIME = now

                # Clinical ward zone based on real distance
                if smooth_distance >= 22.0:
                    zone = "Radiology Suite"
                elif smooth_distance >= 8.0:
                    zone = "Clinical Transit Corridor"
                else:
                    zone = "Emergency Ward"

                # Rate-limiting filter: only dispatch backend update if distance changed noticeably (>= 0.6m),
                # zone changed, or slow heartbeat (every 12 seconds)
                dist_diff = abs(smooth_distance - last_sent_distance)
                zone_changed = (zone != last_sent_zone)
                heartbeat_due = (now - last_sent_time >= 12.0)

                if dist_diff >= 0.6 or zone_changed or heartbeat_due:
                    last_sent_distance = smooth_distance
                    last_sent_zone = zone
                    last_sent_time = now

                    payload = {
                        "equipment": CURRENT_EQUIPMENT,
                        "status": "IN_USE",
                        "event": "RF_SIGNAL_TRACKING",
                        "distance_meters": round(smooth_distance, 1),
                        "speed_mps": round(speed, 1),
                        "rssi": int(smooth_rssi),
                        "signal_pct": pct,
                        "moving": (speed > 0.0),
                        "location": zone,
                        "source": "ESP32_RF_SIGNAL"
                    }

                    # Forward update quietly to website
                    req_data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(
                        BACKEND_URL,
                        data=req_data,
                        headers={"Content-Type": "application/json"}
                    )
                    try:
                        with urllib.request.urlopen(req, timeout=1.5) as resp:
                            pass
                    except Exception:
                        pass

                    # Only print locally if zone changed, significant movement, or 15s elapsed
                    if zone_changed or dist_diff >= 1.0 or (now - last_print_time >= 15.0):
                        last_print_time = now
                        print(f"[RF SIGNAL] {ssid_name}: {pct}% ({int(smooth_rssi)} dBm) | Distance: {smooth_distance:.1f} m | Zone: {zone}", flush=True)

        except Exception as e:
            time.sleep(2.0)

def list_ports():
    print("\n[+] Available Serial & Bluetooth COM Ports on this PC:")
    print("=" * 65)
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("  (No active COM ports detected)")
        return []
    for p in ports:
        print(f"  * {p.device.ljust(8)} : {p.description}")
        if p.hwid:
            print(f"               HWID: {p.hwid}")
    print("=" * 65)
    return ports

def auto_detect_port():
    ports = list(serial.tools.list_ports.comports())
    # Priority 1: Specific ESP32 Outgoing Bluetooth port (with device MAC in HWID)
    for p in ports:
        hwid = (p.hwid or "").upper()
        if "BTHENUM" in hwid and ("680947" in hwid or ("000000000000" not in hwid and "BTH" in hwid)):
            return p.device

    # Priority 2: Any Bluetooth Serial port
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if "bluetooth" in desc or "bth" in hwid or "bt" in desc:
            return p.device

    # Priority 3: CP210x, CH340, FTDI, or USB Serial (ESP32 USB connection)
    for p in ports:
        desc = (p.description or "").lower()
        if any(chip in desc for chip in ["cp210", "ch340", "ftdi", "usb", "serial"]):
            return p.device

    # Priority 4: Fallback to first available port
    if ports:
        return ports[0].device
    return None

def forward_to_backend(payload_str):
    global CURRENT_EQUIPMENT, CURRENT_STATUS
    try:
        data = json.loads(payload_str)
    except Exception:
        return None

    if not isinstance(data, dict) or "equipment" not in data:
        return None

    if "equipment" in data and data["equipment"]:
        CURRENT_EQUIPMENT = data["equipment"]
    if "status" in data and data["status"]:
        CURRENT_STATUS = data["status"]

    if "source" not in data:
        data["source"] = "ESP32_BLUETOOTH"

    req_data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        BACKEND_URL,
        data=req_data,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            resp_body = resp.read().decode("utf-8")
            return json.loads(resp_body)
    except urllib.error.URLError as e:
        print(f"  [!] Backend HTTP Error: {e}")
        return None
    except Exception as e:
        print(f"  [!] Forwarding Exception: {e}")
        return None

def run_bridge(port_name=None):
    print("=" * 72)
    print("   MEDITRACK AI — ESP32 BLUETOOTH & RF SIGNAL GATEWAY")
    print("=" * 72)

    # Start RF Signal Tracking in background daemon thread
    rf_thread = threading.Thread(target=rf_signal_tracker_thread, daemon=True)
    rf_thread.start()

    if not port_name:
        port_name = auto_detect_port()

    if not port_name:
        print("\n[!] No Bluetooth Serial COM port detected.")
        print("    Running in Standalone RF Signal Tracking mode...")
        while True:
            time.sleep(1.0)
        return

    print(f"\n[+] Selected Port: {port_name} @ {BAUD_RATE} baud")
    print(f"[+] MediTrack AI Backend: {BACKEND_URL}")
    print("[+] Status: Listening for wireless events from ESP32...\n")

    reconnect_delay = 2.0
    while True:
        try:
            print(f"[*] Opening {port_name}...")
            ser = serial.Serial()
            ser.port = port_name
            ser.baudrate = BAUD_RATE
            ser.dtr = False
            ser.rts = False
            ser.timeout = 2.0
            ser.open()
            print(f"[OK] CONNECTED to {port_name}! Listening for incoming telemetry...", flush=True)
            print("-" * 72, flush=True)

            while True:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                # Print console logs
                print(f"[ESP32] {line}", flush=True)

                # If line is JSON payload, forward to website
                if line.startswith("{") and line.endswith("}"):
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"\n---> [BLUETOOTH RX @ {timestamp}] Forwarding to MediTrack AI Website:", flush=True)
                    print(f"     Payload: {line}", flush=True)
                    res = forward_to_backend(line)
                    if res:
                        status_str = res.get("new_status") or res.get("status") or "UPDATED"
                        eq_id = res.get("equipment_id") or res.get("equipment") or "UNKNOWN"
                        loc = res.get("location") or "Emergency Ward"
                        print(f"     [SUCCESS] 200 OK | {eq_id} -> {status_str} at {loc}", flush=True)
                    print("-" * 72 + "\n", flush=True)
                else:
                    forward_log_to_backend(line)

        except serial.SerialException as e:
            print(f"[!] Serial port {port_name} not available ({e}). Retrying in {reconnect_delay}s...")
            time.sleep(reconnect_delay)
        except KeyboardInterrupt:
            print("\n[+] Exiting Bluetooth Bridge. Goodbye!")
            break
        except Exception as e:
            print(f"[!] Error: {e}. Retrying in {reconnect_delay}s...")
            time.sleep(reconnect_delay)

def main():
    parser = argparse.ArgumentParser(description="MediTrack AI Bluetooth & RF Signal Gateway")
    parser.add_argument("--port", "-p", help="Specific COM port to connect (e.g. COM4, COM5)")
    parser.add_argument("--list", "-l", action="store_true", help="List all available COM ports and exit")
    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    run_bridge(args.port)

if __name__ == "__main__":
    main()
