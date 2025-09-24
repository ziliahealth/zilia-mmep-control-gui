# Import necessary libraries
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout, \
    QWidget, QGridLayout, QTextEdit, QFileDialog, QComboBox, QGroupBox, QCheckBox, QDialog
from PyQt5.QtGui import QPixmap
from pyqtgraph import PlotWidget
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt
from collections import deque
import configparser
import os
import functools

# Assuming these are local modules for your project
from mcu_cmd import MCUThread
from zo import ZOThread
from guiupdater import GUIUpdater
from flow_controller import FlowControllerThread
from temperature_controller import TemperatureControllerThread
from do_sensor import DOSensorThread
from datasaver import DataSaver
from sequencerunner import SequenceRunner
from calibration_window import CalibrationWindow


class App(QMainWindow, QObject):
    """
    The main application window for the Zilia MMEP Control GUI.
    It handles UI setup, signal/slot connections, and backend thread management.
    """

    # --- Signals ---
    mcu_connect_signal = pyqtSignal()
    logging_signal = pyqtSignal()
    mcu_disconnect_signal = pyqtSignal()
    data_saver_stop_signal = pyqtSignal()

    # Flow controller signals
    fc_pump_type_change_signal = pyqtSignal(int, str)
    fc_flowrate_change_signal = pyqtSignal(int, float)
    fc_PID_change_signal = pyqtSignal(int, float, float, float)
    fc_pump_settings_peristaltic_signal = pyqtSignal(int, float, float)
    fc_pump_settings_syringe_signal = pyqtSignal(int, float, float)
    fc_mode_change_signal = pyqtSignal(int, str)
    fc_sensor_change_signal = pyqtSignal(int,bool)
    fc_enable_change_signal = pyqtSignal(int,bool)
    fc_dispense_signal = pyqtSignal(int, float, float)
    fc_dispense_settings_signal = pyqtSignal(int, float, float)

    # Temperature controller signals
    tc_enable_change_signal = pyqtSignal(int, bool)
    tc_target_temp_change_signal = pyqtSignal(int, float)
    tc_PID_change_signal = pyqtSignal(int, float, float, float)
    tc_sensor_change_signal = pyqtSignal(int, bool)
    tc_continuous_reading_signal = pyqtSignal( bool)

    # DO sensor signals
    do_enable_change_signal = pyqtSignal(int, bool)
    do_start_stop_signal = pyqtSignal(bool)

    def __init__(self):
        """
        Initializes the application by orchestrating the setup process.
        """
        super().__init__()

        self._init_state()
        self._setup_window()
        self._init_ui()
        self._create_layouts()
        self._setup_plots()
        self._init_backend()
        self._connect_signals()
        self._start_services()

    def _init_state(self):
        """Initializes all the state flags and parameters for the application."""
        self.running = False
        self.connected = False
        self.recording = False
        self.num_flow_controllers = 4
        self.num_temp_controllers = 2
        self.num_do_sensors = 2
        self.flowrate_buffer_length = 10000
        self.oxygen_buffer_length = 10000

    def _setup_window(self):
        """Sets the main window's title, size, and stylesheet."""
        self.setWindowTitle("Zilia MMEP Control GUI")
        self.setGeometry(100, 100, 1900, 1400)
        self.setStyleSheet("background-color: black; color: rgb(139,203,149)")

    def _init_ui(self):
        """Creates and initializes all UI widgets."""
        # --- Flow Controller Widgets ---
        self.flow_controller_labels = [QLabel(f'Flow Controller {i + 1}') for i in range(self.num_flow_controllers)]
        self.pump_type_dropdowns = [QComboBox() for _ in range(self.num_flow_controllers)]
        self.flow_rate_inputs = [QLineEdit() for _ in range(self.num_flow_controllers)]
        self.proportional_inputs = [QLineEdit() for _ in range(self.num_flow_controllers)]
        self.integral_inputs = [QLineEdit() for _ in range(self.num_flow_controllers)]
        self.derivative_inputs = [QLineEdit() for _ in range(self.num_flow_controllers)]
        self.diameter_inputs = [QLineEdit() for _ in range(self.num_flow_controllers)]  # Changed from QComboBox
        self.pitch_inputs = [QLineEdit() for _ in range(self.num_flow_controllers)]
        self.flow_controller_dropdowns = [QComboBox() for _ in range(self.num_flow_controllers)]
        self.sensor_dropdowns = [QComboBox() for _ in range(self.num_flow_controllers)]

        # Labels that change based on pump type
        self.diameter_label = QLabel("Syringe diameter [mm]:")
        self.pitch_label = QLabel("Thread Pitch [mm/rev]:")

        for i in range(self.num_flow_controllers):
            self.pump_type_dropdowns[i].addItems(['Syringe', 'Peristaltic', 'None'])
            self.flow_controller_dropdowns[i].addItems(['PID', 'Constant'])
            self.sensor_dropdowns[i].addItems(['Off', 'On'])

        # --- Flow Controller Controls Widgets ---
        self.fc_control_enable = [QCheckBox(f"Enable Controller {i + 1}") for i in range(self.num_flow_controllers)]
        self.fc_control_volume_inputs = [QLineEdit() for _ in range(self.num_flow_controllers)]
        self.fc_control_rate_inputs = [QLineEdit() for _ in range(self.num_flow_controllers)]
        self.fc_control_dispense_buttons = [QPushButton("Dispense Volume") for _ in range(self.num_flow_controllers)]
        for btn in self.fc_control_dispense_buttons:
            btn.setStyleSheet("border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")

        # --- Temperature Controller Widgets ---
        self.temp_controller_labels = [QLabel(f'Temp. Controller {i + 1}') for i in range(self.num_temp_controllers)]
        self.temp_enable_checkboxes = [QCheckBox() for i in range(self.num_temp_controllers)]
        self.target_temp_inputs = [QLineEdit() for _ in range(self.num_temp_controllers)]
        self.temp_proportional_inputs = [QLineEdit() for _ in range(self.num_temp_controllers)]
        self.temp_integral_inputs = [QLineEdit() for _ in range(self.num_temp_controllers)]
        self.temp_derivative_inputs = [QLineEdit() for _ in range(self.num_temp_controllers)]
        self.temp_sensor_dropdowns = [QComboBox() for _ in range(self.num_temp_controllers)]
        for i in range(self.num_temp_controllers):
            self.temp_sensor_dropdowns[i].addItems(['Off', 'On'])

        # --- DO Sensor Widgets ---
        self.do_sensor_start_button = QPushButton("Start DO Reading")
        self.do_sensor_calibrate_button = QPushButton("Calibrate")
        self.do_sensor_units_dropdown = QComboBox()
        self.do_sensor_fluid_dropdown = QComboBox()
        self.do_sensor_enables_checkboxes = []
        for i in range(self.num_do_sensors):
            self.do_sensor_enables_checkboxes.append(QCheckBox(f"Enable DO Sensor {i + 1}"))
        self.do_sensor_start_button.setStyleSheet(
            "border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        self.do_sensor_calibrate_button.setStyleSheet(
            "border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        self.do_sensor_units_dropdown.addItems(['Raw [V]', 'pO2 [mmhg]', 'SO2 [%]'])
        self.do_sensor_fluid_dropdown.addItems(['Water', 'Blood'])

        # --- Common Widgets ---
        self.connect_button = QPushButton("Connect MCU")
        self.load_config_button = QPushButton('Load configuration')
        self.save_config_button = QPushButton('Save configuration')
        self.save_data_button = QPushButton('Log data')
        self.load_sequence_button = QPushButton("Load Sequence")

        self.flowrate_plot_widget = PlotWidget()
        self.do_plot_widget = PlotWidget()
        self.temp_plot_widget = PlotWidget()
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)

    def _create_layouts(self):
        """Arranges all widgets into their respective layouts and sets the central widget."""
        flow_controller_group_box = self._create_flow_controller_groupbox()
        fc_controls_group_box = self._create_fc_controls_groupbox()
        temp_controller_group_box = self._create_temp_controller_groupbox()
        do_sensor_group_box = self._create_do_sensor_groupbox()
        config_btn_layout = self._create_config_buttons_layout()

        plot_layout = QHBoxLayout()
        plot_layout.addWidget(self.flowrate_plot_widget)
        plot_layout.addWidget(self.temp_plot_widget)
        plot_layout.addWidget(self.do_plot_widget)

        main_layout = QGridLayout()
        main_layout.addWidget(flow_controller_group_box, 0, 0, 9, 4)
        main_layout.addWidget(fc_controls_group_box, 0, 4, 9, 4)
        main_layout.addWidget(temp_controller_group_box, 0, 8, 9, 3)
        main_layout.addWidget(do_sensor_group_box, 0, 11, 9, 2)
        main_layout.addLayout(plot_layout, 9, 0, 1, 15)
        main_layout.addWidget(self.log_widget, 10, 0, 1, 13)
        main_layout.addLayout(config_btn_layout, 10, 13, 1, 2)

        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def _create_groupbox_stylesheet(self):
        """Returns a standard stylesheet for QGroupBox elements."""
        return """
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
        """

    def _create_flow_controller_groupbox(self):
        """Creates and returns the Flow Controllers QGroupBox."""
        group_box = QGroupBox("Flow Controllers")
        group_box.setStyleSheet(self._create_groupbox_stylesheet())
        layout = QGridLayout()
        layout.addWidget(QLabel("Pump Type:"), 1, 0)
        layout.addWidget(QLabel("Desired Flow Rate (µL/min):"), 2, 0)
        layout.addWidget(QLabel("Proportional (KP)"), 3, 0)
        layout.addWidget(QLabel("Integral (KI):"), 4, 0)
        layout.addWidget(QLabel("Derivative (KD):"), 5, 0)
        layout.addWidget(self.diameter_label, 6, 0)  # Use instance label
        layout.addWidget(self.pitch_label, 7, 0)  # Use instance label
        layout.addWidget(QLabel("Mode:"), 8, 0)
        layout.addWidget(QLabel("Sensor:"), 9, 0)

        for i in range(self.num_flow_controllers):
            col = i + 1
            layout.addWidget(self.flow_controller_labels[i], 0, col)
            layout.addWidget(self.pump_type_dropdowns[i], 1, col)
            layout.addWidget(self.flow_rate_inputs[i], 2, col)
            layout.addWidget(self.proportional_inputs[i], 3, col)
            layout.addWidget(self.integral_inputs[i], 4, col)
            layout.addWidget(self.derivative_inputs[i], 5, col)
            layout.addWidget(self.diameter_inputs[i], 6, col)  # Use QLineEdit
            layout.addWidget(self.pitch_inputs[i], 7, col)
            layout.addWidget(self.flow_controller_dropdowns[i], 8, col)
            layout.addWidget(self.sensor_dropdowns[i], 9, col)

        group_box.setLayout(layout)
        return group_box

    def _create_fc_controls_groupbox(self):
        """Creates and returns the Flow Controller Controls QGroupBox."""
        group_box = QGroupBox("Flow Controller Controls")
        group_box.setStyleSheet(self._create_groupbox_stylesheet())
        layout = QGridLayout()
        layout.addWidget(QLabel("Volume [µL]"), 0, 1)
        layout.addWidget(QLabel("Dispense Rate [µL/min]"), 0, 2)
        for i in range(self.num_flow_controllers):
            layout.addWidget(self.fc_control_enable[i], i + 1, 0)
            layout.addWidget(self.fc_control_volume_inputs[i], i + 1, 1)
            layout.addWidget(self.fc_control_rate_inputs[i], i + 1, 2)
            layout.addWidget(self.fc_control_dispense_buttons[i], i + 1, 3)
        layout.setRowStretch(self.num_flow_controllers + 1, 1)
        group_box.setLayout(layout)
        return group_box

    def _create_temp_controller_groupbox(self):
        """Creates and returns the Temperature Controllers QGroupBox."""
        group_box = QGroupBox("Temperature Controllers")
        group_box.setStyleSheet(self._create_groupbox_stylesheet())
        layout = QGridLayout()
        layout.addWidget(QLabel("Enable:"), 1, 0)
        layout.addWidget(QLabel("Target Temp (°C):"), 2, 0)
        layout.addWidget(QLabel("Proportional (KP)"), 3, 0)
        layout.addWidget(QLabel("Integral (KI):"), 4, 0)
        layout.addWidget(QLabel("Derivative (KD):"), 5, 0)
        layout.addWidget(QLabel("Sensor:"), 6, 0)
        for i in range(self.num_temp_controllers):
            col = i + 1
            layout.addWidget(self.temp_controller_labels[i], 0, col)
            layout.addWidget(self.temp_enable_checkboxes[i], 1, col)
            layout.addWidget(self.target_temp_inputs[i], 2, col)
            layout.addWidget(self.temp_proportional_inputs[i], 3, col)
            layout.addWidget(self.temp_integral_inputs[i], 4, col)
            layout.addWidget(self.temp_derivative_inputs[i], 5, col)
            layout.addWidget(self.temp_sensor_dropdowns[i], 6, col)
        layout.setRowStretch(7, 1)
        group_box.setLayout(layout)
        return group_box

    def _create_do_sensor_groupbox(self):
        """Creates and returns the DO Sensors QGroupBox."""
        group_box = QGroupBox("DO Sensors")
        group_box.setStyleSheet(self._create_groupbox_stylesheet())
        layout = QGridLayout()
        layout.addWidget(self.do_sensor_start_button, 0, 0, 1, 2)
        layout.addWidget(self.do_sensor_calibrate_button, 1, 0, 1, 2)
        layout.addWidget(QLabel("Units:"), 2, 0)
        layout.addWidget(self.do_sensor_units_dropdown, 2, 1)
        layout.addWidget(QLabel("Fluid Type:"), 3, 0)
        layout.addWidget(self.do_sensor_fluid_dropdown, 3, 1)
        for i in range(self.num_do_sensors):
            layout.addWidget(self.do_sensor_enables_checkboxes[i], i + 4, 0, 1, 2)
        layout.setRowStretch(6, 1)
        group_box.setLayout(layout)
        return group_box

    def _create_config_buttons_layout(self):
        """Creates and returns the layout for configuration buttons and the logo."""
        layout = QVBoxLayout()
        button_stylesheet = "border: 2px solid rgb(139,203,149); background: black; border-radius: 10px"
        self.connect_button.setStyleSheet(button_stylesheet)
        self.load_sequence_button.setStyleSheet(button_stylesheet)
        self.load_config_button.setStyleSheet(button_stylesheet)
        self.save_config_button.setStyleSheet(button_stylesheet)
        self.save_data_button.setStyleSheet(button_stylesheet)

        layout.addWidget(self.connect_button)
        layout.addWidget(self.load_sequence_button)
        layout.addWidget(self.load_config_button)
        layout.addWidget(self.save_config_button)
        layout.addWidget(self.save_data_button)

        logo_label = QLabel()
        if os.path.exists('logo.png'):
            pixmap = QPixmap('logo.png')
            logo_label.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo_label.setText("logo.png not found")
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)

        layout.addStretch()
        return layout

    def _setup_plots(self):
        """Configures the aesthetics and data structures for the plots."""
        # Plot Aesthetics
        self.flowrate_plot_widget.setLabel('bottom', 'Time', units='s')
        self.flowrate_plot_widget.setLabel('left', 'Flow Rate (µL/min)')
        self.flowrate_plot_widget.setTitle('Flow Sensors')
        self.flowrate_plot_widget.addLegend()
        self.do_plot_widget.addLegend()
        self.do_plot_widget.setLabel('bottom', 'Time', units='s')
        self.do_plot_widget.setLabel('left', ' Raw voltage', units='V')
        self.do_plot_widget.setTitle('Oxygen Sensors')
        self.temp_plot_widget.setLabel('bottom', 'Wavelength', units='nm')
        self.temp_plot_widget.setLabel('left', 'Intensity', units='°C')
        self.temp_plot_widget.setTitle('Temperature Sensors')

    def _init_backend(self):
        """Initializes all backend threads and worker objects."""
        self.mcu_thread = MCUThread()
        self.zo_thread = ZOThread()
        self.sequence_runner = SequenceRunner()
        self.flow_controllers = FlowControllerThread()
        self.temp_controllers = TemperatureControllerThread()
        self.do_sensors = DOSensorThread()
        self.gui_updater = GUIUpdater(self.log_widget,
                                      self.do_plot_widget,
                                      self.temp_plot_widget,
                                      self.flowrate_plot_widget,
                                      self.connect_button,
                                      self.flow_controllers.flow_controllers,
                                      self.temp_controllers.temperature_controllers,
                                      self.do_sensors.do_sensors)
        self.data_saver = DataSaver()

    def _connect_signals(self):
        """Connects all signals to their corresponding slots."""
        # Button Clicks
        self.connect_button.clicked.connect(self.connectdisconnect_button_onclick)
        self.load_config_button.clicked.connect(self.load_config_button_onclick)
        self.save_config_button.clicked.connect(self.save_config_button_onclick)
        self.save_data_button.clicked.connect(self.save_data_button_onclick)
        self.load_sequence_button.clicked.connect(self.sequence_onclick)
        self.do_sensor_calibrate_button.clicked.connect(self.open_calibration_window)

        # Flow Controller Inputs
        for i in range(self.num_flow_controllers):
            self.flow_rate_inputs[i].textChanged.connect(functools.partial(self.fc_flowrate_onchange, i))
            self.proportional_inputs[i].textChanged.connect(
                functools.partial(self.fc_PID_input_onchange, i, 'proportional'))
            self.integral_inputs[i].textChanged.connect(functools.partial(self.fc_PID_input_onchange, i, 'integral'))
            self.derivative_inputs[i].textChanged.connect(functools.partial(self.fc_PID_input_onchange, i, 'derivative'))
            self.flow_controller_dropdowns[i].currentTextChanged.connect(functools.partial(self.fc_mode_on_change, i))
            self.sensor_dropdowns[i].currentTextChanged.connect(functools.partial(self.fc_sensor_on_change, i))
            self.pump_type_dropdowns[i].currentTextChanged.connect(functools.partial(self.fc_pump_type_onchange, i))
            self.diameter_inputs[i].textChanged.connect(
                functools.partial(self.fc_pump_parameter_input_onchange, i))
            self.pitch_inputs[i].textChanged.connect(
                functools.partial(self.fc_pump_parameter_input_onchange, i))
            self.fc_control_enable[i].stateChanged.connect(functools.partial(self.fc_enable_onchange, i))
            self.fc_control_dispense_buttons[i].clicked.connect(
                functools.partial(self.fc_dispense_onclick, i))

        # Temperature Controller Inputs
        for i in range(self.num_temp_controllers):
            self.target_temp_inputs[i].textChanged.connect(
                functools.partial(self.tc_target_temp_onchange, i))
            self.temp_proportional_inputs[i].textChanged.connect(
                functools.partial(self.tc_PID_input_onchange, i, 'proportional'))
            self.temp_integral_inputs[i].textChanged.connect(
                functools.partial(self.tc_PID_input_onchange, i, 'integral'))
            self.temp_derivative_inputs[i].textChanged.connect(
                functools.partial(self.tc_PID_input_onchange, i, 'derivative'))
            self.temp_sensor_dropdowns[i].currentTextChanged.connect(functools.partial(self.tc_sensor_on_change, i))
            self.temp_enable_checkboxes[i].stateChanged.connect(functools.partial(self.tc_enable_onchange, i))

        # DO Sensor Inputs
        for i in range(self.num_do_sensors):
            self.do_sensor_enables_checkboxes[i].stateChanged.connect(functools.partial(self.do_enable_onchange, i))

        self.do_sensor_start_button.clicked.connect(self.do_start_stop_onclick)
        self.do_sensor_fluid_dropdown.currentTextChanged.connect(self.do_fluid_onchange)
        self.do_sensor_units_dropdown.currentTextChanged.connect(self.do_units_onchange)

        # Internal Application Signals
        self.mcu_connect_signal.connect(self.mcu_thread.connect_mcu)
        self.mcu_disconnect_signal.connect(self.mcu_thread.disconnect_mcu, Qt.DirectConnection)
        self.data_saver_stop_signal.connect(self.data_saver.stop_save)

        # Thread Communication Signals
        self.mcu_thread.flow_data_received.connect(self.gui_updater.process_sensor_data)
        self.mcu_thread.log_signal.connect(self.gui_updater.update_log)
        self.mcu_thread.connected_signal.connect(self.gui_updater.update_connectdisconnect_button)
        self.mcu_thread.connected_signal.connect(self.update_connected)
        self.mcu_thread.parser.do_data_signal.connect(self.do_sensors.process_do_serial_data)

        # Flow Controller Signals
        self.fc_pump_settings_peristaltic_signal.connect(self.flow_controllers.set_parameters_peristaltic)
        self.fc_pump_settings_syringe_signal.connect(self.flow_controllers.set_parameters_syringe)
        self.fc_dispense_signal.connect(self.flow_controllers.start_dispense)
        self.fc_PID_change_signal.connect(self.flow_controllers.set_pid)
        self.fc_enable_change_signal.connect(self.flow_controllers.start_stop)
        self.fc_flowrate_change_signal.connect(self.flow_controllers.set_flowrate)
        self.fc_mode_change_signal.connect(self.flow_controllers.set_mode)
        self.fc_sensor_change_signal.connect(self.flow_controllers.set_sensor)
        self.flow_controllers.mcu_signal.connect(self.mcu_thread.write_message)

        # Temperature Controller Signals
        self.tc_enable_change_signal.connect(self.temp_controllers.set_enable)
        self.tc_target_temp_change_signal.connect(self.temp_controllers.set_temperature)
        self.tc_PID_change_signal.connect(self.temp_controllers.set_pid)
        self.tc_sensor_change_signal.connect(self.temp_controllers.set_sensor)
        self.tc_continuous_reading_signal.connect(self.temp_controllers.set_continuous_reading)
        self.temp_controllers.mcu_signal.connect(self.mcu_thread.write_message)

        # DO Sensor Signals
        self.do_enable_change_signal.connect(self.do_sensors.do_enable)
        self.do_start_stop_signal.connect(self.do_sensors.do_start_stop)
        self.do_sensors.mcu_signal.connect(self.mcu_thread.write_message)
        self.do_sensors.update_plot_signal.connect(self.gui_updater.update_do_plot)


    def _start_services(self):
        """Loads the default configuration and starts all background threads."""
        self.load_config('default.ini')
        for i in range(self.num_flow_controllers):
            self.flow_controllers.set_flowrate(i, float(self.flow_rate_inputs[i].text()))
            self.flow_controllers.set_mode(i, self.flow_controller_dropdowns[i].currentText())

        self.mcu_thread.start()
        self.zo_thread.start()
        self.gui_updater.start()
        self.data_saver.start()
        self.flow_controllers.start()
        self.temp_controllers.start()
        self.do_sensors.start()
        self.sequence_runner.start()

    # --- Public Methods / Slots ---

    def open_calibration_window(self):
        """Opens the DO sensor calibration window."""
        calibration_dialog = CalibrationWindow(self)
        result = calibration_dialog.exec_()

        if result == QDialog.Accepted:
            self.log_widget.append("Calibration Accepted.")
        else:
            self.log_widget.append("Calibration Canceled.")

    def connectdisconnect_button_onclick(self):
        """Handles the connect/disconnect button click."""
        if not self.connected:
            self.mcu_connect_signal.emit()
        else:
            self.mcu_disconnect_signal.emit()

    def fc_enable_onchange(self, fc_index):
        """Enables or disables a flow controller in the controller thread."""
        try:
            enabled = self.fc_control_enable[fc_index].isChecked()
            self.fc_enable_change_signal.emit(fc_index, enabled)
        except IndexError:
            pass
    def fc_flowrate_onchange(self, fc_index):
        """Updates flow rate in the controller thread."""
        try:
            flowrate = float(self.flow_rate_inputs[fc_index].text())
            self.fc_flowrate_change_signal.emit(fc_index, flowrate)
        except (ValueError, IndexError):
            pass

    def fc_dispense_onclick(self, fc_index):
        """Handles the dispense button click for a flow controller."""
        try:
            volume = float(self.fc_control_volume_inputs[fc_index].text())
            rate = float(self.fc_control_rate_inputs[fc_index].text())
            # assert volume > 0 and rate > 0, "Volume and rate must be positive numbers."
            if volume <= 0 or rate <= 0:
                self.log_widget.append(f"Error: Volume and rate must be positive numbers for Flow Controller {fc_index + 1}.")
                return
            self.fc_dispense_signal.emit(fc_index, volume, rate)
        except (ValueError, IndexError):
            pass

    def fc_pump_type_onchange(self, fc_index):
        """Updates pump type in the controller thread and adjusts the UI accordingly."""
        try:
            pump_type = self.pump_type_dropdowns[fc_index].currentText()
            self.flow_controllers.set_pump_type(fc_index, pump_type)

            fc = self.flow_controllers.flow_controllers[fc_index]

            # Block signals to prevent onchange handlers from firing when we set text
            self.diameter_inputs[fc_index].blockSignals(True)
            self.pitch_inputs[fc_index].blockSignals(True)

            if pump_type == 'Syringe':
                self.diameter_label.setText("Syringe diameter [mm]:")
                self.pitch_label.setText("Thread Pitch [mm/rev]:")
                self.diameter_inputs[fc_index].setText(str(fc.diameter))
                self.pitch_inputs[fc_index].setText(str(fc.thread_pitch))
                self.diameter_inputs[fc_index].setEnabled(True)
                self.pitch_inputs[fc_index].setEnabled(True)
                self.fc_pump_settings_syringe_signal.emit(fc_index, fc.diameter, fc.thread_pitch)
            elif pump_type == 'Peristaltic':
                self.diameter_label.setText("Tube diameter [mm]:")
                self.pitch_label.setText("Calibration factor:")
                self.diameter_inputs[fc_index].setText(str(fc.tube_diameter))
                self.pitch_inputs[fc_index].setText(str(fc.peristaltic_calibration))
                self.diameter_inputs[fc_index].setEnabled(True)
                self.pitch_inputs[fc_index].setEnabled(True)
                self.fc_pump_settings_peristaltic_signal.emit(fc_index, fc.tube_diameter, fc.peristaltic_calibration)
            else:  # 'None'
                self.diameter_label.setText("Syringe diameter [mm]:")
                self.pitch_label.setText("Thread Pitch [mm/rev]:")
                self.diameter_inputs[fc_index].clear()
                self.pitch_inputs[fc_index].clear()
                self.diameter_inputs[fc_index].setEnabled(False)
                self.pitch_inputs[fc_index].setEnabled(False)


        finally:
            self.diameter_inputs[fc_index].blockSignals(False)
            self.pitch_inputs[fc_index].blockSignals(False)

    def fc_pump_parameter_input_onchange(self, fc_index):
        """
        Handles text changes for diameter/pitch inputs and calls the correct
        controller method based on the current pump type.
        """
        pump_type = self.pump_type_dropdowns[fc_index].currentText()
        try:
            if pump_type == 'Syringe':
                diameter = float(self.diameter_inputs[fc_index].text())
                pitch = float(self.pitch_inputs[fc_index].text())
                self.fc_pump_settings_syringe_signal.emit(fc_index, diameter, pitch)

            elif pump_type == 'Peristaltic':
                diameter = float(self.diameter_inputs[fc_index].text())
                calibration = float(self.pitch_inputs[fc_index].text())
                self.fc_pump_settings_peristaltic_signal.emit(fc_index, diameter, calibration)
        except (ValueError, IndexError):
            # Ignore errors from invalid float conversion, which happens during typing
            pass

    def fc_PID_input_onchange(self, fc_index, parameter):
        """Updates PID parameters in the controller thread."""
        try:
            kp = float(self.proportional_inputs[fc_index].text())
            ki = float(self.integral_inputs[fc_index].text())
            kd = float(self.derivative_inputs[fc_index].text())
            self.fc_PID_change_signal.emit(fc_index, kp, ki, kd)
        except (ValueError, IndexError):
            pass
        
    def fc_mode_on_change(self, fc_index):
        """Enables/disables PID input fields based on the selected mode."""
        try:
            mode = self.flow_controller_dropdowns[fc_index].currentText()
            pid_inputs = [self.proportional_inputs[fc_index], self.integral_inputs[fc_index],
                          self.derivative_inputs[fc_index]]
            is_pid_mode = (mode == 'PID')
            for widget in pid_inputs:
                widget.setEnabled(is_pid_mode)
                widget.setStyleSheet("background-color: black" if is_pid_mode else "background-color: rgb(30, 31, 34)")
            self.fc_mode_change_signal.emit(fc_index, mode)
        except IndexError:
            pass

    def fc_sensor_on_change(self, fc_index):
        """Adds or removes the 'PID' option based on sensor state."""
        try:
            state = self.sensor_dropdowns[fc_index].currentText()
            dropdown = self.flow_controller_dropdowns[fc_index]
            pid_exists = dropdown.findText('PID') != -1
            if state == 'On':
                self.fc_sensor_change_signal.emit(fc_index, True)
                if not pid_exists:
                    dropdown.addItem('PID')
            else:
                self.fc_sensor_change_signal.emit(fc_index, False)
                if pid_exists:
                    if dropdown.currentText() == 'PID':
                        dropdown.setCurrentText('Constant')
                    dropdown.removeItem(dropdown.findText('PID'))
        except IndexError:
            pass

    def tc_enable_onchange(self, tc_index):
        """Enables or disables a temperature controller in the controller thread."""
        try:
            enabled = self.temp_enable_checkboxes[tc_index].isChecked()
            self.tc_enable_change_signal.emit(tc_index, enabled)

        except IndexError:
            pass
    def tc_target_temp_onchange(self, tc_index):
        """Updates target temperature in the controller thread."""
        try:
            target_temp = float(self.target_temp_inputs[tc_index].text())
            self.tc_target_temp_change_signal.emit(tc_index, target_temp)
        except (ValueError, IndexError):
            pass

    def tc_PID_input_onchange(self, tc_index, parameter):
        """Updates PID parameters in the temperature controller thread."""
        try:
            kp = float(self.temp_proportional_inputs[tc_index].text())
            ki = float(self.temp_integral_inputs[tc_index].text())
            kd = float(self.temp_derivative_inputs[tc_index].text())
            self.tc_PID_change_signal.emit(tc_index, kp, ki, kd)
        except (ValueError, IndexError):
            pass

    def tc_sensor_on_change(self, tc_index):
        """Enables or disables the temperature sensor in the controller thread."""
        try:
            state = self.temp_sensor_dropdowns[tc_index].currentText()
            is_enabled = (state == 'On')
            self.tc_sensor_change_signal.emit(tc_index, is_enabled)

            any_sensor_enabled = any(tc.sensor for tc in self.temp_controllers.temperature_controllers)

            if any_sensor_enabled and not self.temp_controllers.continuous_reading:
                self.tc_continuous_reading_signal.emit(True)

            elif not any_sensor_enabled and self.temp_controllers.continuous_reading:
                self.tc_continuous_reading_signal.emit(False)
        except IndexError:
            pass

    def do_start_stop_onclick(self):
        """Handles the DO sensor start/stop button click."""
        if self.do_sensor_start_button.text() == "Start DO Reading":
            self.do_sensor_start_button.setText("Stop DO Reading")
            self.do_start_stop_signal.emit(True)
        else:
            self.do_sensor_start_button.setText("Start DO Reading")
            self.do_start_stop_signal.emit(False)

    def do_enable_onchange(self, sensor_index):
        """Enables or disables a DO sensor in the controller thread."""
        try:
            enabled = self.do_sensor_enables_checkboxes[sensor_index].isChecked()
            self.do_enable_change_signal.emit(sensor_index, enabled)
        except IndexError:
            pass

    def do_fluid_onchange(self):
        """Updates the fluid type in the DO sensor thread."""
        pass
    def do_units_onchange(self):
        """Updates the units in the DO sensor thread."""
        pass
    def update_connected(self, is_connected):
        """Updates the internal 'connected' state flag."""
        self.connected = is_connected

    def load_config(self, file_path):
        """Loads configuration from an INI file and updates the UI."""
        if not os.path.exists(file_path):
            self.log_widget.append(f"Configuration file not found: {file_path}")
            return
        config = configparser.ConfigParser()
        config.read(file_path)
        self.log_widget.append(f'Loaded configuration from {file_path}')
        for i in range(self.num_flow_controllers):
            section = f'Flow Controller {i + 1}'
            if not config.has_section(section): continue

            # Set pump type first to ensure UI updates correctly
            pump_type = config.get(section, 'PumpType', fallback='Syringe')
            self.pump_type_dropdowns[i].setCurrentText(pump_type)

            self.flow_rate_inputs[i].setText(config.get(section, 'FlowRate', fallback='0'))
            self.proportional_inputs[i].setText(config.get(section, 'KP', fallback='0'))
            self.integral_inputs[i].setText(config.get(section, 'KI', fallback='0'))
            self.derivative_inputs[i].setText(config.get(section, 'KD', fallback='0'))
            self.flow_controller_dropdowns[i].setCurrentText(
                config.get(section, 'Mode', fallback='Constant').capitalize())
            self.sensor_dropdowns[i].setCurrentText(config.get(section, 'Sensor', fallback='Off').capitalize())

            # Manually set the text for diameter/pitch after pump type is set
            fc = self.flow_controllers.flow_controllers[i]
            if fc.pump_type == 'Syringe':
                self.diameter_inputs[i].setText(config.get(section, 'SyringeDiameter', fallback=str(fc.diameter)))
                self.pitch_inputs[i].setText(config.get(section, 'ThreadPitch', fallback=str(fc.thread_pitch)))
            elif fc.pump_type == 'Peristaltic':
                self.diameter_inputs[i].setText(config.get(section, 'TubeDiameter', fallback=str(fc.tube_diameter)))
                self.pitch_inputs[i].setText(
                    config.get(section, 'CalibrationFactor', fallback=str(fc.peristaltic_calibration)))

    def load_config_button_onclick(self):
        """Opens a file dialog to load a configuration."""
        file_path, _ = QFileDialog.getOpenFileName(self, 'Load Configuration File', '', 'INI Files (*.ini)')
        if file_path:
            self.load_config(file_path)

    def sequence_onclick(self):
        """Handles loading and stopping a sequence file."""
        is_running_sequence = self.load_sequence_button.text() == "Stop"
        if is_running_sequence:
            self.load_sequence_button.setText("Load Sequence")
            # Re-enable controls if needed
        elif self.connected:
            sequence_file, _ = QFileDialog.getOpenFileName(self, 'Load Sequence File', '', 'JSON Files (*.json)')
            if sequence_file:
                self.sequence_runner.load_sequence(sequence_file)
                self.load_sequence_button.setText("Stop")
                # Disable controls if needed
        else:
            self.gui_updater.update_log('Please connect to the MCU before starting a sequence')

    def save_config_button_onclick(self):
        """Saves the current UI configuration to an INI file."""
        file_path, _ = QFileDialog.getSaveFileName(self, 'Save Configuration File', '', 'INI Files (*.ini)')
        if not file_path: return
        config = configparser.ConfigParser()
        for i in range(self.num_flow_controllers):
            section = f'Flow Controller {i + 1}'
            config.add_section(section)

            fc = self.flow_controllers.flow_controllers[i]
            pump_type = fc.pump_type
            config.set(section, 'PumpType', pump_type)

            config.set(section, 'FlowRate', self.flow_rate_inputs[i].text())
            config.set(section, 'KP', self.proportional_inputs[i].text())
            config.set(section, 'KI', self.integral_inputs[i].text())
            config.set(section, 'KD', self.derivative_inputs[i].text())
            config.set(section, 'Mode', self.flow_controller_dropdowns[i].currentText())
            config.set(section, 'Sensor', self.sensor_dropdowns[i].currentText())

            if pump_type == 'Syringe':
                config.set(section, 'SyringeDiameter', self.diameter_inputs[i].text())
                config.set(section, 'ThreadPitch', self.pitch_inputs[i].text())
            elif pump_type == 'Peristaltic':
                config.set(section, 'TubeDiameter', self.diameter_inputs[i].text())
                config.set(section, 'CalibrationFactor', self.pitch_inputs[i].text())

        with open(file_path, 'w') as config_file:
            config.write(config_file)
        self.log_widget.append(f"Configuration saved to {file_path}")

    def save_data_button_onclick(self):
        """Handles starting and stopping data logging."""
        if not self.recording:
            filepath, _ = QFileDialog.getSaveFileName(self, 'Save Data', '', 'CSV Files (*.csv)')
            if filepath:
                self.log_widget.append(f'Saving data to {filepath}')
                self.data_saver.set_filename(filepath)
                self.data_saver.start_save()
                self.recording = True
                self.save_data_button.setText('Stop Recording')
                self.mcu_thread.sensor_signal.connect(self.data_saver.save_data)
        else:
            self.recording = False
            self.save_data_button.setText('Log Data')
            self.data_saver_stop_signal.emit()
            self.mcu_thread.sensor_signal.disconnect(self.data_saver.save_data)


# Application entry point
if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec_())
