### High level commands class for the control of the syringe pump
from PyQt5.QtCore import QThread, pyqtSignal, QObject
import serial
import time
import sys
import os
import numpy as np
class SyringePumps(QThread):
    arduino_signal = pyqtSignal(str)
    #QThread object to receive user inputs from the GUI and send formatted pump commands to the arduino thread
    def __init__(self):
        super().__init__()
        self.num_pumps = 4
        self.pumps = []
        for i in range(self.num_pumps):
            self.pumps.append(pump(i))
            self.pumps[i].info()

    def set_flow(self, pump_num, rate):
        #Set the flow rate of a pump
        if rate:
            self.pumps[pump_num].set_rate(rate)
        self.arduino_signal.emit(f'!kSetFlowRate {pump_num} {self.pumps[pump_num].rate}\r')
        #self.arduino_signal.emit(f'!kSetSpeed {pump_num} {self.pumps[pump_num].speed}\r')

    def set_mode(self, pump_num, mode=None):
        #Set the mode of a pump
        if mode:
            self.pumps[pump_num].set_mode(mode)
        print(f'kSetMode {pump_num} {self.pumps[pump_num].mode}')
        print(f'Sending mode: {self.pumps[pump_num].mode}')
        self.arduino_signal.emit(f'!kSetMode {pump_num} {self.pumps[pump_num].mode}\r')
    def set_sensor(self, pump_num, sensor):
        #Set the sensor of a pump
        if sensor:
            self.pumps[pump_num].set_parameters(sensor=sensor)
        self.arduino_signal.emit(f'!kSetFlowSensor {pump_num} {sensor}\r\n')

    def set_pid(self, pump_num, Ki=None, Kp=None, Kd=None):
        #Set the PID parameters of a pump
        if Ki:
            self.pumps[pump_num].set_pid(Ki=Ki)
        if Kp:
            self.pumps[pump_num].set_pid(Kp=Kp)
        if Kd:
            self.pumps[pump_num].set_pid(Kd=Kd)

        self.arduino_signal.emit(f'!kSetPID {pump_num} {self.pumps[pump_num].Kp} {self.pumps[pump_num].Ki} {self.pumps[pump_num].Kd}\r')
    def set_diameter(self, pump_num, diameter=None):
        #Set the diameter of a pump
        if diameter:
            self.pumps[pump_num].set_parameters(diameter=diameter)
        self.arduino_signal.emit(f'!kSetDiameter {pump_num} {self.pumps[pump_num].diameter}\r')

    def set_all(self,pump_num):
        #method that sends signals to the arduino to send all the current parameters of a pump
        #Used after the connection with the arduino is established
        self.arduino_signal.emit(f'!kSetMode {pump_num} {self.pumps[pump_num].mode}\r')
        self.arduino_signal.emit(f'!kSetFlowRate {pump_num} {self.pumps[pump_num].rate}\r')
        self.arduino_signal.emit(f'!kSetSpeed {pump_num} {self.pumps[pump_num].speed}\r')
        self.arduino_signal.emit(f'!kSetFlowSensor {pump_num} {self.pumps[pump_num].sensor}\r')
        self.arduino_signal.emit(f'!kSetDiameter {pump_num} {self.pumps[pump_num].diameter}\r')
        self.arduino_signal.emit(f'!kSetPID {pump_num} {self.pumps[pump_num].Ki} {self.pumps[pump_num].Kp} {self.pumps[pump_num].Kd}\r')





class pump:
    #Object to set and manage pump properties
    def __init__(self, pump_num):
        self.pump_name = f'pump{pump_num}'
        self.pump_num = pump_num
        self.mode = 'off'
        self.rate = 0
        self.speed = 0
        self.volume = 0
        self.direction = 'push'
        self.active = False
        self.diameter = 12.4 #mm
        self.thread_pitch = 0.7 #mm
        self.steps_per_rev = 200
        self.microsteps = 8
        self.sensor = 0
        self.fill_speed = 200 #mm/min
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
        #Convert rate to speed considering thread and syringe diameter for constant mode
        self.speed = rate / (self.thread_pitch * (self.diameter / 2) ** 2 * np.pi) * self.microsteps *self.steps_per_rev

    def set_pid(self, Ki=None, Kp=None, Kd=None):
        if Ki:
            self.Ki = Ki
        if Kp:
            self.Kp = Kp
        if Kd:
            self.Kd = Kd

    def info(self):
        #print pump properties
        print('----------------------')
        print(f'Pump {self.pump_num} info:')
        print(f'Pump name: {self.pump_name}')
        print(f'Pump mode: {self.mode}')
        print(f'Pump rate: {self.rate}')
        print(f'Pump speed: {self.speed}')
        print(f'Pump volume: {self.volume}')
        print(f'Pump direction: {self.direction}')
        print(f'Pump active: {self.active}')
        print(f'Syringe diameter: {self.diameter}')
        print(f'Pump thread pitch: {self.thread_pitch}')
        print(f'Motor steps per rev: {self.steps_per_rev}')
        print(f'Microsteps: {self.microsteps}')
        print(f'Pump sensor: {self.sensor}')
        print(f'Pump fill speed: {self.fill_speed}')
        print(f'Pump Kp: {self.Kp}')
        print(f'Pump Ki: {self.Ki}')
        print(f'Pump Kd: {self.Kd}')
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


