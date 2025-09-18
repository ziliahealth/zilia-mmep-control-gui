from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QDateTime, QIODevice,QTimer
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo
import time
class ArduinoThread(QThread):
    #QThread object to handle communication with the Arduino Nano
    #Messages are sent and received between ArduinoThread and Arduino in the
    # form ![command] [arguments]\r\n
    #The ArduinoThread object listens for incoming messages and dispatches
    #them to the appropriate callback function
    #The ArduinoThread object also sends messages to the Arduino
    #The ArduinoThread object is also responsible for establishing and
    #terminating the connection with the Arduino

    sensor_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)
    running_signal = pyqtSignal(bool)
    connected_signal = pyqtSignal(bool)
    update_all_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()

        self.connected = False
        self.running = False
        self.Arduino = None  # Initialize the arduino variable

        # Define the callback functions
        self.callbacks = {'!kAcknowledge': self.onAcknowledge,
                            '!kSensors': self.onSensors,
                          '!kError': self.onError}

        # self._send_methods = {
        #     's': self._format_string,
        #     'f': self._format_float,
        #     'b': self._format_bool,
        #     'd': self._format_int
        # }

    # def read_message(self):
    #     if self.Arduino.canReadLine():
    #         try:
    #             msg = self.Arduino.readLine(maxlen=1000)
    #             msg_decoded = msg.decode().split(',')
    #             print('Reading message:'+ msg_decoded[0]+','+msg_decoded[1])
    #             k = msg_decoded[0]
    #             arg = msg_decoded[1]
    #             # Call the corresponding callback function
    #             callback = self.callbacks.get(k)
    #             if callback is not None:
    #                 arg = arg.split(';')[0]
    #                 callback(arg=arg)
    #         except ValueError:
    #             pass
    def read_message(self):
        if self.Arduino.canReadLine():
            try:
                message = self.Arduino.readLine(maxlen=1000)
                message_decoded = message.decode()
                #print(message_decoded)
                self.handle_message(message_decoded)
            except ValueError:
                pass
    def handle_message(self, msg):
        message_parts = msg.split(',')
        cmd = message_parts[0]
        #Rest of parts are args
        args = message_parts[1]
        #print(args)
        # Call the corresponding callback function
        callback = self.callbacks.get(cmd)
        if callback is not None:
            callback(args)

    def write_message(self, cmd=None):
        print('Writing message:'+cmd)
        if self.connected:
            self.Arduino.write(cmd.encode())



    def start(self):
        print('arduino_start')
        if self.connected and (not self.running):
            self.log_signal.emit('start button clicked')
            self.Arduino.clear()
            self.command = 'start\n'
            self.Arduino.write(self.command.encode())
            self.running = True
            self.running_signal.emit(True)
        else:
            pass

    def stop(self):
        if self.connected and self.running:
            self.log_signal.emit('Stopping pumps')
            self.command = 'stop\n'
            self.Arduino.write(self.command.encode())
            self.running = False
            self.running_signal.emit(False)

    def connect(self):
        # Get a list of available COM ports
        serial_port = QSerialPortInfo()
        available_ports = serial_port.availablePorts()
        for port in available_ports:
            print(port.description())
            if "Leonardo" in port.description():
                try:
                    # Establish a connection with the Arduino Nano
                    self.connected = True
                    self.log_signal.emit(f"Connection to Arduino Nano successful on {port.portName()}")
                    print(port.portName)
                    self.Arduino = QSerialPort(port.portName(), baudRate='BAUD115200')
                    self.Arduino.open(QIODevice.ReadWrite)
                    self.Arduino.clear()
                    self.Arduino.flush()
                    time.sleep(2)
                    self.Arduino.readyRead.connect(self.read_message, Qt.QueuedConnection)
                    #self.write_message('!kAcknowledge Arduinoready\r' )
                    self.connected_signal.emit(True)
                    #self.update_all_signal.emit(0)
                    #self.update_all_signal.emit(1)
                    #self.update_all_signal.emit(2)
                    #self.update_all_signal.emit(3)


                except QSerialPort.OpenError:
                    self.log_signal.emit(f"Failed to connect to Arduino Nano on{port.portName()}")
                    self.connected_signal.emit(False)
        if self.Arduino == None:
            self.log_signal.emit(f"No Arduino connected")
            self.connected_signal.emit(False)

    def close(self):
        if self.Arduino:
            print('disconnect button clicked')
            self.Arduino.clear()
            self.Arduino.close()
            self.Arduino = None
            self.connected = False
            self.connected_signal.emit(False)

    def start_logging(self):
        print('start logging')
        ## sends a message to the arduino to reset the data buffer and reset the time
        self.Arduino.clear()
        self.write_message('!kStartLogging\r')

    # Define the callback functions

    def onAcknowledge(self,arg):
        if arg == "Arduino Ready":
            self.connected_signal.emit(True)
            self.connected = True
            self.log_signal.emit(arg)
        else:
            self.log_signal.emit(arg)


    def onSensors(self,arg):
        #Cut off the \r\n
        arg = arg[:-2]
        #print(arg)
        self.sensor_signal.emit(arg)
        pass

    def onError(self,arg):
        msg = 'Error : '+arg
        self.log_signal.emit(msg)
        pass
    def on_syringe_pump_signal(self,msg):
        #Method to receive signals from syringepump object and dispatch specific callback functions
        #The method formats th
        # Split the received message into the command and arguments
#        msg_parts = msg.split(' ')
 #       cmd = msg_parts[0]
  #      args = msg_parts[1].split(',')

        # Determine the types of the arguments based on the command
       # cmd_arg_types = {
        #    'kSetMode': ['d', 's'],
         #   'kSetPID': ['d', 'f', 'f', 'f'],
          ##  'kSetFlowSensor': ['d', 'b'],
            #'kSetFlowRate': ['d', 'f'],
           # 'kSetSpeed': ['d', 'f'],
           # 'kSetDiameter': ['d', 'f']
            #}
        #arg_types = cmd_arg_types.get(cmd, ['s' for _ in args])

         # Call the write_message method with the command, arguments, and argument types
        self.write_message(msg)

