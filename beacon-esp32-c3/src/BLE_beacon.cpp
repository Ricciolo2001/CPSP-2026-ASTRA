#include <Arduino.h>
#include <NimBLEAddress.h>
#include <NimBLEDevice.h>

void setup()
{
  Serial.begin(115200);
  delay(1000);

  Serial.println("Starting BLE Beacon...");

  NimBLEDevice::init("ASTRA BEACON");
  NimBLEDevice::setPower(ESP_PWR_LVL_P9);

  NimBLEAdvertising *pAdvertising = NimBLEDevice::getAdvertising();
  pAdvertising->start();

  NimBLEAddress addr = NimBLEDevice::getAddress();
  Serial.print("Beacon MAC Address: ");
  Serial.println(addr.toString().c_str());

  delay(1000);
  Serial.println("Beacon active.");
}

void loop()
{
  delay(1000);
}
