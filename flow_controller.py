### High level commands class for the control of the syringe flow_controller
from PyQt5.QtCore import QThread, pyqtSignal, QObject
import serial
import time
import sys
import os
import numpy as np
class FlowControllerThread(QThread):
    mcu_signal = pyqtSignal(str)
    #QThread object to receive user inputs from the GUI and send formatted flow_controller commands to the mcu thread
    def __init__(self):
        super().__init__()
        self.num_flow_controllers = 4
        self.flow_controllers = []
        for i in range(self.num_flow_controllers):
            self.flow_controllers.append(flow_controller(i))
            self.flow_controllers[i].info()

    def set_flow(self, flow_controller_num, rate):
        #Set the flow rate of a flow_controller
        if rate:
            self.flow_controllers[flow_controller_num].set_rate(rate)
        self.mcu_signal.emit(f'!kSetFlowRate {flow_controller_num} {self.flow_controllers[flow_controller_num].rate}\r')
        #self.mcu_signal.emit(f'!kSetSpeed {flow_controller_num} {self.flow_controllers[flow_controller_num].speed}\r')

    def set_mode(self, flow_controller_num, mode=None):
        #Set the mode of a flow_controller
        if mode:
            self.flow_controllers[flow_controller_num].set_mode(mode)
        print(f'kSetMode {flow_controller_num} {self.flow_controllers[flow_controller_num].mode}')
        print(f'Sending mode: {self.flow_controllers[flow_controller_num].mode}')
        self.mcu_signal.emit(f'!kSetMode {flow_controller_num} {self.flow_controllers[flow_controller_num].mode}\r')
    def set_sensor(self, flow_controller_num, sensor):
        #Set the sensor of a flow_controller
        if sensor:
            self.flow_controllers[flow_controller_num].set_parameters(sensor=sensor)
        self.mcu_signal.emit(f'!kSetFlowSensor {flow_controller_num} {sensor}\r\n')

    def set_pid(self, flow_controller_num, Ki=None, Kp=None, Kd=None):
        #Set the PID parameters of a flow_controller
        if Ki:
            self.flow_controllers[flow_controller_num].set_pid(Ki=Ki)
        if Kp:
            self.flow_controllers[flow_controller_num].set_pid(Kp=Kp)
        if Kd:
            self.flow_controllers[flow_controller_num].set_pid(Kd=Kd)

        self.mcu_signal.emit(f'!kSetPID {flow_controller_num} {self.flow_controllers[flow_controller_num].Kp} {self.flow_controllers[flow_controller_num].Ki} {self.flow_controllers[flow_controller_num].Kd}\r')
    def set_diameter(self, flow_controller_num, diameter=None):
        #Set the diameter of a flow_controller
        if diameter:
            self.flow_controllers[flow_controller_num].set_parameters(diameter=diameter)
        self.mcu_signal.emit(f'!kSetDiameter {flow_controller_num} {self.flow_controllers[flow_controller_num].diameter}\r')

    def set_all(self,flow_controller_num):
        #method that sends signals to the mcu to send all the current parameters of a flow_controller
        #Used after the connection with the mcu is established
        self.mcu_signal.emit(f'!kSetMode {flow_controller_num} {self.flow_controllers[flow_controller_num].mode}\r')
        self.mcu_signal.emit(f'!kSetFlowRate {flow_controller_num} {self.flow_controllers[flow_controller_num].rate}\r')
        self.mcu_signal.emit(f'!kSetSpeed {flow_controller_num} {self.flow_controllers[flow_controller_num].speed}\r')
        self.mcu_signal.emit(f'!kSetFlowSensor {flow_controller_num} {self.flow_controllers[flow_controller_num].sensor}\r')
        self.mcu_signal.emit(f'!kSetDiameter {flow_controller_num} {self.flow_controllers[flow_controller_num].diameter}\r')
        self.mcu_signal.emit(f'!kSetPID {flow_controller_num} {self.flow_controllers[flow_controller_num].Ki} {self.flow_controllers[flow_controller_num].Kp} {self.flow_controllers[flow_controller_num].Kd}\r')



class pump_types:
    #Enum for pump types
    syringe = 0
    peristaltic = 1

class flow_controller:
    #Object to set and manage flow_controller properties
    def __init__(self, flow_controller_num):
        self.flow_controller_name = f'flow_controller{flow_controller_num}'
        self.flow_controller_num = flow_controller_num
        self.pump_type: int = pump_types.syringe
        self.mode = 'off'
        self.rate = 0
        self.active = False
        self.diameter = 12.4 #mm
        self.thread_pitch = 0.7 #mm
        self.tube_diameter = 0.7#mm
        self.peristaltic_calibration = 1 #calibration factor for peristaltic pumps
        self.sensor = 0
        self.fill_flowrate = 1 #ml/min
        self.Kp = 0
        self.Ki = 0
        self.Kd = 0

    def set_mode(self, mode):
        self.mode = mode
        if mode == 'Off':
            self.active = False
        if mode == 'Constant':
            self.active = True

        if mode == 'PID':
            self.active = True
        if mode == 'Fill':
            self.active = True

        if mode == 'Empty':
            self.active = True

    def set_rate(self, rate):
        self.rate = rate

    def set_pid(self, Ki=None, Kp=None, Kd=None):
        if Ki:
            self.Ki = Ki
        if Kp:
            self.Kp = Kp
        if Kd:
            self.Kd = Kd

    def info(self):
        #print flow_controller properties
        print('----------------------')
        print(f'flow_controller {self.flow_controller_num} info:')
        print(f'flow_controller name: {self.flow_controller_name}')
        print(f'flow_controller mode: {self.mode}')
        print(f'flow_controller rate: {self.rate}')
        print(f'flow_controller active: {self.active}')
        print(f'Syringe diameter: {self.diameter}')
        print(f'flow_controller thread pitch: {self.thread_pitch}')
        print(f'flow_controller sensor: {self.sensor}')
        print(f'flow_controller Kp: {self.Kp}')
        print(f'flow_controller Ki: {self.Ki}')
        print(f'flow_controller Kd: {self.Kd}')
        print(f'----------------------')

    def set_parameters(self,sensor=None, diameter=None, thread_pitch=None, steps_per_rev=None, microsteps=None, name = None):
        if diameter:
            self.diameter = diameter
        if thread_pitch:
            self.thread_pitch = thread_pitch
        if steps_per_rev:
            self.steps_per_rev = steps_per_rev
        if microsteps:
            self.microsteps = microsteps
        if name:
            self.name = name
        if sensor:
            self.sensor = sensor


