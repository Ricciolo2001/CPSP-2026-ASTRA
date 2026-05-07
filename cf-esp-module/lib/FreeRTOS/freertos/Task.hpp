// SPDX-FileCopyrightText: 2026 Eyad Issa
//
// SPDX-License-Identifier: MIT

#pragma once

#include <atomic>

#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

namespace freertos {

/// CRTP base that provides a safe FreeRTOS task lifecycle.
///
/// Usage:
///   class MyTask : public FreeRtosTask<MyTask> {
///     friend class FreeRtosTask<MyTask>;
///   public:
///     MyTask() : FreeRtosTask<MyTask>({"my_task", 4096, 5}) {}
///   private:
///     void run();  // main body; poll running_ in the loop
///   };
///
/// External lifecycle (from any other task):
///   start()          — create the FreeRTOS task (no-op if already running)
///   stop()           — set running_=false, wait until the task exits
///   reset()          — stop() + start()
///
/// From inside run():
///   requestRestart() — exit run() and restart cleanly, avoids self-deletion
template <typename Derived> class Task {
  public:
    struct TaskConfig {
        const char *name = "task";
        uint32_t stackSize = 4096;
        UBaseType_t priority = 1;
    };

    /// Create the FreeRTOS task. No-op if already running.
    void start() {
        if (taskHandle_ != NULL)
            return;
        running_.store(true, std::memory_order_relaxed);
        xTaskCreate(taskEntry, cfg_.name, cfg_.stackSize, this, cfg_.priority,
                    &taskHandle_);
    }

    /// Signal run() to exit, then block until the task is gone.
    /// Safe to call from any external task.
    void stop() {
        if (taskHandle_ == NULL)
            return;
        running_.store(false, std::memory_order_relaxed);
        xTaskNotifyGive(taskHandle_); // wake any blocking wait in run()
        while (taskHandle_ != NULL)
            vTaskDelay(1);
    }

    /// stop() followed by start(). Only call from outside the task.
    void reset() {
        stop();
        start();
    }

    bool isRunning() const { return taskHandle_ != NULL; }

  protected:
    explicit Task(TaskConfig cfg) : cfg_(std::move(cfg)) {}

    /// Call from inside run() to request a clean restart without self-deletion.
    /// Sets running_=false so the loop exits; taskEntry then calls run() again.
    void requestRestart() {
        restartRequested_.store(true, std::memory_order_relaxed);
        running_.store(false, std::memory_order_relaxed);
    }

    /// True while the task should keep running. Poll this in run()'s loop.
    std::atomic<bool> running_{false};

  private:
    static void taskEntry(void *arg) {
        auto *self = static_cast<Derived *>(arg);
        do {
            self->restartRequested_.store(false, std::memory_order_relaxed);
            self->run();
        } while (self->restartRequested_.load(std::memory_order_relaxed));
        self->running_.store(false, std::memory_order_relaxed);
        self->taskHandle_ = NULL;
        vTaskDelete(NULL);
    }

    TaskConfig cfg_;
    TaskHandle_t taskHandle_ = NULL;
    std::atomic<bool> restartRequested_ = {false};
};

} // namespace freertos
