from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QDateTime, QIODevice,QTimer
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo

class MCUThread(QThread):
    #QThread object to send and receive data from the serial port
    data_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    running_signal = pyqtSignal(bool)
    connected_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()

        self.connected = False
        self.running = False
        self.mcu = None  # Initialize the mcu variable

    def run(self):
        # Modify the COM port based on your setup
        if self.running & self.mcu.canReadLine():
            try:
                data = self.mcu.readLine(maxlen=1000)
                data_decoded = data.decode()
                self.data_signal.emit(data_decoded)

            except ValueError:
                pass

    def start(self):
        print('mcu_start')
        if self.connected and (not self.running):
            self.log_signal.emit('start button clicked')
            self.mcu.clear()
            self.command = 'start\n'
            self.mcu.write(self.command.encode())
            self.running = True
            self.running_signal.emit(True)
        else:
            pass

    def stop(self):
        if self.connected and self.running:
            self.log_signal.emit('Stopping pumps')
            self.command = 'stop\n'
            self.mcu.write(self.command.encode())
            self.running = False
            self.running_signal.emit(False)

    def connect(self):
        # Get a list of available COM ports
        serial_port = QSerialPortInfo()
        available_ports = serial_port.availablePorts()
        for port in available_ports:
            print(port.description())
            if "CH340" in port.description():
                try:
                    # Establish a connection with the mcu
                    self.connected = True
                    self.log_signal.emit(f"Connection to mcu successful on {port.portName()}")
                    print(port.portName)
                    self.mcu = QSerialPort(port.portName(), baudRate='BAUD9600')
                    self.mcu.open(QIODevice.ReadWrite)
                    self.mcu.readyRead.connect(self.run, Qt.QueuedConnection)
                    self.connected_signal.emit(True)

                except QSerialPort.OpenError:
                    self.log_signal.emit(f"Failed to connect to mcu on{port.portName()}")
                    self.connected_signal.emit(False)
        if self.mcu == None:
            self.log_signal.emit(f"No mcu connected")
            self.connected_signal.emit(False)

    def disconnect(self):
        if self.mcu:
            print('disconnect button clicked')
            self.mcu.clear()
            self.mcu.close()
            self.mcu = None
            self.connected = False
            self.connected_signal.emit(False)

    def update_flowrate(self):
        print('updating flow rate to')

    def update_PID(self):
        print('updating pid to')