#pragma once

#include <chrono>
#include <stdexcept>

#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

namespace freertos {

/// RAII wrapper around a FreeRTOS binary semaphore.
///
/// Models a binary signal (not a lock): one task calls give(), another waits
/// on take(). Starts in the "empty" (not given) state.
///
/// @warning FreeRTOS semaphores MUST be created after the scheduler has
/// started. This class does not enforce that, so be sure to only instantiate it
/// after vTaskStartScheduler() is called.
class BinarySemaphore {
  public:
    inline explicit BinarySemaphore() : sem_(xSemaphoreCreateBinary()) {
        if (sem_ == nullptr) {
            throw std::runtime_error(
                "Failed to create FreeRTOS binary semaphore");
        }
    }

    inline ~BinarySemaphore() {
        if (sem_ != nullptr) {
            vSemaphoreDelete(sem_);
        }
    }

    // Non-copyable, non-movable.
    BinarySemaphore(const BinarySemaphore &) = delete;
    BinarySemaphore &operator=(const BinarySemaphore &) = delete;

    /// Block until the semaphore is given (or the timeout expires).
    /// Returns true if the semaphore was taken, false on timeout.
    inline bool take(TickType_t timeout = portMAX_DELAY) {
        return xSemaphoreTake(sem_, timeout) == pdTRUE;
    }
    inline bool take(std::chrono::milliseconds timeout) {
        return take(
            static_cast<TickType_t>(timeout.count() / portTICK_PERIOD_MS));
    }

    /// Signal the semaphore. Safe to call from both tasks and ISRs.
    /// Returns true if a waiting task was unblocked.
    inline bool give() { return xSemaphoreGive(sem_) == pdTRUE; }

    /// ISR-safe variant of give().
    inline bool giveFromISR() {
        BaseType_t woken = pdFALSE;
        bool ok = xSemaphoreGiveFromISR(sem_, &woken) == pdTRUE;
#if CONFIG_IDF_TARGET_ARCH_RISCV
        // ESP32-C3, C6, H2 (RISC-V)
        if (woken) {
            portYIELD_FROM_ISR();
        }
#else
        // ESP32, S2, S3 (Xtensa)
        portYIELD_FROM_ISR(woken);
#endif
        return ok;
    }

  private:
    SemaphoreHandle_t sem_;
};

/// RAII wrapper around a FreeRTOS mutex.
///
/// Starts in the unlocked state. Only one task can hold the mutex at a time; if
/// a second task tries to lock it, it will block until the first task unlocks
/// it.
///
/// @warning FreeRTOS mutexes MUST be created after the scheduler has started.
/// This class does not enforce that, so be sure to only instantiate it after
/// vTaskStartScheduler() is called.
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
        if (xSemaphoreGive(mutex_) != pdTRUE) {
            // something went wrong, TODO: handle error
        }
    }

    inline bool try_lock() { return xSemaphoreTake(mutex_, 0) == pdTRUE; }

  private:
    SemaphoreHandle_t mutex_;
};

} // namespace freertos
