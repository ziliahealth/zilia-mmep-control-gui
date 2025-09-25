from collections import deque
from PyQt5.QtCore import QObject, pyqtSignal, QTimer, QIODevice, QByteArray

from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo

class MCUCommands:
    # This class is unchanged
    def __init__(self):
        self.com_id_counter = 0
    def _generate_com_id(self):
        self.com_id_counter += 1
        return f"{self.com_id_counter:04d}"
    def _calculate_checksum(self, command_body):
        return 0
    def _format_command(self, base_command, args):
        com_id = self._generate_com_id()
        if args:
            command_part = f"{base_command}{','.join(map(str, args))}"
        else:
            command_part = base_command[:-1]
        command_body = f"{command_part},{com_id},1"
        checksum = self._calculate_checksum(command_body)
        return f"{command_body};\n", com_id

class MCUResponse(QObject):
    # This class is unchanged
    ok_signal = pyqtSignal(list)
    error_signal = pyqtSignal(list)
    flow_data_signal = pyqtSignal(list)
    temp_data_signal = pyqtSignal(list)
    do_data_signal = pyqtSignal(list)
    info_signal = pyqtSignal(str)
    OK, ERROR, FLOW, TEMP, DO = '$OK,', '$ERROR,', '$FLOW,', '$TEMP,', '$DO,'
    def __init__(self):
        super().__init__()
    def parse(self, message):
        try:
            message_str = message.decode('utf-8').strip(';\n')
            if not message_str: return
            if message_str.startswith(self.FLOW):
            # Handle flow data
                payload = message_str[len(self.FLOW):].split(',')
                payload[0] = int(payload[0])  # time in ms
                for i in range(1, len(payload)):
                    if i % 2 == 1: payload[i] = int(payload[i])
                    elif i % 2 == 0: payload[i] = float(payload[i])
                self.flow_data_signal.emit(payload)

            elif message_str.startswith(self.TEMP):
            # Handle temperature data
                payload = message_str[len(self.TEMP):].split(',')
                payload[0] = int(payload[0])  # time in ms
                for i in range(1, len(payload)):
                    if i % 3 == 1: payload[i] = int(payload[i])
                    elif i % 3 == 2: payload[i] = float(payload[i])
                    elif i % 3 == 0: payload[i] = int(payload[i])
                self.temp_data_signal.emit(payload)
            elif message_str.startswith(self.DO):
            # Handle DO data
                payload = message_str[len(self.DO):].split(',')
                self.do_data_signal.emit([int(payload[0]), float(payload[1]), float(payload[2])])

            elif message_str.startswith(self.OK): self.ok_signal.emit(message_str[len(self.OK):].split(','))
            elif message_str.startswith(self.ERROR): self.error_signal.emit(message_str[len(self.ERROR):].split(','))
            else: self.info_signal.emit(message_str)
        except Exception as e: self.info_signal.emit(f"Error parsing MCU message: '{message}'. Error: {e}")

class MCUWorker(QObject):
    # Signals are unchanged
    flow_data_received = pyqtSignal(list)
    temp_data_received = pyqtSignal(list)
    do_data_received = pyqtSignal(list)
    ack_received = pyqtSignal(list)
    error_received = pyqtSignal(list)
    log_signal = pyqtSignal(str)
    connected_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.mcu = None
        self.ack_timer = None
        self.connected = False
        self.commands = MCUCommands()
        self.parser = MCUResponse()
        self.command_queue = deque()
        self.waiting_for_com_id = None
        self.serial_buffer = QByteArray()
        self.ack_timeout = 500  # milliseconds

        # Connect the parser's signals
        self.parser.flow_data_signal.connect(self.flow_data_received)
        self.parser.temp_data_signal.connect(self.temp_data_received)
        self.parser.do_data_signal.connect(self.do_data_received)
        self.parser.error_signal.connect(self.error_received)
        self.parser.info_signal.connect(self.log_signal)
        self.parser.ok_signal.connect(self.ack_received)
        self.parser.ok_signal.connect(self._handle_mcu_ack)

    def _process_queue(self):
        if self.waiting_for_com_id is None and self.command_queue:
            command, com_id = self.command_queue.popleft()
            if self.connected and self.mcu:
                self.waiting_for_com_id = com_id
                self.mcu.write(command.encode())
                self.ack_timer.start(self.ack_timeout)
            else:
                self.log_signal.emit(f"Command {com_id} dropped: MCU not connected.")

    def _handle_mcu_ack(self, payload):
        if not payload: return
        ack_com_id = payload[0]
        if ack_com_id == self.waiting_for_com_id:
            self.ack_timer.stop()
            # --- FIX: Corrected the debug print statement ---
            self.waiting_for_com_id = None
            # Process the next command in the queue
            # Single shot timer is used so that process is called after the ack_timer has fully stopped
            QTimer.singleShot(0, self._process_queue)

    def _handle_ack_timeout(self):
        if self.waiting_for_com_id is not None:
            timed_out_id = self.waiting_for_com_id
            self.waiting_for_com_id = None
            self.log_signal.emit(f"Timeout: No ACK received for command {timed_out_id}. Moving on.")
            self._process_queue()

    def read_message(self):
        if not self.mcu: return
        incoming_data = self.mcu.readAll()
        self.serial_buffer.append(incoming_data)
        while True:
            end_of_message_pos = self.serial_buffer.indexOf(b';\n')
            if end_of_message_pos == -1: break
            message_length = end_of_message_pos + 2
            message = self.serial_buffer.left(message_length)
            self.serial_buffer = self.serial_buffer.mid(message_length)
            try: self.parser.parse(bytes(message))
            except Exception as e: self.log_signal.emit(f"Error during message parsing: {e}")

    def submit_command(self, command, com_id):
        self.command_queue.append((command, com_id))
        self._process_queue()

    def connect_mcu(self):
        if self.connected: return
        self.ack_timer = QTimer()
        self.ack_timer.setSingleShot(True)
        self.ack_timer.timeout.connect(self._handle_ack_timeout)
        serial_port_info = QSerialPortInfo.availablePorts()
        for port in serial_port_info:
            if "USB Serial Device" in port.description():
                self.mcu = QSerialPort()
                self.mcu.setPortName(port.portName())
                self.mcu.setBaudRate(QSerialPort.Baud115200)
                if self.mcu.open(QIODevice.ReadWrite):
                    self.connected = True
                    self.mcu.readyRead.connect(self.read_message)
                    self.log_signal.emit(f"Connection to MCU successful on {port.portName()}")
                    self.connected_signal.emit(True)
                    return
                else: self.log_signal.emit(f"Failed to open port {port.portName()}: {self.mcu.errorString()}")
        self.log_signal.emit("No MCU connected")
        self.connected_signal.emit(False)

    def disconnect_mcu(self):
        if self.mcu and self.mcu.isOpen(): self.mcu.close()
        if self.ack_timer: self.ack_timer.stop()
        self.connected = False
        self.serial_buffer.clear()
        self.command_queue.clear()
        self.waiting_for_com_id = None
        self.connected_signal.emit(False)
        self.log_signal.emit("Disconnected from MCU")