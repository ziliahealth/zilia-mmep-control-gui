# Import necessary libraries
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QGroupBox, QComboBox, QFileDialog, QCheckBox,
    QLineEdit, QSlider, QLabel)
from PyQt5.QtCore import Qt, pyqtSignal
import pyqtgraph as pg
import numpy as np
import os
from do_sensor_calibration.blood_oxygen_dissociation_models import HemoglobinDissociationDash2010


class CalibrationWindow(QDialog):
    """
    A dialog window for calibrating two DO (Dissolved Oxygen) sensors.

    This window displays raw sensor and temperature data and allows the user to
    select two regions of interest (ROIs) on the main DO sensor plot to define
    calibration points. It also includes a panel for modeling blood oxygen
    dissociation curves.
    """
    load_data_signal = pyqtSignal()
    update_dissociation_signal = pyqtSignal(float, float)
    def __init__(self, main_app, parent=None ):
        super().__init__(parent)
        self.main_app = main_app
        self.setWindowTitle("do_sensor_calibration")
        self.setGeometry(150, 150, 1800, 800)
        self.setStyleSheet("background-color: black; color: rgb(139,203,149)")

        # --- Main Layout ---
        main_layout = QVBoxLayout()
        top_layout = QHBoxLayout()

        # --- Layout for Sensor Panels ---
        sensors_layout = QHBoxLayout()

        # Create panels for each sensor
        self.sensor1_group = self._create_sensor_panel("Sensor 1")
        self.sensor2_group = self._create_sensor_panel("Sensor 2")

        sensors_layout.addWidget(self.sensor1_group)
        sensors_layout.addWidget(self.sensor2_group)

        # --- Blood Oxygen Dissociation Model ---
        self.dissociation_model_dropdown = QComboBox()
        self.dissociation_model_dropdown.addItems(['Dash 2010'])
        self.pco2_input = QLineEdit("40")
        self.ph_input = QLineEdit("7.4")
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setMinimum(20)
        self.temp_slider.setMaximum(40)
        self.temp_slider.setValue(37)
        self.temp_slider_label = QLabel(f"Temperature: {self.temp_slider.value()} °C")
        self.dissociation_plot_widget = pg.PlotWidget()

        # --- Blood Oxygen Dissociation Model GroupBox ---
        dissociation_group_box = QGroupBox("Blood Oxygen Dissociation Model")
        dissociation_group_box.setStyleSheet("""
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
        dissociation_layout = QGridLayout()

        # Left side controls
        controls_layout = QGridLayout()
        controls_layout.addWidget(QLabel("Model:"), 0, 0)
        controls_layout.addWidget(self.dissociation_model_dropdown, 0, 1)
        controls_layout.addWidget(QLabel("pCO2 [mmHg]:"), 1, 0)
        controls_layout.addWidget(self.pco2_input, 1, 1)
        controls_layout.addWidget(QLabel("pH:"), 2, 0)
        controls_layout.addWidget(self.ph_input, 2, 1)
        controls_layout.addWidget(self.temp_slider_label, 3, 0, 1, 2)
        controls_layout.addWidget(self.temp_slider, 4, 0, 1, 2)
        controls_layout.setRowStretch(5, 1)

        # Add controls and plot to the main dissociation layout
        dissociation_layout.addLayout(controls_layout, 0, 0)
        dissociation_layout.addWidget(self.dissociation_plot_widget, 1,0)
        dissociation_layout.setColumnStretch(0, 2)  # Make plot take available space

        dissociation_group_box.setLayout(dissociation_layout)

        # --- MODIFICATION ---
        # Add sensor layout with a stretch factor of 2
        top_layout.addLayout(sensors_layout, 2)
        # Add the dissociation group box with a stretch factor of 1
        # This allows it to expand but keeps the layout balanced
        top_layout.addWidget(dissociation_group_box, 1)

        # --- Layout for Bottom Buttons ---
        buttons_layout = QHBoxLayout()
        self.load_button = QPushButton("Load Data")
        self.load_button.setStyleSheet("border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        self.accept_button = QPushButton("Accept")
        self.accept_button.setStyleSheet("border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("border: 2px solid rgb(139,203,149); background: black; border-radius: 10px")
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.load_button)
        buttons_layout.addWidget(self.accept_button)
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addStretch()

        # Add sub-layouts to the main layout
        main_layout.addLayout(top_layout)
        main_layout.addLayout(buttons_layout)
        self.setLayout(main_layout)

        # Connect button signals to dialog slots
        self.accept_button.clicked.connect(self.on_accept)
        self.cancel_button.clicked.connect(self.on_reject)
        self.dissociation_model_dropdown.currentTextChanged.connect(self.update_dissociation_curve)
        self.pco2_input.textChanged.connect(self.update_dissociation_curve)
        self.ph_input.textChanged.connect(self.update_dissociation_curve)
        self.temp_slider.valueChanged.connect(self.update_dissociation_curve)

        # Store plot items and ROIs in dictionaries for easy access
        self.plots = {}
        self.fitpen = pg.mkPen(color='r', width=3, style=Qt.DashLine)
        self.rois = {}
        self._store_plot_items()

        # Connect signals
        self.connect_signals()
        # Initial Plot
        self.update_dissociation_curve()

    def connect_signals(self):
        self.load_button.clicked.connect(self.load_data_button_onclick)
        self.update_dissociation_signal.connect(self.main_app.do_sensors.update_dissociation_parameters)

    def _create_sensor_panel(self, title):
        """Creates a group box containing a 2x2 grid of plots for a single sensor."""
        group_box = QGroupBox(title)
        group_box.setStyleSheet("""
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

        layout = QGridLayout()

        # Create the four plots for the sensor panel
        plot_do_reading = pg.PlotWidget(title="DO Sensor Reading")
        plot_temperature = pg.PlotWidget(title="Temperature")
        plot_cal_0 = pg.PlotWidget(title="Point 0 Calibration")
        plot_cal_1 = pg.PlotWidget(title="Point 1 Calibration")
        plot_cal_0.addLegend()
        plot_cal_1.addLegend()
        plot_cal_0.setLabel('bottom', 'Temperature (°C)')
        plot_cal_0.setLabel('left', 'DO Voltage (V)')
        plot_cal_1.setLabel('bottom', 'Temperature (°C)')
        plot_cal_1.setLabel('left', 'DO Voltage (V)')
        apply_cal_checkbox = QCheckBox("Apply Calibration")

        # Add plots to the 2x2 grid layout
        layout.addWidget(plot_do_reading, 0, 0)
        layout.addWidget(plot_temperature, 0, 1)
        layout.addWidget(plot_cal_0, 1, 0)
        layout.addWidget(plot_cal_1, 1, 1)
        layout.addWidget(apply_cal_checkbox, 2, 0, 1, 2, alignment=Qt.AlignCenter)

        # Add two interactive LinearRegionItems to the main DO sensor plot
        roi1 = pg.LinearRegionItem(values=(10, 30), brush=(255, 0, 0, 50), movable=True)
        roi2 = pg.LinearRegionItem(values=(60, 80), brush=(0, 0, 255, 50), movable=True)
        plot_do_reading.addItem(roi1)
        plot_do_reading.addItem(roi2)

        group_box.setLayout(layout)
        return group_box

        # In calibration_window.py

    def _store_plot_items(self):
        """
        Helper method to populate dictionaries with references to the plots, ROIs,
        and data curves for easier programmatic access.
        """
        for i, group in enumerate([self.sensor1_group, self.sensor2_group]):
            sensor_id = f"sensor{i + 1}"
            self.plots[sensor_id] = {}
            layout = group.layout()

            # Get widgets from layout and store them
            self.plots[sensor_id]['do_reading'] = layout.itemAtPosition(0, 0).widget()
            self.plots[sensor_id]['temperature'] = layout.itemAtPosition(0, 1).widget()
            self.plots[sensor_id]['cal_0'] = layout.itemAtPosition(1, 0).widget()
            self.plots[sensor_id]['cal_1'] = layout.itemAtPosition(1, 1).widget()
            self.plots[sensor_id]['apply_cal'] = layout.itemAtPosition(2, 0).widget()

            # --- MODIFICATION START ---
            # Create the curve items once and store references to them.
            # This allows us to update their data later without clearing the plot.
            self.plots[sensor_id]['do_curve'] = self.plots[sensor_id]['do_reading'].plot(pen='g')
            self.plots[sensor_id]['temp_curve'] = self.plots[sensor_id]['temperature'].plot(pen='y')
            # --- MODIFICATION END ---

            self.rois[sensor_id] = {}
            items = self.plots[sensor_id]['do_reading'].getPlotItem().items
            # Find the ROIs among the plot items
            rois_found = [item for item in items if isinstance(item, pg.LinearRegionItem)]
            if len(rois_found) >= 2:
                self.rois[sensor_id]['roi1'] = rois_found[0]
                self.rois[sensor_id]['roi2'] = rois_found[1]

                # Connect the signal for region changes to the update method
                self.rois[sensor_id]['roi1'].sigRegionChanged.connect(
                    lambda roi, s=sensor_id: self.update_cal_plot(s, 'cal_0', roi)
                )
                self.rois[sensor_id]['roi2'].sigRegionChanged.connect(
                    lambda roi, s=sensor_id: self.update_cal_plot(s, 'cal_1', roi)
                )

    def update_cal_plot(self, sensor_id, cal_plot_key, roi):
        """
        Slot to update the calibration plots when a LinearRegionItem is moved.
        It extracts the data from the main plot within the selected region and
        re-plots it in the corresponding calibration plot.
        """
        min_x, max_x = roi.getRegion()

        do_plot = self.plots[sensor_id]['do_reading']
        temp_plot = self.plots[sensor_id]['temperature']
        # Ensure there is data to process
        if not do_plot.listDataItems() or not temp_plot.listDataItems():
            return

        do_curve = do_plot.listDataItems()[0]
        do_time_data, do_voltage_data = do_curve.getData()
        temp_curve = temp_plot.listDataItems()[0]
        temp_time_data, temp_data = temp_curve.getData()


        if (do_time_data is not None and do_voltage_data is not None
                and temp_time_data is not None and temp_data is not None):
            try:
                mask = (do_time_data >= min_x) & (do_time_data <= max_x)
                selected_x = temp_data[mask]
                selected_y = do_voltage_data[mask]
                #interp x and y
                interpfunc = np.polyfit(selected_x, selected_y, 1)
                interp_x = np.linspace(np.min(selected_x), np.max(selected_x), 100)
                interp_y = np.polyval(interpfunc, interp_x)

                # Update the target calibration plot with the selected data
                cal_plot = self.plots[sensor_id][cal_plot_key]
                cal_plot.clear()
                #cal_plot.plot(selected_x, selected_y,cal_plot.plot(selected_x, selected_y, pen=None, symbol='o', symbolSize=5, name="DO Voltage vs Temp"),name= "DO Voltage vs Temp")
                scatter = pg.ScatterPlotItem(selected_x, selected_y, pen=None, symbol='o', size=5,alpha = 0.75, brush='g', name="DO Voltage vs Temp")
                cal_plot.addItem(scatter)
                cal_plot.plot(interp_x, interp_y, pen=self.fitpen, name=f"Linear Fit: y={interpfunc[0]:.4f}x + {interpfunc[1]:.4f}\n"
                                                                         f"R²={np.corrcoef(selected_x, selected_y)[0,1]**2:.4f}")
            except Exception:
                pass

    def update_dissociation_curve(self):
        self.temp_slider_label.setText(f"Temperature: {self.temp_slider.value()} °C")

        try:
            model = self.dissociation_model_dropdown.currentText()
            pco2 = float(self.pco2_input.text())
            ph = float(self.ph_input.text())
            temp = self.temp_slider.value()

            po2 = np.linspace(0.1, 150, 500)
            so2 = None

            if model == 'Severinghaus 1979':
                # Simplified Severinghaus calculation
                p50_std = 26.6
                p50 = p50_std * 10 ** (0.024 * (37 - temp) + 0.4 * (7.4 - ph) + 0.06 * (np.log10(40) - np.log10(pco2)))
                n = 2.7
                so2 = 100 / (1 + (p50 / po2) ** n)

            elif model == 'Dash 2010':
                # Simplified Dash-Bassingthwaighte model
                model = HemoglobinDissociationDash2010(pH=ph, pCO2=pco2)
                so2 = model.calculate_sO2(po2,temperature=temp) * 100  # Convert to percentage
                #emit signal
                self.update_dissociation_signal.emit(ph, pco2)

            if so2 is not None:
                self.dissociation_plot_widget.clear()
                self.dissociation_plot_widget.plot(po2, so2, pen='r')
                self.dissociation_plot_widget.setLabel('bottom', 'pO2 (mmHg)')
                self.dissociation_plot_widget.setLabel('left', 'SO2 (%)')
                self.dissociation_plot_widget.setTitle('Dissociation Curve')


        except (ValueError, ZeroDivisionError):
            # Handle cases with invalid input
            self.dissociation_plot_widget.clear()

    def load_data_button_onclick(self, data):
        #open file dialog to select data file
        file_path, _ = QFileDialog.getOpenFileName(self, 'Load sensor data file', '', 'CSV Files (*.csv)')
        if file_path:
            self.load_data(file_path)

    def load_data(self, file_path):
        if not os.path.exists(file_path):
            self.main_app.log_widget.append(f"Data file not found: {file_path}")
            return

        # Use the methods from the DataSaver object to get raw numpy arrays
        self.do_dict = self.main_app.data_saver.read_do_data(file_path)
        self.temp_dict = self.main_app.data_saver.read_temp_data(file_path)

        # interpolate temperature data to match DO timestamps
        for index in self.temp_dict:
            interpolated_temps = self.main_app.data_saver.interpolate_data(self.temp_dict[index], self.do_dict[index]['time'], keys=['temp','duty'])
            self.temp_dict[index]['time'] = self.do_dict[index]['time']
            self.temp_dict[index]['temp'] = interpolated_temps[:,1]
            self.temp_dict[index]['duty'] = interpolated_temps[:,2]
        # Pass the raw data directly to the plotting method
        self.update_time_plots(self.temp_dict, self.do_dict)

        # In calibration_window.py

    def update_time_plots(self, raw_temp_data, raw_do_data):
        """
        Updates the time plots with raw, unaligned DO and temperature data
        by updating the data of the existing curve items.
        """
        #interpolate temperature at same timestap as do data
        # --- 2. Update DO Sensor Plots ---
        for index in raw_do_data.keys():
            if len(raw_do_data[index]['time']) > 0:
             # Use setData() to update the curves without removing ROIs
                self.plots[f'sensor{index}']['do_curve'].setData(raw_do_data[index]['time'], raw_do_data[index]['voltage'])
            else:
            # If no data, clear the curves
                self.plots[f'sensor{index}']['do_curve'].clear()

        # --- 3. Update Temperature Plots ---

        # Update Sensor 1 Temperature Plot
        for index in raw_temp_data.keys():
            if len(raw_temp_data[index]['time']) > 0:
                self.plots[f'sensor{index}']['temp_curve'].setData(raw_temp_data[index]['time'], raw_temp_data[index]['temp'])
            else:
                self.plots[f'sensor{index}']['temp_curve'].clear()

        # Update ROIs to default positions
        start_time = raw_do_data['1']['time'][0] if len(raw_do_data['1']['time']) > 0 else 0
        new_roi1_region = (start_time + 10, start_time + 30)
        new_roi2_region = (start_time + 60, start_time + 80)
        self.rois['sensor1']['roi1'].setRegion(new_roi1_region)
        self.rois['sensor1']['roi2'].setRegion(new_roi2_region)
        self.rois['sensor2']['roi1'].setRegion(new_roi1_region)
        self.rois['sensor2']['roi2'].setRegion(new_roi2_region)

        # --- 4. Refresh Calibration ROI plots ---
        self.update_cal_plot('sensor1', 'cal_0', self.rois['sensor1']['roi1'])
        self.update_cal_plot('sensor1', 'cal_1', self.rois['sensor1']['roi2'])
        self.update_cal_plot('sensor2', 'cal_0', self.rois['sensor2']['roi1'])
        self.update_cal_plot('sensor2', 'cal_1', self.rois['sensor2']['roi2'])

    def on_accept(self):
        """
        Triggered when the 'Accept' button is clicked. It validates, slices,
        and calibrates the sensors for which the 'Apply Calibration' checkbox
        is checked.
        """
        low_point_do_dict = {}
        high_point_do_dict = {}
        low_point_temp_dict = {}
        high_point_temp_dict = {}
        for sensor_index in [1, 2]:
            sensor_id_str = f"sensor{sensor_index}"
            sensor_key = str(sensor_index)

            apply_cal = self.plots[sensor_id_str]['apply_cal'].isChecked()
            if not apply_cal:
                continue

            # 1. Validate that data has been loaded
            try:
                if self.do_dict[sensor_key] is None or self.temp_dict[sensor_key] is None or sensor_key not in self.do_dict:
                    self.main_app.log_widget.append(
                        f"Warning: No data loaded for Sensor {sensor_index}. Skipping calibration.")
                    continue

                #try:
                # 2. Get ROI ranges
                roi1_min, roi1_max = self.rois[sensor_id_str]['roi1'].getRegion()
                roi2_min, roi2_max = self.rois[sensor_id_str]['roi2'].getRegion()
                print(roi1_min, roi1_max, roi2_min, roi2_max)
                print(self.do_dict[sensor_key])
                print(self.temp_dict[sensor_key])

                # 3. Slice data based on ROI ranges
                low_point_do_dict[sensor_key] = self.main_app.data_saver.slice_single_dataset_by_time(
                    self.do_dict[sensor_key], int(roi1_min), int(roi1_max))
                high_point_do_dict[sensor_key] = self.main_app.data_saver.slice_single_dataset_by_time(
                    self.do_dict[sensor_key], int(roi2_min), int(roi2_max))
                low_point_temp_dict[sensor_key] = self.main_app.data_saver.slice_single_dataset_by_time(
                    self.temp_dict[sensor_key], int(roi1_min), int(roi1_max))
                high_point_temp_dict[sensor_key] = self.main_app.data_saver.slice_single_dataset_by_time(
                    self.temp_dict[sensor_key], int(roi2_min), int(roi2_max))

                print(low_point_do_dict)
                print(high_point_do_dict)
                print(low_point_temp_dict)
                print(high_point_temp_dict)



                self.main_app.do_sensors.do_sensors[sensor_index-1].clarke_electrode.calibrate_point('low', low_point_temp_dict, low_point_do_dict,
                                          temp_sensor_id=sensor_key, do_sensor_id=sensor_key,
                                          saturation=0.0)

                # Calibrate the high point (20.95% O2 - standard air)
                self.main_app.do_sensors.do_sensors[sensor_index-1].clarke_electrode.calibrate_point('high', high_point_temp_dict, high_point_do_dict,
                                          temp_sensor_id=sensor_key, do_sensor_id=sensor_key,
                                          saturation=0.2095)

                if self.main_app.do_sensors.do_sensors[sensor_index-1].clarke_electrode.is_calibrated:
                    self.main_app.log_widget.append(f"Sensor {sensor_index} calibrated successfully.")
                else:
                    self.main_app.log_widget.append(f"Sensor {sensor_index} calibration incomplete.")
            except Exception as e:
                self.main_app.log_widget.append(f"Error during calibration for Sensor {sensor_index}. Calibration skipped.")
        self.accept()


    def on_reject(self):
        self.close()
