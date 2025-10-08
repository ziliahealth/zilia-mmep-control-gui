import numpy as np
import os
from datetime import datetime


class DataSimulator:
    """
    A class to generate and manage simulated data log files.

    This class can create a new file with a timestamped header and
    provides methods to append different types of data (flow, temperature,
    dissolved oxygen) from NumPy arrays into distinct, labeled sections.
    """

    def __init__(self, filename="simulated_data.csv"):
        """
        Initializes the DataSimulator with a target filename.

        Args:
            filename (str): The name of the file to be created and managed.
        """
        self.filename = filename

    def create_file(self, overwrite=False):
        """
        Creates a new data file with a header.

        If the file already exists, it will not be modified unless
        'overwrite' is set to True.

        Args:
            overwrite (bool): If True, an existing file with the same name
                              will be overwritten. Defaults to False.
        """
        if os.path.exists(self.filename) and not overwrite:
            print(f"File '{self.filename}' already exists. Set overwrite=True to replace it.")
            return

        try:
            with open(self.filename, 'w') as f:
                f.write(f"# Data logged on: {datetime.now()}\n")
                f.write("\n")  # Add a blank line for spacing
            print(f"Successfully created file: '{self.filename}'")
        except IOError as e:
            print(f"Error creating file: {e}")

    def _append_data_block(self, section_title, header, data_array, fmt='%.6f'):
        """
        A private helper method to append a block of data to the file.

        Args:
            section_title (str): The title for the data section (e.g., "--- FLOW DATA ---").
            header (str): The comma-separated header for the CSV data.
            data_array (np.ndarray): The numpy array containing the data to append.
            fmt (str): The format specifier for numpy.savetxt.
        """
        if not os.path.exists(self.filename):
            print(f"File '{self.filename}' does not exist. Creating it now.")
            self.create_file()

        try:
            with open(self.filename, 'a') as f:
                # Add spacing before the new section
                f.write("\n")
                f.write(f"# {section_title} \n")
                f.write(f"{header}\n")
                # Append the numpy array data
                np.savetxt(f, data_array, delimiter=',', fmt=fmt)
            print(f"Appended data to section: '{section_title}'")
        except IOError as e:
            print(f"Error appending data: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def append_flow(self, data):
        """
        Appends flow data to the file.

        The input array should have 3 columns:
        Timestamp (ms), Controller Index, Flow (uL/min).

        Args:
            data (np.ndarray): A NumPy array of shape (n_samples, 3).
        """
        if data.shape[1] != 3:
            print("Error: Flow data must have 3 columns.")
            return
        header = "Timestamp (ms),Controller Index,Flow (uL/min)"
        # Use mixed formatting for integer timestamp/index and float flow
        self._append_data_block("--- FLOW DATA ---", header, data, fmt='%d,%d,%.1f')

    def append_temp(self, data):
        """
        Appends temperature data to the file with a placeholder for duty cycle.

        The input array should have 3 columns:
        Timestamp (ms), Controller Index, Temperature (C).
        A 'Dutycycle' column with a placeholder value of 100 will be added.

        Args:
            data (np.ndarray): A NumPy array of shape (n_samples, 3).
        """
        if data.shape[1] != 3:
            print("Error: Temperature data must have 3 columns.")
            return

        # Create a placeholder column for Dutycycle with the value 100
        dutycycle_placeholder = np.full((data.shape[0], 1), 100, dtype=int)

        # Combine the original data with the placeholder column
        output_data = np.hstack((data, dutycycle_placeholder))

        header = "Timestamp (ms),Controller Index,Temperature (C),Duty Cycle (%)"
        # Update format string for the new integer column
        self._append_data_block(" --- TEMPERATURE DATA --- ", header, output_data, fmt='%d,%d,%.4f,%d')

    def append_do(self, data):
        """
        Appends Dissolved Oxygen (DO) and Temperature data to the file.

        The input array should have 3 columns:
        Timestamp (ms), DO (%sat), Temperature (C).

        Args:
            data (np.ndarray): A NumPy array of shape (n_samples, 3).
        """
        if data.shape[1] != 3:
            print("Error: DO data must have 3 columns.")
            return
        header = "Timestamp (ms),DO Sensor 1 (V),DO Sensor 2 (V)"
        self._append_data_block("--- DO SENSOR DATA ---", header, data, fmt='%d,%.6f,%.6f')


# --- Example Usage ---
if __name__ == "__main__":
    # 1. Initialize the simulator for a specific file
    simulator = DataSimulator("calibration_test_sim.csv")

    # 2. Create a new file, overwriting if it exists from a previous run
    simulator.create_file(overwrite=False)

    # 3. Generate some sample data using NumPy
    # Flow data: 5 readings

    # Temperature data: 3 readings (now a 3-column array)
    timestamp = np.linspace(5020210, 5020210 + 5000 * 200, 5000, dtype=int)
    temp = np.linspace(25,40,5000)
    controller_index = np.ones((5000, 1), dtype=int)
    dutycycle = np.full((5000, 1), 100, dtype=int)  # Placeholder duty cycle

    temp_data = np.hstack((timestamp.reshape(-1, 1), controller_index, temp.reshape(-1, 1)))
    print(temp_data)

    # DO/Temp data: 4 readings
    do_1 = np.linspace(0.008,0.02,5000) + np.random.normal(0,0.003,5000)
    do_2 = np.linspace(0.01,0.03,5000) + np.random.normal(0,0.003,5000)
    do_array = np.hstack((timestamp.reshape(-1, 1), do_1.reshape(-1, 1), do_2.reshape(-1, 1)))
    # 4. Append the data blocks to the file
    simulator.append_temp(temp_data)
    simulator.append_do(do_array)

    print(f"\nFinished generating data in '{simulator.filename}'")

