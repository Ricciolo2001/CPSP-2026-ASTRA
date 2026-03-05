#include "driver/uart.h"
#include "cJSON.h"

#include <Arduino.h>
#include <stdlib.h>
#include <stdio.h>

#include "Struct/BLE_device.h"
#include "Struct/UART_task_param.h"
#include "BLE_manager.h"

#define TXD_PIN (5)                  // UART TX pin
#define RXD_PIN (6)                  // UART RX pin
#define RTS_PIN (UART_PIN_NO_CHANGE) // UART RTS pin (not used)
#define CTS_PIN (UART_PIN_NO_CHANGE) // UART CTS pin (not used)

#define BUF_SIZE (1024)
#define RECIEVER_TASK_STACK_SIZE (BUF_SIZE * 2) // Remembre to increase this if you want to receive bigger messages

void uart_reciever_task(void *arg);