import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5 import QtCore
from main import SyringePumpApp
from unittest.mock import Mock

@pytest.fixture
def app(qtbot):
    test_app = SyringePumpApp()
    qtbot.addWidget(test_app)
    return test_app

def test_flowrate(app, qtbot):
    app.show()
    qtbot.waitForWindowShown(app)
    app.syringe_pumps.set_flow(0, 100)
    assert app.syringe_pumps.pumps[0].rate == 100
    app.syringe_pumps.set_flow(0, 200)
    assert app.syringe_pumps.pumps[0].rate == 200
