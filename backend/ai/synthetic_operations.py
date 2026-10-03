"""
MEDiTrack AI — Synthetic Hospital Operations & Radiology Simulation Engine
Phase 3 Enterprise Architecture

Simulates realistic, multi-department patient flow across Radiology, Emergency, ICU,
General Ward, OT, and Outpatient Departments.
Primary clinical focus: RADIOLOGY & IMAGING (X-Ray, CT Scan, MRI, Ultrasound, Mammography, Fluoroscopy, Interventional).

Features:
1. Strict separate tracking of:
   - waiting_for_scan_minutes
   - scan_duration_minutes
   - waiting_for_report_minutes
   - total_turnaround_minutes = scan_wait + scan_duration + report_wait
2. Realistic variation by modality, clinical priority (Emergency vs Urgent vs Routine),
   time-of-day diurnal curve, equipment status, and reporting backlog.
3. Equipment-to-Radiology correlation: Wheelchair/Stretcher availability directly affects
   in-patient transport times and overall turnaround.
4. AI Bottleneck Detection: distinguishes Scan Capacity bottlenecks vs Reporting Capacity bottlenecks.
5. Autonomous Simulation Engine with reproducible random seed and ON/OFF toggle.
"""

import math
import random
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

MODALITIES = [
    "X-RAY",
    "CT SCAN",
    "MRI",
    "ULTRASOUND",
    "MAMMOGRAPHY",
    "FLUOROSCOPY",
    "INTERVENTIONAL RADIOLOGY"
]

DEPARTMENTS = [
    "Radiology",
    "Emergency",
    "ICU",
    "General Ward",
    "Operation Theatre",
    "Outpatient Department"
]

MODALITY_EQUIPMENT_MAP = {
    "X-RAY": ["XR-01 (Siemens Multix)", "XR-02 (Mobile Unit A)"],
    "CT SCAN": ["CT-01 (GE Revolution 256)", "CT-02 (Siemens Somatom)"],
    "MRI": ["MRI-01 (Philips Ingenia 3.0T)", "MRI-02 (Siemens Magnetom 1.5T)"],
    "ULTRASOUND": ["US-01 (GE Logiq E10)", "US-02 (Mindray Resona 7)", "US-03 (Bedside FastScan)"],
    "MAMMOGRAPHY": ["MAM-01 (Hologic Selenia 3D)"],
    "FLUOROSCOPY": ["FL-01 (Siemens Luminos dRF)"],
    "INTERVENTIONAL RADIOLOGY": ["IR-01 (Artis Q Angio Suite)"]
}

MODALITY_LOCATIONS = {
    "X-RAY": "Radiology Suites - Room 102",
    "CT SCAN": "Radiology Suites - Room 108",
    "MRI": "Radiology High-Field Magnet Suite - Room 112",
    "ULTRASOUND": "Radiology Ultrasound Wing - Room 104",
    "MAMMOGRAPHY": "Women's Diagnostic Center - Room 116",
    "FLUOROSCOPY": "Fluoroscopy Suite - Room 110",
    "INTERVENTIONAL RADIOLOGY": "Hybrid Angio Suite - Room 120"
}

BASE_DURATIONS = {
    # (scan_wait_base, scan_duration_base, report_wait_base)
    "X-RAY": (12, 8, 28),
    "CT SCAN": (26, 14, 52),
    "MRI": (45, 38, 115),
    "ULTRASOUND": (18, 18, 35),
    "MAMMOGRAPHY": (22, 16, 48),
    "FLUOROSCOPY": (28, 22, 60),
    "INTERVENTIONAL RADIOLOGY": (35, 55, 90)
}

class HospitalSimulationEngine:
    """
    Dynamic operational simulation engine for radiology patient journeys,
    queue wait-times, scan executions, and diagnostic reporting workloads.
    """

    def __init__(self, initial_seed: int = 42):
        self.seed = initial_seed
        self.rng = random.Random(self.seed)
        self.is_running = True
        self.simulation_tick = 0
        self.time_offset_minutes = 0
        self.patients: List[Dict[str, Any]] = []
        self._background_task: Optional[asyncio.Task] = None
        self._websocket_broadcaster: Optional[Any] = None

        # Live operational transport status (tied to Wheelchair Storage)
        self.transport_wheelchairs_available = 1  # Will be dynamically updated from DB
        self.transport_shortage_active = False

        self._generate_initial_dataset()

    def set_websocket_broadcaster(self, broadcaster):
        self._websocket_broadcaster = broadcaster

    def get_time_of_day_profile(self) -> Dict[str, Any]:
        """Calculates realistic diurnal demand curve."""
        current_hour = (datetime.now().hour + (self.time_offset_minutes // 60)) % 24
        
        if 8 <= current_hour < 11:
            name = "Morning Inflow"
            multiplier = 1.05
            load = "MODERATE"
        elif 11 <= current_hour < 14:
            name = "Late Morning Peak"
            multiplier = 1.38
            load = "HIGH"
        elif 14 <= current_hour < 18:
            name = "Afternoon Clinical Surge"
            multiplier = 1.55
            load = "PEAK"
        elif 18 <= current_hour < 22:
            name = "Evening Taper"
            multiplier = 0.95
            load = "MODERATE"
        else:
            name = "Night Shift (Trauma / Emergency Priority)"
            multiplier = 0.55
            load = "LOW (EMERGENCY ONLY)"

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        today = days[datetime.now().weekday()]

        return {
            "hour": current_hour,
            "period_name": name,
            "label": name,
            "time_label": name,
            "workload_multiplier": multiplier,
            "multiplier": multiplier,
            "traffic_multiplier": multiplier,
            "load_level": load,
            "badge": load,
            "status_badge": load,
            "day_of_week": today
        }

    def _generate_initial_dataset(self, count: int = 36):
        """Generates realistic synthetic patient cohort across radiology modalities."""
        self.patients.clear()
        base_time = datetime.now() - timedelta(hours=3, minutes=15)
        tod = self.get_time_of_day_profile()

        priorities = ["EMERGENCY", "URGENT", "ROUTINE"]
        priority_weights = [0.20, 0.35, 0.45]

        for i in range(1, count + 1):
            p_id = f"P-{1000 + i}"
            modality = self.rng.choice(MODALITIES)
            dept = self.rng.choice(DEPARTMENTS) if modality != "INTERVENTIONAL RADIOLOGY" else self.rng.choice(["Emergency", "ICU", "Operation Theatre"])
            priority = self.rng.choices(priorities, weights=priority_weights)[0]
            is_emergency = (priority == "EMERGENCY")

            # Offset registration time
            reg_offset = self.rng.randint(10, 180)
            reg_time = base_time + timedelta(minutes=reg_offset)
            req_time = reg_time - timedelta(minutes=self.rng.randint(5, 20))

            base_scan_wait, base_scan_dur, base_rep_wait = BASE_DURATIONS[modality]

            # Adjust by priority
            if priority == "EMERGENCY":
                scan_wait = max(4, int(base_scan_wait * 0.35 * self.rng.uniform(0.7, 1.1)))
                rep_wait = max(12, int(base_rep_wait * 0.28 * self.rng.uniform(0.8, 1.2)))
            elif priority == "URGENT":
                scan_wait = max(12, int(base_scan_wait * 0.75 * tod["workload_multiplier"] * self.rng.uniform(0.85, 1.25)))
                rep_wait = max(25, int(base_rep_wait * 0.65 * tod["workload_multiplier"] * self.rng.uniform(0.9, 1.3)))
            else: # ROUTINE
                scan_wait = max(18, int(base_scan_wait * tod["workload_multiplier"] * self.rng.uniform(0.9, 1.45)))
                rep_wait = max(35, int(base_rep_wait * tod["workload_multiplier"] * self.rng.uniform(0.95, 1.6)))

            # Transport equipment delay impact (Part 8)
            delay_reason = None
            if self.transport_wheelchairs_available == 0 and dept in ("General Ward", "Emergency", "Outpatient Department"):
                extra_transport_delay = self.rng.randint(14, 26)
                scan_wait += extra_transport_delay
                delay_reason = f"Wheelchair transport delay (+{extra_transport_delay}m): Storage bay empty"

            scan_dur = max(6, int(base_scan_dur * self.rng.uniform(0.85, 1.2)))
            total_turnaround = scan_wait + scan_dur + rep_wait

            # Calculated timestamps
            scan_start = reg_time + timedelta(minutes=scan_wait)
            scan_end = scan_start + timedelta(minutes=scan_dur)
            rep_start = scan_end + timedelta(minutes=self.rng.randint(2, 8))
            rep_ready = scan_end + timedelta(minutes=rep_wait)

            # Determine progression status relative to simulated clock
            elapsed_since_reg = (datetime.now() - reg_time).total_seconds() / 60.0

            if elapsed_since_reg < scan_wait:
                status = "WAITING_FOR_SCAN"
                rad_status = "PENDING_SCAN"
            elif elapsed_since_reg < (scan_wait + scan_dur):
                status = "SCAN_IN_PROGRESS"
                rad_status = "PATIENT_ON_GANTRY"
            elif elapsed_since_reg < (scan_wait + scan_dur + rep_wait):
                status = "REPORT_PENDING"
                rad_status = "READING"
            else:
                status = "REPORT_READY"
                rad_status = "VERIFIED"

            eq_list = MODALITY_EQUIPMENT_MAP.get(modality, ["RAD-GENERIC-01"])
            assigned_eq = self.rng.choice(eq_list)
            eq_status = "IN_USE" if status == "SCAN_IN_PROGRESS" else "AVAILABLE"

            doctor_id = f"DR-RAD-0{self.rng.randint(1, 6)}"
            ward_str = f"ward-{dept.lower().replace(' ', '-')}"

            self.patients.append({
                "patient_id": p_id,
                "department": dept,
                "modality": modality,
                "priority": priority,
                "request_time": req_time.strftime("%H:%M"),
                "registration_time": reg_time.strftime("%H:%M"),
                "equipment_id": assigned_eq,
                "equipment_status": eq_status,
                "queue_position": i,
                "waiting_for_scan_minutes": scan_wait,
                "scan_duration_minutes": scan_dur,
                "scan_start_time": scan_start.strftime("%H:%M"),
                "scan_end_time": scan_end.strftime("%H:%M"),
                "waiting_for_report_minutes": rep_wait,
                "report_start_time": rep_start.strftime("%H:%M"),
                "report_ready_time": rep_ready.strftime("%H:%M"),
                "total_turnaround_minutes": total_turnaround,
                "radiologist_status": rad_status,
                "report_status": status,
                "equipment_location": MODALITY_LOCATIONS.get(modality, "Radiology Central Suite"),
                "doctor_id": doctor_id,
                "ward": ward_str,
                "emergency_flag": is_emergency,
                "time_of_day": tod["period_name"],
                "day_of_week": tod["day_of_week"],
                "equipment_utilization": round(self.rng.uniform(68.0, 94.0), 1),
                "delay_reason": delay_reason
            })

    def update_transport_equipment_count(self, available_wheelchairs: int):
        """
        Called when wheelchair storage state changes.
        Directly affects radiology waiting delay (Part 8).
        """
        old_count = self.transport_wheelchairs_available
        self.transport_wheelchairs_available = available_wheelchairs
        self.transport_shortage_active = (available_wheelchairs <= 0)

        # If wheelchairs just became available, reduce scan waiting times for patients delayed by transport!
        if old_count == 0 and available_wheelchairs > 0:
            for p in self.patients:
                if p["report_status"] == "WAITING_FOR_SCAN" and p.get("delay_reason") and "Wheelchair" in p["delay_reason"]:
                    reduction = self.rng.randint(10, 18)
                    p["waiting_for_scan_minutes"] = max(5, p["waiting_for_scan_minutes"] - reduction)
                    p["total_turnaround_minutes"] = max(15, p["total_turnaround_minutes"] - reduction)
                    p["delay_reason"] = "Wheelchair returned to Storage (Transport delay resolved)"

    def advance_simulation_step(self, force: bool = False):
        """
        Advances the simulated hospital operational clock by 5-10 minutes.
        Patients transition stages: WAITING -> SCANNING -> REPORTING -> READY.
        New patients arrive.
        """
        if not self.is_running and not force:
            return

        self.simulation_tick += 1
        self.time_offset_minutes += self.rng.randint(4, 8)
        tod = self.get_time_of_day_profile()

        # 1. Advance existing patients through lifecycle
        for p in self.patients:
            if p["report_status"] == "WAITING_FOR_SCAN":
                # Probability of entering gantry
                if self.rng.random() < 0.35:
                    p["report_status"] = "SCAN_IN_PROGRESS"
                    p["radiologist_status"] = "PATIENT_ON_GANTRY"
                    p["equipment_status"] = "IN_USE"
            elif p["report_status"] == "SCAN_IN_PROGRESS":
                if self.rng.random() < 0.45:
                    p["report_status"] = "REPORT_PENDING"
                    p["radiologist_status"] = "READING"
                    p["equipment_status"] = "AVAILABLE"
            elif p["report_status"] == "REPORT_PENDING":
                # Probability of radiologist signing off
                rate = 0.50 if p["priority"] == "EMERGENCY" else 0.30
                if self.rng.random() < rate:
                    p["report_status"] = "REPORT_READY"
                    p["radiologist_status"] = "VERIFIED"

        # 2. Randomly ingest 1-2 new patients matching time-of-day profile
        if self.rng.random() < (0.65 * tod["workload_multiplier"]):
            new_id = f"P-{1000 + len(self.patients) + 1}"
            modality = self.rng.choice(MODALITIES)
            priority = self.rng.choices(["EMERGENCY", "URGENT", "ROUTINE"], weights=[0.25, 0.40, 0.35])[0]
            dept = self.rng.choice(DEPARTMENTS)

            base_scan_wait, base_scan_dur, base_rep_wait = BASE_DURATIONS[modality]
            scan_wait = int(base_scan_wait * tod["workload_multiplier"] * self.rng.uniform(0.85, 1.35))
            if priority == "EMERGENCY":
                scan_wait = max(4, int(scan_wait * 0.35))

            delay_reason = None
            if self.transport_wheelchairs_available == 0:
                scan_wait += 18
                delay_reason = "Wheelchair transport delay (+18m): Storage bay empty"

            scan_dur = int(base_scan_dur * self.rng.uniform(0.9, 1.2))
            rep_wait = int(base_rep_wait * tod["workload_multiplier"] * self.rng.uniform(0.85, 1.4))
            now_dt = datetime.now()

            self.patients.append({
                "patient_id": new_id,
                "department": dept,
                "modality": modality,
                "priority": priority,
                "request_time": (now_dt - timedelta(minutes=5)).strftime("%H:%M"),
                "registration_time": now_dt.strftime("%H:%M"),
                "equipment_id": self.rng.choice(MODALITY_EQUIPMENT_MAP.get(modality, ["RAD-01"])),
                "equipment_status": "AVAILABLE",
                "queue_position": len([x for x in self.patients if x["report_status"] == "WAITING_FOR_SCAN"]) + 1,
                "waiting_for_scan_minutes": scan_wait,
                "scan_duration_minutes": scan_dur,
                "scan_start_time": (now_dt + timedelta(minutes=scan_wait)).strftime("%H:%M"),
                "scan_end_time": (now_dt + timedelta(minutes=scan_wait + scan_dur)).strftime("%H:%M"),
                "waiting_for_report_minutes": rep_wait,
                "report_start_time": (now_dt + timedelta(minutes=scan_wait + scan_dur + 5)).strftime("%H:%M"),
                "report_ready_time": (now_dt + timedelta(minutes=scan_wait + scan_dur + rep_wait)).strftime("%H:%M"),
                "total_turnaround_minutes": scan_wait + scan_dur + rep_wait,
                "radiologist_status": "PENDING_SCAN",
                "report_status": "WAITING_FOR_SCAN",
                "equipment_location": MODALITY_LOCATIONS.get(modality, "Radiology Central Suite"),
                "doctor_id": f"DR-RAD-0{self.rng.randint(1, 6)}",
                "ward": f"ward-{dept.lower().replace(' ', '-')}",
                "emergency_flag": priority == "EMERGENCY",
                "time_of_day": tod["period_name"],
                "day_of_week": tod["day_of_week"],
                "equipment_utilization": round(self.rng.uniform(70.0, 95.0), 1),
                "delay_reason": delay_reason
            })

        # Keep patient pool bounded for performance (last 50 patients)
        if len(self.patients) > 50:
            self.patients = self.patients[-50:]

    def get_modality_operations_summary(self) -> List[Dict[str, Any]]:
        """
        Builds the detailed modality operational cards (Part 4):
        X-Ray, CT Scan, MRI, Ultrasound, Mammography, Fluoroscopy.
        """
        results = []
        for mod in ["X-RAY", "CT SCAN", "MRI", "ULTRASOUND", "MAMMOGRAPHY", "FLUOROSCOPY"]:
            subset = [p for p in self.patients if p["modality"] == mod]
            waiting_for_scan = [p for p in subset if p["report_status"] == "WAITING_FOR_SCAN"]
            scan_in_progress = [p for p in subset if p["report_status"] == "SCAN_IN_PROGRESS"]
            reports_pending = [p for p in subset if p["report_status"] == "REPORT_PENDING"]
            reports_ready = [p for p in subset if p["report_status"] == "REPORT_READY"]

            avg_scan_wait = int(sum(p["waiting_for_scan_minutes"] for p in subset) / max(1, len(subset)))
            avg_scan_dur = int(sum(p["scan_duration_minutes"] for p in subset) / max(1, len(subset)))
            avg_report_wait = int(sum(p["waiting_for_report_minutes"] for p in subset) / max(1, len(subset)))
            avg_total_turnaround = avg_scan_wait + avg_scan_dur + avg_report_wait

            # Format report wait hours / mins
            hrs = avg_report_wait // 60
            mins = avg_report_wait % 60
            rep_wait_str = f"{hrs}h {mins}m" if hrs > 0 else f"{mins} min"

            # Determine operational health status
            if len(reports_pending) >= 6 or (mod == "MRI" and avg_report_wait > 120):
                status = "BOTTLENECK"
                status_color = "rose"
            elif len(waiting_for_scan) >= 5 or avg_scan_wait > 35:
                status = "ATTENTION"
                status_color = "amber"
            else:
                status = "OPTIMAL"
                status_color = "emerald"

            eq_list = MODALITY_EQUIPMENT_MAP.get(mod, [])
            primary_eq = eq_list[0].split(" ")[0] if eq_list else "RAD-01"

            results.append({
                "modality": mod,
                "patients_waiting": len(waiting_for_scan),
                "waiting_patients": len(waiting_for_scan),
                "scan_wait_minutes": avg_scan_wait,
                "scan_in_progress_count": len(scan_in_progress),
                "active_scans": len(scan_in_progress),
                "reports_pending_count": len(reports_pending),
                "report_wait_formatted": rep_wait_str,
                "report_wait_minutes": avg_report_wait,
                "scan_duration_minutes": avg_scan_dur,
                "total_turnaround_minutes": avg_total_turnaround,
                "equipment_id": primary_eq,
                "equipment_available_count": len(eq_list),
                "operational_status": status,
                "status": status,
                "status_color": status_color,
                "utilization_pct": round(min(98.0, 50.0 + (len(scan_in_progress) * 22.0) + (len(waiting_for_scan) * 3.5)), 1)
            })
        return results

    def get_ai_bottleneck_insights(self) -> List[Dict[str, Any]]:
        """
        AI Bottleneck Detection Engine (Part 6 & Part 8):
        Analyzes scan capacity vs reporting backlog vs transport shortages.
        """
        insights = []
        tod = self.get_time_of_day_profile()
        summary = self.get_modality_operations_summary()

        # 1. Transport Equipment Shortage Insight (Part 8 Connection)
        if self.transport_wheelchairs_available == 0:
            insights.append({
                "id": "insight-transport-shortage",
                "category": "TRANSPORT_BOTTLENECK",
                "severity": "CRITICAL",
                "modality": "Hospital Fleet (Wheelchairs)",
                "title": "Wheelchair Transport Shortage Impairing Radiology Intake",
                "description": "Zero wheelchairs are currently available at Radiology Wheelchair Storage. Patient transfers from Emergency and General Wards are delayed by +18 minutes.",
                "insight": "Zero wheelchairs are currently available at Radiology Wheelchair Storage. Patient transfers from Emergency and General Wards are delayed by +18 minutes.",
                "recommendation": "Return Wheelchair WC-007 to Radiology Wheelchair Storage. Automated 2-minute verification will restore transport flow.",
                "recommended_action": "Return Wheelchair WC-007 to Radiology Wheelchair Storage. Automated 2-minute verification will restore transport flow.",
                "impact_turnaround_reduction_minutes": 18
            })
        else:
            insights.append({
                "id": "insight-transport-optimal",
                "category": "TRANSPORT_EQUIPMENT",
                "severity": "OPTIMAL",
                "modality": "Hospital Fleet (Wheelchairs)",
                "title": f"Wheelchair Storage Staged ({self.transport_wheelchairs_available} Available)",
                "description": "Wheelchairs verified at Radiology Storage Bay. Ward-to-imaging transport queues operating at baseline velocity.",
                "insight": "Wheelchairs verified at Radiology Storage Bay. Ward-to-imaging transport queues operating at baseline velocity.",
                "recommendation": "Maintain return compliance for WC-007 at designated storage bay.",
                "recommended_action": "Maintain return compliance for WC-007 at designated storage bay.",
                "impact_turnaround_reduction_minutes": 0
            })

        # 2. MRI & CT Scan Capacity vs Reporting Workload Bottlenecks
        mri_card = next((c for c in summary if c["modality"] == "MRI"), None)
        ct_card = next((c for c in summary if c["modality"] == "CT SCAN"), None)

        if ct_card and ct_card["reports_pending_count"] > ct_card["patients_waiting"]:
            insights.append({
                "id": "insight-ct-reporting-lag",
                "category": "REPORTING_BOTTLENECK",
                "severity": "HIGH",
                "modality": "CT SCAN",
                "title": "CT Scan Capacity Sufficient; Reporting Workload is Primary Bottleneck",
                "description": f"CT scanner gantry turnover is optimal ({ct_card['scan_duration_minutes']}m), but {ct_card['reports_pending_count']} diagnostic reports are awaiting radiologist verification.",
                "insight": f"CT scanner gantry turnover is optimal ({ct_card['scan_duration_minutes']}m), but {ct_card['reports_pending_count']} diagnostic reports are awaiting radiologist verification.",
                "recommendation": "Route 3 pending CT chest/abdomen scans to secondary teleradiology reading queue.",
                "recommended_action": "Route 3 pending CT chest/abdomen scans to secondary teleradiology reading queue.",
                "impact_turnaround_reduction_minutes": 25
            })

        if mri_card and mri_card["patients_waiting"] > 4:
            insights.append({
                "id": "insight-mri-peak-demand",
                "category": "SCAN_CAPACITY_BOTTLENECK",
                "severity": "MODERATE",
                "modality": "MRI",
                "title": f"MRI High Demand Detected during {tod['period_name']}",
                "description": f"MRI magnet utilization reached {mri_card['utilization_pct']}%. Average scan waiting time is {mri_card['scan_wait_minutes']} minutes.",
                "insight": f"MRI magnet utilization reached {mri_card['utilization_pct']}%. Average scan waiting time is {mri_card['scan_wait_minutes']} minutes.",
                "recommendation": "Activate MRI-02 (Siemens Magnetom 1.5T) for non-contrast musculoskeletal cases to clear queue.",
                "recommended_action": "Activate MRI-02 (Siemens Magnetom 1.5T) for non-contrast musculoskeletal cases to clear queue.",
                "impact_turnaround_reduction_minutes": 32
            })

        # 3. Emergency Prioritization Assurance
        emergency_count = len([p for p in self.patients if p["priority"] == "EMERGENCY" and p["report_status"] != "REPORT_READY"])
        if emergency_count > 0:
            insights.append({
                "id": "insight-emergency-priority",
                "category": "CLINICAL_PRIORITY",
                "severity": "INFO",
                "modality": "Emergency Radiology",
                "title": f"Emergency Priority Queue Active ({emergency_count} Critical Cases)",
                "description": "Emergency cases automatically bypass routine imaging lines, keeping critical turnaround within target windows.",
                "insight": "Emergency cases automatically bypass routine imaging lines, keeping critical turnaround within target windows.",
                "recommendation": "Continuous adherence to emergency triage protocol.",
                "recommended_action": "Continuous adherence to emergency triage protocol.",
                "impact_turnaround_reduction_minutes": 0
            })

        return insights

    def get_patient_journey(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Returns step-by-step visual timeline for specified patient (Part 5)."""
        target = next((p for p in self.patients if p["patient_id"] == patient_id), None)
        if not target:
            target = self.patients[0] if self.patients else None
        if not target:
            return None

        # Build chronological milestones
        milestones = [
            {
                "stage": "REGISTRATION",
                "label": "Patient Registration & Imaging Request",
                "time": target["registration_time"],
                "status": "COMPLETED",
                "detail": f"Ordered by {target['doctor_id']} from {target['department']}. Clinical Priority: {target['priority']}."
            },
            {
                "stage": "WAITING_FOR_SCAN",
                "label": "Waiting for Scan",
                "time": target["registration_time"],
                "duration_minutes": target["waiting_for_scan_minutes"],
                "status": "COMPLETED" if target["report_status"] != "WAITING_FOR_SCAN" else "ACTIVE",
                "detail": f"Queue position #{target['queue_position']}. Waiting duration: {target['waiting_for_scan_minutes']} min. {target.get('delay_reason') or 'No logistical delay.'}"
            },
            {
                "stage": "SCAN_IN_PROGRESS",
                "label": "Imaging Scan in Progress",
                "time": target["scan_start_time"],
                "duration_minutes": target["scan_duration_minutes"],
                "status": "COMPLETED" if target["report_status"] in ("REPORT_PENDING", "REPORT_READY") else ("ACTIVE" if target["report_status"] == "SCAN_IN_PROGRESS" else "PENDING"),
                "detail": f"Assigned to {target['equipment_id']} at {target['equipment_location']}. Duration: {target['scan_duration_minutes']} min."
            },
            {
                "stage": "WAITING_FOR_REPORT",
                "label": "Radiology Interpretation & Verification",
                "time": target["scan_end_time"],
                "duration_minutes": target["waiting_for_report_minutes"],
                "status": "COMPLETED" if target["report_status"] == "REPORT_READY" else ("ACTIVE" if target["report_status"] == "REPORT_PENDING" else "PENDING"),
                "detail": f"Status: {target['radiologist_status']}. Estimated report generation: {target['waiting_for_report_minutes']} min."
            },
            {
                "stage": "REPORT_READY",
                "label": "Diagnostic Report Verified & Published",
                "time": target["report_ready_time"],
                "status": "COMPLETED" if target["report_status"] == "REPORT_READY" else "PENDING",
                "detail": f"Total turnaround: {target['total_turnaround_minutes']} min ({round(target['total_turnaround_minutes']/60.0, 1)} hrs)."
            }
        ]

        return {
            "patient": target,
            "milestones": milestones,
            "total_turnaround_minutes": target["total_turnaround_minutes"],
            "total_turnaround_formatted": f"{target['total_turnaround_minutes'] // 60}h {target['total_turnaround_minutes'] % 60}m"
        }

    def get_dashboard_payload(self) -> Dict[str, Any]:
        """Complete payload for Dynamic Radiology Dashboard (Part 4-9)."""
        tod = self.get_time_of_day_profile()
        modality_cards = self.get_modality_operations_summary()
        insights = self.get_ai_bottleneck_insights()

        # Overall hospital metrics
        total_waiting_scan = sum(m["patients_waiting"] for m in modality_cards)
        total_in_progress = sum(m["scan_in_progress_count"] for m in modality_cards)
        total_reports_pending = sum(m["reports_pending_count"] for m in modality_cards)
        avg_overall_turnaround = int(sum(m["total_turnaround_minutes"] for m in modality_cards) / max(1, len(modality_cards)))

        # Default patient journey (e.g. highest priority or first patient)
        journey_target = next((p for p in self.patients if p["priority"] == "EMERGENCY"), self.patients[0] if self.patients else None)
        journey_data = self.get_patient_journey(journey_target["patient_id"]) if journey_target else None

        modality_dict = {m["modality"]: m for m in modality_cards}
        is_ready = self.transport_wheelchairs_available > 0
        status_msg = (
            "Radiology Wheelchair Storage Bay has WC-007 verified available. Inpatient pre-gantry transit nominal."
            if is_ready else
            "Radiology Wheelchair Storage Bay has NO available wheelchairs. Adding +18 min pre-scan transit delay."
        )

        transport_obj = {
            "wheelchairs_available_in_radiology": self.transport_wheelchairs_available,
            "transport_shortage_active": self.transport_shortage_active,
            "storage_has_available_wheelchair": is_ready,
            "delay_minutes": 0 if is_ready else 18,
            "status_message": status_msg,
            "status_label": "OPTIMAL" if is_ready else "SHORTAGE_DELAY (+18m)"
        }

        diurnal_obj = {
            **tod,
            "time_label": tod.get("time_label") or tod.get("period_name") or tod.get("label", "Late Morning Peak"),
            "traffic_multiplier": tod.get("traffic_multiplier") or tod.get("workload_multiplier") or tod.get("multiplier", 1.0),
            "status_badge": tod.get("status_badge") or tod.get("load_level") or tod.get("badge", "MODERATE")
        }

        kpi_obj = {
            "total_patients_waiting_scan": total_waiting_scan,
            "total_scans_in_progress": total_in_progress,
            "total_reports_pending": total_reports_pending,
            "waiting_for_scan_count": total_waiting_scan,
            "in_progress_count": total_in_progress,
            "reports_pending_count": total_reports_pending,
            "average_turnaround_minutes": avg_overall_turnaround,
            "average_turnaround_formatted": f"{avg_overall_turnaround // 60}h {avg_overall_turnaround % 60}m"
        }

        return {
            "simulation_active": self.is_running,
            "simulation_tick": self.simulation_tick,
            "random_seed": self.seed,
            "time_of_day": diurnal_obj,
            "diurnal_profile": diurnal_obj,
            "transport_connection": transport_obj,
            "wheelchair_transport_link": transport_obj,
            "kpi_overview": kpi_obj,
            "metrics": kpi_obj,
            "modality_cards": modality_cards,
            "modalities": modality_dict,
            "ai_insights": insights,
            "ai_bottleneck_insights": insights,
            "featured_patient_journey": journey_data,
            "featured_patient": journey_target,
            "patient_count": len(self.patients)
        }


# Global Simulation Engine Singleton
simulation_engine = HospitalSimulationEngine(initial_seed=42)
