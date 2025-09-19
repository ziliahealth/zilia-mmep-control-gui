#QObject that refreshes the GUI on a seperate thread
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QDateTime, QIODevice,QTimer
class GUIUpdater(QThread):
    update_signal = pyqtSignal(str)
    running_signal = pyqtSignal(bool)
    connected_signal = pyqtSignal(bool)
    recording_signal = pyqtSignal(bool)

    def __init__(self, log_widget, zo_plot_widget, start_button, connect_button):
        super().__init__()
        self.log_widget = log_widget
        self.zo_plot_widget = zo_plot_widget
        self.start_button = start_button
        self.connect_button = connect_button
        self.H20Cal = 18395
        self.PO2_cal = 21.9*(760-47.1)/100
        self.DO_calibration_coefs = [1, 0, 0 , 0]
        #self.DO_calibration_coefs[0] =self.PO2_cal/self.H20Cal
        self.avg_n = 20 #number of points to average
        #create fifo buffer for sensor data
        self.DO1Buffer = []
        self.DO2Buffer= []
    def update_ZO_plot(self,data):
        self.zo_plot_widget.clear()
        self.zo_plot_widget.plot(list(data[:,0]),list(data[:,1]),pen=(139,203,149))
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

    def update_startstop_button(self,message):
        if message:
            self.start_button.setText('Stop')
            self.start_button.setEnabled(True)
        else:
            self.start_button.setText('Start')
            self.start_button.setEnabled(True)
    def update_connectdisconnect_button(self,message):
        if message:
            #self.start_button.setEnabled(True)
            self.start_button.setStyleSheet("border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
            self.connect_button.setText('Disconnect MCU')
        else:
            #self.start_button.setEnabled(False)
            self.connect_button.setText('Connect MCU')
            self.start_button.setStyleSheet("border: 2px solid black ; background: black; border-radius: 10px; color: black")