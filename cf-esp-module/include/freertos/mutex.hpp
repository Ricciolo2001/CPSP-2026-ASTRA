#pragma once

#include <stdexcept>
#include <chrono>

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

namespace freertos {

class Mutex {
  public:
    inline explicit Mutex() : mutex_(xSemaphoreCreateMutex()) {
        if (mutex_ == nullptr) {
            throw std::runtime_error("Failed to create FreeRTOS mutex");
        }
    }

    inline ~Mutex() {
        if (mutex_ != nullptr) {
            vSemaphoreDelete(mutex_);
        }
    }

    // Disable copying
    Mutex(const Mutex &) = delete;
    Mutex &operator=(const Mutex &) = delete;

    inline void lock(TickType_t timeout) {
        if (xSemaphoreTake(mutex_, timeout) != pdTRUE) {
            throw std::runtime_error(
                "Failed to acquire FreeRTOS mutex within timeout");
        }
    }
    inline void lock() { lock(portMAX_DELAY); }
    inline void lock(std::chrono::milliseconds timeout) {
        lock(static_cast<TickType_t>(timeout.count() / portTICK_PERIOD_MS));
    }

    inline void unlock() {
        if (xSemaphoreGive(mutex_)) {
            // something went wrong, TODO: handle error
        }
    }

    inline bool try_lock() { return xSemaphoreTake(mutex_, 0) == pdTRUE; }

  private:
    SemaphoreHandle_t mutex_;
};

} // namespace freertos
