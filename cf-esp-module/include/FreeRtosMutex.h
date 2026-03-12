#pragma once

#include <stdexcept>

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

class FreeRtosMutex {
  public:
    explicit FreeRtosMutex() : mutex_(xSemaphoreCreateMutex()) {
        if (mutex_ == nullptr) {
            throw std::runtime_error("Failed to create FreeRTOS mutex");
        }
    }

    ~FreeRtosMutex() {
        if (mutex_ != nullptr) {
            vSemaphoreDelete(mutex_);
        }
    }

    // Disable copying
    FreeRtosMutex(const FreeRtosMutex &) = delete;
    FreeRtosMutex &operator=(const FreeRtosMutex &) = delete;

    // Blocks until the mutex is obtained
    void lock() { xSemaphoreTake(mutex_, portMAX_DELAY); }

    void unlock() {
        if (xSemaphoreGive(mutex_)) {
            ESP_LOGW(
                "FreeRtosMutex",
                "Unlocking a mutex that was not locked or already unlocked");
        }
    }

    bool try_lock() { return xSemaphoreTake(mutex_, 0) == pdTRUE; }

  private:
    SemaphoreHandle_t mutex_;
};
