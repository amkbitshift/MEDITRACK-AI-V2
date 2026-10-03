"""
MediTrack AI - Computer Vision & Automated Inventory Counting
Simulates & integrates YOLO object detection for medical equipment tracking,
bounding box coordinates generation, and real-time inventory reconciliation.
"""

import sys
import random
from datetime import datetime
from pathlib import Path

# Add backend directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from database.db import get_connection

YOLO_CLASSES = [
    "wheelchair",
    "stretcher",
    "walker",
    "hospital_bed",
    "oxygen_cylinder",
    "medical_cart"
]

class VisionAIEngine:
    def __init__(self):
        self.camera_status = "ONLINE"
        self.camera_resolution = "1920x1080 @ 30fps"
        self.active_zone = "Zone A - Central Triage & Staging"

    def get_live_detections(self, zone: str = "Zone A - Central Triage & Staging"):
        """
        Generates simulated high-fidelity bounding box detections aligned with the hackathon scenario:
        Wheelchairs: 12 (DB expects 15 -> Mismatch -3)
        Stretchers: 5 (DB expects 5 -> Mismatch 0)
        Walkers: 8 (DB expects 8 -> Mismatch 0)
        """
        # Bounding box coordinates (percentages of frame: x, y, width, height)
        detections = []

        # 12 Wheelchairs (several grouped across triage hallway)
        wheelchair_coords = [
            (12, 35, 14, 28, 0.96, "WC-007"),
            (28, 42, 13, 27, 0.94, "WC-012"),
            (44, 38, 15, 29, 0.91, "WC-018"),
            (62, 45, 12, 26, 0.93, "WC-003"),
            (76, 40, 14, 28, 0.95, "WC-005"),
            (18, 65, 15, 30, 0.89, "WC-008"),
            (36, 68, 14, 29, 0.92, "WC-010"),
            (55, 62, 13, 27, 0.94, "WC-011"),
            (72, 66, 16, 31, 0.90, "WC-013"),
            (85, 52, 12, 25, 0.88, "WC-016"),
            (8, 72, 13, 27, 0.91, "WC-019"),
            (50, 78, 14, 29, 0.93, "WC-020")
        ]
        for x, y, w, h, conf, tag in wheelchair_coords:
            detections.append({
                "id": f"det-wc-{tag}",
                "class": "wheelchair",
                "label": f"Wheelchair ({tag})",
                "confidence": conf,
                "box": {"x": x, "y": y, "width": w, "height": h},
                "equipment_id": tag,
                "status": "VERIFIED_PRESENT"
            })

        # 5 Stretchers
        stretcher_coords = [
            (10, 15, 22, 18, 0.95, "ST-001"),
            (35, 18, 20, 17, 0.92, "ST-003"),
            (58, 16, 21, 18, 0.94, "ST-005"),
            (80, 20, 18, 16, 0.89, "ST-007"),
            (30, 85, 24, 19, 0.91, "ST-008")
        ]
        for x, y, w, h, conf, tag in stretcher_coords:
            detections.append({
                "id": f"det-st-{tag}",
                "class": "stretcher",
                "label": f"Stretcher ({tag})",
                "confidence": conf,
                "box": {"x": x, "y": y, "width": w, "height": h},
                "equipment_id": tag,
                "status": "VERIFIED_PRESENT"
            })

        # 8 Walkers
        walker_coords = [
            (2, 45, 8, 18, 0.88, "WK-001"),
            (2, 58, 8, 18, 0.92, "WK-002"),
            (24, 25, 9, 19, 0.90, "WK-003"),
            (68, 28, 8, 18, 0.87, "WK-004"),
            (90, 30, 8, 18, 0.94, "WK-005"),
            (90, 75, 8, 18, 0.89, "WK-006"),
            (15, 88, 9, 19, 0.93, "WK-007"),
            (70, 88, 8, 18, 0.91, "WK-008")
        ]
        for x, y, w, h, conf, tag in walker_coords:
            detections.append({
                "id": f"det-wk-{tag}",
                "class": "walker",
                "label": f"Walker ({tag})",
                "confidence": conf,
                "box": {"x": x, "y": y, "width": w, "height": h},
                "equipment_id": tag,
                "status": "VERIFIED_PRESENT"
            })

        return detections

    def compare_inventory_with_database(self, zone: str = "Zone A - Central Triage & Staging"):
        """
        Compares YOLO optical detections against SQLite DB expected inventory for this zone.
        Highlights discrepancies with mismatch counters and investigative flags.
        """
        detections = self.get_live_detections(zone)
        detected_counts = {}
        for d in detections:
            c = d["class"]
            detected_counts[c] = detected_counts.get(c, 0) + 1

        # Database inventory benchmark for the active zone
        # Wheelchairs: 15 expected, 12 detected -> Mismatch: -3
        # Stretchers: 5 expected, 5 detected -> Mismatch: 0
        # Walkers: 8 expected, 8 detected -> Mismatch: 0
        # Beds: 20 expected, 19 detected -> Mismatch: -1
        benchmarks = {
            "wheelchair": {"name": "Wheelchairs", "database": 15, "detected": detected_counts.get("wheelchair", 12)},
            "stretcher": {"name": "Stretchers", "database": 5, "detected": detected_counts.get("stretcher", 5)},
            "walker": {"name": "Walkers", "database": 8, "detected": detected_counts.get("walker", 8)},
            "hospital_bed": {"name": "Hospital Beds", "database": 20, "detected": 19}
        }

        mismatches = []
        for eq_key, data in benchmarks.items():
            diff = data["detected"] - data["database"]
            status = "MATCH" if diff == 0 else "MISMATCH"
            severity = "CRITICAL" if abs(diff) >= 3 else ("WARNING" if abs(diff) > 0 else "OK")
            mismatches.append({
                "class": eq_key,
                "display_name": data["name"],
                "database_count": data["database"],
                "detected_count": data["detected"],
                "difference": diff,
                "status": status,
                "severity": severity,
                "alert_message": f"Expected {data['database']} units, optical AI detected {data['detected']} (Missing: {abs(diff)})" if diff < 0 else "Counts verified."
            })

        # Missing equipment items that need investigation
        missing_investigation = [
            {"id": "WC-009", "name": "Wheelchair WC-009", "last_seen_zone": "Zone A Doorway", "status": "IN_TRANSIT", "reason": "Moved to Emergency Ward without RFID checkout confirmation"},
            {"id": "WC-014", "name": "Wheelchair WC-014", "last_seen_zone": "Corridor 3", "status": "IN_MAINTENANCE", "reason": "Routed to Annex Storage for bearing servicing"},
            {"id": "WC-015", "name": "Wheelchair WC-015", "last_seen_zone": "Storage A", "status": "UNLOCATED", "reason": "Last RFID ping 38 minutes ago near Radiology entrance"}
        ]

        return {
            "zone": zone,
            "camera_status": self.camera_status,
            "fps": 30,
            "total_detected_items": len(detections),
            "detections": detections,
            "reconciliation": mismatches,
            "has_mismatch": any(m["status"] == "MISMATCH" for m in mismatches),
            "critical_mismatch_item": next((m for m in mismatches if m["class"] == "wheelchair"), None),
            "investigation_records": missing_investigation
        }

vision_engine = VisionAIEngine()

if __name__ == "__main__":
    rep = vision_engine.compare_inventory_with_database()
    print(f"Vision AI Report for {rep['zone']}: Total detected {rep['total_detected_items']}")
    for r in rep["reconciliation"]:
        print(f" - {r['display_name']}: DB={r['database_count']}, AI={r['detected_count']}, Diff={r['difference']} [{r['severity']}]")
