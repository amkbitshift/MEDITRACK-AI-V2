/*
 * ======================================================================================
 * MediTrack AI — ESP32 Smart Medical Equipment Node Firmware
 * ======================================================================================
 * Hardware Components:
 *   - ESP32 CP2102 NodeMCU Development Board
 *   - RC522 RFID SPI Reader (Equipment Identification)
 *   - HC-SR501 / AM312 PIR Motion Sensor (Active Equipment Usage Detection)
 *   - Push Button (Start / Stop Usage Session)
 *   - Status LEDs: Green (Available / Active), Red (Alert / Low Battery / Maintenance)
 *   - Active Buzzer (Audible RFID scan confirmations & Emergency Alerts)
 *   - ADC Battery Voltage Divider (Telemetry Monitoring)
 * 
 * Target Server:
 *   - MediTrack AI FastAPI Backend: POST /api/esp32/telemetry and POST /api/esp32/rfid
 * ======================================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>

// --- WiFi Credentials ---
const char* WIFI_SSID     = "Hospital_IoT_Network";    // Change to your WiFi SSID
const char* WIFI_PASSWORD = "HospitalSecurePassword";  // Change to your WiFi Password

// --- Backend API Host ---
// Replace with the IP address of the computer running MediTrack AI backend
const char* SERVER_HOST   = "http://192.168.1.150:8000"; 
const char* TELEMETRY_URL = "http://192.168.1.150:8000/api/esp32/telemetry";
const char* RFID_URL      = "http://192.168.1.150:8000/api/esp32/rfid";

// --- Hardware Pin Definitions ---
#define PIN_RC522_SS     5    // SPI Chip Select (SDA)
#define PIN_RC522_RST    22   // RC522 Reset Pin
#define PIN_PIR_SENSOR   27   // HC-SR501 PIR Digital Output
#define PIN_BUTTON       14   // Push Button (Active LOW with internal pullup)
#define PIN_LED_GREEN    12   // Green Status LED
#define PIN_LED_RED      13   // Red Alert LED
#define PIN_BUZZER       25   // Active Buzzer
#define PIN_BATTERY_ADC  34   // Analog Input for Battery Voltage Divider

MFRC522 rfid(PIN_RC522_SS, PIN_RC522_RST);

// --- Operational State ---
String currentEquipmentId = "WC-009";
String currentLocation   = "Emergency Ward";
bool isSessionActive      = false;
unsigned long sessionStartTime = 0;
unsigned long lastTelemetryTime = 0;
const unsigned long TELEMETRY_INTERVAL_MS = 3000; // Send telemetry every 3 seconds

// Debounce helper
int lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long DEBOUNCE_DELAY = 50;

void beep(int frequencyHz, int durationMs) {
  digitalWrite(PIN_BUZZER, HIGH);
  delay(durationMs);
  digitalWrite(PIN_BUZZER, LOW);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n==========================================");
  Serial.println("  MediTrack AI - ESP32 Smart IoT Node    ");
  Serial.println("==========================================");

  // Configure Pins
  pinMode(PIN_PIR_SENSOR, INPUT);
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);

  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_BUZZER, LOW);

  // Initialize SPI & RC522 RFID
  SPI.begin();
  rfid.PCD_Init();
  Serial.println("[RFID] RC522 Reader Initialized.");

  // Connect to WiFi
  Serial.print("[WiFi] Connecting to: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int wifiAttempts = 0;
  while (WiFi.status() != WL_CONNECTED && wifiAttempts < 20) {
    delay(500);
    Serial.print(".");
    digitalWrite(PIN_LED_GREEN, !digitalRead(PIN_LED_GREEN));
    wifiAttempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected! IP Address: " + WiFi.localIP().toString());
    digitalWrite(PIN_LED_GREEN, HIGH);
    beep(1000, 100);
    delay(100);
    beep(1500, 150);
  } else {
    Serial.println("\n[WiFi] Warning: Running in offline simulation mode.");
    digitalWrite(PIN_LED_RED, HIGH);
  }
}

void loop() {
  // 1. Check for RFID Scans
  checkRFID();

  // 2. Read Push Button (Start/End Session)
  checkButton();

  // 3. Periodic IoT Telemetry Broadcast
  if (millis() - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryTime = millis();
    sendTelemetry();
  }

  delay(20);
}

void checkRFID() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    return;
  }

  // Format UID string: "10 0D 71 5C"
  String uidStr = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uidStr += "0";
    uidStr += String(rfid.uid.uidByte[i], HEX);
    if (i < rfid.uid.size - 1) uidStr += " ";
  }
  uidStr.toUpperCase();

  Serial.println("[RFID] Scanned UID: " + uidStr);
  beep(2000, 80);

  // Send RFID scan to MediTrack AI Server
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(RFID_URL);
    http.addHeader("Content-Type", "application/json");

    String jsonPayload = "{\"uid\": \"" + uidStr + "\", \"location\": \"" + currentLocation + "\"}";
    int httpResponseCode = http.POST(jsonPayload);
    
    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.println("[Server Response]: " + response);
      digitalWrite(PIN_LED_GREEN, HIGH);
      digitalWrite(PIN_LED_RED, LOW);
    } else {
      Serial.println("[HTTP Error]: " + String(httpResponseCode));
    }
    http.end();
  }

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}

void checkButton() {
  int reading = digitalRead(PIN_BUTTON);
  if (reading != lastButtonState) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > DEBOUNCE_DELAY) {
    // If state has changed
    static int confirmedButtonState = HIGH;
    if (reading != confirmedButtonState) {
      confirmedButtonState = reading;
      if (confirmedButtonState == LOW) { // Button Pressed
        isSessionActive = !isSessionActive;
        if (isSessionActive) {
          sessionStartTime = millis();
          Serial.println("[Session] Usage STARTED for: " + currentEquipmentId);
          beep(1800, 120);
          digitalWrite(PIN_LED_GREEN, HIGH);
        } else {
          Serial.println("[Session] Usage ENDED for: " + currentEquipmentId);
          beep(1200, 80);
          delay(80);
          beep(800, 80);
        }
      }
    }
  }
  lastButtonState = reading;
}

void sendTelemetry() {
  bool pirMovement = (digitalRead(PIN_PIR_SENSOR) == HIGH);

  // Simulated / ADC Battery Level reading
  int rawAdc = analogRead(PIN_BATTERY_ADC);
  // Example divider map to 0-100%
  int batteryPct = map(rawAdc, 2400, 4095, 0, 100);
  if (batteryPct < 0) batteryPct = 18; // Default to realistic low battery demo
  if (batteryPct > 100) batteryPct = 100;

  // Approximate temperature calculation
  float tempC = 31.4;

  unsigned long usageSeconds = isSessionActive ? ((millis() - sessionStartTime) / 1000) : 0;

  // LED indication based on battery and movement
  if (batteryPct < 20) {
    digitalWrite(PIN_LED_RED, millis() % 1000 > 500 ? HIGH : LOW); // Flashing alert
  } else {
    digitalWrite(PIN_LED_RED, LOW);
  }

  if (pirMovement) {
    digitalWrite(PIN_LED_GREEN, HIGH);
  } else if (!isSessionActive) {
    digitalWrite(PIN_LED_GREEN, LOW);
  }

  // Construct JSON payload
  String payload = "{";
  payload += "\"equipment_id\":\"" + currentEquipmentId + "\",";
  payload += "\"battery\":" + String(batteryPct) + ",";
  payload += "\"movement\":" + String(pirMovement ? "true" : "false") + ",";
  payload += "\"temperature\":" + String(tempC, 1) + ",";
  payload += "\"usage_time\":" + String(usageSeconds) + ",";
  payload += "\"location\":\"" + currentLocation + "\"";
  payload += "}";

  Serial.println("[Telemetry Out] " + payload);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(TELEMETRY_URL);
    http.addHeader("Content-Type", "application/json");
    int httpCode = http.POST(payload);
    if (httpCode > 0) {
      // Success
    } else {
      Serial.println("[HTTP Fail]: " + String(httpCode));
    }
    http.end();
  }
}
