// This code is mounted on a BLE beacon used for testing

#include <Arduino.h> // Serve solo se si usa platform IO
#include <NimBLEDevice.h>  // Lightweight BLE library for esp32-C3

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("Starting BLE Beacon...");

  pinMode(8, OUTPUT);
  digitalWrite(8, HIGH);
  delay(100);

  NimBLEDevice::init("BLE_Beacon");
  NimBLEDevice::setPower(ESP_PWR_LVL_P9); 

  NimBLEAdvertising* pAdvertising = NimBLEDevice::getAdvertising();
  pAdvertising->start();

  delay(1000);
  Serial.println("Beacon active.");
}

void loop() {
  digitalWrite(8, LOW);
  delay(150);
  digitalWrite(8, HIGH);
  delay(1250);
}
