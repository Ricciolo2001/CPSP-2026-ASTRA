#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "driver/uart.h"

void app_main(void) {
  // Print all UART1 data to the console for debugging
  const int uart_num = UART_NUM_1;
  const int buf_size = 1024;
  uint8_t *data = (uint8_t *)malloc(buf_size);

  uart_config_t uart_config = {.baud_rate = 115200,
                               .data_bits = UART_DATA_8_BITS,
                               .parity = UART_PARITY_DISABLE,
                               .stop_bits = UART_STOP_BITS_1,
                               .flow_ctrl = UART_HW_FLOWCTRL_DISABLE};

  uart_param_config(uart_num, &uart_config);
  uart_set_pin(uart_num, 5, 6, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
  uart_driver_install(uart_num, buf_size * 2, 0, 0, NULL, 0);

  while (true) {
    int len = uart_read_bytes(uart_num, data, buf_size, pdMS_TO_TICKS(100));
    if (len > 0) {
      printf("Received %d bytes: ", len);
      for (int i = 0; i < len; i++) {
        printf("%02X ", data[i]);
      }
      printf("\n");
    }
  }
}
