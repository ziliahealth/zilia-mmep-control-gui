from PyQt5.QtCore import QThread, pyqtSignal
import datetime
## Qtbread object for saving data to file
class DataSaver(QThread):
    #QThread object to save data to a file
    # The thread receeives data from the GUIUpdater object and saves it to a file
    # The filename can be set by the user
    def __init__(self):
        super().__init__()
        self.data = []
        self.filename = None
        self.saving = False

    def save_data(self, data):
        #Save the data to a file
        print('Saving data')
        if self.saving:
            with open(self.filename, 'a') as self.file:
                self.file.write(data+'\n')

    def set_filename(self, filename):
        self.filename = filename

    def start_save(self):
        self.saving = True
        self.set_header()

    def stop_save(self):
        self.saving=False
        self.file.close()

    def set_header(self):
        with open(self.filename, 'a') as self.file:
            #write current date and time
            self.file.write('Date: '+str(datetime.datetime.now())+'\n')
            #Include other metadata here as necessary
            #write the header
            self.file.write('Time,Flowrate1,Flowrate2,Flowrate3,Flowrate4,DO1,DO2\n')
