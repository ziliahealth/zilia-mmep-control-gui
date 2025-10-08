# datasaver.py

import numpy as np
from PyQt5.QtCore import QObject, pyqtSlot
import datetime
import csv
from scipy.interpolate import interp1d

class DataSaver(QObject):
    """
    A QObject to handle saving, reading, and processing sensor data to/from a sectioned CSV file.
    - It buffers data in memory during recording and writes a formatted file upon stopping.
    - It can also parse these files and perform common processing tasks like slicing and interpolation.
    It's designed to be moved to a separate thread to avoid blocking the GUI.
    """
    def __init__(self, do_sensors):
        super().__init__()
        self.filename = None
        self.saving = False

        self.do_sensors = do_sensors
        # Buffers to hold data during a recording session
        self.flow_data_buffer = []
        self.temp_data_buffer = []
        self.do_data_buffer = []

    def _clear_buffers(self):
        """Clears all data buffers."""
        self.flow_data_buffer.clear()
        self.temp_data_buffer.clear()
        self.do_data_buffer.clear()

    @pyqtSlot(str)
    def start_saving_to_file(self, filename):
        """Prepares for a new logging session."""
        if self.saving:
            self.stop_save()

        self.filename = filename
        self._clear_buffers()
        self.saving = True

    @pyqtSlot(list)
    def save_flow_data(self, data):
        """Buffers incoming flow data."""
        if not self.saving: return
        time_ms = data[0]
        num_readings = (len(data) - 1) // 2
        for i in range(num_readings):
            index = data[1 + i * 2]
            flow = data[2 + i * 2]
            self.flow_data_buffer.append((time_ms, index, flow))

    @pyqtSlot(list)
    def save_temp_data(self, data):
        """Buffers incoming temperature data."""
        if not self.saving: return
        time_ms = data[0]
        num_readings = (len(data) - 1) // 3
        for i in range(num_readings):
            index = data[1 + i * 3]
            temp = data[2 + i * 3]
            duty_raw = data[3 + i * 3]
            duty_percent = (duty_raw / 65535.0) * 100.0
            self.temp_data_buffer.append((time_ms, index, temp, f"{duty_percent:.2f}"))

    @pyqtSlot(list)
    def save_do_data(self, data):
        """Buffers incoming DO sensor data.
        Expected data format: [time_ms, [index1, raw1, po2_1, so2_1], [index2, raw2, po2_2, so2_2], ...]
        """
        if not self.saving or not data:
            return

        time_ms = data[0]
        # Iterate over the sensor data sub-lists, which start from the second element (index 1)
        for sensor_reading in data[1:]:
            # Each sensor_reading is a list like [index, raw, po2, so2]
            if isinstance(sensor_reading, list) and len(sensor_reading) == 4:
                index, raw, po2, so2 = sensor_reading
                # Append a flat tuple to the buffer, ready for CSV writing.
                self.do_data_buffer.append((time_ms, index, raw, po2, so2))
    @pyqtSlot()
    def stop_save(self):
        """Stops the logging session and writes all buffered data to the file."""
        if not self.saving:
            return
        self.saving = False
        try:
            with open(self.filename, 'w', newline='') as f:
                f.write(f"# Data logged on: {datetime.datetime.now()}\n")
                ## write calibration info if available
                f.write("# Calibration Info:\n")
                for i in range(1,3):
                    sensor = self.do_sensors.do_sensors[i-1]
                    if sensor.clarke_electrode.is_calibrated:
                        coefs_low = sensor.clarke_electrode.cal_points['low'].model
                        coefs_high = sensor.clarke_electrode.cal_points['high'].model
                        f.write(f"# DO Sensor {i} Coefficients -> 0%: {coefs_low}, 20.995%: {coefs_high} \n# Valid Temperature Range: {sensor.clarke_electrode.valid_temp_range} Celsius\n")
                    else:
                        f.write(f"# DO Sensor {i} Coefficients: Not Calibrated\n")

                f.write("# Oxygen dissocation model parameters:\n")
                f.write(f"Dash 2010: {sensor.hemoglobin_model.pH}, pCO2: {sensor.hemoglobin_model.pCO2}, DPG: {sensor.hemoglobin_model.DPG}, Hct: {sensor.hemoglobin_model.Hct}\n")
                f.write("\n# --- FLOW DATA --- \n")
                f.write("Timestamp (ms),Controller Index,Flow (uL/min)\n")
                writer = csv.writer(f)
                writer.writerows(self.flow_data_buffer)
                f.write("\n# --- TEMPERATURE DATA --- \n")
                f.write("Timestamp (ms),Controller Index,Temperature (C),Duty Cycle (%)\n")
                writer.writerows(self.temp_data_buffer)
                f.write("\n# --- DO SENSOR DATA --- \n")
                f.write("Timestamp (ms),Sensor Index,Raw Voltage (V),pO2 (mmHg),sO2 (%)\n")  #
                writer.writerows(self.do_data_buffer)
        except (IOError, TypeError) as e:
            print(f"Error writing data to file: {e}")
        finally:
            self._clear_buffers()

    # --- DATA READING AND PARSING METHODS ---

    def _read_data_section(self, file_path, section_header, num_columns):
        """A generic method to read a specific section from the log file into a NumPy array."""
        data = []
        in_section = False
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    stripped_line = line.strip()
                    if not stripped_line:
                        continue
                    if stripped_line.startswith('#'):
                        in_section = (section_header in stripped_line)
                        continue
                    if in_section and not stripped_line.startswith('Timestamp'):
                        try:
                            parts = [float(p) for p in stripped_line.split(',')]
                            if len(parts) == num_columns:
                                data.append(tuple(parts))
                        except (ValueError, IndexError):
                            continue
            return np.array(data)
        except FileNotFoundError:
            print(f"Error: File not found at {file_path}")
            return np.array([])
        except Exception as e:
            print(f"An error occurred while reading the file: {e}")
            return np.array([])

    def read_do_data(self, file_path):
        """
        Reads the DO sensor data section and returns it in a dictionary format.
        Format: {'1': {'time': [...], 'voltage': [...]}, '2': {'time': [...]}}
        """
        raw_data = self._read_data_section(file_path, "# --- DO SENSOR DATA ---", 3)
        if raw_data.size == 0:
            return {}

        do_data_dict = {
            '1': {'time': raw_data[:, 0], 'voltage': raw_data[:, 1]},
            '2': {'time': raw_data[:, 0], 'voltage': raw_data[:, 2]}
        }
        return do_data_dict

    def read_temp_data(self, file_path):
        """
        Reads the temperature data section and returns it in a dictionary format.
        Format: {idx1: {'time': [...], 'temp': [...], 'duty': [...]}, idx2: ...}
        """
        raw_data = self._read_data_section(file_path, "# --- TEMPERATURE DATA ---", 4)
        if raw_data.size == 0:
            return {}

        temp_data_dict = {}
        # Get unique controller indices
        indices = np.unique(raw_data[:, 1])
        for idx in indices:
            # Find all rows for the current index
            mask = raw_data[:, 1] == idx
            controller_data = raw_data[mask]
            temp_data_dict[str(int(idx))] = {
                'time': controller_data[:, 0],
                'temp': controller_data[:, 2],
                'duty': controller_data[:, 3]
            }
        return temp_data_dict

    # --- DATA PROCESSING METHODS (MOVED FROM DataProcessor) ---

    def slice_data_by_time(self, data_dict, start_time=None, end_time=None):
        sliced_dict = {}
        for key, value_dict in data_dict.items():
            # This is the dictionary containing 'time' and other data arrays
            time_array = value_dict['time']

            # Defensive check to prevent a crash
            for sub_key, data_array in value_dict.items():
                if len(data_array) != len(time_array):
                    raise ValueError(
                        f"Data mismatch in sensor '{key}'. The '{sub_key}' array has "
                        f"{len(data_array)} entries, but the 'time' array has "
                        f"{len(time_array)} entries. Please check the source CSV file."
                    )

            # Create a boolean mask based on the time range
            mask = np.ones_like(time_array, dtype=bool)
            if start_time is not None:
                mask &= (time_array >= start_time)
            if end_time is not None:
                mask &= (time_array <= end_time)

            # If any data points fall within the time range, slice all arrays
            if np.any(mask):
                sliced_dict[key] = {}
                for sub_key, data_array in value_dict.items():
                    sliced_dict[key][sub_key] = data_array[mask]

        print(f"Sliced data from {start_time} to {end_time}")
        print(sliced_dict)
        return sliced_dict

    def slice_single_dataset_by_time(self, data_dict, start_time=None, end_time=None):
        # No loop needed, operate directly on data_dict
        sliced_dict = {}
        time_array = data_dict['time']

        # --- (The rest of your validation and masking logic is the same) ---

        mask = np.ones_like(time_array, dtype=bool)
        if start_time is not None:
            mask &= (time_array >= start_time)
        if end_time is not None:
            mask &= (time_array <= end_time)

        if np.any(mask):
            for sub_key, data_array in data_dict.items():
                # Note: We are not creating a nested dictionary in the output here
                sliced_dict[sub_key] = data_array[mask]

        return sliced_dict

    def interpolate_data(self, source_data_dict, target_time_array, keys: list):
        """
        Resamples data for specified keys from a source dictionary to match a target time array.

        Args:
            source_data_dict (dict): A dictionary containing a 'time' array and other data arrays.
                                     Example: {'time': [...], 'temp': [...], 'duty': [...]}
            target_time_array (np.ndarray): The 1D array of timestamps to interpolate onto.
            keys (list): A list of strings representing the keys of the data to be interpolated.
                         Example: ['temp', 'duty']

        Returns:
            np.ndarray: A 2D NumPy array where the first column is the target time array
                        and subsequent columns are the interpolated values for each key
                        in the order they were provided.
        """
        if 'time' not in source_data_dict:
            raise ValueError("source_data_dict must contain a 'time' key.")

        source_time = source_data_dict['time']

        # Initialize a list to hold all the columns of the final array.
        # The first column is always the target time.
        interpolated_columns = [target_time_array]

        # Loop through each key the user wants to interpolate
        for key in keys:
            if key not in source_data_dict:
                print(f"Warning: Key '{key}' not found in source_data_dict. Skipping.")
                continue

            source_values = source_data_dict[key]

            # Ensure the source time and source values have the same length
            if len(source_time) != len(source_values):
                raise ValueError(
                    f"Data mismatch for key '{key}'. The 'time' array has {len(source_time)} "
                    f"entries, but the '{key}' array has {len(source_values)} entries."
                )

            # Create the interpolation function for the current key
            interp_func = interp1d(source_time, source_values, kind='linear', fill_value="extrapolate")

            # Calculate the interpolated values at the target timestamps
            interpolated_values = interp_func(target_time_array)

            # Add the new column of interpolated values to our list
            interpolated_columns.append(interpolated_values)

        # If no valid keys were processed, return just the time array reshaped as a single column
        if len(interpolated_columns) <= 1:
            return target_time_array.reshape(-1, 1)

        # Stack the columns horizontally (as columns).
        # np.vstack treats them as rows, so we transpose (.T) to get the desired column structure.
        resampled_array = np.vstack(interpolated_columns).T

        return resampled_array

    def data_dict_from_arrays(self, data_array:np.array, index:str, type:str, data_dict:dict = None):
        # converts an input numpy array into accepted data dictionary format
        # if data_dict is provided, appends to it
        if data_dict is None:
            data_dict = {}
        if index not in data_dict:
            data_dict[index] = {}
        if type == 'do':
            if data_array.shape[1] != 2:
                raise ValueError("DO data array must have exactly 2 columns: time, voltage")
            data_dict[index]['time'] = data_array[:,0]
            data_dict[index]['voltage'] = data_array[:,1]
        elif type == 'temp':
            if data_array.shape[1] != 3:
                raise ValueError("Temperature data array must have at least 3 columns: time, temp, duty")
            data_dict[index]['time'] = data_array[:,0]
            data_dict[index]['temp'] = data_array[:,1]
            data_dict[index]['duty'] = data_array[:,2]

        elif type == 'flow':
            if data_array.shape[1] != 2:
                raise ValueError("Flow data array must have exactly 2 columns: time, flow")
            data_dict[index]['time'] = data_array[:,0]
            data_dict[index]['flow'] = data_array[:,1]

        else:
            raise ValueError("Type must be one of: 'do', 'temp', 'flow'")
        return data_dict


if __name__ == "__main__":
    # Simple test to verify functionality
    saver = DataSaver()
    filepath = r"C:\Users\marca\PycharmProjects\MMEP-Control-GUI\calibration_test.csv"
    do_data = saver.read_do_data(filepath)
    temp_data = saver.read_temp_data(filepath)
    resamp = saver.interpolate_data(temp_data['1'], do_data['1']['time'], ['temp', 'duty'])
    temp_data['1']['time'] = resamp[:, 0]
    temp_data['1']['temp'] = resamp[:, 1]
    temp_data['1']['duty'] = resamp[:, 2]

    # Slicing example
    sliced_temp = saver.slice_data_by_time(temp_data, start_time=1.9e6, end_time=2.2e6)
    sliced_do = saver.slice_data_by_time(do_data, start_time=1.9e6, end_time=2.2e6)