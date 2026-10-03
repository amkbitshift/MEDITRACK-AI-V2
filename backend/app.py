"""
MediTrack AI - Primary Backend Server
Starlette/FastAPI ASGI Application providing REST APIs, WebSockets, Role-Based Access Control (RBAC),
Architectural Hospital Blueprint, Equipment Location Tracking, and Department Digital Twins (ICU & Gynaecology).
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import json
import random
import asyncio
from datetime import datetime, timedelta
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.routing import Route, WebSocketRoute, Mount
from starlette.responses import JSONResponse, HTMLResponse, FileResponse
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database.db import get_connection, init_db
from database.seed_data import seed, RFID_MAPPINGS, USERS, WARDS
from ai.allocation import evaluate_equipment_allocation
from ai.maintenance import maintenance_model
from ai.demand_forecast import demand_forecaster
from ai.priority import calculate_emergency_priority
from ai.vision import vision_engine
from ai.assistant import query_mediai_assistant
from websocket.manager import ws_manager
from models.state_machine import (
    EquipmentState,
    EquipmentStateMachine,
    storage_verification_manager,
    temporary_hold_manager
)
from ai.synthetic_operations import (
    simulation_engine,
    MODALITIES,
    DEPARTMENTS
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

# Ensure DB initialized
init_db()

# --- Role-Based Access Control (RBAC) Helpers ---

ROLE_PERMISSIONS = {
    "NURSE": {
        "VIEW_WARD_EQUIPMENT", "VIEW_HOSPITAL_MAP", "CREATE_EQUIPMENT_REQUEST",
        "VIEW_EMERGENCY_ALERTS", "VIEW_DEPARTMENT", "REQUEST_EQUIPMENT", "VIEW_LIVE_EQUIPMENT"
    },
    "DOCTOR": {
        "VIEW_WARD_EQUIPMENT", "VIEW_HOSPITAL_MAP", "CREATE_EQUIPMENT_REQUEST",
        "VIEW_EMERGENCY_ALERTS", "VIEW_DEPARTMENT", "VIEW_ANALYTICS", "VIEW_CLINICAL_INSIGHTS", "VIEW_LIVE_EQUIPMENT"
    },
    "EQUIPMENT_MANAGER": {
        "ALL", "VIEW_WARD_EQUIPMENT", "VIEW_HOSPITAL_MAP", "CREATE_EQUIPMENT_REQUEST",
        "VIEW_EMERGENCY_ALERTS", "VIEW_MAINTENANCE", "MANAGE_EQUIPMENT", "ALLOCATE_EQUIPMENT",
        "VIEW_IOT", "VIEW_ANALYTICS", "VIEW_DEPARTMENT", "TRANSFER_EQUIPMENT",
        "SCHEDULE_MAINTENANCE", "VIEW_SHORTAGES", "VIEW_LIVE_EQUIPMENT", "VIEW_ALL_EQUIPMENT",
        "MANAGE_USERS", "VIEW_REPORTS"
    },
    "ADMIN": {
        "ALL", "VIEW_WARD_EQUIPMENT", "VIEW_HOSPITAL_MAP", "CREATE_EQUIPMENT_REQUEST",
        "VIEW_EMERGENCY_ALERTS", "VIEW_MAINTENANCE", "MANAGE_EQUIPMENT", "ALLOCATE_EQUIPMENT",
        "VIEW_IOT", "VIEW_ANALYTICS", "VIEW_DEPARTMENT", "TRANSFER_EQUIPMENT",
        "SCHEDULE_MAINTENANCE", "VIEW_SHORTAGES", "MANAGE_USERS", "MANAGE_SYSTEM",
        "VIEW_LIVE_EQUIPMENT", "VIEW_ALL_EQUIPMENT", "VIEW_REPORTS"
    }
}

def get_current_user_from_request(request):
    """
    Extracts the authenticated user based on:
    1. Header 'X-User-Id' or 'X-User-Role'
    2. Query param 'role' or 'user_id'
    Defaults to Marcus Reed (EQUIPMENT_MANAGER) for seamless testing if unspecified.
    """
    user_id = request.headers.get("X-User-Id") or request.query_params.get("user_id")
    role = request.headers.get("X-User-Role") or request.query_params.get("role")

    conn = get_connection()
    cursor = conn.cursor()

    if user_id:
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            conn.close()
            user_data = dict(row)
            user_data["permissions"] = json.loads(user_data["permissions"])
            return user_data

    if role:
        cursor.execute("SELECT * FROM users WHERE role = ? AND status = 'ACTIVE' LIMIT 1", (role.upper(),))
        row = cursor.fetchone()
        if row:
            conn.close()
            user_data = dict(row)
            user_data["permissions"] = json.loads(user_data["permissions"])
            return user_data

    # Default to Marcus Reed (Equipment Manager) for rich hackathon experience
    cursor.execute("SELECT * FROM users WHERE id = 'mgr-marcus'")
    row = cursor.fetchone()
    conn.close()
    if row:
        user_data = dict(row)
        user_data["permissions"] = json.loads(user_data["permissions"])
        return user_data

    return {
        "id": "mgr-marcus",
        "name": "Marcus Reed",
        "role": "EQUIPMENT_MANAGER",
        "department": "Equipment Control",
        "assigned_ward": "ward-storage-a",
        "permissions": list(ROLE_PERMISSIONS["EQUIPMENT_MANAGER"])
    }

def check_permission(user: dict, required_permission: str) -> bool:
    perms = set(user.get("permissions", []))
    return "ALL" in perms or required_permission in perms

# --- Authentication & User Management Endpoints ---

async def api_auth_login(request):
    """Handles login by email/password or quick Demo Role switch."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    demo_role = body.get("demo_role")
    email = body.get("email")

    conn = get_connection()
    cursor = conn.cursor()

    if demo_role:
        cursor.execute("SELECT * FROM users WHERE role = ? AND status = 'ACTIVE' LIMIT 1", (demo_role.upper(),))
    elif email:
        cursor.execute("SELECT * FROM users WHERE email = ? AND status = 'ACTIVE'", (email,))
    else:
        cursor.execute("SELECT * FROM users WHERE id = 'mgr-marcus'")

    user = cursor.fetchone()
    conn.close()

    if not user:
        return JSONResponse({"error": "Invalid credentials or demo role not found"}, status_code=401)

    user_dict = dict(user)
    user_dict["permissions"] = json.loads(user_dict["permissions"])
    # Fake session token
    token = f"meditrack_token_{user_dict['id']}_{random.randint(1000, 9999)}"

    return JSONResponse({
        "success": True,
        "token": token,
        "user": user_dict
    })

async def api_auth_me(request):
    """Returns profile and active permissions of current user."""
    user = get_current_user_from_request(request)
    return JSONResponse(user)

async def api_users_list(request):
    """Returns all users for RBAC Governance directory."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, department, assigned_ward, status, last_active, permissions FROM users ORDER BY name ASC")
    users = [dict(u) for u in cursor.fetchall()]
    conn.close()
    for u in users:
        try:
            u["permissions"] = json.loads(u["permissions"]) if isinstance(u["permissions"], str) else u["permissions"]
        except Exception:
            u["permissions"] = []
    return JSONResponse(users)

async def api_users_create(request):
    """Admin / Equipment Manager: creates a new staff user."""
    user = get_current_user_from_request(request)
    if not (check_permission(user, "MANAGE_USERS") or user.get("role") in ["ADMIN", "EQUIPMENT_MANAGER"]):
        return JSONResponse({"detail": "Access forbidden: insufficient role permissions to create users"}, status_code=403)

    body = await request.json()
    u_id = f"user-{random.randint(1000, 9999)}"
    name = body.get("name")
    email = body.get("email")
    role = body.get("role", "NURSE").upper()
    department = body.get("department", "General")
    assigned_ward = body.get("assigned_ward", "ward-gen-a")
    perms = list(ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["NURSE"]))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (id, name, email, password_hash, role, department, assigned_ward, status, last_active, permissions)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (u_id, name, email, "demo123", role, department, assigned_ward, "ACTIVE", datetime.now().isoformat(), json.dumps(perms)))
    conn.commit()
    conn.close()

    return JSONResponse({"success": True, "id": u_id, "name": name, "role": role})

async def api_users_update(request):
    """Admin / Equipment Manager: updates user role or department or status."""
    current_u = get_current_user_from_request(request)
    if not (check_permission(current_u, "MANAGE_USERS") or current_u.get("role") in ["ADMIN", "EQUIPMENT_MANAGER"]):
        return JSONResponse({"detail": "Access forbidden: insufficient role permissions to update users"}, status_code=403)

    target_id = request.path_params["id"]
    body = await request.json()
    role = body.get("role")
    dept = body.get("department")
    status = body.get("status")

    conn = get_connection()
    cursor = conn.cursor()
    if role:
        perms = list(ROLE_PERMISSIONS.get(role.upper(), ROLE_PERMISSIONS["NURSE"]))
        cursor.execute("UPDATE users SET role = ?, permissions = ? WHERE id = ?", (role.upper(), json.dumps(perms), target_id))
    if dept:
        cursor.execute("UPDATE users SET department = ? WHERE id = ?", (dept, target_id))
    if status:
        cursor.execute("UPDATE users SET status = ? WHERE id = ?", (status, target_id))
    conn.commit()
    conn.close()

    return JSONResponse({"success": True, "updated_id": target_id})

# --- Role-Specific Dashboard Views ---

async def api_role_dashboard(request):
    """
    Returns role-tailored dashboard data:
    - Nurse: Ward-specific equipment, requests, alerts, shortage warning for their ward
    - Doctor: Department-specific clinical equipment, ventilators/monitors, shortage predictions
    - Equipment Manager: Full 247-fleet operational control center
    - Admin: System metrics and governance
    """
    user = get_current_user_from_request(request)
    role = user.get("role", "EQUIPMENT_MANAGER")
    assigned_ward = user.get("assigned_ward", "ward-icu")
    department = user.get("department", "ICU")

    conn = get_connection()
    cursor = conn.cursor()

    if role == "NURSE":
        # Nurse sees only their ward's equipment and alerts
        cursor.execute("SELECT name FROM wards WHERE id = ?", (assigned_ward,))
        ward_row = cursor.fetchone()
        ward_name = ward_row["name"] if ward_row else "Intensive Care Unit (ICU)"

        cursor.execute("SELECT * FROM equipment WHERE location = ? ORDER BY type ASC, id ASC", (ward_name,))
        ward_equipment = [dict(r) for r in cursor.fetchall()]

        avail = [e for e in ward_equipment if e["status"] == "AVAILABLE"]
        in_use = [e for e in ward_equipment if e["status"] == "IN_USE"]
        maint = [e for e in ward_equipment if e["status"] == "MAINTENANCE"]

        # Ward-specific shortage predictions
        cursor.execute("SELECT * FROM shortage_predictions WHERE ward_id = ? OR ward_name = ?", (assigned_ward, ward_name))
        shortages = [dict(s) for s in cursor.fetchall()]

        # Ward requests
        cursor.execute("SELECT * FROM equipment_requests WHERE ward_id = ? ORDER BY created_at DESC LIMIT 5", (assigned_ward,))
        requests = [dict(rq) for rq in cursor.fetchall()]
        conn.close()

        return JSONResponse({
            "role": "NURSE",
            "ward": ward_name,
            "ward_id": assigned_ward,
            "ward_name": ward_name,
            "user_name": user["name"],
            "stats": {
                "available_in_ward": len(avail),
                "in_use": len(in_use),
                "maintenance": len(maint),
                "critical_count": 2,
                "total_ward_equipment": len(ward_equipment)
            },
            "available_count": len(avail),
            "in_use_count": len(in_use),
            "maintenance_count": len(maint),
            "total_ward_equipment": len(ward_equipment),
            "equipment_summary": {
                "icu_beds_available": sum(1 for e in avail if "Bed" in e["type"]),
                "infusion_pumps_available": sum(1 for e in avail if "Infusion" in e["type"]),
                "defibrillators_available": sum(1 for e in avail if "Defibrillator" in e["type"]),
                "ventilators_available": sum(1 for e in avail if "Ventilator" in e["type"]),
                "monitors_available": sum(1 for e in avail if "Monitor" in e["type"]),
                "wheelchairs_available": sum(1 for e in avail if "Wheelchair" in e["type"])
            },
            "shortage_warnings": shortages,
            "recent_requests": requests,
            "available_items": avail[:10],
            "in_use_items": in_use[:10]
        })

    elif role == "DOCTOR":
        # Doctor sees department equipment availability and clinical shortage risks
        dept_name = department if department != "General" else "ICU"

        cursor.execute("SELECT * FROM equipment WHERE department LIKE ? OR location LIKE ? ORDER BY status ASC", (f"%{dept_name}%", f"%{dept_name}%"))
        dept_equipment = [dict(r) for r in cursor.fetchall()]

        # ICU Ventilators & Critical Life Support
        cursor.execute("SELECT * FROM equipment WHERE type LIKE '%Ventilator%'")
        ventilators = [dict(v) for v in cursor.fetchall()]

        cursor.execute("SELECT * FROM shortage_predictions WHERE ward_name LIKE ? OR explanation LIKE ?", (f"%{dept_name}%", f"%{dept_name}%"))
        dept_shortages = [dict(s) for s in cursor.fetchall()]
        conn.close()

        return JSONResponse({
            "role": "DOCTOR",
            "user_name": user["name"],
            "department": dept_name,
            "stats": {
                "critical_count": 4,
                "available": sum(1 for e in dept_equipment if e["status"] == "AVAILABLE"),
                "in_use": sum(1 for e in dept_equipment if e["status"] == "IN_USE"),
                "shortage_risks": len(dept_shortages)
            },
            "total_dept_equipment": len(dept_equipment),
            "available_count": sum(1 for e in dept_equipment if e["status"] == "AVAILABLE"),
            "in_use_count": sum(1 for e in dept_equipment if e["status"] == "IN_USE"),
            "critical_life_support": {
                "ventilators_available": sum(1 for v in ventilators if v["status"] == "AVAILABLE"),
                "ventilators_in_use": sum(1 for v in ventilators if v["status"] == "IN_USE"),
                "ventilators_predicted_requirement": 11,
                "shortage_risk": True,
                "ai_recommendation": "Prepare 1 additional ventilator for ICU within the next 3 hours."
            },
            "shortage_predictions": dept_shortages,
            "clinical_equipment": dept_equipment[:15]
        })

    elif role == "ADMIN":
        cursor.execute("SELECT COUNT(*) as total FROM users")
        user_count = cursor.fetchone()["total"]
        cursor.execute("SELECT * FROM shortage_predictions ORDER BY id ASC")
        all_shortages = [dict(s) for s in cursor.fetchall()]
        conn.close()

        return JSONResponse({
            "role": "ADMIN",
            "user_name": user["name"],
            "stats": {
                "system_health": "99.8%",
                "total_users": user_count,
                "active_nodes": 8,
                "total_equipment": 247
            },
            "total_equipment": 247,
            "available": 132,
            "in_use": 96,
            "maintenance": 19,
            "system_health": "99.8%",
            "shortage_predictions": all_shortages
        })

    else:
        # Equipment Manager: Full Operational Control Center
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'AVAILABLE' THEN 1 ELSE 0 END) as available,
                SUM(CASE WHEN status = 'IN_USE' THEN 1 ELSE 0 END) as in_use,
                SUM(CASE WHEN status = 'MAINTENANCE' THEN 1 ELSE 0 END) as maintenance,
                SUM(CASE WHEN battery < 20 THEN 1 ELSE 0 END) as critical_battery,
                SUM(CASE WHEN health_score < 75 THEN 1 ELSE 0 END) as critical_health
            FROM equipment
        """)
        row = cursor.fetchone()

        cursor.execute("SELECT COUNT(*) as count FROM shortage_predictions WHERE severity = 'HIGH'")
        shortage_count = cursor.fetchone()["count"]

        cursor.execute("SELECT * FROM shortage_predictions ORDER BY id ASC")
        all_shortages = [dict(s) for s in cursor.fetchall()]
        conn.close()

        return JSONResponse({
            "role": "EQUIPMENT_MANAGER",
            "user_name": user["name"],
            "stats": {
                "total_equipment": 247,
                "available": 132,
                "in_use": 96,
                "maintenance": 19,
                "critical_alerts": 7,
                "shortage_risks": 4,
                "ai_recommendations": 12
            },
            "total_equipment": 247,  # Presentation fleet scale
            "actual_db_equipment": row["total"],
            "available": 132,
            "in_use": 96,
            "maintenance": 19,
            "critical_alerts": 7,
            "shortage_risks": 4,
            "ai_recommendations": 12,
            "shortage_predictions": all_shortages
        })

# --- Architectural Hospital Blueprint & Equipment Location ---

BLUEPRINT_ROOMS = [
    {"id": "room-entrance", "name": "Main Entrance", "category": "Public Access", "x": 42.0, "y": 90.0, "w": 16.0, "h": 8.0, "label": "MAIN ENTRANCE"},
    {"id": "room-reception", "name": "Reception & Waiting Area", "category": "Public / Triage", "x": 36.0, "y": 74.0, "w": 28.0, "h": 14.0, "label": "RECEPTION / WAITING AREA"},
    {"id": "room-emergency", "name": "Emergency Ward & Trauma Bay", "category": "Clinical Critical", "x": 68.0, "y": 8.0, "w": 28.0, "h": 24.0, "label": "EMERGENCY & TRAUMA"},
    {"id": "room-icu", "name": "Intensive Care Unit (ICU)", "category": "Critical Life Support", "x": 68.0, "y": 56.0, "w": 28.0, "h": 32.0, "label": "INTENSIVE CARE UNIT (ICU)"},
    {"id": "room-gynae", "name": "Gynaecology Department", "category": "Maternal & Women Care", "x": 4.0, "y": 56.0, "w": 30.0, "h": 32.0, "label": "GYNAECOLOGY DEPT"},
    {"id": "room-gen-a", "name": "General Ward A", "category": "Inpatient Care", "x": 4.0, "y": 8.0, "w": 30.0, "h": 22.0, "label": "GENERAL WARD A"},
    {"id": "room-gen-b", "name": "General Ward B", "category": "Inpatient Care", "x": 4.0, "y": 32.0, "w": 30.0, "h": 22.0, "label": "GENERAL WARD B"},
    {"id": "room-ot", "name": "Operation Theatre (OT)", "category": "Surgical Suite", "x": 36.0, "y": 8.0, "w": 28.0, "h": 20.0, "label": "OPERATION THEATRE"},
    {"id": "room-storage-a", "name": "Central Storage A", "category": "Logistics & Fleet", "x": 36.0, "y": 30.0, "w": 17.0, "h": 18.0, "label": "CENTRAL STORAGE A"},
    {"id": "room-storage-b", "name": "Annex Storage B (Repairs)", "category": "Maintenance Workshop", "x": 36.0, "y": 50.0, "w": 14.0, "h": 22.0, "label": "ANNEX STORAGE B (REPAIRS)"},
    {"id": "room-control", "name": "Equipment Control Room", "category": "Control Center", "x": 51.0, "y": 50.0, "w": 13.0, "h": 22.0, "label": "EQUIPMENT CONTROL"},
    {"id": "room-radiology", "name": "Radiology & Diagnostic Imaging", "category": "Diagnostic Imaging", "x": 68.0, "y": 34.0, "w": 16.0, "h": 20.0, "label": "RADIOLOGY & IMAGING"},
    {"id": "room-radiology-storage", "name": "Clustered Chair Zone (Radiology Wheelchair Storage)", "category": "Wheelchair Fleet Storage", "x": 84.0, "y": 34.0, "w": 12.0, "h": 20.0, "label": "CLUSTERED CHAIR ZONE"},
    {"id": "room-nurse-station", "name": "Central Nurse Station", "category": "Clinical Support", "x": 54.0, "y": 30.0, "w": 10.0, "h": 18.0, "label": "NURSE STATION"},
    {"id": "room-doctor-station", "name": "Doctor Station & Consultation", "category": "Clinical Consultation", "x": 4.0, "y": 90.0, "w": 14.0, "h": 8.0, "label": "DOCTOR STATION"},
    {"id": "room-pharmacy", "name": "Central Pharmacy", "category": "Support Services", "x": 20.0, "y": 90.0, "w": 19.0, "h": 8.0, "label": "PHARMACY"},
    {"id": "room-lab", "name": "Pathology Laboratory", "category": "Diagnostic Lab", "x": 66.0, "y": 90.0, "w": 18.0, "h": 8.0, "label": "PATHOLOGY LAB"},
    {"id": "room-elevators", "name": "Service Elevators A & B", "category": "Transit Core", "x": 34.0, "y": 29.0, "w": 2.0, "h": 19.0, "label": "ELEVATORS"},
    {"id": "room-staircase-n", "name": "Emergency Staircase North", "category": "Transit Egress", "x": 64.0, "y": 8.0, "w": 3.0, "h": 11.0, "label": "STAIRS N"},
    {"id": "room-staircase-s", "name": "Emergency Staircase South", "category": "Transit Egress", "x": 86.0, "y": 90.0, "w": 10.0, "h": 8.0, "label": "STAIRS S"},
    {"id": "room-toilets", "name": "Sanitization & Restrooms", "category": "Facilities", "x": 64.0, "y": 20.0, "w": 3.0, "h": 12.0, "label": "TOILETS"}
]

async def api_blueprint(request):
    """
    Returns schematic architectural hospital blueprint floor plan
    with rooms, corridors, facilities, and live positioned equipment markers.
    """
    user = get_current_user_from_request(request)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equipment ORDER BY id ASC")
    items = [dict(r) for r in cursor.fetchall()]
    conn.close()

    # Apply role scoping if Nurse
    if user.get("role") == "NURSE":
        assigned_ward = user.get("assigned_ward", "ward-icu")
        # Find ward name
        w_name = "Intensive Care Unit (ICU)" if "icu" in assigned_ward else "Emergency Ward"
        # Filter items or highlight ward items
        for it in items:
            it["is_in_my_ward"] = (it["location"] == w_name)

    return JSONResponse({
        "blueprint_version": "2.4.0-Architectural",
        "hospital_name": "St. Jude Metro AI Hospital",
        "dimensions": {"width": 1000, "height": 650},
        "rooms": BLUEPRINT_ROOMS,
        "equipment": items
    })

async def api_equipment_location_search(request):
    """Searches equipment and returns exact coordinates on hospital blueprint."""
    params = request.query_params
    query = params.get("search", "").strip().lower()
    eq_type = params.get("type", "")
    ward = params.get("ward", "")
    status = params.get("status", "")

    conn = get_connection()
    cursor = conn.cursor()
    sql = "SELECT * FROM equipment WHERE 1=1"
    args = []

    if query:
        sql += " AND (LOWER(id) LIKE ? OR LOWER(name) LIKE ? OR LOWER(type) LIKE ? OR LOWER(location) LIKE ?)"
        args.extend([f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"])
    if eq_type:
        sql += " AND type = ?"
        args.append(eq_type)
    if ward:
        sql += " AND location LIKE ?"
        args.append(f"%{ward}%")
    if status:
        sql += " AND status = ?"
        args.append(status)

    sql += " ORDER BY id ASC"
    cursor.execute(sql, args)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return JSONResponse(rows)

async def api_equipment_movements(request):
    """Returns equipment movement history."""
    eq_id = request.query_params.get("equipment_id")
    conn = get_connection()
    cursor = conn.cursor()
    if eq_id:
        cursor.execute("SELECT * FROM equipment_movements WHERE equipment_id = ? ORDER BY movement_time DESC LIMIT 10", (eq_id,))
    else:
        cursor.execute("SELECT * FROM equipment_movements ORDER BY movement_time DESC LIMIT 20")
    movements = [dict(m) for m in cursor.fetchall()]
    conn.close()
    return JSONResponse(movements)

async def api_equipment_transfer(request):
    """Transfers equipment to a new ward/room, animates path, and logs movement."""
    user = get_current_user_from_request(request)
    if not check_permission(user, "TRANSFER_EQUIPMENT") and user.get("role") != "DOCTOR":
        return JSONResponse({"detail": "Access forbidden: insufficient role permissions to transfer equipment"}, status_code=403)

    body = await request.json()
    eq_id = body.get("equipment_id")
    to_ward = body.get("to_ward", "Emergency Ward")
    to_room = body.get("to_room", "General Area")
    reason = body.get("reason", "Clinical reallocation")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT location, coordinates_x, coordinates_y FROM equipment WHERE id = ?", (eq_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        return JSONResponse({"error": "Equipment not found"}, status_code=404)

    from_loc = item["location"]
    now_str = datetime.now().isoformat()

    # Normalize ward name
    ward_name_map = {
        "GENERAL_WARD_A": "General Ward A",
        "GENERAL_WARD_B": "General Ward B",
        "EMERGENCY": "Emergency Ward",
        "EMERGENCY_WARD": "Emergency Ward",
        "ICU": "Intensive Care Unit (ICU)",
        "GYNAECOLOGY": "Gynaecology Department",
        "STORAGE": "Central Storage A",
        "MAINTENANCE": "Annex Storage B (Repairs)"
    }
    to_ward_display = ward_name_map.get(to_ward.upper(), to_ward)

    # Determine destination coordinates based on ward
    target_ward = next((w for w in WARDS if w["name"] == to_ward_display or w["id"] == to_ward or to_ward_display.lower() in w["name"].lower()), WARDS[0])
    new_x = target_ward["pos_x"] + random.uniform(-2.0, 2.0)
    new_y = target_ward["pos_y"] + random.uniform(-2.0, 2.0)

    cursor.execute("""
        UPDATE equipment 
        SET location = ?, room = ?, coordinates_x = ?, coordinates_y = ?, last_updated = ?
        WHERE id = ?
    """, (to_ward_display, to_room, round(new_x, 1), round(new_y, 1), now_str, eq_id))

    cursor.execute("""
        INSERT INTO equipment_movements (equipment_id, from_location, to_location, movement_time, duration_seconds, rfid_scanned_by, status, route_description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (eq_id, from_loc, to_ward_display, now_str, 55, user.get("id", "mgr-marcus"), "COMPLETED", f"Transfer requested by {user.get('name')}: {reason}"))
    movement_id = cursor.lastrowid

    conn.commit()
    conn.close()

    # Broadcast movement for real-time blueprint animation
    event = {
        "type": "EQUIPMENT_MOVED",
        "equipment_id": eq_id,
        "from_location": from_loc,
        "to_location": to_ward_display,
        "new_coordinates": {"x": new_x, "y": new_y},
        "moved_by": user.get("name"),
        "timestamp": now_str
    }
    await ws_manager.broadcast(event)

    return JSONResponse({
        "success": True,
        "message": f"Successfully transferred {eq_id} to {to_ward_display}",
        "movement": {
            "id": movement_id,
            "equipment_id": eq_id,
            "from_location": from_loc,
            "to_location": to_ward_display,
            "timestamp": now_str
        },
        "event": event
    })

async def api_maintenance_action(request):
    """Sends equipment to maintenance or marks maintenance complete."""
    user = get_current_user_from_request(request)
    if not check_permission(user, "SCHEDULE_MAINTENANCE"):
        return JSONResponse({"detail": "Access forbidden: insufficient role permissions to schedule maintenance"}, status_code=403)

    body = await request.json()
    eq_id = body.get("equipment_id")
    action = body.get("action", "send_to_maintenance")  # or "complete_maintenance"
    now_str = datetime.now().isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    if action == "send_to_maintenance":
        new_loc = "Annex Storage B (Repairs)"
        new_room = "Repairs Workshop"
        new_status = "MAINTENANCE"
        cx, cy = 50.0, 85.0
        desc = "Moved to maintenance workshop for overhaul"
    else:
        new_loc = "Central Storage A"
        new_room = "Fleet Storage Bay"
        new_status = "AVAILABLE"
        cx, cy = 48.0, 48.0
        desc = "Maintenance completed, returned to active fleet"

    cursor.execute("""
        UPDATE equipment 
        SET status = ?, location = ?, room = ?, coordinates_x = ?, coordinates_y = ?, 
            health_score = CASE WHEN ? = 'complete_maintenance' THEN 98 ELSE health_score END,
            days_since_maintenance = CASE WHEN ? = 'complete_maintenance' THEN 0 ELSE days_since_maintenance END,
            last_updated = ?
        WHERE id = ?
    """, (new_status, new_loc, new_room, cx, cy, action, action, now_str, eq_id))

    cursor.execute("""
        INSERT INTO equipment_movements (equipment_id, from_location, to_location, movement_time, duration_seconds, rfid_scanned_by, status, route_description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (eq_id, "Current Location", new_loc, now_str, 60, user.get("id"), "COMPLETED", desc))

    conn.commit()
    conn.close()

    # Broadcast event
    await ws_manager.broadcast({
        "type": "MAINTENANCE_STATUS_CHANGED",
        "equipment_id": eq_id,
        "status": new_status,
        "location": new_loc,
        "coordinates": {"x": cx, "y": cy}
    })

    return JSONResponse({"success": True, "equipment_id": eq_id, "status": new_status, "location": new_loc})

# --- Emergency Shortage Predictions ---

async def api_shortages_list(request):
    """Returns all active AI shortage predictions across hospital wards."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM shortage_predictions ORDER BY time_to_shortage_hours ASC")
    shortages = [dict(s) for s in cursor.fetchall()]
    conn.close()
    return JSONResponse(shortages)

async def api_shortages_ward(request):
    """Returns ward-specific shortage predictions."""
    ward_id = request.path_params["ward_id"]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM shortage_predictions WHERE ward_id = ? OR ward_name LIKE ?", (ward_id, f"%{ward_id}%"))
    shortages = [dict(s) for s in cursor.fetchall()]
    conn.close()
    return JSONResponse(shortages)

# --- Department Digital Twins (Gynaecology & ICU) ---

async def api_dept_gynaecology(request):
    """Digital twin data for Gynaecology Department."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equipment WHERE department = 'Gynaecology' OR location LIKE '%Gynaecology%'")
    tracked = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM shortage_predictions WHERE ward_name LIKE '%Gynaecology%'")
    shortages = [dict(s) for s in cursor.fetchall()]
    conn.close()

    # Non-tracked clinical instruments list (explicitly documented as instruments, not IoT tags)
    clinical_instruments = [
        {"name": "Cusco Vaginal Speculum (Small/Med/Large)", "category": "Reusable Stainless Steel", "sterilization_status": "AUTOCLAVED", "qty_in_stock": 24},
        {"name": "Sims Double-Ended Vaginal Speculum", "category": "Reusable Stainless Steel", "sterilization_status": "AUTOCLAVED", "qty_in_stock": 16},
        {"name": "Novak Endometrial Biopsy Curettes", "category": "Diagnostic Instrument", "sterilization_status": "STERILE PACK", "qty_in_stock": 18},
        {"name": "Tischler Cervical Biopsy Forceps", "category": "Specialized Biopsy", "sterilization_status": "STERILE PACK", "qty_in_stock": 8},
        {"name": "Hegar Uterine Dilator Set (1-10mm)", "category": "Surgical Dilators", "sterilization_status": "AUTOCLAVED", "qty_in_stock": 6},
        {"name": "Disposable Sterile Pap Smear Kits", "category": "Consumables", "sterilization_status": "READY", "qty_in_stock": 120}
    ]

    return JSONResponse({
        "department_name": "Gynaecology Department",
        "ward_id": "ward-gynae",
        "total_trackable": len(tracked),
        "total_tracked_assets": len(tracked),
        "available_tracked_assets": sum(1 for e in tracked if e["status"] == "AVAILABLE"),
        "in_use_tracked_assets": sum(1 for e in tracked if e["status"] == "IN_USE"),
        "maintenance_assets": sum(1 for e in tracked if e["status"] == "MAINTENANCE"),
        "tracked_equipment": tracked,
        "shortages": shortages,
        "shortage_predictions": shortages,
        "non_tracked_instruments": clinical_instruments,
        "clinical_instruments_untracked": clinical_instruments,
        "rooms": [
            {"id": "gyn-exam-1", "name": "Examination Room 1", "equipment_ids": ["ET-GYN-01", "EL-GYN-01"]},
            {"id": "gyn-ultrasound", "name": "Ultrasound Room", "equipment_ids": ["US-GYN-01", "US-GYN-02"]},
            {"id": "gyn-ctg", "name": "CTG Room", "equipment_ids": ["CTG-01", "FD-GYN-01"]},
            {"id": "gyn-procedure", "name": "Procedure Room", "equipment_ids": ["COLP-01", "HYST-01"]},
            {"id": "gyn-lap", "name": "Laparoscopy Room", "equipment_ids": ["LAP-01", "ESU-01"]}
        ]
    })

async def api_dept_icu(request):
    """Digital twin data for Intensive Care Unit (ICU)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equipment WHERE department = 'ICU' OR location LIKE '%ICU%'")
    tracked = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM shortage_predictions WHERE ward_name LIKE '%ICU%'")
    shortages = [dict(s) for s in cursor.fetchall()]
    conn.close()

    # Fixed Infrastructure (Non-movable assets clearly distinguished)
    fixed_infrastructure = [
        {"name": "Central Oxygen Wall Pipeline Outlets", "type": "Gas Pipeline", "status": "PRESSURE NOMINAL (4.2 BAR)", "coverage": "Beds 01–04"},
        {"name": "Medical Compressed Air Pipeline Outlets", "type": "Air Pipeline", "status": "PRESSURE NOMINAL (4.0 BAR)", "coverage": "Beds 01–04"},
        {"name": "Central Hospital Vacuum Suction Ports", "type": "Vacuum Suction", "status": "NEGATIVE PRESSURE ACTIVE (-60 kPa)", "coverage": "Beds 01–04"},
        {"name": "Overhead Dual-Arm ICU Surgical Pendant Bridges", "type": "Power & Data Pendant", "status": "ENERGIZED / UPS PROTECTED", "coverage": "Beds 01–04"}
    ]

    return JSONResponse({
        "department_name": "Intensive Care Unit (ICU)",
        "ward_id": "ward-icu",
        "bed_capacity": 20,
        "occupied_beds": 18,
        "total_trackable": len(tracked),
        "total_tracked_assets": len(tracked),
        "available_tracked_assets": sum(1 for e in tracked if e["status"] == "AVAILABLE"),
        "in_use_tracked_assets": sum(1 for e in tracked if e["status"] == "IN_USE"),
        "maintenance_assets": sum(1 for e in tracked if e["status"] == "MAINTENANCE"),
        "tracked_equipment": tracked,
        "fixed_infrastructure": fixed_infrastructure,
        "shortages": shortages,
        "shortage_predictions": shortages,
        "beds": [
            {"bed_id": "ICU Bed 01", "bed_eq": "BD-ICU-01", "monitor_eq": "MON-ICU-01", "ventilator_eq": "VENT-01", "status": "OCCUPIED (CRITICAL)"},
            {"bed_id": "ICU Bed 02", "bed_eq": "BD-ICU-02", "monitor_eq": "MON-ICU-02", "ventilator_eq": "VENT-02", "status": "OCCUPIED (HIGH)"},
            {"bed_id": "ICU Bed 03", "bed_eq": "BD-ICU-03", "monitor_eq": "MON-ICU-03", "ventilator_eq": "VENT-03", "status": "AVAILABLE (STANDBY)"},
            {"bed_id": "ICU Bed 04", "bed_eq": "BD-ICU-04", "monitor_eq": "MON-ICU-04", "ventilator_eq": "VENT-04", "status": "AVAILABLE (STANDBY)"}
        ]
    })

# --- Existing Core REST Endpoints (Preserved) ---

async def api_stats(request):
    """Returns top KPI statistics for executive dashboard."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'AVAILABLE' THEN 1 ELSE 0 END) as available,
            SUM(CASE WHEN status = 'IN_USE' THEN 1 ELSE 0 END) as in_use,
            SUM(CASE WHEN status = 'MAINTENANCE' THEN 1 ELSE 0 END) as maintenance,
            SUM(CASE WHEN battery < 20 THEN 1 ELSE 0 END) as critical_battery,
            SUM(CASE WHEN health_score < 75 THEN 1 ELSE 0 END) as critical_health
        FROM equipment
    """)
    row = cursor.fetchone()
    conn.close()

    return JSONResponse({
        "total_equipment": row["total"],
        "total_growth": "+8.2%",
        "available": row["available"],
        "available_growth": "+4.1%",
        "in_use": row["in_use"],
        "in_use_growth": "+6.7%",
        "maintenance": row["maintenance"],
        "maintenance_growth": "-3.2%",
        "critical_alerts": (row["critical_battery"] or 0) + (row["critical_health"] or 0) + 2,
        "recommendations_count": 6,
        "active_wards": 8,
        "iot_connected_devices": 14,
        "hospital_name": "St. Jude Metro AI Hospital",
        "system_status": "ONLINE - ALL AI NODES OPERATIONAL"
    })

async def api_equipment_list(request):
    """Returns searchable and filterable equipment list."""
    user = get_current_user_from_request(request)
    query_params = request.query_params
    search = query_params.get("search", "").strip().lower()
    eq_type = query_params.get("type", "").strip()
    status = query_params.get("status", "").strip()
    location = query_params.get("location", "").strip()

    # Scope for Nurse if not authorized to view all equipment
    if user.get("role") == "NURSE" and not check_permission(user, "VIEW_ALL_EQUIPMENT"):
        assigned_ward = user.get("assigned_ward", "ward-icu")
        w_name = "Intensive Care Unit (ICU)" if "icu" in assigned_ward else "Emergency Ward"
        if not location:
            location = w_name

    conn = get_connection()
    cursor = conn.cursor()
    
    sql = "SELECT * FROM equipment WHERE 1=1"
    params = []

    if search:
        sql += " AND (id LIKE ? OR name LIKE ? OR type LIKE ? OR location LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])
    if eq_type:
        sql += " AND type = ?"
        params.append(eq_type)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if location:
        sql += " AND location LIKE ?"
        params.append(f"%{location}%")

    sql += " ORDER BY id ASC"
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        d["failure_risk"] = max(2, min(95, int(100 - d["health_score"] + (d["days_since_maintenance"] * 0.25))))
        result.append(d)

    return JSONResponse(result)

async def api_equipment_detail(request):
    """Detailed profile for a specific equipment piece."""
    eq_id = request.path_params["id"]
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equipment WHERE id = ?", (eq_id,))
    item = cursor.fetchone()
    
    cursor.execute("SELECT * FROM sensor_telemetry WHERE equipment_id = ? ORDER BY id DESC LIMIT 10", (eq_id,))
    telemetry = [dict(t) for t in cursor.fetchall()]

    cursor.execute("SELECT * FROM equipment_movements WHERE equipment_id = ? ORDER BY movement_time DESC LIMIT 5", (eq_id,))
    movements = [dict(m) for m in cursor.fetchall()]
    conn.close()

    if not item:
        return JSONResponse({"error": "Equipment not found"}, status_code=404)

    diagnostics = maintenance_model.analyze_equipment(eq_id)

    return JSONResponse({
        "equipment": dict(item),
        "telemetry_history": telemetry,
        "movement_history": movements,
        "ai_diagnostics": diagnostics
    })

async def api_wards(request):
    """Returns ward floor plan and occupancy metrics."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wards ORDER BY name ASC")
    wards = [dict(w) for w in cursor.fetchall()]
    
    for w in wards:
        cursor.execute("SELECT COUNT(*) as count FROM equipment WHERE location LIKE ?", (f"%{w['name']}%",))
        w["equipment_count"] = cursor.fetchone()["count"]

    conn.close()
    return JSONResponse(wards)

async def api_allocation_evaluate(request):
    """Evaluates multi-criteria allocation optimization."""
    user = get_current_user_from_request(request)
    if not check_permission(user, "ALLOCATE_EQUIPMENT"):
        return JSONResponse({"detail": "Access forbidden: insufficient role permissions to evaluate equipment allocation"}, status_code=403)

    try:
        body = await request.json()
    except Exception:
        body = {}

    ward_id = body.get("ward_id") or body.get("target_ward", "ward-emergency")
    eq_type = body.get("equipment_type", "Wheelchair")
    quantity = int(body.get("quantity", 3))
    priority = body.get("priority", "Emergency")
    weights = body.get("weights", None)

    evaluation = evaluate_equipment_allocation(ward_id, eq_type, quantity, priority, weights)
    evaluation["selected_units"] = evaluation.get("selected_equipment", [])
    return JSONResponse(evaluation)

async def api_allocation_confirm(request):
    """Confirms allocation, updates DB, animates transit on blueprint, and logs movement."""
    user = get_current_user_from_request(request)
    if not check_permission(user, "ALLOCATE_EQUIPMENT"):
        return JSONResponse({"detail": "Access forbidden: insufficient role permissions to confirm equipment allocation"}, status_code=403)

    body = await request.json()
    ward_name = body.get("ward_name", "Emergency Ward")
    equipment_ids = body.get("equipment_ids", [])
    now_str = datetime.now().isoformat()

    conn = get_connection()
    cursor = conn.cursor()
    for eq_id in equipment_ids:
        cursor.execute("""
            UPDATE equipment 
            SET status = 'RESERVED', location = ?, last_updated = ?
            WHERE id = ?
        """, (ward_name, now_str, eq_id))

        cursor.execute("""
            INSERT INTO equipment_movements (equipment_id, from_location, to_location, movement_time, duration_seconds, rfid_scanned_by, status, route_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (eq_id, "Central Storage A", ward_name, now_str, 42, "AI Allocation Engine", "COMPLETED", "AI Autonomous Dispatch to emergency area"))

    conn.commit()
    conn.close()

    # Broadcast real-time allocation event for animated route
    await ws_manager.broadcast({
        "type": "ALLOCATION_DISPATCHED",
        "ward_name": ward_name,
        "equipment_ids": equipment_ids,
        "timestamp": now_str
    })

    return JSONResponse({"success": True, "allocated": equipment_ids, "destination": ward_name})

async def api_maintenance_overview(request):
    """Fleet-wide maintenance analytics."""
    user = get_current_user_from_request(request)
    if not check_permission(user, "VIEW_MAINTENANCE"):
        return JSONResponse({"detail": "Access forbidden: insufficient role permissions to view fleet maintenance"}, status_code=403)
    data = maintenance_model.get_fleet_maintenance_overview()
    return JSONResponse(data)

async def api_maintenance_detail(request):
    """Single equipment predictive maintenance detail."""
    user = get_current_user_from_request(request)
    if not check_permission(user, "VIEW_MAINTENANCE") and not check_permission(user, "VIEW_WARD_EQUIPMENT"):
        return JSONResponse({"detail": "Access forbidden: insufficient role permissions to view maintenance detail"}, status_code=403)
    eq_id = request.path_params["id"]
    analysis = maintenance_model.analyze_equipment(eq_id)
    if not analysis:
        return JSONResponse({"error": "Equipment not found"}, status_code=404)
    return JSONResponse(analysis)

async def api_demand_forecast(request):
    """Ward equipment requirement forecast."""
    user = get_current_user_from_request(request)
    if not check_permission(user, "VIEW_ANALYTICS"):
        return JSONResponse({"detail": "Access forbidden: insufficient role permissions to view demand forecasts"}, status_code=403)
    ward_id = request.query_params.get("ward_id", "ward-emergency")
    eq_type = request.query_params.get("equipment_type", "Wheelchair")
    forecast = demand_forecaster.forecast_ward_equipment(ward_id, eq_type)
    return JSONResponse(forecast)

async def api_demand_summary(request):
    """Multi-ward forecast overview."""
    user = get_current_user_from_request(request)
    if not check_permission(user, "VIEW_ANALYTICS"):
        return JSONResponse({"detail": "Access forbidden: insufficient role permissions to view demand forecast summary"}, status_code=403)
    summary = demand_forecaster.get_multi_ward_forecast_summary()
    return JSONResponse(summary)

async def api_emergency_request_create(request):
    """Submits new emergency equipment request and generates AI priority score."""
    body = await request.json()
    ward_id = body.get("ward_id", "ward-emergency")
    eq_type = body.get("equipment_type", "Wheelchair")
    quantity = int(body.get("quantity", 3))
    urgency = body.get("patient_urgency", "Critical")
    reason = body.get("reason", "Trauma emergency triage")
    requested_by = body.get("requested_by", "nurse-priya")

    priority_analysis = calculate_emergency_priority(ward_id, eq_type, quantity, urgency, reason)

    req_id = f"REQ-{random.randint(1000, 9999)}"
    now_str = datetime.now().isoformat()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO equipment_requests (
            id, ward_id, equipment_type, quantity, patient_status,
            priority_score, priority_level, status, reason, requested_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        req_id, ward_id, eq_type, quantity, urgency,
        priority_analysis["priority_score"], priority_analysis["priority_level"],
        "PENDING", reason, requested_by, now_str
    ))
    conn.commit()
    conn.close()

    # Broadcast emergency alert
    await ws_manager.broadcast({
        "type": "EMERGENCY_ALERT",
        "request_id": req_id,
        "ward_name": priority_analysis["ward_name"],
        "equipment_type": eq_type,
        "quantity": quantity,
        "priority_score": priority_analysis["priority_score"],
        "priority_level": priority_analysis["priority_level"],
        "explanation": priority_analysis["explanation"]
    })

    return JSONResponse({
        "request_id": req_id,
        "analysis": priority_analysis
    })

async def api_emergency_requests_list(request):
    """Lists recent emergency requests."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM equipment_requests ORDER BY created_at DESC LIMIT 15")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return JSONResponse(rows)

# --- Global Hardware State Tracking ---
LATEST_HARDWARE_STATE = None

EQUIPMENT_TO_UID_MAP = {
    "VENT-04": "30 94 2B 58",
    "WC-007": "10 0D 71 5C",
    "ST-003": "BD 70 00 02",
    "INF-03": "21 2F 7B 69",
    "BP-003": "40 0D 0F 58",
    "BD-ICU-01": "40 0D 0F 58"
}

HARDWARE_EQUIPMENT_TITLES = {
    "VENT-04": "MECHANICAL VENTILATOR",
    "WC-007": "WHEELCHAIR",
    "ST-003": "STRETCHER",
    "INF-03": "INFUSION PUMP",
    "BD-ICU-01": "SMART ICU BED",
    "BP-003": "BLOOD PRESSURE MONITOR"
}

def resolve_hardware_uid(eq_id: str, eq_type: str = "", eq_name: str = "") -> str:
    if eq_id in EQUIPMENT_TO_UID_MAP:
        return EQUIPMENT_TO_UID_MAP[eq_id]
    for uid_val, info in RFID_MAPPINGS.items():
        if info.get("id") == eq_id:
            return uid_val
    combined = f"{eq_type} {eq_name}".upper()
    if "VENTILATOR" in combined:
        return "30 94 2B 58"
    if "WHEELCHAIR" in combined:
        return "10 0D 71 5C"
    if "STRETCHER" in combined:
        return "BD 70 00 02"
    if "INFUSION" in combined:
        return "21 2F 7B 69"
    if "BED" in combined or "BP" in combined:
        return "40 0D 0F 58"
    return "30 94 2B 58"

def resolve_hardware_title(eq_id: str, eq_type: str = "", eq_name: str = "", raw_equipment: str = "") -> str:
    if raw_equipment:
        raw_upper = raw_equipment.strip().upper()
        if raw_upper in ("MECHANICAL VENTILATOR", "VENTILATOR", "WHEELCHAIR", "STRETCHER", "INFUSION PUMP", "SMART ICU BED", "BLOOD PRESSURE MONITOR", "BP MONITOR"):
            if raw_upper == "VENTILATOR":
                return "MECHANICAL VENTILATOR"
            if raw_upper == "BP MONITOR":
                return "BLOOD PRESSURE MONITOR"
            return raw_upper
    if eq_id in HARDWARE_EQUIPMENT_TITLES:
        return HARDWARE_EQUIPMENT_TITLES[eq_id]
    combined = f"{eq_type} {eq_name}".upper()
    if "VENTILATOR" in combined:
        return "MECHANICAL VENTILATOR"
    if "WHEELCHAIR" in combined:
        return "WHEELCHAIR"
    if "STRETCHER" in combined:
        return "STRETCHER"
    if "INFUSION" in combined:
        return "INFUSION PUMP"
    if "BED" in combined:
        return "SMART ICU BED"
    return eq_type.upper() if eq_type else "EQUIPMENT"

def build_hardware_update_event(
    eq_id: str,
    eq_name: str,
    eq_type: str,
    status: str,
    previous_status: str,
    location: str,
    raw_equipment: str = "",
    uid: str = "",
    esp32_ip: str = "172.27.195.51",
    wifi: str = "CONNECTED",
    pir: bool = None,
    main_button: bool = None,
    temporary_waiting: bool = False,
    usage_timer: int = 0,
    motion_seconds: float = 0.0,
    warning: str = None,
    red_led_state: str = None,
    event_type: str = "ESP32_HARDWARE_UPDATE"
) -> dict:
    now_str = datetime.now().isoformat()
    final_uid = (uid or resolve_hardware_uid(eq_id, eq_type, eq_name)).strip().upper()
    equipment_title = resolve_hardware_title(eq_id, eq_type, eq_name, raw_equipment)

    is_in_use = (status == "IN_USE")
    # PIR sensor state reflects true infrared motion presence
    if pir is not None:
        pir_bool = bool(pir)
    elif event_type in ("RFID_SCAN", "PIR_MOTION_STOPPED"):
        pir_bool = False
    elif event_type in ("PIR_MOTION_DETECTED", "PIR_MOTION_PROGRESS", "AUTO_USE_STARTED", "AUTO_USE"):
        pir_bool = True
    elif is_in_use:
        pir_bool = True
    else:
        pir_bool = False
    pir_state = "HIGH" if pir_bool else "LOW"

    btn_bool = is_in_use if main_button is None else bool(main_button)
    btn_state = "PRESSED" if btn_bool else "IDLE"

    temp_wait_bool = bool(temporary_waiting) or (status == "TEMPORARY_HOLD")
    temp_wait_state = "ACTIVE" if temp_wait_bool else "INACTIVE"

    is_warning = bool(warning or red_led_state == "BLINKING" or event_type == "TEMP_WAIT_BLOCKED")
    is_temp_hold = (status == "TEMPORARY_HOLD")
    is_storage_return = (status == "RETURNING_TO_STORAGE")

    storage_session = storage_verification_manager.get_session(eq_id)
    storage_remaining = storage_session.get("remaining_seconds", 0) if storage_session else (120 if is_storage_return else 0)

    hold_session = temporary_hold_manager.get_hold(eq_id)
    hold_duration = hold_session.get("duration_formatted", "00:00:00") if hold_session else None
    hold_reason = hold_session.get("reason", "Awaiting patient transfer") if hold_session else None

    if is_warning:
        green_led_bool = False
        green_led_state = "LOW"
        red_led_bool = True
        final_red_led_state = "BLINKING"
        final_event_type = "TEMP_WAIT_BLOCKED"
        warning_text = warning or "Equipment is currently in use. End usage before temporary waiting."
        serial_logs = [
            "",
            "==============================",
            "WARNING: OPERATION BLOCKED",
            "Equipment is currently in use.",
            "End usage before temporary waiting.",
            "=============================="
        ]
    elif is_temp_hold:
        green_led_bool = False
        green_led_state = "LOW"
        red_led_bool = False
        final_red_led_state = "LOW"
        final_event_type = "TEMPORARY_HOLD"
        warning_text = None
        serial_logs = [
            "",
            "==============================",
            "TEMPORARY HOLD ENGAGED",
            f"Equipment: {equipment_title}",
            f"Reason: {hold_reason or 'Awaiting patient transfer'}",
            "Usage paused. Timer frozen.",
            "Press Switch 2 again to resume usage.",
            "=============================="
        ]
    elif is_storage_return:
        green_led_bool = True
        green_led_state = "BLINKING"
        red_led_bool = False
        final_red_led_state = "LOW"
        final_event_type = "STORAGE_VERIFICATION"
        warning_text = None
        serial_logs = [
            "",
            "==============================",
            "WHEELCHAIR STORAGE RETURN DETECTED",
            f"Equipment: {equipment_title}",
            f"Location: {location}",
            f"Storage verification active: {storage_remaining}s remaining",
            "Keep in bay to automatically verify AVAILABLE.",
            "=============================="
        ]
    else:
        green_led_bool = True
        green_led_state = "HIGH"
        final_red_led_state = red_led_state or "LOW"
        red_led_bool = (final_red_led_state in ("HIGH", "BLINKING", "1", "TRUE"))
        final_event_type = event_type
        warning_text = None
        if final_event_type == "PIR_MOTION_DETECTED":
            serial_logs = [
                "",
                "==========================================",
                f"[PIR] ULTRA-CLOSE HAND DETECTED (~4cm)! [{equipment_title}]",
                "Hold hand continuously for 10 seconds to start motion...",
                "=========================================="
            ]
        elif final_event_type == "PIR_MOTION_PROGRESS":
            serial_logs = [
                f"[PIR] Hand motion detected (~4cm) — Auto-Start Timer: {float(motion_seconds):.1f}s / 10.0s"
            ]
        elif final_event_type == "PIR_MOTION_STOPPED":
            serial_logs = [
                "",
                "==========================================",
                f"[PIR] Hand removed from 4cm radius (>2s).",
                f"Motion NOT detected! [{equipment_title}] Sensor returned to LOW.",
                "10-second auto-start timer reset to 0.0s.",
                "=========================================="
            ]
        elif final_event_type in ("AUTO_USE_STARTED", "AUTO_USE"):
            serial_logs = [
                "",
                "==========================================",
                "[PIR] 10 SECONDS CONTINUOUS MOTION ACHIEVED!",
                "Hand steadily verified in ~4cm range.",
                f"Equipment in motion: {equipment_title} is now IN_USE",
                "PIR monitoring active.",
                "Maximum usage time: 30 minutes.",
                "=========================================="
            ]
        elif final_event_type == "RFID_SCAN":
            serial_logs = [
                "",
                "==============================",
                "RFID CARD DETECTED",
                f"Card UID: {final_uid}",
                f"Equipment: {equipment_title}",
                "Status: INITIALIZED",
                "Waiting 3 seconds before activating motion detection...",
                "=============================="
            ]
        elif final_event_type in ("BUTTON_USE_STARTED", "BUTTON_START"):
            serial_logs = [
                "",
                "==============================",
                "USE STARTED (SWITCH 1 PRESSED)",
                f"Equipment: {equipment_title}",
                "Status: IN_USE",
                "PIR monitoring active.",
                "Maximum usage time: 30 minutes.",
                "=============================="
            ]
        elif final_event_type in ("BUTTON_USE_ENDED", "BUTTON_END"):
            serial_logs = [
                "",
                "==============================",
                "USE ENDED (SWITCH 1 PRESSED)",
                f"Equipment: {equipment_title}",
                "Status: AVAILABLE",
                "Equipment is ready.",
                "Waiting for next activity...",
                "=============================="
            ]
        elif final_event_type == "WAYPOINT_VERIFIED":
            wp_name = location or "Hospital Corridor Checkpoint"
            serial_logs = [
                "",
                "==========================================",
                f"[WAYPOINT VERIFIED] {wp_name}",
                f"Card UID: {final_uid}",
                f"Equipment: {equipment_title}",
                "Physical Checkpoint Calibrated via RFID",
                "=========================================="
            ]
        elif final_event_type in ("TEMPORARY_HOLD_ENDED", "TEMP_WAIT_ENDED"):
            serial_logs = [
                "",
                "==============================",
                "TEMPORARY WAITING ENDED (SWITCH 2 PRESSED)",
                f"Equipment: {equipment_title}",
                "Status: AVAILABLE",
                "Equipment is ready.",
                "=============================="
            ]
        else:
            if is_in_use:
                serial_logs = [
                    "",
                    "==============================",
                    "USE STARTED",
                    f"Equipment: {equipment_title}",
                    "Status: IN_USE",
                    "PIR monitoring active.",
                    "Maximum usage time: 30 minutes.",
                    "=============================="
                ]
            else:
                serial_logs = [
                    "",
                    "==============================",
                    "EQUIPMENT STATUS UPDATE",
                    f"Equipment: {equipment_title}",
                    f"Status: {status}",
                    "Equipment is ready.",
                    "Waiting for next activity...",
                    "=============================="
                ]

    buzzer_bool = False
    buzzer_state = "IDLE"

    return {
        "type": "ESP32_HARDWARE_UPDATE",
        "event_type": final_event_type,
        "event": final_event_type,
        "uid": final_uid,
        "equipment": equipment_title,
        "equipment_name": eq_name,
        "equipment_id": eq_id,
        "equipment_type": eq_type,
        "status": status,
        "previous_status": previous_status,
        "location": location,
        "timestamp": now_str,
        "esp32_ip": esp32_ip or "172.27.195.199",
        "wifi": wifi or "CONNECTED",
        "wifi_status": wifi or "CONNECTED",
        "pir_state": pir_state,
        "pir": pir_bool,
        "motion_seconds": float(motion_seconds or (10.0 if final_event_type in ("AUTO_USE_STARTED", "AUTO_USE") else 0.0)),
        "main_button_state": btn_state,
        "main_button": btn_bool,
        "temporary_waiting_state": temp_wait_state,
        "temporary_waiting": temp_wait_bool,
        "usage_timer": int(usage_timer or 0),
        "green_led_state": green_led_state,
        "green_led": green_led_bool,
        "red_led_state": final_red_led_state,
        "red_led": red_led_bool,
        "buzzer_state": buzzer_state,
        "buzzer": buzzer_bool,
        "warning": warning_text,
        "storage_countdown": storage_remaining,
        "is_verifying_storage": (status == "RETURNING_TO_STORAGE"),
        "hold_duration": hold_duration,
        "hold_reason": hold_reason,
        "source": "ESP32_HARDWARE",
        "is_real_hardware": True,
        "serial_logs": serial_logs,
        "message": warning_text if is_warning else f"ESP32 Hardware Event: {eq_name} ({eq_id}) set to {status}"
    }

async def on_storage_verified_callback(equipment_id: str, location: str):
    """Automatically invoked when the 120s storage countdown completes without movement."""
    now_str = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE equipment 
        SET status = 'AVAILABLE', location = ?, room = 'Wheelchair Storage Bay',
            coordinates_x = 88.0, coordinates_y = 44.0, last_updated = ?
        WHERE id = ?
    """, (location, now_str, equipment_id))

    cursor.execute("""
        INSERT INTO equipment_movements (equipment_id, from_location, to_location, movement_time, duration_seconds, route_description)
        VALUES (?, ?, ?, ?, 120, '2-Minute Wheelchair Storage Auto-Verification Completed')
    """, (equipment_id, location, location, now_str))

    cursor.execute("""
        UPDATE storage_verification_sessions 
        SET status = 'VERIFIED', completed_at = ?
        WHERE equipment_id = ? AND status = 'COUNTDOWN_ACTIVE'
    """, (now_str, equipment_id))

    cursor.execute("""
        SELECT COUNT(*) as cnt FROM equipment 
        WHERE type = 'Wheelchair' AND status = 'AVAILABLE' 
        AND (location LIKE '%Radiology%' OR location LIKE '%Storage%')
    """)
    avail_wc = cursor.fetchone()["cnt"]
    conn.commit()
    conn.close()

    # Inform simulation engine: transport shortage cleared!
    simulation_engine.update_transport_equipment_count(avail_wc)

    ver_ev = {
        "type": "WHEELCHAIR_STORAGE_VERIFIED",
        "equipment_id": equipment_id,
        "status": "AVAILABLE",
        "location": location,
        "message": f"✓ {equipment_id} verified AVAILABLE at {location} (2-minute countdown complete)",
        "timestamp": now_str
    }
    await ws_manager.broadcast(ver_ev)

    hw_ev = build_hardware_update_event(
        eq_id=equipment_id,
        eq_name="Wheelchair WC-007 (Smart IoT)",
        eq_type="Wheelchair",
        status="AVAILABLE",
        previous_status="RETURNING_TO_STORAGE",
        location=location,
        raw_equipment="WHEELCHAIR"
    )
    global LATEST_HARDWARE_STATE
    LATEST_HARDWARE_STATE = hw_ev
    await ws_manager.broadcast(hw_ev)

    await ws_manager.broadcast({
        "type": "EQUIPMENT_STATUS_CHANGED",
        "equipment_id": equipment_id,
        "status": "AVAILABLE",
        "location": location,
        "timestamp": now_str,
        "source": "STORAGE_VERIFICATION_COMPLETE"
    })

async def on_storage_tick_callback(equipment_id: str, remaining_seconds: int):
    """Broadcasts storage countdown tick every 5s or at final 10s."""
    if remaining_seconds % 5 == 0 or remaining_seconds <= 10:
        await ws_manager.broadcast({
            "type": "WHEELCHAIR_STORAGE_TICK",
            "equipment_id": equipment_id,
            "remaining_seconds": remaining_seconds,
            "timestamp": datetime.now().isoformat()
        })

async def canonical_update_equipment_state(
    equipment_id: str,
    target_state: str,
    location: str = None,
    source: str = "SYSTEM",
    reason: str = None,
    remote_ip: str = "172.27.195.199",
    raw_equipment: str = "",
    uid: str = "",
    pir: bool = None,
    main_button: bool = None,
    battery: int = None,
    temperature: float = None,
    warning: str = None,
    red_led_state: str = None,
    event_type: str = None,
    duration_seconds: int = 120,
    motion_seconds: float = 0.0
):
    """
    Enterprise Canonical State Transition Function.
    All transitions must pass validation via EquipmentStateMachine.
    Guarantees no impossible concurrent states, triggers 2-min storage verification,
    tracks temporary hold duration, and updates database + WebSocket clients.
    """
    global LATEST_HARDWARE_STATE
    now_str = datetime.now().isoformat()
    norm_target = EquipmentStateMachine.normalize_state(target_state)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, type, location, status, movement_count, battery, temperature, health_score, coordinates_x, coordinates_y, room
        FROM equipment WHERE id = ?
    """, (equipment_id,))
    item = cursor.fetchone()
    if not item:
        conn.close()
        return False, {"error": f"Equipment '{equipment_id}' not found in database"}

    current_status = item["status"]
    is_valid, val_msg = EquipmentStateMachine.validate_transition(current_status, norm_target)
    if not is_valid:
        conn.close()
        return False, {"error": val_msg, "current_status": current_status, "target_state": norm_target}

    target_location = location or item["location"]
    movement_count = item["movement_count"] or 0
    coords_x = item["coordinates_x"]
    coords_y = item["coordinates_y"]
    room = item["room"] if "room" in item.keys() and item["room"] else "Central Area"

    # Dynamic Blueprint Coordinates based on Target Location
    if target_location:
        loc_upper = target_location.upper()
        if "EMERGENCY" in loc_upper:
            coords_x = 18.0
            coords_y = 65.0
            room = "Emergency Bay"
        elif "CORRIDOR" in loc_upper or "JUNCTION" in loc_upper:
            coords_x = 52.0
            coords_y = 50.0
            room = "Clinical Transit Corridor"
        elif "RADIOLOGY" in loc_upper and "STORAGE" not in loc_upper:
            coords_x = 84.0
            coords_y = 52.0
            room = "Radiology Suite"
        elif "ICU" in loc_upper:
            coords_x = 35.0
            coords_y = 25.0
            room = "ICU Recovery"

    # 1. RETURNING_TO_STORAGE Transition
    if norm_target == EquipmentState.RETURNING_TO_STORAGE:
        target_location = "Radiology Wheelchair Storage"
        coords_x = 88.0
        coords_y = 44.0
        room = "Wheelchair Storage Bay"
        dur = int(duration_seconds or 120)
        storage_verification_manager.start_verification(
            equipment_id=equipment_id,
            location=target_location,
            duration_seconds=dur,
            on_verified_callback=on_storage_verified_callback,
            on_tick_callback=on_storage_tick_callback
        )
        cursor.execute("""
            INSERT INTO storage_verification_sessions (equipment_id, location, status, countdown_seconds, started_at, target_verification_at)
            VALUES (?, ?, 'COUNTDOWN_ACTIVE', ?, ?, ?)
        """, (equipment_id, target_location, dur, now_str, (datetime.now() + timedelta(seconds=dur)).isoformat()))

        await ws_manager.broadcast({
            "type": "WHEELCHAIR_STORAGE_STARTED",
            "equipment_id": equipment_id,
            "equipment_name": item["name"],
            "location": target_location,
            "status": "RETURNING_TO_STORAGE",
            "duration_seconds": dur,
            "remaining_seconds": dur,
            "message": f"{item['name']} returned to {target_location}. {dur}s verification countdown started.",
            "timestamp": now_str
        })

    elif current_status == EquipmentState.RETURNING_TO_STORAGE and norm_target != EquipmentState.RETURNING_TO_STORAGE:
        # Edge case: Wheelchair moved or resumed while in 2-min countdown
        storage_verification_manager.cancel_verification(equipment_id, reason=reason or "Movement / state change detected")
        cursor.execute("""
            UPDATE storage_verification_sessions 
            SET status = 'CANCELLED', cancellation_reason = ?, completed_at = ?
            WHERE equipment_id = ? AND status = 'COUNTDOWN_ACTIVE'
        """, (reason or "Movement detected during countdown", now_str, equipment_id))

        await ws_manager.broadcast({
            "type": "WHEELCHAIR_STORAGE_CANCELLED",
            "equipment_id": equipment_id,
            "status": norm_target,
            "reason": reason or "Movement detected during countdown",
            "timestamp": now_str
        })

        await ws_manager.broadcast({
            "type": "WHEELCHAIR_STORAGE_CANCELLED",
            "equipment_id": equipment_id,
            "status": norm_target,
            "reason": reason or "Movement detected during countdown",
            "timestamp": now_str
        })

    # 2. TEMPORARY_HOLD Transition
    if norm_target == EquipmentState.TEMPORARY_HOLD:
        hold = temporary_hold_manager.start_hold(equipment_id, reason=reason or "Awaiting patient transfer")
        await ws_manager.broadcast({
            "type": "TEMPORARY_HOLD_STARTED",
            "equipment_id": equipment_id,
            "status": "TEMPORARY_HOLD",
            "reason": hold["reason"],
            "timestamp": now_str
        })

    elif current_status == EquipmentState.TEMPORARY_HOLD and norm_target != EquipmentState.TEMPORARY_HOLD:
        hold = temporary_hold_manager.end_hold(equipment_id, resumed_to=norm_target)
        await ws_manager.broadcast({
            "type": "TEMPORARY_HOLD_ENDED",
            "equipment_id": equipment_id,
            "resumed_to": norm_target,
            "duration_seconds": hold.get("duration_seconds", 0) if hold else 0,
            "timestamp": now_str
        })

    # 3. Log Movement if transitioning to IN_USE or location changed
    if norm_target in (EquipmentState.IN_USE, EquipmentState.RETURNING_TO_STORAGE) or target_location != item["location"]:
        movement_count += 1
        cursor.execute("""
            INSERT INTO equipment_movements (equipment_id, from_location, to_location, movement_time, duration_seconds, route_description)
            VALUES (?, ?, ?, ?, 60, ?)
        """, (equipment_id, item["location"], target_location, now_str, f"State change to {norm_target} via {source}: {reason or 'Normal operation'}"))

    new_batt = battery if battery is not None else (item["battery"] or 85)
    new_temp = temperature if temperature is not None else (item["temperature"] or 36.5)

    cursor.execute("""
        UPDATE equipment 
        SET status = ?, location = ?, room = ?, coordinates_x = ?, coordinates_y = ?,
            movement_count = ?, battery = ?, temperature = ?, last_updated = ?
        WHERE id = ?
    """, (norm_target, target_location, room, coords_x, coords_y, movement_count, new_batt, new_temp, now_str, equipment_id))

    cursor.execute("""
        SELECT COUNT(*) as cnt FROM equipment 
        WHERE type = 'Wheelchair' AND status = 'AVAILABLE' 
        AND (location LIKE '%Radiology%' OR location LIKE '%Storage%')
    """)
    avail_wc = cursor.fetchone()["cnt"]
    simulation_engine.update_transport_equipment_count(avail_wc)

    conn.commit()
    conn.close()

    hw_ev = build_hardware_update_event(
        eq_id=equipment_id,
        eq_name=item["name"],
        eq_type=item["type"],
        status=norm_target,
        previous_status=current_status,
        location=target_location,
        raw_equipment=raw_equipment,
        uid=uid,
        esp32_ip=remote_ip,
        pir=pir,
        main_button=main_button,
        temporary_waiting=(norm_target == EquipmentState.TEMPORARY_HOLD),
        warning=warning,
        red_led_state=red_led_state,
        event_type=event_type or "ESP32_HARDWARE_UPDATE",
        motion_seconds=motion_seconds
    )
    LATEST_HARDWARE_STATE = hw_ev
    await ws_manager.broadcast(hw_ev)

    await ws_manager.broadcast({
        "type": "EQUIPMENT_STATUS_CHANGED",
        "equipment_id": equipment_id,
        "status": norm_target,
        "location": target_location,
        "timestamp": now_str,
        "source": source
    })

    if target_location != item["location"]:
        await ws_manager.broadcast({
            "type": "EQUIPMENT_MOVED",
            "equipment_id": equipment_id,
            "from_location": item["location"],
            "to_location": target_location,
            "new_coordinates": {"x": coords_x, "y": coords_y},
            "timestamp": now_str
        })

    return True, {
        "status": "success",
        "equipment_id": equipment_id,
        "previous_status": current_status,
        "new_status": norm_target,
        "location": target_location,
        "movement_count": movement_count,
        "hardware_event": hw_ev
    }

async def api_esp32_telemetry(request):
    """Ingests live sensor data sent by ESP32."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    eq_id = data.get("equipment_id", "WC-009")
    battery = int(data.get("battery", 80))
    movement = bool(data.get("movement", False))
    temperature = float(data.get("temperature", 28.0))
    usage_time = int(data.get("usage_time", 0))
    new_location = data.get("location")
    now_str = datetime.now().isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT status, location, movement_count, name, type FROM equipment WHERE id = ?", (eq_id,))
    item = cursor.fetchone()

    if not item:
        conn.close()
        return JSONResponse({"error": f"Equipment {eq_id} not found"}, status_code=404)

    current_status = item["status"]
    old_location = item["location"]
    movement_count = item["movement_count"] or 0
    eq_name = item["name"]
    eq_type = item["type"]
    # Phase 3 Edge Case Handling:
    if current_status == "RETURNING_TO_STORAGE":
        if movement:
            # Wheelchair was moved during 2-minute verification period!
            # Cancel timer and revert to IN_USE
            storage_verification_manager.cancel_verification(eq_id, reason="Movement detected during 2-min verification countdown")
            cursor.execute("""
                UPDATE storage_verification_sessions 
                SET status = 'CANCELLED', cancellation_reason = 'Motion detected during countdown'
                WHERE equipment_id = ? AND status = 'COUNTDOWN_ACTIVE'
            """, (eq_id,))
            new_status = "IN_USE"
            await ws_manager.broadcast({
                "type": "WHEELCHAIR_STORAGE_CANCELLED",
                "equipment_id": eq_id,
                "status": "IN_USE",
                "reason": "Motion detected during 2-minute verification countdown",
                "timestamp": now_str
            })
        else:
            # Still in verification countdown: remain in RETURNING_TO_STORAGE
            new_status = "RETURNING_TO_STORAGE"
    elif current_status == "TEMPORARY_HOLD":
        # Do not override temporary hold via background telemetry
        new_status = "TEMPORARY_HOLD"
    elif current_status not in ("MAINTENANCE", "RESERVED"):
        new_status = "IN_USE" if movement else "AVAILABLE"
    else:
        new_status = current_status

    location_to_set = new_location if new_location else old_location
    if new_location and old_location and new_location != old_location:
        cursor.execute("""
            INSERT INTO equipment_movements (equipment_id, from_location, to_location, movement_time, duration_seconds, route_description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (eq_id, old_location, new_location, now_str, 60, f"IoT Relocation to {new_location}"))
        movement_count += 1

    cursor.execute("""
        UPDATE equipment 
        SET battery = ?, temperature = ?, location = ?, status = ?, movement_count = ?, last_updated = ?
        WHERE id = ?
    """, (battery, temperature, location_to_set, new_status, movement_count, now_str, eq_id))

    cursor.execute("""
        INSERT INTO sensor_telemetry (equipment_id, battery, movement, temperature, usage_time, location, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (eq_id, battery, 1 if movement else 0, temperature, usage_time, location_to_set, now_str))

    conn.commit()
    conn.close()

    payload = {
        "type": "ESP32_TELEMETRY",
        "equipment_id": eq_id,
        "battery": battery,
        "movement": movement,
        "temperature": temperature,
        "usage_time": usage_time,
        "location": location_to_set,
        "status": new_status,
        "timestamp": now_str,
        "is_low_battery": battery < 20
    }
    await ws_manager.broadcast(payload)

    # Also build and broadcast full structured hardware-state event
    remote_ip = request.client.host if request.client and request.client.host not in ("127.0.0.1", "localhost", "testclient") else "172.27.195.51"
    hw_ev = build_hardware_update_event(
        eq_id=eq_id,
        eq_name=eq_name,
        eq_type=eq_type,
        status=new_status,
        previous_status=current_status,
        location=location_to_set,
        esp32_ip=remote_ip,
        pir=movement,
        usage_timer=usage_time
    )
    global LATEST_HARDWARE_STATE
    LATEST_HARDWARE_STATE = hw_ev
    await ws_manager.broadcast(hw_ev)

    return JSONResponse({"status": "received", "data": payload})

async def api_esp32_rfid(request):
    """Hardware RFID Reader endpoint."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    uid = data.get("uid", "").strip().upper()
    location = data.get("location", "Central Storage A")
    now_str = datetime.now().isoformat()

    # Rejects unknown RFID tags cleanly
    mapped_info = RFID_MAPPINGS.get(uid)
    if not mapped_info:
        return JSONResponse({
            "status": "error",
            "message": f"Unknown RFID tag: '{uid}'. Tag is not registered in hospital database.",
            "uid": uid
        }, status_code=404)

    eq_id = mapped_info["id"]
    eq_type = mapped_info["type"]
    eq_name = mapped_info["name"]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT health_score, battery, status, location, movement_count FROM equipment WHERE id = ?", (eq_id,))
    item = cursor.fetchone()

    health = item["health_score"] if item else 95
    battery = item["battery"] if item else 85
    status = item["status"] if item else "AVAILABLE"
    old_location = item["location"] if item else "Central Storage A"
    movement_count = (item["movement_count"] or 0) + 1 if item else 1

    # Records every RFID scan
    cursor.execute("""
        INSERT INTO rfid_scans (uid, equipment_id, equipment_type, location, status, scanned_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (uid, eq_id, eq_type, location, status, now_str))

    # Creates equipment_movements history when location changes
    if old_location and old_location != location:
        cursor.execute("""
            INSERT INTO equipment_movements (equipment_id, from_location, to_location, movement_time, duration_seconds, route_description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (eq_id, old_location, location, now_str, 45, f"RFID Checkpoint Scan ({location})"))

    # Updates equipment location and increments movement count
    cursor.execute("""
        UPDATE equipment 
        SET location = ?, movement_count = ?, last_updated = ?
        WHERE id = ?
    """, (location, movement_count, now_str, eq_id))

    conn.commit()
    conn.close()

    scan_event = {
        "type": "RFID_SCAN_EVENT",
        "uid": uid,
        "equipment_id": eq_id,
        "equipment_name": eq_name,
        "equipment_type": eq_type,
        "location": location,
        "previous_location": old_location,
        "status": status,
        "health_score": health,
        "battery": battery,
        "movement_count": movement_count,
        "scanned_at": now_str,
        "message": f"✓ {eq_type.upper()} {eq_id} IDENTIFIED ({location})"
    }

    # Broadcasts the RFID event through WebSocket
    await ws_manager.broadcast(scan_event)

    # Build and broadcast structured hardware-state event
    remote_ip = request.client.host if request.client and request.client.host not in ("127.0.0.1", "localhost", "testclient") else "172.27.195.51"
    hw_event = build_hardware_update_event(
        eq_id=eq_id,
        eq_name=eq_name,
        eq_type=eq_type,
        status=status,
        previous_status=status,
        location=location,
        uid=uid,
        esp32_ip=remote_ip
    )
    global LATEST_HARDWARE_STATE
    LATEST_HARDWARE_STATE = hw_event
    await ws_manager.broadcast(hw_event)

    if old_location and old_location != location:
        await ws_manager.broadcast({
            "type": "EQUIPMENT_MOVED",
            "equipment_id": eq_id,
            "from_location": old_location,
            "to_location": location,
            "timestamp": now_str
        })

    return JSONResponse(scan_event)

async def api_esp32_equipment_update(request):
    """
    Direct endpoint for ESP32 hardware firmware sending:
    {"equipment": "<EQUIPMENT_NAME_OR_ID>", "status": "<STATUS>"}
    Accepts both standard equipment names ('WHEELCHAIR', 'MECHANICAL VENTILATOR', 'STRETCHER', 'INFUSION PUMP', 'SMART ICU BED')
    and exact asset IDs ('WC-007', 'VENT-04', 'ST-003', 'INF-03', 'BD-ICU-01', 'BP-003').
    """
    global LATEST_HARDWARE_STATE
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"status": "error", "message": "Invalid JSON payload"}, status_code=400)

    raw_eq = str(data.get("equipment", "")).strip()
    status = str(data.get("status", "AVAILABLE")).strip().upper()
    req_uid = str(data.get("uid", "")).strip().upper()
    warning_param = data.get("warning")
    event_param = str(data.get("event", data.get("event_type", ""))).strip().upper()
    red_led_param = str(data.get("red_led", data.get("red_led_state", ""))).strip().upper()
    now_str = datetime.now().isoformat()

    is_temp_blocked = bool(
        warning_param
        or event_param == "TEMP_WAIT_BLOCKED"
        or red_led_param == "BLINKING"
        or status in ("TEMP_WAIT_BLOCKED", "WARNING_IN_USE")
    )
    if is_temp_blocked:
        if not warning_param:
            warning_param = "Equipment is currently in use. End usage before temporary waiting."
        if status in ("TEMP_WAIT_BLOCKED", "WARNING_IN_USE", "AVAILABLE"):
            status = "IN_USE"

    # If equipment is omitted but uid is supplied, resolve via RFID mapping
    if not raw_eq and req_uid:
        mapped_rfid = RFID_MAPPINGS.get(req_uid)
        if mapped_rfid:
            raw_eq = mapped_rfid.get("type", "").upper()

    # If equipment is omitted during warning/action, fallback to latest known hardware state
    if not raw_eq and is_temp_blocked and LATEST_HARDWARE_STATE and LATEST_HARDWARE_STATE.get("equipment"):
        raw_eq = LATEST_HARDWARE_STATE.get("equipment")
        if not req_uid:
            req_uid = LATEST_HARDWARE_STATE.get("uid", "")

    if not raw_eq:
        return JSONResponse({"status": "error", "message": "Missing 'equipment' field in request"}, status_code=400)

    # Name-to-Asset ID mapping matching ESP32 firmware
    EQUIPMENT_NAME_LOOKUP = {
        "MECHANICAL VENTILATOR": "VENT-04",
        "VENTILATOR": "VENT-04",
        "STRETCHER": "ST-003",
        "WHEELCHAIR": "WC-007",
        "INFUSION PUMP": "INF-03",
        "SMART ICU BED": "BD-ICU-01",
        "ICU BED": "BD-ICU-01",
        "BLOOD PRESSURE MONITOR": "BP-003",
        "BP MONITOR": "BP-003"
    }

    target_id = EQUIPMENT_NAME_LOOKUP.get(raw_eq.upper(), raw_eq)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, type, location, status, movement_count, battery, temperature, health_score 
        FROM equipment 
        WHERE id = ? 
        LIMIT 1
    """, (target_id,))
    item = cursor.fetchone()

    if not item:
        cursor.execute("""
            SELECT id, name, type, location, status, movement_count, battery, temperature, health_score 
            FROM equipment 
            WHERE UPPER(name) LIKE ? OR UPPER(type) LIKE ? 
            ORDER BY id ASC 
            LIMIT 1
        """, (f"%{raw_eq.upper()}%", f"%{raw_eq.upper()}%"))
        item = cursor.fetchone()

    if not item:
        conn.close()
        return JSONResponse({
            "status": "error",
            "message": f"Equipment '{raw_eq}' not registered in hospital database.",
            "equipment": raw_eq
        }, status_code=404)

    eq_id = item["id"]
    current_status = item["status"]
    location = item["location"]
    movement_count = item["movement_count"] or 0

    # Determine remote ESP32 IP (physical hardware is 172.27.195.199 on local Wi-Fi)
    remote_ip = data.get("esp32_ip") or (request.client.host if request.client and request.client.host not in ("127.0.0.1", "localhost", "testclient") else "172.27.195.199")
    wifi_status = str(data.get("wifi", data.get("wifi_status", "CONNECTED")))

    # Phase 3: Detect Storage Return intent
    is_storage_return = (
        event_param in ("STORAGE_RETURN", "RETURN_STORAGE", "RETURN_TO_STORAGE")
        or status in ("RETURNING_TO_STORAGE", "STORAGE_RETURN")
        or data.get("action") in ("STORAGE_RETURN", "RETURN_TO_STORAGE")
        or (target_id == "WC-007" and "STORAGE" in str(data.get("location", "")).upper())
    )

    # Phase 3: Detect Temporary Hold intent
    is_temp_hold_toggle = (
        event_param in ("TEMPORARY_HOLD", "TEMP_HOLD", "TEMP_WAIT")
        or status in ("TEMPORARY_HOLD", "TEMP_WAITING")
        or data.get("action") in ("TEMPORARY_HOLD", "TEMP_HOLD")
    )

    # Phase 3: Detect Resume Usage intent
    is_resume_intent = (
        event_param in ("RESUME_USAGE", "RESUME")
        or data.get("action") in ("RESUME_USAGE", "RESUME")
        or (current_status == "TEMPORARY_HOLD" and status == "IN_USE")
    )

    incoming_loc = data.get("location")

    if is_storage_return:
        target_state = "RETURNING_TO_STORAGE"
        target_loc = "Radiology Wheelchair Storage"
    elif is_temp_hold_toggle:
        if current_status == "IN_USE":
            target_state = "TEMPORARY_HOLD"
            target_loc = incoming_loc or location
        elif current_status == "TEMPORARY_HOLD":
            target_state = "IN_USE"
            target_loc = incoming_loc or location
        else:
            is_temp_blocked = True
            warning_param = "Equipment is currently in use. End usage before temporary waiting."
            target_state = current_status
            target_loc = incoming_loc or location
    elif is_resume_intent:
        target_state = "IN_USE"
        target_loc = incoming_loc or location
    else:
        # Preserve MAINTENANCE and RESERVED states unless explicitly commanded
        if current_status in ("MAINTENANCE", "RESERVED") and status not in ("MAINTENANCE", "RESERVED"):
            target_state = current_status
        else:
            target_state = status
        target_loc = incoming_loc or location

    motion_sec = float(data.get("motion_seconds", 0.0) or 0.0)
    pir_val = data.get("pir")
    if pir_val is None:
        if data.get("pir_state"):
            pir_val = (data.get("pir_state") == "HIGH")
        elif event_param in ("RFID_SCAN", "PIR_MOTION_STOPPED"):
            pir_val = False
        elif event_param in ("PIR_MOTION_DETECTED", "PIR_MOTION_PROGRESS", "AUTO_USE_STARTED"):
            pir_val = True
        elif target_state == "IN_USE":
            pir_val = True
        else:
            pir_val = False
    else:
        pir_val = bool(pir_val)

    btn_val = data.get("main_button") or data.get("button")
    if btn_val is None:
        btn_val = (target_state == "IN_USE")

    source_val = str(data.get("source", "ESP32_HARDWARE"))
    computed_event_type = "TEMP_WAIT_BLOCKED" if is_temp_blocked else (
        "STORAGE_VERIFICATION" if is_storage_return else (
            "TEMPORARY_HOLD" if target_state == "TEMPORARY_HOLD" else (
                event_param if event_param else "ESP32_HARDWARE_UPDATE"
            )
        )
    )

    ok, result = await canonical_update_equipment_state(
        equipment_id=eq_id,
        target_state=target_state,
        location=target_loc,
        source=source_val,
        reason=data.get("reason"),
        remote_ip=remote_ip,
        raw_equipment=raw_eq,
        uid=req_uid,
        pir=pir_val,
        main_button=btn_val,
        warning=warning_param,
        red_led_state="BLINKING" if is_temp_blocked else red_led_param,
        event_type=computed_event_type,
        motion_seconds=motion_sec
    )

    hardware_event = result.get("hardware_event") or LATEST_HARDWARE_STATE

    dist_param = data.get("distance_meters")
    speed_param = data.get("speed_mps")
    steps_param = data.get("steps")
    if dist_param is not None:
        try:
            hardware_event["distance_meters"] = round(float(dist_param), 1)
        except Exception:
            pass
    elif target_state != "IN_USE":
        hardware_event["distance_meters"] = 0.0

    if speed_param is not None:
        try:
            hardware_event["speed_mps"] = round(float(speed_param), 1)
        except Exception:
            pass
    elif target_state != "IN_USE":
        hardware_event["speed_mps"] = 0.0

    if steps_param is not None:
        try:
            hardware_event["steps"] = int(steps_param)
        except Exception:
            pass
    elif target_state != "IN_USE":
        hardware_event["steps"] = 0

    rssi_param = data.get("rssi")
    if rssi_param is not None:
        try:
            hardware_event["rssi"] = int(rssi_param)
        except Exception:
            pass
    elif target_state != "IN_USE":
        hardware_event["rssi"] = -42

    if data.get("waypoint"):
        hardware_event["waypoint"] = data.get("waypoint")

    # Legacy compatibility payload
    legacy_payload = {
        "type": "ESP32_EQUIPMENT_UPDATE",
        "equipment_id": eq_id,
        "equipment_name": item["name"],
        "equipment_type": item["type"],
        "equipment": hardware_event["equipment"],
        "status": target_state,
        "previous_status": current_status,
        "location": target_loc,
        "timestamp": now_str,
        "source": source_val,
        "uid": hardware_event["uid"],
        "esp32_ip": hardware_event["esp32_ip"],
        "message": hardware_event["message"],
        "warning": warning_param,
        "event": "TEMP_WAIT_BLOCKED" if is_temp_blocked else ("STORAGE_VERIFICATION" if is_storage_return else ("TEMPORARY_HOLD" if target_state == "TEMPORARY_HOLD" else ("RF_SIGNAL_TRACKING" if event_param == "RF_SIGNAL_TRACKING" else "ESP32_EQUIPMENT_UPDATE"))),
        "red_led_state": hardware_event.get("red_led_state", "LOW"),
        "green_led_state": hardware_event.get("green_led_state", "HIGH"),
        "buzzer_state": hardware_event.get("buzzer_state", "IDLE"),
        "pir_state": hardware_event.get("pir_state", "LOW"),
        "distance_meters": hardware_event.get("distance_meters", 0.0),
        "speed_mps": hardware_event.get("speed_mps", 0.0),
        "rssi": hardware_event.get("rssi", -42),
        "steps": hardware_event.get("steps", 0),
        "moving": bool(data.get("moving", hardware_event.get("speed_mps", 0.0) > 0.0)),
        "serial_logs": hardware_event.get("serial_logs")
    }
    await ws_manager.broadcast(legacy_payload)

    return JSONResponse({
        "status": "success",
        "equipment": raw_eq,
        "equipment_id": eq_id,
        "equipment_name": item["name"],
        "equipment_type": item["type"],
        "new_status": target_state,
        "previous_status": current_status,
        "location": target_loc,
        "movement_count": result.get("movement_count", movement_count),
        "timestamp": now_str,
        "uid": hardware_event["uid"],
        "warning": warning_param,
        "event": "TEMP_WAIT_BLOCKED" if is_temp_blocked else ("STORAGE_VERIFICATION" if is_storage_return else ("TEMPORARY_HOLD" if target_state == "TEMPORARY_HOLD" else ("RF_SIGNAL_TRACKING" if event_param == "RF_SIGNAL_TRACKING" else "ESP32_HARDWARE_UPDATE"))),
        "red_led_state": hardware_event.get("red_led_state", "LOW"),
        "hardware_event": hardware_event
    })

async def api_esp32_latest_state(request):
    """Returns the most recent ESP32 hardware state broadcast."""
    global LATEST_HARDWARE_STATE
    if LATEST_HARDWARE_STATE:
        return JSONResponse(LATEST_HARDWARE_STATE)
    return JSONResponse({
        "status": "idle",
        "message": "No hardware events received yet"
    })

async def api_rfid_recent(request):
    """Returns recent RFID scans."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rfid_scans ORDER BY scanned_at DESC LIMIT 10")
    scans = [dict(s) for s in cursor.fetchall()]
    conn.close()
    return JSONResponse(scans)

async def api_vision_detections(request):
    """Returns optical YOLO detection stream & inventory mismatch comparison."""
    user = get_current_user_from_request(request)
    if not check_permission(user, "VIEW_ANALYTICS") and not check_permission(user, "MANAGE_EQUIPMENT"):
        return JSONResponse({"detail": "Access forbidden: insufficient role permissions to view vision detections"}, status_code=403)
    zone = request.query_params.get("zone", "Zone A - Central Triage & Staging")
    rep = vision_engine.compare_inventory_with_database(zone)
    return JSONResponse(rep)

async def api_assistant_chat(request):
    """MediAI natural language conversation endpoint."""
    body = await request.json()
    prompt = body.get("message", "")
    response = query_mediai_assistant(prompt)
    return JSONResponse(response)

async def api_iot_nodes(request):
    """Returns real microcontroller nodes, signal telemetry, battery levels, and sensory telemetry."""
    global LATEST_HARDWARE_STATE
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, type, location, battery, status, temperature, rfid_uid, last_updated FROM equipment ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    # ESP32 Master Gateway node (Hardware / Bridge)
    hw_status = "ONLINE"
    hw_ip = "172.27.195.199"
    pir_state = "IDLE"
    rfid_uid = "10 0D 71 5C"
    motion_timer = "0s / 10s"
    proximity = "4cm Proximity Ready"
    if LATEST_HARDWARE_STATE:
        pir_state = LATEST_HARDWARE_STATE.get("pir", "IDLE")
        rfid_uid = LATEST_HARDWARE_STATE.get("rfid_uid", "10 0D 71 5C")
        motion_timer = LATEST_HARDWARE_STATE.get("timer", "10s Active")

    nodes = [
        {
            "node_id": "ESP32-GW-01",
            "name": "ESP32 Master Clinical Gateway",
            "device_class": "ESP32-WROOM-32D",
            "equipment_id": "WC-007",
            "equipment_name": "Smart Wheelchair WC-007",
            "location": "Emergency Ward",
            "network": {
                "ip": hw_ip,
                "port": "COM5 / USB UART",
                "protocol": "Wi-Fi 802.11 b/g/n + BLE 5.0",
                "rssi": -52,
                "signal_quality": "Excellent (-52 dBm)",
                "packet_loss": 0.01,
                "latency_ms": 11
            },
            "power": {
                "battery": 96,
                "voltage": 5.02,
                "power_source": "USB Line / Internal LiPo Buffer",
                "health": "Optimal"
            },
            "sensors": {
                "pir_infrared": {
                    "model": "HC-SR501",
                    "pin": "Pin D32",
                    "state": pir_state,
                    "proximity_radius": "4cm Hand Infrared Signature",
                    "motion_window": "10s Continuous Window",
                    "motion_timer": motion_timer
                },
                "rfid": {
                    "model": "MFRC522 (13.56 MHz SPI)",
                    "last_uid": rfid_uid,
                    "auth_mode": "Single-Tap RFID Initializer (3s Read)",
                    "status": "Ready"
                },
                "imu": {
                    "motion": "Stationary" if pir_state == "IDLE" else "Active In-Use",
                    "tilt": 1.1,
                    "vibration_g": 0.02
                },
                "environment": {
                    "temperature": 31.4,
                    "humidity": 46.2
                }
            },
            "firmware_version": "v3.4.1-clinical",
            "status": "STREAMING",
            "last_seen": datetime.now().isoformat()
        }
    ]

    for idx, eq in enumerate(rows[:13]):
        eq_id = eq["id"]
        if eq_id == "WC-007":
            continue

        batt = eq.get("battery", 80)
        is_low = batt < 20
        rssi = -54 - (idx * 3 % 26)
        loss = round(0.01 + (idx * 0.02 % 0.12), 2)
        latency = 12 + (idx * 2 % 16)
        temp = round(28.5 + (idx * 0.7 % 4.5), 1)

        nodes.append({
            "node_id": f"NODE-{eq_id}",
            "name": f"IoT Telemetry Pod: {eq['name']}",
            "device_class": "Nordic nRF52840 BLE 5.0" if "WC" in eq_id or "STR" in eq_id else "ESP32-S3 Medical Mesh",
            "equipment_id": eq_id,
            "equipment_name": eq["name"],
            "location": eq.get("location", "Central Hospital"),
            "network": {
                "ip": f"172.27.195.{101 + idx}",
                "port": f"BLE UUID-0x{1000 + idx:X}",
                "protocol": "BLE Mesh / 6LoWPAN",
                "rssi": rssi,
                "signal_quality": f"{rssi} dBm (Strong)" if rssi > -70 else f"{rssi} dBm (Fair)",
                "packet_loss": loss,
                "latency_ms": latency
            },
            "power": {
                "battery": batt,
                "voltage": 3.7 if batt > 30 else 3.1,
                "power_source": "Rechargeable LiFePO4" if batt < 100 else "Mains AC Backup",
                "health": "Critically Degraded" if is_low else "Healthy"
            },
            "sensors": {
                "pir_infrared": {
                    "model": "HC-SR501",
                    "pin": "Internal",
                    "state": "DETECTED" if eq["status"] == "IN_USE" else "IDLE",
                    "proximity_radius": "4cm Proximity Radius",
                    "motion_window": "10s Continuous Motion",
                    "motion_timer": "10s Active" if eq["status"] == "IN_USE" else "0s"
                },
                "rfid": {
                    "model": "RC522 13.56 MHz",
                    "last_uid": f"E2 80 6F {idx:02X}",
                    "auth_mode": "Single-Tap RFID Initializer",
                    "status": "Ready"
                },
                "imu": {
                    "motion": "In Motion" if eq["status"] == "IN_USE" else "Stationary",
                    "tilt": round(0.8 + (idx * 0.3 % 2.5), 1),
                    "vibration_g": round(0.01 + (0.05 if eq["status"] == "IN_USE" else 0.0), 2)
                },
                "environment": {
                    "temperature": temp,
                    "humidity": 45 + (idx % 8)
                }
            },
            "firmware_version": "v2.8.0-mesh",
            "status": "ALERT" if is_low else ("ACTIVE" if eq["status"] == "IN_USE" else "ONLINE"),
            "last_seen": datetime.now().isoformat()
        })

    summary = {
        "total_nodes": len(nodes),
        "online_nodes": sum(1 for n in nodes if n["status"] in ["ONLINE", "ACTIVE", "STREAMING"]),
        "alert_nodes": sum(1 for n in nodes if n["status"] == "ALERT" or n["power"]["battery"] < 20),
        "avg_latency_ms": round(sum(n["network"]["latency_ms"] for n in nodes) / len(nodes), 1),
        "avg_battery": round(sum(n["power"]["battery"] for n in nodes) / len(nodes), 1),
        "mesh_health": "99.8% Nominal Uptime"
    }

    return JSONResponse({"summary": summary, "nodes": nodes})

async def api_clinical_reports(request):
    """Returns executive performance reports covering radiology throughput, equipment utilization, and MTBF health."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total, SUM(CASE WHEN status='IN_USE' THEN 1 ELSE 0 END) as in_use FROM equipment")
    eq_stats = cursor.fetchone()
    conn.close()

    total_eq = eq_stats["total"] or 60
    in_use_eq = eq_stats["in_use"] or 38
    util_rate = round((in_use_eq / total_eq) * 100, 1)

    reports = {
        "generated_at": datetime.now().isoformat(),
        "hospital": "St. Jude Metro AI Hospital",
        "executive_summary": {
            "radiology_throughput_today": 184,
            "radiology_on_time_rate": 94.2,
            "hospital_equipment_utilization": util_rate,
            "fleet_mtbf_hours": 1420,
            "preventative_compliance_rate": 98.2,
            "cost_savings_quarter": "$48,200",
            "average_transit_dwell_minutes": 32
        },
        "radiology": {
            "daily_total_scans": 184,
            "target_scans": 195,
            "on_time_rate": 94.2,
            "avg_dwell_reduction_mins": 34,
            "modalities": [
                {
                    "modality": "MRI Scanner (Siemens Magnetom 3T)",
                    "scans_completed": 28,
                    "target_scans": 30,
                    "avg_cycle_mins": 42,
                    "utilization_pct": 88,
                    "status": "OPTIMAL",
                    "lead_technologist": "Dr. Sarah Jenkins"
                },
                {
                    "modality": "CT Scanner (GE Revolution 128-Slice)",
                    "scans_completed": 44,
                    "target_scans": 45,
                    "avg_cycle_mins": 14,
                    "utilization_pct": 92,
                    "status": "PEAK_LOAD",
                    "lead_technologist": "Dr. Priya Sen"
                },
                {
                    "modality": "Digital X-Ray (Philips DigitalDiagnost)",
                    "scans_completed": 86,
                    "target_scans": 90,
                    "avg_cycle_mins": 8,
                    "utilization_pct": 82,
                    "status": "OPTIMAL",
                    "lead_technologist": "Tech Robert Vance"
                },
                {
                    "modality": "Ultrasound Doppler (GE Logiq E10)",
                    "scans_completed": 26,
                    "target_scans": 30,
                    "avg_cycle_mins": 18,
                    "utilization_pct": 75,
                    "status": "AVAILABLE",
                    "lead_technologist": "Dr. Elena Rostova"
                }
            ],
            "bottleneck_insights": "Automated wheelchair pre-staging at Radiology Bay 2 reduced patient transit waiting times by 34 minutes per journey."
        },
        "equipment_utilization": {
            "fleet_size": total_eq,
            "active_in_use": in_use_eq,
            "idle_ready": total_eq - in_use_eq,
            "overall_utilization_pct": util_rate,
            "by_department": [
                {"department": "Emergency & Trauma Ward", "utilization_pct": 94, "deployed": 18, "capacity": 19, "status": "NEAR_CAPACITY"},
                {"department": "Intensive Care Unit (ICU)", "utilization_pct": 91, "deployed": 15, "capacity": 16, "status": "CRITICAL_HIGH"},
                {"department": "Gynaecology & Obstetrics", "utilization_pct": 78, "deployed": 8, "capacity": 10, "status": "BALANCED"},
                {"department": "General Inpatient Wards", "utilization_pct": 72, "deployed": 19, "capacity": 25, "status": "SURPLUS_BUFFER"}
            ],
            "dwell_time_reduction": "Average post-procedure idle dwell dropped from 2.4 hours to 32 minutes via automated PIR movement detection."
        },
        "mtbf_reliability": {
            "mean_time_between_failures_hours": 1420,
            "target_mtbf_hours": 1200,
            "preventative_compliance_pct": 98.2,
            "total_servicing_events_month": 19,
            "unplanned_breakdowns": 1,
            "monitored_fleet": [
                {
                    "equipment_id": "WC-009",
                    "name": "Wheelchair WC-009",
                    "category": "Transport Mobility",
                    "battery": 18,
                    "risk_pct": 88,
                    "mtbf_hours": 940,
                    "directive": "CRITICAL: Battery degradation below 20%. Rapid recharge required within 30 mins."
                },
                {
                    "equipment_id": "VENT-004",
                    "name": "Dräger Evita ICU Ventilator",
                    "category": "Life Support",
                    "battery": 94,
                    "risk_pct": 32,
                    "mtbf_hours": 1840,
                    "directive": "Solenoid valve calibration scheduled in 7 days. Operational reserve active."
                },
                {
                    "equipment_id": "STR-002",
                    "name": "Emergency Trauma Stretcher",
                    "category": "Patient Transfer",
                    "battery": 82,
                    "risk_pct": 24,
                    "mtbf_hours": 1620,
                    "directive": "Hydraulic lift cylinder inspection complete. Certified for code red transit."
                }
            ]
        }
    }
    return JSONResponse(reports)

async def api_demo_simulate(request):
    """Simulates an event for live presentation when hardware is absent."""
    body = await request.json()
    action = body.get("action", "rfid_scan")
    now_str = datetime.now().isoformat()

    if action == "rfid_scan":
        uid = "10 0D 71 5C"
        event = {
            "type": "RFID_SCAN_EVENT",
            "uid": uid,
            "equipment_id": "WC-007",
            "equipment_name": "Wheelchair WC-007 (Smart IoT)",
            "equipment_type": "Wheelchair",
            "location": "Emergency Ward",
            "status": "AVAILABLE",
            "health_score": 96,
            "battery": 82,
            "scanned_at": now_str,
            "message": "✓ WHEELCHAIR WC-007 IDENTIFIED (Transit to Emergency Ward complete)"
        }
        # Update DB location
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE equipment SET location = 'Emergency Ward', room = 'Triage Area', last_updated = ? WHERE id = 'WC-007'", (now_str,))
        cursor.execute("""
            INSERT INTO equipment_movements (equipment_id, from_location, to_location, movement_time, duration_seconds, rfid_scanned_by, status, route_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("WC-007", "Central Storage A", "Emergency Ward", now_str, 42, "Demo RFID Reader", "COMPLETED", "RFID Check-in at Emergency Ward portal"))
        conn.commit()
        conn.close()

        await ws_manager.broadcast(event)
        return JSONResponse(event)

    elif action == "iot_movement":
        batt = random.randint(15, 19)
        temp = round(31.0 + random.uniform(0.1, 0.8), 1)
        event = {
            "type": "ESP32_TELEMETRY",
            "equipment_id": "WC-009",
            "battery": batt,
            "movement": True,
            "temperature": temp,
            "usage_time": 187,
            "location": "Emergency Ward",
            "timestamp": now_str,
            "is_low_battery": True,
            "message": "PIR Motion Detected: Usage Session Active (00:03:17)"
        }
        await ws_manager.broadcast(event)
        return JSONResponse(event)

    elif action == "emergency_surge":
        event = {
            "type": "EMERGENCY_ALERT",
            "request_id": f"REQ-{random.randint(5000, 9999)}",
            "ward_name": "Emergency Ward",
            "equipment_type": "Wheelchair",
            "quantity": 3,
            "priority_score": 94,
            "priority_level": "HIGH",
            "explanation": "Critical trauma triage surge detected. Immediate 3-unit wheelchair allocation requested."
        }
        await ws_manager.broadcast(event)
        return JSONResponse(event)

    return JSONResponse({"status": "unknown_action"})

# --- WebSocket Endpoint ---

async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    global LATEST_HARDWARE_STATE
    if LATEST_HARDWARE_STATE:
        try:
            await websocket.send_text(json.dumps(LATEST_HARDWARE_STATE))
        except Exception:
            pass
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "time": datetime.now().isoformat()}))
                elif msg.get("action") == "get_hardware_state":
                    if LATEST_HARDWARE_STATE:
                        await websocket.send_text(json.dumps(LATEST_HARDWARE_STATE))
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

async def api_esp32_log(request):
    """
    Receives raw console/debug lines from ESP32 via bluetooth_bridge.py
    and broadcasts them to the website's Arduino Serial Monitor terminal in real-time.
    """
    try:
        data = await request.json()
        line = data.get("line", "")
        if line:
            await ws_manager.broadcast({
                "type": "ESP32_HARDWARE_UPDATE",
                "serial_logs": [line]
            })
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)

# --- Frontend Serving ---

async def serve_index(request):
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>MediTrack AI Frontend Building...</h1>")

async def serve_hardware_simulator(request):
    sim_file = FRONTEND_DIR / "hardware-simulator.html"
    if sim_file.exists():
        return FileResponse(sim_file)
    return HTMLResponse("<h1>MediTrack AI Hardware Simulator Building...</h1>")

async def root_handler(request):
    if request.method == "POST":
        return await api_esp32_equipment_update(request)
    return await serve_index(request)

# --- Phase 3: Radiology Operations & Simulation APIs ---

async def api_radiology_dashboard(request):
    """Returns dynamic radiology operations dashboard metrics."""
    return JSONResponse(simulation_engine.get_dashboard_payload())

async def api_radiology_patients(request):
    """Returns synthetic patient dataset with 27 attributes across 7 modalities."""
    params = request.query_params
    modality = params.get("modality")
    priority = params.get("priority")
    status = params.get("status")
    pts = list(simulation_engine.patients)
    if modality:
        pts = [p for p in pts if p["modality"].upper() == modality.upper()]
    if priority:
        pts = [p for p in pts if p["priority"].upper() == priority.upper()]
    if status:
        pts = [p for p in pts if p["report_status"].upper() == status.upper()]
    return JSONResponse({
        "patients": pts,
        "total": len(pts),
        "time_of_day": simulation_engine.get_time_of_day_profile()
    })

async def api_radiology_patient_journey(request):
    """Returns timeline journey and split turnaround stages for specified patient."""
    p_id = request.path_params.get("patient_id", "P-1001")
    journey = simulation_engine.get_patient_journey(p_id)
    if not journey:
        return JSONResponse({"error": f"Patient {p_id} not found"}, status_code=404)
    return JSONResponse(journey)

async def api_radiology_modalities(request):
    """Returns operations summary for the 6 primary radiology modalities."""
    return JSONResponse({"modalities": simulation_engine.get_modality_operations_summary()})

async def api_radiology_bottlenecks(request):
    """Returns AI-detected bottlenecks (Scan Capacity vs Reporting Backlog vs Transport)."""
    return JSONResponse({"insights": simulation_engine.get_ai_bottleneck_insights()})

async def api_simulation_toggle(request):
    """Toggles the autonomous hospital simulation engine ON/OFF."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if "active" in body:
        simulation_engine.is_running = bool(body["active"])
    else:
        simulation_engine.is_running = not simulation_engine.is_running
    return JSONResponse({
        "status": "success",
        "simulation_active": simulation_engine.is_running,
        "message": f"Simulation {'RUNNING' if simulation_engine.is_running else 'PAUSED'}"
    })

async def api_simulation_step(request):
    """Advances the simulation by one operational step."""
    simulation_engine.advance_simulation_step(force=True)
    dash = simulation_engine.get_dashboard_payload()
    await ws_manager.broadcast({
        "type": "RADIOLOGY_QUEUE_UPDATED",
        "data": dash,
        "timestamp": datetime.now().isoformat()
    })
    return JSONResponse({
        "status": "success",
        "simulation_tick": simulation_engine.simulation_tick,
        "data": dash
    })

async def api_simulation_reset(request):
    """Resets the simulation to initial state with reproducible seed 42."""
    simulation_engine.seed = 42
    simulation_engine.rng = random.Random(42)
    simulation_engine.simulation_tick = 0
    simulation_engine.time_offset_minutes = 0
    simulation_engine._generate_initial_dataset()
    dash = simulation_engine.get_dashboard_payload()
    await ws_manager.broadcast({
        "type": "RADIOLOGY_QUEUE_UPDATED",
        "data": dash,
        "timestamp": datetime.now().isoformat()
    })
    return JSONResponse({
        "status": "success",
        "message": "Simulation reset to seed=42",
        "data": dash
    })

# --- Phase 3: Wheelchair Storage Auto-Verification & Temporary Hold APIs ---

async def api_wheelchair_storage_status(request):
    """Returns real-time status of wheelchair storage verification."""
    wc_session = storage_verification_manager.get_session("WC-007")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, location, status, coordinates_x, coordinates_y, last_updated FROM equipment WHERE id = 'WC-007'")
    row = cursor.fetchone()
    wc_item = dict(row) if row else None

    # If countdown elapsed on real clock but async loop hasn't triggered callback yet, finalize immediately:
    if wc_session and wc_session.get("remaining_seconds", 0) <= 0 and wc_item and wc_item.get("status") == "RETURNING_TO_STORAGE":
        await on_storage_verified_callback("WC-007", wc_item.get("location") or "Radiology Wheelchair Storage")
        cursor.execute("SELECT id, name, location, status, coordinates_x, coordinates_y, last_updated FROM equipment WHERE id = 'WC-007'")
        wc_item = dict(cursor.fetchone())

    conn.close()
    return JSONResponse({
        "equipment": wc_item,
        "session": wc_session,
        "is_verifying": wc_session is not None and wc_session.get("remaining_seconds", 0) > 0,
        "remaining_seconds": wc_session["remaining_seconds"] if wc_session else 0,
        "all_active": storage_verification_manager.list_active(),
        "history": storage_verification_manager.history[-5:]
    })

async def api_wheelchair_storage_trigger(request):
    """Triggers return to storage for WC-007 or specified equipment."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    eq_id = body.get("equipment_id", "WC-007")
    loc = body.get("location", "Radiology Wheelchair Storage")
    dur = int(body.get("duration_seconds", 120))

    # If equipment is currently AVAILABLE, prime it into IN_USE first so return flow can be demonstrated seamlessly
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT status FROM equipment WHERE id = ?", (eq_id,))
        row = c.fetchone()
        conn.close()
        if row and row["status"] == "AVAILABLE":
            await canonical_update_equipment_state(
                equipment_id=eq_id,
                target_state="IN_USE",
                location="Emergency Corridor Transfer",
                source="DEMO_RETURN_PREP"
            )
    except Exception as e:
        print(f"[Storage Trigger] Warning priming equipment: {e}")

    ok, result = await canonical_update_equipment_state(
        equipment_id=eq_id,
        target_state="RETURNING_TO_STORAGE",
        location=loc,
        source="STORAGE_RETURN_TRIGGER",
        duration_seconds=dur
    )
    if not ok:
        return JSONResponse(result, status_code=400)
    return JSONResponse(result)

async def api_wheelchair_storage_cancel(request):
    """Cancels active storage verification countdown."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    eq_id = body.get("equipment_id", "WC-007")
    reason = body.get("reason", "Manual cancel or movement detected")
    resumed_to = body.get("resumed_to", "IN_USE")
    ok, result = await canonical_update_equipment_state(
        equipment_id=eq_id,
        target_state=resumed_to,
        reason=reason,
        source="STORAGE_VERIFICATION_CANCEL"
    )
    if not ok:
        return JSONResponse(result, status_code=400)
    return JSONResponse(result)

async def api_temporary_hold_status(request):
    """Returns active temporary hold session with stopwatch calculation."""
    eq_id = request.query_params.get("equipment_id", "WC-007")
    hold = temporary_hold_manager.get_hold(eq_id)
    return JSONResponse({
        "equipment_id": eq_id,
        "is_on_hold": hold is not None,
        "hold": hold,
        "all_active_holds": temporary_hold_manager.active_holds
    })

async def api_temporary_hold_toggle(request):
    """Toggles TEMPORARY_HOLD on/off for equipment."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    eq_id = body.get("equipment_id", "WC-007")
    reason = body.get("reason", "Awaiting patient transfer")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, status, location FROM equipment WHERE id = ?", (eq_id,))
    item = cursor.fetchone()
    conn.close()
    if not item:
        return JSONResponse({"error": "Equipment not found"}, status_code=404)

    curr_status = item["status"]
    target_state = "IN_USE" if curr_status == "TEMPORARY_HOLD" else "TEMPORARY_HOLD"
    ok, result = await canonical_update_equipment_state(
        equipment_id=eq_id,
        target_state=target_state,
        location=item["location"],
        reason=reason,
        source="HOLD_TOGGLE"
    )
    if not ok:
        return JSONResponse(result, status_code=400)
    return JSONResponse(result)

async def api_equipment_state_update(request):
    """Canonical equipment state transition endpoint adhering to strict state machine."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    eq_id = body.get("equipment_id")
    target_state = body.get("status") or body.get("target_state")
    location = body.get("location")
    reason = body.get("reason")
    source = body.get("source", "API_REQUEST")

    if not eq_id or not target_state:
        return JSONResponse({"error": "Missing equipment_id or status"}, status_code=400)

    ok, result = await canonical_update_equipment_state(
        equipment_id=eq_id,
        target_state=target_state,
        location=location,
        source=source,
        reason=reason
    )
    if not ok:
        return JSONResponse(result, status_code=400)
    return JSONResponse(result)

async def run_simulation_ticker():
    """Background task to advance simulation step every 15s."""
    while True:
        try:
            await asyncio.sleep(15)
            if simulation_engine.is_running:
                simulation_engine.advance_simulation_step()
                dash_data = simulation_engine.get_dashboard_payload()
                await ws_manager.broadcast({
                    "type": "RADIOLOGY_QUEUE_UPDATED",
                    "data": dash_data,
                    "timestamp": datetime.now().isoformat()
                })
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app):
    ticker_task = asyncio.create_task(run_simulation_ticker())
    try:
        yield
    finally:
        ticker_task.cancel()

routes = [
    # Auth & Users
    Route("/api/auth/login", api_auth_login, methods=["POST"]),
    Route("/api/auth/me", api_auth_me, methods=["GET"]),
    Route("/api/users", api_users_list, methods=["GET"]),
    Route("/api/users", api_users_create, methods=["POST"]),
    Route("/api/users/{id}", api_users_update, methods=["PUT"]),

    # Role Dashboards
    Route("/api/dashboard/role-view", api_role_dashboard, methods=["GET"]),

    # Blueprint & Location
    Route("/api/blueprint", api_blueprint, methods=["GET"]),
    Route("/api/equipment/location", api_equipment_location_search, methods=["GET"]),
    Route("/api/equipment/movement", api_equipment_movements, methods=["GET"]),
    Route("/api/equipment/transfer", api_equipment_transfer, methods=["POST"]),
    Route("/api/equipment/maintenance-action", api_maintenance_action, methods=["POST"]),

    # Shortages
    Route("/api/shortages", api_shortages_list, methods=["GET"]),
    Route("/api/shortages/ward/{ward_id}", api_shortages_ward, methods=["GET"]),

    # Departments
    Route("/api/department/gynaecology", api_dept_gynaecology, methods=["GET"]),
    Route("/api/department/icu", api_dept_icu, methods=["GET"]),

    # Phase 3 Canonical State & Storage APIs
    Route("/api/equipment/state-update", api_equipment_state_update, methods=["POST"]),
    Route("/api/equipment/wheelchair-storage/status", api_wheelchair_storage_status, methods=["GET"]),
    Route("/api/equipment/wheelchair-storage/trigger", api_wheelchair_storage_trigger, methods=["POST"]),
    Route("/api/equipment/wheelchair-storage/cancel", api_wheelchair_storage_cancel, methods=["POST"]),
    Route("/api/equipment/temporary-hold/status", api_temporary_hold_status, methods=["GET"]),
    Route("/api/equipment/temporary-hold/toggle", api_temporary_hold_toggle, methods=["POST"]),

    # Phase 3 Radiology Operations & Simulation APIs
    Route("/api/radiology/dashboard", api_radiology_dashboard, methods=["GET"]),
    Route("/api/radiology/patients", api_radiology_patients, methods=["GET"]),
    Route("/api/radiology/patient-journey/{patient_id}", api_radiology_patient_journey, methods=["GET"]),
    Route("/api/radiology/patient/{patient_id}", api_radiology_patient_journey, methods=["GET"]),
    Route("/api/radiology/modalities", api_radiology_modalities, methods=["GET"]),
    Route("/api/radiology/bottlenecks", api_radiology_bottlenecks, methods=["GET"]),
    Route("/api/simulation/toggle", api_simulation_toggle, methods=["POST"]),
    Route("/api/simulation/step", api_simulation_step, methods=["POST"]),
    Route("/api/simulation/reset", api_simulation_reset, methods=["POST"]),

    # Existing Core APIs
    Route("/api/stats", api_stats, methods=["GET"]),
    Route("/api/equipment", api_equipment_list, methods=["GET"]),
    Route("/api/equipment/{id}", api_equipment_detail, methods=["GET"]),
    Route("/api/wards", api_wards, methods=["GET"]),
    Route("/api/allocation/evaluate", api_allocation_evaluate, methods=["POST"]),
    Route("/api/allocation/confirm", api_allocation_confirm, methods=["POST"]),
    Route("/api/maintenance/overview", api_maintenance_overview, methods=["GET"]),
    Route("/api/maintenance/{id}", api_maintenance_detail, methods=["GET"]),
    Route("/api/demand/forecast", api_demand_forecast, methods=["GET"]),
    Route("/api/demand/summary", api_demand_summary, methods=["GET"]),
    Route("/api/emergency/request", api_emergency_request_create, methods=["POST"]),
    Route("/api/emergency/requests", api_emergency_requests_list, methods=["GET"]),
    Route("/api/esp32/telemetry", api_esp32_telemetry, methods=["POST"]),
    Route("/api/esp32/rfid", api_esp32_rfid, methods=["POST"]),
    Route("/api/esp32/equipment-update", api_esp32_equipment_update, methods=["POST"]),
    Route("/api/esp32/update", api_esp32_equipment_update, methods=["POST"]),
    Route("/api/esp32/log", api_esp32_log, methods=["POST"]),
    Route("/api/esp32/hardware-state", api_esp32_latest_state, methods=["GET"]),
    Route("/api/iot/nodes", api_iot_nodes, methods=["GET"]),
    Route("/api/reports/clinical", api_clinical_reports, methods=["GET"]),
    Route("/api/rfid/recent", api_rfid_recent, methods=["GET"]),
    Route("/api/vision/detections", api_vision_detections, methods=["GET"]),
    Route("/api/assistant/chat", api_assistant_chat, methods=["POST"]),
    Route("/api/demo/simulate-step", api_demo_simulate, methods=["POST"]),
    WebSocketRoute("/ws", websocket_endpoint),
    Mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static"),
    Route("/hardware-simulator", serve_hardware_simulator, methods=["GET"]),
    Route("/simulator", serve_hardware_simulator, methods=["GET"]),
    Route("/", root_handler, methods=["GET", "POST"]),
]

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

app = Starlette(debug=True, routes=routes, middleware=middleware, lifespan=lifespan)

if __name__ == "__main__":
    import uvicorn
    print("Starting MediTrack AI Server on http://127.0.0.1:8000 ...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
