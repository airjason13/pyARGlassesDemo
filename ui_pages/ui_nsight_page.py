import json
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QGroupBox,
    QFileDialog,
    QLineEdit,
)


class NsightPage(QWidget):
    name = "Nsight"

    def __init__(self, _main_window, _central_qwidget, media_engine, **kwargs):
        super(NsightPage, self).__init__(**kwargs)
        self.main_window = _main_window
        self.central_widget = _central_qwidget
        self.media_engine = media_engine

        self.direction_options = [
            "straight",
            "turn_left",
            "turn_right",
            "turn_slight_left",
            "turn_slight_right",
            "roundabout_enter",
            "roundabout_exit",
            "uturn_left",
            "uturn_right",
            "arrived",
        ]

        self.road_options = [
            "忠孝東路",
            "中山路",
            "民生東路",
            "仁愛路",
            "信義路",
            "測試道路",
        ]

        self.arrived_road_options = [
            "台北 101",
            "台北車站",
            "市府轉運站",
            "測試終點",
        ]

        self.nav_timer = QTimer(self)
        self.nav_timer.timeout.connect(self._on_nav_timer_timeout)

        self.sim_distance_m = 0
        self.sim_running = False

        # NAV_MAP_IMAGE test state
        self.map_image_path = ""
        self.map_image_hex = ""

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        title = QLabel("Nsight Navigation Simulator")
        title.setStyleSheet("color: white; font-size: 22px; font-weight: bold;")
        main_layout.addWidget(title)

        # ---------- NAV state form ----------
        cmd_group = QGroupBox("NAV Command Editor")
        form_layout = QFormLayout()

        self.combo_direction = QComboBox()
        self.combo_direction.addItems(self.direction_options)
        form_layout.addRow("Direction", self.combo_direction)

        self.combo_road_name = QComboBox()
        self.combo_road_name.setEditable(True)
        self.combo_road_name.addItems(self.road_options)
        form_layout.addRow("Road Name", self.combo_road_name)

        self.combo_arrived_road_name = QComboBox()
        self.combo_arrived_road_name.setEditable(True)
        self.combo_arrived_road_name.addItems(self.arrived_road_options)
        form_layout.addRow("Arrived Location", self.combo_arrived_road_name)

        self.spin_distance_m = QSpinBox()
        self.spin_distance_m.setRange(0, 10000)
        self.spin_distance_m.setSingleStep(50)
        self.spin_distance_m.setSuffix(" m")
        self.spin_distance_m.setValue(500)
        form_layout.addRow("Distance", self.spin_distance_m)

        self.spin_interval_ms = QSpinBox()
        self.spin_interval_ms.setRange(100, 10000)
        self.spin_interval_ms.setSingleStep(100)
        self.spin_interval_ms.setSuffix(" ms")
        self.spin_interval_ms.setValue(1000)
        form_layout.addRow("Trigger Interval", self.spin_interval_ms)

        self.spin_step_m = QSpinBox()
        self.spin_step_m.setRange(1, 1000)
        self.spin_step_m.setSingleStep(10)
        self.spin_step_m.setSuffix(" m")
        self.spin_step_m.setValue(50)
        form_layout.addRow("Step Distance", self.spin_step_m)

        self.check_auto_arrived = QCheckBox("Auto send arrived when distance reaches 0")
        self.check_auto_arrived.setChecked(True)
        form_layout.addRow("", self.check_auto_arrived)

        cmd_group.setLayout(form_layout)
        main_layout.addWidget(cmd_group)

        # ---------- NAV MAP IMAGE form ----------
        map_group = QGroupBox("NAV_MAP_IMAGE Tester")
        map_layout = QFormLayout()

        self.label_map_file_name = QLabel("ex: live_map_001")
        self.label_map_file_name.setStyleSheet("""
            QLabel {
                background-color: #333;
                color: #aaa;
                border: 1px solid #555;
                padding: 3px;
            }
        """)
        self.label_map_file_name.setWordWrap(True)
        map_layout.addRow("Map File Name", self.label_map_file_name)


        self.label_map_path = QLabel("No image selected")
        self.label_map_path.setWordWrap(True)
        map_layout.addRow("Selected Image", self.label_map_path)

        self.label_map_hex_info = QLabel("HEX bytes: 0")
        map_layout.addRow("HEX Info", self.label_map_hex_info)

        map_btn_row = QHBoxLayout()

        self.btn_browse_map = QPushButton("上傳地圖")
        self.btn_browse_map.clicked.connect(self.on_browse_map_image)
        map_btn_row.addWidget(self.btn_browse_map)

        self.btn_send_map = QPushButton("發送地圖")
        self.btn_send_map.clicked.connect(self.on_send_nav_map_image)
        map_btn_row.addWidget(self.btn_send_map)

        self.btn_clear_map = QPushButton("清除地圖")
        self.btn_clear_map.clicked.connect(self.on_clear_nav_map_image)
        map_btn_row.addWidget(self.btn_clear_map)

        map_layout.addRow("", map_btn_row)

        map_group.setLayout(map_layout)
        main_layout.addWidget(map_group)

        # ---------- nav buttons ----------
        btn_row_2 = QHBoxLayout()

        self.btn_start_nav = QPushButton("啟動導航")
        self.btn_start_nav.clicked.connect(self.on_start_nav)
        btn_row_2.addWidget(self.btn_start_nav)

        self.btn_stop_nav = QPushButton("取消導航")
        self.btn_stop_nav.clicked.connect(self.on_stop_nav)
        btn_row_2.addWidget(self.btn_stop_nav)

        main_layout.addLayout(btn_row_2)

        # ---------- output ----------
        output_group = QGroupBox("Push Command Log")
        output_layout = QVBoxLayout()

        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)
        output_layout.addWidget(self.text_output)

        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)

        self.setLayout(main_layout)
        self.setStyleSheet("""
                    QWidget {
                        background-color: #121212;
                        color: white;
                        font-family: "Microsoft JhengHei", "微軟正黑體", sans-serif;
                    }
                    QGroupBox {
                        border: 1px solid #444;
                        margin-top: 12px;
                        font-weight: bold;
                        color: orange;
                    }
                    QGroupBox::title {
                        subcontrol-origin: margin;
                        left: 10px;
                        padding: 0 3px;
                    }
                    QLineEdit, QComboBox, QSpinBox {
                        background-color: #333;
                        color: white;
                        border: 1px solid #555;
                        padding: 3px;
                    }
                    QPushButton {
                        background-color: #444;
                        color: white;
                        border: 1px solid #666;
                        padding: 5px;
                        min-height: 25px;
                    }
                    QPushButton:hover {
                        background-color: #555;
                    }
                    QPushButton:pressed {
                        background-color: #222;
                    }
                    QTextEdit {
                        background-color: #000;
                        color: #00FF00;
                        border: 1px solid #444;
                    }
                    QLabel {
                        color: white;
                    }
                """)
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _current_road_name(self) -> str:
        text = self.combo_road_name.currentText().strip()
        return text if text else "測試道路"

    def _current_arrived_road_name(self) -> str:
        text = self.combo_arrived_road_name.currentText().strip()
        return text if text else "目的地"

    def _build_nav_state_payload(
        self,
        distance_m: int | None = None,
        direction: str | None = None,
        road_name: str | None = None,
    ):
        if distance_m is None:
            distance_m = self.spin_distance_m.value()
        if direction is None:
            direction = self.combo_direction.currentText().strip()
        if road_name is None:
            road_name = self._current_road_name()

        return {
            "direction": direction,
            "road_name": road_name,
            "distance_m": int(distance_m),
        }

    def _build_nav_state_command(
        self,
        distance_m: int | None = None,
        direction: str | None = None,
        road_name: str | None = None,
    ) -> str:

        payload = self._build_nav_state_payload(
            distance_m=distance_m,
            direction=direction,
            road_name=road_name,
        )
        return (
            "cmd:demo_set_nav_state;"
            f"data:{json.dumps(payload, ensure_ascii=False)};"
            "src:mobile;dst:demo"
        )

    def _build_nav_stop_command(self) -> str:
        return "cmd:demo_set_nav_stop;data:{};src:mobile;dst:demo"

    def _build_nav_map_image_payload(self) -> dict:
        file_name = self.map_file_name or self._default_map_file_name()

        return {
            "file_name": file_name,
            "hex": self.map_image_hex,
        }

    def _build_nav_map_image_command(self) -> str:
        payload = self._build_nav_map_image_payload()
        return (
            "cmd:demo_set_nav_map_image;"
            f"data:{json.dumps(payload, ensure_ascii=False)};"
            "src:mobile;dst:demo"
        )

    def _build_nav_map_image_clear_command(self) -> str:
        payload = {
            "file_name": "",
            "hex": "",
        }
        return (
            "cmd:demo_set_nav_map_image;"
            f"data:{json.dumps(payload, ensure_ascii=False)};"
            "src:mobile;dst:demo"
        )

    def _default_map_file_name(self) -> str:
        if self.map_image_path:
            return Path(self.map_image_path).stem
        return "nav_map_test"

    def _push_command(self, cmd: str):
        self.main_window.cmd_parser.parse_cmds(cmd)
        self._append_output(cmd)

    def _append_output(self, cmd: str):
        now = datetime.now().strftime("%H:%M:%S")
        self.text_output.append(f"[{now}] {cmd}")

    def _file_to_hex(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return f.read().hex()

    def _set_map_file_ui(self, file_path: str, hex_str: str):
        self.map_image_path = file_path
        self.map_image_hex = hex_str

        # Set file name state
        self.map_file_name = Path(file_path).stem if file_path else ""

        # UI
        self.label_map_file_name.setText(self.map_file_name or "ex: live_map_001")
        self.label_map_path.setText(file_path if file_path else "No image selected")
        self.label_map_hex_info.setText(f"HEX bytes: {len(hex_str) // 2}")
    # ------------------------------------------------------------------
    # NAV MAP IMAGE actions
    # ------------------------------------------------------------------
    def on_browse_map_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "選擇導航圖片",
            "",
            "Image Files (*.webp *.png *.jpg *.jpeg *.bmp);;All Files (*)"
        )
        if not file_path:
            return

        try:
            hex_str = self._file_to_hex(file_path)
            self._set_map_file_ui(file_path, hex_str)
            self._append_output(f"[LOAD_MAP_IMAGE] {file_path} -> hex length={len(hex_str)}")
        except Exception as e:
            self._append_output(f"[LOAD_MAP_IMAGE][ERROR] {e}")

    def on_send_nav_map_image(self):
        if not self.map_image_hex:
            self._append_output("[NAV_MAP_IMAGE] no image loaded")
            return

        cmd = self._build_nav_map_image_command()
        self._push_command(cmd)

    def on_clear_nav_map_image(self):
        # self.map_image_path = ""
        # self.map_image_hex = ""
        # self.label_map_path.setText("No image selected")
        # self.label_map_hex_info.setText("HEX bytes: 0")

        cmd = self._build_nav_map_image_clear_command()
        self._push_command(cmd)

    # ------------------------------------------------------------------
    # Simulation controls
    # ------------------------------------------------------------------
    def on_start_nav(self):
        self.sim_distance_m = self.spin_distance_m.value()
        self.sim_running = True

        interval_ms = self.spin_interval_ms.value()
        self.nav_timer.start(interval_ms)

        cmd = self._build_nav_state_command(distance_m=self.sim_distance_m)
        self._push_command(cmd)

    def on_stop_nav(self):
        self.sim_running = False
        self.nav_timer.stop()
        self.sim_distance_m = self.spin_distance_m.value()

        cmd = self._build_nav_stop_command()
        self._push_command(cmd)

    def _on_nav_timer_timeout(self):
        if not self.sim_running:
            return

        step_m = self.spin_step_m.value()
        self.sim_distance_m = max(0, self.sim_distance_m - step_m)

        if self.sim_distance_m == 0 and self.check_auto_arrived.isChecked():
            cmd = self._build_nav_state_command(
                distance_m=0,
                direction="arrived",
                road_name=self._current_arrived_road_name(),
            )
            self._push_command(cmd)
            self.sim_running = False
            self.nav_timer.stop()
            return

        cmd = self._build_nav_state_command(distance_m=self.sim_distance_m)
        self._push_command(cmd)