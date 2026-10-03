"""
MediTrack AI - Database Layer
SQLite / PostgreSQL compatible schema with fast in-memory caching, persistent storage,
role-based access control, architectural blueprint mapping, and department digital twins.
"""

import sqlite3
import json
import os
import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "meditrack.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Users Table (Role-Based Access Control)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,           -- 'NURSE', 'DOCTOR', 'EQUIPMENT_MANAGER', 'ADMIN'
        department TEXT NOT NULL,     -- 'ICU', 'Gynaecology', 'Emergency', 'Equipment Control', 'Hospital Administration'
        assigned_ward TEXT,           -- 'ward-icu', 'ward-gynae', 'ward-emergency', etc.
        status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'DISABLED'
        last_active TEXT NOT NULL,
        permissions TEXT NOT NULL     -- JSON array of permission strings
    );
    """)

    # 2. Equipment Table (Enhanced with department, room, category)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS equipment (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        status TEXT NOT NULL,          -- 'AVAILABLE', 'IN_USE', 'MAINTENANCE', 'RESERVED'
        location TEXT NOT NULL,        -- 'Emergency Ward', 'ICU', 'Gynaecology Department', etc.
        department TEXT NOT NULL DEFAULT 'General', -- 'ICU', 'Gynaecology', 'Emergency', etc.
        room TEXT NOT NULL DEFAULT 'General Area',  -- Specific room name in blueprint
        category TEXT NOT NULL DEFAULT 'TRACKABLE', -- 'TRACKABLE', 'NON_TRACKED_INSTRUMENT', 'FIXED_INFRASTRUCTURE'
        is_emergency_ready INTEGER DEFAULT 1,       -- 1 or 0
        battery INTEGER NOT NULL,      -- 0 - 100
        health_score INTEGER NOT NULL, -- 0 - 100
        usage_hours REAL NOT NULL,
        movement_count INTEGER NOT NULL,
        days_since_maintenance INTEGER NOT NULL,
        equipment_age_years REAL NOT NULL,
        previous_faults INTEGER NOT NULL,
        temperature REAL NOT NULL,
        rfid_uid TEXT,
        last_updated TEXT NOT NULL,
        coordinates_x REAL DEFAULT 50.0,
        coordinates_y REAL DEFAULT 50.0
    );
    """)

    # 3. Wards Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wards (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        current_urgency TEXT NOT NULL,  -- 'NORMAL', 'MODERATE', 'CRITICAL'
        bed_capacity INTEGER NOT NULL,
        occupied_beds INTEGER NOT NULL,
        pos_x REAL NOT NULL,
        pos_y REAL NOT NULL
    );
    """)

    # 4. Equipment Movements History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS equipment_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id TEXT NOT NULL,
        from_location TEXT NOT NULL,
        to_location TEXT NOT NULL,
        movement_time TEXT NOT NULL,
        duration_seconds INTEGER DEFAULT 60,
        rfid_scanned_by TEXT,
        status TEXT NOT NULL DEFAULT 'COMPLETED', -- 'COMPLETED', 'IN_TRANSIT'
        route_description TEXT,
        FOREIGN KEY (equipment_id) REFERENCES equipment(id)
    );
    """)

    # 5. Shortage Predictions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shortage_predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ward_id TEXT NOT NULL,
        ward_name TEXT NOT NULL,
        equipment_type TEXT NOT NULL,
        current_available INTEGER NOT NULL,
        current_demand INTEGER NOT NULL,
        predicted_demand_3h INTEGER NOT NULL,
        expected_shortage INTEGER NOT NULL,
        time_to_shortage_hours REAL NOT NULL,
        severity TEXT NOT NULL,        -- 'HIGH', 'MODERATE', 'POSSIBLE'
        explanation TEXT NOT NULL,
        ai_recommendation TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    # 6. Telemetry Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id TEXT NOT NULL,
        battery INTEGER NOT NULL,
        movement INTEGER NOT NULL,     -- 0 or 1
        temperature REAL NOT NULL,
        usage_time INTEGER NOT NULL,
        location TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (equipment_id) REFERENCES equipment(id)
    );
    """)

    # 7. RFID Scans Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rfid_scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uid TEXT NOT NULL,
        equipment_id TEXT NOT NULL,
        equipment_type TEXT NOT NULL,
        location TEXT NOT NULL,
        status TEXT NOT NULL,
        scanned_at TEXT NOT NULL
    );
    """)

    # 8. Maintenance Records
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS maintenance_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id TEXT NOT NULL,
        maintenance_type TEXT NOT NULL,
        findings TEXT NOT NULL,
        risk_score INTEGER NOT NULL,
        recommended_date TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (equipment_id) REFERENCES equipment(id)
    );
    """)

    # 9. Emergency Requests
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS equipment_requests (
        id TEXT PRIMARY KEY,
        ward_id TEXT NOT NULL,
        equipment_type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        patient_status TEXT NOT NULL,  -- 'Critical', 'Urgent', 'Stable'
        priority_score INTEGER NOT NULL, -- 0 - 100
        priority_level TEXT NOT NULL,   -- 'HIGH', 'MEDIUM', 'LOW'
        status TEXT NOT NULL,          -- 'PENDING', 'ALLOCATED', 'FULFILLED'
        reason TEXT,
        allocated_equipment TEXT,      -- JSON list of IDs
        requested_by TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # 10. Demand Forecast History & Cache
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS demand_forecasts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ward_id TEXT NOT NULL,
        equipment_type TEXT NOT NULL,
        current_count INTEGER NOT NULL,
        predicted_1h INTEGER NOT NULL,
        predicted_3h INTEGER NOT NULL,
        predicted_6h INTEGER NOT NULL,
        predicted_12h INTEGER NOT NULL,
        predicted_24h INTEGER NOT NULL,
        trend TEXT NOT NULL,
        confidence REAL NOT NULL,
        recommendation TEXT,
        generated_at TEXT NOT NULL
    );
    """)

    # 11. Vision Detections Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vision_detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zone TEXT NOT NULL,
        equipment_type TEXT NOT NULL,
        detected_count INTEGER NOT NULL,
        database_count INTEGER NOT NULL,
        mismatch INTEGER NOT NULL,
        confidence_avg REAL NOT NULL,
        timestamp TEXT NOT NULL
    );
    """)

    # 12. Storage Verification Sessions Table (Wheelchair 2-Minute Verification)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS storage_verification_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment_id TEXT NOT NULL,
        location TEXT NOT NULL,
        status TEXT NOT NULL,          -- 'COUNTDOWN_ACTIVE', 'VERIFIED', 'CANCELLED'
        countdown_seconds INTEGER NOT NULL,
        started_at TEXT NOT NULL,
        target_verification_at TEXT NOT NULL,
        completed_at TEXT,
        cancellation_reason TEXT
    );
    """)

    # 13. Synthetic Radiology Operations Table (27 Analytical Fields)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS synthetic_radiology_flow (
        patient_id TEXT PRIMARY KEY,
        department TEXT NOT NULL,
        modality TEXT NOT NULL,
        priority TEXT NOT NULL,
        request_time TEXT NOT NULL,
        registration_time TEXT NOT NULL,
        equipment_id TEXT NOT NULL,
        equipment_status TEXT NOT NULL,
        queue_position INTEGER NOT NULL,
        waiting_for_scan_minutes INTEGER NOT NULL,
        scan_duration_minutes INTEGER NOT NULL,
        scan_start_time TEXT,
        scan_end_time TEXT,
        waiting_for_report_minutes INTEGER NOT NULL,
        report_start_time TEXT,
        report_ready_time TEXT,
        total_turnaround_minutes INTEGER NOT NULL,
        radiologist_status TEXT NOT NULL,
        report_status TEXT NOT NULL,
        equipment_location TEXT NOT NULL,
        doctor_id TEXT,
        ward TEXT,
        emergency_flag INTEGER DEFAULT 0,
        time_of_day TEXT,
        day_of_week TEXT,
        equipment_utilization REAL DEFAULT 75.0,
        delay_reason TEXT,
        last_updated TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
