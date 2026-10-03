#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <HTTPClient.h>

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
// WIFI
// ==================================================

const char* ssid = "Amshaaa shinigami";
const char* password = "ameyajosechazhoor";

const char* SERVER_URL = "http://172.27.195.51:8000";

// ==================================================
// RFID
// ==================================================

MFRC522 rfid(SS_PIN, RST_PIN);


// ==================================================
// VARIABLES
// ==================================================

String selectedEquipment = "";

bool lastButtonState = HIGH;
bool lastTempButtonState = HIGH;

bool equipmentInUse = false;

bool temporarilyWaiting = false;


// ==================================================
// USAGE TIMER
// ==================================================

const unsigned long MAX_USE_TIME =
  30UL * 60UL * 1000UL;

unsigned long usageStartTime = 0;


// ==================================================
// MOTION TIMER
// ==================================================

bool motionTimerRunning = false;

unsigned long motionStartTime = 0;

const unsigned long REQUIRED_MOTION_TIME = 10000;


// ==================================================
// SETUP
// ==================================================

void setup() {

  Serial.begin(115200);

  delay(1000);

// ------------------------------------------------
// WIFI CONNECTION
// ------------------------------------------------

WiFi.begin(ssid, password);

Serial.print("Connecting to WiFi");

while (WiFi.status() != WL_CONNECTED) {
  delay(500);
  Serial.print(".");
}

Serial.println();
Serial.println("WiFi connected!");
Serial.print("ESP32 IP: ");
Serial.println(WiFi.localIP());
  // ------------------------------------------------
  // OUTPUTS
  // ------------------------------------------------

  pinMode(RED_LED, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(BUZZER, OUTPUT);


  // ------------------------------------------------
  // INPUTS
  // ------------------------------------------------

  pinMode(BUTTON, INPUT_PULLUP);

  pinMode(TEMP_BUTTON, INPUT_PULLUP);

  pinMode(PIR_PIN, INPUT);


  // ------------------------------------------------
  // INITIAL STATE
  // ------------------------------------------------

  digitalWrite(RED_LED, LOW);

  digitalWrite(GREEN_LED, HIGH);

  digitalWrite(BUZZER, LOW);


  // ------------------------------------------------
  // RFID
  // ------------------------------------------------

  SPI.begin(18, 19, 23, 5);

  rfid.PCD_Init();

  delay(100);


  // ------------------------------------------------
  // START MESSAGE
  // ------------------------------------------------

  Serial.println();
  Serial.println("==============================");
  Serial.println("   SMART EQUIPMENT FINDER");
  Serial.println("==============================");

  Serial.println();
  Serial.println("RFID + PIR + 2 BUTTONS");

  Serial.println();

  Serial.println("RC522 ready.");

  Serial.println("Scan an RFID card...");
}


// ==================================================
// GET RFID UID
// ==================================================

String getUID() {

  String uid = "";

  for (byte i = 0; i < rfid.uid.size; i++) {

    if (rfid.uid.uidByte[i] < 0x10) {
      uid += "0";
    }

    uid += String(
      rfid.uid.uidByte[i],
      HEX
    );

    if (i < rfid.uid.size - 1) {
      uid += " ";
    }
  }

  uid.toUpperCase();

  return uid;
}

// ==================================================
// SEND EQUIPMENT DATA TO WEBSITE
// ==================================================

void sendEquipmentUpdate(String equipment, String status) {

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected!");
    return;
  }

  HTTPClient http;

  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  String json = "{";
  json += "\"equipment\":\"" + equipment + "\",";
  json += "\"status\":\"" + status + "\"";
  json += "}";

  Serial.println("Sending to website:");
  Serial.println(json);

  int responseCode = http.POST(json);

  Serial.print("Server response: ");
  Serial.println(responseCode);

  http.end();
}

// ==================================================
// SEND EQUIPMENT WARNING TO WEBSITE
// ==================================================

void sendEquipmentWarning(String equipment, String warningMessage) {

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected!");
    return;
  }

  HTTPClient http;

  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  String json = "{";
  json += "\"equipment\":\"" + equipment + "\",";
  json += "\"status\":\"IN_USE\",";
  json += "\"event\":\"TEMP_WAIT_BLOCKED\",";
  json += "\"warning\":\"" + warningMessage + "\",";
  json += "\"red_led\":\"BLINKING\"";
  json += "}";

  Serial.println("Sending to website:");
  Serial.println(json);

  int responseCode = http.POST(json);

  Serial.print("Server response: ");
  Serial.println(responseCode);

  http.end();
}

// ==================================================
// IDENTIFY EQUIPMENT
// ==================================================

void identifyEquipment(String uid) {

  selectedEquipment = "";


  if (uid == "30 94 2B 58") {

    selectedEquipment = "MECHANICAL VENTILATOR";
  }

  else if (uid == "BD 70 00 02") {

    selectedEquipment = "STRETCHER";
  }

  else if (uid == "10 0D 71 5C") {

    selectedEquipment = "WHEELCHAIR";
  }

  else if (uid == "21 2F 7B 69") {

    selectedEquipment = "INFUSION PUMP";
  }

  else if (uid == "40 0D 0F 58") {

    selectedEquipment =
      "SMART ICU BED";
  }
}


// ==================================================
// RFID CHECK
// ==================================================

void checkRFID() {

  if (!rfid.PICC_IsNewCardPresent()) {
    return;
  }


  if (!rfid.PICC_ReadCardSerial()) {
    return;
  }


  String uid = getUID();


  Serial.println();
  Serial.println("==============================");

  Serial.println("RFID CARD DETECTED");

  Serial.print("Card UID: ");
  Serial.println(uid);


  identifyEquipment(uid);


  // ------------------------------------------------
  // UNKNOWN CARD
  // ------------------------------------------------

  if (selectedEquipment == "") {

    Serial.println("Unknown equipment.");
  }


  // ------------------------------------------------
  // EQUIPMENT FOUND
  // ------------------------------------------------

  else {

    equipmentInUse = false;

    temporarilyWaiting = false;

    motionTimerRunning = false;

    motionStartTime = 0;


    Serial.println();

    Serial.print("Equipment selected: ");
    Serial.println(selectedEquipment);

    Serial.println(
      "Waiting for button or motion..."
    );
    // SEND TO WEBSITE
sendEquipmentUpdate(selectedEquipment, "AVAILABLE");

    digitalWrite(GREEN_LED, HIGH);
    digitalWrite(RED_LED, LOW);
  }


  Serial.println(
    "=============================="
  );


  rfid.PICC_HaltA();

  rfid.PCD_StopCrypto1();

  delay(300);
}


// ==================================================
// START USAGE
// ==================================================

void startUsage(bool automaticStart) {

  equipmentInUse = true;

  temporarilyWaiting = false;

  usageStartTime = millis();


  Serial.println();

  Serial.println("==============================");


  if (automaticStart) {

    Serial.println("AUTO USE STARTED");
  }

  else {

    Serial.println("USE STARTED");
  }


  Serial.print("Equipment: ");
  Serial.println(selectedEquipment);

  sendEquipmentUpdate(selectedEquipment, "IN_USE");


  Serial.println(
    "=============================="
  );


  // GREEN LED

  digitalWrite(GREEN_LED, HIGH);
  digitalWrite(RED_LED, LOW);


  // BUZZER

  digitalWrite(BUZZER, HIGH);

  delay(300);

  digitalWrite(BUZZER, LOW);


  Serial.println(
    "PIR monitoring is active."
  );

  Serial.println(
    "Maximum usage time: 30 minutes."
  );
}


// ==================================================
// END USAGE
// ==================================================

void endUsage(bool automaticEnd) {

  equipmentInUse = false;


  Serial.println();

  Serial.println("==============================");


  if (automaticEnd) {

    Serial.println("AUTO USE ENDED");
  }

  else {

    Serial.println("USE ENDED");
  }


  Serial.print("Equipment: ");
  Serial.println(selectedEquipment);

  sendEquipmentUpdate(selectedEquipment, "AVAILABLE");


  Serial.println(
    "=============================="
  );


  // RED LED

  digitalWrite(GREEN_LED, LOW);
  digitalWrite(RED_LED, HIGH);


  // TWO BEEPS

  digitalWrite(BUZZER, HIGH);

  delay(200);

  digitalWrite(BUZZER, LOW);

  delay(200);

  digitalWrite(BUZZER, HIGH);

  delay(200);

  digitalWrite(BUZZER, LOW);


  delay(1000);


  // READY

  digitalWrite(RED_LED, LOW);
  digitalWrite(GREEN_LED, HIGH);


  Serial.println();

  Serial.println(
    "Equipment is ready."
  );

  Serial.println(
    "Waiting for next activity..."
  );
}


// ==================================================
// TEMPORARILY WAITING
// ==================================================

void toggleTemporaryWaiting() {

  if (selectedEquipment == "") {

    Serial.println();

    Serial.println(
      "Please scan an RFID card first."
    );

    return;
  }


  // Don't allow temporary waiting
  // while equipment is already in use

  if (equipmentInUse) {

    Serial.println();

    Serial.println(
      "Equipment is currently in use."
    );

    Serial.println(
      "End usage before temporary waiting."
    );

    // Hardware Red LED blinking alert (3 rapid blinks)
    for (int i = 0; i < 3; i++) {
      digitalWrite(RED_LED, HIGH);
      delay(150);
      digitalWrite(RED_LED, LOW);
      delay(150);
    }

    // Keep Green LED ON since equipment is still in clinical use
    digitalWrite(GREEN_LED, HIGH);

    // Notify website so virtual twin and website serial monitor reflect this live
    sendEquipmentWarning(
      selectedEquipment,
      "Equipment is currently in use. End usage before temporary waiting."
    );

    return;
  }


  // ------------------------------------------------
  // ENTER TEMPORARY WAITING
  // ------------------------------------------------

  if (!temporarilyWaiting) {

    temporarilyWaiting = true;

    motionTimerRunning = false;

    motionStartTime = 0;


    Serial.println();

    Serial.println("==============================");

    Serial.println(
      "TEMPORARILY WAITING"
    );

    Serial.print("Equipment: ");

    Serial.println(
      selectedEquipment
    );

    Serial.println(
      "PIR automatic start is paused."
    );

    Serial.println(
      "Press temporary button again to return."
    );

    Serial.println(
      "=============================="
    );


    // Green LED stays ON

    digitalWrite(GREEN_LED, HIGH);

    digitalWrite(RED_LED, LOW);
  }


  // ------------------------------------------------
  // EXIT TEMPORARY WAITING
  // ------------------------------------------------

  else {

    temporarilyWaiting = false;


    Serial.println();

    Serial.println(
      "TEMPORARY WAITING ENDED"
    );

    Serial.print("Equipment: ");

    Serial.println(
      selectedEquipment
    );

    Serial.println(
      "Equipment is READY."
    );


    digitalWrite(GREEN_LED, HIGH);

    digitalWrite(RED_LED, LOW);
  }
}


// ==================================================
// CHECK MOTION
// ==================================================

void checkMotion() {

  bool motionState =
    digitalRead(PIR_PIN);


  // ------------------------------------------------
  // NO EQUIPMENT
  // ------------------------------------------------

  if (selectedEquipment == "") {

    motionTimerRunning = false;

    motionStartTime = 0;

    return;
  }


  // ------------------------------------------------
  // TEMPORARILY WAITING
  // ------------------------------------------------

  if (temporarilyWaiting) {

    // Ignore PIR automatic start

    motionTimerRunning = false;

    motionStartTime = 0;

    return;
  }


  // ------------------------------------------------
  // EQUIPMENT IN USE
  // ------------------------------------------------

  if (equipmentInUse) {

    return;
  }


  // ------------------------------------------------
  // EQUIPMENT READY
  // ------------------------------------------------

  if (motionState == HIGH) {


    // Start timer

    if (!motionTimerRunning) {

      motionTimerRunning = true;

      motionStartTime = millis();


      Serial.println();

      Serial.println(
        "MOTION DETECTED!"
      );

      Serial.println(
        "Continuous motion required for 10 seconds..."
      );
    }


    // Check 10 seconds

    if (
      motionTimerRunning &&
      millis() - motionStartTime >=
      REQUIRED_MOTION_TIME
    ) {

      Serial.println();

      Serial.println(
        "10 seconds continuous motion detected!"
      );

      Serial.println(
        "Starting usage automatically..."
      );


      startUsage(true);


      motionTimerRunning = false;

      motionStartTime = 0;
    }
  }


  // ------------------------------------------------
  // MOTION STOPPED
  // ------------------------------------------------

  else {

    if (motionTimerRunning) {

      Serial.println();

      Serial.println(
        "Motion stopped."
      );

      Serial.println(
        "10-second timer reset."
      );
    }


    motionTimerRunning = false;

    motionStartTime = 0;
  }
}


// ==================================================
// SWITCH 1
// ON/OFF / START-END
// ==================================================

void checkMainButton() {

  bool buttonState =
    digitalRead(BUTTON);


  // Button just pressed

  if (
    lastButtonState == HIGH &&
    buttonState == LOW
  ) {


    // No equipment

    if (selectedEquipment == "") {

      Serial.println();

      Serial.println(
        "Please scan an RFID card first."
      );
    }


    // Start usage

    else if (!equipmentInUse) {

      if (temporarilyWaiting) {

        Serial.println();

        Serial.println(
          "Equipment is temporarily waiting."
        );

        Serial.println(
          "Cancel temporary waiting first."
        );
      }

      else {

        motionTimerRunning = false;

        motionStartTime = 0;

        startUsage(false);
      }
    }


    // End usage

    else {

      endUsage(false);
    }
  }


  lastButtonState =
    buttonState;
}


// ==================================================
// SWITCH 2
// TEMPORARILY WAITING
// ==================================================

void checkTemporaryButton() {

  bool tempButtonState =
    digitalRead(TEMP_BUTTON);


  // Button just pressed

  if (
    lastTempButtonState == HIGH &&
    tempButtonState == LOW
  ) {

    toggleTemporaryWaiting();
  }


  lastTempButtonState =
    tempButtonState;
}


// ==================================================
// MAXIMUM USAGE TIMER
// ==================================================

void checkUsageTimer() {

  if (
    equipmentInUse &&
    selectedEquipment != ""
  ) {

    unsigned long usageDuration =
      millis() - usageStartTime;


    if (
      usageDuration >=
      MAX_USE_TIME
    ) {

      Serial.println();

      Serial.println(
        "Maximum usage time reached."
      );

      Serial.println(
        "Automatically ending usage..."
      );


      endUsage(true);
    }
  }
}


// ==================================================
// MAIN LOOP
// ==================================================

void loop() {

  // 1. RFID

  checkRFID();


  // 2. PIR

  checkMotion();


  // 3. Maximum usage timer

  checkUsageTimer();


  // 4. Main ON/OFF switch

  checkMainButton();


  // 5. Temporary waiting switch

  checkTemporaryButton();


  delay(10);
}