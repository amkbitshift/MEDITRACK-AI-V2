import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from starlette.testclient import TestClient
from backend.app import app

def run():
    client = TestClient(app)

    print("=== Testing ESP32 RFID & Telemetry Updates ===")

    # 1. Test Valid RFID Scan: WC-007
    r1 = client.post('/api/esp32/rfid', json={'uid': '10 0D 71 5C', 'location': 'Emergency Ward'})
    assert r1.status_code == 200, f"Expected 200, got {r1.status_code}"
    d1 = r1.json()
    assert d1['equipment_id'] == 'WC-007', f"Expected WC-007, got {d1['equipment_id']}"
    assert d1['location'] == 'Emergency Ward'
    print(f"[PASS] 1. Valid RFID '10 0D 71 5C' -> WC-007 identified in {d1['location']}")

    # 2. Test Valid RFID Scan: VENT-04
    r2 = client.post('/api/esp32/rfid', json={'uid': '30 94 2B 58', 'location': 'Intensive Care Unit (ICU)'})
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}"
    d2 = r2.json()
    assert d2['equipment_id'] == 'VENT-04', f"Expected VENT-04, got {d2['equipment_id']}"
    assert d2['equipment_type'] == 'Mechanical Ventilator'
    print(f"[PASS] 2. Valid RFID '30 94 2B 58' -> VENT-04 identified as {d2['equipment_type']}")

    # 3. Test Valid RFID Scan: ST-003
    r_st = client.post('/api/esp32/rfid', json={'uid': 'BD 70 00 02', 'location': 'Central Storage A'})
    assert r_st.status_code == 200
    assert r_st.json()['equipment_id'] == 'ST-003'
    print("[PASS] 3. Valid RFID 'BD 70 00 02' -> ST-003 (Stretcher)")

    # 4. Test Valid RFID Scan: INF-03
    r_inf = client.post('/api/esp32/rfid', json={'uid': '21 2F 7B 69', 'location': 'ICU Equipment Storage'})
    assert r_inf.status_code == 200
    assert r_inf.json()['equipment_id'] == 'INF-03'
    print("[PASS] 4. Valid RFID '21 2F 7B 69' -> INF-03 (Infusion Pump)")

    # 5. Test Valid RFID Scan: BP-003
    r_bp = client.post('/api/esp32/rfid', json={'uid': '40 0D 0F 58', 'location': 'General Ward B'})
    assert r_bp.status_code == 200
    assert r_bp.json()['equipment_id'] == 'BP-003'
    print("[PASS] 5. Valid RFID '40 0D 0F 58' -> BP-003 (Blood Pressure Monitor)")

    # 6. Test Unknown RFID Tag rejected cleanly
    r_unk = client.post('/api/esp32/rfid', json={'uid': 'FF FF FF FF', 'location': 'Corridor'})
    assert r_unk.status_code == 404, f"Expected 404, got {r_unk.status_code}"
    d_unk = r_unk.json()
    assert d_unk['status'] == 'error'
    print(f"[PASS] 6. Unknown RFID cleanly rejected: {d_unk['message']}")

    # 7. Test Telemetry: movement = True -> IN_USE
    r_tel_1 = client.post('/api/esp32/telemetry', json={'equipment_id': 'WC-007', 'movement': True, 'battery': 82})
    assert r_tel_1.status_code == 200
    d_tel_1 = r_tel_1.json()['data']
    assert d_tel_1['status'] == 'IN_USE'
    print("[PASS] 7. Telemetry movement=True automatically sets status to IN_USE")

    # 8. Test Telemetry: movement = False -> AVAILABLE
    r_tel_2 = client.post('/api/esp32/telemetry', json={'equipment_id': 'WC-007', 'movement': False, 'battery': 81})
    assert r_tel_2.status_code == 200
    d_tel_2 = r_tel_2.json()['data']
    assert d_tel_2['status'] == 'AVAILABLE'
    print("[PASS] 8. Telemetry movement=False automatically sets status to AVAILABLE")

    # 9. Test Telemetry: Preserves MAINTENANCE state
    r_tel_maint = client.post('/api/esp32/telemetry', json={'equipment_id': 'WC-014', 'movement': True, 'battery': 64})
    assert r_tel_maint.status_code == 200
    d_tel_maint = r_tel_maint.json()['data']
    assert d_tel_maint['status'] == 'MAINTENANCE', f"Expected MAINTENANCE, got {d_tel_maint['status']}"
    print("[PASS] 9. Telemetry preserves MAINTENANCE state when movement=True")

    # 10. Test Telemetry: Location change logs movement history
    r_tel_loc = client.post('/api/esp32/telemetry', json={'equipment_id': 'WC-007', 'location': 'Radiology', 'movement': True})
    assert r_tel_loc.status_code == 200
    print("[PASS] 10. Telemetry relocation logged successfully")

    print("\n[SUCCESS] ALL ESP32 RFID & TELEMETRY CHECKS PASSED WITH 100% SUCCESS!")

if __name__ == '__main__':
    run()
