#include <Arduino.h>
#include <unity.h>
#include "UartEchoTest.h"

UartEchoTest echo;

void test_uart_echo() {
    const char *msg = "HELLO";
    echo.send(msg);

    // Simula lettura e echo
    int len = echo.process();
    TEST_ASSERT_EQUAL(strlen(msg), len);
}

void setup() {
    Serial.begin(115200);
    echo.begin();
    UNITY_BEGIN();
    RUN_TEST(test_uart_echo);
    UNITY_END();
}

void loop() {
}