from starlette.testclient import TestClient
from backend.app import app
import json

def run_tests():
    client = TestClient(app)
    print("=== Running Comprehensive Verification Test ===")

    # 1. Nurse View
    resp = client.get('/api/dashboard/role-view', headers={'X-User-Role': 'NURSE', 'X-User-Id': 'user-nurse-1'})
    assert resp.status_code == 200, f"Nurse view failed: {resp.status_code}"
    nurse = resp.json()
    assert 'ward' in nurse and 'available_in_ward' in nurse['stats']
    print(f"[PASS] 1. Nurse View: Ward={nurse['ward']}, Available={nurse['stats']['available_in_ward']}")

    # 2. Doctor View
    resp = client.get('/api/dashboard/role-view', headers={'X-User-Role': 'DOCTOR', 'X-User-Id': 'user-doc-1'})
    assert resp.status_code == 200, f"Doctor view failed: {resp.status_code}"
    doc = resp.json()
    assert 'department' in doc and 'critical_count' in doc['stats']
    print(f"[PASS] 2. Doctor View: Dept={doc['department']}, CriticalCount={doc['stats']['critical_count']}")

    # 3. Equipment Manager View
    resp = client.get('/api/dashboard/role-view', headers={'X-User-Role': 'EQUIPMENT_MANAGER'})
    assert resp.status_code == 200, f"Mgr view failed: {resp.status_code}"
    mgr = resp.json()
    assert 'total_equipment' in mgr['stats']
    print(f"[PASS] 3. Equipment Manager View: Total={mgr['stats']['total_equipment']}")

    # 4. Admin View
    resp = client.get('/api/dashboard/role-view', headers={'X-User-Role': 'ADMIN'})
    assert resp.status_code == 200, f"Admin view failed: {resp.status_code}"
    admin = resp.json()
    assert 'system_health' in admin['stats']
    print(f"[PASS] 4. Admin View: Health={admin['stats']['system_health']}")

    # 5. Blueprint Architectural Map (20 rooms)
    resp = client.get('/api/blueprint')
    assert resp.status_code == 200
    bp = resp.json()
    assert len(bp['rooms']) in (20, 21), f"Expected 20-21 blueprint rooms, got {len(bp['rooms'])}"
    assert len(bp['equipment']) > 0
    print(f"[PASS] 5. Architectural Blueprint: Rooms={len(bp['rooms'])}, Equipment Markers={len(bp['equipment'])}")

    # 6. Gynaecology Digital Twin
    resp = client.get('/api/department/gynaecology')
    assert resp.status_code == 200
    gynae = resp.json()
    assert 'total_trackable' in gynae
    assert len(gynae['shortages']) > 0
    assert len(gynae['non_tracked_instruments']) > 0
    print(f"[PASS] 6. Gynaecology Twin: Trackable={gynae['total_trackable']}, Shortages={len(gynae['shortages'])}, NonTrackedSets={len(gynae['non_tracked_instruments'])}")

    # 7. ICU Digital Twin
    resp = client.get('/api/department/icu')
    assert resp.status_code == 200
    icu = resp.json()
    assert 'total_trackable' in icu
    assert len(icu['fixed_infrastructure']) > 0
    assert len(icu['beds']) > 0
    print(f"[PASS] 7. ICU Twin: Trackable={icu['total_trackable']}, FixedInfra={len(icu['fixed_infrastructure'])}, Beds={len(icu['beds'])}")

    # 8. Equipment Transfer Dispatch
    t_payload = {
        "equipment_id": "EQ-ICU-001",
        "to_ward": "GENERAL_WARD_A",
        "to_room": "Ward A - Bed 01",
        "reason": "Temporary transfer test"
    }
    resp = client.post('/api/equipment/transfer', headers={'X-User-Role': 'EQUIPMENT_MANAGER'}, json=t_payload)
    assert resp.status_code == 200
    t_res = resp.json()
    assert 'movement' in t_res and 'id' in t_res['movement']
    print(f"[PASS] 8. Equipment Transfer: Message={t_res['message']}, MovementID={t_res['movement']['id']}")

    # 9. Return Transfer
    r_payload = {
        "equipment_id": "EQ-ICU-001",
        "to_ward": "ICU",
        "to_room": "Bed 01",
        "reason": "Return to ICU"
    }
    resp = client.post('/api/equipment/transfer', headers={'X-User-Role': 'EQUIPMENT_MANAGER'}, json=r_payload)
    assert resp.status_code == 200
    r_res = resp.json()
    print(f"[PASS] 9. Return Transfer: Message={r_res['message']}")

    # 10. Emergency Shortage Intelligence
    resp = client.get('/api/shortages')
    assert resp.status_code == 200
    shortages = resp.json()
    assert len(shortages) > 0
    print(f"[PASS] 10. Shortage Intelligence: ActivePredictions={len(shortages)}")

    # 11. Strict RBAC Enforcement (403 Forbidden)
    resp = client.get('/api/maintenance/overview', headers={'X-User-Role': 'NURSE'})
    assert resp.status_code == 403, f"Nurse should be blocked from maintenance overview, got {resp.status_code}"
    print(f"[PASS] 11. RBAC Security: Nurse accessing Maintenance Overview blocked with 403 Forbidden")

    resp = client.get('/api/users', headers={'X-User-Role': 'DOCTOR'})
    assert resp.status_code == 403, f"Doctor should be blocked from User Admin, got {resp.status_code}"
    print(f"[PASS] 12. RBAC Security: Doctor accessing User Admin blocked with 403 Forbidden")

    resp = client.get('/api/users', headers={'X-User-Role': 'ADMIN'})
    assert resp.status_code == 200, f"Admin should have access to User Admin, got {resp.status_code}"
    print(f"[PASS] 13. RBAC Security: Admin successfully granted access to User Admin (200 OK)")

    # 12. AI Allocation Evaluation
    alloc_payload = {
        "equipment_type": "Wheelchair",
        "target_ward": "EMERGENCY",
        "priority": "Critical",
        "quantity": 2
    }
    resp = client.post('/api/allocation/evaluate', headers={'X-User-Role': 'EQUIPMENT_MANAGER'}, json=alloc_payload)
    assert resp.status_code == 200, f"Allocation failed: {resp.status_code}"
    alloc = resp.json()
    assert len(alloc.get('selected_units', [])) > 0
    print(f"[PASS] 14. AI Allocation Engine: Found {len(alloc['selected_units'])} units for emergency target")

    # 13. Vision AI Detections
    resp = client.get('/api/vision/detections', headers={'X-User-Role': 'EQUIPMENT_MANAGER'})
    assert resp.status_code == 200
    vision = resp.json()
    assert 'detections' in vision and 'reconciliation' in vision
    print(f"[PASS] 15. Vision AI Engine: Optical detections loaded successfully (Total detected: {vision['total_detected_items']})")

    # 14. Demand Forecast
    resp = client.get('/api/demand/forecast', headers={'X-User-Role': 'EQUIPMENT_MANAGER'})
    assert resp.status_code == 200
    fc = resp.json()
    assert 'timeline' in fc and 'predicted_6h' in fc
    print(f"[PASS] 16. Demand Forecasting AI: 24h diurnal predictions loaded successfully (Trend: {fc['trend']})")

    print("\n=======================================================")
    print("ALL 16 BACKEND VERIFICATION CHECKS PASSED WITH 100% SUCCESS!")
    print("=======================================================")

if __name__ == '__main__':
    run_tests()
