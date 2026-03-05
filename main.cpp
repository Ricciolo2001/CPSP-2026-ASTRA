#include <Arduino.h>
#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "sdkconfig.h"
#include "BLEManager.h"

// !================================================

/**
 * This is an example which echos any data it receives on configured UART back to the sender,
 * with hardware flow control turned off. It does not use UART driver event queue.
 *
 * - Port: configured UART
 * - Receive (Rx) buffer: on
 * - Transmit (Tx) buffer: off
 * - Flow control: off
 * - Event queue: off
 * - Pin assignment: see defines below (See Kconfig)
 */

// !================================================

#define TXD_PIN (4)                  // UART TX pin
#define RXD_PIN (5)                  // UART RX pin
#define RTS_PIN (UART_PIN_NO_CHANGE) // UART RTS pin (not used)
#define CTS_PIN (UART_PIN_NO_CHANGE) // UART CTS pin (not used)

#define UART_PORT_NUM (UART_NUM_1)
#define UART_BAUD_RATE (115000)
#define BUF_SIZE (1024)
#define RECIEVER_TASK_STACK_SIZE (BUF_SIZE * 2) // Remembre to increase this if you want to receive bigger messages

static void uart_reciever_task(void *arg)
{
  Serial.println("UART receiver task beguin creation.");

  /* Configure parameters of an UART driver, communication pins and install the driver */
  uart_config_t uart_config = {
      .baud_rate = UART_BAUD_RATE,
      .data_bits = UART_DATA_8_BITS,
      .parity = UART_PARITY_DISABLE,
      .stop_bits = UART_STOP_BITS_1,
      .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
      // .source_clk = UART_SCLK_APB,
  };
  int intr_alloc_flags = 0;

  Serial.println("UART configuration complete, installing driver.");

#if CONFIG_UART_ISR_IN_IRAM
  intr_alloc_flags = ESP_INTR_FLAG_IRAM;
#endif

  ESP_ERROR_CHECK(uart_driver_install(UART_PORT_NUM, BUF_SIZE * 2, 0, 0, NULL, intr_alloc_flags));
  ESP_ERROR_CHECK(uart_param_config(UART_PORT_NUM, &uart_config));
  ESP_ERROR_CHECK(uart_set_pin(UART_PORT_NUM, TXD_PIN, RXD_PIN, RTS_PIN, CTS_PIN));

  Serial.println("UART driver installed, starting to receive data.");

  // Configure a temporary buffer for the incoming data
  uint8_t *data = (uint8_t *)malloc(BUF_SIZE);

  while (true)
  {
    // Read data from the UART
    int len = uart_read_bytes(UART_PORT_NUM, data, BUF_SIZE, 20 / portTICK_RATE_MS);
    if (len > 0)
    {
      // Null-terminate the received data
      data[len] = '\0';
      Serial.printf("Received %d bytes: '%s'\n", len, (char *)data);
      if (strcmp((char *)data, "LED ON") == 0) {
        digitalWrite(BUILTIN_LED, LOW); // Turn on the LED
        Serial.println("LED turned ON");
      } else if (strcmp((char *)data, "LED OFF") == 0) {
        digitalWrite(BUILTIN_LED, HIGH); // Turn off the LED
        Serial.println("LED turned OFF");
      }
      else {
        Serial.println("Unknown command received.");
      }
    }
  }
}

// =================================================

BleManager ble;

void setup()
{
  Serial.begin(115200);
  delay(500); // Better safe than sorry?
  Serial.println("Serial communication setup complete.");

  ble.init();
  Serial.println("BLE Manager initialized.");

  pinMode(BUILTIN_LED, OUTPUT);
  digitalWrite(BUILTIN_LED, HIGH); // LOW turns the LED on, HIGH turns it off like who designed that?
}

void loop()
{
  xTaskCreate(uart_reciever_task, "uart_reciever_task", RECIEVER_TASK_STACK_SIZE, NULL, 10, NULL);
}