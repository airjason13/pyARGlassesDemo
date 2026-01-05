import json
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QTextEdit, QLineEdit, QHBoxLayout, QPushButton, QFrame

from cmd_parser import CmdParser
from global_def import *
from mediaengine.mediaengine import MediaEngine
from unix_client import UnixClient


class PlaylistPage(QWidget):
    name = 'Playlist'

    def __init__(self, _main_window, _central_qwidget, media_engine, **kwargs):
        super(PlaylistPage, self).__init__(**kwargs)

        self.btn_vol_up = None
        self.btn_vol_down = None
        self.label_volume = None
       
        self.input_index = None
        self.batch_inputs = None
        self.btn_expand_all_playlists = None
        self.btn_remove_batch_items_by_name = None
        self.btn_remove_batch_items_by_index = None
        self.btn_add_batch_items = None
        self.test_sock_cmd = False
        self.btn_get_current_playing_item = None
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
        self.media_engine = media_engine
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
        input_row = QHBoxLayout()

        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("[ Playlist name / File path ]")
        self.input_name.setStyleSheet("font-size: 14px; padding: 6px;")

        self.input_index = QLineEdit()
        self.input_index.setPlaceholderText("[ Index (play) ]")
        # self.input_index.setFixedWidth(70)
        self.input_index.setStyleSheet("font-size: 14px; padding: 6px;")

        input_row.addWidget(self.input_name)
        input_row.addWidget(self.input_index)

        layout.addLayout(input_row)
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
        self.btn_get_current_playing_item = QPushButton("🎬 Get Current item\n正在播放")
        self.btn_remove_playlist = QPushButton("🗑 Remove\n刪除清單")
        layout.addLayout(make_row(self.btn_get_all, self.btn_get_list,
                                  self.btn_get_current_playing_item, self.btn_remove_playlist))

        # --- Section 4: Volume Control ---
        section_vol = QLabel("🔊 Volume Control")
        section_vol.setStyleSheet("color: lightyellow; font-weight: bold; font-size: 16px;")
        layout.addWidget(section_vol)

        vol_row = QHBoxLayout()

        self.btn_vol_down = QPushButton("－")
        self.btn_vol_up = QPushButton("＋")

        self.btn_vol_down.setFixedWidth(60)
        self.btn_vol_up.setFixedWidth(60)

        for b in (self.btn_vol_down, self.btn_vol_up):
            b.setStyleSheet("""
                        QPushButton {
                            font-size: 20px;
                            padding: 8px;
                            background-color: #444;
                            color: white;
                            border-radius: 6px;
                        }
                        QPushButton:hover { background-color: #666; }
                    """)

        self.label_volume = QLabel(f"{int(self.media_engine.current_volume * 100)}%")
        self.label_volume.setStyleSheet("font-size: 16px; color: white; margin-left: 12px;")

        vol_row.addWidget(self.btn_vol_down)
        vol_row.addWidget(self.btn_vol_up)
        vol_row.addWidget(self.label_volume)

        layout.addLayout(vol_row)


        # ---

        # Connect
        self.btn_vol_down.clicked.connect(self.on_vol_down)
        self.btn_vol_up.clicked.connect(self.on_vol_up)

        # --- Section 5: Test Playlist Batch Commands ---
        section4 = QLabel("🧪 Playlist Batch Commands")
        section4.setStyleSheet("color: lightgreen; font-weight: bold; font-size: 16px;")
        layout.addWidget(section4)

        from PyQt5.QtWidgets import QGridLayout
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)

        # Label
        header_playlist = QLabel("🎵 Playlist Name")
        header_playlist.setStyleSheet("color: orange; font-weight: bold;")
        header_items = QLabel("🎬 Playlist Items")
        header_items.setStyleSheet("color: lightblue; font-weight: bold;")
        header_index = QLabel("🔢 Indexes")
        header_index.setStyleSheet("color: lightcyan; font-weight: bold;")

        grid_layout.addWidget(header_playlist, 0, 0)
        grid_layout.addWidget(header_items, 0, 1)
        grid_layout.addWidget(header_index, 0, 2)

        # Edit Line
        self.batch_inputs = []
        for i in range(3):
            playlist_edit = QLineEdit()
            items_edit = QLineEdit()
            index_edit = QLineEdit()

            playlist_edit.setPlaceholderText(f"Playlist {i + 1}")
            items_edit.setPlaceholderText("e.g /Media/song1.mp4, ....mp4")
            index_edit.setPlaceholderText("e.g 0, 2, 5")

            index_edit.setStyleSheet("background-color:#222; color:white; font-size:13px; padding:4px;")

            grid_layout.addWidget(playlist_edit, i + 1, 0)
            grid_layout.addWidget(items_edit, i + 1, 1)
            grid_layout.addWidget(index_edit, i + 1, 2)

            self.batch_inputs.append((playlist_edit, items_edit, index_edit))

        layout.addLayout(grid_layout)

        # Batch command buttons
        self.btn_add_batch_items = QPushButton("➕ Add Batch Items\n批次清單加入影片")
        self.btn_remove_batch_items_by_name = QPushButton("❌ Batch Remove Matching Items\n批次刪除（依名稱）")
        self.btn_remove_batch_items_by_index = QPushButton("❌ Batch Remove by Index\n批次刪除（依索引）")
        self.btn_expand_all_playlists = QPushButton("📂 Expand All Playlists\n展開全部清單")

        layout.addLayout(make_row(
            self.btn_add_batch_items,
            self.btn_remove_batch_items_by_name,
            self.btn_remove_batch_items_by_index,
            self.btn_expand_all_playlists
        ))

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
        self.btn_get_current_playing_item.clicked.connect(self.on_get_playing_item)
        self.btn_add_batch_items.clicked.connect(self.on_add_batch_items)
        self.btn_remove_batch_items_by_name.clicked.connect(self.on_remove_batch_items_by_name)
        self.btn_remove_batch_items_by_index.clicked.connect(self.on_remove_batch_items_by_index)
        self.btn_expand_all_playlists.clicked.connect(self.on_get_playlist_expand_all)


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
        playlist_name = self.input_name.text().strip()
        idx_str = self.input_index.text().strip()

        # convert index
        try:
            index = int(idx_str) if idx_str else 0
        except:
            index = 0

        payload = {
            "name": playlist_name or None,
            "index": index,
        }

        parser = CmdParser(UnixClient("/tmp/ipc_test.sock"), self.media_engine)

        test_data = {
            "src": "mobile",
            "dst": "demo",
            "data": json.dumps(payload, ensure_ascii=False),
        }

        parser.unix_data_ready_to_send.connect(
            lambda msg: self.text_output.setPlainText(msg)
        )
        parser.demo_set_playlist_play(test_data)

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

    def on_get_playing_item(self):
        result = self.media_engine.playlist_get_current_file()
        self.output_result(result)

    # --- Section 4: Test Batch-Playlist Commands ---
    def on_add_batch_items(self):
        playlists = []
        for name_edit, items_edit,index_edit in self.batch_inputs:
            name = name_edit.text().strip()
            items = [x.strip() for x in items_edit.text().split(",") if x.strip()]
            if name and items:
                playlists.append({"name": name, "files": items})

        if not playlists:
            self.output_result({"status": "NG", "error": "Please enter playlist names and items"})
            return

        parser = CmdParser(UnixClient("/tmp/ipc_test.sock"), self.media_engine)
        test_data = {
            "src": "mobile",
            "dst": "demo",
            "data": json.dumps({"playlists": playlists}, ensure_ascii=False)
        }
        parser.unix_data_ready_to_send.connect(
            lambda msg: self.text_output.setPlainText(msg)
        )
        parser.demo_set_playlist_batch_add(test_data)

    def on_remove_batch_items_by_name(self):
        playlists = []
        for name_edit, items_edit, index_edit in self.batch_inputs:
            name = name_edit.text().strip()
            items = [x.strip() for x in items_edit.text().split(",") if x.strip()]
            if name and items:
                playlists.append({"name": name, "files": items})

        if not playlists:
            self.output_result({"status": "NG", "error": "Please enter playlist names and items"})
            return

        parser = CmdParser(UnixClient("/tmp/ipc_test.sock"), self.media_engine)
        test_data = {
            "src": "mobile",
            "dst": "demo",
            "data": json.dumps({"playlists": playlists}, ensure_ascii=False)
        }
        parser.unix_data_ready_to_send.connect(
            lambda msg: self.text_output.setPlainText(msg)
        )
        parser.demo_set_playlist_batch_remove_by_name(test_data)

    def on_remove_batch_items_by_index(self):
        playlists = []

        for name_edit, items_edit, index_edit in self.batch_inputs:
            name = name_edit.text().strip()

            indexes = []
            if index_edit.text().strip():
                indexes = [int(x.strip()) for x in index_edit.text().split(",") if x.strip().isdigit()]

            if name and indexes:
                playlists.append({"name": name, "index": indexes})

        if not playlists:
            self.output_result({"status": "NG", "error": "Please enter playlist names and indexes"})
            return

        parser = CmdParser(UnixClient("/tmp/ipc_test.sock"), self.media_engine)
        test_data = {
            "src": "mobile",
            "dst": "demo",
            "data": json.dumps({"playlists": playlists}, ensure_ascii=False)
        }
        parser.unix_data_ready_to_send.connect(
            lambda msg: self.text_output.setPlainText(msg)
        )
        parser.demo_set_playlist_batch_remove_by_index(test_data)

    def on_get_playlist_expand_all(self):
        parser = CmdParser(UnixClient("/tmp/ipc_test.sock"), self.media_engine)
        test_data = {
            "src": "mobile",
            "dst": "demo",
            "data": "{}"
        }
        parser.unix_data_ready_to_send.connect(
            lambda msg: self.text_output.setPlainText(msg)
        )
        parser.demo_get_playlist_expand_all(test_data)

    def on_vol_down(self):

        new = max(0.0, self.media_engine.current_volume - 0.05)
        new = round(new, 2)

        self.media_engine.set_volume(new)
        self.label_volume.setText(f"{int(new * 100)}%")

        '''
        parser = CmdParser(UnixClient("/tmp/ipc_test.sock"), self.media_engine)

        test_data = {
            "src": "mobile",
            "dst": "demo",
            "data": "{}"
        }

        def parser_volume(msg: str):
            try:
                parts = dict(item.split(":", 1) for item in msg.split(";"))
                payload = json.loads(parts.get("data", "{}"))

                volume = payload.get("volume")
                max_volume = payload.get("max")

                self.label_volume.setText(f"{int(volume * 100)}%")
                self.text_output.setPlainText(
                    f"volume={volume}, max={max_volume}"
                )

                # Minus 0.5
                new = max(0.0, volume - 0.05)
                new = round(new, 2)
                self.media_engine.set_volume(new)
                self.label_volume.setText(f"{int(new * 100)}%")
            finally:
                parser.unix_data_ready_to_send.disconnect(parser_volume)

        parser.unix_data_ready_to_send.connect(parser_volume)
        parser.demo_get_media_volume(test_data)
        '''


    def on_vol_up(self):
        max_boost = self.media_engine.max_volume_boost
        new = min(max_boost, self.media_engine.current_volume + 0.05)
        new = round(new, 2)
        self.media_engine.set_volume(new)
        self.label_volume.setText(f"{int(new * 100)}%")
