"""
MediTrack AI - Emergency Priority AI Engine
Calculates urgency classification, quantitative priority scores (0-100),
and immediate automated allocation dispatch decisions.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from database.db import get_connection

def calculate_emergency_priority(
    ward_id: str,
    equipment_type: str,
    quantity: int,
    patient_urgency: str = "Critical",
    reason: str = "Trauma triage influx"
):
    """
    Evaluates emergency request parameters and generates an AI priority score and rationale.
    Returns:
      - priority_score: 0-100
      - priority_level: 'HIGH', 'MEDIUM', 'LOW'
      - badge_color: 'red', 'yellow', 'green'
      - recommended_action: clinical action recommendation
      - factor_breakdown: detailed weighted contributions
      - explanation: clinical engineering reasoning
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get ward details
    cursor.execute("SELECT * FROM wards WHERE id = ? OR name LIKE ?", (ward_id, f"%{ward_id}%"))
    ward = cursor.fetchone()
    ward_name = ward["name"] if ward else "Emergency Ward"
    ward_type = ward["type"] if ward else "Emergency"

    # Count available equipment fleet-wide
    cursor.execute("""
        SELECT COUNT(*) as count FROM equipment 
        WHERE type LIKE ? AND status = 'AVAILABLE'
    """, (f"%{equipment_type}%",))
    avail_count = cursor.fetchone()["count"]
    conn.close()

    # 1. Patient Urgency Factor (Max 35 points)
    urgency_map = {
        "Critical": 35,
        "Severe": 28,
        "Urgent": 20,
        "Moderate": 12,
        "Stable": 6
    }
    patient_points = urgency_map.get(patient_urgency, 25)

    # 2. Ward Urgency Factor (Max 25 points)
    ward_map = {
        "Emergency": 25,
        "ICU": 23,
        "Surgical": 18,
        "General": 10,
        "Storage": 2
    }
    ward_points = ward_map.get(ward_type, 15)

    # 3. Equipment Availability Factor (Max 15 points)
    if avail_count <= 3:
        avail_points = 15
    elif avail_count <= 8:
        avail_points = 13
    elif avail_count <= 15:
        avail_points = 12
    else:
        avail_points = 8

    # 4. Current Demand Factor (Max 15 points)
    if quantity >= 3:
        demand_points = 12
    elif quantity == 2:
        demand_points = 10
    else:
        demand_points = 7

    # 5. Distance & Staging Proximity Factor (Max 10 points)
    # Emergency Ward and ICU are closest to Central Storage Transit Corridors
    distance_map = {
        "Emergency": 10,
        "ICU": 9,
        "Surgical": 8,
        "General": 6,
        "Storage": 4
    }
    dist_points = distance_map.get(ward_type, 7)

    total_score = min(100, patient_points + ward_points + avail_points + demand_points + dist_points)

    if total_score >= 80:
        priority_level = "HIGH PRIORITY"
        badge_color = "red"
        rec_action = "Immediate allocation"
    elif total_score >= 55:
        priority_level = "MEDIUM PRIORITY"
        badge_color = "yellow"
        rec_action = "Priority Staging Queue (within 15 mins)"
    else:
        priority_level = "ROUTINE"
        badge_color = "green"
        rec_action = "Routine Ward Fulfillment"

    explanation = (
        f"Request classified as {priority_level} (Score: {total_score}/100). "
        f"Patient status '{patient_urgency}' in '{ward_name}' imposes critical response requirement. "
        f"Available inventory ({avail_count} {equipment_type}s) versus {quantity} requested requires {rec_action.lower()}."
    )

    return {
        "ward_name": ward_name,
        "equipment_type": equipment_type,
        "quantity": quantity,
        "patient_urgency": patient_urgency,
        "reason": reason,
        "priority_score": total_score,
        "priority_level": priority_level,
        "badge_color": badge_color,
        "recommended_action": rec_action,
        "available_inventory": avail_count,
        "factors": {
            "patient_urgency": patient_points,
            "ward_urgency": ward_points,
            "equipment_availability": avail_points,
            "current_demand": demand_points,
            "distance": dist_points
        },
        "explanation": explanation
    }

if __name__ == "__main__":
    p_res = calculate_emergency_priority("ward-emergency", "Wheelchair", 3, "Critical", "Highway collision triage")
    print(f"Priority Score: {p_res['priority_score']}/100 [{p_res['priority_level']}]")
    print(f"Action: {p_res['recommended_action']}")
    print(f"Explanation: {p_res['explanation']}")
