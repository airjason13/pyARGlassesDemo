"""Simple local Demura SET/GET test page."""
import json
import hashlib
from uuid import uuid4
from pathlib import Path
from color_adj.color_adj_config import (VIDEO_FRAME_H_SIZE_MAX, VIDEO_FRAME_W_SIZE_MAX,
                                        DEMURA_LUT_MAX_BYTES, DEMURA_LUT_CHUNK_BYTES)
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QSpinBox, QGridLayout, QScrollArea, QFileDialog
from arglassescmd.cmd_def import (DEMO_GET_DEMURA_ON_OFF, DEMO_SET_DEMURA_ON_OFF,
                                    DEMO_GET_VIDEO_FRAME_SIZE, DEMO_SET_VIDEO_FRAME_SIZE,
                                    DEMO_GET_DEMURA_EDGE, DEMO_SET_DEMURA_EDGE,
                                    DEMO_GET_DEMURA_ROI, DEMO_SET_DEMURA_ROI, DEMO_SET_DEMURA_LUT)


class ColorAdjPage(QWidget):
    name = 'Color Adj'

    def __init__(self, _main_window, _central_qwidget, media_engine, **kwargs):
        super().__init__(**kwargs)
        self.parser = _main_window.cmd_parser
        self.setStyleSheet('''
            QWidget { background-color: black; color: #90ee90; }
            QPushButton, QComboBox, QSpinBox { border: 1px solid #559955; padding: 8px; }
        ''')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        layout = QVBoxLayout(content)
        title = QLabel(self.name)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(QLabel('Demura ON / OFF'))
        row = QHBoxLayout()
        self.on_off = QComboBox()
        self.on_off.addItem('OFF', False)
        self.on_off.addItem('ON', True)
        self.set_button = QPushButton('SET')
        self.get_button = QPushButton('GET')
        self.set_button.clicked.connect(self.demo_set_demura_on_off)
        self.get_button.clicked.connect(self.demo_get_demura_on_off)
        for widget in (self.on_off, self.set_button, self.get_button):
            row.addWidget(widget)
        layout.addLayout(row)
        self.status = QLabel('Ready')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addWidget(QLabel('Video Frame Size'))
        frame_grid = QGridLayout()
        self.video_frame_size_inputs = {}
        for column, key in enumerate(('width', 'height')):
            spin = QSpinBox()
            spin.setRange(1, VIDEO_FRAME_W_SIZE_MAX if key == 'width'
                          else VIDEO_FRAME_H_SIZE_MAX)
            self.video_frame_size_inputs[key] = spin
            frame_grid.addWidget(QLabel(key.capitalize()), 0, column * 2)
            frame_grid.addWidget(spin, 0, column * 2 + 1)
        layout.addLayout(frame_grid)
        frame_buttons = QHBoxLayout()
        self.video_frame_size_set_button = QPushButton('SET Video Frame Size')
        self.video_frame_size_get_button = QPushButton('GET Video Frame Size')
        self.video_frame_size_set_button.clicked.connect(self.demo_set_video_frame_size)
        self.video_frame_size_get_button.clicked.connect(self.demo_get_video_frame_size)
        frame_buttons.addWidget(self.video_frame_size_set_button)
        frame_buttons.addWidget(self.video_frame_size_get_button)
        layout.addLayout(frame_buttons)
        self.video_frame_size_status = QLabel('SET stops playback and updates the next pipeline size.')
        self.video_frame_size_status.setWordWrap(True)
        layout.addWidget(self.video_frame_size_status)
        layout.addWidget(QLabel('Demura ROI'))
        offset_grid = QGridLayout()
        self.offset_inputs = {}
        for index, key in enumerate(('x_min', 'y_min', 'x_max', 'y_max')):
            spin = QSpinBox()
            spin.setRange(0, VIDEO_FRAME_W_SIZE_MAX if key.startswith('x')
                          else VIDEO_FRAME_H_SIZE_MAX)
            self.offset_inputs[key] = spin
            offset_grid.addWidget(QLabel(key), index // 2, (index % 2) * 2)
            offset_grid.addWidget(spin, index // 2, (index % 2) * 2 + 1)
        layout.addLayout(offset_grid)
        offset_buttons = QHBoxLayout()
        self.offset_set_button = QPushButton('SET ROI')
        self.offset_get_button = QPushButton('GET ROI')
        self.offset_set_button.clicked.connect(self.demo_set_demura_roi)
        self.offset_get_button.clicked.connect(self.demo_get_demura_roi)
        offset_buttons.addWidget(self.offset_set_button)
        offset_buttons.addWidget(self.offset_get_button)
        layout.addLayout(offset_buttons)
        self.offset_status = QLabel('Top-left: x_min/y_min; bottom-right: x_max/y_max (exclusive).')
        self.offset_status.setWordWrap(True)
        layout.addWidget(self.offset_status)
        layout.addWidget(QLabel('Demura Edge (pixels)'))
        grid = QGridLayout()
        self.edge_inputs = {}
        for index, side in enumerate(('top', 'bottom', 'left', 'right')):
            spin = QSpinBox()
            spin.setRange(0, VIDEO_FRAME_H_SIZE_MAX if side in ('top', 'bottom')
                          else VIDEO_FRAME_W_SIZE_MAX)
            self.edge_inputs[side] = spin
            grid.addWidget(QLabel(side.capitalize()), index // 2, (index % 2) * 2)
            grid.addWidget(spin, index // 2, (index % 2) * 2 + 1)
        layout.addLayout(grid)
        edge_buttons = QHBoxLayout()
        self.edge_set_button = QPushButton('SET Edge')
        self.edge_get_button = QPushButton('GET Edge')
        self.edge_set_button.clicked.connect(self.demo_set_demura_edge)
        self.edge_get_button.clicked.connect(self.demo_get_demura_edge)
        edge_buttons.addWidget(self.edge_set_button)
        edge_buttons.addWidget(self.edge_get_button)
        layout.addLayout(edge_buttons)
        self.edge_status = QLabel('SET stops playback and reloads gain. Press Play to use the new settings.')
        self.edge_status.setWordWrap(True)
        layout.addWidget(self.edge_status)
        # hint = QLabel('Extension is limited by the frame boundary. Full-frame ROI cannot extend further.')
        # hint.setWordWrap(True)
        # layout.addWidget(hint)
        layout.addWidget(QLabel('Demura LUT (.npy)'))
        self.lut_file = None
        self.lut_path_label = QLabel('Select a .npy file (max 16 MB)')
        self.lut_path_label.setWordWrap(True)
        layout.addWidget(self.lut_path_label)
        lut_buttons = QHBoxLayout()
        self.lut_load_button = QPushButton('Load .npy')
        self.lut_set_button = QPushButton('SET LUT')
        self.lut_set_button.setEnabled(False)
        self.lut_load_button.clicked.connect(self._browse_lut)
        self.lut_set_button.clicked.connect(self.demo_set_demura_lut)
        lut_buttons.addWidget(self.lut_load_button)
        lut_buttons.addWidget(self.lut_set_button)
        layout.addLayout(lut_buttons)
        self.lut_status = QLabel('SET stops playback and loads the new LUT. Press Play afterwards.')
        self.lut_status.setWordWrap(True)
        layout.addWidget(self.lut_status)
        layout.addStretch()

    def showEvent(self, event):
        super().showEvent(event)
        self.demo_get_demura_on_off()
        self.demo_get_video_frame_size()
        self.demo_get_demura_edge()
        self.demo_get_demura_roi()

    def demo_set_demura_on_off(self):
        result = self._local_send_command(DEMO_SET_DEMURA_ON_OFF, json.dumps(self.on_off.currentData()))
        self._update_on_off(result, 'SET')

    def demo_get_demura_on_off(self):
        self.on_off.setCurrentIndex(-1)
        self.set_button.setEnabled(False)
        result = self._local_send_command(DEMO_GET_DEMURA_ON_OFF, 'no_data')
        self._update_on_off(result, 'GET')

    def _update_on_off(self, result, operation):
        if result['status'] != 'OK':
            self.status.setText(f"{operation} failed: {result.get('error', 'Unknown error')}")
            return
        self.set_button.setEnabled(True)
        enabled = result['enabled']
        self.on_off.setCurrentIndex(1 if enabled else 0)
        self.status.setText(f"{operation} OK — {'ON' if enabled else 'OFF'}")

    def demo_set_video_frame_size(self):
        video_frame_size = {key: spin.value() for key, spin in self.video_frame_size_inputs.items()}
        result = self._local_send_command(DEMO_SET_VIDEO_FRAME_SIZE, json.dumps(video_frame_size))
        self._update_video_frame_size(result, 'SET')

    def demo_get_video_frame_size(self):
        self.video_frame_size_set_button.setEnabled(False)
        result = self._local_send_command(DEMO_GET_VIDEO_FRAME_SIZE, 'no_data')
        self._update_video_frame_size(result, 'GET')

    def _update_video_frame_size(self, result, operation):
        if result['status'] != 'OK':
            self.video_frame_size_status.setText(
                f"{operation} Video Frame Size failed: {result.get('error', 'Unknown error')}")
            return
        video_frame_size = result['video_frame_size']
        for key, value in video_frame_size.items():
            self.video_frame_size_inputs[key].setValue(value)
        width, height = video_frame_size['width'], video_frame_size['height']
        for key, spin in self.offset_inputs.items():
            spin.setMaximum(width if key.startswith('x') else height)
        for side, spin in self.edge_inputs.items():
            spin.setMaximum(height if side in ('top', 'bottom') else width)
        self.video_frame_size_set_button.setEnabled(True)
        self.video_frame_size_status.setText(
            f'{operation} Video Frame Size OK — {width} x {height}; ready for next playback.')

    def demo_set_demura_edge(self):
        result = self._local_send_command(DEMO_SET_DEMURA_EDGE,
                                  json.dumps({side: spin.value() for side, spin in self.edge_inputs.items()}))
        self._update_edge(result, 'SET')

    def demo_get_demura_edge(self):
        self.edge_set_button.setEnabled(False)
        for spin in self.edge_inputs.values():
            spin.setEnabled(False)
            spin.clear()
        result = self._local_send_command(DEMO_GET_DEMURA_EDGE, 'no_data')
        self._update_edge(result, 'GET')

    def _update_edge(self, result, operation):
        if result['status'] != 'OK':
            self.edge_status.setText(f"{operation} Edge failed: {result.get('error', 'Unknown error')}")
            return
        for side, value in result['edge'].items():
            self.edge_inputs[side].setValue(value)
            self.edge_inputs[side].setEnabled(True)
        self.edge_set_button.setEnabled(True)
        self.edge_status.setText('SET Edge OK — saved and loaded; ready for next playback.' if operation == 'SET'
                                 else 'GET Edge OK — saved values loaded.')

    def demo_set_demura_roi(self):
        result = self._local_send_command(DEMO_SET_DEMURA_ROI,
                                  json.dumps({key: spin.value() for key, spin in self.offset_inputs.items()}))
        self._update_roi(result, 'SET')

    def demo_get_demura_roi(self):
        self.offset_set_button.setEnabled(False)
        for spin in self.offset_inputs.values():
            spin.setEnabled(False)
            spin.clear()
        result = self._local_send_command(DEMO_GET_DEMURA_ROI, 'no_data')
        self._update_roi(result, 'GET')

    def _update_roi(self, result, operation):
        if result['status'] != 'OK':
            self.offset_status.setText(f"{operation} ROI failed: {result.get('error', 'Unknown error')}")
            return
        for key, value in result['roi'].items():
            self.offset_inputs[key].setValue(value)
            self.offset_inputs[key].setEnabled(True)
        self.offset_set_button.setEnabled(True)
        self.offset_status.setText('SET ROI OK — saved and loaded; ready for next playback.' if operation == 'SET'
                                   else 'GET ROI OK — saved values loaded.')

    def _browse_lut(self):
        filename, _ = QFileDialog.getOpenFileName(self, 'Load Demura LUT', '', 'NumPy LUT (*.npy)')
        if filename:
            self.lut_file = Path(filename)
            self.lut_path_label.setText(str(self.lut_file))
            self.lut_set_button.setEnabled(True)

    def demo_set_demura_lut(self):
        try:
            if self.lut_file is None:
                raise ValueError('Select a .npy file first')
            with self.lut_file.open('rb') as stream:
                raw = stream.read(DEMURA_LUT_MAX_BYTES + 1)
            if not 0 < len(raw) <= DEMURA_LUT_MAX_BYTES:
                raise ValueError('LUT must be between 1 byte and 16 MiB')
            upload_id = uuid4().hex
            payload = {'id': upload_id, 'size': len(raw),
                       'sha256': hashlib.sha256(raw).hexdigest()}
            self.lut_status.setText('Uploading and loading LUT...')
            for start in range(0, len(raw), DEMURA_LUT_CHUNK_BYTES):
                payload['hex'] = raw[start:start + DEMURA_LUT_CHUNK_BYTES].hex()
                result = self._local_send_command(DEMO_SET_DEMURA_LUT, json.dumps(payload))
                if result['status'] == 'RECEIVING':
                    self.lut_status.setText(f"Receiving LUT: {result['received']} / {result['size']} bytes")
                elif result['status'] == 'OK':
                    self.lut_status.setText(f"SET LUT OK — {result['size']} bytes verified, saved and loaded. Press Play.")
                    break
                else:
                    self.lut_status.setText(f"SET LUT failed: {result.get('error', 'Unknown error')}")
                    break
        except Exception as error:
            self.lut_status.setText(f'SET LUT failed: {error}')

    def _local_send_command(self, command, value):
        return self.parser.parse_cmds(
            f'idx:0;src:color_adj;dst:demo;cmd:{command};data:{value}\n',
            send_reply=False,
        )
