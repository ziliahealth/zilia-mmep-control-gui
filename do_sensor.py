import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from mcu import MCUCommands
from collections import deque
import os
from do_sensor_calibration.clarke_electrode import ClarkeElectrode, DataProcessor, load_vapor_pressure_func
from do_sensor_calibration.blood_oxygen_dissociation_models import HemoglobinDissociationDash2010

class DOCommands(MCUCommands):
    #DO Sensor Commands
    DO_START = '$DOSSR,START,'
    DO_STOP = '$DOSSR,STOP,'
    DO_HELP = '$DOSSR,HELP,'
    DO_INFO = '$DOSSR,INFO,'
    def start_stop(self, start=True):
        """Starts or stops DO sensor readings."""
        base_command = DOCommands.DO_START if start else DOCommands.DO_STOP
        return self._format_command(base_command, [])

    def enable(self,target, enable=True):
        """Enables or disables DO sensor."""
        # This method seems to be a placeholder; if it needs to send a command,
        # it should be implemented similarly to the others.
        pass

    def info(self):
        """Requests information from the DO sensor."""
        return self._format_command(DOCommands.DO_INFO, [])

    def help(self):
        """Requests help information from the DO sensor."""
        return self._format_command(DOCommands.DO_HELP, [])


class DOSensorThread(QThread):
    # Signal now emits the command string and its unique communication ID
    mcu_signal = pyqtSignal(str, str)
    update_plot_signal = pyqtSignal()  # Signal containing data to be logged and plotted
    commands = DOCommands()
    num_sensors = 2  # Number of DO sensors
    buffer_size = 10000 # Size of the FIFO buffer for each sensor

    def __init__(self):
        super().__init__()
        self.do_sensors = []
        for i in range(self.num_sensors):
            self.do_sensors.append(do_sensor(i+1, f"DO Sensor {i+1}", self.buffer_size))

    def do_start_stop(self, start=True):
        command, com_id = self.commands.start_stop(start=start)
        #print(f"DO Thread: Queuing command {com_id}")
        self.mcu_signal.emit(command, com_id)

    def do_info(self):
        command, com_id = self.commands.info()
        #print(f"DO Thread: Queuing command {com_id}")
        self.mcu_signal.emit(command, com_id)

    def do_help(self):
        command, com_id = self.commands.help()
        #print(f"DO Thread: Queuing command {com_id}")
        self.mcu_signal.emit(command, com_id)

    def do_enable(self,target_id, enable=True):
        # This method only changes internal state. It does not send a command.
        self.do_sensors[target_id].set_enable(enable)

    def process_do_serial_data(self, data:list):
        # Process the incoming DO sensor data
        # convert time from ms to seconds
        for i, sensor in enumerate(self.do_sensors):
            if sensor.enabled:
                sensor.add_raw_data((data[0]), (data[i+1]))
        # Emit a signal
        if any(sensor.enabled for sensor in self.do_sensors):
            self.update_plot_signal.emit()

    def clear_buffers(self):
        for sensor in self.do_sensors:
            sensor.raw_data_buffer.clear()
            sensor.partial_pressure_buffer.clear()
            sensor.saturation_buffer.clear()
            sensor.time_buffer.clear()

    def update_last_temperature(self, data: list):
        for i in len(data):
            index = data[i]
            temperature = data [i+1]
            for sensor in self.do_sensors:
                if sensor.number == index:
                    sensor.update_temperature(temperature)

    def update_dissociation_parameters(self, pH: float, pCO2:float):
        for sensor in self.do_sensors:
            sensor.update_hemoglobin_parameters(pH=pH, pCO2=pCO2, DPG=None, Hct=None)
        print(sensor.hemoglobin_model.pH, sensor.hemoglobin_model.pCO2)

class do_sensor:
    def __init__(self,number,name,buffer_size):
        self.number = number
        self.name = name
        self.enabled = False
        self.buffer_size = buffer_size
        self.raw_data_buffer = deque(maxlen=buffer_size)
        self.partial_pressure_buffer = deque(maxlen=buffer_size)
        self.saturation_buffer = deque(maxlen=buffer_size)
        self.time_buffer = deque(maxlen=buffer_size)
        self.temperature_celsius = 25.0  # Default temperature for saturation calculation
        self.hemoglobin_model = HemoglobinDissociationDash2010()
        self.processor = DataProcessor()
        print(os.getcwd())
        vapor_pressure_func = load_vapor_pressure_func(r"do_sensor_calibration/water_vapor_pressure.csv")
        self.clarke_electrode = ClarkeElectrode(vapor_pressure_func=vapor_pressure_func)
        self.temperature_celsius = None  # Current temperature for calibration

    def set_enable(self,enable):
        self.enabled = enable


    def add_data(self, time_ms: int, raw_voltage: float):
        # Simply append; deque handles discarding the oldest element
        self.raw_data_buffer.append(raw_voltage)
        self.time_buffer.append(self.ms_to_elapsed_seconds(time_ms))
        self.add_calibrated_data(raw_voltage)

    def add_calibrated_data(self, raw_voltage: float):
        if self.clarke_electrode.is_calibrated and self.temperature_celsius is not None:
            po2 = self.clarke_electrode.get_po2(temperature=self.temperature_celsius, measured_voltage=raw_voltage)
            self.partial_pressure_buffer.append(po2)
            so2 = self.hemoglobin_model.calculate_sO2(po2, temperature=self.temperature_celsius)
            self.saturation_buffer.append(so2)
    def deque_to_numpy(self):
        """Helper to get a NumPy array view of the data."""
        return np.array(self.raw_data_buffer)

    def ms_to_elapsed_seconds(self, ms):
        return ms / 1000.0

    def compute_partial_pressure(self, raw_voltage):
        #placeholder conversion to partial pressure
        return raw_voltage * 10.0
    def update_hemoglobin_parameters(self,pH: float = None, pCO2: float = None, DPG: float = None, Hct: float = None):
        self.hemoglobin_model.set_parameters(pH=pH, pCO2=pCO2, DPG=DPG, Hct=Hct)

    def update_temperature(self, temperature_celsius: float):
        self.temperature_celsius = temperature_celsius