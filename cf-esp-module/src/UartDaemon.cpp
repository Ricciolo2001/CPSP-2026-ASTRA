#include "UartDaemon.h"

#include <Arduino.h>
#include <cJSON.h>

UartDaemon::UartDaemon(const Config &config, BleManager *ble)
    : FreeRtosTask<UartDaemon>(
          {"uart_daemon_task", config.taskStackSize, config.taskPriority}),
      uart_({config.port, config.uart, config.txdPin, config.rxdPin,
             config.rtsPin, config.ctsPin}),
      ble_(ble), dataBuffer_(std::make_unique<uint8_t[]>(UartPort::kBufSize)) {}

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
    if (strcasecmp(command.c_str(), "SCAN") == 0) {
        Serial.println("UART: Command SCAN received.");
        auto devices = ble_->scanDevices(5);

        // --- Generazione JSON ---
        cJSON *root = cJSON_CreateObject();
        cJSON *array = cJSON_AddArrayToObject(root, "devices");
        for (const auto &dev : devices) {
            cJSON *d = cJSON_CreateObject();
            cJSON_AddStringToObject(d, "name", dev.name.c_str());
            cJSON_AddStringToObject(d, "address", dev.address.c_str());
            cJSON_AddNumberToObject(d, "rssi", dev.rssi);
            cJSON_AddItemToArray(array, d);
        }
        char *json = cJSON_PrintUnformatted(root);
        uart_.write(json, strlen(json));
        uart_.write("\n");

        free(json);
        cJSON_Delete(root);
    } else if (strcasecmp(command.c_str(), "BIND") == 0) {
        if (args.empty()) {
            Serial.println("UART: BIND requires a device name argument.");
            uart_.write("BIND_ERROR: missing argument\n");
        } else {
            Serial.printf("UART: Command BIND received with name: %s\n",
                          args.c_str());
            bool success = ble_->setTargetDevice(args);
            uart_.write(success ? "BIND_SUCCESS\n" : "BIND_FAILED\n");
        }
    } else if (strcasecmp(command.c_str(), "DISTANCE") == 0) {
        Serial.println("UART: Command DISTANCE received.");
        float distance = ble_->getTargetDistance();
        char response[32];
        snprintf(response, sizeof(response), "DISTANCE:%.2f\n", distance);
        uart_.write(response, strlen(response));
    } else if (strcasecmp(command.c_str(), "RESET") == 0) {
        // Signal the task to restart cleanly (avoids self-deletion deadlock)
        requestRestart();
        return;
    }
}
