# Import necessary libraries
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, \
    QWidget, QGridLayout, QTextEdit, QFileDialog, QComboBox, QGroupBox, QCheckBox, QDialog
from PyQt5.QtGui import QPixmap
from pyqtgraph import PlotWidget
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt
from collections import deque
import configparser
import os as os

import numpy as np
from mcu_cmd import MCUThread
from zo import ZOThread
from guiupdater import GUIUpdater
from flow_controller import FlowControllerThread
from datasaver import DataSaver
from sequencerunner import SequenceRunner
from calibration_window import CalibrationWindow


# ...
# Define the main application window
class App(QMainWindow, QObject):
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
        self.num_flow_controllers = 4
        self.num_temp_controllers = 2

        # Initialize UI elements
        self.setWindowTitle("Zilia MMEP Control GUI")
        self.setGeometry(100, 100, 1900, 800)  # Adjust the initial window size as needed
        self.setStyleSheet("background-color: black; color: rgb(139,203,149)")

        # --- Flow Controller Widget Initialization ---
        self.flow_controller_labels = []
        self.pump_type_dropdowns = []
        self.flow_rate_inputs = []
        self.proportional_inputs = []
        self.integral_inputs = []
        self.derivative_inputs = []
        self.diameter_dropdowns = []
        self.flow_controller_dropdowns = []
        self.sensor_dropdowns = []

        syringe_diameters = ['16 mm (12 mL)', '14 mm (10 mL)', '8 mm (3 mL)', '4.7 mm (1 mL)']
        pump_types = ['Syringe', 'Peristaltic', 'None']
        flow_controller_modes = ['PID', 'Constant']
        sensor_options = ['Off', 'On']

        for i in range(self.num_flow_controllers):
            self.flow_controller_labels.append(QLabel(f'Flow Controller {i + 1}'))
            pump_type_dd = QComboBox()
            pump_type_dd.addItems(pump_types)
            self.pump_type_dropdowns.append(pump_type_dd)
            self.flow_rate_inputs.append(QLineEdit())
            self.proportional_inputs.append(QLineEdit())
            self.integral_inputs.append(QLineEdit())
            self.derivative_inputs.append(QLineEdit())
            diameter_dd = QComboBox()
            diameter_dd.addItems(syringe_diameters)
            self.diameter_dropdowns.append(diameter_dd)
            flow_controller_dd = QComboBox()
            flow_controller_dd.addItems(flow_controller_modes)
            self.flow_controller_dropdowns.append(flow_controller_dd)
            sensor_dd = QComboBox()
            sensor_dd.addItems(sensor_options)
            self.sensor_dropdowns.append(sensor_dd)

        # --- Flow Controller Controls Widget Initialization ---
        self.fc_control_checkboxes = []
        self.fc_control_volume_inputs = []
        self.fc_control_rate_inputs = []
        self.fc_control_dispense_buttons = []

        for i in range(self.num_flow_controllers):
            self.fc_control_checkboxes.append(QCheckBox(f"Enable Controller {i + 1}"))
            self.fc_control_volume_inputs.append(QLineEdit())
            self.fc_control_rate_inputs.append(QLineEdit())
            self.fc_control_dispense_buttons.append(QPushButton("Dispense Volume"))
            self.fc_control_dispense_buttons[i].setStyleSheet("border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")

        # --- Temperature Controller Widget Initialization ---
        self.temp_controller_labels = []
        self.temp_status_dropdowns = []
        self.target_temp_inputs = []
        self.temp_proportional_inputs = []
        self.temp_integral_inputs = []
        self.temp_derivative_inputs = []
        self.temp_sensor_dropdowns = []

        status_options = ['Off', 'On']

        for i in range(self.num_temp_controllers):
            self.temp_controller_labels.append(QLabel(f'Temp. Controller {i + 1}'))
            status_dd = QComboBox()
            status_dd.addItems(status_options)
            self.temp_status_dropdowns.append(status_dd)
            self.target_temp_inputs.append(QLineEdit())
            self.temp_proportional_inputs.append(QLineEdit())
            self.temp_integral_inputs.append(QLineEdit())
            self.temp_derivative_inputs.append(QLineEdit())
            sensor_dd = QComboBox()
            sensor_dd.addItems(sensor_options)
            self.temp_sensor_dropdowns.append(sensor_dd)

        # --- DO Sensor Widget Initialization ---
        self.do_sensor_start_button = QPushButton("Start DO Reading")
        self.do_sensor_start_button.setStyleSheet("border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        self.do_sensor_calibrate_button = QPushButton("Calibrate")
        self.do_sensor_calibrate_button.setStyleSheet("border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        self.do_sensor_units_dropdown = QComboBox()
        self.do_sensor_units_dropdown.addItems(['Raw [V]', 'pO2 [mmhg]', 'SO2 [%]'])

        self.do_sensor_fluid_dropdown = QComboBox()
        self.do_sensor_fluid_dropdown.addItems(['Water', 'Blood'])

        self.do_sensor_1_checkbox = QCheckBox("Enable Sensor 1")
        self.do_sensor_2_checkbox = QCheckBox("Enable Sensor 2")

        # Common Widgets
        self.start_button = QPushButton("Start Experiment")
        self.connect_button = QPushButton("Connect MCU")
        self.load_config_button = QPushButton('Load configuration')
        self.save_config_button = QPushButton('Save configuration')
        self.save_data_button = QPushButton('Log data')
        self.load_sequence_button = QPushButton("Load Sequence")

        self.flowrate_plot_widget = PlotWidget()
        self.oxygen_plot_widget = PlotWidget()
        self.zo_plot_widget = PlotWidget()
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)

        # ==================== LAYOUT GENERATION START ====================

        # --- Main Layout ---
        layout = QGridLayout()

        # --- Flow Controller GroupBox ---
        flow_controller_group_box = QGroupBox("Flow Controllers")
        flow_controller_group_box.setStyleSheet("""
            QGroupBox {
                border: 1px solid green;
                border-radius: 5px;
                margin-top: 10px;
                color: rgb(139,203,149);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
        """)
        flow_controller_layout = QGridLayout()
        flow_controller_layout.addWidget(QLabel("Pump Type:"), 1, 0)
        flow_controller_layout.addWidget(QLabel("Desired Flow Rate (µL/min):"), 2, 0)
        flow_controller_layout.addWidget(QLabel("Proportional (KP)"), 3, 0)
        flow_controller_layout.addWidget(QLabel("Integral (KI):"), 4, 0)
        flow_controller_layout.addWidget(QLabel("Derivative (KD):"), 5, 0)
        flow_controller_layout.addWidget(QLabel("Syringe diameter:"), 6, 0)
        flow_controller_layout.addWidget(QLabel("Mode:"), 7, 0)
        flow_controller_layout.addWidget(QLabel("Sensor:"), 8, 0)

        for i in range(self.num_flow_controllers):
            col = i + 1
            flow_controller_layout.addWidget(self.flow_controller_labels[i], 0, col)
            flow_controller_layout.addWidget(self.pump_type_dropdowns[i], 1, col)
            flow_controller_layout.addWidget(self.flow_rate_inputs[i], 2, col)
            flow_controller_layout.addWidget(self.proportional_inputs[i], 3, col)
            flow_controller_layout.addWidget(self.integral_inputs[i], 4, col)
            flow_controller_layout.addWidget(self.derivative_inputs[i], 5, col)
            flow_controller_layout.addWidget(self.diameter_dropdowns[i], 6, col)
            flow_controller_layout.addWidget(self.flow_controller_dropdowns[i], 7, col)
            flow_controller_layout.addWidget(self.sensor_dropdowns[i], 8, col)

        flow_controller_group_box.setLayout(flow_controller_layout)
        layout.addWidget(flow_controller_group_box, 0, 0, 9, 4)

        # --- Flow Controller Controls GroupBox ---
        fc_controls_group_box = QGroupBox("Flow Controller Controls")
        fc_controls_group_box.setStyleSheet("""
            QGroupBox {
                border: 1px solid green;
                border-radius: 5px;
                margin-top: 10px;
                color: rgb(139,203,149);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
        """)
        fc_controls_layout = QGridLayout()
        fc_controls_layout.addWidget(QLabel("Volume [µL]"), 0, 1)
        fc_controls_layout.addWidget(QLabel("Dispense Rate [µL/min]"), 0, 2)

        for i in range(self.num_flow_controllers):
            fc_controls_layout.addWidget(self.fc_control_checkboxes[i], i + 1, 0)
            fc_controls_layout.addWidget(self.fc_control_volume_inputs[i], i + 1, 1)
            fc_controls_layout.addWidget(self.fc_control_rate_inputs[i], i + 1, 2)
            fc_controls_layout.addWidget(self.fc_control_dispense_buttons[i], i + 1, 3)

        fc_controls_layout.setRowStretch(self.num_flow_controllers + 1, 1)  # Add stretch to push widgets up
        fc_controls_group_box.setLayout(fc_controls_layout)
        layout.addWidget(fc_controls_group_box, 0, 4, 9, 4)

        # --- Temperature Controller GroupBox ---
        temp_controller_group_box = QGroupBox("Temperature Controllers")
        temp_controller_group_box.setStyleSheet("""
            QGroupBox {
                border: 1px solid green;
                border-radius: 5px;
                margin-top: 10px;
                color: rgb(139,203,149);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
        """)
        temperature_controller_layout = QGridLayout()
        temperature_controller_layout.addWidget(QLabel("Status:"), 1, 0)
        temperature_controller_layout.addWidget(QLabel("Target Temp (°C):"), 2, 0)
        temperature_controller_layout.addWidget(QLabel("Proportional (KP)"), 3, 0)
        temperature_controller_layout.addWidget(QLabel("Integral (KI):"), 4, 0)
        temperature_controller_layout.addWidget(QLabel("Derivative (KD):"), 5, 0)
        temperature_controller_layout.addWidget(QLabel("Sensor:"), 6, 0)

        for i in range(self.num_temp_controllers):
            col = i + 1
            temperature_controller_layout.addWidget(self.temp_controller_labels[i], 0, col)
            temperature_controller_layout.addWidget(self.temp_status_dropdowns[i], 1, col)
            temperature_controller_layout.addWidget(self.target_temp_inputs[i], 2, col)
            temperature_controller_layout.addWidget(self.temp_proportional_inputs[i], 3, col)
            temperature_controller_layout.addWidget(self.temp_integral_inputs[i], 4, col)
            temperature_controller_layout.addWidget(self.temp_derivative_inputs[i], 5, col)
            temperature_controller_layout.addWidget(self.temp_sensor_dropdowns[i], 6, col)

        temperature_controller_layout.setRowStretch(7, 1)  # Add stretch to push widgets up
        temp_controller_group_box.setLayout(temperature_controller_layout)
        layout.addWidget(temp_controller_group_box, 0, 8, 9, 3)

        # --- DO Sensor GroupBox ---
        do_sensor_group_box = QGroupBox("DO Sensors")
        do_sensor_group_box.setStyleSheet("""
            QGroupBox {
                border: 1px solid green;
                border-radius: 5px;
                margin-top: 10px;
                color: rgb(139,203,149);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
        """)
        do_sensor_layout = QGridLayout()
        do_sensor_layout.addWidget(self.do_sensor_start_button, 0, 0, 1, 2)
        do_sensor_layout.addWidget(self.do_sensor_calibrate_button, 1, 0, 1, 2)
        do_sensor_layout.addWidget(QLabel("Units:"), 2, 0)
        do_sensor_layout.addWidget(self.do_sensor_units_dropdown, 2, 1)
        do_sensor_layout.addWidget(QLabel("Fluid Type:"), 3, 0)
        do_sensor_layout.addWidget(self.do_sensor_fluid_dropdown, 3, 1)
        do_sensor_layout.addWidget(self.do_sensor_1_checkbox, 4, 0, 1, 2)
        do_sensor_layout.addWidget(self.do_sensor_2_checkbox, 5, 0, 1, 2)
        do_sensor_layout.setRowStretch(6, 1)  # Add stretch to push widgets up
        do_sensor_group_box.setLayout(do_sensor_layout)
        layout.addWidget(do_sensor_group_box, 0, 11, 9, 2)

        # --- Control Buttons ---
        self.start_button.setStyleSheet(
            "border: 2px solid black ; background: black; border-radius: 10px; color: black")
        self.start_button.setEnabled(False)
        layout.addWidget(self.start_button, 1, 13, 2, 2)

        # --- Plots and Log ---
        plot_layout = QHBoxLayout()
        plot_layout.addWidget(self.flowrate_plot_widget)
        plot_layout.addWidget(self.oxygen_plot_widget)
        plot_layout.addWidget(self.zo_plot_widget)
        layout.addLayout(plot_layout, 9, 0, 1, 15)
        layout.addWidget(self.log_widget, 10, 0, 1, 13)

        # --- Configuration and File Buttons ---
        config_btn_layout = QVBoxLayout()
        config_btn_layout.addWidget(self.connect_button)
        self.connect_button.setStyleSheet("border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        config_btn_layout.addWidget(self.load_sequence_button)
        self.load_sequence_button.setStyleSheet(
            "border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        config_btn_layout.addWidget(self.load_config_button)
        self.load_config_button.setStyleSheet(
            "border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        config_btn_layout.addWidget(self.save_config_button)
        self.save_config_button.setStyleSheet(
            "border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        config_btn_layout.addWidget(self.save_data_button)
        self.save_data_button.setStyleSheet(
            "border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")

        # --- Add Logo ---
        logo_label = QLabel()
        if os.path.exists('logo.png'):
            pixmap = QPixmap('logo.png')
            logo_label.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            logo_label.setAlignment(Qt.AlignCenter)
        else:
            logo_label.setText("logo.png not found")
            logo_label.setAlignment(Qt.AlignCenter)
        config_btn_layout.addWidget(logo_label)

        config_btn_layout.addStretch()
        layout.addLayout(config_btn_layout, 10, 13, 1, 2)

        # ===================== LAYOUT GENERATION END =====================

        # Setup Plot Aesthetics
        self.flowrate_plot_widget.setLabel('bottom', 'Time', units='s')
        self.flowrate_plot_widget.setLabel('left', 'Flow Rate (µL/min)')
        self.flowrate_plot_widget.setTitle('Flow Rate')
        self.flowrate_plot_widget.addLegend()

        self.oxygen_plot_widget.addLegend()
        self.oxygen_plot_widget.setLabel('bottom', 'Time', units='s')
        self.oxygen_plot_widget.setLabel('left', ' O2 partial pressure', units='mmHg')
        self.oxygen_plot_widget.setTitle('Oxygen Saturation')

        self.zo_plot_widget.setLabel('bottom', 'Wavelength', units='nm')
        self.zo_plot_widget.setLabel('left', 'Intensity', units='A.U.')
        self.zo_plot_widget.setTitle('Raw spectrum')
        self.zo_plot_widget.setXRange(450, 800)
        self.zo_plot_widget.setYRange(0, 65000)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Initialize backend threads
        self.mcu_thread = MCUThread()
        self.zo_thread = ZOThread()
        self.sequence_runner = SequenceRunner()

        # --- Signal Connections ---
        self.start_button.clicked.connect(self.startstop_button_onclick)
        self.connect_button.clicked.connect(self.connectdisconnect_button_onclick)
        self.load_config_button.clicked.connect(self.load_config_button_onclick)
        self.save_config_button.clicked.connect(self.save_config_button_onclick)
        self.save_data_button.clicked.connect(self.save_data_button_onclick)
        self.load_sequence_button.clicked.connect(self.sequence_onclick)
        self.do_sensor_calibrate_button.clicked.connect(self.open_calibration_window)

        for i in range(self.num_flow_controllers):
            self.flow_rate_inputs[i].textChanged.connect(
                lambda text, flow_controller_index=i: self.flowrate_input_onchange(flow_controller_index))
            self.proportional_inputs[i].textChanged.connect(
                lambda text, flow_controller_index=i: self.PID_input_onchange(flow_controller_index, 'proportional'))
            self.integral_inputs[i].textChanged.connect(
                lambda text, flow_controller_index=i: self.PID_input_onchange(flow_controller_index, 'integral'))
            self.derivative_inputs[i].textChanged.connect(
                lambda text, flow_controller_index=i: self.PID_input_onchange(flow_controller_index, 'derivative'))
            self.flow_controller_dropdowns[i].currentTextChanged.connect(
                lambda text, flow_controller_index=i: self.mode_on_change(flow_controller_index))
            self.sensor_dropdowns[i].currentTextChanged.connect(
                lambda text, flow_controller_index=i: self.sensor_on_change(flow_controller_index))
            self.diameter_dropdowns[i].currentTextChanged.connect(
                lambda text, flow_controller_index=i: self.diameter_onchange(flow_controller_index))

        self.arduino_start_signal.connect(self.mcu_thread.start)
        self.arduino_stop_signal.connect(self.mcu_thread.stop)
        self.arduino_connect_signal.connect(self.mcu_thread.connect)
        self.arduino_disconnect_signal.connect(self.mcu_thread.close, Qt.DirectConnection)
        self.ZO_start_signal.connect(self.zo_thread.start)
        self.ZO_stop_signal.connect(self.zo_thread.stop)

        # --- Plotting Buffers and Setup ---
        self.flowrate_buffer_length = 10000
        self.oxygen_buffer_length = 10000
        self.flowrate_buffers = [deque(maxlen=self.flowrate_buffer_length) for _ in range(self.num_flow_controllers)]
        self.oxygen_buffers = [deque(maxlen=self.oxygen_buffer_length) for _ in range(2)]  # 2 oxygen sensors
        self.plot_pens = [(255, 255, 102), (139, 203, 149), (51, 204, 204), (0, 102, 255)]

        for i in range(self.num_flow_controllers):
            self.flowrate_plot_widget.plot(list(self.flowrate_buffers[i]), pen=self.plot_pens[i],
                                           name=f'flow_controller {i + 1}')

        self.oxygen_plot_widget.plot(list(self.oxygen_buffers[0]), pen=(255, 255, 102), name='Retina')
        self.oxygen_plot_widget.plot(list(self.oxygen_buffers[1]), pen=(139, 203, 149), name='Choroid')

        # Initialize GUI updater and connect signals
        self.gui_updater = GUIUpdater(self.log_widget, self.zo_plot_widget, self.start_button, self.connect_button)
        self.gui_updater.update_signal.connect(self.update_plot)
        self.mcu_thread.sensor_signal.connect(self.gui_updater.process_sensor_data)
        self.mcu_thread.log_signal.connect(self.gui_updater.update_log)
        self.mcu_thread.running_signal.connect(self.gui_updater.update_startstop_button)
        self.mcu_thread.running_signal.connect(self.update_running)
        self.mcu_thread.connected_signal.connect(self.gui_updater.update_connectdisconnect_button)
        self.mcu_thread.connected_signal.connect(self.update_connected)
        self.zo_thread.data_signal.connect(self.gui_updater.update_ZO_plot)

        # Initialize FlowControllerThread object and connect signals
        self.flow_controllers = FlowControllerThread()
        self.flow_controllers.mcu_signal.connect(self.mcu_thread.on_flow_controller_signal)
        self.mcu_thread.update_all_signal.connect(self.flow_controllers.set_all)

        # Initialize DataSaver object and connect signals
        self.data_saver = DataSaver()
        self.arduino_logging_signal.connect(self.mcu_thread.start_logging, Qt.DirectConnection)
        self.data_saver_stop_signal.connect(self.data_saver.stop_save)

        # Load default config and update flow_controllers object
        self.load_config('default.ini')
        for i in range(self.num_flow_controllers):
            self.flow_controllers.set_flow(i, float(self.flow_rate_inputs[i].text()))
            self.flow_controllers.set_mode(i, self.flow_controller_dropdowns[i].currentText())
            self.flow_controllers.flow_controllers[i].info()

        # Start threads
        self.mcu_thread.start()
        self.zo_thread.start()
        self.gui_updater.start()
        self.data_saver.start()
        self.flow_controllers.start()
        self.sequence_runner.start()

    def open_calibration_window(self):
        """Opens the DO sensor calibration window."""
        # Pass `self` to make the main window the parent
        calibration_dialog = CalibrationWindow(self)
        # `exec_()` makes the dialog modal, blocking the main window
        result = calibration_dialog.exec_()

        if result == QDialog.Accepted:
            print("Calibration Accepted")
            # Here you would retrieve the calibration data from the dialog
            # For example: cal_data = calibration_dialog.get_calibration_data()
            # And then apply it
        else:
            print("Calibration Canceled")

    def startstop_button_onclick(self):
        if not self.running:
            self.arduino_start_signal.emit()
            self.ZO_start_signal.emit()
        else:
            self.arduino_stop_signal.emit()
            self.ZO_stop_signal.emit()
        pass

    def connectdisconnect_button_onclick(self):
        if not self.connected:
            self.arduino_connect_signal.emit()
        else:
            print('disconnect')
            self.arduino_disconnect_signal.emit()

    def update_plot(self, data):
        data = data.strip().split(',')
        for i in range(self.num_flow_controllers):
            self.flowrate_buffers[i].append(float(data[i + 1]))
        self.oxygen_buffers[0].append(float(data[5]))
        self.oxygen_buffers[1].append(float(data[6]))
        self.flowrate_plot_widget.clear()
        self.oxygen_plot_widget.clear()
        for i in range(self.num_flow_controllers):
            self.flowrate_plot_widget.plot(list(self.flowrate_buffers[i]), pen=self.plot_pens[i],
                                           name=f'flow_controller {i + 1}')
        self.oxygen_plot_widget.plot(list(self.oxygen_buffers[0]), pen=(255, 255, 102), name='Retina')
        self.oxygen_plot_widget.plot(list(self.oxygen_buffers[1]), pen=(0, 204, 102), name='Choroid')

    def flowrate_input_onchange(self, flow_controller_index):
        try:
            self.flow_controllers.set_flow(flow_controller_index,
                                           float(self.flow_rate_inputs[flow_controller_index].text()))
        except (ValueError, IndexError):
            pass

    def PID_input_onchange(self, flow_controller_index, parameter):
        try:
            if parameter == 'proportional':
                self.flow_controllers.set_pid(flow_controller_index,
                                              Kp=float(self.proportional_inputs[flow_controller_index].text()))
            elif parameter == 'integral':
                self.flow_controllers.set_pid(flow_controller_index,
                                              Ki=float(self.integral_inputs[flow_controller_index].text()))
            elif parameter == 'derivative':
                self.flow_controllers.set_pid(flow_controller_index,
                                              Kd=float(self.derivative_inputs[flow_controller_index].text()))
        except (ValueError, IndexError):
            pass

    def diameter_onchange(self, flow_controller_index):
        try:
            diameter_text = self.diameter_dropdowns[flow_controller_index].currentText()
            diameter_map = {
                '16 mm (12 mL)': 16.0, '14 mm (10 mL)': 14.3, '8 mm (3 mL)': 8.0, '4.7 mm (1 mL)': 4.7
            }
            if diameter_text in diameter_map:
                self.flow_controllers.set_diameter(flow_controller_index, diameter_map[diameter_text])
        except IndexError:
            pass

    def update_running(self, message):
        self.running = message
        print('update running')

    def update_connected(self, message):
        print('update connected')
        self.connected = message

    def load_config(self, file_path):
        config = configparser.ConfigParser()
        config.read(file_path)
        self.log_widget.append(f'Loaded configuration from {file_path}')
        for i in range(self.num_flow_controllers):
            section = f'Flow Controller {i + 1}'
            if not config.has_section(section): continue
            self.flow_rate_inputs[i].setText(config.get(section, 'FlowRate', fallback='0'))
            self.proportional_inputs[i].setText(config.get(section, 'KP', fallback='0'))
            self.integral_inputs[i].setText(config.get(section, 'KI', fallback='0'))
            self.derivative_inputs[i].setText(config.get(section, 'KD', fallback='0'))
            mode = config.get(section, 'Mode', fallback='Off').capitalize()
            self.flow_controller_dropdowns[i].setCurrentText(mode)
            sensor = config.get(section, 'Sensor', fallback='Off').capitalize()
            self.sensor_dropdowns[i].setCurrentText(sensor)
            diameter = config.get(section, 'Diameter', fallback='')
            diameter_map = {'16': '16 mm (12 mL)', '14.3': '14 mm (10 mL)', '8': '8 mm (3 mL)', '4.7': '4.7 mm (1 mL)'}
            if diameter in diameter_map:
                self.diameter_dropdowns[i].setCurrentText(diameter_map[diameter])
            self.mode_on_change(i)
            self.sensor_on_change(i)
            self.flowrate_input_onchange(i)
            self.PID_input_onchange(i, 'proportional')
            self.PID_input_onchange(i, 'integral')
            self.PID_input_onchange(i, 'derivative')
            self.diameter_onchange(i)

    def load_config_button_onclick(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Load Configuration File', '', 'INI Files (*.ini)')
        if file_path:
            self.load_config(file_path)

    def sequence_onclick(self):
        is_running_sequence = self.load_sequence_button.text() == "Stop"
        if is_running_sequence:
            self.load_sequence_button.setText("Load Sequence")
            enabled = True
        elif self.connected:
            sequence_file, _ = QFileDialog.getOpenFileName(self, 'Load Sequence File', '', 'JSON Files (*.json)')
            if sequence_file:
                self.sequence_runner.load_sequence(sequence_file)
                self.load_sequence_button.setText("Stop")
                enabled = False
            else:
                return
        else:
            self.gui_updater.update_log('Please connect to the MCU before starting a sequence')
            return
        for i in range(self.num_flow_controllers):
            self.proportional_inputs[i].setDisabled(not enabled)
            self.integral_inputs[i].setDisabled(not enabled)
            self.derivative_inputs[i].setDisabled(not enabled)

    def save_config_button_onclick(self):
        file_path, _ = QFileDialog.getSaveFileName(self, 'Save Configuration File', '', 'INI Files (*.ini)')
        if not file_path: return
        config = configparser.ConfigParser()
        for i in range(self.num_flow_controllers):
            section = f'flow_controller{i + 1}'
            config.add_section(section)
            config.set(section, 'FlowRate', self.flow_rate_inputs[i].text())
            config.set(section, 'KP', self.proportional_inputs[i].text())
            config.set(section, 'KI', self.integral_inputs[i].text())
            config.set(section, 'KD', self.derivative_inputs[i].text())
            config.set(section, 'Mode', self.flow_controller_dropdowns[i].currentText())
            config.set(section, 'Sensor', self.sensor_dropdowns[i].currentText())
            diameter_text = self.diameter_dropdowns[i].currentText()
            diameter_map = {'16 mm (12 mL)': '16', '14 mm (10 mL)': '14.3', '8 mm (3 mL)': '8', '4.7 mm (1 mL)': '4.7'}
            config.set(section, 'Diameter', diameter_map.get(diameter_text, ''))
        with open(file_path, 'w') as config_file:
            config.write(config_file)
        self.log_widget.append(f"Configuration saved to {file_path}")

    def save_data_button_onclick(self):
        if not self.recording:
            filepath, _ = QFileDialog.getSaveFileName(self, 'Save Data', '', 'CSV Files (*.csv)')
            if filepath:
                if os.path.exists(filepath):
                    base, ext = os.path.splitext(filepath)
                    filepath = f"{base}_1{ext}"
                self.log_widget.append(f'Saving data to {filepath}')
                self.data_saver.set_filename(filepath)
                self.data_saver.start_save()
                self.recording = True
                self.save_data_button.setText('Stop Recording')
                self.arduino_logging_signal.emit()
                self.mcu_thread.sensor_signal.connect(self.data_saver.save_data)
        else:
            self.recording = False
            self.save_data_button.setText('Log Data')
            self.data_saver_stop_signal.emit()
            self.mcu_thread.sensor_signal.disconnect(self.data_saver.save_data)

    def mode_on_change(self, flow_controller_index):
        try:
            mode = self.flow_controller_dropdowns[flow_controller_index].currentText()
            pid_inputs = [self.proportional_inputs[flow_controller_index], self.integral_inputs[flow_controller_index],
                          self.derivative_inputs[flow_controller_index]]
            if mode == 'PID':
                for widget in pid_inputs:
                    widget.setEnabled(True)
                    widget.setStyleSheet("background-color: black")
            else:
                for widget in pid_inputs:
                    widget.setEnabled(False)
                    widget.setStyleSheet("background-color: rgb(30, 31, 34)")
            self.flow_controllers.set_mode(flow_controller_index, mode)
        except IndexError:
            pass

    def sensor_on_change(self, flow_controller_index):
        try:
            state = self.sensor_dropdowns[flow_controller_index].currentText()
            flow_controller_dropdown = self.flow_controller_dropdowns[flow_controller_index]
            pid_exists = flow_controller_dropdown.findText('PID') != -1
            if state == 'On':
                self.flow_controllers.set_sensor(flow_controller_index, 1)
                if not pid_exists:
                    flow_controller_dropdown.addItem('PID')
            else:
                self.flow_controllers.set_sensor(flow_controller_index, 0)
                if pid_exists:
                    if flow_controller_dropdown.currentText() == 'PID':
                        flow_controller_dropdown.setCurrentText('Constant')
                    flow_controller_dropdown.removeItem(flow_controller_dropdown.findText('PID'))
        except IndexError:
            pass


# Application entry point
if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec_())

