
import json

class SequenceBuilder:
    def __init__(self):
        self.sequence = []
        self.total_volume = {'pump1': 0, 'pump2': 0, 'pump3': 0, 'pump4': 0}

    def add_step(self, pump_modes, flow_rates, run_time, pumps):
        step = {"pump_modes": pump_modes, "flow_rates": flow_rates, "run_time": run_time, "pumps": pumps}
        self.sequence.append(step)
        # Update the total volume for each pump
        for pump, flow_rate in zip(pumps, flow_rates):
            self.total_volume[pump] += flow_rate * run_time

    def save_sequence(self, sequence_file):
        data = {
            'metadata': {
                'total_volume': self.total_volume
            },
            'sequence': self.sequence
        }
        with open(sequence_file, 'w') as f:
            json.dump(data, f)