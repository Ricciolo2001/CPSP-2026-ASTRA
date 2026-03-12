#include "UartDaemon.h"

#include <cJSON.h>

UartDaemon::UartDaemon(uart_port_t port, int baudrate, BleManager *ble)
    : port_(port), baudrate_(baudrate), ble_(ble), taskHandle_(NULL),
      dataBuffer_(NULL) {}

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
    // Se run() esce, cancelliamo la task in sicurezza
    instance->stop();
}

void UartDaemon::stop() {
    TaskHandle_t toDelete = taskHandle_;
    taskHandle_ = NULL;

    if (toDelete != NULL) {
        vTaskDelete(toDelete);
    }

    // Cleanup hardware and memory
    if (dataBuffer_ != NULL) {
        free(dataBuffer_);
        dataBuffer_ = NULL;
    }
    uart_driver_delete(port_);
}

void UartDaemon::reset() {
    stop();
    start();
}

bool UartDaemon::init() {
    Serial.println("UART: Initializing hardware...");

    dataBuffer_ = (uint8_t *)malloc(kBufSize);
    if (!dataBuffer_)
        return false;

    uart_config_t uart_config = {
        .baud_rate = baudrate_,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
    };

    if (uart_driver_install(port_, kBufSize * 2, 0, 0, NULL, 0) != ESP_OK)
        return false;
    if (uart_param_config(port_, &uart_config) != ESP_OK)
        return false;
    // Sostituisci TXD_PIN, RXD_PIN etc con i tuoi define o variabili
    if (uart_set_pin(port_, UART_TXD_PIN, UART_RXD_PIN, UART_RTS_PIN,
                     UART_CTS_PIN) != ESP_OK)
        return false;

    Serial.println("UART: Driver installed successfully.");
    return true;
}

void UartDaemon::run() {
    while (true) {
        int len = uart_read_bytes(port_, this->dataBuffer_, this->kBufSize - 1,
                                  20 / portTICK_PERIOD_MS);
        if (len > 0) {
            dataBuffer_[len] = '\0';
            char *command = (char *)dataBuffer_;

            if (strcmp(command, "SCAN") == 0) {
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
            } else if (strcasecmp(command, "BIND") == 0) {
                len = uart_read_bytes(port_, dataBuffer_, kBufSize - 1,
                                      20 / portTICK_PERIOD_MS);
                if (len == 0) {
                    Serial.println("Failed to read");
                    uart_write_bytes(port_, "Failed to read",
                                     sizeof("Failde to read"));
                } else if (len > 0) {
                    dataBuffer_[len] = '\0';
                    std::string name((char *)dataBuffer_);
                    Serial.printf("UART: Command BIND received with name: %s\n",
                                  name.c_str());
                    bool success = ble_->setTargetDevice(name);
                    const char *response =
                        success ? "BIND_SUCCESS" : "BIND_FAILED";
                    uart_write_bytes(port_, response, strlen(response));
                }
            } else if (strcmp(command, "DISTANCE") == 0) {
                Serial.println("UART: Command DISTANCE received.");
                float distance = ble_->getTargetDistance();
                char response[32];
                snprintf(response, sizeof(response), "DISTANCE:%.2f\n",
                         distance);
                uart_write_bytes(port_, response, strlen(response));
            } else if (strcmp(command, "RESET") == 0) {
                // Esempio di comando che resetta il demone stesso
                this->reset();
                return; // Esci per sicurezza poiché la task viene distrutta e
                        // ricreata
            }
        }
    }
}
