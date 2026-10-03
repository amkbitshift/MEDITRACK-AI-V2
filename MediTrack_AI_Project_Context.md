# MediTrack AI --- Complete Project Context & Hardware/Software Handoff

## 1. Project Overview

**Project:** MediTrack AI

MediTrack AI is an AI-powered hospital operations platform combining
real-time medical equipment tracking, ESP32/IoT hardware, RFID
identification, PIR-based motion/usage detection, hospital workflow
simulation, and radiology operations analytics.

The project has two connected layers:

1.  **Physical IoT/hardware layer** --- ESP32, RC522 RFID, PIR motion
    sensor, buttons, LEDs, buzzer.
2.  **Hospital operations software/AI layer** --- FastAPI backend,
    database, WebSocket, dashboard, radiology analytics, equipment
    tracking, hospital map and AI decision support.

Core architecture:

``` text
Physical Equipment
      ↓
RFID / Sensors
      ↓
ESP32
      ↓
Wi-Fi
      ↓
FastAPI Backend
      ↓
Database / State Management
      ↓
WebSocket
      ↓
MediTrack AI Web App
      ↓
Radiology + Hospital Operations + AI Insights
```

------------------------------------------------------------------------

## 2. Main Project Focus

The project originally focused on tracking medical equipment. After the
second judging phase, the focus expanded to demonstrate the connection
between:

**equipment availability → radiology workflow → patient waiting →
reporting delay → AI operational insights**

Radiology is now the main operational department used for the
demonstration.

The project is a hackathon/Yodha-style prototype and is intended for
operational decision support, not medical diagnosis.

------------------------------------------------------------------------

## 3. Radiology Workflow

The intended patient journey is:

``` text
Patient Request
      ↓
Registration
      ↓
Waiting for Scan
      ↓
Scan in Progress
      ↓
Waiting for Report
      ↓
Report Ready
```

Track these separately:

-   Waiting for scan
-   Scan duration
-   Waiting for report
-   Total turnaround time

Formula:

``` text
Total Turnaround =
Waiting for Scan + Scan Duration + Waiting for Report
```

Do not collapse everything into one generic waiting-time value.

------------------------------------------------------------------------

## 4. Radiology Sections

The synthetic/demo hospital model includes:

-   X-Ray
-   CT Scan
-   MRI
-   Ultrasound / USG
-   Mammography
-   Fluoroscopy
-   Interventional Radiology

Each modality should be able to show:

-   Patients waiting
-   Queue position
-   Waiting for scan
-   Scan in progress
-   Scan duration
-   Reports pending
-   Waiting for report
-   Equipment availability
-   Equipment utilization
-   Current status

------------------------------------------------------------------------

## 5. Synthetic Hospital Dataset

A synthetic dataset is being added for demonstration and analytics. It
must contain **no real patient information**.

Suggested fields:

``` text
patient_id
department
modality
priority
request_time
registration_time
queue_position

equipment_id
equipment_status
equipment_location

waiting_for_scan_minutes
scan_duration_minutes
scan_start_time
scan_end_time

waiting_for_report_minutes
report_start_time
report_ready_time

total_turnaround_minutes

radiologist_status
report_status

ward
emergency_flag
time_of_day
day_of_week
delay_reason
```

Synthetic patient IDs can be `P-1001`, `P-1002`, etc. Never use real
patient names.

Priority categories:

-   EMERGENCY
-   URGENT
-   ROUTINE

Waiting values should vary according to modality, queue, priority,
equipment availability, time of day, day of week, workload and reporting
workload.

The app should support:

-   **DEMO / SYNTHETIC MODE**
-   **REAL HARDWARE / REAL BACKEND MODE**

These must be visually distinguishable.

------------------------------------------------------------------------

## 6. AI / Analytics Goal

The AI portion is operational decision support, not diagnosis.

Possible insights:

-   High scan queue
-   Equipment shortage
-   High equipment utilization
-   Report backlog
-   Long patient turnaround
-   Radiology bottleneck
-   Demand increase
-   Maintenance risk

Example:

> MRI reporting workload is currently contributing more to total
> turnaround time than scan availability.

Example:

> CT transport demand has increased while available transport equipment
> is limited.

------------------------------------------------------------------------

# HARDWARE

## 7. ESP32

Main controller:

**ESP32-WROOM development board / ESP32 Dev Module**

Connected components:

-   RC522 RFID reader
-   PIR motion sensor
-   Main button
-   Temporary button
-   Red LED
-   Green LED
-   Buzzer

The ESP32 communicates with the backend over Wi-Fi.

------------------------------------------------------------------------

## 8. RC522 RFID Reader

Component: **RC522 RFID reader**

Purpose:

-   Identify equipment
-   Associate RFID UID with equipment
-   Trigger equipment state updates

Pin configuration:

``` text
SS / SDA = GPIO 5
RST      = GPIO 27
SCK      = GPIO 18
MISO     = GPIO 19
MOSI     = GPIO 23
```

Current Arduino initialization:

``` cpp
SPI.begin(18, 19, 23, 5);
rfid.PCD_Init();
```

------------------------------------------------------------------------

## 9. PIR Motion Sensor

Component: **PIR (Passive Infrared) motion sensor**.

The project uses the PIR to detect movement/changes in infrared
radiation associated with moving warm bodies. It is **not a medical
temperature sensor**.

Pin:

``` text
PIR = GPIO 32
```

Current intended behavior:

``` text
Equipment identified
      ↓
Equipment AVAILABLE
      ↓
PIR detects continuous movement
      ↓
10 seconds
      ↓
AUTO USAGE START
      ↓
IN_USE
```

PIR should not automatically start usage while equipment is already
`IN_USE`, `TEMPORARY_HOLD` or `RETURNING_TO_STORAGE`.

------------------------------------------------------------------------

## 10. LEDs and Buzzer

``` text
Red LED   = GPIO 25
Green LED = GPIO 26
Buzzer    = GPIO 14
```

They provide physical status/audio feedback.

Typical uses:

-   RFID detection
-   State change
-   Warning
-   Storage verification
-   Completion

Avoid continuous unnecessary buzzing.

------------------------------------------------------------------------

## 11. Buttons

Main button:

``` text
GPIO 33
```

Typical usage:

``` text
AVAILABLE → Main Button → IN_USE
IN_USE → Main Button → Usage End
```

Temporary button:

``` text
GPIO 13
```

Used for `TEMPORARY_HOLD` behavior.

Button debounce should be around 200--300 ms.

------------------------------------------------------------------------

## 12. Equipment RFID Mapping

Current known mappings:

  RFID UID        Equipment
  --------------- -----------------------
  `30 94 2B 58`   Mechanical Ventilator
  `BD 70 00 02`   Stretcher
  `10 0D 71 5C`   Wheelchair
  `21 2F 7B 69`   Infusion Pump
  `40 0D 0F 58`   Smart ICU Bed

Known equipment IDs:

``` text
Wheelchair → WC-007
Ventilator → VENT-04
Stretcher → ST-003
```

Do not invent IDs for the other equipment if the existing backend
already defines them; inspect the existing project data.

------------------------------------------------------------------------

# EQUIPMENT STATE MANAGEMENT

## 13. Canonical Equipment State Machine

The previous implementation used independent flags for usage and
temporary waiting. That can create contradictory states.

Preferred canonical states:

``` text
AVAILABLE
IN_USE
TEMPORARY_HOLD
WAITING
RETURNING_TO_STORAGE
MAINTENANCE
UNKNOWN
```

Normal flow:

``` text
AVAILABLE
    ↓
WAITING
    ↓
IN_USE
    ↓
TEMPORARY_HOLD
    ↓
IN_USE
    ↓
RETURNING_TO_STORAGE
    ↓
AVAILABLE
```

Maintenance:

``` text
AVAILABLE
    ↓
MAINTENANCE
    ↓
AVAILABLE
```

Never allow contradictory states such as:

``` text
AVAILABLE + IN_USE
AVAILABLE + TEMPORARY_HOLD
MAINTENANCE + IN_USE
```

The backend should be the canonical source of truth.

------------------------------------------------------------------------

## 14. Temporary Hold

`TEMPORARY_HOLD` means equipment is temporarily unavailable for normal
allocation but has not been returned or sent for maintenance.

Example:

``` text
Equipment: WC-007
Status: TEMPORARY HOLD
Reason: Awaiting patient transfer
Duration: 00:04:21
```

Expected transitions:

``` text
IN_USE → TEMPORARY_HOLD → IN_USE
```

or:

``` text
TEMPORARY_HOLD → RETURNING_TO_STORAGE
```

Record timestamps and reasons.

------------------------------------------------------------------------

# WHEELCHAIR STORAGE FEATURE

## 15. Judge Feedback: 2-Minute Wheelchair Return

One major judge suggestion was to save staff time by automatically
making a returned wheelchair available after a short verification
period.

Designated location:

``` text
RADIOLOGY_WHEELCHAIR_STORAGE
```

Expected flow:

``` text
Wheelchair IN_USE
       ↓
Returned to storage
       ↓
RFID detected
       ↓
RETURNING_TO_STORAGE
       ↓
2-minute verification
       ↓
AVAILABLE
```

During verification:

``` text
WC-007
Wheelchair

Location:
Radiology Wheelchair Storage

Status:
RETURNING TO STORAGE

Verification:
01:42 remaining
```

After two minutes:

``` text
WC-007
✓ AVAILABLE

Location:
Radiology Wheelchair Storage

Return Verified
```

If the wheelchair leaves before verification completes, cancel the timer
and do not mark it available.

------------------------------------------------------------------------

## 16. Important Hardware Limitation

The current physical prototype has one RC522 reader. Therefore the ESP32
cannot independently know that an RFID scan occurred at a specific room
unless there is a location-specific RFID reader or another location
sensor.

For the prototype demonstration, the intended method is:

``` text
Place wheelchair at storage area
        ↓
Scan WC-007 RFID
        ↓
Backend starts 2-minute verification
        ↓
AVAILABLE
```

The backend should be the authoritative source for the two-minute timer.

------------------------------------------------------------------------

## 17. Preferred Storage Architecture

``` text
Wheelchair
    ↓
RFID tag
    ↓
RC522
    ↓
ESP32
    ↓
STORAGE_RETURN event
    ↓
FastAPI backend
    ↓
Start 2-minute timer
    ↓
Verify storage state
    ↓
AVAILABLE
    ↓
WebSocket broadcast
    ↓
Dashboard
    ↓
Hospital Map
    ↓
ESP32 Hardware Lab
```

------------------------------------------------------------------------

## 18. Maximum Usage Guard

Current intended maximum usage:

``` text
30 minutes
```

The ESP32 should automatically end active usage when the configured
maximum is reached.

For a wheelchair, the preferred return flow is:

``` text
IN_USE
↓
Usage limit reached
↓
RETURNING_TO_STORAGE
```

For other equipment, follow the existing backend workflow rather than
inventing a new one.

------------------------------------------------------------------------

# SOFTWARE / BACKEND

## 19. Backend

Backend technology:

**FastAPI / Uvicorn**

Current development backend address used by the ESP32:

``` text
http://172.27.195.51:8000
```

The server should bind to:

``` text
0.0.0.0:8000
```

`0.0.0.0` is a bind address, not the browser destination. Browser/ESP32
access uses the laptop LAN IP.

Existing project activity has included routes such as:

``` text
GET /api/equipment
GET /api/blueprint
GET /api/dashboard/role-view
POST /api/demo/simulate-step
WebSocket /ws
```

Do not invent replacement endpoints before inspecting the existing
backend.

------------------------------------------------------------------------

## 20. Central Equipment State Service

Preferred architecture:

``` text
update_equipment_state(
    equipment_id,
    new_state,
    reason,
    location
)
```

It should:

1.  Validate the state transition
2.  Update database
3.  Record timestamp
4.  Record location
5.  Broadcast WebSocket event
6.  Update dashboard
7.  Update Hardware Lab

The frontend should not independently invent canonical equipment states.

------------------------------------------------------------------------

## 21. Hardware Events

Preferred event types:

``` text
RFID_DETECTED
USAGE_STARTED
AUTO_USAGE_STARTED
TEMPORARY_HOLD_STARTED
TEMPORARY_HOLD_ENDED
USAGE_ENDED
AUTO_USAGE_ENDED
STORAGE_RETURN
STORAGE_VERIFIED
UNKNOWN_RFID
```

Example:

``` json
{
  "equipment": "WHEELCHAIR",
  "equipment_id": "WC-007",
  "event": "STORAGE_RETURN",
  "location": "RADIOLOGY_WHEELCHAIR_STORAGE"
}
```

The exact API payload must match the existing backend implementation.

------------------------------------------------------------------------

## 22. WebSocket

The existing WebSocket should remain the main real-time update
mechanism.

Preferred flow:

``` text
Physical event
    ↓
ESP32
    ↓
Backend
    ↓
WebSocket
    ↓
Dashboard
    ↓
Radiology
    ↓
Hospital Map
    ↓
ESP32 Hardware Lab
```

Do not create separate frontend-only hardware states.

------------------------------------------------------------------------

# WEB APPLICATION

## 23. Existing / Planned Modules

The application includes:

-   Dashboard
-   Radiology Operations
-   Equipment Inventory
-   AI Allocation
-   Live Tracking
-   Hospital Map
-   ESP32 Hardware Lab
-   Maintenance Intelligence
-   IoT Intelligence
-   Demand Forecast
-   Emergency Requests
-   Inventory Intelligence
-   Vision AI
-   Equipment Movement
-   Reports
-   MediAI
-   Settings
-   Role-based access
-   Demo/Synthetic mode
-   Real hardware mode

------------------------------------------------------------------------

## 24. Hospital Map

The demonstration blueprint includes:

-   Emergency
-   Radiology
-   MRI
-   CT
-   X-Ray
-   Ultrasound
-   ICU
-   Operation Theatre
-   General Ward
-   Equipment Storage
-   Radiology Wheelchair Storage
-   Biomedical Engineering

Example equipment movement:

``` text
General Ward
    ↓
Radiology
    ↓
CT
    ↓
Radiology Wheelchair Storage
```

The map is a demo blueprint, not a real hospital map.

------------------------------------------------------------------------

## 25. Equipment Tracking

Tracked equipment includes:

-   Wheelchair WC-007
-   Mechanical Ventilator VENT-04
-   Stretcher ST-003
-   Infusion Pump
-   Smart ICU Bed

Equipment detail should show:

-   Equipment ID
-   Type
-   RFID UID
-   Status
-   Current location
-   Last updated
-   Usage duration
-   Movement history

Example:

``` text
WC-007
WHEELCHAIR

Status: AVAILABLE
Location: Radiology Wheelchair Storage
RFID: 10 0D 71 5C
Last Updated: LIVE
```

------------------------------------------------------------------------

## 26. Live Tracking

Show:

-   Equipment
-   Current location
-   Previous location
-   Destination
-   Movement time
-   Status

Example:

``` text
WC-007

WARD
 ↓
RADIOLOGY
 ↓
STORAGE
```

Movement should be visually animated but subtle.

------------------------------------------------------------------------

## 27. Radiology + Equipment Connection

This is a central project story:

``` text
Patient requires CT
        ↓
CT queue
        ↓
Transport equipment required
        ↓
Check stretcher/wheelchair availability
        ↓
Equipment allocated
        ↓
Patient transported
        ↓
CT scan
        ↓
Report queue
        ↓
Report ready
```

Synthetic operational data can demonstrate how transport equipment
shortages may contribute to operational waiting.

------------------------------------------------------------------------

## 28. AI Allocation

The AI Allocation page can show:

-   Patient/request
-   Priority
-   Required equipment
-   Available equipment
-   Equipment location
-   Suggested allocation

Example:

``` text
Radiology
CT Patient
Priority: URGENT

Required: Stretcher
Available: ST-003
Location: Emergency

Suggested allocation: ST-003
```

This is operational decision support.

------------------------------------------------------------------------

## 29. Maintenance Intelligence

Possible data:

-   Equipment
-   Usage
-   Maintenance risk
-   Last service
-   Next service

Do not make unsupported medical/safety claims.

------------------------------------------------------------------------

## 30. IoT Intelligence

Show:

-   ESP32 connection
-   RFID activity
-   PIR activity
-   Button activity
-   LED state
-   Buzzer state
-   Wi-Fi status
-   Backend status
-   WebSocket status
-   Hardware events

------------------------------------------------------------------------

## 31. Demand Forecast

Possible synthetic/demo metrics:

-   Expected demand
-   Current demand
-   Available equipment
-   Predicted shortage
-   Modality demand
-   Department demand

Clearly label synthetic forecasts when appropriate.

------------------------------------------------------------------------

## 32. Emergency Requests

May show:

-   Priority
-   Department
-   Equipment needed
-   Request time
-   Status
-   Assigned equipment

Emergency cases should be distinct without relying only on red color.

------------------------------------------------------------------------

## 33. Inventory Intelligence

Possible metrics:

-   Total fleet
-   Available
-   In use
-   Maintenance
-   Underutilized
-   High demand
-   Shortage risk

------------------------------------------------------------------------

## 34. Vision AI

Can show:

-   Camera
-   Detection
-   Object
-   Confidence
-   Location
-   Timestamp

If simulated, label it as DEMO.

------------------------------------------------------------------------

## 35. Reports

Reports can cover:

-   Radiology
-   Equipment
-   Waiting time
-   Turnaround
-   Maintenance
-   Utilization
-   Movement

Prefer clear charts and summaries over very dense tables.

------------------------------------------------------------------------

## 36. MediAI

The assistant can answer operational questions such as:

``` text
Which equipment is available?
Which radiology department has the longest queue?
Where is WC-007?
Which modality has the highest report backlog?
Which equipment is currently in use?
What is causing the current radiology bottleneck?
```

It should not be presented as a medical diagnosis system.

------------------------------------------------------------------------

# UI / UX

## 37. Visual Design Reference

The website is being redesigned using a reference image with a premium
soft healthcare aesthetic.

Desired visual language:

-   Soft lavender/light-blue background
-   White translucent glass cards
-   Large rounded corners
-   Soft shadows
-   Blue/purple ambient gradients
-   Glassmorphism
-   Neumorphic touches
-   Large clean typography
-   Minimal navigation
-   Floating circular elements
-   Rounded pill buttons
-   Generous whitespace
-   Calm premium healthcare appearance

Overall feeling:

**Premium Healthcare + AI Platform + IoT Digital Twin + Modern SaaS**

Avoid:

-   Dense traditional admin-dashboard look
-   Excessive neon
-   Excessive borders
-   Harsh colors
-   Tiny text
-   Clutter
-   Unnecessary animations

Every page should feel like part of one unified design system.

------------------------------------------------------------------------

## 38. User-Friendly Requirement

The app should be understandable to non-technical hospital users.

Every major screen should answer:

``` text
WHAT is happening?
WHERE is it?
WHAT is the status?
HOW LONG has it been?
WHAT should I do?
```

Use plain labels instead of internal technical field names.

------------------------------------------------------------------------

## 39. Responsive Requirement

Test and support:

``` text
320px
375px
390px
430px
768px
820px
1024px
1280px
1366px
1440px
1920px
```

Mobile:

-   Hamburger navigation
-   Single-column cards
-   Stacked metrics
-   Vertical timelines
-   Responsive charts
-   Responsive map
-   Large touch targets

Tablet:

-   Two-column layouts where appropriate

Desktop:

-   Spacious multi-column layouts

Avoid horizontal overflow.

------------------------------------------------------------------------

## 40. Loading / Empty / Error States

Loading examples:

-   Loading Radiology...
-   Synchronizing Equipment...
-   Connecting to ESP32...
-   Loading Hospital Map...
-   Loading AI Insights...

Empty examples:

-   No patients currently waiting.
-   No pending reports.
-   No equipment currently available in this zone.

Do not expose raw technical errors to normal users. Use friendly
messages such as:

> Hardware connection temporarily unavailable.

> Unable to load radiology data.

Technical details may remain in developer logs.

------------------------------------------------------------------------

# ARDUINO / FIRMWARE

## 41. Current Firmware Libraries

``` cpp
#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <HTTPClient.h>
```

The RC522 library used is **MFRC522 by GithubCommunity**.

------------------------------------------------------------------------

## 42. Current Pin Map

``` text
RC522 SS/SDA  → GPIO 5
RC522 RST     → GPIO 27
RC522 SCK     → GPIO 18
RC522 MISO    → GPIO 19
RC522 MOSI    → GPIO 23

Red LED       → GPIO 25
Green LED     → GPIO 26
Buzzer        → GPIO 14

Main Button   → GPIO 33
Temp Button   → GPIO 13
PIR           → GPIO 32
```

Do not change physical pin assignments without first checking the actual
wiring.

------------------------------------------------------------------------

## 43. Firmware Behavior

Startup:

-   Connect Wi-Fi
-   Print ESP32 IP
-   Initialize outputs
-   Initialize buttons/PIR
-   Initialize RC522
-   Wait for RFID

RFID:

-   Detect UID
-   Identify equipment
-   Notify backend
-   Set equipment to appropriate state

PIR:

-   Detect movement
-   Require approximately 10 seconds continuous motion
-   Start usage automatically when appropriate

Main button:

-   Start/stop normal usage according to state machine

Temporary button:

-   Enter/release temporary hold where allowed
-   Use debounce

Usage guard:

-   Maximum 30 minutes

Wheelchair:

-   Returned to storage workflow uses `STORAGE_RETURN`
-   Backend performs 2-minute verification
-   Backend broadcasts `AVAILABLE` after successful verification

------------------------------------------------------------------------

## 44. Important Firmware Principle

Do not create a second communication system.

Keep the existing ESP32 → Wi-Fi → backend communication architecture.

The backend should remain the canonical source of equipment state.

The ESP32 should primarily detect physical events and report them.

------------------------------------------------------------------------

# DEMONSTRATION

## 45. Expected Hardware Demo

### RFID

``` text
Scan equipment
↓
Equipment identified
↓
Dashboard updates
```

### PIR

``` text
Equipment AVAILABLE
↓
Human movement detected
↓
10 seconds continuous motion
↓
AUTO USAGE START
↓
IN_USE
```

### Main button

``` text
AVAILABLE
↓
Button
↓
IN_USE

IN_USE
↓
Button
↓
End usage
```

### Temporary button

``` text
TEMPORARY_HOLD
↓
Resume
↓
IN_USE / AVAILABLE according to valid workflow
```

### Wheelchair return

``` text
Wheelchair IN_USE
↓
Return to storage
↓
RFID scan
↓
RETURNING_TO_STORAGE
↓
2-minute verification
↓
AVAILABLE
```

### Website

Real events should update through backend/WebSocket on:

-   Dashboard
-   Equipment
-   Hospital Map
-   ESP32 Hardware Lab
-   Notifications

------------------------------------------------------------------------

# CURRENT JUDGE FEEDBACK

## 46. Second Judging Phase Feedback

### Suggestion 1 --- Wheelchair storage

Create a place where wheelchairs are stored. After a wheelchair is
returned and identified there, it should automatically become available
after approximately 2 minutes to save staff time and improve efficiency.

### Suggestion 2 --- Temporary/In-use state

The temporary/in-use section has flaws. It should be corrected with a
proper state model rather than conflicting toggles.

### Additional enhancement

Create synthetic datasets for radiology and other departments where the
system demonstrates:

-   waiting before a scan
-   scan duration
-   waiting for the report
-   report ready
-   varying workload/waiting times

The values should vary automatically based on operational conditions.

------------------------------------------------------------------------

# 47. Final Project Story

The complete story is:

``` text
Physical medical equipment
        ↓
RFID + PIR + ESP32
        ↓
Real-time equipment state
        ↓
Hospital equipment availability
        ↓
Radiology workflow
        ↓
Patient scan waiting
        ↓
Scan
        ↓
Report waiting
        ↓
Report ready
        ↓
Turnaround analysis
        ↓
AI bottleneck detection
        ↓
Operational decision support
```

The project is an operational platform for visibility, resource
tracking, workflow awareness and decision support. It is not intended to
replace doctors or radiologists.

------------------------------------------------------------------------

# 48. Instructions for Any AI Continuing the Project

If another AI receives this document, it should:

1.  Inspect the existing architecture before changing code.
2.  Preserve existing ESP32 wiring.
3.  Preserve existing RFID mappings.
4.  Preserve working backend/API/WebSocket behavior.
5.  Inspect actual source files before inventing endpoints.
6.  Keep the backend as the canonical equipment-state source.
7.  Keep real hardware and synthetic simulation clearly separated.
8.  Avoid fake hardware events when real hardware data exists.
9.  Make changes incrementally and test after each major change.
10. Give exact file names and code locations for changes.
11. Do not assume one RFID reader can determine room location.
12. Treat wheelchair storage as a backend-controlled verification
    workflow.
13. Keep the UI user-friendly and responsive.
14. Do not remove working functionality simply to improve appearance.
15. Preserve the current physical pin map unless wiring is intentionally
    changed and verified.

------------------------------------------------------------------------

# 49. One-Line Project Description

**MediTrack AI is a real-time AI-powered hospital operations platform
that combines ESP32-based RFID/PIR equipment tracking with radiology
workflow simulation, patient waiting-time analytics, equipment
allocation, and operational bottleneck detection.**
