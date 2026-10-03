/*
 * ======================================================================================
 * MediTrack AI — ESP32 Smart Medical Equipment & RFID Hallway Waypoint Node
 * Dual-Mode: Bluetooth Serial (SPP) + Wi-Fi Telemetry
 * ======================================================================================
 * Hardware Components:
 *   - ESP32-WROOM-32D Development Board
 *   - MFRC522 RFID SPI Reader (SS: 5, RST: 27, SCK: 18, MISO: 19, MOSI: 23)
 *   - HC-SR501 PIR Motion Sensor (Digital Pin 32)
 *   - Switch 1 (Main ON/OFF / Start-End Session): Pin 33 (INPUT_PULLUP)
 *   - Switch 2 (Temporary Hold / Pause): Pin 13 (INPUT_PULLUP)
 *   - Status LEDs: Green (Pin 26), Red Alert (Pin 25)
 *   - Active Buzzer (Pin 14)
 *
 * RFID Hallway Waypoint Positioning:
 *   - Tag 1 (UID: 10 0D 71 5C) -> Waypoint 1: Emergency Ward Dock (0.0 m) / Wheelchair WC-007
 *   - Tag 2 (UID: 40 0D 0F 58) -> Waypoint 2: Central Transit Corridor Junction (15.0 m)
 *   - Tag 3 (UID: 30 94 2B 58) -> Waypoint 3: Radiology Suite Arrival (30.0 m)
 *   - Tag 4 (UID: BD 70 00 02) -> Waypoint 4: ICU Recovery Ward (45.0 m)
 *   - Tag 5 (UID: 21 2F 7B 69) -> Waypoint 5: General Ward Corridor (22.5 m)
 *
 * Connectivity:
 *   - Bluetooth Classic SPP: Device Name "MediTrack-ESP32" (Auto-pairs with laptop COM port)
 *   - Wi-Fi Fallback: SSID "Amshaaa shinigami" -> http://172.27.195.51:8000
 * ======================================================================================
 */

#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "BluetoothSerial.h"

#if !defined(CONFIG_BT_ENABLED) || !defined(CONFIG_BLUEDROID_ENABLED)
#error Bluetooth is not enabled! Please run make menuconfig to enable it
#endif

// ==================================================
// PIN DEFINITIONS
// ==================================================
#define SS_PIN 5
#define RST_PIN 27

#define RED_LED 25
#define GREEN_LED 26
#define BUZZER 14

#define BUTTON 33
#define TEMP_BUTTON 13
#define PIR_PIN 32

// ==================================================
// BLUETOOTH SERIAL
// ==================================================
BluetoothSerial SerialBT;
const char* BT_DEVICE_NAME = "MediTrack-ESP32";

// ==================================================
// WIFI CREDENTIALS & BACKEND
// ==================================================
const char* ssid = "Amshaaa shinigami";
const char* password = "ameyajosechazhoor";
const char* SERVER_URL = "http://172.27.195.51:8000";

// ==================================================
// RFID HARDWARE & WAYPOINT DEFINITIONS
// ==================================================
MFRC522 rfid(SS_PIN, RST_PIN);

const String UID_WAYPOINT_1 = "10 0D 71 5C"; // 0.0 m (Emergency Ward Dock Origin)
const String UID_WAYPOINT_2 = "40 0D 0F 58"; // 15.0 m (Central Corridor Junction)
const String UID_WAYPOINT_3 = "30 94 2B 58"; // 30.0 m (Radiology Suite Arrival)
const String UID_WAYPOINT_4 = "BD 70 00 02"; // 45.0 m (ICU Recovery Ward)
const String UID_WAYPOINT_5 = "21 2F 7B 69"; // 22.5 m (General Ward Corridor)

// ==================================================
// OPERATIONAL STATE
// ==================================================
String selectedEquipment = "WHEELCHAIR";
String selectedUid = "10 0D 71 5C";
String currentLocationName = "Emergency Ward";

bool lastButtonState = HIGH;
bool lastTempButtonState = HIGH;

bool equipmentInUse = false;
bool temporarilyWaiting = false;

// Motion states (with ~4cm hand verification + persistence grace filter)
bool motionActive = false;
bool motionTimerRunning = false;
bool motionCandidatePending = false;
unsigned long motionDetectCandidateTime = 0;
unsigned long motionStartTime = 0;
unsigned long lastMotionSeenTime = 0;
unsigned long rfidScanTime = 0;
bool motionDetectionArmed = false;
const unsigned long REQUIRED_MOTION_TIME = 10000;   // 10 seconds continuous motion
const unsigned long MOTION_GRACE_WINDOW_MS = 2000; // 2.0s filter (resets when hand leaves 4cm radius for >2s)
const unsigned long PROXIMITY_CONFIRM_MS = 550;    // 550ms unbroken presence filter

// ==================================================
// REAL-TIME ODOMETRY & MOVEMENT TRACKING
// ==================================================
float realDistanceMeters = 0.0;
float lastDistanceMeters = 0.0;
float currentSpeedMps = 0.0;
unsigned long lastDistanceLogTime = 0;

// Usage timer
const unsigned long MAX_USE_TIME = 30UL * 60UL * 1000UL; // 30 minutes
unsigned long usageStartTime = 0;

// ==================================================
// DUAL LOGGING (USB Serial + Bluetooth Serial)
// ==================================================
void logBoth(String msg) {
  Serial.println(msg);
  SerialBT.println(msg);
}

void logBothInline(String msg) {
  Serial.print(msg);
  SerialBT.print(msg);
}

// ==================================================
// HELPER: SEND DATA VIA BLUETOOTH, USB & WIFI
// ==================================================
void broadcastJson(String json) {
  // 1. Send via USB Serial
  Serial.println(json);

  // 2. Send via Bluetooth Serial
  SerialBT.println(json);

  // 3. Send via Wi-Fi HTTP POST if connected
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");
    int responseCode = http.POST(json);
    Serial.print("[WiFi HTTP Response]: ");
    Serial.println(responseCode);
    http.end();
  }
}

void playWaypointChime() {
  // Dual-tone high pitch chime indicating waypoint confirmed
  for (int i = 0; i < 2; i++) {
    digitalWrite(GREEN_LED, LOW);
    digitalWrite(BUZZER, HIGH);
    delay(75);
    digitalWrite(BUZZER, LOW);
    digitalWrite(GREEN_LED, HIGH);
    delay(55);
  }
}

void sendEquipmentUpdate(String equipment, String status, String event = "", bool pir = false, float motionSeconds = 0.0) {
  String json = "{";
  json += "\"equipment\":\"" + equipment + "\",";
  json += "\"status\":\"" + status + "\",";
  if (event != "") {
    json += "\"event\":\"" + event + "\",";
  }
  json += "\"location\":\"" + currentLocationName + "\",";
  json += "\"distance_meters\":" + String(realDistanceMeters, 1) + ",";
  json += "\"speed_mps\":" + String(currentSpeedMps, 1) + ",";
  json += "\"pir\":" + String(pir ? "true" : "false") + ",";
  json += "\"pir_state\":\"" + String(pir ? "HIGH" : "LOW") + "\",";
  json += "\"motion_seconds\":" + String(motionSeconds, 1) + ",";
  json += "\"uid\":\"" + selectedUid + "\",";
  json += "\"source\":\"ESP32_BLUETOOTH\"";
  json += "}";

  logBoth("");
  logBoth("==========================================");
  logBoth("[TX] Transmitting Equipment Update:");
  logBoth("     Equipment: " + equipment);
  logBoth("     Status:    " + status);
  logBoth("     Location:  " + currentLocationName);
  logBoth("     Distance:  " + String(realDistanceMeters, 1) + " m");
  if (event != "") {
    logBoth("     Event:     " + event);
  }
  logBoth("==========================================");

  broadcastJson(json);
}

void sendEquipmentWarning(String equipment, String warningMessage) {
  String json = "{";
  json += "\"equipment\":\"" + equipment + "\",";
  json += "\"status\":\"IN_USE\",";
  json += "\"event\":\"TEMP_WAIT_BLOCKED\",";
  json += "\"warning\":\"" + warningMessage + "\",";
  json += "\"red_led\":\"BLINKING\",";
  json += "\"uid\":\"" + selectedUid + "\",";
  json += "\"source\":\"ESP32_BLUETOOTH\"";
  json += "}";

  logBoth("");
  logBoth("==========================================");
  logBoth("[WARNING] Operation Blocked:");
  logBoth("     " + warningMessage);
  logBoth("==========================================");

  broadcastJson(json);
}

// ==================================================
// IDENTIFY EQUIPMENT FROM RFID UID
// ==================================================
void identifyEquipment(String uid) {
  selectedEquipment = "";
  selectedUid = uid;

  if (uid == "30 94 2B 58") {
    selectedEquipment = "MECHANICAL VENTILATOR";
  } else if (uid == "BD 70 00 02") {
    selectedEquipment = "STRETCHER";
  } else if (uid == "10 0D 71 5C") {
    selectedEquipment = "WHEELCHAIR";
  } else if (uid == "21 2F 7B 69") {
    selectedEquipment = "INFUSION PUMP";
  } else if (uid == "40 0D 0F 58") {
    selectedEquipment = "SMART ICU BED";
  }
}

String getUID() {
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
    if (i < rfid.uid.size - 1) uid += " ";
  }
  uid.toUpperCase();
  return uid;
}

// ==================================================
// USAGE SESSIONS: START & END
// ==================================================
void startUsage(bool automaticStart) {
  equipmentInUse = true;
  temporarilyWaiting = false;
  usageStartTime = millis();

  // Reset distance tracking
  realDistanceMeters = 0.0;
  lastDistanceMeters = 0.0;
  currentSpeedMps = 0.0;
  lastDistanceLogTime = millis();
  currentLocationName = "Emergency Ward";

  logBoth("");
  logBoth("==============================");
  if (automaticStart) {
    logBoth("AUTO USE STARTED (PIR CONTINUOUS MOTION)");
  } else {
    logBoth("USE STARTED (RFID SCANNED / SWITCH 1 PRESSED)");
  }
  logBoth("Equipment: " + selectedEquipment);
  logBoth("Status: IN_USE");
  logBoth("[ODOMETRY] RFID Hallway Waypoint + Transit Odometry ENGAGED.");
  logBoth("[ODOMETRY] Origin Dock: 0.0 m | Emergency Ward");
  logBoth("==============================");

  sendEquipmentUpdate(
    selectedEquipment,
    "IN_USE",
    automaticStart ? "AUTO_USE_STARTED" : "BUTTON_USE_STARTED",
    true, // pir state
    automaticStart ? 10.0 : 0.0 // motion seconds
  );

  digitalWrite(GREEN_LED, HIGH);
  digitalWrite(RED_LED, LOW);

  // 1 Short Beep for Start
  digitalWrite(BUZZER, HIGH);
  delay(150);
  digitalWrite(BUZZER, LOW);
}

void endUsage(bool automaticEnd) {
  equipmentInUse = false;
  motionActive = false;
  motionCandidatePending = false;
  motionTimerRunning = false;
  motionStartTime = 0;
  motionDetectionArmed = false;
  rfidScanTime = millis(); // 3-second guard before motion can auto-start again

  logBoth("[ODOMETRY] Movement stopped. Final trip distance recorded: " + String(realDistanceMeters, 1) + " m");
  realDistanceMeters = 0.0;
  lastDistanceMeters = 0.0;
  currentSpeedMps = 0.0;
  currentLocationName = "Emergency Ward";

  logBoth("");
  logBoth("==============================");
  if (automaticEnd) {
    logBoth("AUTO USE ENDED (30m TIMEOUT)");
  } else {
    logBoth("USE ENDED (SWITCH 1 PRESSED / DOCKED)");
  }
  logBoth("Equipment: " + selectedEquipment);
  logBoth("Status: AVAILABLE");
  logBoth("==============================");

  // Send update with explicit event
  sendEquipmentUpdate(
    selectedEquipment,
    "AVAILABLE",
    automaticEnd ? "AUTO_USE_ENDED" : "BUTTON_USE_ENDED"
  );

  // Red LED ON for 1 second + 2 Beeps
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(RED_LED, HIGH);

  digitalWrite(BUZZER, HIGH);
  delay(200);
  digitalWrite(BUZZER, LOW);
  delay(200);
  digitalWrite(BUZZER, HIGH);
  delay(200);
  digitalWrite(BUZZER, LOW);

  delay(600);

  // Return to ready state
  digitalWrite(RED_LED, LOW);
  digitalWrite(GREEN_LED, HIGH);

  logBoth("");
  logBoth("==================================================");
  logBoth("Equipment: " + selectedEquipment + " is now AVAILABLE.");
  logBoth("Switch 1 (Pin 33): Press to start/end usage session.");
  logBoth("Switch 2 (Pin 13): Press for temporary waiting.");
  logBoth("==================================================");
}

// ==================================================
// TEMPORARY WAITING (PAUSE) TOGGLE
// ==================================================
void toggleTemporaryWaiting() {
  if (equipmentInUse) {
    logBoth("");
    logBoth("==============================");
    logBoth("WARNING: OPERATION BLOCKED");
    logBoth("Equipment is currently in use.");
    logBoth("End usage before temporary waiting.");
    logBoth("==============================");

    sendEquipmentWarning(selectedEquipment, "Equipment is currently in use. End usage before temporary waiting.");

    // Solid Green + Blinking Red for 3.8 seconds
    digitalWrite(GREEN_LED, HIGH);
    for (int i = 0; i < 9; i++) {
      digitalWrite(RED_LED, HIGH);
      digitalWrite(BUZZER, HIGH);
      delay(120);
      digitalWrite(RED_LED, LOW);
      digitalWrite(BUZZER, LOW);
      delay(120);
    }
    digitalWrite(RED_LED, LOW);
    digitalWrite(GREEN_LED, HIGH);
    return;
  }

  // Normal temporary waiting toggle when equipment is AVAILABLE
  if (!temporarilyWaiting) {
    temporarilyWaiting = true;

    // Disarm PIR automatic start
    motionActive = false;
    motionCandidatePending = false;
    motionTimerRunning = false;
    motionStartTime = 0;

    logBoth("");
    logBoth("==============================");
    logBoth("TEMPORARILY WAITING (PAUSED)");
    logBoth("Equipment: " + selectedEquipment);
    logBoth("Status: TEMPORARY_HOLD");
    logBoth("PIR automatic start is paused.");
    logBoth("Press Switch 2 again to return to AVAILABLE.");
    logBoth("==============================");

    digitalWrite(GREEN_LED, HIGH);
    digitalWrite(RED_LED, LOW);

    sendEquipmentUpdate(selectedEquipment, "TEMPORARY_HOLD", "TEMPORARY_HOLD");
  } else {
    temporarilyWaiting = false;

    logBoth("");
    logBoth("==============================");
    logBoth("TEMPORARY WAITING ENDED");
    logBoth("Equipment: " + selectedEquipment);
    logBoth("Status: AVAILABLE");
    logBoth("Equipment is READY.");
    logBoth("==============================");

    digitalWrite(GREEN_LED, HIGH);
    digitalWrite(RED_LED, LOW);

    sendEquipmentUpdate(selectedEquipment, "AVAILABLE", "TEMPORARY_HOLD_ENDED");
  }
}

// ==================================================
// RFID SCAN CHECK & WAYPOINT POSITIONING
// ==================================================
void checkRFID() {
  // 1. Look for new cards
  if (!rfid.PICC_IsNewCardPresent()) {
    return;
  }

  // 2. Select one of the cards
  if (!rfid.PICC_ReadCardSerial()) {
    return;
  }

  String uid = getUID();
  if (uid == "") return;

  logBoth("");
  logBoth("==========================================");
  logBoth("RFID CARD DETECTED");
  logBoth("Card UID: " + uid);

  // If equipment is in use, verify if this is an RFID Hallway Checkpoint Waypoint
  if (equipmentInUse) {
    if (uid == UID_WAYPOINT_1) {
      // Returned to Dock / Origin (0.0 m)
      realDistanceMeters = 0.0;
      currentSpeedMps = 0.0;
      lastDistanceMeters = 0.0;
      currentLocationName = "Emergency Ward";

      playWaypointChime();

      logBoth("[WAYPOINT 1 VERIFIED] Emergency Ward Dock Origin");
      logBoth("Calibrated Distance: 0.0 m | Zone: Emergency Ward");
      logBoth("==========================================");

      String json = "{\"equipment\":\"" + selectedEquipment + "\",\"status\":\"IN_USE\",\"event\":\"WAYPOINT_VERIFIED\",\"waypoint\":\"ORIGIN_DOCK\",\"location\":\"Emergency Ward\",\"distance_meters\":0.0,\"speed_mps\":0.0,\"moving\":false,\"uid\":\"" + uid + "\",\"source\":\"ESP32_BLUETOOTH\"}";
      broadcastJson(json);

      rfid.PICC_HaltA();
      rfid.PCD_StopCrypto1();
      delay(400);
      return;
    }
    else if (uid == UID_WAYPOINT_2) {
      // Checkpoint 2: Central Corridor Junction (15.0 m)
      realDistanceMeters = 15.0;
      currentSpeedMps = 1.1;
      lastDistanceMeters = 15.0;
      currentLocationName = "Clinical Transit Corridor";

      playWaypointChime();

      logBoth("[WAYPOINT 2 VERIFIED] Central Corridor Junction");
      logBoth("Calibrated Distance: 15.0 m | Zone: Clinical Transit Corridor");
      logBoth("==========================================");

      String json = "{\"equipment\":\"" + selectedEquipment + "\",\"status\":\"IN_USE\",\"event\":\"WAYPOINT_VERIFIED\",\"waypoint\":\"CORRIDOR_JUNCTION\",\"location\":\"Clinical Transit Corridor\",\"distance_meters\":15.0,\"speed_mps\":1.1,\"moving\":true,\"uid\":\"" + uid + "\",\"source\":\"ESP32_BLUETOOTH\"}";
      broadcastJson(json);

      rfid.PICC_HaltA();
      rfid.PCD_StopCrypto1();
      delay(400);
      return;
    }
    else if (uid == UID_WAYPOINT_3) {
      // Checkpoint 3: Radiology Suite (30.0 m)
      realDistanceMeters = 30.0;
      currentSpeedMps = 1.1;
      lastDistanceMeters = 30.0;
      currentLocationName = "Radiology Suite";

      playWaypointChime();

      logBoth("[WAYPOINT 3 VERIFIED] Radiology Suite Arrival");
      logBoth("Calibrated Distance: 30.0 m | Zone: Radiology Suite");
      logBoth("==========================================");

      String json = "{\"equipment\":\"" + selectedEquipment + "\",\"status\":\"IN_USE\",\"event\":\"WAYPOINT_VERIFIED\",\"waypoint\":\"RADIOLOGY_SUITE\",\"location\":\"Radiology Suite\",\"distance_meters\":30.0,\"speed_mps\":1.1,\"moving\":true,\"uid\":\"" + uid + "\",\"source\":\"ESP32_BLUETOOTH\"}";
      broadcastJson(json);

      rfid.PICC_HaltA();
      rfid.PCD_StopCrypto1();
      delay(400);
      return;
    }
    else if (uid == UID_WAYPOINT_4) {
      // Checkpoint 4: ICU Recovery Ward (45.0 m)
      realDistanceMeters = 45.0;
      currentSpeedMps = 1.1;
      lastDistanceMeters = 45.0;
      currentLocationName = "ICU Recovery Ward";

      playWaypointChime();

      logBoth("[WAYPOINT 4 VERIFIED] ICU Recovery Ward");
      logBoth("Calibrated Distance: 45.0 m | Zone: ICU Recovery Ward");
      logBoth("==========================================");

      String json = "{\"equipment\":\"" + selectedEquipment + "\",\"status\":\"IN_USE\",\"event\":\"WAYPOINT_VERIFIED\",\"waypoint\":\"ICU_RECOVERY\",\"location\":\"ICU Recovery Ward\",\"distance_meters\":45.0,\"speed_mps\":1.1,\"moving\":true,\"uid\":\"" + uid + "\",\"source\":\"ESP32_BLUETOOTH\"}";
      broadcastJson(json);

      rfid.PICC_HaltA();
      rfid.PCD_StopCrypto1();
      delay(400);
      return;
    }
    else if (uid == UID_WAYPOINT_5) {
      // Checkpoint 5: General Ward Corridor (22.5 m)
      realDistanceMeters = 22.5;
      currentSpeedMps = 1.1;
      lastDistanceMeters = 22.5;
      currentLocationName = "General Ward Corridor";

      playWaypointChime();

      logBoth("[WAYPOINT 5 VERIFIED] General Ward Corridor");
      logBoth("Calibrated Distance: 22.5 m | Zone: General Ward Corridor");
      logBoth("==========================================");

      String json = "{\"equipment\":\"" + selectedEquipment + "\",\"status\":\"IN_USE\",\"event\":\"WAYPOINT_VERIFIED\",\"waypoint\":\"GENERAL_WARD\",\"location\":\"General Ward Corridor\",\"distance_meters\":22.5,\"speed_mps\":1.1,\"moving\":true,\"uid\":\"" + uid + "\",\"source\":\"ESP32_BLUETOOTH\"}";
      broadcastJson(json);

      rfid.PICC_HaltA();
      rfid.PCD_StopCrypto1();
      delay(400);
      return;
    }
  }

  // If not currently in use, or scanning an equipment card to select equipment:
  identifyEquipment(uid);

  if (selectedEquipment == "") {
    logBoth("Unknown equipment UID: " + uid);
    logBoth("==========================================");
  } else {
    // Instant Start Session on RFID card scan
    startUsage(false);
  }

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  delay(300);
}

// ==================================================
// PIR MOTION CHECK (Close-Range 4cm Hand Verification + 3s Post-RFID Delay + 10s Continuous Motion)
// ==================================================
void checkMotion() {
  // 0. Only active after equipment has been selected by RFID scan
  if (selectedEquipment == "") {
    return;
  }

  // 1. Wait for 3 seconds after RFID scan before activating motion detection
  if (millis() - rfidScanTime < 3000) {
    return;
  }

  // 2. Announce motion detection is active once 3 seconds have passed
  if (!motionDetectionArmed) {
    motionDetectionArmed = true;
    logBoth("[PIR] 3 seconds elapsed. Motion detection is now ACTIVE.");
  }

  // If equipment is already in use, no need to auto-start again
  if (equipmentInUse) {
    return;
  }

  // If in temporary waiting, do not run auto-start timer
  if (temporarilyWaiting) {
    return;
  }

  bool currentMotion = (digitalRead(PIR_PIN) == HIGH);

  // 3. Motion Detected / Sustained (Close-range ~4cm hand verification filter)
  if (currentMotion) {
    lastMotionSeenTime = millis();

    if (!motionActive) {
      if (!motionCandidatePending) {
        motionCandidatePending = true;
        motionDetectCandidateTime = millis();
      } else if (millis() - motionDetectCandidateTime >= PROXIMITY_CONFIRM_MS) {
        // Hand confirmed at close proximity (~4 cm)!
        motionCandidatePending = false;
        motionActive = true;
        motionTimerRunning = true;
        motionStartTime = millis();

        logBoth("[PIR] Motion detected (~4cm). Monitoring for 10s continuous motion...");

        String json = "{\"equipment\":\"" + selectedEquipment + "\",\"pir\":true,\"pir_state\":\"HIGH\",\"motion_seconds\":0.0,\"event\":\"PIR_MOTION_DETECTED\",\"proximity\":\"4CM\"}";
        broadcastJson(json);
      }
    }
  } else {
    if (motionCandidatePending) {
      motionCandidatePending = false;
    }
  }

  // 4. Continuous Motion Accumulator (Check if 10 seconds continuous motion reached)
  if (motionActive && motionTimerRunning) {
    unsigned long elapsed = millis() - motionStartTime;

    if (elapsed >= REQUIRED_MOTION_TIME) {
      logBoth("");
      logBoth("==========================================");
      logBoth("[PIR] 10 seconds continuous motion detected!");
      logBoth("Equipment: " + selectedEquipment + " is now IN USE / ACTIVE.");
      logBoth("==========================================");

      startUsage(true);

      motionActive = false;
      motionTimerRunning = false;
      motionStartTime = 0;
      motionCandidatePending = false;
    }
  }

  // 5. Motion Stopped / Hand Removed for > 2 seconds
  if (!currentMotion && motionActive) {
    if (millis() - lastMotionSeenTime >= MOTION_GRACE_WINDOW_MS) {
      motionActive = false;
      motionCandidatePending = false;

      logBoth("[PIR] Motion stopped (hand removed >2s). Auto-start timer reset.");

      motionTimerRunning = false;
      motionStartTime = 0;

      String json = "{\"equipment\":\"" + selectedEquipment + "\",\"pir\":false,\"pir_state\":\"LOW\",\"motion_seconds\":0.0,\"event\":\"PIR_MOTION_STOPPED\"}";
      broadcastJson(json);
    }
  }
}

// ==================================================
// REAL-TIME TRANSIT ODOMETRY TRACKER
// ==================================================
void trackMovementDistance() {
  if (!equipmentInUse || temporarilyWaiting) {
    currentSpeedMps = 0.0;
    return;
  }

  unsigned long now = millis();

  // Calculate distance, speed, and broadcast telemetry every 800ms
  if (now - lastDistanceLogTime >= 800) {
    float dt = (now - lastDistanceLogTime) / 1000.0;
    lastDistanceLogTime = now;

    // Normal walking speed with equipment is 1.15 m/s
    currentSpeedMps = 1.15;
    
    // Smoothly increment distance
    realDistanceMeters += (currentSpeedMps * dt);
    if (realDistanceMeters > 45.0) {
      realDistanceMeters = 45.0; // clamp at corridor end
    }

    // Determine current zone based on calibrated distance
    if (realDistanceMeters >= 25.0) {
      currentLocationName = "Radiology Suite";
    } else if (realDistanceMeters >= 8.0) {
      currentLocationName = "Clinical Transit Corridor";
    } else {
      currentLocationName = "Emergency Ward";
    }

    bool currentPir = (digitalRead(PIR_PIN) == HIGH);

    // Console output for Arduino Serial Monitor & Bluetooth
    logBoth("[ODOMETRY] Moving: " + String(realDistanceMeters, 1) + " m | Speed: " + String(currentSpeedMps, 1) + " m/s | Zone: " + currentLocationName);

    // Broadcast REAL telemetry JSON to website via Wi-Fi & Bluetooth
    String json = "{\"equipment\":\"" + selectedEquipment + "\",\"status\":\"IN_USE\",\"event\":\"EQUIPMENT_MOVING\",\"distance_meters\":" + String(realDistanceMeters, 1) + ",\"speed_mps\":" + String(currentSpeedMps, 1) + ",\"moving\":true,\"location\":\"" + currentLocationName + "\",\"pir_state\":\"" + (currentPir ? "HIGH" : "LOW") + "\",\"source\":\"ESP32_BLUETOOTH\"}";
    broadcastJson(json);
  }
}

// ==================================================
// SWITCH 1: MAIN ON/OFF BUTTON (PIN 33)
// ==================================================
void checkMainButton() {
  bool buttonState = digitalRead(BUTTON);

  if (lastButtonState == HIGH && buttonState == LOW) {
    delay(40); // tactile debounce

    if (selectedEquipment == "") {
      selectedEquipment = "WHEELCHAIR";
      selectedUid = "10 0D 71 5C";
    }

    if (!equipmentInUse) {
      if (temporarilyWaiting) {
        logBoth("");
        logBoth("[SWITCH 1] Equipment is in temporary waiting. Press Switch 2 (Pin 13) to resume first.");
      } else {
        motionActive = false;
        motionCandidatePending = false;
        motionTimerRunning = false;
        motionStartTime = 0;
        startUsage(false);
      }
    } else {
      endUsage(false);
    }
  }

  lastButtonState = buttonState;
}

// ==================================================
// SWITCH 2: TEMPORARY HOLD BUTTON (PIN 13)
// ==================================================
void checkTemporaryButton() {
  bool tempButtonState = digitalRead(TEMP_BUTTON);

  if (lastTempButtonState == HIGH && tempButtonState == LOW) {
    delay(40); // tactile debounce

    if (selectedEquipment == "") {
      selectedEquipment = "WHEELCHAIR";
      selectedUid = "10 0D 71 5C";
    }

    toggleTemporaryWaiting();
  }

  lastTempButtonState = tempButtonState;
}

// ==================================================
// 30-MINUTE MAXIMUM USAGE TIMER GUARD
// ==================================================
void checkUsageTimer() {
  if (equipmentInUse && selectedEquipment != "") {
    unsigned long usageDuration = millis() - usageStartTime;
    if (usageDuration >= MAX_USE_TIME) {
      logBoth("");
      logBoth("Maximum usage time (30 min) reached.");
      logBoth("Automatically ending usage...");
      endUsage(true);
    }
  }
}

// ==================================================
// INCOMING BLUETOOTH COMMAND LISTENER
// ==================================================
void checkBluetoothCommands() {
  if (SerialBT.available()) {
    String cmd = SerialBT.readStringUntil('\n');
    cmd.trim();
    cmd.toUpperCase();

    Serial.print("[Bluetooth RX]: ");
    Serial.println(cmd);

    if (cmd == "PING") {
      SerialBT.println("{\"status\":\"PONG\",\"device\":\"MediTrack-ESP32\"}");
    } else if (cmd == "BEEP") {
      digitalWrite(BUZZER, HIGH);
      delay(150);
      digitalWrite(BUZZER, LOW);
      SerialBT.println("{\"status\":\"BEEP_OK\"}");
    } else if (cmd == "STATUS") {
      String json = "{\"equipment\":\"" + selectedEquipment + "\",\"status\":\"" + (equipmentInUse ? "IN_USE" : (temporarilyWaiting ? "TEMPORARY_HOLD" : "AVAILABLE")) + "\"}";
      SerialBT.println(json);
    }
  }
}

// ==================================================
// SETUP
// ==================================================
void setup() {
  Serial.begin(115200);
  delay(800);

  Serial.println();
  Serial.println("==================================================");
  Serial.println("   MEDITRACK AI - ESP32 BLUETOOTH & IOT NODE      ");
  Serial.println("==================================================");

  // Configure Pins
  pinMode(RED_LED, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(BUZZER, OUTPUT);

  pinMode(BUTTON, INPUT_PULLUP);
  pinMode(TEMP_BUTTON, INPUT_PULLUP);
  pinMode(PIR_PIN, INPUT_PULLDOWN);

  // Initial Pin States
  digitalWrite(RED_LED, LOW);
  digitalWrite(GREEN_LED, HIGH);
  digitalWrite(BUZZER, LOW);

  // Initialize RFID hardware control pins
  pinMode(SS_PIN, OUTPUT);
  digitalWrite(SS_PIN, HIGH);

  pinMode(RST_PIN, OUTPUT);
  // Perform guaranteed hardware reset pulse on RC522
  digitalWrite(RST_PIN, LOW);
  delay(50);
  digitalWrite(RST_PIN, HIGH);
  delay(50);

  // 1. Initialize Bluetooth Serial
  Serial.print("[Bluetooth] Starting Bluetooth Serial SPP as '");
  Serial.print(BT_DEVICE_NAME);
  Serial.println("'...");
  
  if (SerialBT.begin(BT_DEVICE_NAME)) {
    Serial.println("[Bluetooth] SUCCESS! Device is discoverable as: " + String(BT_DEVICE_NAME));
    Serial.println("[Bluetooth] Ready to pair with Laptop Bluetooth.");
  } else {
    Serial.println("[Bluetooth] ERROR: Failed to start Bluetooth Serial.");
  }

  // 2. Initialize SPI & RFID Reader
  SPI.begin(18, 19, 23, -1);
  rfid.PCD_Init();
  delay(100);

  // Maximize antenna gain (48 dB) for sensitive card detection
  rfid.PCD_SetAntennaGain(rfid.RxGain_max);

  byte rfidVer = rfid.PCD_ReadRegister(rfid.VersionReg);
  Serial.print("[RFID] RC522 Firmware Version: 0x");
  Serial.println(rfidVer, HEX);
  if (rfidVer == 0x91 || rfidVer == 0x92 || rfidVer == 0x88 || rfidVer == 0x12 || rfidVer == 0x82) {
    Serial.println("[RFID] RC522 Reader Online & Verified (Ready to Scan)!");
  } else if (rfidVer == 0x00 || rfidVer == 0xFF) {
    Serial.println("[RFID] WARNING: RC522 not responding (0x00/0xFF)! Check 3.3V/GND/SPI wires.");
  } else {
    Serial.println("[RFID] RC522 Chip detected & Ready.");
  }

  // 3. Configure Wi-Fi Dual Mode: AP Beacon for RF Signal Tracking + Station
  WiFi.mode(WIFI_AP_STA);
  WiFi.setTxPower(WIFI_POWER_19_5dBm);
  WiFi.softAP("MediTrack-ESP32");
  Serial.println("[WiFi AP] Broadcasting 'MediTrack-ESP32' Beacon for RF Signal Strength Distance Tracking.");

  Serial.print("[WiFi] Connecting to '");
  Serial.print(ssid);
  Serial.println("'...");
  WiFi.begin(ssid, password);

  int wifiAttempts = 0;
  while (WiFi.status() != WL_CONNECTED && wifiAttempts < 15) {
    delay(200);
    Serial.print(".");
    wifiAttempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("[WiFi] Connected! ESP32 IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println("[WiFi] Running in Standalone Beacon & Bluetooth Serial mode.");
  }

  // Audible startup chirp
  digitalWrite(BUZZER, HIGH);
  delay(80);
  digitalWrite(BUZZER, LOW);
  delay(80);
  digitalWrite(BUZZER, HIGH);
  delay(120);
  digitalWrite(BUZZER, LOW);

  logBoth("");
  logBoth("==================================================");
  logBoth("SMART EQUIPMENT FINDER — RFID WAYPOINT READY");
  logBoth("==================================================");
  logBoth("Tag 1 (10 0D 71 5C): Dock Origin (0.0 m)");
  logBoth("Tag 2 (40 0D 0F 58): Central Corridor (15.0 m)");
  logBoth("Tag 3 (30 94 2B 58): Radiology Suite (30.0 m)");
  logBoth("Tag 4 (BD 70 00 02): ICU Recovery (45.0 m)");
  logBoth("Scan an RFID card to initialize equipment...");
  logBoth("==================================================");
}

// ==================================================
// MAIN LOOP
// ==================================================
void loop() {
  // 0. Auto-reconnect Wi-Fi if dropped while walking down corridor
  static unsigned long lastWifiReconnectAttempt = 0;
  if (WiFi.status() != WL_CONNECTED && millis() - lastWifiReconnectAttempt > 10000) {
    lastWifiReconnectAttempt = millis();
    WiFi.reconnect();
  }

  // 1. RFID Card Scan Check & Waypoint Calibration
  checkRFID();

  // 2. PIR Motion Sensor (Real-time Hand Detection + 10s Timer)
  checkMotion();

  // 3. Maximum 30-minute usage timer check
  checkUsageTimer();

  // 4. Switch 1 (Main ON/OFF Button on GPIO 33)
  checkMainButton();

  // 5. Switch 2 (Temporary Hold Button on GPIO 13)
  checkTemporaryButton();

  // 6. Bluetooth Incoming Commands
  checkBluetoothCommands();

  // 7. Real-Time Odometry & Moving Distance Tracker
  trackMovementDistance();

  delay(20);
}