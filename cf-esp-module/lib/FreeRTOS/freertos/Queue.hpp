// SPDX-FileCopyrightText: 2026 Eyad Issa
//
// SPDX-License-Identifier: MIT

#pragma once

#include <freertos/queue.h>
#include <stdexcept>

namespace freertos {

/// RAII wrapper around a FreeRTOS queue.
///
/// Provides type safety and automatic cleanup. The queue is created when the
/// Queue object is constructed, and deleted when the Queue object is destroyed.
/// The template parameter T specifies the type of items stored in the queue.
template <typename T> class Queue {
  public:
    explicit Queue(size_t length) : queue_(xQueueCreate(length, sizeof(T))) {
        if (queue_ == nullptr) {
            throw std::runtime_error("Failed to create FreeRTOS queue");
        }
    }

    ~Queue() {
        if (queue_ != nullptr) {
            vQueueDelete(queue_);
        }
    }

    // Disable copy and move semantics
    Queue(const Queue &) = delete;
    Queue &operator=(const Queue &) = delete;
    Queue(Queue &&) = delete;
    Queue &operator=(Queue &&) = delete;

    /// Send an item to the back of the queue. Blocks for at most `timeout`
    /// ticks if the queue is full.
    /// @returns pdTRUE on success, pdFALSE on timeout.
    BaseType_t send(const T &item, TickType_t timeout = portMAX_DELAY) {
        return xQueueSend(queue_, &item, timeout) == pdTRUE;
    }

    /// Receive an item from the front of the queue. Blocks for at most
    /// `timeout` ticks if the queue is empty.
    /// @returns pdTRUE on success (item is written to `out`), pdFALSE on
    /// timeout.
    BaseType_t receive(T &out, TickType_t timeout = portMAX_DELAY) {
        return xQueueReceive(queue_, &out, timeout) == pdTRUE;
    }

    /// Reset the queue to the empty state, discarding all items.
    void reset() { xQueueReset(queue_); }

  private:
    QueueHandle_t queue_;
};
} // namespace freertos
