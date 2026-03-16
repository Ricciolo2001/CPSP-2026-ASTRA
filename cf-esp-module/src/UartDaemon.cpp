#include "UartDaemon.h"

#include <Arduino.h>
#include <cJSON.h>
#include <cctype>
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

std::string toLower(std::string_view str) {
    std::string result(str);
    for (char &c : result)
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return result;
}

} // namespace

UartDaemon::UartDaemon(const Config &config, BleManager &ble)
    : freertos::Task<UartDaemon>(
          {"uart_daemon_task", config.taskStackSize, config.taskPriority}),
      uart_(config.uartConfig), ble_(ble),
      dataBuffer_(std::make_unique<uint8_t[]>(UartDaemon::kBufSize)) {}

UartDaemon::~UartDaemon() {
    stop(); // Automatic cleanup
}

void UartDaemon::run() {
    std::string lineBuffer;

    while (running_.load(std::memory_order_relaxed)) {
        int len = uart_.read(dataBuffer_.get(), UartDaemon::kBufSize - 1,
                             pdMS_TO_TICKS(20));
        if (len <= 0)
            continue;

        // Accumulate incoming bytes into the line buffer
        lineBuffer.append(reinterpret_cast<char *>(dataBuffer_.get()), len);

        if (lineBuffer.length() > UartDaemon::kBufSize) {
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
}

void UartDaemon::executeCommand(const std::string &command,
                                const std::string &args) {
    // Normalise once so handlers don't need case-insensitive comparisons.
    std::string lowercaseCommand = toLower(command);

    Serial.printf("UART: Received command: '%s' with args: '%s'\n",
                  lowercaseCommand.c_str(), args.c_str());

    // The table is static const so it lives in flash (.rodata) rather than
    // being reconstructed on the stack every call. This requires plain function
    // pointers. Lambdas that capture 'this' become closure objects and lose
    // the ability to decay to a raw pointer, so the instance is passed as an
    // explicit 'self' parameter instead.
    using Handler = void (*)(UartDaemon &, const std::string &);
    struct Entry {
        std::string_view name;
        Handler fn;
    };

    static const Entry kCommands[] = {
        {"scan",
         [](UartDaemon &self, const std::string &) {
             Serial.println("UART: Command SCAN received.");
             auto devices = self.ble_.scanDevices(5);
             Serial.printf("UART: Found %d devices.\n", (int)devices.size());

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
             self.uart_.writeln(std::string_view(jsonStr));
         }},
        {"bind",
         [](UartDaemon &self, const std::string &a) {
             if (a.empty()) {
                 Serial.println(
                     "UART: BIND requires a device address argument.");
                 auto errJson = errorResponse(cjson::Str(
                     "BIND command requires a device address argument"));
                 auto jsonStr = cjson::printUnformatted(errJson);
                 self.uart_.writeln(std::string_view(jsonStr));
                 return;
             }
             Serial.printf("UART: Command BIND received with address: %s\n",
                           a.c_str());
             self.ble_.setTargetDevice(a);

             auto responseMsg =
                 successResponse(cjson::Str("Bound to device successfully"));
             auto jsonStr = cjson::printUnformatted(responseMsg);
             self.uart_.writeln(std::string_view(jsonStr));
         }},
        {"distance",
         [](UartDaemon &self, const std::string &) {
             Serial.println("UART: Command DISTANCE received.");
             auto rssi = self.ble_.getTargetRssi();
             Serial.printf("UART: Current RSSI of target device: %.2f\n", rssi);
             auto response = successResponse(cjson::Num(rssi));
             auto jsonStr = cjson::printUnformatted(response);
             self.uart_.writeln(std::string_view(jsonStr));
         }},
        {"reset",
         [](UartDaemon &self, const std::string &) {
             // requestRestart() signals the task to exit run() and restart
             // cleanly, avoiding a self-deletion deadlock.
             self.requestRestart();
         }},
    };

    for (const auto &entry : kCommands) {
        if (lowercaseCommand == entry.name) {
            entry.fn(*this, args);
            return;
        }
    }

    // No match: unknown command
    Serial.printf("UART: Unknown command: %s\n", lowercaseCommand.c_str());
    auto errJson = errorResponse(cjson::Str("Unknown command"));
    auto jsonStr = cjson::printUnformatted(errJson);
    uart_.writeln(std::string_view(jsonStr));
}
