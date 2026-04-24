# ASTRA

## 1. Abstract

**ASTRA** (_Autonomous Signal Tracking & Ranging Aircraft_) is an autonomous drone system that locates the source of a Bluetooth Low Energy (BLE) beacon inside a room in order to navigates towards it.

Built on the Crazyflie 2.X platform, it combines onboard RSSI sampling performed by an ESP32 module mounted on the drone with the Flow deck motion tracking to estimate and navigate towards the beacon.

## 2. Introduction & Motivation

<!-- Rispondi a tre domande: Qual è il problema? (localizzazione indoor senza GPS), Perché è rilevante? (robotica, search & rescue, IoT), Qual è il vostro contributo specifico? Chiudi con una panoramica della struttura del paper. -->

Indoor localization is a fundamental challenge in Cyber-Physical Systems, where GPS signals are unavailable or unreliable. Existing solutions such as UWB or camera-based systems offer high accuracy but require fixed infrastructure or significant computational resources, making them unsuitable for lightweight autonomous platforms.

In this work, we present ASTRA, an autonomous drone system that leverages BLE RSSI measurements to locate and navigate towards a beacon source, using only the onboard hardware of the Crazyflie 2.X platform...

The main contributions of this work are:

1. Integration of an ESP32 coprocessor for BLE scanning on a nano-drone platform;
2. A trilateration-based localization algorithm with RSSI filtering;
3. A Python application for real-time visualization and control.

The remainder of this paper is organized as follows: Section 3 provides background on BLE ranging, Section 4 describes the system architecture and hardware components and Section 5 details the communication protocols; Section 6 explains the localization algorithm, while Section 7 outlines the navigation strategy; Section 8 presents experimental results, and Section 9 discusses constraints and known issues. Finally, Section 10 concludes the paper and suggests future work directions.

## 3. Background

<!--
Tre blocchi teorici:

BLE RSSI ranging: il modello log-distance path loss RSSI = A - 10·n·log₁₀(d), dove A è l'RSSI a 1 metro e n è il path loss exponent
Trilateration: come si ricava la posizione da 3+ distanze note, con il sistema di equazioni circolari
Filtri: perché Median + EMA e non solo uno dei due
-->

### BLE RSSI Ranging

Bluetooth Low Energy (BLE) is a wireless communication protocol widely used for short-range applications. BLE devices periodically broadcast advertisement packets that can be detected by nearby receivers. The Received Signal Strength Indicator (RSSI) of these packets can be used to estimate the distance between the transmitter and receiver using the log-distance path loss model:

$$RSSI = A - 10 \cdot n \cdot \log_{10}(d)$$

Where:

- $A$ is the RSSI value at a reference distance of 1 meter,
- $n$ is the path loss exponent that characterizes the environment,
- $d$ is the distance between the transmitter and receiver.

### Trilateration

Trilateration is a geometric method used to determine the position of a point based on its distance from three or more known reference points. In a 2D plane, if we have three reference points with known coordinates $(x_i, y_i)$ and their corresponding distances $d_i$ to the target point $(x, y)$, we can derive the following system of equations:

$$(x - x_i)^2 + (y - y_i)^2 = d_i^2 \quad \text{for } i = 1, 2, 3$$

Solving this system allows us to estimate the coordinates of the target point. In practice, due to measurement noise and environmental factors, the equations may not have an exact solution. To account for this, we use a least-squares optimization approach to find the best estimate of the target position that minimizes the error between the measured distances and the distances calculated from the estimated position.

### Filtering

Due to the inherent noise in RSSI measurements, we apply a combination of Median and Exponential Moving Average (EMA) filters to the sampled values. The Median filter is effective at removing outliers and sudden spikes in the data, while the EMA provides a smoothed estimate that gives more weight to recent measurements. The choice of filter coefficients is crucial and is typically determined empirically based on the expected dynamics of the system and the noise characteristics of the environment.

## 4. System Architecture

The system consists of three main components:

- The Crazyflie drone, which serves as the main platform for navigation and data collection.
- An ESP32 module mounted on the drone, responsible for performing BLE scanning and sampling the RSSI values from the beacon's advertisements.
- A PC application that receives data from the drone, visualizes the estimated position of the beacon, and allows the user to send commands to the drone.

```mermaid
graph TD
    Beacon -->|BLE| ESP32[ESP32 Module]
    ESP32 -->|UART| CF[Crazyflie Drone]
    CF <-->|CRTP| PC[PC Application]
```

![Project schema img](res/schema_progetto.drawio.png)

### 4.1 Hardware

<!--
Lista componente per componente: Crazyflie 2.X, Flow Deck v2, ESP32 (modello esatto), beacon BLE usato, CrazyRadio. Per ognuno: ruolo, specifiche rilevanti, eventuali limitazioni.
-->

### Crazyflie 2.X

The Crazyflie 2.1 is a nano quadcopter used as the main aerial platform.

**Role:** Executes flight control, stabilization, and onboard processing.
**Key specifications:**

- Weight: ~27 g
- MCU: STM32F405 (main processor) + nRF51822 (radio)
- Open-source firmware and hardware
- Expansion support via deck system

**Limitations:**

- Limited payload capacity
- Short flight time (~7 minutes)
- Limited onboard computational power

### Flow Deck v2

The Flow Deck v2 is an expansion module mounted underneath the drone.

**Role:** Provides relative positioning by measuring motion and distance to the ground.

**Key specifications:**

- Optical flow sensor for lateral motion estimation
- Time-of-Flight (ToF) distance sensor (VL53L1X)
- Effective altitude range: ~0.1–4 m

**Limitations:**

- Requires textured surfaces for accurate tracking
- Performance degrades in low-light or reflective conditions

### ESP32 (e.g., ESP32-WROOM-32)

The ESP32-WROOM-32 is used as a secondary processing and communication unit.

**Role:** Handles BLE communication, beacon detection, and external data processing.

**Key specifications:**

- Dual-core Tensilica CPU up to 240 MHz
- Integrated Wi-Fi and Bluetooth (BLE)
- Rich GPIO and peripheral interfaces

**Limitations:**

- Power consumption can be significant
- BLE positioning accuracy is limited

### BLE Beacon

A BLE beacon is used as a reference point for localization.
**Role:** Broadcasts Bluetooth signals used to estimate distance or proximity.
**Key specifications:**

- Periodic advertising packets (BLE)
- Low power consumption (battery-powered)
- Configurable transmission interval and power
  **Limitations:**
- Signal strength (RSSI) is noisy and environment-dependent
- Accuracy affected by obstacles and interference

### Crazyradio

The Crazyradio PA is a USB communication interface.

**Role:** Enables wireless communication between the drone and a ground station (PC).

**Key specifications:**

- 2.4 GHz radio communication
- Low latency link for control and telemetry
- USB interface for easy integration

**Limitations:**

- Limited communication range (~1 km line-of-sight, much less indoors)
- Susceptible to interference in crowded RF environments

### 4.2 Software

<!--
Descrivi lo stack: firmware Crazyflie (versione, linguaggio), codice ESP32, applicazione PC (libreria cflib, linguaggio, GUI se presente).
-->

The software stack of the ASTRA system is composed of three components:

1. **Crazyflie custom application:** A custom application running on the Crazyflie that implements the localization and navigation logic, processes the RSSI data received from the ESP32, and sends telemetry data to the PC.

2. **ESP32 firmware:** A custom firmware running on the ESP32 module that performs BLE scanning, samples RSSI values, and communicates with the Crazyflie via UART.

3. **PC application:** A Python application that uses the `cflib` library to communicate with the Crazyflie, visualize the estimated position of the beacon, and send high level commands to the drone.

## 5. Communication Protocol

The communication between the components is structured as follows:

- **ESP32 to beacon**
- **Communication between ESP32 and Crazyflie**
- **Drone to PC via crazyradio**

### Beacon to ESP32

BLE beacons advertise their presence by broadcasting advertisement messages at regular intervals (200ms).
The ESP32 module mounted on the Crazyflie scans for these advertisements and samples the RSSI values, which are then used to estimate the distance to the beacon.

When the ESP32 is not bound, it continuously scans for BLE advertisements, but it does not store or send any data to the Crazyflie.
Once it receives a BIND command with a specific BLE MAC address, it starts sampling the RSSI values for that beacon and sends the data back to the Crazyflie at regular intervals.

### ESP32 to Crazyflie

Between the ESP32 and the Crazyflie, we use a UART communication channel to exchange data.

Since UART is a simple serial communication protocol, we have to ensure a proper data format and reliable transmission. For that we encode the data using COBS (Consistent Overhead Byte Stuffing) and we append a CRC16 checksum to ensure data integrity.

During hardware integration, we identified a conflict between the ESP32 coprocessor UART connection and the Flow Deck v2. Initial wiring routed the ESP32 TX line to the UART2 interface of the CrazyFlie deck connector. Under normal operating conditions this configuration appeared functional; however, under heavy UART bus utilization, the onboard state estimator began producing inaccurate readings, causing the drone to drift unpredictably.
Further analysis revealed that UART2 is internally shared with the Flow Deck v2, which relies on it to stream optical flow data to the state estimator. Concurrent traffic on the same bus corrupted the flow data stream, degrading position estimation accuracy.

The issue was resolved by migrating the ESP32 connection to the UART1 interface, which is not allocated by any onboard deck driver, eliminating the conflict entirely.

### Crazyflie to PC

The CrazyFlie communicates with the host PC via the Crazy Real-Time Protocol (CRTP), transported over a bidirectional radio link established through the CrazyRadio USB dongle.
BLE beacon RSSI sampled value is exposed through the standard CrazyFlie parameter and logging infrastructure.
The MAC address of the target beacon is configurable at runtime as a writable parameter, allowing the host application to bind the system to a specific device without requiring firmware modifications.

## 6. Localization Algorithm

<!--
È la sezione più debole tecnicamente. Dovresti aggiungere:

Formula RSSI → distanza con i parametri scelti
Schema degli step: hover in N punti → campionamento → filtraggio → trilateration → stima posizione
Come vengono scelti i punti di campionamento (griglia fissa? pattern di volo?)
Quante misure per punto e con quale criterio si conferma la posizione
-->

To locate the beacon, we rely only on the RSSI sampled values coming from the ESP32 module.
The BLE advertiser continuously sends messages that we can sample to estimate the distance from it.

The drone estimates the position of the beacon using trilateration, which is a method to determine the position of a point based on its distance from three or more known points.

To account for the noise and interference in the RSSI measurements, we apply a strong Median & EMA filter to the sampled RSSI values during the capture phase and we repeat more than 3 measurements to confirm the exact position of the beacon.

## 7. Navigation Strategy

The navigation strategy is handled by a mission application running on the host PC, which coordinates the drone's flight phases through high-level commands sent via CRTP.

**Phase 1 — Takeoff:**
The mission begins with a takeoff command that brings the drone to a fixed operating altitude, where it hovers.

**Phase 2 — Sampling Grid:**
The drone navigates to a set of predefined waypoints arranged in an L pattern with the takeoff point at the corner.
At each waypoint, the drone hovers while the ESP32 collects and filters RSSI samples.
A minimum of three valid distance estimates at distinct locations are required before proceeding to localization.

**Phase 3 — Localization & Tracking:**
Once sufficient samples are collected, the trilateration algorithm produces an initial estimate of the beacon position and the drone navigates towards it.
The system then enters a continuous refinement loop: new RSSI measurements are collected at the current position, the beacon estimate is updated, and the drone adjusts its trajectory accordingly.

This loop runs indefinitely, keeping the drone hovering above the estimated beacon position and correcting for drift in the estimate over time.

> [!WARN]
> In the current implementation, the drone does not perform obstacle avoidance and does not terminate the mission autonomously.
> The operator must issue a manual landing command to end the flight.

## 8. Experimental Evaluation

Precise tracking requires the algorithms to account for two factors of calibration: the path loss exponent $n$ and the reference RSSI value $A$ at 1 meter. We empirically determined these parameters by performing a calibration procedure in the test environment, measuring the RSSI values at known distances from the beacon and fitting the log-distance path loss model to the data.

After calibration, we conducted a series of test flights in a controlled indoor environment (a 5x5 meter room with typical living room furnishings) to evaluate the localization accuracy and navigation performance of the system. The drone was tasked with locating a BLE beacon placed at various positions within the room, starting from a fixed takeoff point.

The results showed that the system was able to successfully locate the beacon and navigate towards it, with an average localization error of approximately 0.5 meters. The accuracy varied depending on the position of the beacon and the presence of obstacles, with better performance observed in line-of-sight conditions.

<!--
TODO: aggiungere grafici o tabelle con i risultati quantitativi, se disponibili. Ad esempio, una tabella con le posizioni reali vs stimate del beacon, o un grafico che mostra la traiettoria del drone durante il test.
-->

## 9. Constraints & Known Issues

Deploying the system on a small platform such as the CrazyFlie introduces several hardware and environmental constraints that were taken into account during development.

- **Shadowing, Multipath and RF Interference:**
  RSSI-based ranging is inherently sensitive to multipath propagation and electromagnetic interference. On a compact platform, motor drivers and switching power electronics are in close physical proximity to the radio antenna, introducing high-frequency noise that may corrupt the analog-to-digital conversion of the received signal. Additionally, mounting the ESP32 coprocessor on a deck immediately above the drone body can produce a shadowing effect, further degrading signal quality and increasing measurement variance.

- **Voltage Sag:**
  Standard RSSI measurement pipelines do not account for supply voltage variations. In our configuration, the ESP32 is powered directly from the LiPo battery through the integrated battery management system (BMS). Under high power demand, the supply rail may drop below the 3.3 V nominal operating voltage of the ESP32, causing erroneous RSSI readings and, in severe cases, triggering an unintended device reboot that interrupts the ranging pipeline.

- **Top Deck Occupancy:**
  Interfacing the ESP32 coprocessor with the CrazyFlie requires use of UART1, the only UART interface not allocated by onboard deck drivers. Routing this connection through the deck connector physically occupies the top expansion port, precluding the simultaneous use of any additional deck hardware that relies on the same connector.

## 10. Conclusions & Future Work

The primary limitation of the current architecture is the dependency on an external ESP32 module for BLE ranging, which occupies the top deck expansion port and introduces the hardware constraints discussed in the previous section.
This limitation could be addressed by using the internal BLE radio of the CrazyFlie, which is already present on the nRF52840 microcontroller.
Migrating the beacon scanning and distance estimation logic directly onto the CrazyFlie would eliminate the need to use an ESP entirely freeing the top deck expansion port for additional sensor hardware.

- First, the Ranger deck could be mounted to provide precise altitude and obstacle distance measurements, improving flight stability and enabling more accurate three-dimensional positioning.
- Second, replacing the BLE antenna with a Loco Positioning deck would allow UWB-based ranging against fixed anchors, offering centimetre-level distance estimation accuracy that far exceeds what is achievable through RSSI-based approaches.

## 11. References

[BITCRAZE](https://www.bitcraze.io/documentation/repository/)
[CRTP_COMMUNICATION](https://www.bitcraze.io/documentation/repository/crazyflie-firmware/master/functional-areas/crtp/)
[CPX_PACKET_STRUCTURE](https://www.bitcraze.io/documentation/repository/crazyflie-firmware/master/functional-areas/cpx/)
[BLE_AND_CRAZYRADIO](https://www.bitcraze.io/documentation/repository/crazyflie2-nrf-firmware/master/protocols/ble/)

## 12. Contributions

The project was completed cooperatively by all three team members, with everyone participating in all aspects:

- Alessandro Ricci Armandi
- Eyad Issa
- Giulia Pareschi
