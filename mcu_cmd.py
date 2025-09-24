from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QIODevice
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo
import time


class MCUCommands:
    """
    This class defines and formats the commands sent to the MCU.

    It handles the creation of command strings according to the firmware's
    specifications, including handlers, arguments, unique communication IDs,
    and checksums. Each method corresponds to a specific command the MCU
    can understand.
    """




    # Dissolved Oxygen Sensor Commands
    DO_START = '$DOSSR,START,'
    DO_STOP = '$DOSSR,STOP,'

    def __init__(self):
        self.com_id_counter = 0

    def _generate_com_id(self):
        """Generates a unique alphanumeric ID for each command."""
        self.com_id_counter += 1
        return f"{self.com_id_counter:04d}"

    def _calculate_checksum(self, command_body):
        """Calculates a checksum for the command string (placeholder)."""
        # The firmware currently doesn't use the checksum, so we send a placeholder.
        return 0

    def _format_command(self, base_command, args):
        """
        Constructs the final command string with a unique ID and checksum.

        Args:
            base_command (str): The starting part of the command (e.g., '$FLOWCTRL,START,').
            args (list): A list of arguments for the command.

        Returns:
            str: The fully formatted command string.
        """
        com_id = self._generate_com_id()

        if args:
            # Append arguments to the base command
            command_part = f"{base_command}{','.join(map(str, args))}"
        else:
            # If no args, remove the trailing comma from the base command
            command_part = base_command[:-1]

        command_body = f"{command_part},{com_id},1"
        checksum = self._calculate_checksum(command_body)
        return f"{command_body};\n"




    # ----- Dissolved Oxygen Sensor Methods -----
    def do_start_stop(self, start=True):
        """Starts or stops continuous DO sensor readings."""
        base_command = self.DO_START if start else self.DO_STOP
        return self._format_command(base_command, [])


class MCUResponse(QObject):
    """
    Parses responses from the MCU and emits corresponding signals.
    """
    # Define signals for different message types.
    # The payload will be a list of the message arguments.
    ok_signal = pyqtSignal(list)
    error_signal = pyqtSignal(list)
    flow_data_signal = pyqtSignal(list)
    temp_data_signal = pyqtSignal(list)
    do_data_signal = pyqtSignal(list)
    info_signal = pyqtSignal(str)  # For unhandled messages or logs

    # Define the response headers
    OK = '$OK,'
    ERROR = '$ERROR,'
    FLOW = '$FLOW,'
    TEMP = '$TEMP,'
    DO = '$DO,'

    def __init__(self):
        super().__init__()

    def parse(self, message):
        """
        Parses a raw message string from the MCU.

        Identifies the message type by its header and emits the
        appropriate signal with the message payload.

        Args:
            message (str): The raw string received from the serial port.
        """
        try:
            # Clean up the incoming message
            message = message.decode('utf-8')  # Ensure it's a string
            #remove ;\n at the end
            message = message.strip(';\n')
            if not message:
                return

            if message.startswith(self.FLOW):
                # Extract payload: timestamp, id1, flow1, id2, flow2, ...
                payload = message[len(self.FLOW):].strip(';').split(',')
                print(payload)
                self.flow_data_signal.emit(payload)
            elif message.startswith(self.TEMP):
                # Extract payload: timestamp, id1, temp1, ...
                payload = message[len(self.TEMP):].strip(';').split(',')
                print(payload)
                self.temp_data_signal.emit(payload)
            elif message.startswith(self.DO):
                # Extract payload: timestamp (int), do1(float), do2(float)
                payload = message[len(self.DO):].strip(';').split(',')
                payload = [int(payload[0]), float(payload[1]), float(payload[2])]
                self.do_data_signal.emit(payload)
            elif message.startswith(self.OK):
                # Extract payload: com_id, optional messages
                payload = message[len(self.OK):].strip(';').split(',')
                self.ok_signal.emit(payload)
            elif message.startswith(self.ERROR):
                # Extract payload: com_id, error message
                payload = message[len(self.ERROR):].strip(';').split(',')
                self.error_signal.emit(payload)
            else:
                # Emit any other messages as general info
                self.info_signal.emit(message)

        except Exception as e:
            self.info_signal.emit(f"Error parsing MCU message: '{message}'. Error: {e}")


class MCUThread(QThread):
    # Signals to be connected by the main application
    flow_data_received = pyqtSignal(list)
    temp_data_received = pyqtSignal(list)
    do_data_received = pyqtSignal(list)
    ack_received = pyqtSignal(list)
    error_received = pyqtSignal(list)
    log_signal = pyqtSignal(str)  # For general logging and info

    # Internal signals for thread management
    running_signal = pyqtSignal(bool)
    connected_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()

        self.connected = False
        self.running = False
        self.mcu = None
        self.commands = MCUCommands()
        self.parser = MCUResponse()

        # Connect the parser's signals to this thread's signals
        self.parser.flow_data_signal.connect(self.flow_data_received)
        self.parser.temp_data_signal.connect(self.temp_data_received)
        self.parser.do_data_signal.connect(self.do_data_received)
        self.parser.ok_signal.connect(self.ack_received)
        self.parser.error_signal.connect(self.error_received)
        self.parser.info_signal.connect(self.log_signal)

    def read_message(self):
        """Reads all available lines from the serial port and parses them."""
        while self.mcu and self.mcu.canReadLine():
            try:
                message = self.mcu.readLine(maxlen=1000)
                print(f"{message}")
                # Convert QByteArray to Python string
                self.parser.parse(message)
            except Exception as e:
                self.log_signal.emit(f"Serial read error: {e}")

    def write_message(self, cmd=None):
        """Writes a command string to the serial port."""
        if self.connected and self.mcu:
            print('Writing message:' + cmd)
            self.mcu.write(cmd.encode())
        else:
            self.log_signal.emit("Cannot send command: MCU not connected.")

    # --- Public Slots for GUI Interaction ---

    def start_stop_controllers(self, start=True):
        """Public slot to start or stop all controllers."""
        if self.connected:
            if start and not self.running:
                self.log_signal.emit('Start command issued')
                command_string = self.commands.flow_start_stop(targets=15, start=True)
                self.write_message(command_string)
                # You might also want to start temp/DO controllers here
                self.running = True
                self.running_signal.emit(True)
            elif not start and self.running:
                self.log_signal.emit('Stop command issued')
                command_string = self.commands.flow_start_stop(targets=15, start=False)
                self.write_message(command_string)
                self.running = False
                self.running_signal.emit(False)

    def connect_mcu(self):
        """Public slot to initiate a connection to the MCU."""
        if not self.connected:
            # ... (rest of the connection logic remains the same)
            serial_port = QSerialPortInfo()
            available_ports = serial_port.availablePorts()
            for port in available_ports:
                if "USB Serial Device" in port.description():
                    try:
                        self.mcu = QSerialPort(port.portName(), baudRate=QSerialPort.Baud115200)
                        if self.mcu.open(QIODevice.ReadWrite):
                            self.connected = True
                            self.log_signal.emit(f"Connection to MCU successful on {port.portName()}")
                            self.mcu.readyRead.connect(self.read_message)
                            self.connected_signal.emit(True)
                            return
                        else:
                            self.log_signal.emit(f"Failed to open port {port.portName()}")

                    except Exception as e:
                        self.log_signal.emit(f"Failed to connect to MCU on {port.portName()}: {e}")

            self.log_signal.emit("No MCU connected")
            self.connected_signal.emit(False)

    def disconnect_mcu(self):
        """Public slot to close the connection to the MCU."""
        if self.mcu:
            self.mcu.close()
            self.mcu = None
            self.connected = False
            self.connected_signal.emit(False)
            self.log_signal.emit("Disconnected from MCU")

    def send_flow_rate(self, targets, flowrates):
        """Public slot to set flow rates."""
        try:
            command = self.commands.flow_set_flowrate(targets, flowrates)
            self.write_message(command)
        except ValueError as e:
            self.log_signal.emit(f"Invalid flow rate command: {e}")

    def send_generic_command(self, command_string):
        """
        Public slot to send a pre-formatted command string.
        Useful for simple commands or forwarding from other classes.
        """
        self.write_message(command_string)