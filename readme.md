# MMEP Control GUI
## Overview
The MMEP Control GUI is a comprehensive desktop application built with PyQt5 for controlling and monitoring the experimental setup for Microfluidic Multilayer Eye Phantom (MMEP) experiments at Zilia. It provides a real-time interface for managing multiple flow controllers, temperature controllers, and dissolved oxygen (DO) sensors. The application is designed to be the central hub for running experiments, whether they are controlled manually or fully automated through the sequential scripting functionality.

The GUI is designed to operate with the Zilia MMEP PCB Rev 1.1 and its dedicated firmware.

The system is built on a multithreaded architecture, ensuring that the user interface remains fluid and responsive at all times, even while handling intensive data logging and hardware communication in the background.

## Core Functionalities
The application's workflow is centered around a few key high-level functionalities:

### 1. Manual Instrument Control
The main window serves as an interactive dashboard for direct, real-time control of all connected hardware. It is divided into panels for each type of instrument, offering detailed configuration and operational modes.

#### Flow Controllers:
The GUI provides granular control over four independent pump channels.

Pump Type Configuration: Each channel can be configured to control either a Syringe Pump or a Peristaltic Pump.

For syringe pumps, users must input the syringe's inner diameter and the pump's lead screw pitch.

For peristaltic pumps, the tube's inner diameter and a calibration factor are required.

#### Operation Modes:

Constant Mode: An open-loop mode where the pump motor operates at a fixed speed calculated to correspond to the target flow rate. This mode is simple and direct.

PID Mode: A closed-loop feedback mode that requires an associated flow sensor to be active. The system continuously compares the measured flow rate to the target setpoint and uses a PID (Proportional-Integral-Derivative) algorithm to dynamically adjust the pump's speed to minimize the error. The KP, KI, and KD gains can be tuned for optimal performance.

Dispense Volume: A one-shot function to dispense a precise, user-defined volume at a specified flow rate. The volume dispensing and calculation is handled on the firmware.

#### Temperature Controllers:
Two independent heater channels can be managed.

Target Temperature: Users can define a precise temperature setpoint in degrees Celsius.

PID Control: The heating elements are managed by a PID controller. The KP, KI, and KD parameters can be adjusted to control how quickly the system reaches the setpoint and to minimize overshoot.

#### General Controls:

Enable Checkboxes: Every flow and temperature controller has an "Enable" checkbox. Checking this box activates the controller, starting the pump motor or the heater. Unchecking it stops the operation.

Sensor Toggles: Each controller also has an associated "Sensor" toggle. Activating this begins data acquisition from the corresponding sensor, which is required for PID mode and for live data plotting.

All changes made in the control panels are sent to the hardware immediately, providing instantaneous and fine-grained manual control over the entire experimental setup.

### 2. Live Data Monitoring & Visualization
Three real-time graphs provide instant visual feedback on the state of the system:

Flow Rate Plot: Displays the measured flow from any enabled flow sensors.

Temperature Plot: Tracks the temperature from the enabled thermal sensors.

DO Sensor Plot: Shows the readings from the dissolved oxygen sensors.

A Logger presents information about ongoing operations and errors to the user.

These plots allow for at-a-glance monitoring of the experiment's progress and stability.

### 3. Automated Experiment Sequences
For complex or lengthy experiments, the application supports full automation via simple script files.

Protocol Scripting: Users can define a sequence of experimental steps in a human-readable .toml file. Events can include start_logging, set_flow_rate, set_temperature, enable_pump, delay, and even commands to start and stop data logging. The .toml file structure and a list of currently implemented event types can be found in exemple_sequence.toml.

Execution: By clicking "Load Sequence", the user can select their script, and the SequenceRunner module will execute each step in order, automatically controlling the hardware and providing status updates to the log.

### 4. Comprehensive Data Management
The application provides a robust system for logging and reviewing experimental data.

Data Logging: At any point, either manually or via a sequence command, the user can start logging. All incoming data from every active sensor is saved into a single, organized .csv file. The file is cleanly structured with commented sections for Flow, Temperature, and DO data, making it easy to parse.

Data Review: To be implemented.

### 5. Setup Persistence (Configurations)
To ensure reproducibility, the entire state of the control panel can be saved and loaded.

Save Configuration: Saves all current setpoints, PID values, pump settings, and selections into an .ini file.

Load Configuration: Restores the GUI to a previously saved state, instantly setting up the hardware for a replicated experiment.

### 6. DO Sensor Calibration
To be implemented.

System Architecture: Threading and Signals
The application's responsiveness is achieved through a multi-layered, multithreaded architecture using PyQt's QThread and signal/slot mechanism. This ensures that the user interface remains fast and responsive while backend processes handle complex logic and communication.

Main Thread: This thread is exclusively for the User Interface. It handles all user interactions (button clicks, text input) and dispatches tasks to other threads by emitting signals. It never performs slow operations, ensuring the GUI never freezes.

Controller Threads (FlowControllerThread, TemperatureControllerThread, DOSensorThread): These high-level threads manage the state and logic for their respective hardware. For example, FlowControllerThread holds the setpoints, PID values, and data buffers for all four flow controllers. When a user changes a setting in the GUI:

A signal from the Main Thread is sent to a slot in the appropriate controller thread.

The controller thread updates its internal state and formats a command string for the microcontroller.

Crucially, it does not communicate with the hardware directly. Instead, it emits an mcu_signal containing the formatted command string.

MCU Worker Thread: This is the dedicated, low-level communication thread. It has a slot connected to the mcu_signal from all controller threads. Its sole responsibility is to manage the serial port. It receives command strings, adds them to a queue, sends them sequentially, and waits for acknowledgements from the hardware. This isolates all direct hardware interaction into one managed place.

Data Flow and UI Updates:

When the MCU sends back data (e.g., $FLOW,...), the MCU Worker Thread parses it and emits a data-specific signal (e.g., flow_data_signal).

This signal is connected to a slot in the corresponding Controller Thread, which processes the data and stores it in a buffer.

The Controller Thread then emits an update_plot_signal.

A dedicated GUIUpdater Thread listens for these update signals and redraws the plots with the new data from the controller's buffer.

This decoupled, signal-based architecture ensures a smooth, non-blocking flow of information, from user action to hardware command and back to the user's screen.