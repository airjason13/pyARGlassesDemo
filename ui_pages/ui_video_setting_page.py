from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout


class VideoSettingPage(QWidget):
    name = 'Video_Setting'
    def __init__(self, _main_window, _central_qwidget, **kwargs):
        super(VideoSettingPage, self).__init__(**kwargs)
        self.main_window = _main_window
        self.central_widget = _central_qwidget

        self.label_title = None
        self.init_ui()

    def init_ui(self):
        self.label_title = QLabel(self)
        self.label_title.setStyleSheet("color: green;")
        self.label_title.setAlignment(Qt.AlignCenter)
        self.label_title.setText(self.name)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.label_title)
        self.setLayout(self.layout)

