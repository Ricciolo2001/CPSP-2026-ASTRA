# ASTRA

Autonomous Signal Tracking & Ranging Aircraft is a project that aims to develop an autonomous drone capable of tracking and moving towards a signal source.

The drone will be based on the Crazyflie 2.1 platform and will use BLE (Bluetooth Low Energy) beacons for signal tracking.

This project is done for the Cyber Physical Systems Programming (CPSP) course at the University of Bologna.

## Project Structure

The project is organized into the following directories:

- `cf-app`: Contains the code for the Crazyflie application
- `cf-firmware`: Contains the firmware code for the Crazyflie. It is a git submodule and tracks the official Crazyflie firmware repository.
- `cf-esp-module`: Contains the code for the ESP32 module that will be used mounted on the Crazyflie to perform BLE scanning and signal processing.
- `pc-python`: Contains the code for the PC application that will be used to visualize the data received from the drone and to send commands to it.

## Getting Started

To get started with the project, follow these steps:

1. Clone the repository and initialize the submodule:

   ```bash
   git clone --recursive <repository_url>
   ```

2. Build and flash the firmware for the Crazyflie:

   ```bash
   cd cf-firmware
   make
   cfloader flash build/cf2.bin stm32-fw
   ```

3. Build and flash the code for the ESP32 module:

   ```bash
   cd cf-esp-module
   pio run
   # TODO: add instructions for flashing the ESP32 module
   ```

4. Build and run the PC application:
   ```bash
   cd pc-python
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   # TODO: add instructions for running the PC application
   ```

## Contributing

This project is not open for external contributions as it is a course project. However, if you have any suggestions or feedback, feel free to reach out to the project maintainers via GitHub issues.

## License

This project follows the [REUSE 3.3 guidelines](https://reuse.software/) for licensing. You can find a SPDX-License-Identifier in each source file, and the LICENSES directory contains the full text of each license used in the project. Please refer to the LICENSES directory for more information on the licenses used in this project.
