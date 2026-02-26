#include <stdbool.h>
#include <stdint.h>

#include "app.h"

#include "FreeRTOS.h" // IWYU pragma: keep
#include "task.h"

#define DEBUG_MODULE "HELLOWORLD"
#include "debug.h"

void appMain() {
  DEBUG_PRINT("Waiting for activation ...\n");

  while (1) {
    vTaskDelay(M2T(2000));
    DEBUG_PRINT("Hello World!\n");
  }
}
