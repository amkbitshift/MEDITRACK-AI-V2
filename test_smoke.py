import urllib.request
import json

def test_api(url, headers=None, method='GET', data=None):
    req = urllib.request.Request(url, headers=headers or {}, method=method)
    if data:
        req.add_header('Content-Type', 'application/json')
        body = json.dumps(data).encode('utf-8')
    else:
        body = None
    with urllib.request.urlopen(req, data=body) as resp:
        return json.loads(resp.read().decode('utf-8'))

def main():
    print("=== MediTrack AI API Smoke Test ===")
    
    # Nurse
    nurse = test_api('http://127.0.0.1:8000/api/dashboard/role-view', {'X-User-Role': 'NURSE', 'X-User-Id': 'user-nurse-1'})
    print(f"[OK] Nurse View Ward: {nurse['ward']} | Available: {nurse['stats']['available_in_ward']}")
    
    # Doctor
    doc = test_api('http://127.0.0.1:8000/api/dashboard/role-view', {'X-User-Role': 'DOCTOR', 'X-User-Id': 'user-doc-1'})
    print(f"[OK] Doctor View Dept: {doc['department']} | Critical Count: {doc['stats']['critical_count']}")
    
    # Equipment Manager
    mgr = test_api('http://127.0.0.1:8000/api/dashboard/role-view', {'X-User-Role': 'EQUIPMENT_MANAGER'})
    print(f"[OK] Equipment Manager: Total Assets: {mgr['stats']['total_equipment']}")
    
    # Admin
    admin = test_api('http://127.0.0.1:8000/api/dashboard/role-view', {'X-User-Role': 'ADMIN'})
    print(f"[OK] Admin View: System Health: {admin['stats']['system_health']}")

    # Blueprint
    bp = test_api('http://127.0.0.1:8000/api/blueprint')
    print(f"[OK] Blueprint Rooms: {len(bp['rooms'])} | Markers: {len(bp['equipment'])}")

    # Gynaecology
    gynae = test_api('http://127.0.0.1:8000/api/department/gynaecology')
    print(f"[OK] Gynaecology Trackable: {gynae['total_trackable']} | Shortages: {len(gynae['shortages'])} | Non-tracked: {len(gynae['non_tracked_instruments'])}")

    # ICU
    icu = test_api('http://127.0.0.1:8000/api/department/icu')
    print(f"[OK] ICU Trackable: {icu['total_trackable']} | Fixed Infra: {len(icu['fixed_infrastructure'])} | Beds: {len(icu['beds'])}")

    # Transfer test
    transfer_payload = {
        "equipment_id": "EQ-ICU-001",
        "to_ward": "GENERAL_WARD_A",
        "to_room": "Ward A - Bed 01",
        "reason": "Temporary transfer test"
    }
    t_res = test_api('http://127.0.0.1:8000/api/equipment/transfer', {'X-User-Role': 'EQUIPMENT_MANAGER'}, method='POST', data=transfer_payload)
    print(f"[OK] Transfer: {t_res['message']} (Logged movement ID: {t_res['movement']['id']})")

    # Move back
    return_payload = {
        "equipment_id": "EQ-ICU-001",
        "to_ward": "ICU",
        "to_room": "Bed 01",
        "reason": "Return to ICU"
    }
    r_res = test_api('http://127.0.0.1:8000/api/equipment/transfer', {'X-User-Role': 'EQUIPMENT_MANAGER'}, method='POST', data=return_payload)
    print(f"[OK] Return: {r_res['message']}")

    # Shortages
    shortages = test_api('http://127.0.0.1:8000/api/shortages')
    print(f"[OK] Shortage Predictions: {len(shortages)} active predictions")

    print("\n[SUCCESS] ALL SMOKE TESTS PASSED!")

if __name__ == '__main__':
    main()
