from PyQt5.QtCore import QObject, pyqtSlot
import datetime
import csv


class DataSaver(QObject):
    """
    A QObject to handle saving and reading sensor data to/from a sectioned CSV file.
    - It buffers data in memory during recording and writes a formatted file upon stopping.
    - It can also parse these files to load data back into the application.
    It's designed to be moved to a separate thread to avoid blocking the GUI.
    """

    def __init__(self):
        super().__init__()
        self.filename = None
        self.saving = False

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
            self.stop_save()  # Ensure any previous session is properly saved

        self.filename = filename
        self._clear_buffers()
        self.saving = True

    @pyqtSlot(list)
    def save_flow_data(self, data):
        """Buffers incoming flow data."""
        if not self.saving: return
        # Expected data format: [time_ms, index_1, flow_1, index_2, flow_2,...]
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
        # Expected data format: [time_ms, index_1, temp_1, duty_1, ...]
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
        """Buffers incoming DO sensor data."""
        if not self.saving: return
        # Expected data format: [time_ms, do_1_voltage, do_2_voltage]
        if len(data) >= 3:
            self.do_data_buffer.append((data[0], data[1], data[2]))

    @pyqtSlot()
    def stop_save(self):
        """Stops the logging session and writes all buffered data to the file."""
        if not self.saving:
            return

        self.saving = False
        #print(f"Stopping data saver and writing to {self.filename}...")

        try:
            with open(self.filename, 'w', newline='') as f:
                f.write(f"# Data logged on: {datetime.datetime.now()}\n")

                # Write Flow Data Section
                f.write("\n# --- FLOW DATA --- \n")
                f.write("Timestamp (ms),Controller Index,Flow (uL/min)\n")
                writer = csv.writer(f)
                writer.writerows(self.flow_data_buffer)

                # Write Temperature Data Section
                f.write("\n# --- TEMPERATURE DATA --- \n")
                f.write("Timestamp (ms),Controller Index,Temperature (C),Duty Cycle (%)\n")
                writer.writerows(self.temp_data_buffer)

                # Write DO Sensor Data Section
                f.write("\n# --- DO SENSOR DATA --- \n")
                f.write("Timestamp (ms),DO Sensor 1 (V),DO Sensor 2 (V)\n")
                writer.writerows(self.do_data_buffer)

            #print("File successfully written.")

        except (IOError, TypeError) as e:
            print(f"Error writing data to file: {e}")
        finally:
            self._clear_buffers()

    # --- DATA READING METHODS ---

    def _read_data_section(self, file_path, section_header, num_columns):
        """A generic method to read a specific section from the log file."""
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
                            # Skip lines that can't be converted or don't match column count
                            continue
        except FileNotFoundError:
            print(f"Error: File not found at {file_path}")
        except Exception as e:
            print(f"An error occurred while reading the file: {e}")
        return data

    def read_flow_data(self, file_path):
        """
        Reads the flow data section from a log file.
        Returns a list of tuples: [(timestamp, controller_index, flow_rate), ...]
        """
        return self._read_data_section(file_path, "# --- FLOW DATA ---", 3)

    def read_temp_data(self, file_path):
        """
        Reads the temperature data section from a log file.
        Returns a list of tuples: [(timestamp, controller_index, temperature, duty_cycle), ...]
        """
        return self._read_data_section(file_path, "# --- TEMPERATURE DATA ---", 4)

    def read_do_data(self, file_path):
        """
        Reads the DO sensor data section from a log file.
        Returns a list of tuples: [(timestamp, do_sensor_1, do_sensor_2), ...]
        """
        return self._read_data_section(file_path, "# --- DO SENSOR DATA ---", 3)

