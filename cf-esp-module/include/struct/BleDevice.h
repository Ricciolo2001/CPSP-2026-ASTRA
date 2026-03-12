#pragma once

#include <string>

struct BleDevice {
    std::string name;
    std::string address;
    int rssi;
    float distance;
};
