#include "UartDaemon.h"

#include <Arduino.h>
#include <cJSON.h>
#include <cstring>
#include <memory>

#include "cJson.hpp"

namespace {
cjson::Document errorResponse(cjson::Element message) {
    cjson::Document doc{};
    doc.add("error", std::move(message));
    return doc;
}

cjson::Document successResponse(cjson::Element message) {
    cjson::Document doc{};
    doc.add("result", std::move(message));
    return doc;
}

} // namespace

UartDaemon::UartDaemon(const Config &config, BleManager *ble)
    : freertos::Task<UartDaemon>(
          {"uart_daemon_task", config.taskStackSize, config.taskPriority}),
      uart_(config.uartConfig), ble_(ble),
      dataBuffer_(std::make_unique<uint8_t[]>(UartPort::kBufSize)) {}

UartDaemon::~UartDaemon() {
    stop(); // Automatic cleanup
}

bool UartDaemon::init() { return uart_.init(); }

void UartDaemon::run() {
    if (!init()) {
        return;
    }
    std::string lineBuffer;

    while (running_.load(std::memory_order_relaxed)) {
        int len = uart_.read(dataBuffer_.get(), UartPort::kBufSize - 1,
                             20 / portTICK_PERIOD_MS);
        if (len <= 0)
            continue;

        // Accumulate incoming bytes into the line buffer
        lineBuffer.append(reinterpret_cast<char *>(dataBuffer_.get()), len);

        if (lineBuffer.length() > UartPort::kBufSize) {
            Serial.printf("UART: Line buffer overflow. Goto data length: %d. "
                          "Clearing buffer.\n",
                          len);
            lineBuffer.clear();
            continue;
        }

        // Only process when a full newline-terminated line has arrived
        size_t newlinePos = lineBuffer.find('\n');
        if (newlinePos == std::string::npos)
            continue;

        // Extract the line (strip \r\n)
        std::string line = lineBuffer.substr(0, newlinePos);
        lineBuffer.erase(0, newlinePos + 1); // keep any bytes after the newline

        if (!line.empty() && line.back() == '\r')
            line.pop_back();
        if (line.empty())
            continue;

        // Split on the first space: command name + rest as args
        std::string cmd, args;
        size_t spacePos = line.find(' ');
        if (spacePos != std::string::npos) {
            cmd = line.substr(0, spacePos);
            args = line.substr(spacePos + 1);
        } else {
            cmd = line;
            args = "";
        }

        executeCommand(cmd, args);
    }

    uart_.deinit();
}

void UartDaemon::executeCommand(const std::string &command,
                                const std::string &args) {

    Serial.printf("UART: Received command: '%s' with args: '%s'\n",
                  command.c_str(), args.c_str());

    if (strcasecmp(command.c_str(), "SCAN") == 0) {
        Serial.println("UART: Command SCAN received.");
        auto devices = ble_->scanDevices(5);

        Serial.printf("UART: Found %d devices.\n", (int)devices.size());

        cjson::Document root{};
        cjson::Arr deviceArray{};
        for (const auto &dev : devices) {
            cjson::Document d{};
            d.add("name", cjson::Str(dev.name));
            d.add("address", cjson::Str(dev.address));
            d.add("rssi", cjson::Num(dev.rssi));
            d.add("serviceUUID", cjson::Str(dev.serviceUUID));
            d.add("serviceData", cjson::Str(dev.serviceData));

            deviceArray.addItem(std::move(d));
        }

        auto response = successResponse(std::move(deviceArray));
        auto jsonStr = cjson::printUnformatted(std::move(response));
        uart_.writeln(std::string_view(jsonStr));

    } else if (strcasecmp(command.c_str(), "BIND") == 0) {
        if (args.empty()) {
            Serial.println("UART: BIND requires a device name argument.");
            auto errJson = errorResponse(
                cjson::Str("BIND command requires a device name argument"));
            auto jsonStr = cjson::printUnformatted(errJson);
            uart_.writeln(std::string_view(jsonStr));
            return;
        }

        Serial.printf("UART: Command BIND received with name: %s\n",
                      args.c_str());

        bool success = ble_->setTargetDevice(args);

        auto responseMsg =
            success
                ? successResponse(cjson::Str("Bound to device successfully"))
                : errorResponse(cjson::Str("Failed to bind to device"));

        Serial.printf("UART: BIND result: %s\n",
                      success ? "success" : "failure");

        auto jsonStr = cjson::printUnformatted(responseMsg);
        uart_.writeln(std::string_view(jsonStr));

    } else if (strcasecmp(command.c_str(), "DISTANCE") == 0) {
        Serial.println("UART: Command DISTANCE received.");
        auto distance = ble_->getTargetRssi();

        Serial.printf("UART: Current distance to target device: %.2f\n",
                      distance);

        auto response = successResponse(cjson::Num(distance));
        auto jsonStr = cjson::printUnformatted(response);
        uart_.writeln(std::string_view(jsonStr));

    } else if (strcasecmp(command.c_str(), "RESET") == 0) {
        // Signal the task to restart cleanly (avoids self-deletion deadlock)
        requestRestart();
        return;
    } else {
        Serial.printf("UART: Unknown command: %s\n", command.c_str());
        auto errJson = errorResponse(cjson::Str("Unknown command"));
        auto jsonStr = cjson::printUnformatted(errJson);
        uart_.writeln(std::string_view(jsonStr));
    }
}
