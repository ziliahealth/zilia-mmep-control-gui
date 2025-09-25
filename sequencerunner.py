from PyQt5.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot
import toml


class SequenceRunner(QObject):
    """
    A QObject to run experimental sequences from a TOML file in an event-driven manner.
    This object is intended to be moved to a separate QThread to ensure the GUI remains responsive.
    """
    # --- Signals to command the controller threads ---
    set_flow_rate_signal = pyqtSignal(int, float)
    enable_pump_signal = pyqtSignal(int, bool)
    set_temperature_signal = pyqtSignal(int, float)
    enable_heater_signal = pyqtSignal(int, bool)
    dispense_volume_signal = pyqtSignal(int, float, float)
    start_logging_signal = pyqtSignal(str)
    stop_logging_signal = pyqtSignal()

    # --- Signals for GUI feedback ---
    log_signal = pyqtSignal(str)
    sequence_finished_signal = pyqtSignal()
    sequence_started_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.sequence = []
        self.current_step = -1
        self._is_stopped = True

        self.delay_timer = QTimer(self)
        self.delay_timer.setSingleShot(True)
        self.delay_timer.timeout.connect(self._process_next_step)

    def _load_sequence_from_file(self, sequence_file):
        """Loads sequence from a file. Returns True on success."""
        try:
            with open(sequence_file, 'r') as f:
                sequence_data = toml.load(f)
                self.sequence = sequence_data.get('event', [])
            self.log_signal.emit(f"Sequence loaded from {sequence_file}")
            return True
        except (toml.TomlDecodeError, FileNotFoundError) as e:
            self.log_signal.emit(f"Error loading sequence file: {e}")
            self.sequence = []
            return False

    @pyqtSlot(str)
    def load_and_start_sequence(self, sequence_file):
        """Public slot to be called from the main thread to load and start a sequence."""
        if self._load_sequence_from_file(sequence_file):
            if not self.sequence:
                self.log_signal.emit("Sequence file is valid but contains no events.")
                return

            self._is_stopped = False
            self.current_step = -1
            self.sequence_started_signal.emit()
            self._process_next_step()  # Start processing the first step

    @pyqtSlot()
    def stop_sequence(self):
        """Public slot to stop the sequence execution."""
        if not self._is_stopped:
            self._is_stopped = True
            if self.delay_timer.isActive():
                self.delay_timer.stop()
            self.log_signal.emit("Sequence stopped by user.")
            self.sequence_finished_signal.emit()  # Signal that it's done

    def is_running(self):
        """Returns True if the sequence is currently running."""
        return not self._is_stopped

    def _process_next_step(self):
        """Processes the next event in the sequence."""
        if self._is_stopped:
            return

        self.current_step += 1
        if self.current_step >= len(self.sequence):
            self.log_signal.emit("Sequence finished.")
            self._is_stopped = True
            self.sequence_finished_signal.emit()
            return

        event = self.sequence[self.current_step]
        self.log_signal.emit(f"Executing step {self.current_step + 1}: {event}")

        try:
            event_type = event.get('type')
            if event_type == 'delay':
                duration_ms = int(event['duration_s'] * 1000)
                self.delay_timer.start(duration_ms)
                return  # Stop processing here; timer will trigger the next step

            elif event_type == 'set_flow_rate':
                self.set_flow_rate_signal.emit(event['controller'], event['rate'])
            elif event_type == 'enable_pump':
                self.enable_pump_signal.emit(event['controller'], event['enabled'])
            elif event_type == 'set_temperature':
                self.set_temperature_signal.emit(event['controller'], event['temp'])
            elif event_type == 'enable_heater':
                self.enable_heater_signal.emit(event['controller'], event['enabled'])
            elif event_type == 'dispense_volume':
                self.dispense_volume_signal.emit(event['controller'], event['volume'], event['flowrate'])
            elif event_type == 'start_logging':
                self.start_logging_signal.emit(event['filepath'])
            elif event_type == 'stop_logging':
                self.stop_logging_signal.emit()
            else:
                self.log_signal.emit(f"Unknown event type: {event_type}")

        except KeyError as e:
            self.log_widget.append(f"Error in sequence step {event}: Missing parameter {e}")
            self.stop_sequence()
            return

        # For non-delay events, trigger the next step immediately via the event loop
        QTimer.singleShot(0, self._process_next_step)

