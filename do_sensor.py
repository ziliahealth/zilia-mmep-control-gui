import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from mcu_cmd import MCUCommands

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
    data_signal = pyqtSignal(list)  # Signal containing data to be logged and plotted
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
        self.do_sensors[target_id-1].set_enable(enable)
        print(self.do_sensors[target_id-1].enabled)

    def process_do_serial_data(self, data:list):
        # Process the incoming DO sensor data
        #convert time from ms to seconds
        for i, sensor in enumerate(self.do_sensors):
            if sensor.enabled:
                sensor.add_data((data[0]), (data[i+1]))



class do_sensor:
    def __init__(self,number,name,buffer_size):
        self.number = number
        self.name = name
        self.enabled = False
        self.calibrated = False
        self.buffer_size = buffer_size
        self.raw_data_buffer = np.zeros(buffer_size)
        self.partial_pressure_buffer = np.zeros(buffer_size)
        self.saturation_buffer = np.zeros(buffer_size)
        self.time_buffer = np.zeros(buffer_size)

    def set_enable(self,enable):
        self.enabled = enable

    def set_calibrated(self, calibrated):
        self.calibrated = calibrated

    def add_data(self, time_ms: int, raw_voltage: float):
        time_s = self.ms_to_elapsed_seconds(time_ms)
        # add data to fifo buffer
        self.raw_data_buffer = np.roll(self.raw_data_buffer, -1)
        self.raw_data_buffer[-1] = raw_voltage
    def ms_to_elapsed_seconds(self, ms):
            return ms / 1000.0