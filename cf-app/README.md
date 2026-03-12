# ASTRA - CRTP-UART bridge app

This CrazyFlie app implements a bridge between the CrazyRadio Transceiver Protocol (CRTP) and a UART interface. It allows communication between a Crazyflie drone and an external device via UART, enabling control and data exchange.

## Building the App

The app uses the CrazyFlie Kbuild system.

To build the app, use Make:

```bash
make -j4
```

## Flashing the App

After building, you can flash the app to your Crazyflie drone using the following command:

```bash
cfloader flash build/cf2.bin stm32-fw
```
