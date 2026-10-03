import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from starlette.testclient import TestClient
from backend.app import app

def run_tests():
    client = TestClient(app)
    print("=== Testing Hardware Simulator & ESP32 Update Endpoints ===")

    # 1. Standalone Simulator Page Serving
    r_sim = client.get('/hardware-simulator')
    assert r_sim.status_code == 200, f"Expected 200 for /hardware-simulator, got {r_sim.status_code}"
    assert "ESP32-WROOM-32D" in r_sim.text
    assert "MFRC522 RFID Sensor" in r_sim.text
    print("[PASS] 1. GET /hardware-simulator serves dedicated hardware twin page (200 OK)")

    # 2. Alias route /simulator
    r_alias = client.get('/simulator')
    assert r_alias.status_code == 200
    print("[PASS] 2. GET /simulator alias route serves hardware twin page (200 OK)")

    # 3. Main Page Serving (GET /)
    r_index = client.get('/')
    assert r_index.status_code == 200
    assert "tab-hardware-sim" in r_index.text
    assert "Open Hardware Lab" in r_index.text
    print("[PASS] 3. GET / serves index.html with embedded Hardware Lab tab (200 OK)")

    # 4. Direct Root POST (as sent by ESP32 firmware SERVER_URL = "http://...:8000")
    r_root_post = client.post('/', json={"equipment": "WHEELCHAIR", "status": "IN_USE"})
    assert r_root_post.status_code == 200, f"Expected 200, got {r_root_post.status_code}: {r_root_post.text}"
    d_root = r_root_post.json()
    assert d_root['equipment_id'] == 'WC-007'
    assert d_root['new_status'] == 'IN_USE'
    print(f"[PASS] 4. POST / (Firmware direct compatibility) -> Updated {d_root['equipment_id']} to {d_root['new_status']}")

    # 5. POST /api/esp32/update for Ventilator
    r_vent = client.post('/api/esp32/update', json={"equipment": "MECHANICAL VENTILATOR", "status": "AVAILABLE"})
    assert r_vent.status_code == 200
    d_vent = r_vent.json()
    assert d_vent['equipment_id'] == 'VENT-04'
    assert d_vent['new_status'] == 'AVAILABLE'
    print(f"[PASS] 5. POST /api/esp32/update -> Updated {d_vent['equipment_id']} to {d_vent['new_status']}")

    # 6. POST /api/esp32/update for Stretcher
    r_st = client.post('/api/esp32/update', json={"equipment": "STRETCHER", "status": "IN_USE"})
    assert r_st.status_code == 200
    d_st = r_st.json()
    assert d_st['equipment_id'] == 'ST-003'
    print(f"[PASS] 6. POST /api/esp32/update -> Updated {d_st['equipment_id']} to {d_st['new_status']}")

    # 7. POST /api/esp32/equipment-update for Smart ICU Bed
    r_bed = client.post('/api/esp32/equipment-update', json={"equipment": "SMART ICU BED", "status": "AVAILABLE"})
    assert r_bed.status_code == 200
    d_bed = r_bed.json()
    assert d_bed['equipment_id'] == 'BD-ICU-01'
    print(f"[PASS] 7. POST /api/esp32/equipment-update -> Updated {d_bed['equipment_id']} to {d_bed['new_status']}")

    # 8. POST /api/esp32/update for Infusion Pump
    r_inf = client.post('/api/esp32/update', json={"equipment": "INFUSION PUMP", "status": "AVAILABLE"})
    assert r_inf.status_code == 200
    d_inf = r_inf.json()
    assert d_inf['equipment_id'] == 'INF-03'
    print(f"[PASS] 8. POST /api/esp32/update -> Updated {d_inf['equipment_id']} to {d_inf['new_status']}")

    # 9. Clean 404 on Unknown Equipment
    r_unk = client.post('/api/esp32/update', json={"equipment": "NONEXISTENT_MACHINE", "status": "AVAILABLE"})
    assert r_unk.status_code == 404
    print("[PASS] 9. Unknown equipment cleanly rejected with HTTP 404")

    # 10. Clean 400 on Missing Equipment Field
    r_bad = client.post('/api/esp32/update', json={"status": "AVAILABLE"})
    assert r_bad.status_code == 400
    print("[PASS] 10. Missing equipment field rejected with HTTP 400")

    print("\n[SUCCESS] ALL 10 HARDWARE SIMULATION ENDPOINT CHECKS PASSED WITH 100% SUCCESS!\n")

if __name__ == "__main__":
    run_tests()
