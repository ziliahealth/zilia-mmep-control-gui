import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from mcu_cmd import MCUCommands
from collections import deque

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
        pass

    def info(self):
        """Requests information from the DO sensor."""
        return self._format_command(DOCommands.DO_INFO, [])

    def help(self):
        """Requests help information from the DO sensor."""
        return self._format_command(DOCommands.DO_HELP, [])



class DOSensorThread(QThread):
    mcu_signal = pyqtSignal(str)  # Signal to send commands to MCU
    update_plot_signal = pyqtSignal()  # Signal containing data to be logged and plotted
    commands = DOCommands()
    num_sensors = 2  # Number of DO sensors
    buffer_size = 10000 # Size of the FIFO buffer for each sensor

    def __init__(self):
        super().__init__()  # Call the __init method of the base class
        self.do_sensors = []
        for i in range(self.num_sensors):
            self.do_sensors.append(do_sensor(i+1, f"DO Sensor {i+1}", self.buffer_size))

    def do_start_stop(self, start=True):
        if start:
            command = self.commands.start_stop(start=True)
        else:
            command = self.commands.start_stop(start=False)
        print(command)
        self.mcu_signal.emit(command)
    def do_info(self):
        command = self.commands.info()
        self.mcu_signal.emit(command)

    def do_help(self):
        command = self.commands.help()
        self.mcu_signal.emit(command)

    def do_enable(self,target_id, enable=True):
        self.do_sensors[target_id].set_enable(enable)

    def process_do_serial_data(self, data:list):
        # Process the incoming DO sensor data
        #convert time from ms to seconds
        for i, sensor in enumerate(self.do_sensors):
            if sensor.enabled:
                sensor.add_data((data[0]), (data[i+1]))
        # Emit a signal
        if any(sensor.enabled for sensor in self.do_sensors):
            self.update_plot_signal.emit()



class do_sensor:
    def __init__(self,number,name,buffer_size):
        self.number = number
        self.name = name
        self.enabled = False
        self.calibrated = False
        self.buffer_size = buffer_size
        self.raw_data_buffer = deque(maxlen=buffer_size)
        self.partial_pressure_buffer = deque(maxlen=buffer_size)
        self.saturation_buffer = deque(maxlen=buffer_size)
        self.time_buffer = deque(maxlen=buffer_size)
        self.temperature_celsius = 25.0  # Default temperature for saturation calculation

    def set_enable(self,enable):
        self.enabled = enable

    def set_calibrated(self, calibrated):
        self.calibrated = calibrated

    def add_data(self, time_ms: int, raw_voltage: float):
        # Simply append; deque handles discarding the oldest element
        self.raw_data_buffer.append(raw_voltage)
        self.time_buffer.append(self.ms_to_elapsed_seconds(time_ms))
        if self.calibrated:
            partial_pressure = self.compute_partial_pressure(raw_voltage)
            saturation = self.compute_saturation(partial_pressure, self.temperature_celsius)
            self.partial_pressure_buffer.append(partial_pressure)
            self.saturation_buffer.append(saturation)

    def deque_to_numpy(self):
        """Helper to get a NumPy array view of the data."""
        return np.array(self.raw_data_buffer)

    def ms_to_elapsed_seconds(self, ms):
        return ms / 1000.0

    def compute_partial_pressure(self, raw_voltage):
        #placeholder conversion to partial pressure
        return raw_voltage * 10.0

    def compute_saturation(self, partial_pressure, temperature_celsius):
        # Placeholder formula for saturation calculation
        saturation = (partial_pressure / 21.0) * 100.0
        # Simple temperature correction (not accurate, just for illustration)
        saturation *= (1 + 0.03 * (temperature_celsius - 25))
        return saturation