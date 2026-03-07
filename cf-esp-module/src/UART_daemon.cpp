#include "UART_daemon.h"

UartDaemon::UartDaemon(uart_port_t port, int baudrate, BleManager *ble)
    : _port(port), _baudrate(baudrate), _ble(ble), _taskHandle(NULL), _dataBuffer(NULL) {}

UartDaemon::~UartDaemon()
{
    stop(); // Automatic cleanup
}

void UartDaemon::start(uint32_t stackSize, UBaseType_t priority)
{
    if (_taskHandle == NULL)
    { // Check if the task is already running
        xTaskCreate(taskWrapper, "uart_daemon_task", stackSize, this, priority, &_taskHandle);
    }
}

void UartDaemon::stop()
{
    if (_taskHandle != NULL)
    {
        vTaskDelete(_taskHandle);
        _taskHandle = NULL;
    }
    if (_dataBuffer != NULL)
    {
        free(_dataBuffer);
        _dataBuffer = NULL;
    }
    // Disinstalla il driver per liberare l'hardware
    uart_driver_delete(_port);
}

void UartDaemon::reset()
{
    stop();
    start();
}

bool UartDaemon::init()
{
    Serial.println("UART: Initializing hardware...");

    _dataBuffer = (uint8_t *)malloc(BUF_SIZE);
    if (!_dataBuffer)
        return false;

    uart_config_t uart_config = {
        .baud_rate = _baudrate,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
    };

    if (uart_driver_install(_port, BUF_SIZE * 2, 0, 0, NULL, 0) != ESP_OK)
        return false;
    if (uart_param_config(_port, &uart_config) != ESP_OK)
        return false;
    // Sostituisci TXD_PIN, RXD_PIN etc con i tuoi define o variabili
    if (uart_set_pin(_port, TXD_PIN, RXD_PIN, RTS_PIN, CTS_PIN) != ESP_OK)
        return false;

    Serial.println("UART: Driver installed successfully.");
    return true;
}

void UartDaemon::run()
{
    while (true)
    {
        int len = uart_read_bytes(_port, _dataBuffer, BUF_SIZE - 1, 20 / portTICK_PERIOD_MS);
        if (len > 0)
        {
            _dataBuffer[len] = '\0';
            char *command = (char *)_dataBuffer;

            if (strcmp(command, "SCAN") == 0)
            {
                Serial.println("UART: Command SCAN received.");
                auto devices = _ble->scanDevices(5);

                // --- Generazione JSON ---
                cJSON *root = cJSON_CreateObject();
                cJSON *array = cJSON_AddArrayToObject(root, "devices");
                for (const auto &dev : devices)
                {
                    cJSON *d = cJSON_CreateObject();
                    cJSON_AddStringToObject(d, "name", dev.name.c_str());
                    cJSON_AddStringToObject(d, "address", dev.address.c_str());
                    cJSON_AddNumberToObject(d, "rssi", dev.rssi);
                    cJSON_AddItemToArray(array, d);
                }
                char *json = cJSON_PrintUnformatted(root);
                uart_write_bytes(_port, json, strlen(json));
                uart_write_bytes(_port, "\n", 1);

                free(json);
                cJSON_Delete(root);
            }
            else if (strcasecmp(command, "BIND") == 0)
            {
                len = uart_read_bytes(_port, _dataBuffer, BUF_SIZE - 1, 20 / portTICK_PERIOD_MS);
                if (len == 0)
                {
                    Serial.println("Failed to read");
                    uart_write_bytes(_port, "Failed to read", sizeof("Failde to read"));
                }
                else if (len > 0)
                {
                    _dataBuffer[len] = '\0';
                    std::string name((char *)_dataBuffer);
                    Serial.printf("UART: Command BIND received with name: %s\n", name.c_str());
                    bool success = _ble->setTargetDevice(name);
                    const char *response = success ? "BIND_SUCCESS" : "BIND_FAILED";
                    uart_write_bytes(_port, response, strlen(response));
                }
            }
            else if (strcmp(command, "RESET") == 0)
            {
                // Esempio di comando che resetta il demone stesso
                this->reset();
                return; // Esci per sicurezza poiché la task viene distrutta e ricreata
            }
        }
    }
}