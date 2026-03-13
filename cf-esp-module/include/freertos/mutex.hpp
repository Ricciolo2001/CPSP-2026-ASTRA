#pragma once

#include <stdexcept>

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

namespace freertos {

class Mutex {
  public:
    explicit Mutex() : mutex_(xSemaphoreCreateMutex()) {
        if (mutex_ == nullptr) {
            throw std::runtime_error("Failed to create FreeRTOS mutex");
        }
    }

    ~Mutex() {
        if (mutex_ != nullptr) {
            vSemaphoreDelete(mutex_);
        }
    }

    // Disable copying
    Mutex(const Mutex &) = delete;
    Mutex &operator=(const Mutex &) = delete;

    // Blocks until the mutex is obtained
    void lock() { xSemaphoreTake(mutex_, portMAX_DELAY); }

    void unlock() {
        if (xSemaphoreGive(mutex_)) {
            // something went wrong, TODO: handle error
        }
    }

    bool try_lock() { return xSemaphoreTake(mutex_, 0) == pdTRUE; }

  private:
    SemaphoreHandle_t mutex_;
};

} // namespace freertos
