#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN 5
#define RST_PIN 27

MFRC522 rfid(SS_PIN, RST_PIN);

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n\n==========================================");
  Serial.println("  RC522 LIVE CARD DETECTION TEST");
  Serial.println("==========================================");

  // Configure RST & SS explicitly
  pinMode(SS_PIN, OUTPUT);
  digitalWrite(SS_PIN, HIGH);

  pinMode(RST_PIN, OUTPUT);
  digitalWrite(RST_PIN, LOW);
  delay(50);
  digitalWrite(RST_PIN, HIGH);
  delay(50);

  SPI.begin(18, 19, 23, -1);
  rfid.PCD_Init();
  delay(100);

  // Maximize antenna sensitivity
  rfid.PCD_SetAntennaGain(rfid.RxGain_max);

  byte ver = rfid.PCD_ReadRegister(rfid.VersionReg);
  Serial.print("RC522 Version: 0x");
  Serial.println(ver, HEX);
  Serial.println("Antenna Gain: MAX");
  Serial.println("Waiting for RFID card to be placed near reader...");
  Serial.println("==========================================");
}

void loop() {
  // Check if a new card is present
  if (!rfid.PICC_IsNewCardPresent()) {
    delay(50);
    return;
  }

  // Read card serial
  if (!rfid.PICC_ReadCardSerial()) {
    delay(50);
    return;
  }

  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
    if (i < rfid.uid.size - 1) uid += " ";
  }
  uid.toUpperCase();

  Serial.println(">>> CARD DETECTED! UID: " + uid);

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  delay(500);
}
