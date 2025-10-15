import time

from PyQt5.QtCore import QThread, pyqtSignal, QObject
from mcu import MCUCommands
from collections import deque


class TemperatureControllerCommands(MCUCommands):
    # Temperature Controller Commands
    TEMP_START = '$TEMPCTRL,START,'
    TEMP_STOP = '$TEMPCTRL,STOP,'
    TEMP_SET_TEMP = '$TEMPCTRL,SET_TEMP,'
    TEMP_SSR_ENABLE = '$TEMPCTRL,SSR_ENABLE,'
    TEMP_SSR_DISABLE = '$TEMPCTRL,SSR_DISABLE,'
    TEMP_SET_PID = '$TEMPCTRL,SET_PID_SETTINGS,'
    TEMP_INFO = '$TEMPCTRL,INFO,'
    TEMP_HELP = '$TEMPCTRL,HELP,'
    TEMP_CONT_TEMP_ON = '$TEMPCTRL,CONT_TEMP_ON,'
    TEMP_CONT_TEMP_OFF = '$TEMPCTRL,CONT_TEMP_OFF,'

    # ----- Temperature Controller Methods -----
    def temp_start_stop(self, targets, start=True):
        """Starts or stops temperature controllers."""
        if not (0 <= targets <= 3):
            raise ValueError("Targets must be an integer between 0 and 3.")
        base_command = self.TEMP_START if start else self.TEMP_STOP
        return self._format_command(base_command, [targets])

    def temp_ssr_enable_disable(self, targets, enable=True):
        """Enables or disables continuous temperature readings."""
        if not (0 <= targets <= 3):
            raise ValueError("Targets must be an integer between 0 and 3.")
        base_command = self.TEMP_SSR_ENABLE if enable else self.TEMP_SSR_DISABLE
        return self._format_command(base_command, [targets])

    def temp_set_temp(self, targets, temperature):
        """Sets the target temperature."""
        if not (0 <= targets <= 3):
            raise ValueError("Targets must be an integer between 0 and 3.")
        return self._format_command(self.TEMP_SET_TEMP, [targets, temperature])

    def temp_set_pid(self, targets, kp, ki, kd):
        """Sets the PID gains for temperature controllers."""
        if not (0 <= targets <= 3):
            raise ValueError("Targets must be an integer between 0 and 3.")
        args = [targets, kp, ki, kd]
        return self._format_command(self.TEMP_SET_PID, args)

    def temp_info(self, targets):
        """Requests information from the temperature controllers."""
        if not (0 <= targets <= 3):
            raise ValueError("Targets must be an integer between 0 and 3.")
        return self._format_command(self.TEMP_INFO, [targets])

    def temp_help(self):
        """Requests help information from the temperature controllers."""
        return self._format_command(self.TEMP_HELP, [])

    def continuous_read(self,on=True):
        """Toggles continuous serial transmission of temp readings."""
        base_command = self.TEMP_CONT_TEMP_ON if on else self.TEMP_CONT_TEMP_OFF
        return self._format_command(base_command, [])


class TemperatureControllerThread(QThread):
    # Signal now emits the command string and its unique communication ID
    mcu_signal = pyqtSignal(str, str)
    update_plot_signal = pyqtSignal()  # Signal containing data to be logged and plotted
    update_temperature_signal = pyqtSignal(list)
    commands = TemperatureControllerCommands()

    def __init__(self):
        super().__init__()
        self.num_temp_controllers = 2  # Number of temperature controllers
        self.temperature_controllers = []
        self.continuous_reading = False

        for i in range(self.num_temp_controllers):
            self.temperature_controllers.append(temperature_controller(f"TempCtrl_{i}", 2**i))

    def set_temperature(self, temp_controller_num, temperature):
        if self.temperature_controllers[temp_controller_num].temperature_limits[0] <= temperature <= self.temperature_controllers[temp_controller_num].temperature_limits[1]:
            #to implement: clamp displayed temperature to limits
            pass
        if 0 <= temp_controller_num < self.num_temp_controllers:
            self.temperature_controllers[temp_controller_num].set_temperature(temperature)
            target = self.temperature_controllers[temp_controller_num].num
            command, com_id = self.commands.temp_set_temp(target, self.temperature_controllers[temp_controller_num].temperature)
                #print(f"TC Thread: Queuing command {com_id}")
            self.mcu_signal.emit(command, com_id)
        else:
            raise ValueError("Invalid temperature controller number.")

    def set_enable(self, temp_controller_num, enable):
        if 0 <= temp_controller_num < self.num_temp_controllers:
            self.temperature_controllers[temp_controller_num].set_enable(enable)
            target = self.temperature_controllers[temp_controller_num].num
            command, com_id = self.commands.temp_start_stop(target, enable)
                #print(f"TC Thread: Queuing command {com_id}")
            self.mcu_signal.emit(command, com_id)
        else:
            raise ValueError("Invalid temperature controller number.")

    def set_pid(self, temp_controller_num, kp=None, ki=None, kd=None):
        if 0 <= temp_controller_num < self.num_temp_controllers:
            self.temperature_controllers[temp_controller_num].set_pid(kp, ki, kd)
            target = self.temperature_controllers[temp_controller_num].num
            command, com_id = self.commands.temp_set_pid(target,
                                                self.temperature_controllers[temp_controller_num].kp,
                                                self.temperature_controllers[temp_controller_num].ki,
                                                self.temperature_controllers[temp_controller_num].kd)
                #print(f"TC Thread: Queuing command {com_id}")
            self.mcu_signal.emit(command, com_id)
        else:
            raise ValueError("Invalid temperature controller number.")

    def set_sensor(self, temp_controller_num, sensor):
        if 0 <= temp_controller_num < self.num_temp_controllers:
            self.temperature_controllers[temp_controller_num].set_sensor(sensor)
            target = self.temperature_controllers[temp_controller_num].num
            command, com_id = self.commands.temp_ssr_enable_disable(target, sensor)
                #print(f"TC Thread: Queuing command {com_id}")
            self.mcu_signal.emit(command, com_id)
        else:
            raise ValueError("Invalid temperature controller number.")

    def set_continuous_reading(self, enable):
        if enable != self.continuous_reading:
            self.continuous_reading = enable
            command, com_id = self.commands.continuous_read(on=enable)
                #print(f"TC Thread: Queuing command {com_id}")
            self.mcu_signal.emit(command, com_id)

    def process_temp_serial_data(self, data: list):
        # Process the incoming temperature controller data
        # Data format: [time_ms, index_1, temp_1, duty_1, ...] depending on number of controllers that are enabled
        # parse data into two lists for each controller

        # Ex
        #get the indexes of the enabled controllers from data
        data_length = len(data)
        num_controllers_in_data = (data_length - 1) // 3
        new_data = False
        do_sensor_temp = []
        for i in range(num_controllers_in_data):
            index = data[1 + i * 3]
            temp = data[2 + i * 3]
            duty = data[3 + i * 3]
            do_sensor_temp.append(index)
            do_sensor_temp.append(temp)
            for controller in self.temperature_controllers:
                if controller.num == index and controller.sensor:
                    new_data = True
                    controller.add_data(data[0], temp)
                    controller.current_dutycycle_percent = (duty / controller.max_dutycycle) * 100.0
                    break
        if new_data:
            self.update_plot_signal.emit()
            self.update_temperature_signal.emit(do_sensor_temp)

    def clear_buffers(self):
        for controller in self.temperature_controllers:
            controller.temp_buffer.clear()
            controller.time_buffer.clear()

class temperature_controller:
    def __init__(self, name, number):
        self.name = name
        self.num = number
        self.enable = False
        self.temperature = 20.0
        self.sensor = 0
        self.kp = 1.0
        self.ki = 0.0
        self.kd = 0.0
        self.max_dutycycle = 65535  # max heater duty cycle
        self.current_dutycycle_percent = 0
        self.buffer_size = 10000
        self.temp_buffer = deque(maxlen=self.buffer_size)
        self.time_buffer = deque(maxlen=self.buffer_size)
        self.temperature_limits = (0, 40.0)  # min and max temperature limits

    def set_enable(self, enable):
        self.enable = enable

    def set_temperature(self, temperature):
        self.temperature = temperature

    def set_sensor(self, sensor):
        self.sensor = sensor

    def set_pid(self, kp=None, ki=None, kd=None):
        if ki:
            self.ki = ki
        if kp:
            self.kp = kp
        if kd:
            self.kd = kd

    def ms_to_elaspsed_seconds(self, ms):
        return ms / 1000.0

    def add_data(self, time_ms: int, temperature: float):
        self.time_buffer.append(self.ms_to_elaspsed_seconds(time_ms))
        self.temp_buffer.append(temperature)