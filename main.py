# Import necessary libraries
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, \
    QWidget, QGridLayout, QTextEdit, QCheckBox, QFileDialog, QComboBox
from pyqtgraph import PlotWidget, TextItem
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QDateTime, QIODevice, QTimer
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo
from PyQt5.QtGui import QPixmap
# import serial
# from serial.tools import list_ports
from collections import deque
import configparser
import os as os

import numpy as np
from arduino_CMD import ArduinoThread
from zo import ZOThread
from guiupdater import GUIUpdater
from syringepump import SyringePumps
from datasaver import DataSaver
from sequencerunner import SequenceRunner


# ...
# Define the main application window
class SyringePumpApp(QMainWindow, QObject):
    arduino_start_signal = pyqtSignal()
    arduino_stop_signal = pyqtSignal()
    arduino_connect_signal = pyqtSignal()
    arduino_logging_signal = pyqtSignal()
    arduino_disconnect_signal = pyqtSignal()
    arduino_flowrate_change_signal = pyqtSignal()
    data_saver_stop_signal = pyqtSignal()
    ZO_start_signal = pyqtSignal()
    ZO_stop_signal = pyqtSignal()

    def __init__(self):
        super().__init__()

        # status bools for GUI
        self.running = False
        self.connected = False
        self.recording = False

        # Initialize UI elements
        self.setWindowTitle("Syringe Pump Control App")
        self.setGeometry(100, 100, 1000, 800)  # Adjust the initial window size as needed
        self.setStyleSheet("background-color: black; color: rgb(139,203,149)")

        # Create widgets
        self.flow_rate_label = QLabel("Desired Flow Rate (0-1000 µL/min):")
        self.flow_rate_input1 = QLineEdit()
        self.flow_rate_input1.setStyleSheet("color: rgb(139,203,149);")
        self.flow_rate_input2 = QLineEdit()
        self.flow_rate_input2.setStyleSheet("color: rgb(139,203,149);")
        self.flow_rate_input3 = QLineEdit()
        self.flow_rate_input3.setStyleSheet("color: rgb(139,203,149);")
        self.flow_rate_input4 = QLineEdit()
        self.flow_rate_input4.setStyleSheet("color: rgb(139,203,149);")

        self.proportional_input1 = QLineEdit()
        self.proportional_input2 = QLineEdit()
        self.proportional_input3 = QLineEdit()
        self.proportional_input4 = QLineEdit()

        self.derivative_input1 = QLineEdit()
        self.derivative_input2 = QLineEdit()
        self.derivative_input3 = QLineEdit()
        self.derivative_input4 = QLineEdit()

        self.integral_input1 = QLineEdit()
        self.integral_input2 = QLineEdit()
        self.integral_input3 = QLineEdit()
        self.integral_input4 = QLineEdit()

        self.diameter_dropdown1 = QComboBox()
        self.diameter_dropdown2 = QComboBox()
        self.diameter_dropdown3 = QComboBox()
        self.diameter_dropdown4 = QComboBox()
        self.diameter_dropdown1.addItems(['16 mm (12 mL)','14 mm (10 mL)', '8 mm (3 mL)', '4.7 mm (1 mL)'])
        self.diameter_dropdown2.addItems(['16 mm (12 mL)','14 mm (10 mL)', '8 mm (3 mL)', '4.7 mm (1 mL)'])
        self.diameter_dropdown3.addItems(['16 mm (12 mL)', '14 mm (10 mL)','8 mm (3 mL)', '4.7 mm (1 mL)'])
        self.diameter_dropdown4.addItems(['16 mm (12 mL)','14 mm (10 mL)', '8 mm (3 mL)', '4.7 mm (1 mL)'])

        self.pid_params_label = QLabel("PID Parameters:")
        self.pump1_label = QLabel('Pump 1')
        self.pump2_label = QLabel('Pump 2')
        self.pump3_label = QLabel('Pump 3')
        self.pump4_label = QLabel('Pump 4')

        # pump drop down list with options off, pid, and constant
        self.pump1_dropdown = QComboBox()
        self.pump2_dropdown = QComboBox()
        self.pump3_dropdown = QComboBox()
        self.pump4_dropdown = QComboBox()
        self.pump1_dropdown.addItems(['Off', 'PID', 'Constant', 'Fill', 'Empty'])
        self.pump2_dropdown.addItems(['Off', 'PID', 'Constant', 'Fill', 'Empty'])
        self.pump3_dropdown.addItems(['Off', 'PID', 'Constant', 'Fill', 'Empty'])
        self.pump4_dropdown.addItems(['Off', 'PID', 'Constant', 'Fill', 'Empty'])

        self.sensor1_dropdown = QComboBox()
        self.sensor2_dropdown = QComboBox()
        self.sensor3_dropdown = QComboBox()
        self.sensor4_dropdown = QComboBox()
        self.sensor1_dropdown.addItems(['Off', 'On'])
        self.sensor2_dropdown.addItems(['Off', 'On'])
        self.sensor3_dropdown.addItems(['Off', 'On'])
        self.sensor4_dropdown.addItems(['Off', 'On'])

        self.start_button = QPushButton("Start Pump")
        self.stop_button = QPushButton("Stop Pump")
        self.connect_button = QPushButton("Connect to Arduino")
        self.disconnect_button = QPushButton("Disconnect from Arduino")
        self.load_config_button = QPushButton('Load configuration')
        self.save_config_button = QPushButton('Save configuration')
        self.save_data_button = QPushButton('Log data')
        self.load_sequence_button = QPushButton("Load Sequence")


        self.flowrate_plot_widget = PlotWidget()
        self.oxygen_plot_widget = PlotWidget()
        self.zo_plot_widget = PlotWidget()
        self.log_label = QLabel("Log:")
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.logo = QPixmap('logo.png')
        self.logo.setDevicePixelRatio(1)
        self.logo_label = QLabel()
        self.logo_label.setPixmap(self.logo)

        # Create QLineEdit widgets for PID parameters
        self.proportional_input = QLineEdit()
        self.derivative_input = QLineEdit()
        self.integral_input = QLineEdit()

        # generate layouts
        layout = QGridLayout()
        config_btn_layout = QVBoxLayout()
        plot_layout = QHBoxLayout()

        # Add flow rate input box to the layout
        layout.addWidget(QLabel("Desired Flow Rate (0-1000 µL/min):"), 1, 0)
        layout.addWidget(self.flow_rate_input1, 1, 1)
        layout.addWidget(self.flow_rate_input2, 1, 2)
        layout.addWidget(self.flow_rate_input3, 1, 3)
        layout.addWidget(self.flow_rate_input4, 1, 4)

        # Add PID parameter input boxes to the layout
        layout.addWidget(QLabel("Proportional (KP)"), 2, 0)
        layout.addWidget(self.proportional_input1, 2, 1)
        layout.addWidget(self.proportional_input2, 2, 2)
        layout.addWidget(self.proportional_input3, 2, 3)
        layout.addWidget(self.proportional_input4, 2, 4)
        layout.addWidget(QLabel("Integral (KI):"), 3, 0)
        layout.addWidget(self.integral_input1, 3, 1)
        layout.addWidget(self.integral_input2, 3, 2)
        layout.addWidget(self.integral_input3, 3, 3)
        layout.addWidget(self.integral_input4, 3, 4)
        layout.addWidget(QLabel("Derivative (KD):"), 4, 0)

        layout.addWidget(self.derivative_input1, 4, 1)
        layout.addWidget(self.derivative_input2, 4, 2)
        layout.addWidget(self.derivative_input3, 4, 3)
        layout.addWidget(self.derivative_input4, 4, 4)

        # add pump diameter dropdown
        layout.addWidget(QLabel("Syringe diameter:"), 5, 0)
        layout.addWidget(self.diameter_dropdown1, 5, 1)
        layout.addWidget(self.diameter_dropdown2, 5, 2)
        layout.addWidget(self.diameter_dropdown3, 5, 3)
        layout.addWidget(self.diameter_dropdown4, 5, 4)

        layout.addWidget(QLabel("Pump mode:"), 6, 0)
        layout.addWidget(self.pump1_dropdown, 6, 1)
        layout.addWidget(self.pump2_dropdown, 6, 2)
        layout.addWidget(self.pump3_dropdown, 6, 3)
        layout.addWidget(self.pump4_dropdown, 6, 4)

        layout.addWidget(QLabel("Sensor:"), 7, 0)
        layout.addWidget(self.sensor1_dropdown, 7, 1)
        layout.addWidget(self.sensor2_dropdown, 7, 2)
        layout.addWidget(self.sensor3_dropdown, 7, 3)
        layout.addWidget(self.sensor4_dropdown, 7, 4)

        # add Pump checkboxes
        layout.addWidget(self.pump1_label, 0, 1)
        layout.addWidget(self.pump2_label, 0, 2)
        layout.addWidget(self.pump3_label, 0, 3)
        layout.addWidget(self.pump4_label, 0, 4)
        # Add buttons to the layout

        # Add buttons to the layout
        self.start_button.setStyleSheet(
            "border: 2px solid black ; background: black; border-radius: 10px; color: black")
        self.start_button.setEnabled(False)
        layout.addWidget(self.start_button, 1, 7, 2, 3)
        self.stop_button.setStyleSheet("border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        # layout.addWidget(self.stop_button, 2, 7)
        self.connect_button.setStyleSheet("border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        layout.addWidget(self.connect_button, 3, 7, 2, 3)
        self.disconnect_button.setStyleSheet(
            "border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        # layout.addWidget(self.disconnect_button, 4, 7)
        config_btn_layout.addWidget(self.load_config_button)
        self.load_config_button.setStyleSheet(
            "border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        config_btn_layout.addWidget(self.save_config_button)
        self.save_config_button.setStyleSheet(
            "border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        config_btn_layout.addWidget(self.save_data_button)
        config_btn_layout.addWidget(self.logo_label)
        self.save_data_button.setStyleSheet(
            "border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        layout.addLayout(config_btn_layout, 9, 7)
        self.load_sequence_button.setStyleSheet(
            "border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        layout.addWidget(self.load_sequence_button, 5, 7, 2, 3)

        # Add the plot to the layout
        # layout.addWidget(self.flowrate_plot_widget, 6, 0, 1, 3)
        # layout.addWidget(self.oxygen_plot_widget, 6, 3, 1, 6)
        plot_layout.addWidget(self.flowrate_plot_widget)
        plot_layout.addWidget(self.oxygen_plot_widget)
        plot_layout.addWidget(self.zo_plot_widget)
        layout.addLayout(plot_layout, 8, 0, 1, 8)

        self.flowrate_plot_widget.setLabel('bottom', 'Time', units='s')
        self.flowrate_plot_widget.setLabel('left', 'Flow Rate (µL/min)')
        self.flowrate_plot_widget.setTitle('Flow Rate')

        self.oxygen_plot_widget.addLegend()
        self.oxygen_plot_widget.setLabel('bottom', 'Time', units='s')
        self.oxygen_plot_widget.setLabel('left', ' O2 partial pressure', units='mmHg')
        self.oxygen_plot_widget.setTitle('Oxygen Saturation')

        self.zo_plot_widget.setLabel('bottom', 'Wavelength', units='nm')
        self.zo_plot_widget.setLabel('left', 'Intensity', units='A.U.')
        self.zo_plot_widget.setTitle('Raw spectrum')
        self.zo_plot_widget.setXRange(450, 800)
        self.zo_plot_widget.setYRange(0, 65000)
        # Add the log label and widget
        layout.addWidget(self.log_widget, 9, 0, 1, 6)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Initialize Arduino communication thread
        self.arduino_thread = ArduinoThread()
        self.zo_thread = ZOThread()
        self.sequence_runner = SequenceRunner()

        # Connect signals to slots
        self.start_button.clicked.connect(self.startstop_button_onclick)
        self.connect_button.clicked.connect(self.connectdisconnect_button_onclick)
        self.load_config_button.clicked.connect(self.load_config_button_onclick)
        self.save_config_button.clicked.connect(self.save_config_button_onclick)
        self.save_data_button.clicked.connect(self.save_data_button_onclick)
        self.load_sequence_button.clicked.connect(self.sequence_onclick)
        self.flow_rate_input1.textChanged.connect(lambda: self.flowrate_input_onchange('pump1'))
        self.proportional_input1.textChanged.connect(lambda: self.PID_input_onchange('pump1', 'proportional'))
        self.derivative_input1.textChanged.connect(lambda: self.PID_input_onchange('pump1', 'derivative'))
        self.integral_input1.textChanged.connect(lambda: self.PID_input_onchange('pump1', 'integral'))
        self.flow_rate_input2.textChanged.connect(lambda: self.flowrate_input_onchange('pump2'))
        self.proportional_input2.textChanged.connect(lambda: self.PID_input_onchange('pump2', 'proportional'))
        self.derivative_input2.textChanged.connect(lambda: self.PID_input_onchange('pump2', 'derivative'))
        self.integral_input2.textChanged.connect(lambda: self.PID_input_onchange('pump2', 'integral'))
        self.flow_rate_input3.textChanged.connect(lambda: self.flowrate_input_onchange('pump3'))
        self.proportional_input3.textChanged.connect(lambda: self.PID_input_onchange('pump3', 'proportional'))
        self.derivative_input3.textChanged.connect(lambda: self.PID_input_onchange('pump3', 'derivative'))
        self.integral_input3.textChanged.connect(lambda: self.PID_input_onchange('pump3', 'integral'))
        self.flow_rate_input4.textChanged.connect(lambda: self.flowrate_input_onchange('pump4'))
        self.proportional_input4.textChanged.connect(lambda: self.PID_input_onchange('pump4', 'proportional'))
        self.derivative_input4.textChanged.connect(lambda: self.PID_input_onchange('pump4', 'derivative'))

        self.arduino_start_signal.connect(self.arduino_thread.start)
        self.arduino_stop_signal.connect(self.arduino_thread.stop)
        self.arduino_connect_signal.connect(self.arduino_thread.connect)
        self.arduino_disconnect_signal.connect(self.arduino_thread.close, Qt.DirectConnection)
        self.pump1_dropdown.currentTextChanged.connect(lambda: self.mode_on_change('pump1'))
        self.pump2_dropdown.currentTextChanged.connect(lambda: self.mode_on_change('pump2'))
        self.pump3_dropdown.currentTextChanged.connect(lambda: self.mode_on_change('pump3'))
        self.pump4_dropdown.currentTextChanged.connect(lambda: self.mode_on_change('pump4'))
        self.sensor1_dropdown.currentTextChanged.connect(lambda: self.sensor_on_change('pump1'))
        self.sensor2_dropdown.currentTextChanged.connect(lambda: self.sensor_on_change('pump2'))
        self.sensor3_dropdown.currentTextChanged.connect(lambda: self.sensor_on_change('pump3'))
        self.sensor4_dropdown.currentTextChanged.connect(lambda: self.sensor_on_change('pump4'))
        self.diameter_dropdown1.currentTextChanged.connect(lambda: self.diameter_onchange('pump1'))
        self.diameter_dropdown2.currentTextChanged.connect(lambda: self.diameter_onchange('pump2'))
        self.diameter_dropdown3.currentTextChanged.connect(lambda: self.diameter_onchange('pump3'))
        self.diameter_dropdown4.currentTextChanged.connect(lambda: self.diameter_onchange('pump4'))

        # Initialize FIFO buffer with a maximum length of 1000 points
        self.flowrate_buffer_length = 10000
        self.oxygen_buffer_length = 10000
        self.flowrate1_buffer = deque(maxlen=self.flowrate_buffer_length)
        self.flowrate2_buffer = deque(maxlen=self.flowrate_buffer_length)
        self.flowrate3_buffer = deque(maxlen=self.flowrate_buffer_length)
        self.flowrate4_buffer = deque(maxlen=self.flowrate_buffer_length)
        self.oxygen1_buffer = deque(maxlen=self.oxygen_buffer_length)
        self.oxygen2_buffer = deque(maxlen=self.oxygen_buffer_length)

        self.flowrate_plot_widget.plot(list(self.flowrate1_buffer), pen=(255, 255, 102), name='pump 1')
        self.flowrate_plot_widget.plot(list(self.flowrate2_buffer), pen=(139, 203, 149), name='pump 2')
        self.flowrate_plot_widget.plot(list(self.flowrate3_buffer), pen=(51, 204, 204), name='pump 3')
        self.flowrate_plot_widget.plot(list(self.flowrate4_buffer), pen=(0, 102, 255), name='pump 4')
        self.oxygen_plot_widget.plot(list(self.oxygen1_buffer), pen=(255, 255, 102), name='Retina')
        self.oxygen_plot_widget.plot(list(self.oxygen2_buffer), pen=(139,203,149), name='Choroid')
        # add legends
        self.flowrate_plot_widget.addLegend()
        self.oxygen_plot_widget.addLegend()

        ##self.oxygen_value_text = TextItem(text="Current Oxygen Value: ")
        # self.oxygen_value_text.setPos(10, 10)  # Adjust the position as needed
        # self.oxygen_plot_widget.addItem(self.oxygen_value_text)

        # ZO thread signals
        self.ZO_start_signal.connect(self.zo_thread.start)
        self.ZO_stop_signal.connect(self.zo_thread.stop)

        # Initialize GUI updater
        self.gui_updater = GUIUpdater(self.log_widget, self.zo_plot_widget, self.start_button, self.connect_button)
        self.gui_updater.update_signal.connect(self.update_plot)

        # Connect Arduino thread signal to GUI updater slot
        self.arduino_thread.sensor_signal.connect(self.gui_updater.process_sensor_data)
        self.arduino_thread.log_signal.connect(self.gui_updater.update_log)
        self.arduino_thread.running_signal.connect(self.gui_updater.update_startstop_button)
        self.arduino_thread.running_signal.connect(self.update_running)
        self.arduino_thread.connected_signal.connect(self.gui_updater.update_connectdisconnect_button)
        self.arduino_thread.connected_signal.connect(self.update_connected)
        self.zo_thread.data_signal.connect(self.gui_updater.update_ZO_plot)

        # initialize syringe pump object
        self.syringe_pumps = SyringePumps()
        self.syringe_pumps.arduino_signal.connect(self.arduino_thread.on_syringe_pump_signal)
        self.arduino_thread.update_all_signal.connect(self.syringe_pumps.set_all)

        #Initialize data saver object
        self.data_saver = DataSaver()
        self.arduino_logging_signal.connect(self.arduino_thread.start_logging, Qt.DirectConnection)
        self.data_saver_stop_signal.connect(self.data_saver.stop_save)



        # Load default config .ini
        self.load_config('C:/Users/marca/PycharmProjects/MMEP-Control-GUI/default.ini')

        # Update syringe_pumps object with 'default' config
        self.syringe_pumps.set_flow(0, float(self.flow_rate_input1.text()))
        self.syringe_pumps.set_flow(1, float(self.flow_rate_input2.text()))
        self.syringe_pumps.set_flow(2, float(self.flow_rate_input3.text()))
        self.syringe_pumps.set_flow(3, float(self.flow_rate_input4.text()))
        self.syringe_pumps.set_mode(0, self.pump1_dropdown.currentText())
        self.syringe_pumps.set_mode(1, self.pump2_dropdown.currentText())
        self.syringe_pumps.set_mode(2, self.pump3_dropdown.currentText())
        self.syringe_pumps.set_mode(3, self.pump4_dropdown.currentText())

        # get syringe pump info
        self.syringe_pumps.pumps[0].info()
        self.syringe_pumps.pumps[1].info()
        self.syringe_pumps.pumps[2].info()
        self.syringe_pumps.pumps[3].info()

        # Start threads
        self.arduino_thread.start()
        self.zo_thread.start()
        self.gui_updater.start()
        self.data_saver.start()
        self.syringe_pumps.start()
        self.sequence_runner.start()


    def startstop_button_onclick(self):

        if (not (self.running)):
            self.arduino_start_signal.emit()
            self.ZO_start_signal.emit()
        else:
            self.arduino_stop_signal.emit()
            self.ZO_stop_signal.emit()
        # Implement pump start logic
        pass

    def connectdisconnect_button_onclick(self):
        if (not (self.connected)):
            self.arduino_connect_signal.emit()
        else:
            print('disconnect')
            self.arduino_disconnect_signal.emit()

    def update_plot(self, data):
        #print(data)
        data = data.strip().split(',')
        self.flowrate1_buffer.append(float(data[1]))
        self.flowrate2_buffer.append(float(data[2]))
        self.flowrate3_buffer.append(float(data[3]))
        self.flowrate4_buffer.append(float(data[4]))
        self.oxygen1_buffer.append(float(data[5]))
        self.oxygen2_buffer.append(float(data[6]))
        # self.oxygen_value_text.setText(f"Current Oxygen Value: {data[4]}, {data[5]}")  # Update the text item with the latest oxygen value

        # Update the pyqtgraph plot with the latest 1000 points from the buffer
        self.flowrate_plot_widget.clear()
        self.oxygen_plot_widget.clear()
        self.flowrate_plot_widget.plot(list(self.flowrate1_buffer), pen=(255, 255, 102), name='pump 1')
        self.flowrate_plot_widget.plot(list(self.flowrate2_buffer), pen=(0, 204, 102), name='pump 2')
        self.flowrate_plot_widget.plot(list(self.flowrate3_buffer), pen=(51, 204, 204), name='pump 3')
        self.flowrate_plot_widget.plot(list(self.flowrate4_buffer), pen=(0, 102, 255), name='pump 4')
        self.oxygen_plot_widget.plot(list(self.oxygen1_buffer), pen=(255, 255, 102), name='Retina')
        self.oxygen_plot_widget.plot(list(self.oxygen2_buffer), pen=(0, 204, 102), name='Choroid')

    def flowrate_input_onchange(self, pump):
        # Method that updates the flow rate of a pump
        # If the flow rate is changed, update the syringe_pumps object
        if pump == 'pump1':
            self.syringe_pumps.set_flow(0, float(self.flow_rate_input1.text()))
        elif pump == 'pump2':
            self.syringe_pumps.set_flow(1, float(self.flow_rate_input2.text()))
        elif pump == 'pump3':
            self.syringe_pumps.set_flow(2, float(self.flow_rate_input3.text()))
        elif pump == 'pump4':
            self.syringe_pumps.set_flow(3, float(self.flow_rate_input4.text()))

    def PID_input_onchange(self, pump, parameter):
        # Method that updates the PID parameters of a pump
        # If a PID parameter is changed, update the syringe_pumps object
        if pump == 'pump1':
            if parameter == 'proportional':
                self.syringe_pumps.set_pid(0, Kp=float(self.proportional_input1.text()))
            elif parameter == 'derivative':
                self.syringe_pumps.set_pid(0, Kd=float(self.derivative_input1.text()))
            elif parameter == 'integral':
                self.syringe_pumps.set_pid(0, Ki=float(self.integral_input1.text()))
        elif pump == 'pump2':
            if parameter == 'proportional':
                self.syringe_pumps.set_pid(1, Kp=float(self.proportional_input2.text()))
            elif parameter == 'derivative':
                self.syringe_pumps.set_pid(1, Kd=float(self.derivative_input2.text()))
            elif parameter == 'integral':
                self.syringe_pumps.set_pid(1, Ki=float(self.integral_input2.text()))
        elif pump == 'pump3':
            if parameter == 'proportional':
                self.syringe_pumps.set_pid(2, Kp=float(self.proportional_input3.text()))
            elif parameter == 'derivative':
                self.syringe_pumps.set_pid(2, Kd=float(self.derivative_input3.text()))
            elif parameter == 'integral':
                self.syringe_pumps.set_pid(2, Ki=float(self.integral_input3.text()))
        elif pump == 'pump4':
            if parameter == 'proportional':
                self.syringe_pumps.set_pid(3, Kp=float(self.proportional_input4.text()))
            elif parameter == 'derivative':
                self.syringe_pumps.set_pid(3, Kd=float(self.derivative_input4.text()))
            elif parameter == 'integral':
                self.syringe_pumps.set_pid(3, Ki=float(self.integral_input4.text()))

    def diameter_onchange(self, pump):
        # Method that updates the diameter of a pump
        # If the diameter is changed, update the syringe_pumps object
        if pump == 'pump1':
            if self.diameter_dropdown1.currentText() == '16 mm (12 mL)':
                self.syringe_pumps.set_diameter(0, 16)
            elif self.diameter_dropdown1.currentText() == '8 mm (3 mL)':
                self.syringe_pumps.set_diameter(0, 8)
            elif self.diameter_dropdown1.currentText() == '4.7 mm (1 mL)':
                self.syringe_pumps.set_diameter(0, 4.7)
            elif self.diameter_dropdown1.currentText() == '14 mm (10 mL)':
                self.syringe_pumps.set_diameter(0, 14.3)
        elif pump == 'pump2':
            if self.diameter_dropdown2.currentText() == '16 mm (12 mL)':
                self.syringe_pumps.set_diameter(1, 16)
            elif self.diameter_dropdown2.currentText() == '8 mm (3 mL)':
                self.syringe_pumps.set_diameter(1, 8)
            elif self.diameter_dropdown2.currentText() == '4.7 mm (1 mL)':
                self.syringe_pumps.set_diameter(1, 4.7)
            elif self.diameter_dropdown2.currentText() == '14 mm (10 mL)':
                self.syringe_pumps.set_diameter(1, 14.3)

        elif pump == 'pump3':
            if self.diameter_dropdown3.currentText() == '16 mm (12 mL)':
                self.syringe_pumps.set_diameter(2, 16)
            elif self.diameter_dropdown3.currentText() == '8 mm (3 mL)':
                self.syringe_pumps.set_diameter(2, 8)
            elif self.diameter_dropdown3.currentText() == '4.7 mm (1 mL)':
                self.syringe_pumps.set_diameter(2, 4.7)
            elif self.diameter_dropdown3.currentText()=='14 mm (10 mL)':
                self.syringe_pumps.set_diameter(2, 14.3)
        elif pump == 'pump4':
            if self.diameter_dropdown4.currentText() == '16 mm (12 mL)':
                self.syringe_pumps.set_diameter(3, 16)
            elif self.diameter_dropdown4.currentText() == '8 mm (3 mL)':
                self.syringe_pumps.set_diameter(3, 8)
            elif self.diameter_dropdown4.currentText() == '4.7 mm (1 mL)':
                self.syringe_pumps.set_diameter(3, 4.7)
            elif self.diameter_dropdown4.currentText() == '14 mm (10 mL)':
                self.syringe_pumps.set_diameter(4, 14.3)

    def update_running(self, message):
        self.running = message
        print('update running')

    def update_connected(self, message):
        print('update connected')
        self.connected = message

    def update_recording(self, message):
        print('update recording')

    def load_config(self, file_path):
        # Open a file dialog to select a configuration file for loading
        # Load configuration from the specified file
        config = configparser.ConfigParser()
        config.read(file_path)
        # print on log
        self.log_widget.append(f'Loaded configuration from {file_path}')
        # Update UI elements with the loaded configuration
        self.flow_rate_input1.setText(config.get('Pump1', 'FlowRate'))
        self.proportional_input1.setText(config.get('Pump1', 'KP'))
        self.integral_input1.setText(config.get('Pump1', 'KI'))
        self.derivative_input1.setText(config.get('Pump1', 'KD'))
        mode = str(config.get('Pump1', 'Mode'))
        if mode == 'pid':
            self.pump1_dropdown.setCurrentText('PID')
        elif mode == 'constant':
            self.pump1_dropdown.setCurrentText('Constant')
        elif mode == 'fill':
            self.pump1_dropdown.setCurrentText('Fill')
        elif mode == 'empty':
            self.pump1_dropdown.setCurrentText('Empty')
        else:
            self.pump1_dropdown.setCurrentText('Off')
        if str(config.get('Pump1', 'Sensor')) == 'on':
            self.sensor1_dropdown.setCurrentText('On')
        else:
            self.sensor1_dropdown.setCurrentText('Off')

        diameter = str(config.get('Pump1', 'Diameter'))
        if diameter == '16':
            self.diameter_dropdown1.setCurrentText('16 mm (12 mL)')
        elif diameter == '8':
            self.diameter_dropdown1.setCurrentText('8 mm (3 mL)')
        elif diameter == '4.7':
            self.diameter_dropdown1.setCurrentText('4.7 mm (1 mL)')

        self.flow_rate_input2.setText(config.get('Pump2', 'FlowRate'))
        self.proportional_input2.setText(config.get('Pump2', 'KP'))
        self.integral_input2.setText(config.get('Pump2', 'KI'))
        self.derivative_input2.setText(config.get('Pump2', 'KD'))
        self.pump2_dropdown.setCurrentText(config.get('Pump2', 'Mode'))
        diameter = config.get('Pump2', 'Diameter')
        self.sensor2_dropdown.setCurrentText(config.get('Pump2', 'Sensor'))
        if diameter == '16':
            self.diameter_dropdown2.setCurrentText('16 mm (12 mL)')
        elif diameter == '8':
            self.diameter_dropdown2.setCurrentText('8 mm (3 mL)')
        elif diameter == '4.7':
            self.diameter_dropdown2.setCurrentText('4.7 mm (1 mL)')

        self.flow_rate_input3.setText(config.get('Pump3', 'FlowRate'))
        self.proportional_input3.setText(config.get('Pump3', 'KP'))
        self.integral_input3.setText(config.get('Pump3', 'KI'))
        self.derivative_input3.setText(config.get('Pump3', 'KD'))
        self.pump3_dropdown.setCurrentText(config.get('Pump3', 'Mode'))
        self.sensor3_dropdown.setCurrentText(config.get('Pump3', 'Sensor'))
        diameter = config.get('Pump3', 'Diameter')

        sensor = config.get('Pump4', 'Sensor')
        if sensor == 'on':
            self.sensor3_dropdown.setCurrentText('On')
        else:
            self.sensor3_dropdown.setCurrentText('Off')
        if diameter == '16':
            self.diameter_dropdown3.setCurrentText('16 mm (12 mL)')
        elif diameter == '8':
            self.diameter_dropdown3.setCurrentText('8 mm (3 mL)')
        elif diameter == '4.7':
            self.diameter_dropdown3.setCurrentText('4.7 mm (1 mL)')

        self.flow_rate_input4.setText(config.get('Pump4', 'FlowRate'))
        self.proportional_input4.setText(config.get('Pump4', 'KP'))
        self.integral_input4.setText(config.get('Pump4', 'KI'))
        self.derivative_input4.setText(config.get('Pump4', 'KD'))
        self.pump4_dropdown.setCurrentText(config.get('Pump4', 'Mode'))
        diameter = config.get('Pump4', 'Diameter')
        sensor = config.get('Pump4', 'Sensor')
        if sensor == 'on':
            self.sensor4_dropdown.setCurrentText('On')
        else:
            self.sensor4_dropdown.setCurrentText('Off')
        if diameter == '16':
            self.diameter_dropdown4.setCurrentText('16 mm (12 mL)')
        elif diameter == '8':
            self.diameter_dropdown4.setCurrentText('8 mm (3 mL)')
        elif diameter == '4.7':
            self.diameter_dropdown4.setCurrentText('4.7 mm (1 mL)')

        # Update syringe_pumps object with loaded config
        self.mode_on_change('pump1')
        self.mode_on_change('pump2')
        self.mode_on_change('pump3')
        self.mode_on_change('pump4')

        self.sensor_on_change('pump1')
        self.sensor_on_change('pump2')
        self.sensor_on_change('pump3')
        self.sensor_on_change('pump4')

        self.flowrate_input_onchange('pump1')
        self.flowrate_input_onchange('pump2')
        self.flowrate_input_onchange('pump3')
        self.flowrate_input_onchange('pump4')

        self.PID_input_onchange('pump1', 'proportional')
        self.PID_input_onchange('pump1', 'integral')
        self.PID_input_onchange('pump1', 'derivative')
        self.PID_input_onchange('pump2', 'proportional')
        self.PID_input_onchange('pump2', 'integral')
        self.PID_input_onchange('pump2', 'derivative')
        self.PID_input_onchange('pump3', 'proportional')
        self.PID_input_onchange('pump3', 'integral')
        self.PID_input_onchange('pump3', 'derivative')
        self.PID_input_onchange('pump4', 'proportional')
        self.PID_input_onchange('pump4', 'integral')
        self.PID_input_onchange('pump4', 'derivative')

        self.diameter_onchange('pump1')
        self.diameter_onchange('pump2')
        self.diameter_onchange('pump3')
        self.diameter_onchange('pump4')

    def load_config_button_onclick(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Load Configuration File', '', 'INI Files (*.ini)')
        if file_path:
            self.load_config(file_path)


    def sequence_onclick(self):
        if self.connected:
            sequence_file, _ = QFileDialog.getOpenFileName(self, 'Load Sequence File', '', 'JSON Files (*.json)')
            if sequence_file:
                self.sequence_runner.load_sequence(sequence_file)
                self.load_sequence_button.setText("Stop")
                # Disable the parameter QtextEdits
                self.proportional_input1.setDisabled(True)
                self.proportional_input2.setDisabled(True)
                self.proportional_input3.setDisabled(True)
                self.proportional_input4.setDisabled(True)
                self.derivative_input1.setDisabled(True)
                self.derivative_input2.setDisabled(True)
                self.derivative_input3.setDisabled(True)
                self.derivative_input4.setDisabled(True)
                self.integral_input1.setDisabled(True)
                self.integral_input2.setDisabled(True)
                self.integral_input3.setDisabled(True)
                self.integral_input4.setDisabled(True)
        else:
            self.load_sequence_button.setText("Load Sequence")
            # Enable the parameter QtextEdits
            self.proportional_input1.setDisabled(False)
            self.proportional_input2.setDisabled(False)
            self.proportional_input3.setDisabled(False)
            self.proportional_input4.setDisabled(False)
            self.derivative_input1.setDisabled(False)
            self.derivative_input2.setDisabled(False)
            self.derivative_input3.setDisabled(False)
            self.derivative_input4.setDisabled(False)
            self.integral_input1.setDisabled(False)
            self.integral_input2.setDisabled(False)
            self.integral_input3.setDisabled(False)
            self.integral_input4.setDisabled(False)
            self.gui_updater.update_log('Please connect to the Arduino before starting a sequence')


    def save_config_button_onclick(self):

        file_path, _ = QFileDialog.getSaveFileName(self, 'Save Configuration File', '', 'INI Files (*.ini)')
        if file_path:
            # Save configuration to the specified file
            config = configparser.ConfigParser()

            # Add sections for each pump
            config.add_section('Pump1')
            config.add_section('Pump2')
            config.add_section('Pump3')
            config.add_section('Pump4')

            # Add key-value pairs for each parameter
            config.set('Pump1', 'FlowRate', self.flow_rate_input1.text())
            config.set('Pump1', 'KP', self.proportional_input1.text())
            config.set('Pump1', 'KI', self.integral_input1.text())
            config.set('Pump1', 'KD', self.derivative_input1.text())
            config.set('Pump1', 'Mode', self.pump1_dropdown.currentText())

            config.set('Pump2', 'FlowRate', self.flow_rate_input2.text())
            config.set('Pump2', 'KP', self.proportional_input2.text())
            config.set('Pump2', 'KI', self.integral_input2.text())
            config.set('Pump2', 'KD', self.derivative_input2.text())
            config.set('Pump2', 'Mode', self.pump2_dropdown.currentText())

            config.set('Pump3', 'FlowRate', self.flow_rate_input3.text())
            config.set('Pump3', 'KP', self.proportional_input3.text())
            config.set('Pump3', 'KI', self.integral_input3.text())
            config.set('Pump3', 'KD', self.derivative_input3.text())
            config.set('Pump3', 'Mode', self.pump3_dropdown.currentText())

            config.set('Pump4', 'FlowRate', self.flow_rate_input1.text())
            config.set('Pump4', 'KP', self.proportional_input1.text())
            config.set('Pump4', 'KI', self.integral_input1.text())
            config.set('Pump4', 'KD', self.derivative_input1.text())
            config.set('Pump4', 'Mode', self.pump4_dropdown.currentText())

            # Save the configuration to the file
            with open(file_path, 'w') as config_file:
                config.write(config_file)

    def save_data_button_onclick(self):
        # Open a file dialog to select a file for saving the data
        # Save the data to the specified file
        if self.recording == False:
            filepath = QFileDialog.getSaveFileName(self, 'Save Data', '', 'CSV Files (*.csv)')
            if filepath:
                #Check if filepath already exists
                if os.path.exists(filepath[0]):
                    #increment filename
                    filename = filepath[0].split('.csv')[0]
                    filename = filename + '_1.csv'
                    filepath = filename
                else:
                    filepath = filepath[0]
                    self.log_widget.append(f'Saving data to {filepath}')

                print(filepath)

                self.data_saver.set_filename(filepath)
                self.data_saver.start_save()
                self.recording = True
                self.save_data_button.setText('Stop Recording')
                #Send command to arduino to reset time
                self.arduino_logging_signal.emit()
                self.arduino_thread.sensor_signal.connect(self.data_saver.save_data)
        else:
            #self.data_saver.stop_save()
            self.recording = False
            self.save_data_button.setText('Log Data')
            self.data_saver_stop_signal.emit()
            self.arduino_thread.sensor_signal.disconnect(self.data_saver.save_data)




    def mode_on_change(self, pump):
        # Method that updates the GUI for different modes
        # If the mode is set to PID, enable the PID parameter input boxes
        # If the mode is set to Constant, Change input boxes to thread and syringue diameter
        # If the mode is set to Off, disable all input boxes
        print(pump)
        if pump == 'pump1':
            mode = self.pump1_dropdown.currentText()
            if mode == 'PID':
                self.proportional_input1.setEnabled(True)
                self.integral_input1.setEnabled(True)
                self.derivative_input1.setEnabled(True)
                self.proportional_input1.setStyleSheet("background-color: black")
                self.integral_input1.setStyleSheet("background-color: black")
                self.derivative_input1.setStyleSheet("background-color: black")
            elif mode == 'Constant':
                self.proportional_input1.setEnabled(False)
                self.integral_input1.setEnabled(False)
                self.derivative_input1.setEnabled(False)
                self.proportional_input1.setStyleSheet("background-color: black")
                self.integral_input1.setStyleSheet("background-color: black")
                self.derivative_input1.setStyleSheet("background-color: black")
            elif mode == 'Off':
                self.proportional_input1.setEnabled(False)
                self.integral_input1.setEnabled(False)
                self.derivative_input1.setEnabled(False)
                # Set background to grey
                self.proportional_input1.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.integral_input1.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.derivative_input1.setStyleSheet("background-color: rgb(30, 31, 34)")

            elif mode == 'Fill':
                self.proportional_input1.setEnabled(False)
                self.integral_input1.setEnabled(False)
                self.derivative_input1.setEnabled(False)
                # Set background to grey
                self.proportional_input1.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.integral_input1.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.derivative_input1.setStyleSheet("background-color: rgb(30, 31, 34)")

            elif mode == 'Empty':
                self.proportional_input1.setEnabled(False)
                self.integral_input1.setEnabled(False)
                self.derivative_input1.setEnabled(False)
                # Set background to grey
                self.proportional_input1.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.integral_input1.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.derivative_input1.setStyleSheet("background-color: rgb(30, 31, 34)")

            # Set mode in syringe_pumps object
            self.syringe_pumps.set_mode(0, mode)

        elif pump == 'pump2':
            mode = self.pump2_dropdown.currentText()
            if mode == 'PID':
                self.proportional_input2.setEnabled(True)
                self.integral_input2.setEnabled(True)
                self.derivative_input2.setEnabled(True)
                self.proportional_input2.setStyleSheet("background-color: black")
                self.integral_input2.setStyleSheet("background-color: black")
                self.derivative_input2.setStyleSheet("background-color: black")

            elif mode == 'Constant':
                self.proportional_input2.setEnabled(False)
                self.integral_input2.setEnabled(False)
                self.derivative_input2.setEnabled(False)
                self.proportional_input2.setStyleSheet("background-color: black")
                self.integral_input2.setStyleSheet("background-color: black")
                self.derivative_input2.setStyleSheet("background-color: black")
            elif mode == 'Off':
                self.proportional_input2.setEnabled(False)
                self.integral_input2.setEnabled(False)
                self.derivative_input2.setEnabled(False)
                self.proportional_input2.setStyleSheet("background-color:rgb(30, 31, 34)")
                self.integral_input2.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.derivative_input2.setStyleSheet("background-color: rgb(30, 31, 34)")

            elif mode == 'Fill':
                self.proportional_input2.setEnabled(False)
                self.integral_input2.setEnabled(False)
                self.derivative_input2.setEnabled(False)
                self.proportional_input2.setStyleSheet("background-color:rgb(30, 31, 34)")
                self.integral_input2.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.derivative_input2.setStyleSheet("background-color: rgb(30, 31, 34)")

            elif mode == 'Empty':
                self.proportional_input2.setEnabled(False)
                self.integral_input2.setEnabled(False)
                self.derivative_input2.setEnabled(False)
                self.proportional_input2.setStyleSheet("background-color:rgb(30, 31, 34)")
                self.integral_input2.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.derivative_input2.setStyleSheet("background-color: rgb(30, 31, 34)")

            # Set mode in syringe_pumps object
            self.syringe_pumps.set_mode(1, mode)

        elif pump == 'pump3':
            mode = self.pump3_dropdown.currentText()
            if mode == 'PID':
                self.proportional_input3.setEnabled(True)
                self.integral_input3.setEnabled(True)
                self.derivative_input3.setEnabled(True)

            elif mode == 'Constant':
                self.proportional_input3.setEnabled(False)
                self.integral_input3.setEnabled(False)
                self.derivative_input3.setEnabled(False)
            elif mode == 'Off':
                self.proportional_input3.setEnabled(False)
                self.integral_input3.setEnabled(False)
                self.derivative_input3.setEnabled(False)
                self.proportional_input3.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.integral_input3.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.derivative_input3.setStyleSheet("background-color: rgb(30, 31, 34)")

            elif mode == 'Fill':
                self.proportional_input3.setEnabled(False)
                self.integral_input3.setEnabled(False)
                self.derivative_input3.setEnabled(False)
                self.proportional_input3.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.integral_input3.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.derivative_input3.setStyleSheet("background-color: rgb(30, 31, 34)")
            elif mode == 'Empty':
                self.proportional_input3.setEnabled(False)
                self.integral_input3.setEnabled(False)
                self.derivative_input3.setEnabled(False)
                self.proportional_input3.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.integral_input3.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.derivative_input3.setStyleSheet("background-color: rgb(30, 31, 34)")

            # Set mode in syringe_pumps object
            self.syringe_pumps.set_mode(2, mode)

        elif pump == 'pump4':
            mode = self.pump4_dropdown.currentText()
            if mode == 'PID':
                self.proportional_input4.setEnabled(True)
                self.integral_input4.setEnabled(True)
                self.derivative_input4.setEnabled(True)
            elif mode == 'Constant':
                self.proportional_input4.setEnabled(False)
                self.integral_input4.setEnabled(False)
                self.derivative_input4.setEnabled(False)
            elif mode == 'Off':
                self.proportional_input4.setEnabled(False)
                self.integral_input4.setEnabled(False)
                self.derivative_input4.setEnabled(False)
                self.proportional_input4.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.integral_input4.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.derivative_input4.setStyleSheet("background-color: rgb(30, 31, 34)")
            elif mode == 'Fill':
                self.proportional_input4.setEnabled(False)
                self.integral_input4.setEnabled(False)
                self.derivative_input4.setEnabled(False)
                self.proportional_input4.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.integral_input4.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.derivative_input4.setStyleSheet("background-color: rgb(30, 31, 34)")
            elif mode == 'Empty':
                self.proportional_input4.setEnabled(False)
                self.integral_input4.setEnabled(False)
                self.derivative_input4.setEnabled(False)
                self.proportional_input4.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.integral_input4.setStyleSheet("background-color: rgb(30, 31, 34)")
                self.derivative_input4.setStyleSheet("background-color: rgb(30, 31, 34)")
            # Set mode in syringe_pumps object
            self.syringe_pumps.set_mode(3, mode)

    def sensor_on_change(self, pump):
        # Method that updates the GUI for different sensor options
        print(pump)
        if pump == 'pump1':
            state = self.sensor1_dropdown.currentText()
            print(state)
            print(type(state))
            if state == 'On':
                self.syringe_pumps.set_sensor(0, 1)
                # if sensor is on add PID item to Combobox
                # Check if PID is already in Combobox first
                if self.pump1_dropdown.findText('PID') == -1:
                    self.pump1_dropdown.addItem('PID')
            else:
                self.syringe_pumps.set_sensor(0, 0)
                # if sensor is off remove PID mode from Combobox
                # Find index of PID mode
                if self.pump1_dropdown.findText('PID') != -1:
                    idx = self.pump1_dropdown.findText('PID')
                    self.pump1_dropdown.removeItem(idx)
                # If mode is PID set mode to constant
                if self.pump1_dropdown.currentText() == 'PID':
                    self.pump1_dropdown.setCurrentText('Constant')

            # print info

        elif pump == 'pump2':
            state = self.sensor2_dropdown.currentText()
            if state == 'On':
                self.syringe_pumps.set_sensor(1, 1)
                # if sensor is on add PID item to Combobox
                # Check if PID is already in Combobox first
                if self.pump2_dropdown.findText('PID') == -1:
                    self.pump2_dropdown.addItem('PID')
            else:
                self.syringe_pumps.set_sensor(1, 0)
                # if sensor is off remove PID mode from Combobox
                # Find index of PID mode
                if self.pump2_dropdown.findText('PID') != -1:
                    idx = self.pump2_dropdown.findText('PID')
                    self.pump2_dropdown.removeItem(idx)
                # If mode is PID set mode to constant
                if self.pump2_dropdown.currentText() == 'PID':
                    self.pump2_dropdown.setCurrentText('Constant')

        elif pump == 'pump3':
            state = self.sensor3_dropdown.currentText()
            if state == 'On':
                # if sensor is on add PID item to Combobox
                # Check if PID is already in Combobox first
                if self.pump3_dropdown.findText('PID') == -1:
                    self.pump3_dropdown.addItem('PID')
                self.syringe_pumps.set_sensor(2, 1)
            else:
                self.syringe_pumps.set_sensor(2, 0)
                # if sensor is off remove PID mode from Combobox
                # Find index of PID mode
                if self.pump3_dropdown.findText('PID') != -1:
                    idx = self.pump3_dropdown.findText('PID')
                    self.pump3_dropdown.removeItem(idx)
                # If mode is PID set mode to constant
                if self.pump3_dropdown.currentText() == 'PID':
                    self.pump3_dropdown.setCurrentText('Constant')

        elif pump == 'pump4':
            state = self.sensor4_dropdown.currentText()
            if state == 'On':
                # if sensor is on add PID item to Combobox
                # Check if PID is already in Combobox first
                if self.pump4_dropdown.findText('PID') == -1:
                    self.pump4_dropdown.addItem('PID')
                self.syringe_pumps.set_sensor(3, 1)
            else:
                self.syringe_pumps.set_sensor(3, 0)
                # if sensor is off remove PID mode from Combobox
                # Find index of PID mode
                if self.pump4_dropdown.findText('PID') != -1:
                    idx = self.pump4_dropdown.findText('PID')
                    self.pump4_dropdown.removeItem(idx)
                # If mode is PID set mode to constant
                if self.pump4_dropdown.currentText() == 'PID':
                    self.pump4_dropdown.setCurrentText('Constant')

# Application entry point
if __name__ == "__main__":
    app = QApplication([])
    window = SyringePumpApp()
    window.show()
    app.exec_()
