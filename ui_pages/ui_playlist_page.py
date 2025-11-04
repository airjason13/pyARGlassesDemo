import json
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QTextEdit, QLineEdit, QHBoxLayout, QPushButton, QFrame

from cmd_parser import CmdParser
from global_def import *
from mediaengine.mediaengine import MediaEngine
from unix_client import UnixClient


class PlaylistPage(QWidget):
    name = 'Playlist'

    def __init__(self, _main_window, _central_qwidget, **kwargs):
        super(PlaylistPage, self).__init__(**kwargs)
        self.test_sock_cmd = False
        self.btn_get_item = None
        self.btn_prev = None
        self.btn_next = None
        self.text_output = None
        self.btn_remove_playlist = None
        self.btn_get_list = None
        self.btn_get_all = None
        self.btn_stop = None
        self.btn_play = None
        self.btn_remove = None
        self.input_name = None
        self.btn_add = None
        self.btn_select = None
        self.btn_create = None
        self.layout = None
        self.main_window = _main_window
        self.central_widget = _central_qwidget
        self.label_title = None
        self.media_engine = MediaEngine()
        self.init_ui()
        # === For Test ===
        if self.test_sock_cmd:
            dummy_client = UnixClient("/tmp/ipc_test.sock")
            self.cmd_parser = CmdParser(dummy_client, self.media_engine)

    def init_ui(self):
        layout = QVBoxLayout()

        # --- Title ---
        title = QLabel("🎵 Playlist Manager")
        title.setStyleSheet("color: lightgreen; font-size: 22px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # --- Input Area ---
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Playlist name or file name")
        self.input_name.setStyleSheet("font-size: 14px; padding: 6px;")
        layout.addWidget(self.input_name)

        # --- Helper function to create uniform rows ---
        def make_row(*buttons):
            row = QHBoxLayout()
            for b in buttons:
                if isinstance(b, QPushButton):
                    b.setMinimumHeight(50)
                    b.setStyleSheet("""
                        QPushButton {
                            font-size: 14px;
                            color: white;
                            background-color: #333;
                            border: 1px solid #666;
                            border-radius: 6px;
                            padding: 6px;
                            min-width: 150px;
                        }
                        QPushButton:hover { background-color: #555; }
                        QPushButton:pressed { background-color: #777; }
                    """)
                row.addWidget(b)
            return row

        def make_separator():
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            line.setStyleSheet("color: #444; margin: 10px 0;")
            return line

        # --- Section 1: Playlist Setup ---
        section1 = QLabel("📂 Playlist Setup")
        section1.setStyleSheet("color: orange; font-weight: bold; font-size: 16px;")
        layout.addWidget(section1)

        self.btn_create = QPushButton("➕ Create\n建立清單")
        self.btn_select = QPushButton("📁 Select\n選取清單")
        self.btn_add = QPushButton("📝 Add Item\n加入項目")
        self.btn_remove = QPushButton("❌ Remove Item\n移除項目")
        layout.addLayout(make_row(self.btn_create, self.btn_select, self.btn_add, self.btn_remove))
        layout.addWidget(make_separator())

        # --- Section 2: Playback Control ---
        section2 = QLabel("🎬 Playback Control")
        section2.setStyleSheet("color: lightblue; font-weight: bold; font-size: 16px;")
        layout.addWidget(section2)

        self.btn_play = QPushButton("▶️ Play\n播放清單")
        self.btn_stop = QPushButton("⏹ Stop\n停止播放")
        self.btn_prev = QPushButton("⏮ Prev\n上一部")
        self.btn_next = QPushButton("⏭ Next\n下一部")
        self.btn_play.setStyleSheet("font-size: 14px; font-weight: bold; color: lime;")
        self.btn_stop.setStyleSheet("font-size: 14px; font-weight: bold; color: red;")
        layout.addLayout(make_row(self.btn_play, self.btn_stop, self.btn_prev, self.btn_next))
        layout.addWidget(make_separator())

        # --- Section 3: Information & Tools ---
        section3 = QLabel("📋 Playlist Info & Tools")
        section3.setStyleSheet("color: lightpink; font-weight: bold; font-size: 16px;")
        layout.addWidget(section3)

        self.btn_get_all = QPushButton("📂 Get All\n全部清單")
        self.btn_get_list = QPushButton("📜 Get Current list\n當前清單")
        self.btn_get_item = QPushButton("🎬 Get Current item\n正在播放")
        self.btn_remove_playlist = QPushButton("🗑 Remove\n刪除清單")
        layout.addLayout(make_row(self.btn_get_all, self.btn_get_list, self.btn_get_item, self.btn_remove_playlist))

        # --- Output Area ---
        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        self.text_output.setStyleSheet("""
            QTextEdit {
                color: white;
                background-color: #111;
                border: 1px solid #444;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.text_output)

        # --- Signal connection ---
        self.btn_create.clicked.connect(self.on_create)
        self.btn_select.clicked.connect(self.on_select)
        self.btn_add.clicked.connect(self.on_add)
        self.btn_remove.clicked.connect(self.on_remove)
        self.btn_get_all.clicked.connect(self.on_get_all)
        self.btn_get_list.clicked.connect(self.on_get_list)
        self.btn_play.clicked.connect(self.on_play)
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_remove_playlist.clicked.connect(self.on_remove_playlist)
        self.btn_next.clicked.connect(self.on_next)
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_get_item.clicked.connect(self.on_get_item)

        # --- Final layout setup ---
        layout.addSpacing(10)
        self.setLayout(layout)

        # --- Page styling ---
        self.setStyleSheet("""
            QWidget {
                background-color: black;
                color: white;
            }
        """)

    def output_result(self, result: dict):
        text = json.dumps(result, indent=2, ensure_ascii=False)
        self.text_output.setPlainText(text)

    def on_create(self):
        name = self.input_name.text().strip()
        # if not name:
        #     self.output_result({"error": "Please enter playlist name"})
        #     return
        result = self.media_engine.playlist_create(name)
        self.output_result(result)

    def on_select(self):
        name = self.input_name.text().strip()
        # if not name:
        #     self.output_result({"error": "Please enter playlist name"})
        #     return
        result = self.media_engine.playlist_select(name)
        self.output_result(result)

    def on_add(self):
        name = self.input_name.text().strip()
        # if not name:
        #     self.output_result({"error": "Please enter filename to add"})
        #     return
        result = self.media_engine.playlist_add_item(name)
        self.output_result(result)

    def on_remove(self):
        name = self.input_name.text().strip()
        # if not name:
        #     self.output_result({"error": "Please enter filename to remove"})
        #     return
        result = self.media_engine.playlist_remove_item(name)
        self.output_result(result)

    def on_get_all(self):
        result = self.media_engine.playlist_get_all()
        self.output_result(result)

    def on_get_list(self):
        result = self.media_engine.playlist_get_current_list()
        self.output_result(result)

    def on_play(self):
         result = self.media_engine.playlist_play()
         self.output_result(result)

    def on_stop(self):
        result = self.media_engine.playlist_stop()
        self.output_result(result)

    def on_remove_playlist(self):
        name = self.input_name.text().strip()
        result = self.media_engine.playlist_remove_playlist(name)
        self.output_result(result)

    def on_next(self):
        result = self.media_engine.playlist_skip_next()
        self.output_result(result)

    def on_prev(self):
        result = self.media_engine.playlist_skip_prev()
        self.output_result(result)

    def on_get_item(self):
        result = self.media_engine.playlist_get_current_file()
        self.output_result(result)