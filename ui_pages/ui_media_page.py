import os
from pathlib import Path

from global_def import *
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QStackedLayout, QPushButton, QGridLayout, QFileDialog, \
    QMessageBox

from mediaengine.mediaengine import MediaEngine


class MediaPage(QWidget):
    name = 'Media'


    def __init__(self, _main_window, _central_qwidget, **kwargs):
        super(MediaPage, self).__init__(**kwargs)
        self.main_window = _main_window
        self.central_widget = _central_qwidget
        self.label_title = None
        self.media_engine = MediaEngine()

        if ENG_UI is True:
            self.init_eng_ui()
        else:
            self.init_ui()

    def init_eng_ui(self):
        self.label_title = QLabel(self)
        self.label_title.setStyleSheet("color: green;")
        self.label_title.setAlignment(Qt.AlignCenter)
        self.label_title.setText(self.name)
        self.layout = QVBoxLayout()

        self.layout.addWidget(self.label_title)

        # Media Control Widget
        self.media_control_widget = QWidget(self)  
        self.layout.addWidget(self.media_control_widget)
        # File uri label
        self.label_file_uri = QLabel(self)
        self.label_file_uri.setText("No file selected")
        self.label_file_uri.setStyleSheet("color: green;")

        # Browser Btn
        self.btn_browse = QPushButton(self)
        self.btn_browse.setText("Browse")
        self.btn_browse.setStyleSheet("color: green;")
        self.btn_browse.clicked.connect(self.browse_file)

        # Play & Pause Btn
        self.btn_play = QPushButton(self)
        self.btn_play.setText("Play")
        self.btn_play.setStyleSheet("color: green;")
        self.btn_play.clicked.connect(self.play_file)

        # Stop Btn
        self.btn_stop = QPushButton(self)
        self.btn_stop.setText("Stop")
        self.btn_stop.setStyleSheet("color: green;")
        self.btn_stop.clicked.connect(self.stop_play)

        # Status Label
        self.label_status = QLabel(self)
        self.label_status.setText("Play Status")
        self.label_status.setStyleSheet("color: green;")

        self.media_control_layout = QGridLayout()
        self.media_control_widget.setLayout(self.media_control_layout)
        self.media_control_layout.addWidget(self.label_file_uri, 0, 0, 1, 2)
        self.media_control_layout.addWidget(self.btn_browse, 0, 2, 1, 1)
        self.media_control_layout.addWidget(self.btn_play, 1, 0, 1, 3)
        self.media_control_layout.addWidget(self.btn_stop, 2, 0, 1, 3)
        self.media_control_layout.addWidget(self.label_status, 3, 0, 1, 3)

        self.setLayout(self.layout)

    def init_ui(self):
        self.label_title = QLabel(self)
        self.label_title.setStyleSheet("color: green;")
        self.label_title.setAlignment(Qt.AlignCenter)
        self.label_title.setText(self.name)
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.label_title)
        self.setLayout(self.layout)

    def browse_file(self):
        # Add playlist later???
        path, _ = QFileDialog.getOpenFileName(self, "選擇檔案", os.getcwd(),
                                              "Media Files (*.mp4 *.jpg *.jpeg *.png);;All files (*)")
        if path:
            self._current_file = path
            if ENG_UI is True:
                self.label_file_uri.setText(os.path.basename(path))


    def play_file(self):
        log.debug("play_file")
        # add check file ext
        if self._current_file is not None:
            try:
                p = Path(self._current_file)
                ext = p.suffix
                if ext == ".plt":
                    log.debug("play playlist is not implemented")
                    pass
                else:
                    self.media_engine.single_play(self._current_file, file_ext=ext)
            except Exception as e:
                log.error(e)
        else:
            QMessageBox.information(self, "No file", "請先選擇 MP4 檔案")

    def stop_play(self):
        log.debug("stop_file")
        self.media_engine.stop_play()

