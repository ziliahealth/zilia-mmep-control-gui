from PyQt5.QtCore import QThread, pyqtSignal
import time
import json

class SequenceRunner(QThread):
    sequence_step_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.sequence = []
        self.current_step = 0

    def load_sequence(self, sequence_file):
        with open(sequence_file, 'r') as f:
            self.sequence = json.load(f)

    def run(self):
        while self.current_step < len(self.sequence):
            step = self.sequence[self.current_step]
            for pump_mode, flow_rate, pump in zip(step['pump_modes'], step['flow_rates'], step['pumps']):
                pump_step = {"pump_mode": pump_mode, "flow_rate": flow_rate, "pump": pump}
                self.sequence_step_signal.emit(pump_step)
                time.sleep(step['run_time'])
            self.current_step += 1