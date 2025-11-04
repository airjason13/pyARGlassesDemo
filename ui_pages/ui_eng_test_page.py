from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout


class EngPage(QWidget):
    name = 'Eng'
    def __init__(self, _main_window, _central_qwidget, **kwargs):
        super(EngPage, self).__init__(**kwargs)
        self.main_window = _main_window
        self.central_widget = _central_qwidget
        self.label_title = None
        self.label_recv_cmd = None
        self.init_ui()

    def init_ui(self):
        self.label_title = QLabel(self)
        self.label_title.setStyleSheet("color: green;")
        self.label_title.setAlignment(Qt.AlignCenter)
        self.label_title.setText(self.name)

        self.label_recv_cmd = QLabel(self)
        self.label_recv_cmd.setStyleSheet("color: green;")
        self.label_recv_cmd.setAlignment(Qt.AlignCenter)
        self.label_recv_cmd.setText("cmd:")

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.label_title)
        self.setLayout(self.layout)

    def set_recv_cmd(self, cmd):
        self.label_recv_cmd.setText(cmd)
