#QObject that refreshes the GUI on a seperate thread
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QDateTime, QIODevice,QTimer
from do_sensor import DOUnits
class GUIUpdater(QThread):
    update_signal = pyqtSignal(str)
    running_signal = pyqtSignal(bool)
    connected_signal = pyqtSignal(bool)
    recording_signal = pyqtSignal(bool)
    clear_buffers_signal = pyqtSignal()

    def __init__(self, log_widget,
                 do_plot_widget,
                 temp_plot_widget,
                 flow_plot_widget,
                 connect_button,flow_controllers_list: list, temp_controllers_list: list, do_sensors_list: list):
        super().__init__()
        self.log_widget = log_widget
        # Plot widgets references
        self.do_plot_widget = do_plot_widget
        self.temp_plot_widget = temp_plot_widget
        self.flow_plot_widget = flow_plot_widget

        self.connect_button = connect_button
        self.DO_calibration_coefs = [1, 0, 0 , 0]
        self.avg_n = 20 #number of points to average
        self.flow_controllers = flow_controllers_list
        self.temp_controllers = temp_controllers_list
        self.do_sensors = do_sensors_list
        self.do_pen_colors = [(255, 255, 102), (139, 203, 149)]
        self.temp_pen_colors = [(255, 255, 102), (139, 203, 149)]
        self.flow_pen_colors =  [(255, 255, 102), (139, 203, 149), (51, 204, 204), (0, 102, 255)]
        self.current_do_units = DOUnits.VOLTAGE

    def update_do_plot(self):
        self.do_plot_widget.clear()
        for i, sensor in enumerate(self.do_sensors):
            if sensor.enabled:
                if units := self.current_do_units:
                    if units == DOUnits.VOLTAGE:
                        self.do_plot_widget.plot(list(sensor.time_buffer), list(sensor.raw_data_buffer), pen=self.do_pen_colors[i], name=sensor.name)
                    elif units == DOUnits.PO2_MMHG:
                        self.do_plot_widget.plot(list(sensor.time_buffer), list(sensor.partial_pressure_buffer), pen=self.do_pen_colors[i], name=sensor.name)
                    elif units == DOUnits.SO2_PERCENT:
                        self.do_plot_widget.plot(list(sensor.time_buffer), list(sensor.saturation_buffer), pen=self.do_pen_colors[i], name=sensor.name)

    def update_temp_plot(self):
        self.temp_plot_widget.clear()
        for i,controller in enumerate(self.temp_controllers):
            if controller.sensor:
                self.temp_plot_widget.plot(list(controller.time_buffer), list(controller.temp_buffer), pen=self.temp_pen_colors[i], name=controller.name)


    def update_flow_plot(self):
        self.flow_plot_widget.clear()
        for i, controller in enumerate(self.flow_controllers):
            if controller.sensor:
                self.flow_plot_widget.plot(list(controller.time_buffer), list(controller.flow_buffer), pen=self.flow_pen_colors[i], name=controller.name)
    def update_log(self, message):
        current_time = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        # Update the log widget with the new message
        log_entry = f'{current_time} - {message}'
        self.log_widget.append(log_entry)  # Append to the existing text and scroll to the bottom

    def update_connectdisconnect_button(self,message):
        if message:
            self.connect_button.setText('Disconnect MCU')
        else:
            #self.start_button.setEnabled(False)
            self.connect_button.setText('Connect MCU')
    def update_do_units(self, units: DOUnits):
        # updates the plot y-axis label based on the selected units
        self.current_do_units = units
        if units == DOUnits.VOLTAGE:
            print(DOUnits.VOLTAGE)
            self.do_plot_widget.setLabel('left', 'DO Sensor [V]')
        elif units == DOUnits.PO2_MMHG:
            print(DOUnits.PO2_MMHG)
            self.do_plot_widget.setLabel('left', 'Oxygen Partial pressure PO2 [mmHg]')
        elif units == DOUnits.SO2_PERCENT:
            print(DOUnits.SO2_PERCENT)
            self.do_plot_widget.setLabel('left', 'Oxygen saturation SO2 [-]')

        self.clear_buffers_signal.emit()


