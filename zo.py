#For now this class only generates fake spectrums
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QDateTime, QIODevice, QTimer
import numpy as np
class ZOThread(QThread):
    data_signal = pyqtSignal(np.ndarray)
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()  # Call the __init__ method of the base class
        self.connected = False
        self.running = False
        #filepath for dummy spectrum
        filename = "C:/Users/marca/PycharmProjects/MMEP-Control-GUI/dummy_spectrum.csv"
        self.spectrum = np.loadtxt(filename,delimiter=';')
        self.spectrum_shape = self.spectrum.shape[0]
        self.timer=QTimer()
        self.timer.timeout.connect(self.update_spectrum)

    def update_spectrum(self):
            noise = np.random.normal(0, 500, self.spectrum_shape)
            self.noisy_spectrum = np.copy(self.spectrum)
            self.noisy_spectrum[:, 1] = self.noisy_spectrum[:, 1] + noise
            self.data_signal.emit(self.noisy_spectrum)

    def start(self):
            print('start')
            self.timer.start(100)

    def stop(self):
            self.timer.stop()
            print('stop')
    # Define a custom QObject to handle GUI updates in the main thread