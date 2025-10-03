import numpy as np
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
from dataclasses import dataclass, field
from datasaver import DataSaver  # Assuming DataSaver exists
from typing import Callable, Tuple


# --- Encapsulate Calibration State ---
@dataclass
class CalibrationPoint:
    """Holds the data and model for a single calibration point."""
    saturation: float
    model: np.ndarray = field(default=None, repr=False)
    temp_range: tuple[float, float] = field(default=None)
    voltage_range: tuple[float, float] = field(default=None)

    def fit(self, temp_data: np.ndarray, voltage_data: np.ndarray):
        """Fits the linear model and stores data ranges."""
        if temp_data.ndim != 2 or voltage_data.ndim != 2:
            raise ValueError("Input data must be 2D arrays [time, value].")
        self.model = np.polyfit(temp_data[:, 1], voltage_data[:, 1], deg=1)
        self.temp_range = (temp_data[:, 1].min(), temp_data[:, 1].max())
        self.voltage_range = (voltage_data[:, 1].min(), voltage_data[:, 1].max())

    def get_model(self) -> np.ndarray:
        """Returns the fitted model coefficients."""
        if self.model is None:
            raise RuntimeError("Model has not been fitted yet.")
        return self.model

    def get_temperature_range(self) -> tuple[float, float]:
        """Returns the temperature range of the calibration data."""
        if self.temp_range is None:
            raise RuntimeError("Temperature range is not defined.")
        return self.temp_range

    def get_voltage_range(self) -> tuple[float, float]:
        """Returns the voltage range of the calibration data."""
        if self.voltage_range is None:
            raise RuntimeError("Voltage range is not defined.")
        return self.voltage_range


class ClarkeElectrode:
    """
    Models a Clarke-type electrode, handling calibration and pO2 conversion.
    This class focuses on the scientific model, delegating I/O and plotting.
    """

    def __init__(self, vapor_pressure_func: Callable, atmospheric_pressure: float = 760.0):
        """Initializes the electrode model."""
        self.vapor_pressure_func = vapor_pressure_func
        self.atmospheric_pressure = atmospheric_pressure
        self.cal_points = {'low': None, 'high': None}

    @property
    def is_calibrated(self) -> bool:
        """Returns True if both low and high points are calibrated."""
        return all(point is not None for point in self.cal_points.values())

    @property
    def valid_temp_range(self) -> Tuple[float, float] | None:
        """
        Calculates the common (overlapping) temperature range for which the calibration is valid.
        Returns None if not fully calibrated or if there is no overlap.
        """
        if not self.is_calibrated:
            return None

        low_range = self.cal_points['low'].temp_range
        high_range = self.cal_points['high'].temp_range

        start = max(low_range[0], high_range[0])
        end = min(low_range[1], high_range[1])

        return (start, end) if start < end else None

    @property
    def valid_voltage_range(self) -> Tuple[float, float] | None:
        """
        Calculates the common (overlapping) voltage range for which the calibration is valid.
        """
        if not self.is_calibrated:
            return None

        low_range = self.cal_points['low'].voltage_range
        high_range = self.cal_points['high'].voltage_range

        start = min(low_range[0], low_range[1])
        end = max(high_range[0], high_range[1])

        return (start, end) if start < end else None

    def calibrate_point(self, point_type: str, temp_array: np.ndarray, do_array: np.ndarray, saturation: float = None):
        """Calibrates a single point ('low' or 'high') by fitting a linear model."""
        point_type = point_type.lower()
        if point_type not in self.cal_points:
            raise ValueError("point_type must be either 'low' or 'high'")
        if not np.array_equal(temp_array[:, 0], do_array[:, 0]):
            raise ValueError("Temperature and DO arrays must have matching timestamps.")

        saturation = saturation if saturation is not None else (0.0 if point_type == 'low' else 0.2095)

        cal_point = CalibrationPoint(saturation=saturation)
        cal_point.fit(temp_array, do_array)
        self.cal_points[point_type] = cal_point
        print(f"'{point_type.capitalize()}' point calibrated successfully.")

    def compute_henrys_pO2(self, temperature: float | np.ndarray, so2: float) -> float | np.ndarray:
        """Computes theoretical pO2 in water using Henry's Law."""
        water_vp = self.vapor_pressure_func(temperature)
        return (self.atmospheric_pressure - water_vp) * so2

    def update_atmospheric_pressure(self, new_pressure: float):
        """Updates the atmospheric pressure used in calculations."""
        self.atmospheric_pressure = new_pressure

    def get_po2(self, measured_voltage: float | np.ndarray, temperature: float | np.ndarray) -> float | np.ndarray:
        """Converts a measured voltage to pO2 in mmHg using the calibration."""
        if not self.is_calibrated:
            raise RuntimeError("Sensor is not calibrated. Calibrate both 'low' and 'high' points.")

        # --- MODIFIED: Check if temperature is within the valid common range ---
        valid_range = self.valid_temp_range
        if valid_range is None:
            raise RuntimeError("Calibration is invalid: no overlapping temperature range.")

        start, end = valid_range
        if np.any((temperature < start) | (temperature > end)):
            raise ValueError(f"Temperature is outside the valid calibration range of {start:.2f}°C to {end:.2f}°C.")
        # --- END MODIFICATION ---

        high_sat = self.cal_points['high'].saturation
        henrys_po2_high = self.compute_henrys_pO2(temperature, so2=high_sat)

        V_high = np.polyval(self.cal_points['high'].model, temperature)
        V_low = np.polyval(self.cal_points['low'].model, temperature)

        po2 = henrys_po2_high * (measured_voltage - V_low) / (V_high - V_low)

        #negative values could emerge in low oxygen conditions due to noise
        if po2 < 0:
            po2 = 0.0
        return po2

# --- Separate Visualization and Data Utilities ---

class DataProcessor:
    """A utility class for pre-processing sensor data."""

    @staticmethod
    def slice_data(do_array, temp_array, do_idx, temp_idx, start_time=None, end_time=None):
        """Selects sensor data and slices it within a time window."""
        do_sliced = do_array[:, [0, do_idx]]

        temp_column_index = -1
        for i in range(1, temp_array.shape[1], 3):
            if temp_array[0, i] == temp_idx:
                temp_column_index = i + 1
                break

        if temp_column_index == -1:
            raise ValueError(f"Temperature sensor with ID '{temp_idx}' not found in temp_array.")

        temp_sliced = temp_array[:, [0, temp_column_index]]

        if start_time is not None:
            do_sliced = do_sliced[do_sliced[:, 0] >= start_time]
            temp_sliced = temp_sliced[temp_sliced[:, 0] >= start_time]
        if end_time is not None:
            do_sliced = do_sliced[do_sliced[:, 0] <= end_time]
            temp_sliced = temp_sliced[temp_sliced[:, 0] <= end_time]

        print(do_sliced)
        print(temp_sliced)

        return do_sliced, temp_sliced

    @staticmethod
    def interpolate_temperature(temp_array, do_array):
        """Resamples temperature data to match DO data timestamps."""
        temp_interp_func = interp1d(temp_array[:, 0], temp_array[:, 1], kind='linear', fill_value="extrapolate")
        resampled_temp = np.zeros_like(do_array)
        resampled_temp[:, 0] = do_array[:, 0]
        resampled_temp[:, 1] = temp_interp_func(do_array[:, 0])
        return resampled_temp


class ElectrodeVisualizer:
    """A utility class for plotting electrode data and models."""

    @staticmethod
    def plot_timeseries(data_array: np.ndarray, title: str, ylabel: str):
        """Plots a simple time-series curve from a 2D numpy array."""
        plt.figure(figsize=(10, 6))
        plt.plot(data_array[:, 0], data_array[:, 1])
        plt.title(title)
        plt.xlabel('Timestamp')
        plt.ylabel(ylabel)
        plt.grid(True)
        plt.show()

    @staticmethod
    def plot_calibration_point(cal_point: CalibrationPoint, temp_array: np.ndarray, do_array: np.ndarray,
                               point_type: str):
        """Plots the data and linear fit for a single calibration point."""
        plt.figure(figsize=(10, 6))
        plt.scatter(temp_array[:, 1], do_array[:, 1], label='Data Points',
                    color='blue' if point_type == 'low' else 'red')
        plt.plot(temp_array[:, 1], np.polyval(cal_point.model, temp_array[:, 1]), 'k--',
                 label=f'Fit: y = {cal_point.model[0]:.4f}x + {cal_point.model[1]:.4f}')
        plt.title(f'{point_type.capitalize()} Point Calibration ({cal_point.saturation * 100:.2f}% Saturation)')
        plt.xlabel('Temperature (°C)')
        plt.ylabel('DO Sensor Voltage (V)')
        plt.legend()
        plt.grid(True)
        plt.show()

    @staticmethod
    def plot_calibration_surface(electrode: ClarkeElectrode):
        """Generates a contour plot of the electrode's calibration surface within the valid common range."""
        if not electrode.is_calibrated:
            raise RuntimeError("Cannot plot surface for uncalibrated electrode.")

        # --- MODIFIED: Use the valid common range for plotting ---
        temp_range_valid = electrode.valid_temp_range
        volt_range_valid = electrode.valid_voltage_range

        if temp_range_valid is None or volt_range_valid is None:
            raise RuntimeError("Calibration invalid: No overlapping range to plot.")

        temp_range = np.linspace(temp_range_valid[0], temp_range_valid[1], 100)
        volt_range = np.linspace(volt_range_valid[0], volt_range_valid[1], 100)
        # --- END MODIFICATION ---

        Temp_mesh, Volt_mesh = np.meshgrid(temp_range, volt_range)
        PO2_mesh = electrode.get_po2(Volt_mesh, Temp_mesh)

        fig, ax = plt.subplots(figsize=(12, 8))
        contour = ax.contourf(Temp_mesh, Volt_mesh, PO2_mesh, cmap='viridis', levels=100)
        ax.set_title('Calibrated pO2 Surface (Valid Common Range)')
        ax.set_xlabel('Temperature (°C)')
        ax.set_ylabel('DO Sensor Voltage (V)')
        fig.colorbar(contour, ax=ax, label='pO2 (mmHg)')
        plt.show()

def load_vapor_pressure_func(file_path: str) -> Callable:
        """Loads vapor pressure data and returns an interpolation function."""
        try:
            data = np.loadtxt(file_path, delimiter=',', skiprows=2)
            return interp1d(data[:, 0], data[:, 1], bounds_error=True)
        except FileNotFoundError:
            print(f"Error: '{file_path}' not found.")
            raise
# --- Main script demonstrating usage ---
if __name__ == "__main__":

    try:
        vapor_pressure_function = load_vapor_pressure_func("water_vapor_pressure.csv")
    except FileNotFoundError:
        exit()

    electrode = ClarkeElectrode(vapor_pressure_func=vapor_pressure_function, atmospheric_pressure=758.0)
    processor = DataProcessor()
    visualizer = ElectrodeVisualizer()
    datasaver = DataSaver()

    # 2. CALIBRATION
    path = r"C:\Users\marca\PycharmProjects\MMEP-Control-GUI\calibration_test.csv" # UPDATE THIS PATH
    high_do_data = datasaver.read_do_data(path)
    high_temp_data = datasaver.read_temp_data(path)
    high_do_data,high_temp_data = processor.slice_data(high_do_data, high_temp_data, do_idx=1, temp_idx=1,start_time=1.9e6, end_time=2.2e6)
    high_temp_data = processor.interpolate_temperature(high_temp_data, high_do_data)
    visualizer.plot_timeseries(high_temp_data, 'High Point DO Sensor Data', 'Temp')
    electrode.calibrate_point('high', temp_array=high_temp_data, do_array=high_do_data)
    visualizer.plot_calibration_point(electrode.cal_points['high'], high_temp_data, high_do_data, 'high')

    # --- LOW POINT ---
    low_temp_arr = np.array([np.linspace(2e6, 2.2e6, 1000), np.linspace(25, 38, 1000)]).T
    low_volt_arr = np.array(
        [low_temp_arr[:, 0], 0.004 * low_temp_arr[:, 1] - 0.075 + np.random.normal(0, 0.002, 1000)]).T
    electrode.calibrate_point('low', temp_array=low_temp_arr, do_array=low_volt_arr)
    visualizer.plot_calibration_point(electrode.cal_points['low'], low_temp_arr, low_volt_arr, 'low')

    if electrode.is_calibrated:
        valid_range = electrode.valid_temp_range
        print("\n--- Electrode is fully calibrated. ---")
        print(f"High point temp range: {electrode.cal_points['high'].temp_range[0]:.2f}°C to {electrode.cal_points['high'].temp_range[1]:.2f}°C\n")
        print(f"High point voltage range:   {electrode.cal_points['high'].voltage_range[0]:.4f} V to {electrode.cal_points['high'].voltage_range[1]:.4f} V")
        print(f"Low point temp range:  {electrode.cal_points['low'].temp_range[0]:.2f}°C to {electrode.cal_points['low'].temp_range[1]:.2f}°C")
        print(f"Low point voltage range:    {electrode.cal_points['low'].voltage_range[0]:.4f} V to {electrode.cal_points['low'].voltage_range[1]:.4f} V")
        print(f"VALID COMMON RANGE:    {valid_range[0]:.2f}°C to {valid_range[1]:.2f}°C")

        visualizer.plot_calibration_surface(electrode)
        # --- Test the range check in get_po2 ---
        temp_inside = 32  # Should be inside the 28-38 range
        temp_outside = 45.0  # Should be outside
        volt_test = 1

        try:
            po2_inside = electrode.get_po2(volt_test, temp_inside)
            print(f"\nSUCCESS: pO2 at {temp_inside}°C is {po2_inside:.2f} mmHg.")
        except ValueError as e:
            print(f"\nERROR as expected: {e}")

        try:
            po2_outside = electrode.get_po2(volt_test, temp_outside)
            print(f"SUCCESS: pO2 at {temp_outside}°C is {po2_outside:.2f} mmHg.")
        except ValueError as e:
            print(f"ERROR as expected: {e}")
