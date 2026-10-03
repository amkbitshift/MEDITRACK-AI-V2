"""
MediTrack AI - Comprehensive Hospital Seed Data
Includes Role-Based Users, Blueprint-Mapped Equipment Fleet (ICU, Gynaecology, Emergency),
Movement Histories, and AI Emergency Shortage Predictions.
"""

import json
import random
from datetime import datetime, timedelta
try:
    from database.db import get_connection, init_db
except ImportError:
    from db import get_connection, init_db

# RFID Card / Tag Mappings
RFID_MAPPINGS = {
    "10 0D 71 5C": {"id": "WC-007", "type": "Wheelchair", "name": "Heavy-Duty Ergonomic Wheelchair"},
    "30 94 2B 58": {"id": "VENT-04", "type": "Mechanical Ventilator", "name": "Mindray SV300 Mobile Ventilator"},
    "BD 70 00 02": {"id": "ST-003", "type": "Stretcher", "name": "Hydraulic Stretcher ST-003"},
    "21 2F 7B 69": {"id": "INF-03", "type": "Infusion Pump", "name": "Alaris Volumetric Infusion Pump 03"},
    "40 0D 0F 58": {"id": "BP-003", "type": "Blood Pressure Monitor", "name": "Digital Patient Vital BP Monitor"},
    "55 11 AA 01": {"id": "VENT-01", "type": "Mechanical Ventilator", "name": "Servo-U Mechanical ICU Ventilator"},
    "55 11 AA 02": {"id": "VENT-02", "type": "Mechanical Ventilator", "name": "Puritan Bennett 980 Ventilator"},
    "77 22 BB 01": {"id": "DEFIB-01", "type": "Defibrillator", "name": "Biphasic Defibrillator & External Pacer"},
    "88 33 CC 01": {"id": "CRASH-01", "type": "Emergency Crash Cart", "name": "Rapid Response ICU Crash Cart"},
    "99 44 DD 01": {"id": "US-GYN-01", "type": "Ultrasound Machine", "name": "Voluson E10 3D/4D Ultrasound Machine"},
    "99 44 DD 03": {"id": "CTG-01", "type": "CTG Machine", "name": "Dual Channel Fetal Cardiotocograph"},
    "99 44 DD 04": {"id": "LAP-01", "type": "Laparoscopy Cart", "name": "4K Ultra-HD Endoscopic Laparoscopy Tower"}
}

# Role-Based Users Seed
USERS = [
    {
        "id": "user-nurse-1",
        "name": "Nurse Priya Sharma",
        "email": "priya.sharma@stjude-hospital.org",
        "password_hash": "demo123",
        "role": "NURSE",
        "department": "ICU",
        "assigned_ward": "ward-icu",
        "status": "ACTIVE",
        "permissions": ["VIEW_WARD_EQUIPMENT", "VIEW_HOSPITAL_MAP", "CREATE_EQUIPMENT_REQUEST", "VIEW_EMERGENCY_ALERTS", "VIEW_DEPARTMENT", "REQUEST_EQUIPMENT", "VIEW_LIVE_EQUIPMENT"]
    },
    {
        "id": "nurse-priya",
        "name": "Nurse Priya Sharma",
        "email": "priya.nurse@stjude-hospital.org",
        "password_hash": "demo123",
        "role": "NURSE",
        "department": "ICU",
        "assigned_ward": "ward-icu",
        "status": "ACTIVE",
        "permissions": ["VIEW_WARD_EQUIPMENT", "VIEW_HOSPITAL_MAP", "CREATE_EQUIPMENT_REQUEST", "VIEW_EMERGENCY_ALERTS", "VIEW_DEPARTMENT", "REQUEST_EQUIPMENT", "VIEW_LIVE_EQUIPMENT"]
    },
    {
        "id": "user-doc-1",
        "name": "Dr. Ananya Sen (MD)",
        "email": "ananya.sen@stjude-hospital.org",
        "password_hash": "demo123",
        "role": "DOCTOR",
        "department": "ICU",
        "assigned_ward": "ward-icu",
        "status": "ACTIVE",
        "permissions": ["VIEW_WARD_EQUIPMENT", "VIEW_HOSPITAL_MAP", "CREATE_EQUIPMENT_REQUEST", "VIEW_EMERGENCY_ALERTS", "VIEW_DEPARTMENT", "VIEW_ANALYTICS", "VIEW_CLINICAL_INSIGHTS", "VIEW_LIVE_EQUIPMENT", "TRANSFER_EQUIPMENT"]
    },
    {
        "id": "doc-ananya",
        "name": "Dr. Ananya Sen (MD)",
        "email": "ananya.doc@stjude-hospital.org",
        "password_hash": "demo123",
        "role": "DOCTOR",
        "department": "ICU",
        "assigned_ward": "ward-icu",
        "status": "ACTIVE",
        "permissions": ["VIEW_WARD_EQUIPMENT", "VIEW_HOSPITAL_MAP", "CREATE_EQUIPMENT_REQUEST", "VIEW_EMERGENCY_ALERTS", "VIEW_DEPARTMENT", "VIEW_ANALYTICS", "VIEW_CLINICAL_INSIGHTS", "VIEW_LIVE_EQUIPMENT", "TRANSFER_EQUIPMENT"]
    },
    {
        "id": "mgr-marcus",
        "name": "Marcus Reed",
        "email": "marcus.reed@stjude-hospital.org",
        "password_hash": "demo123",
        "role": "EQUIPMENT_MANAGER",
        "department": "Equipment Control",
        "assigned_ward": "ward-storage-a",
        "status": "ACTIVE",
        "permissions": [
            "VIEW_WARD_EQUIPMENT", "VIEW_HOSPITAL_MAP", "CREATE_EQUIPMENT_REQUEST",
            "VIEW_EMERGENCY_ALERTS", "VIEW_MAINTENANCE", "MANAGE_EQUIPMENT",
            "ALLOCATE_EQUIPMENT", "VIEW_IOT", "VIEW_ANALYTICS", "VIEW_DEPARTMENT",
            "TRANSFER_EQUIPMENT", "SCHEDULE_MAINTENANCE", "VIEW_SHORTAGES"
        ]
    },
    {
        "id": "admin-vance",
        "name": "Dr. Alex Vance",
        "email": "alex.vance@stjude-hospital.org",
        "password_hash": "demo123",
        "role": "ADMIN",
        "department": "Hospital Administration",
        "assigned_ward": "all",
        "status": "ACTIVE",
        "permissions": [
            "ALL", "VIEW_WARD_EQUIPMENT", "VIEW_HOSPITAL_MAP", "CREATE_EQUIPMENT_REQUEST",
            "VIEW_EMERGENCY_ALERTS", "VIEW_MAINTENANCE", "MANAGE_EQUIPMENT",
            "ALLOCATE_EQUIPMENT", "VIEW_IOT", "VIEW_ANALYTICS", "VIEW_DEPARTMENT",
            "TRANSFER_EQUIPMENT", "SCHEDULE_MAINTENANCE", "VIEW_SHORTAGES",
            "MANAGE_USERS", "MANAGE_SYSTEM"
        ]
    }
]

# Wards & Hospital Blueprint Areas
WARDS = [
    {"id": "ward-emergency", "name": "Emergency Ward", "type": "Emergency", "current_urgency": "CRITICAL", "bed_capacity": 30, "occupied_beds": 28, "pos_x": 75.0, "pos_y": 20.0},
    {"id": "ward-icu", "name": "Intensive Care Unit (ICU)", "type": "ICU", "current_urgency": "HIGH", "bed_capacity": 20, "occupied_beds": 18, "pos_x": 78.0, "pos_y": 68.0},
    {"id": "ward-gynae", "name": "Gynaecology Department", "type": "Gynaecology", "current_urgency": "MODERATE", "bed_capacity": 25, "occupied_beds": 19, "pos_x": 22.0, "pos_y": 68.0},
    {"id": "ward-gen-a", "name": "General Ward A", "type": "General", "current_urgency": "NORMAL", "bed_capacity": 45, "occupied_beds": 32, "pos_x": 22.0, "pos_y": 20.0},
    {"id": "ward-gen-b", "name": "General Ward B", "type": "General", "current_urgency": "NORMAL", "bed_capacity": 45, "occupied_beds": 29, "pos_x": 22.0, "pos_y": 42.0},
    {"id": "ward-ot", "name": "Operation Theatre (OT)", "type": "Surgical", "current_urgency": "HIGH", "bed_capacity": 10, "occupied_beds": 8, "pos_x": 50.0, "pos_y": 14.0},
    {"id": "ward-storage-a", "name": "Central Storage A", "type": "Storage", "current_urgency": "NORMAL", "bed_capacity": 50, "occupied_beds": 0, "pos_x": 48.0, "pos_y": 48.0},
    {"id": "ward-storage-b", "name": "Annex Storage B (Repairs)", "type": "Storage", "current_urgency": "NORMAL", "bed_capacity": 30, "occupied_beds": 0, "pos_x": 50.0, "pos_y": 85.0},
    {"id": "ward-pharmacy", "name": "Central Pharmacy", "type": "Pharmacy", "current_urgency": "NORMAL", "bed_capacity": 15, "occupied_beds": 0, "pos_x": 12.0, "pos_y": 48.0},
    {"id": "ward-lab", "name": "Pathology Laboratory", "type": "Laboratory", "current_urgency": "NORMAL", "bed_capacity": 15, "occupied_beds": 0, "pos_x": 88.0, "pos_y": 45.0},
    {"id": "ward-radiology", "name": "Radiology & Imaging", "type": "Radiology", "current_urgency": "NORMAL", "bed_capacity": 10, "occupied_beds": 0, "pos_x": 50.0, "pos_y": 32.0},
    {"id": "ward-control", "name": "Equipment Control Room", "type": "Control", "current_urgency": "NORMAL", "bed_capacity": 10, "occupied_beds": 0, "pos_x": 42.0, "pos_y": 66.0}
]

def generate_equipment():
    equipment = []

    # --- 1. Emergency & Storage Key Equipment (Hackathon Demo Items) ---
    equipment.append({
        "id": "WC-007", "name": "Wheelchair WC-007 (Smart IoT)", "type": "Wheelchair",
        "status": "AVAILABLE", "location": "Central Storage A", "department": "Emergency", "room": "Fleet Storage Bay",
        "battery": 82, "health_score": 96, "usage_hours": 187.0, "movement_count": 4210,
        "days_since_maintenance": 12, "equipment_age_years": 1.2, "previous_faults": 0,
        "temperature": 26.4, "rfid_uid": "10 0D 71 5C", "coordinates_x": 47.0, "coordinates_y": 46.0,
        "category": "TRACKABLE", "is_emergency_ready": 1
    })

    equipment.append({
        "id": "WC-012", "name": "Wheelchair WC-012", "type": "Wheelchair",
        "status": "AVAILABLE", "location": "Central Storage A", "department": "Emergency", "room": "Fleet Storage Bay",
        "battery": 78, "health_score": 91, "usage_hours": 240.5, "movement_count": 5930,
        "days_since_maintenance": 18, "equipment_age_years": 1.5, "previous_faults": 1,
        "temperature": 27.1, "rfid_uid": "10 0D 71 6A", "coordinates_x": 49.0, "coordinates_y": 49.0,
        "category": "TRACKABLE", "is_emergency_ready": 1
    })

    equipment.append({
        "id": "WC-014", "name": "Wheelchair WC-014 (High Risk)", "type": "Wheelchair",
        "status": "MAINTENANCE", "location": "Annex Storage B (Repairs)", "department": "General", "room": "Repairs Workshop",
        "battery": 64, "health_score": 72, "usage_hours": 487.2, "movement_count": 12481,
        "days_since_maintenance": 74, "equipment_age_years": 2.4, "previous_faults": 2,
        "temperature": 34.2, "rfid_uid": "10 0D 71 8E", "coordinates_x": 51.0, "coordinates_y": 86.0,
        "category": "TRACKABLE", "is_emergency_ready": 0
    })

    equipment.append({
        "id": "WC-018", "name": "Wheelchair WC-018", "type": "Wheelchair",
        "status": "AVAILABLE", "location": "General Ward A", "department": "General", "room": "General Corridor",
        "battery": 94, "health_score": 94, "usage_hours": 142.0, "movement_count": 3100,
        "days_since_maintenance": 9, "equipment_age_years": 0.8, "previous_faults": 0,
        "temperature": 25.8, "rfid_uid": "10 0D 71 9F", "coordinates_x": 27.0, "coordinates_y": 28.0,
        "category": "TRACKABLE", "is_emergency_ready": 1
    })

    equipment.append({
        "id": "WC-009", "name": "Wheelchair WC-009 (Low Battery Alert)", "type": "Wheelchair",
        "status": "IN_USE", "location": "Emergency Ward", "department": "Emergency", "room": "Triage Area",
        "battery": 18, "health_score": 84, "usage_hours": 320.0, "movement_count": 8920,
        "days_since_maintenance": 32, "equipment_age_years": 1.8, "previous_faults": 1,
        "temperature": 31.4, "rfid_uid": "10 0D 71 3B", "coordinates_x": 76.0, "coordinates_y": 23.0,
        "category": "TRACKABLE", "is_emergency_ready": 0
    })

    equipment.append({
        "id": "ST-003", "name": "Hydraulic Stretcher ST-003", "type": "Stretcher",
        "status": "AVAILABLE", "location": "Central Storage A", "department": "Emergency", "room": "Fleet Storage Bay",
        "battery": 92, "health_score": 94, "usage_hours": 110.0, "movement_count": 2840,
        "days_since_maintenance": 14, "equipment_age_years": 0.9, "previous_faults": 0,
        "temperature": 26.0, "rfid_uid": "BD 70 00 02", "coordinates_x": 48.0, "coordinates_y": 50.0,
        "category": "TRACKABLE", "is_emergency_ready": 1
    })

    equipment.append({
        "id": "OX-015", "name": "Medical Oxygen Cylinder 10L", "type": "Oxygen Cylinder",
        "status": "AVAILABLE", "location": "Central Storage A", "department": "General", "room": "Gas Depot",
        "battery": 100, "health_score": 98, "usage_hours": 45.0, "movement_count": 800,
        "days_since_maintenance": 5, "equipment_age_years": 0.5, "previous_faults": 0,
        "temperature": 24.5, "rfid_uid": "OX-015-TAG", "coordinates_x": 46.0, "coordinates_y": 47.0,
        "category": "TRACKABLE", "is_emergency_ready": 1
    })

    equipment.append({
        "id": "BP-003", "name": "Smart BP Monitor Station", "type": "Blood Pressure Monitor",
        "status": "AVAILABLE", "location": "General Ward B", "department": "General", "room": "Nurse Station B",
        "battery": 75, "health_score": 93, "usage_hours": 180.0, "movement_count": 3200,
        "days_since_maintenance": 21, "equipment_age_years": 1.1, "previous_faults": 0,
        "temperature": 25.5, "rfid_uid": "40 0D 0F 58", "coordinates_x": 24.0, "coordinates_y": 44.0,
        "category": "TRACKABLE", "is_emergency_ready": 1
    })

    equipment.append({
        "id": "FA-004", "name": "Rapid Response Trauma Kit", "type": "First Aid Kit",
        "status": "AVAILABLE", "location": "Emergency Ward", "department": "Emergency", "room": "Trauma Bay 1",
        "battery": 100, "health_score": 100, "usage_hours": 12.0, "movement_count": 450,
        "days_since_maintenance": 3, "equipment_age_years": 0.3, "previous_faults": 0,
        "temperature": 24.0, "rfid_uid": "FA-004-TAG", "coordinates_x": 78.0, "coordinates_y": 18.0,
        "category": "TRACKABLE", "is_emergency_ready": 1
    })

    # --- 2. ICU Trackable Assets (Dedicated Section) ---
    icu_assets = [
        ("BD-ICU-01", "Motorized Smart ICU Bed 01", "ICU Bed", "IN_USE", "ICU Bed 01", 98, 95, 620.0, 14, 28.1, "BD-ICU-TAG-01", 72.0, 64.0),
        ("BD-ICU-02", "Motorized Smart ICU Bed 02", "ICU Bed", "IN_USE", "ICU Bed 02", 96, 92, 580.0, 20, 27.8, "30 94 2B 59", 84.0, 64.0),
        ("BD-ICU-03", "Motorized Smart ICU Bed 03", "ICU Bed", "AVAILABLE", "ICU Bed 03", 95, 94, 430.0, 8, 26.5, "30 94 2B 60", 72.0, 75.0),
        ("BD-ICU-04", "Motorized Smart ICU Bed 04", "ICU Bed", "AVAILABLE", "ICU Bed 04", 91, 90, 490.0, 15, 27.0, "30 94 2B 61", 84.0, 75.0),
        ("MON-ICU-01", "Multiparameter Patient Monitor 01", "Multiparameter Monitor", "IN_USE", "ICU Bed 01", 100, 98, 890.0, 5, 29.4, "MON-001", 73.0, 63.0),
        ("MON-ICU-02", "Multiparameter Patient Monitor 02", "Multiparameter Monitor", "IN_USE", "ICU Bed 02", 82, 74, 950.0, 38, 32.1, "MON-002", 85.0, 63.0),
        ("MON-ICU-03", "Multiparameter Patient Monitor 03", "Multiparameter Monitor", "AVAILABLE", "ICU Bed 03", 94, 96, 320.0, 10, 26.8, "MON-003", 73.0, 74.0),
        ("MON-ICU-04", "Multiparameter Patient Monitor 04", "Multiparameter Monitor", "AVAILABLE", "ICU Bed 04", 96, 97, 280.0, 12, 27.2, "MON-004", 85.0, 74.0),
        ("VENT-01", "Servo-U Mechanical Ventilator", "Mechanical Ventilator", "IN_USE", "ICU Bed 01", 94, 96, 450.0, 12, 30.2, "55 11 AA 01", 71.0, 63.0),
        ("VENT-02", "Puritan Bennett 980 Ventilator", "Mechanical Ventilator", "IN_USE", "ICU Bed 02", 90, 92, 510.0, 16, 29.8, "55 11 AA 02", 83.0, 63.0),
        ("VENT-03", "Hamilton-G5 ICU Ventilator", "Mechanical Ventilator", "IN_USE", "ICU Bed 03", 76, 76, 720.0, 42, 33.4, "55 11 AA 03", 71.0, 74.0),
        ("VENT-04", "Mindray SV300 Mobile Ventilator", "Mechanical Ventilator", "AVAILABLE", "ICU Equipment Storage", 98, 95, 120.0, 6, 25.4, "30 94 2B 58", 78.0, 72.0),
        ("DEFIB-01", "Biphasic Defibrillator & Pacer", "Defibrillator", "AVAILABLE", "ICU Equipment Storage", 100, 99, 45.0, 4, 24.8, "77 22 BB 01", 77.0, 74.0),
        ("INF-01", "Alaris Volumetric Infusion Pump 01", "Infusion Pump", "IN_USE", "ICU Bed 01", 88, 94, 380.0, 14, 27.5, "INF-001", 74.0, 65.0),
        ("INF-02", "Alaris Volumetric Infusion Pump 02", "Infusion Pump", "IN_USE", "ICU Bed 02", 85, 93, 410.0, 18, 28.0, "INF-002", 86.0, 65.0),
        ("INF-03", "Alaris Volumetric Infusion Pump 03", "Infusion Pump", "AVAILABLE", "ICU Equipment Storage", 95, 97, 95.0, 8, 25.1, "21 2F 7B 69", 79.0, 74.0),
        ("INF-04", "Alaris Volumetric Infusion Pump 04", "Infusion Pump", "AVAILABLE", "ICU Equipment Storage", 94, 96, 110.0, 11, 25.5, "INF-004", 80.0, 74.0),
        ("SYR-01", "Precision Syringe Micro-Pump 01", "Syringe Pump", "IN_USE", "ICU Bed 03", 82, 89, 420.0, 24, 28.4, "SYR-001", 74.0, 76.0),
        ("SYR-02", "Precision Syringe Micro-Pump 02", "Syringe Pump", "AVAILABLE", "ICU Equipment Storage", 96, 95, 80.0, 7, 24.9, "SYR-002", 79.0, 76.0),
        ("SUCT-01", "Mobile High-Vacuum Suction Machine", "Suction Machine", "AVAILABLE", "ICU Equipment Storage", 92, 94, 65.0, 15, 26.2, "SUCT-001", 81.0, 72.0),
        ("XRAY-01", "Mobile Digital C-Arm X-Ray Unit", "Portable X-Ray Machine", "AVAILABLE", "ICU Equipment Storage", 95, 96, 85.0, 9, 25.8, "XRAY-001", 82.0, 75.0),
        ("ECG-01", "12-Lead Diagnostic ECG Station", "ECG Machine", "AVAILABLE", "ICU Equipment Storage", 90, 95, 140.0, 14, 26.0, "ECG-001", 78.0, 76.0),
        ("ABG-01", "Point-of-Care Blood Gas Analyzer", "Blood Gas Analyzer", "AVAILABLE", "ICU Nurse Station", 98, 98, 210.0, 5, 25.0, "ABG-001", 76.0, 68.0),
        ("CRASH-01", "ICU Emergency Crash Cart", "Emergency Crash Cart", "AVAILABLE", "ICU Crash Cart Area", 100, 100, 15.0, 2, 24.2, "88 33 CC 01", 86.0, 72.0),
        ("NEB-01", "Ultrasonic Hospital Nebulizer", "Nebulizer", "AVAILABLE", "ICU Equipment Storage", 89, 93, 75.0, 16, 26.3, "NEB-001", 80.0, 75.0),
        ("EQ-ICU-001", "ICU Bedside Multi-Monitor EQ-001", "Multiparameter Monitor", "AVAILABLE", "Bed 01", 96, 95, 210.0, 8, 26.2, "RFID-EQ-ICU-001", 72.0, 63.0)
    ]
    for eq_id, name, eq_type, status, room, batt, health, usage, days_maint, temp, rfid, cx, cy in icu_assets:
        equipment.append({
            "id": eq_id, "name": name, "type": eq_type, "status": status,
            "location": "Intensive Care Unit (ICU)", "department": "ICU", "room": room,
            "battery": batt, "health_score": health, "usage_hours": usage,
            "movement_count": int(usage * 8), "days_since_maintenance": days_maint,
            "equipment_age_years": 1.1, "previous_faults": 0 if health > 90 else 1,
            "temperature": temp, "rfid_uid": rfid, "coordinates_x": cx, "coordinates_y": cy,
            "category": "TRACKABLE", "is_emergency_ready": 1 if status == "AVAILABLE" else 0
        })

    # --- 3. Gynaecology Trackable Assets (Dedicated Section) ---
    gynae_assets = [
        ("ET-GYN-01", "Gynaecological Examination Table", "Gynaecological Exam Table", "AVAILABLE", "Examination Room 1", 100, 96, 210.0, 10, 25.1, "ET-001", 18.0, 64.0),
        ("EL-GYN-01", "Surgical Examination Shadowless Light", "Examination Light", "AVAILABLE", "Examination Room 1", 100, 98, 150.0, 6, 26.0, "EL-001", 19.0, 63.0),
        ("US-GYN-01", "Voluson E10 3D/4D Ultrasound Machine", "Ultrasound Machine", "IN_USE", "Ultrasound Room", 90, 94, 380.0, 14, 28.5, "99 44 DD 01", 26.0, 64.0),
        ("US-GYN-02", "Mobile High-Res Ultrasound Console", "Ultrasound Machine", "AVAILABLE", "Ultrasound Room", 95, 92, 290.0, 18, 27.2, "99 44 DD 02", 28.0, 65.0),
        ("FD-GYN-01", "Fetal Acoustic Heart Doppler", "Fetal Doppler", "AVAILABLE", "CTG Room", 88, 97, 85.0, 8, 24.8, "FD-001", 18.0, 72.0),
        ("CTG-01", "Dual Channel Cardiotocograph", "CTG Machine", "AVAILABLE", "CTG Room", 92, 95, 160.0, 12, 26.1, "99 44 DD 03", 20.0, 73.0),
        ("COLP-01", "High-Definition Video Colposcope", "Colposcope", "MAINTENANCE", "Procedure Room", 74, 76, 320.0, 58, 31.8, "COLP-001", 26.0, 72.0),
        ("HYST-01", "Integrated Hysteroscope Fluid Cart", "Hysteroscope System", "AVAILABLE", "Procedure Room", 91, 93, 140.0, 15, 27.0, "HYST-001", 28.0, 73.0),
        ("LAP-01", "4K Endoscopic Laparoscopy Tower", "Laparoscopy Cart", "AVAILABLE", "Laparoscopy Room", 98, 97, 190.0, 9, 26.5, "99 44 DD 04", 23.0, 78.0),
        ("ESU-01", "Electrosurgical Diathermy Generator", "Diathermy Unit", "AVAILABLE", "Laparoscopy Room", 96, 95, 160.0, 11, 26.8, "ESU-001", 25.0, 78.0)
    ]
    for eq_id, name, eq_type, status, room, batt, health, usage, days_maint, temp, rfid, cx, cy in gynae_assets:
        equipment.append({
            "id": eq_id, "name": name, "type": eq_type, "status": status,
            "location": "Gynaecology Department", "department": "Gynaecology", "room": room,
            "battery": batt, "health_score": health, "usage_hours": usage,
            "movement_count": int(usage * 6), "days_since_maintenance": days_maint,
            "equipment_age_years": 1.4, "previous_faults": 0 if health > 85 else 1,
            "temperature": temp, "rfid_uid": rfid, "coordinates_x": cx, "coordinates_y": cy,
            "category": "TRACKABLE", "is_emergency_ready": 1 if status == "AVAILABLE" else 0
        })

    # Additional batch fleet to reach 75+ realistic hospital equipment items
    general_batches = [
        ("Wheelchair", "WC", 15, "General Ward A", "General"),
        ("Hospital Bed", "BD", 10, "General Ward B", "General"),
        ("Stretcher", "ST", 6, "Emergency Ward", "Emergency"),
        ("Oxygen Cylinder", "OX", 8, "Central Storage A", "General"),
        ("Walker", "WK", 6, "General Ward A", "General")
    ]
    for eq_type, prefix, count, def_loc, dept in general_batches:
        for i in range(1, count + 1):
            eq_id = f"{prefix}-{i:03d}"
            if any(e["id"] == eq_id for e in equipment):
                continue
            status = random.choices(["AVAILABLE", "IN_USE", "MAINTENANCE"], weights=[0.60, 0.32, 0.08])[0]
            health = random.randint(75, 99) if status != "MAINTENANCE" else random.randint(48, 73)
            batt = random.randint(35, 99)
            usage = round(random.uniform(25.0, 500.0), 1)

            equipment.append({
                "id": eq_id, "name": f"{eq_type} {eq_id}", "type": eq_type,
                "status": status, "location": def_loc, "department": dept,
                "room": "General Corridor", "battery": batt, "health_score": health,
                "usage_hours": usage, "movement_count": int(usage * 15),
                "days_since_maintenance": random.randint(4, 70),
                "equipment_age_years": round(random.uniform(0.5, 3.0), 1),
                "previous_faults": 0 if health > 80 else 1,
                "temperature": round(random.uniform(24.0, 31.0), 1),
                "rfid_uid": f"RFID-{eq_id}",
                "coordinates_x": round(random.uniform(15.0, 85.0), 1),
                "coordinates_y": round(random.uniform(18.0, 80.0), 1),
                "category": "TRACKABLE", "is_emergency_ready": 1 if status == "AVAILABLE" else 0
            })

    return equipment

def seed():
    conn = get_connection()
    cursor = conn.cursor()
    # Drop legacy tables so new columns are recreated cleanly
    tables = ["users", "equipment", "wards", "equipment_movements", "shortage_predictions", 
              "sensor_telemetry", "rfid_scans", "maintenance_logs", "equipment_requests", 
              "demand_forecasts", "vision_detections"]
    for t in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {t}")
    conn.commit()
    conn.close()

    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    now_str = datetime.now().isoformat()

    # 1. Insert Users
    for u in USERS:
        cursor.execute("""
        INSERT INTO users (id, name, email, password_hash, role, department, assigned_ward, status, last_active, permissions)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (u["id"], u["name"], u["email"], u["password_hash"], u["role"], u["department"], u["assigned_ward"], u["status"], now_str, json.dumps(u["permissions"])))

    # 2. Insert Wards
    for w in WARDS:
        cursor.execute("""
        INSERT INTO wards (id, name, type, current_urgency, bed_capacity, occupied_beds, pos_x, pos_y)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (w["id"], w["name"], w["type"], w["current_urgency"], w["bed_capacity"], w["occupied_beds"], w["pos_x"], w["pos_y"]))

    # 3. Insert Equipment
    equipment_list = generate_equipment()
    for e in equipment_list:
        cursor.execute("""
        INSERT INTO equipment (
            id, name, type, status, location, department, room, category, is_emergency_ready,
            battery, health_score, usage_hours, movement_count, days_since_maintenance,
            equipment_age_years, previous_faults, temperature, rfid_uid, last_updated,
            coordinates_x, coordinates_y
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            e["id"], e["name"], e["type"], e["status"], e["location"], e["department"], e["room"],
            e.get("category", "TRACKABLE"), e.get("is_emergency_ready", 1),
            e["battery"], e["health_score"], e["usage_hours"], e["movement_count"],
            e["days_since_maintenance"], e["equipment_age_years"], e["previous_faults"],
            e["temperature"], e["rfid_uid"], now_str, e["coordinates_x"], e["coordinates_y"]
        ))

    # 4. Insert Movement History
    movement_samples = [
        ("WC-007", "Central Storage A", "Emergency Ward", (datetime.now() - timedelta(minutes=45)).isoformat(), 42, "nurse-priya", "COMPLETED", "Transit via Corridor B directly to Emergency Triage"),
        ("VENT-02", "Central Storage A", "Intensive Care Unit (ICU)", (datetime.now() - timedelta(hours=2)).isoformat(), 78, "doc-ananya", "COMPLETED", "Staged via Service Elevator A to ICU Bed 02"),
        ("WC-014", "Emergency Ward", "Annex Storage B (Repairs)", (datetime.now() - timedelta(hours=5)).isoformat(), 110, "mgr-marcus", "COMPLETED", "Sidelined due to motor bearing heat warning (78% risk)"),
        ("US-GYN-01", "Central Storage A", "Gynaecology Department", (datetime.now() - timedelta(hours=8)).isoformat(), 55, "doc-ananya", "COMPLETED", "Positioned in Ultrasound Room for high-risk maternal clinic"),
        ("DEFIB-01", "Emergency Ward", "Intensive Care Unit (ICU)", (datetime.now() - timedelta(days=1)).isoformat(), 65, "nurse-priya", "COMPLETED", "Emergency transfer following cardiovascular admission")
    ]
    for mov in movement_samples:
        cursor.execute("""
        INSERT INTO equipment_movements (equipment_id, from_location, to_location, movement_time, duration_seconds, rfid_scanned_by, status, route_description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, mov)

    # 5. Insert Shortage Predictions (AI Decision-Support Feature)
    shortage_samples = [
        ("ward-icu", "Intensive Care Unit (ICU)", "Mechanical Ventilator", 3, 7, 10, 3, 2.4, "HIGH",
         "Shortage predicted because ICU severe respiratory intake increased by 27% over last 4 hours while VENT-03 is showing warning wear and 1 unit is undergoing maintenance.",
         "Transfer 2 ventilators (VENT-04 and Central Storage standby) to ICU within next 2.4 hours before peak admissions.", now_str),
        ("ward-icu", "Intensive Care Unit (ICU)", "Infusion Pump", 4, 8, 11, 3, 3.2, "MODERATE",
         "ICU bed occupancy reached 90% (18/20 beds). Each multi-trauma patient requires minimum 2 infusion lines.",
         "Pre-stage 2 volumetric infusion pumps from General Ward A into ICU Equipment Storage.", now_str),
        ("ward-emergency", "Emergency Ward", "Wheelchair", 8, 11, 13, 5, 1.8, "HIGH",
         "Trauma ambulance triage influx from regional highway collision incoming. Emergency fleet current available is 8 vs 13 anticipated.",
         "Immediate automated dispatch of 3 wheelchairs (WC-007, WC-012, WC-018) from Central Storage A.", now_str),
        ("ward-gynae", "Gynaecology Department", "Ultrasound Machine", 1, 2, 3, 1, 4.8, "POSSIBLE",
         "Scheduled high-resolution obstetric scans scheduled in evening clinic from 18:00 to 21:00.",
         "Prepare mobile ultrasound console US-GYN-02 and verify battery calibration prior to clinic start.", now_str)
    ]
    for sp in shortage_samples:
        cursor.execute("""
        INSERT INTO shortage_predictions (ward_id, ward_name, equipment_type, current_available, current_demand, predicted_demand_3h, expected_shortage, time_to_shortage_hours, severity, explanation, ai_recommendation, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, sp)

    # 6. Sample RFID Scans
    sample_scans = [
        ("10 0D 71 5C", "WC-007", "Wheelchair", "Central Storage A", "AVAILABLE", (datetime.now() - timedelta(minutes=2)).isoformat()),
        ("55 11 AA 01", "VENT-01", "Mechanical Ventilator", "Intensive Care Unit (ICU)", "IN_USE", (datetime.now() - timedelta(minutes=10)).isoformat()),
        ("99 44 DD 01", "US-GYN-01", "Ultrasound Machine", "Gynaecology Department", "IN_USE", (datetime.now() - timedelta(minutes=25)).isoformat()),
        ("30 94 2B 58", "BD-021", "Hospital Bed", "Intensive Care Unit (ICU)", "IN_USE", (datetime.now() - timedelta(minutes=35)).isoformat())
    ]
    for scan in sample_scans:
        cursor.execute("""
        INSERT INTO rfid_scans (uid, equipment_id, equipment_type, location, status, scanned_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, scan)

    # 7. Telemetry Snapshot
    telemetry_samples = [
        ("WC-009", 18, 1, 31.4, 187, "Emergency Ward", now_str),
        ("VENT-01", 94, 1, 30.2, 450, "Intensive Care Unit (ICU)", now_str),
        ("US-GYN-01", 90, 1, 28.5, 380, "Gynaecology Department", now_str),
        ("WC-014", 64, 0, 34.2, 487, "Annex Storage B (Repairs)", now_str)
    ]
    for tel in telemetry_samples:
        cursor.execute("""
        INSERT INTO sensor_telemetry (equipment_id, battery, movement, temperature, usage_time, location, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, tel)

    # 8. Maintenance Logs
    maint_samples = [
        ("WC-014", "PREDICTIVE_ALERT", "High bearing wear and motor thermal rise detected. Failure probability 78%.", 78, (datetime.now() + timedelta(days=8)).strftime("%Y-%m-%d"), "PENDING", now_str),
        ("COLP-01", "OPTICAL_CALIBRATION", "LED illumination lens degraded. White balance sensor requires calibration.", 62, (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d"), "PENDING", now_str),
        ("VENT-03", "VALVE_INSPECTION", "Expiratory flow sensor drift noted. Recalibration scheduled.", 45, (datetime.now() + timedelta(days=12)).strftime("%Y-%m-%d"), "PENDING", now_str)
    ]
    for m in maint_samples:
        cursor.execute("""
        INSERT INTO maintenance_logs (equipment_id, maintenance_type, findings, risk_score, recommended_date, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, m)

    # 9. Emergency Request
    cursor.execute("""
    INSERT INTO equipment_requests (
        id, ward_id, equipment_type, quantity, patient_status, priority_score, priority_level, status, reason, allocated_equipment, requested_by, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "REQ-8891", "ward-emergency", "Wheelchair", 3, "Critical", 94, "HIGH", "ALLOCATED",
        "Trauma triage influx following highway collision.",
        json.dumps(["WC-007", "WC-012", "WC-018"]), "nurse-priya", now_str
    ))

    # 10. Vision Detections
    cursor.execute("""
    INSERT INTO vision_detections (zone, equipment_type, detected_count, database_count, mismatch, confidence_avg, timestamp)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("Zone A - Triage Hub", "Wheelchair", 12, 15, -3, 0.94, now_str))

    conn.commit()
    conn.close()
    print(f"Successfully seeded database with {len(equipment_list)} equipment items, {len(USERS)} users, and operational data.")

if __name__ == "__main__":
    seed()
