# 🏥 MediTrack AI — Intelligent Medical Equipment Management System
> **Track. Predict. Allocate. Protect.**  
> *"MediTrack AI doesn't just tell hospitals where their equipment is. It predicts what they will need, identifies what may fail, and recommends where every available piece of equipment should go."*

---

## 🌟 Overview
**MediTrack AI** transforms traditional hospital equipment tracking into an autonomous, AI-powered healthcare operations platform. Combining physical **ESP32 IoT hardware** with **machine learning predictive models** and **computer vision**, MediTrack AI unifies equipment identification, spatial tracking, predictive maintenance, emergency prioritization, and ward demand forecasting into a single cohesive system.

---

## 🏗️ System Architecture

```text
                   ┌────────────────────────┐
                   │   ESP32 IoT Hardware   │
                   │  RC522 RFID • PIR      │
                   │  Battery ADC • Buzzer  │
                   └───────────┬────────────┘
                               │ (Wi-Fi HTTP & WebSocket)
                               ▼
                   ┌────────────────────────┐
                   │  FastAPI/Starlette     │
                   │  ASGI Backend Engine   │
                   └───────────┬────────────┘
                               │
       ┌───────────────────────┼───────────────────────┐
       ▼                       ▼                       ▼
┌──────────────┐     ┌──────────────────┐     ┌────────────────┐
│  SQLite DB   │     │    AI Models     │     │   WebSocket    │
│  60+ Assets  │     │  • Allocation    │     │   Broadcast    │
│  Wards & Logs│     │  • Maintenance   │     │   Manager      │
└──────────────┘     │  • Forecasting   │     └────────┬───────┘
                     │  • Vision & YOLO │              │
                     │  • Emergency AI  │              │
                     └─────────┬────────┘              │
                               │                       │
                               ▼                       ▼
                   ┌────────────────────────────────────────┐
                   │     Dark Futuristic Medical UI         │
                   │  Glassmorphism • SVG Hospital Map      │
                   │  Real-time Gauges • MediAI Assistant   │
                   └────────────────────────────────────────┘
```

---

## 🧠 The 5 AI Machine Learning Modules

| AI Engine | Model / Technique | Inputs | Outputs | Hackathon Demo Focus |
|---|---|---|---|---|
| **AI Allocation** | Multi-Criteria Weighted Optimization | Proximity, Condition, MTBF, Battery, Urgency | Best candidate units + Transit Route | Recommends `WC-007`, `WC-012`, `WC-018` for Emergency Ward |
| **Predictive Maintenance** | Random Forest Regressor / Classifier | Usage hours, movement count, service age, faults | Degradation trajectory (+28d) & Failure % | Diagnoses `WC-014` at 78% risk; alerts 7–12 days window |
| **Demand Forecasting** | Random Forest Diurnal Time-Series | Hour, day, triage influx, admissions | Hourly demand curves (+1h, +3h, +6h, +12h, +24h) | Predicts Emergency Wheelchair surge (4 → 7 units) |
| **Vision AI** | YOLO Object Detection + Optical Counting | Camera video feed / CCTV | Bounding boxes, confidence, class counts | Flags inventory mismatch: DB=15 vs Camera=12 (-3 discrepancy) |
| **Emergency Priority AI** | Multi-Variable Urgency Classifier | Patient urgency, ward urgency, fleet scarcity | Urgency Score (0–100) & Dispatch Action | Generates High Priority (94/100) for trauma surge |

---

## ⚡ Quick Start (One-Click Launch)

1. **Start the Application Server & Dashboard:**
   ```powershell
   python run.py
   ```
2. The server initializes SQLite with **60 realistic equipment items** and automatically opens your browser to:
   ```text
   http://127.0.0.1:8000
   ```

---

## 🏆 The Hackathon Demo Script (9 Steps)

1. **Step 1 — RFID Identification:**
   - Click the **"RFID Tap"** button in the top bar.
   - The UI immediately identifies `Wheelchair WC-007 (Smart IoT)` with its UID `10 0D 71 5C` and location `Central Storage A`.
2. **Step 2 — IoT Sensor Telemetry:**
   - Click **"PIR Motion"** in the top bar.
   - The IoT feed pulses green: `WC-009` shows active movement, live session runtime `00:03:17`, and critical 18% battery alert.
3. **Step 3 — Emergency Ward Triage Surge:**
   - Click **"Surge"** in the top bar or submit an emergency request in the **Emergency Requests** tab.
   - AI calculates an urgency score of **94 / 100 (HIGH PRIORITY)** with immediate automated allocation recommendations.
4. **Step 4 — AI Allocation Sequence:**
   - Navigate to **AI Allocation** and click **"ASK AI TO ALLOCATE"**.
   - Watch the animated 6-step reasoning sequence evaluate availability, distance, condition, and MTBF.
   - AI selects `WC-007`, `WC-012`, and `WC-018` with full clinical justifications.
5. **Step 5 — Live Spatial Transit Route:**
   - Click **"DISPATCH & INITIATE TRANSIT ROUTE"**.
   - The interactive hospital map animates an equipment transit route from `Central Storage A` to `Emergency Ward`.
6. **Step 6 — Predictive Maintenance:**
   - Open **Predictive Maintenance** tab.
   - Review `WC-014`: 78% failure risk, 74 days since service, and projected failure curve over the next 28 days with **91% AI confidence**.
7. **Step 7 — Computer Vision AI:**
   - Open **Vision AI & Camera** tab.
   - Observe live YOLO detection bounding boxes across triage equipment (Wheelchairs 94%, Stretchers 91%, Walkers 89%).
8. **Step 8 — Automatic Inventory Counting:**
   - Point out the **"⚠ OPTICAL INVENTORY MISMATCH"** banner: Database expects 15, camera detected 12 (Discrepancy: -3).
   - Click **"INVESTIGATE DISCREPANCY"** to view audit logs showing the missing units.
9. **Step 9 — Demand Forecasting & MediAI Assistant:**
   - Check **Demand Forecast AI**: Emergency Ward Wheelchair surge (4 → 7 units).
   - Open the floating **MediAI Assistant** in the bottom right and ask: *"Why was WC-007 selected?"* or *"Which equipment needs maintenance?"* for instant, grounded clinical reasoning.

---

## 🔌 Hardware Circuit & Pinout (ESP32)

| Component | ESP32 GPIO Pin | Description |
|---|---|---|
| **RC522 SDA (SS)** | `GPIO 5` | SPI Chip Select |
| **RC522 SCK** | `GPIO 18` | SPI Clock |
| **RC522 MOSI** | `GPIO 23` | SPI Master Out Slave In |
| **RC522 MISO** | `GPIO 19` | SPI Master In Slave Out |
| **RC522 RST** | `GPIO 22` | Hardware Reset |
| **HC-SR501 PIR** | `GPIO 27` | Digital Motion Detection |
| **Push Button** | `GPIO 14` | Start / Stop Usage Session (Internal Pullup) |
| **Green LED** | `GPIO 12` | Available / Active Indicator |
| **Red LED** | `GPIO 13` | Alert / Low Battery Indicator |
| **Buzzer** | `GPIO 25` | Audible RFID Scan & Alert Signal |
| **Battery ADC** | `GPIO 34` | Analog Voltage Divider Telemetry |

Firmware source is located at `firmware/esp32_meditrack.ino`.

---

## 📡 REST API & WebSocket Endpoints

- `GET  /api/stats` — Executive dashboard KPIs
- `GET  /api/equipment` — Searchable equipment catalog
- `GET  /api/equipment/{id}` — Equipment profile and diagnostics
- `POST /api/allocation/evaluate` — Multi-factor allocation optimization
- `POST /api/allocation/confirm` — Dispatches equipment and triggers animated route
- `GET  /api/maintenance/{id}` — Predictive degradation trajectory
- `GET  /api/demand/forecast` — Temporal ward demand curves
- `POST /api/emergency/request` — Emergency request urgency evaluation
- `POST /api/esp32/telemetry` — Hardware telemetry receiver
- `POST /api/esp32/rfid` — RFID card swipe endpoint
- `POST /api/assistant/chat` — Grounded natural-language MediAI chat
- `POST /api/demo/simulate-step` — Demo mode trigger simulations
- `WS   /ws` — Real-time telemetry broadcast stream
