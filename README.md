# Project Nirvan: Autonomous Sewer and Pipeline Inspection Robot


Project Nirvan is an autonomous, dual-controller inspection rover designed to navigate hazardous, GPS-denied underground environments such as pipelines, sewer systems, and industrial conduits. The system combines real-time multi-gas detection, thermal infrared imaging, ultrasonic obstacle avoidance, and web-based telemetry and manual control.
---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
  - [Hardware Architecture](#hardware-architecture)
  - [Software Architecture](#software-architecture)
- [Hardware Components](#hardware-components)
- [Wiring and Pinout Reference](#wiring-and-pinout-reference)
  - [Raspberry Pi to Arduino Interface](#raspberry-pi-to-arduino-interface)
  - [Raspberry Pi to Thermal Camera Interface](#raspberry-pi-to-thermal-camera-interface)
  - [Arduino to L298N Motor Driver](#arduino-to-l298n-motor-driver)
  - [Arduino to Sensors and Actuators](#arduino-to-sensors-and-actuators)
- [Power Distribution and Grounding](#power-distribution-and-grounding)
- [Communication Protocol](#communication-protocol)
  - [Serial Telemetry Format](#serial-telemetry-format)
  - [Serial Command Format](#serial-command-format)
  - [REST API Endpoints](#rest-api-endpoints)
- [Navigation and Obstacle Avoidance Logic](#navigation-and-obstacle-avoidance-logic)
- [Thermal Imaging Pipeline](#thermal-imaging-pipeline)
- [Installation and Setup](#installation-and-setup)
  - [1. Arduino Firmware Setup](#1-arduino-firmware-setup)
  - [2. Raspberry Pi Configuration](#2-raspberry-pi-configuration)
  - [3. Python Environment and Dependencies](#3-python-environment-and-dependencies)
  - [4. Running the Application](#4-running-the-application)
- [Web Dashboard and Controls](#web-dashboard-and-controls)
- [Repository Structure](#repository-structure)
- [License](#license)

---

## Overview

### Project Demo
[![Watch the Demo](https://img.youtube.com/vi/8IM5mLFAT-4/maxresdefault.jpg)](https://youtu.be/8IM5mLFAT-4)


Operating inside confined subterranean networks presents multiple hazards, including toxic gas accumulation, structural collapses, and zero visual line-of-sight. Project Nirvan addresses these challenges through a distributed computing model:

1. **High-Level Controller (Raspberry Pi Zero 2W):** Hosts the web application and REST API, captures and processes MLX90640 thermal infrared imagery, aggregates telemetry over serial, and serves a live browser dashboard.
2. **Low-Level Controller (Arduino UNO):** Handles hard real-time tasks including sensor ADC polling, ultrasonic ping timing, servo positioning, and H-bridge motor PWM actuation.

This separation isolates time-critical motor and sensor loops from network operations and operating system scheduling jitter.

---

## Key Features

- **Dual Operation Modes:** Supports autonomous obstacle avoidance (`MODE:A`) and operator-driven manual override (`MODE:M`).
- **Hazardous Gas Detection:** Continuous monitoring of three analog gas channels (MQ-2 for combustible gases and smoke, MQ-135 for air quality and hazardous vapors, MQ-136 for hydrogen sulfide and sulfur compounds).
- **Thermal Imaging Stream:** Captures 32x24 thermal arrays via an MLX90640 sensor over I2C, interpolates the frame to 640x480 resolution using cubic interpolation, applies an Inferno colormap, and streams live MJPEG video with maximum temperature tracking.
- **Dynamic Ultrasonic Radar:** Sweeps an HC-SR04 ultrasonic distance sensor across 150 degrees (left), 90 degrees (center), and 30 degrees (right) using an SG90 servo to determine optimal travel clearance.
- **Real-Time Telemetry Dashboard:** Responsive dark-mode interface with Chart.js time-series plots, live environmental status banners, KPI metric displays, and keyboard-driven navigation controls.
- **Remote Power Management:** Graceful system shutdown command via web dashboard to protect filesystem integrity before power disconnection.

---

## System Architecture

### Hardware Architecture

```
+-------------------------------------------------------------------+
|                        Operator Device                            |
|             (Web Browser: http://<robot-ip>:5000)                 |
+---------------------------------+---------------------------------+
                                  |
                                  | Wi-Fi (HTTP / WebSocket / MJPEG)
                                  v
+-------------------------------------------------------------------+
|                      Raspberry Pi Zero 2W                         |
|  - Flask Application Server (app.py)                              |
|  - Thermal Image Processing (OpenCV / MLX90640)                   |
|  - Serial Communication Engine (pyserial)                         |
+-------------------+-------------------------------+---------------+
                    |                               |
     I2C (400 kHz)  |                               | USB Serial (115200 Baud)
                    v                               v
+-------------------------------+   +-------------------------------+
|     MLX90640 Thermal Array    |   |          Arduino UNO          |
|    (32x24 IR Temperature)     |   |  - Sensor ADC Sampling        |
+-------------------------------+   |  - Servo Sweep & Ultrasonic   |
                                    |  - Motor Direction Control    |
                                    +---------------+---------------+
                                                    |
                    +-------------------------------+-------------------------------+
                    |                               |                               |
                    v                               v                               v
    +-------------------------------+   +-----------------------+   +-----------------------+
    |      L298N Motor Driver       |   |   MQ Sensor Suite     |   | HC-SR04 on SG90 Servo |
    | (4WD TT Motors - Skid Steer)  |   | (MQ-2, MQ-135, MQ-136)|   | (Obstacle Avoidance)  |
    +-------------------------------+   +-----------------------+   +-----------------------+
```

### Software Architecture

The software stack comprises two main components:
- **`arduino.ino` (Embedded C++ Firmware):** Runs at 115200 baud, continuously monitoring incoming serial commands, reading ultrasonic distances, scanning analog gas channels every 200 ms, and driving the L298N H-bridge.
- **`app.py` (Python 3 / Flask):** Launches a background daemon thread for non-blocking serial acquisition, continuously updates global telemetry state, manages the MLX90640 I2C interface with percentile-based noise reduction, and serves the web frontend.

---

## Hardware Components

| Category | Component | Model / Specification | Purpose |
| :--- | :--- | :--- | :--- |
| Compute | Single Board Computer | Raspberry Pi Zero 2W | Web server, thermal vision, telemetry aggregation |
| Compute | Microcontroller | Arduino UNO R3 (ATmega328P) | Real-time sensor polling, motor PWM, servo sweep |
| Vision | Thermal Sensor | MLX90640 (32x24 IR array) | Surface temperature mapping and heat anomaly detection |
| Sensing | Ultrasonic Sensor | HC-SR04 | Distance measurement and collision avoidance |
| Sensing | Combustible Gas Sensor | MQ-2 | LPG, methane, alcohol, hydrogen, smoke detection |
| Sensing | Air Quality Sensor | MQ-135 | Ammonia, benzene, alcohol, carbon dioxide detection |
| Sensing | Hydrogen Sulfide Sensor| MQ-136 | Hydrogen sulfide (H2S), sulfur dioxide detection |
| Actuation | Motor Driver | L298N Dual H-Bridge | DC gear motor driving and skid-steer direction control |
| Actuation | Motors | 4x TT DC Gear Motors | 4WD chassis locomotion |
| Actuation | Radar Servo | SG90 Micro Servo (9g) | 180-degree sensor panning mount |
| Power | Logic Supply | 5V / 2.4A Power Bank | Regulated power for Raspberry Pi and Arduino |
| Power | Motor Supply | 11.1V - 12V Li-ion Battery Pack | Dedicated high-current supply for L298N |

---

## Wiring and Pinout Reference

### Raspberry Pi to Arduino Interface

| Raspberry Pi Pin / Port | Arduino UNO Pin / Port | Connection Type | Function |
| :--- | :--- | :--- | :--- |
| Micro-USB Data Port (OTG) | USB Type-B Port | USB-A to Micro-USB / USB-B | Full-duplex Serial (115200 baud) and 5V power |

### Raspberry Pi to Thermal Camera Interface

| Raspberry Pi Header Pin | MLX90640 Pin | Function |
| :--- | :--- | :--- |
| Pin 1 (3.3V Power) | VCC / VIN | 3.3V DC Power Supply |
| Pin 3 (GPIO 2 / I2C SDA) | SDA | I2C Data Line |
| Pin 5 (GPIO 3 / I2C SCL) | SCL | I2C Clock Line (400 kHz) |
| Pin 9 (Ground) | GND | Common Ground |

### Arduino to L298N Motor Driver

| Arduino UNO Pin | L298N Pin | Function | Logic High Action |
| :--- | :--- | :--- | :--- |
| Digital Pin 2 | IN1 | Left Motor Forward | Rotates left motors forward |
| Digital Pin 3 | IN2 | Left Motor Reverse | Rotates left motors reverse |
| Digital Pin 4 | IN3 | Right Motor Forward | Rotates right motors forward |
| Digital Pin 5 | IN4 | Right Motor Reverse | Rotates right motors reverse |

### Arduino to Sensors and Actuators

| Arduino UNO Pin | Target Device | Device Pin | Description |
| :--- | :--- | :--- | :--- |
| Analog Pin A0 | MQ-2 Gas Sensor | AOUT | Analog output for combustible gases |
| Analog Pin A1 | MQ-135 Gas Sensor | AOUT | Analog output for air quality/toxins |
| Analog Pin A2 | MQ-136 Gas Sensor | AOUT | Analog output for hydrogen sulfide |
| Digital Pin 6 | HC-SR04 Ultrasonic | TRIG | Ultrasonic pulse trigger output |
| Digital Pin 7 | HC-SR04 Ultrasonic | ECHO | Ultrasonic pulse echo input |
| Digital Pin 11 | SG90 Servo | Signal (PWM) | Servo position control line |
| 5V Pin | Sensor Rail | VCC | 5V regulated power to sensors and servo |
| GND Pin | Common Ground Rail | GND | Reference ground |

---

## Power Distribution and Grounding

To prevent voltage dips, inductive noise, and brownouts caused by motor stall currents:

1. **Motor Power Rail:** An external 11.1V - 12V lithium-ion battery connects directly to the L298N terminal block (`12V` and `GND`).
2. **Logic Power Rail:** A dedicated 5V power bank feeds the Raspberry Pi Zero 2W through its PWR IN micro-USB port. The Pi powers the Arduino through the USB data link.
3. **Common Ground:** All ground lines (Li-ion battery negative terminal, L298N GND terminal, Arduino GND, and Raspberry Pi GND) must be connected to a shared ground reference.

---

## Communication Protocol

### Serial Telemetry Format

The Arduino sends ASCII telemetry strings over serial every 200 ms:

```
GAS1:<val>,GAS2:<val>,GAS3:<val>,DIST:<val>,MODE:<mode>
```

- `GAS1`: Raw 10-bit ADC reading from MQ-2 (0 - 1023).
- `GAS2`: Raw 10-bit ADC reading from MQ-135 (0 - 1023).
- `GAS3`: Raw 10-bit ADC reading from MQ-136 (0 - 1023).
- `DIST`: Measured distance in centimeters (returns 999 if no echo received).
- `MODE`: Operating mode identifier (`A` for Autonomous, `M` for Manual).

### Serial Command Format

The Raspberry Pi sends newline-terminated ASCII control strings to the Arduino:

| Command String | Description | Action |
| :--- | :--- | :--- |
| `MODE:A` | Switch to Autonomous Mode | Enables autonomous obstacle avoidance routine |
| `MODE:M` | Switch to Manual Mode | Stops motors and waits for manual commands |
| `CMD:F` | Drive Forward | Actuates both motor banks forward (Manual mode only) |
| `CMD:B` | Drive Backward | Actuates both motor banks in reverse (Manual mode only) |
| `CMD:L` | Turn Left | Counter-rotates tracks/wheels left (Manual mode only) |
| `CMD:R` | Turn Right | Counter-rotates tracks/wheels right (Manual mode only) |
| `CMD:S` | Stop / Brake | Disengages all motor outputs |

### REST API Endpoints

The Flask server provides the following endpoints:

| Endpoint | Method | Payload / Format | Response | Description |
| :--- | :--- | :--- | :--- | :--- |
| `/` | `GET` | None | HTML | Serves the browser dashboard |
| `/video_feed` | `GET` | None | `multipart/x-mixed-replace` | MJPEG video stream from thermal camera |
| `/api/telemetry` | `GET` | None | JSON | Returns current gas readings, distance, and mode |
| `/api/command` | `POST` | `{"command": "<CMD_STRING>"}` | JSON | Forwards control command to Arduino |
| `/api/shutdown` | `POST` | None | JSON | Executes system shutdown (`sudo poweroff`) |

---

## Navigation and Obstacle Avoidance Logic

When running in Autonomous Mode (`MODE:A`), the navigation loop operates as follows:

1. **Clearance Check:** Measures frontal distance using the ultrasonic sensor.
2. **Forward Motion:** If distance is greater than 30 cm, the rover moves forward.
3. **Obstacle Response:** If distance drops below or equal to 30 cm:
   - Vehicle halts immediately.
   - Servo rotates the sensor to 150 degrees (left scan) and records distance.
   - Servo rotates the sensor to 30 degrees (right scan) and records distance.
   - Servo returns to 90 degrees (center).
   - If left distance exceeds right distance and is greater than 30 cm, turn left for 500 ms.
   - If right distance exceeds left distance and is greater than 30 cm, turn right for 500 ms.
   - If both directions are obstructed, reverse for 600 ms, turn left for 500 ms, and re-evaluate.

---

## Thermal Imaging Pipeline

The MLX90640 thermal imaging processing pipeline includes:

1. **Data Acquisition:** Reads 768 temperature values (24x32 array) at 4 Hz over I2C.
2. **Outlier Filtering:** Computes the 3rd and 97th percentiles to reject bad or saturated pixels.
3. **Dynamic Normalization:** Clamps values within the percentile boundaries and scales to 8-bit unsigned integer values (0 - 255).
4. **Color Mapping:** Applies OpenCV's `COLORMAP_INFERNO` for visual temperature gradients.
5. **Spatial Filtering & Upscaling:** Applies a 5x5 Gaussian blur and bicubic interpolation to upscale the matrix from 32x24 to 640x480 resolution.
6. **Annotation & Streaming:** Overlays maximum detected temperature and encodes frames into JPEG format for real-time HTTP streaming.

---

## Installation and Setup

### 1. Arduino Firmware Setup

1. Connect the Arduino UNO to your workstation via USB.
2. Open `arduino.ino` in the Arduino IDE.
3. Ensure the `Servo` library is installed (included by default in Arduino IDE).
4. Select **Board:** "Arduino Uno" and select the corresponding serial port.
5. Click **Upload** to flash the firmware.

### 2. Raspberry Pi Configuration

1. Install Raspberry Pi OS Lite (64-bit recommended) on the microSD card.
2. Enable I2C and set the clock speed to 400 kHz:
   ```bash
   sudo raspi-config nonint do_i2c 0
   ```
3. Add the following line to `/boot/config.txt` (or `/boot/firmware/config.txt` on newer OS releases):
   ```ini
   dtparam=i2c_arm=on,i2c_arm_baudrate=400000
   ```
4. Reboot the Raspberry Pi:
   ```bash
   sudo reboot
   ```

### 3. Python Environment and Dependencies

Install system packages and Python dependencies:

```bash
# Update package lists
sudo apt update && sudo apt install -y python3-pip python3-opencv i2c-tools

# Clone the repository
git clone https://github.com/iamshresthraj/Project-Nirvan.git
cd Project-Nirvan

# Install required Python packages
pip3 install -r requirements.txt
```

Verify that the I2C thermal camera is detected at address `0x33`:

```bash
i2cdetect -y 1
```

### 4. Running the Application

Start the Flask server:

```bash
python3 app.py
```

To run the application automatically at boot, create a systemd service:

```ini
# /etc/systemd/system/nirvan.service
[Unit]
Description=Project Nirvan Inspection Robot Service
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/Project-Nirvan
ExecStart=/usr/bin/python3 /home/pi/Project-Nirvan/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable nirvan.service
sudo systemctl start nirvan.service
```

---

## Web Dashboard and Controls

Access the web interface by navigating to `http://<raspberry-pi-ip>:5000` in any web browser on the local network.

### Dashboard Modules

- **Thermal Vision Feed:** Displays live heat signature with temperature overlays.
- **Environmental Gas Trends:** Dynamic line chart tracking MQ-2, MQ-135, and MQ-136 sensor outputs.
- **Safety Status Banner:**
  - **Atmosphere Normal:** Gas readings below 350 ADC.
  - **Elevated Gas Levels Detected:** Gas readings between 350 and 650 ADC.
  - **Toxic Environment / Danger:** Gas readings exceed 650 ADC.
- **KPI Metrics:** Displays current navigation mode, obstacle clearance distance, and sensor channel values.

### Keyboard Controls (Manual Mode)

| Key | Action |
| :--- | :--- |
| `W` | Drive Forward (`CMD:F`) |
| `A` | Turn Left (`CMD:L`) |
| `S` | Drive Backward (`CMD:B`) |
| `D` | Turn Right (`CMD:R`) |
| `Space` | Emergency Stop / Brake (`CMD:S`) |

---

## Repository Structure

```
Project-Nirvan/
├── .gitignore          # Git ignore configuration for Python and embedded files
├── README.md           # Technical documentation and system manual
├── app.py              # Flask server, thermal camera pipeline, and web dashboard
├── arduino.ino         # Arduino firmware for motor control, sensing, and telemetry
└── requirements.txt    # Python package dependencies
```

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.
