#include "UartDaemon.h"

#include <cJSON.h>

UartDaemon::UartDaemon(uart_port_t port, int baudrate, BleManager *ble)
    : port_(port), baudrate_(baudrate), ble_(ble), taskHandle_(NULL),
      dataBuffer_(std::make_unique<uint8_t[]>(kBufSize)) {}

UartDaemon::~UartDaemon() {
    stop(); // Automatic cleanup
}

void UartDaemon::start(uint32_t stackSize, UBaseType_t priority) {
    if (taskHandle_ != NULL) { // Check if the task is already running
        return;
    }

    // Pass "this" as argument to the task so it can call member functions
    xTaskCreate(taskWrapper, "uart_daemon_task", stackSize, this, priority,
                &taskHandle_);
}

void UartDaemon::taskWrapper(void *arg) {
    UartDaemon *instance = static_cast<UartDaemon *>(arg);
    if (instance->init()) { // Se l'init fallisce, non entriamo nel loop
        instance->run();
    }
    // run() exited: clean up resources without going through stop(),
    // then delete ourselves safely with NULL (avoids vTaskDelete on own
    // handle).
    instance->taskHandle_ = NULL;
    uart_driver_delete(instance->port_);
    vTaskDelete(NULL);
}

void UartDaemon::stop() {
    TaskHandle_t toDelete = taskHandle_;
    taskHandle_ = NULL;

    if (toDelete == NULL) {
        return; // Task is not running
    }

    // Cleanup hardware resources before potentially deleting the task
    if (uart_driver_delete(port_) != ESP_OK) {
        Serial.println("UART: Failed to delete driver");
    }

    if (toDelete == xTaskGetCurrentTaskHandle()) {
        // Called from within the task itself: use NULL to safely
        // self-delete
        vTaskDelete(NULL);
    } else {
        vTaskDelete(toDelete);
    }
}

void UartDaemon::reset() {
    stop();
    start();
}

bool UartDaemon::init() {
    Serial.println("UART: Initializing hardware...");

    uart_config_t uart_config = {
        .baud_rate = baudrate_,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
    };

    if (uart_driver_install(port_, kBufSize * 2, 0, 0, NULL, 0) != ESP_OK) {
        Serial.println("UART: Failed to install driver");
        return false;
    }

    if (uart_param_config(port_, &uart_config) != ESP_OK) {
        Serial.println("UART: Failed to configure parameters");
        return false;
    }
    // Sostituisci TXD_PIN, RXD_PIN etc con i tuoi define o variabili
    if (uart_set_pin(port_, UART_TXD_PIN, UART_RXD_PIN, UART_RTS_PIN,
                     UART_CTS_PIN) != ESP_OK) {
        Serial.println("UART: Failed to set pins");
        return false;
    }

    Serial.println("UART: Driver installed successfully.");
    return true;
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
        uart_write_bytes(port_, json, strlen(json));
        uart_write_bytes(port_, "\n", 1);

        free(json);
        cJSON_Delete(root);
    } else if (strcasecmp(command.c_str(), "BIND") == 0) {
        if (args.empty()) {
            Serial.println("UART: BIND requires a device name argument.");
            const char *err = "BIND_ERROR: missing argument\n";
            uart_write_bytes(port_, err, strlen(err));
        } else {
            Serial.printf("UART: Command BIND received with name: %s\n",
                          args.c_str());
            bool success = ble_->setTargetDevice(args);
            const char *response = success ? "BIND_SUCCESS\n" : "BIND_FAILED\n";
            uart_write_bytes(port_, response, strlen(response));
        }
    } else if (strcasecmp(command.c_str(), "DISTANCE") == 0) {
        Serial.println("UART: Command DISTANCE received.");
        float distance = ble_->getTargetDistance();
        char response[32];
        snprintf(response, sizeof(response), "DISTANCE:%.2f\n", distance);
        uart_write_bytes(port_, response, strlen(response));
    } else if (strcasecmp(command.c_str(), "RESET") == 0) {
        // Esempio di comando che resetta il demone stesso
        this->reset();
        return; // Esci per sicurezza poiché la task viene distrutta e
                // ricreata
    }
}

void UartDaemon::run() {
    std::string lineBuffer;

    while (true) {
        int len = uart_read_bytes(port_, dataBuffer_.get(), kBufSize - 1,
                                  20 / portTICK_PERIOD_MS);
        if (len <= 0)
            continue;

        // Accumulate incoming bytes into the line buffer
        lineBuffer.append(reinterpret_cast<char *>(dataBuffer_.get()), len);

        if (lineBuffer.length() > kBufSize) {
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
