// SPDX-License-Identifier: MIT
// SPDX-FileCopyrightText: 2026 Eyad Issa <eyadlorenzo@gmail.com>

#pragma once

/**
 * @file astra_debug.h
 * @brief Debug polyfill for ASTRA
 */

// If we are on Crazyflie, try to include the next debug.h
#if defined(CRAZYFLIE_FW) && __has_include("debug.h")
  #include "debug.h"
#endif

#ifndef DEBUG_FMT
  #define DEBUG_FMT(fmt) DEBUG_MODULE ": " fmt
#endif

// ESP-IDF logging macros
#if !defined(DEBUG_PRINT) && defined(ESP_PLATFORM)
  #include "esp_log.h"
  #define DEBUG_PRINT(fmt, ...)                                                                                        \
    do {                                                                                                               \
      ESP_LOGI(DEBUG_MODULE, DEBUG_FMT(fmt), ##__VA_ARGS__);                                                           \
    } while (0)

// Generic fallback implementation
#elif !defined(DEBUG_PRINT)
  #include <stdio.h>
  #define DEBUG_PRINT(fmt, ...)                                                                                        \
    do {                                                                                                               \
      printf(DEBUG_FMT(fmt), ##__VA_ARGS__);                                                                           \
    } while (0)
  #warning "DEBUG_PRINT will use printf fallback implementation."
#endif
