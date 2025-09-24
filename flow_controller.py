### High level commands class for the control of the syringe flow_controller
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from mcu_cmd import MCUCommands
import serial
import time
import sys
import os
import numpy as np


class FlowControllerCommands(MCUCommands):
    # Class that defines flow controller related commands understood by the microcontroller
    # Includes methods to generate the commands with the correct format
    FLOW_START = '$FLOWCTRL,START,'
    FLOW_STOP = '$FLOWCTRL,STOP,'
    FLOW_MODE_PID = '$FLOWCTRL,SET_MODE_PID,'
    FLOW_MODE_CONSTANT = '$FLOWCTRL,SET_MODE_CONSTANT,'
    FLOW_SET_FLOWRATE = '$FLOWCTRL,SET_FLOWRATE,'
    FLOW_SSR_ENABLE = '$FLOWCTRL,SSR_ENABLE,'
    FLOW_SSR_DISABLE = '$FLOWCTRL,SSR_DISABLE,'
    FLOW_SSR_RESET = '$FLOWCTRL,SSR_RESET,'
    FLOW_CONT_READ_ON = '$FLOWCTRL,CONT_FLOWRATE_ON,'
    FLOW_CONT_READ_OFF = '$FLOWCTRL,CONT_FLOWRATE_OFF,'
    FLOW_SET_PUMP_SETTINGS = '$FLOWCTRL,SET_PUMP_SETTINGS,'
    FLOW_SET_PID = '$FLOWCTRL,SET_PID_SETTINGS,'
    FLOW_START_DISPENSE = '$FLOWCTRL,START_DISPENSE,'
    FLOW_STOP_DISPENSE = '$FLOWCTRL,STOP_DISPENSE,'
    FLOW_INFO = '$FLOWCTRL,INFO,'
    FLOW_HELP = '$FLOWCTRL,HELP,'

    # ----- Flow Controller Methods -----
    def start_stop(self, targets: int, start=True):
        """Generates the command to start or stop flow controllers."""
        if not (0 <= targets <= 15):
            raise ValueError("Targets must be an integer between 0 and 15.")
        base_command = self.FLOW_START if start else self.FLOW_STOP
        return self._format_command(base_command, [targets])

    def set_mode(self, targets: int, is_pid: bool):
        """Sets the operation mode for the flow controllers."""
        if not (0 <= targets <= 15):
            raise ValueError("Targets must be an integer between 0 and 15.")
        base_command = self.FLOW_MODE_PID if is_pid else self.FLOW_MODE_CONSTANT
        return self._format_command(base_command, [targets])

    def set_flowrate(self, targets: int, flowrates: float):
        """Sets the target flow rate for one or more controllers."""
        if not (0 <= targets <= 15):
            raise ValueError("Targets must be an integer between 0 and 15.")
        if not isinstance(flowrates, list):
            flowrates = [flowrates]
        args = [targets] + flowrates
        return self._format_command(self.FLOW_SET_FLOWRATE, args)

    def ssr_enable_disable(self, targets: int, enable=True):
        """Enables or disables the flow sensor reading."""
        if not (0 <= targets <= 15):
            raise ValueError("Targets must be an integer between 0 and 15.")
        base_command = self.FLOW_SSR_ENABLE if enable else self.FLOW_SSR_DISABLE
        return self._format_command(base_command, [targets])

    def ssr_reset(self):
        """Resets all flow sensors."""
        return self._format_command(self.FLOW_SSR_RESET, [])

    def continuous_read(self, on=True):
        """Toggles continuous serial transmission of flow readings."""
        base_command = self.FLOW_CONT_READ_ON if on else self.FLOW_CONT_READ_OFF
        return self._format_command(base_command, [])

    def pump_settings(self, targets, pump_type: str, param1: float, param2: float):
        """Configures the settings for a specific pump type."""
        if not (0 <= targets <= 15):
            raise ValueError("Targets must be an integer between 0 and 15.")
        if pump_type.upper() not in ["PERISTALTIC", "SYRINGE"]:
            raise ValueError("Pump type must be 'PERISTALTIC' or 'SYRINGE'.")
        args = [targets, pump_type.upper(), param1, param2]
        return self._format_command(self.FLOW_SET_PUMP_SETTINGS, args)

    def set_pid(self, targets, kp: float, ki: float, kd:float):
        """Sets the PID gains for flow controllers."""
        if not (0 <= targets <= 15):
            raise ValueError("Targets must be an integer between 0 and 15.")
        args = [targets, kp, ki, kd]
        return self._format_command(self.FLOW_SET_PID, args)

    def continuous_read(self, on=True):
        """Toggles continuous serial transmission of flow readings."""
        base_command = self.FLOW_CONT_READ_ON if on else self.FLOW_CONT_READ_OFF
        return self._format_command(base_command, [])

    def info(self, targets: int):
        """Requests information about specified flow controllers."""
        if not (0 <= targets <= 15):
            raise ValueError("Targets must be an integer between 0 and 15.")
        return self._format_command(self.FLOW_INFO, [targets])

    def help(self):
        """Requests help information about flow controller commands."""
        return self._format_command(self.FLOW_HELP, [])

    def start_dispense(self, targets: int,volume_to_dispense: float, flowrate: float):
        """Starts a dispensing operation for specified flow controllers."""
        if not (0 <= targets <= 15):
            raise ValueError("Targets must be an integer between 0 and 15.")
        return self._format_command(self.FLOW_START_DISPENSE, [targets, volume_to_dispense, flowrate])
    def stop_dispense(self, targets: int):
        """Stops a dispensing operation for specified flow controllers."""
        if not (0 <= targets <= 15):
            raise ValueError("Targets must be an integer between 0 and 15.")
        return self._format_command(self.FLOW_STOP_DISPENSE, [targets])


class FlowControllerThread(QThread):
    mcu_signal = pyqtSignal(str)
    commands = FlowControllerCommands()

    # QThread object to receive user inputs from the GUI and send formatted flow_controller commands to the mcu thread
    def __init__(self):
        super().__init__()
        self.num_flow_controllers = 4
        self.flow_controllers = []
        self.continuous_reading = False
        for i in range(self.num_flow_controllers):
            # convert i to 4 bit representation of flow controller to target (0001,0010,0100,1000)
            self.flow_controllers.append(flow_controller(2 ** i))

    def set_pump_type(self, flow_controller_index, pump_type):
        """Sets the pump type for a specific flow controller."""
        self.flow_controllers[flow_controller_index].set_pump_type(pump_type)

    def set_flowrate(self, flow_controller_index, flowrate):
        # Set the flow rate of a flow_controller
        if flowrate:
            self.flow_controllers[flow_controller_index].set_flowrate(flowrate)
        target = self.flow_controllers[flow_controller_index].num
        message = self.commands.set_flowrate(target, self.flow_controllers[flow_controller_index].flowrate)
        print(message)
        self.mcu_signal.emit(message)

    def set_mode(self, flow_controller_index, mode=None):
        # Set the mode of a flow_controller
        if mode:
            self.flow_controllers[flow_controller_index].set_mode(mode)
        target = self.flow_controllers[flow_controller_index].num
        if self.flow_controllers[flow_controller_index].mode == 'PID':
            message = self.commands.set_mode(target, 1)
        elif self.flow_controllers[flow_controller_index].mode == 'Constant':
            message = self.commands.set_mode(target, 0)
        else:
            raise ValueError('Invalid mode. Mode must be "pid" or "constant".')
        print(message)
        self.mcu_signal.emit(message)

    def set_sensor(self, flow_controller_index, sensor):
        # Set the sensor of a flow_controller

        self.flow_controllers[flow_controller_index].set_parameters(sensor=sensor)
        target = self.flow_controllers[flow_controller_index].num
        message = self.commands.ssr_enable_disable(target, sensor)
        print(message)
        self.mcu_signal.emit(message)

        any_sensor_enabled = any(fc.sensor == 1 for fc in self.flow_controllers)
        print(any_sensor_enabled, self.continuous_reading)
        time.sleep(1)
        if any_sensor_enabled and not self.continuous_reading:
            command = self.commands.continuous_read(on=True)
            self.mcu_signal.emit(command)
            self.continuous_reading = True
        elif not any_sensor_enabled and self.continuous_reading:
            command = self.commands.continuous_read(on=False)
            self.mcu_signal.emit(command)
            self.continuous_reading = False
    def set_pid(self, flow_controller_index, Ki=None, Kp=None, Kd=None):
        # Set the PID parameters of a flow_controller
        if Ki:
            self.flow_controllers[flow_controller_index].set_pid(Ki=Ki)
        if Kp:
            self.flow_controllers[flow_controller_index].set_pid(Kp=Kp)
        if Kd:
            self.flow_controllers[flow_controller_index].set_pid(Kd=Kd)
        target = self.flow_controllers[flow_controller_index].num
        message = self.commands.set_pid(target,
                                        self.flow_controllers[flow_controller_index].Ki,
                                        self.flow_controllers[flow_controller_index].Kp,
                                        self.flow_controllers[flow_controller_index].Kd)
        print(message)
        self.mcu_signal.emit(message)

    def set_parameters_syringe(self, flow_controller_index, diameter=None, thread_pitch=None):
        # Set the diameter of a flow_controller
        if diameter:
            self.flow_controllers[flow_controller_index].set_parameters(diameter=diameter)
        if thread_pitch:
            self.flow_controllers[flow_controller_index].set_parameters(thread_pitch=thread_pitch)
        target = self.flow_controllers[flow_controller_index].num
        message = self.commands.pump_settings(target, 'SYRINGE',
                                              self.flow_controllers[flow_controller_index].diameter,
                                              self.flow_controllers[flow_controller_index].thread_pitch)
        print(message)
        self.mcu_signal.emit(message)

    def set_parameters_peristaltic(self, flow_controller_index, tube_diameter=None, calibration=None):
        # Set the tube diameter and calibration factor of a peristaltic flow_controller
        if tube_diameter:
            self.flow_controllers[flow_controller_index].set_parameters(tube_diameter=tube_diameter)
        if calibration:
            self.flow_controllers[flow_controller_index].set_parameters(peristaltic_cal=calibration)
        target = self.flow_controllers[flow_controller_index].num  # Corrected from flow_controller_index
        message = self.commands.pump_settings(target, 'PERISTALTIC',
                                              self.flow_controllers[flow_controller_index].tube_diameter,
                                              self.flow_controllers[flow_controller_index].peristaltic_calibration)
        print(message)
        self.mcu_signal.emit(message)

    def start_stop(self, flow_controller_index, start=True):
        # Start or stop a flow_controller
        self.flow_controllers[flow_controller_index].set_active(start)
        target = self.flow_controllers[flow_controller_index].num  # Corrected from flow_controller_index
        message = self.commands.start_stop(target, start)
        print(message)
        self.mcu_signal.emit(message)

    def reset_sensors(self):
        # Reset all flow sensors
        message = self.commands.ssr_reset()
        print(message)
        self.mcu_signal.emit(message)

    def continuous_read(self, on=True):
        # Toggle continuous serial transmission of flow readings
        message = self.commands.continuous_read(on)
        print(message)
        self.mcu_signal.emit(message)

        any_sensor_enabled = any(fc.sensor == 1 for fc in self.flow_controllers)

        if any_sensor_enabled and not self.continuous_reading:
            command = self.commands.continuous_read(on=True)
            self.mcu_signal.emit(command)
            self.continuous_reading = True

        elif not any_sensor_enabled and self.continuous_reading:
            command = self.commands.continuous_read(on=False)
            self.mcu_signal.emit(command)
            self.continuous_reading = False

    def start_dispense(self, flow_controller_index, volume_to_dispense, flowrate):
        # Start a dispensing operation for a flow_controller
        target = self.flow_controllers[flow_controller_index].num
        message = self.commands.start_dispense(target, volume_to_dispense, flowrate)
        print(message)
        self.mcu_signal.emit(message)

    def stop_dispense(self, flow_controller_index):
        # Stop a dispensing operation for a flow_controller
        target = self.flow_controllers[flow_controller_index].num
        message = self.commands.stop_dispense(target)
        print(message)
        self.mcu_signal.emit(message)

    def set_all(self, flow_controller_index):
        # method that sends signals to the mcu to send all the current parameters of a flow_controller
        # Used after the connection with the mcu is established
        self.set_mode(flow_controller_index)
        self.set_flow(flow_controller_index, self.flow_controllers[flow_controller_index].flowrate)
        self.set_sensor(flow_controller_index, self.flow_controllers[flow_controller_index].sensor)
        if self.flow_controllers[flow_controller_index].pump_type == pump_types.syringe:
            self.set_parameters_syringe(flow_controller_index)
        elif self.flow_controllers[flow_controller_index].pump_type == pump_types.peristaltic:
            self.set_parameters_peristaltic(flow_controller_index)
        self.set_pid(flow_controller_index)


class pump_types:
    # Enum for pump types - Use strings to match GUI
    syringe = 'Syringe'
    peristaltic = 'Peristaltic'
    none = 'None'


class flow_controller:
    # Object to set and manage flow_controller properties
    def __init__(self, flow_controller_index):
        self.name = f'flow_controller{flow_controller_index}'
        self.num = flow_controller_index
        self.pump_type: str = pump_types.syringe
        self.mode = 'Constant'  # or 'PID'
        self.flowrate = 0
        self.active = False
        self.diameter = 12.4  # mm
        self.thread_pitch = 0.7  # mm
        self.tube_diameter = 0.7  # mm
        self.peristaltic_calibration = 1  # calibration factor for peristaltic pumps
        self.sensor = 0
        self.Kp = 0
        self.Ki = 0
        self.Kd = 0

    def set_mode(self, mode):
        if mode in ['pid', 'constant', 'PID', 'Constant']:
            self.mode = mode

    def set_pump_type(self, pump_type):
        if pump_type in [pump_types.syringe, pump_types.peristaltic, pump_types.none]:
            self.pump_type = pump_type

    def set_flowrate(self, flowrate):
        self.flowrate = flowrate

    def set_pid(self, Ki=None, Kp=None, Kd=None):
        if Ki is not None:
            self.Ki = Ki
        if Kp is not None:
            self.Kp = Kp
        if Kd is not None:
            self.Kd = Kd

    def info(self):
        # print flow_controller properties
        print('----------------------')
        print(f'flow_controller {self.num} info:')
        print(f'flow_controller name: {self.name}')
        print(f'flow_controller mode: {self.mode}')
        print(f'flow_controller flow rate: {self.flowrate}')
        print(f'flow_controller active: {self.active}')
        print(f'Syringe diameter: {self.diameter}')
        print(f'flow_controller thread pitch: {self.thread_pitch}')
        print(f'flow_controller sensor: {self.sensor}')
        print(f'flow_controller Kp: {self.Kp}')
        print(f'flow_controller Ki: {self.Ki}')
        print(f'flow_controller Kd: {self.Kd}')
        print(f'----------------------')

    def set_parameters(self, sensor=None, diameter=None, thread_pitch=None, peristaltic_cal=None, tube_diameter=None,
                       name=None):
        if diameter is not None:
            self.diameter = diameter
        if thread_pitch is not None:
            self.thread_pitch = thread_pitch
        if name is not None:
            self.name = name
        if sensor is not None:
            self.sensor = sensor
        if tube_diameter is not None:
            self.tube_diameter = tube_diameter
        if peristaltic_cal is not None:
            self.peristaltic_calibration = peristaltic_cal

    def set_active(self, active):
        self.active = active