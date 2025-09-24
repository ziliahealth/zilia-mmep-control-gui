#QObject that refreshes the GUI on a seperate thread
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QDateTime, QIODevice,QTimer
class GUIUpdater(QThread):
    update_signal = pyqtSignal(str)
    running_signal = pyqtSignal(bool)
    connected_signal = pyqtSignal(bool)
    recording_signal = pyqtSignal(bool)

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
        self.flow_pen_colors =  [(255, 255, 102), (139, 203, 149), (51, 204, 204), (0, 102, 255)]

    def update_do_plot(self):
        self.do_plot_widget.clear()
        for i, sensor in enumerate(self.do_sensors):
            if sensor.enabled:
                self.do_plot_widget.plot(list(sensor.time_buffer), list(sensor.raw_data_buffer), pen=self.do_pen_colors[i], name=sensor.name)

#    def update_ZO_plot(self,data):
 #       self.zo_plot_widget.clear()
  #      self.zo_plot_widget.plot(list(data[:,0]),list(data[:,1]),pen=(139,203,149))
    #def update_plot(self, data):
    #    print(data)
    #    data = data.split(',')
    #    self.flowrate1_buffer.append(data[0])
    #    self.flowrate1_buffer.append(data[1])
    #    self.flowrate3_buffer.append(data[2])
    #    self.flowrate4_buffer.append(data[3])

    def process_sensor_data(self, data):
        # Process the incoming sensor data
        data = data.split(';')
        print(data)
        #Apply calibration to DO sensor data
        data[5] = float(data[5])*self.DO_calibration_coefs[0]+self.DO_calibration_coefs[1]
        data[6] = float(data[6])*self.DO_calibration_coefs[0]+self.DO_calibration_coefs[1]
        #update fifo buffer
        self.DO1Buffer.append(data[5])
        self.DO2Buffer.append(data[6])
        if len(self.DO1Buffer) > self.avg_n:
            self.DO1Buffer.pop(0)
            self.DO2Buffer.pop(0)
        data[5] = sum(self.DO1Buffer)/len(self.DO1Buffer)
        data[6] = sum(self.DO2Buffer)/len(self.DO2Buffer)

        #Convert miliseconds to seconds
        data[0]  = float(data[0])/1000
        #format the data to message to be sent to the GUI
        message = '{:.3f}'.format(data[0])+','+data[1]+','+data[2]+','+data[3]+','+data[4]+','+'{:.3f}'.format(data[5])
        message = message + ',' + '{:.3f}'.format(data[6])
        self.update_signal.emit(message)
        # Update the pyqtgraph plot with the latest 1000 points from the buffer
     #   self.plot_widget.clear()
     #   self.plot_widget.plot(list(self.flowrate1_buffer), pen=(255, 0, 0))
     #   self.plot_widget.plot(list(self.flowrate2_buffer), pen=(255, 0, 0))
     #   self.plot_widget.plot(list(self.flowrate3_buffer), pen=(255, 0, 0))
     #   self.plot_widget.plot(list(self.flowrate4_buffer), pen=(255, 0, 0))

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