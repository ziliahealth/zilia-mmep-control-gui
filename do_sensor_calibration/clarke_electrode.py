# clarke_electrode.py

import numpy as np
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
from dataclasses import dataclass, field
from datasaver import DataSaver
from typing import Callable, Tuple


@dataclass
class CalibrationPoint:
    """Holds the data and model for a single calibration point."""
    saturation: float
    model: np.ndarray = field(default=None, repr=False)
    temp_range: tuple[float, float] = field(default=None, repr=False)
    voltage_range: tuple[float, float] = field(default=None, repr=False)

    def fit(self, temp_data: np.ndarray, voltage_data: np.ndarray):
        """Fits the linear model (voltage vs. temp) and stores data ranges."""
        self.model = np.polyfit(temp_data, voltage_data, deg=1)
        self.temp_range = (temp_data.min(), temp_data.max())
        self.voltage_range = (voltage_data.min(), voltage_data.max())

    def get_model(self) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model has not been fitted yet.")
        return self.model

class ClarkeElectrode:
    """
    Models a Clarke-type electrode, handling calibration and pO2 conversion.
    This class focuses on the scientific model, delegating I/O and plotting.
    """

    def __init__(self, vapor_pressure_func: Callable, atmospheric_pressure: float = 760.0):
        self.vapor_pressure_func = vapor_pressure_func
        self.atmospheric_pressure = atmospheric_pressure
        self.cal_points = {'low': None, 'high': None}

    @property
    def is_calibrated(self) -> bool:
        return all(point is not None for point in self.cal_points.values())

    @property
    def valid_temp_range(self) -> Tuple[float, float] | None:
        if not self.is_calibrated: return None
        low_range, high_range = self.cal_points['low'].temp_range, self.cal_points['high'].temp_range
        start, end = max(low_range[0], high_range[0]), min(low_range[1], high_range[1])
        return (start, end) if start < end else None

    @property
    def valid_voltage_range(self) -> Tuple[float, float] | None:
        if not self.is_calibrated: return None
        low_range, high_range = self.cal_points['low'].voltage_range, self.cal_points['high'].voltage_range
        start, end = min(low_range[0], low_range[1]), max(high_range[0], high_range[1])
        return (start, end) if start < end else None

    # --- MODIFIED METHOD ---
    def calibrate_point(self, point_type: str, temp_data_dict: dict, do_data_dict: dict, temp_sensor_id: str,
                        do_sensor_id: str, saturation: float = None):
        """
        Calibrates a single point ('low' or 'high') using data from dictionaries.
        This method extracts the relevant sensor data, interpolates temperature to DO
        timestamps, and fits a linear model.

        Args:
            point_type (str): The calibration point, either 'low' or 'high'.
            temp_data_dict (dict): The full temperature data dictionary from DataSaver.
            do_data_dict (dict): The full DO sensor data dictionary from DataSaver.
            temp_sensor_id (str): The key for the temperature sensor to use (e.g., '1').
            do_sensor_id (str): The key for the DO sensor to use (e.g., '1').
            saturation (float, optional): The O2 saturation for this point.
                                           Defaults to 0.0 for 'low' and 0.2095 for 'high'.
        """
        point_type = point_type.lower()
        if point_type not in self.cal_points:
            raise ValueError("point_type must be either 'low' or 'high'")

        # 1. Validate that the sensor IDs exist in the dictionaries
        if temp_sensor_id not in temp_data_dict:
            raise KeyError(f"Temperature sensor ID '{temp_sensor_id}' not found in temp_data_dict.")
        if do_sensor_id not in do_data_dict:
            raise KeyError(f"DO sensor ID '{do_sensor_id}' not found in do_data_dict.")

        # 2. Extract the 1D NumPy arrays for time and values
        temp_time = temp_data_dict[temp_sensor_id]['time']
        temp_values = temp_data_dict[temp_sensor_id]['temp']
        do_time = do_data_dict[do_sensor_id]['time']
        do_voltage_values = do_data_dict[do_sensor_id]['voltage']

        # 3. Interpolate temperature data to match the DO sensor's timestamps
        temp_interp_func = interp1d(temp_time, temp_values, kind='linear', fill_value="extrapolate")
        resampled_temp_values = temp_interp_func(do_time)

        # 4. Determine the O2 saturation level for this calibration point
        saturation = saturation if saturation is not None else (0.0 if point_type == 'low' else 0.2095)

        # 5. Fit the model and store the calibration point
        cal_point = CalibrationPoint(saturation=saturation)
        cal_point.fit(resampled_temp_values, do_voltage_values)
        self.cal_points[point_type] = cal_point
        print(f"'{point_type.capitalize()}' point for DO sensor '{do_sensor_id}' calibrated successfully.")

    def compute_henrys_pO2(self, temperature: float | np.ndarray, so2: float) -> float | np.ndarray:
        water_vp = self.vapor_pressure_func(temperature)
        return (self.atmospheric_pressure - water_vp) * so2

    def get_po2(self, measured_voltage: float | np.ndarray, temperature: float | np.ndarray) -> float | np.ndarray:
        if not self.is_calibrated:
            raise RuntimeError("Sensor is not calibrated.")
        valid_range = self.valid_temp_range
        if valid_range is None:
            raise RuntimeError("Calibration is invalid: no overlapping temperature range.")
        start, end = valid_range
        if np.any((temperature < start) | (temperature > end)):
            print(f"Warning: Temperature is outside valid range of {start:.2f}°C to {end:.2f}°C.")
            return np.NaN
        high_sat = self.cal_points['high'].saturation
        henrys_po2_high = self.compute_henrys_pO2(temperature, so2=high_sat)
        V_high = np.polyval(self.cal_points['high'].model, temperature)
        V_low = np.polyval(self.cal_points['low'].model, temperature)
        voltage_diff = V_high - V_low
        if np.any(np.isclose(voltage_diff, 0)):
            raise ValueError("Calibration error: High and low voltage points are indistinguishable.")
        po2 = henrys_po2_high * (measured_voltage - V_low) / voltage_diff
        return np.maximum(0, po2)

    def get_so2(self, po2: float | np.ndarray, temperature: float | np.ndarray) -> float | np.ndarray:
        """
        Given a calibrated a calibrated sensor, returns the oxygen saturation (sO2) of water from pO2 and temperature.
        :param po2:
        :param temperature:
        :return:
        """
        if not self.is_calibrated:
            return np.NaN
        valid_range = self.valid_temp_range
        if valid_range is None:
            return np.NaN
        start, end = valid_range
        if np.any((temperature < start) | (temperature > end)):
            return np.NaN
        water_vp = self.vapor_pressure_func(temperature)
        so2 = po2 / (self.atmospheric_pressure - water_vp)
        return np.clip(so2, 0, 1)


class ElectrodeVisualizer:
    @staticmethod
    def plot_timeseries(data_dict: dict, sensor_id: str, value_key: str, title: str, ylabel: str):
        """Plots a simple time-series curve from a data dictionary."""
        print(data_dict)
        plt.figure(figsize=(10, 6))
        plt.plot(data_dict[sensor_id]['time'], data_dict[sensor_id][value_key])
        plt.title(title)
        plt.xlabel('Timestamp (ms)')
        plt.ylabel(ylabel)
        plt.grid(True)
        plt.show()

    @staticmethod
    def plot_calibration_point(cal_point: CalibrationPoint, temp_dict: dict, do_dict: dict, temp_id: str, do_id: str,
                               point_type: str):
        """Plots the data and linear fit for a single calibration point."""
        plt.figure(figsize=(10, 6))
        temp_values = temp_dict[temp_id]['temp']
        do_values = do_dict[do_id]['voltage']
        plt.scatter(temp_values, do_values, label='Raw Data Points', color='blue' if point_type == 'low' else 'red',
                    alpha=0.5)
        voltage_fit = np.polyval(cal_point.model, temp_values)
        plt.plot(temp_values, voltage_fit, 'k--',
                 label=f'Fit: V = {cal_point.model[0]:.4f}*T + {cal_point.model[1]:.4f}')
        plt.title(f'{point_type.capitalize()} Point Calibration ({cal_point.saturation * 100:.2f}% O2)')
        plt.xlabel('Temperature (°C)')
        plt.ylabel('DO Sensor Voltage (V)')
        plt.legend()
        plt.grid(True)
        plt.show()

    # ... (plot_calibration_surface remains the same) ...
    @staticmethod
    def plot_calibration_surface(electrode: ClarkeElectrode):
        if not electrode.is_calibrated:
            raise RuntimeError("Cannot plot surface for uncalibrated electrode.")
        temp_range_valid, volt_range_valid = electrode.valid_temp_range, electrode.valid_voltage_range
        if temp_range_valid is None or volt_range_valid is None:
            raise RuntimeError("Calibration invalid: No overlapping range to plot.")
        temp_grid = np.linspace(temp_range_valid[0], temp_range_valid[1], 100)
        volt_grid = np.linspace(volt_range_valid[0], volt_range_valid[1], 100)
        Temp_mesh, Volt_mesh = np.meshgrid(temp_grid, volt_grid)
        PO2_mesh = electrode.get_po2(Volt_mesh, Temp_mesh)
        fig, ax = plt.subplots(figsize=(12, 8))
        contour = ax.contourf(Temp_mesh, Volt_mesh, PO2_mesh, cmap='viridis', levels=50)
        ax.set_title('Calibrated pO2 Surface')
        ax.set_xlabel('Temperature (°C)')
        ax.set_ylabel('DO Sensor Voltage (V)')
        fig.colorbar(contour, ax=ax, label='pO2 (mmHg)')
        plt.show()


def load_vapor_pressure_func(file_path: str) -> Callable:
    try:
        data = np.loadtxt(file_path, delimiter=',', skiprows=2)
        return interp1d(data[:, 0], data[:, 1], bounds_error=True)
    except FileNotFoundError:
        print(f"Error: Vapor pressure data file not found at '{file_path}'.")
        raise


# --- MAIN EXAMPLE BLOCK MODIFIED ---
if __name__ == "__main__":
    print("--- Running Clarke Electrode Example with Visualization ---")
    try:
        vapor_pressure_file = r"water_vapor_pressure.csv"
        vapor_pressure_function = load_vapor_pressure_func(vapor_pressure_file)
    except (FileNotFoundError, IndexError):
        exit()

    datasaver, visualizer = DataSaver(), ElectrodeVisualizer()
    electrode = ClarkeElectrode(vapor_pressure_func=vapor_pressure_function, atmospheric_pressure=758.0)

    filepath = r"C:\Users\marca\PycharmProjects\MMEP-Control-GUI\calibration_test.csv"
    do_data = datasaver.read_do_data(filepath)
    temp_data = datasaver.read_temp_data(filepath)
    resamp = datasaver.interpolate_data(temp_data['1'], do_data['1']['time'], ['temp', 'duty'])
    temp_data = datasaver.data_dict_from_arrays(resamp,'1','temp')

    # Slicing example
    sliced_temp = datasaver.slice_data_by_time(temp_data, start_time=1.9e6, end_time=2.2e6)
    sliced_do = datasaver.slice_data_by_time(do_data, start_time=1.9e6, end_time=2.2e6)

    visualizer.plot_timeseries(sliced_temp, sensor_id='1', value_key='temp',
                                title='Temperature Time Series', ylabel='Temperature (°C)')
    visualizer.plot_timeseries(sliced_do, sensor_id='1', value_key='voltage',
                                title='DO Sensor Voltage Time Series', ylabel='Voltage (V)')

    electrode.calibrate_point('high', sliced_temp, sliced_do, temp_sensor_id='1', do_sensor_id='1', saturation=0.2095)
    visualizer.plot_calibration_point(electrode.cal_points['high'], sliced_temp, sliced_do, temp_id='1', do_id='1',
                                      point_type='high')

    # Simulate low point data for demonstration
    low_point_temp = np.zeros((1000, 3))
    low_point_temp[:, 0] = np.linspace(1.9e6, 2.2e6, 1000)  # Timestamps
    low_point_temp[:, 1] = np.linspace(31, 38, 1000)     # Temperatures
    low_point_temp[:, 2] = np.linspace(100, 100, 1000)  # Duty cycle (constant)
    low_point_do = np.zeros((1000, 2))
    low_point_do[:, 0] = np.linspace(1.9e6, 2.2e6, 1000)  # Timestamps
    low_point_do[:, 1] = np.linspace(0.03, 0.08, 1000) + np.random.normal(0, 0.002, 1000)  # Voltages with noise
    low_do_dict = datasaver.data_dict_from_arrays(low_point_do, '1', 'do')
    low_temp_dict = datasaver.data_dict_from_arrays(low_point_temp, '1', 'temp')
    electrode.calibrate_point('low', low_temp_dict, low_do_dict, temp_sensor_id='1', do_sensor_id='1', saturation=0.0)
    visualizer.plot_calibration_point(electrode.cal_points['low'], low_temp_dict, low_do_dict, temp_id='1', do_id='1',
                                      point_type='low')

    visualizer.plot_calibration_surface(electrode)