import pathlib
import platform
import sys
import os
import shlex
import errno
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QLabel, QSpinBox, QHBoxLayout, QMessageBox
)
from PyQt5.QtCore import QObject, pyqtSignal, QThread, Qt, QTimer
from global_def import *
from mediaengine.gst_subproc_player import GstSingleFileWorker
from mediaengine.media_engine_def import *

class MediaEngine(QObject):
    qsignal_play_single_file_finished = pyqtSignal(str)  # success, reason
    qsignal_play_single_file_started = pyqtSignal()
    qsignal_play_single_file_paused = pyqtSignal()
    qsignal_media_play_status_changed = pyqtSignal(int)
    qsignal_mediaengine_error_report = pyqtSignal(str)

    def __init__(self):
        super(MediaEngine, self).__init__()
        # worker/thread holders
        self.play_single_file_thread = None
        self.play_single_file_worker = None
        self._current_file = 'None'
        self._current_playlist = 'None'
        # need to get default from config file
        self.media_engine_status = PlayStatus.IDLE
        log.warn("check still_image_play_period later")
        self.still_image_play_period = 30

    def install_media_engine_error_report(self, slot_func):
        self.qsignal_mediaengine_error_report.connect(slot_func)

    def install_media_play_status_changed(self, slot_func):
        self.qsignal_media_play_status_changed.connect(slot_func)

    def install_play_single_file_started(self, slot_func):
        self.qsignal_play_single_file_started.connect(slot_func)

    def install_play_single_file_finished(self, slot_func):
        self.qsignal_play_single_file_finished.connect(slot_func)

    def install_play_single_file_paused(self, slot_func):
        self.qsignal_play_single_file_paused.connect(slot_func)

    def _play_single_file_worker_with_cmd(self, cmd_args, auto_kill_after=None):
        if self.media_engine_status == PlayStatus.FINISHED or self.media_engine_status == PlayStatus.IDLE:
            self.play_single_file_worker = None
            self.play_single_file_thread = None
        # If previous running, ask to stop first
        if self.play_single_file_thread is not None and self.play_single_file_thread.isRunning():
            log.debug("Playing, Please Stop First")
            return

        # Create worker + thread
        self.play_single_file_worker = GstSingleFileWorker(cmd_args, auto_kill_after=auto_kill_after)
        self.play_single_file_thread = QThread()
        self.play_single_file_worker.moveToThread(self.play_single_file_thread)
        self.play_single_file_thread.started.connect(self.play_single_file_worker.run)
        self.play_single_file_worker.gst_single_file_play_proc_finished.connect(self._on_play_single_file_worker_finished)
        self.play_single_file_worker.gst_single_file_play_proc_started.connect(self._on_play_single_file_worker_started)
        self.play_single_file_worker.install_gst_single_file_play_proc_paused(self._on_play_single_file_worker_paused)
        self.play_single_file_worker.install_gst_single_file_play_proc_status(self._on_play_single_file_worker_status)
        # cleanup when thread finishes
        self.play_single_file_worker.gst_single_file_play_proc_finished.connect(lambda ok, reason: self.play_single_file_thread.quit())
        self.play_single_file_thread.finished.connect(self.play_single_file_thread.deleteLater)
        self.play_single_file_thread.start()

    def _on_play_single_file_worker_finished(self, result, reason):
        log.debug(f"_on_play_single_file_worker_finished res:{result}")
        self.qsignal_play_single_file_finished.emit(reason)

    def _on_play_single_file_worker_started(self):
        log.debug("_on_play_single_file_worker_started")
        self.qsignal_play_single_file_started.emit()

    def _on_play_single_file_worker_paused(self):
        log.debug("_on_play_single_file_worker_paused")
        self.qsignal_play_single_file_paused.emit()

    def _on_play_single_file_worker_status(self, status: int):
        log.debug(f"_on_play_single_file_worker_status res:{status}")
        self.media_engine_status = status
        self.qsignal_media_play_status_changed.emit(self.media_engine_status)

    def get_status_int(self) -> int:
        return self.media_engine_status

    def get_status_str(self) -> str:
        return PlayStatus_Dict.get(self.media_engine_status)

    def get_still_image_play_period_with_int(self) -> int:
        return self.still_image_play_period

    def get_still_image_play_period_str(self) -> str:
        return str(self.still_image_play_period)

    def get_current_file(self) -> str:
        p = pathlib.Path(self._current_file)
        if not p.is_file():
            return "None"
        return p.stem

    def get_current_playlist(self) -> str:
        p = pathlib.Path(self._current_playlist)
        if not p.is_file():
            return "None"
        return p.stem

    def set_still_image_play_period(self, still_image_play_period: int):
        self.still_image_play_period = still_image_play_period

    def set_current_file(self, sub_file_uri: str):
        self._current_file = MEDIAFILE_URI_PATH + sub_file_uri
        log.debug(f"self._current_file :{self._current_file}")

    def set_current_playlist(self, sub_playlist: str):
        self._current_playlist = PLAYLISTS_URI_PATH + sub_playlist
        log.debug(f"self._current_playlist :{self._current_playlist}")

    def single_play_from_cmd(self):
        p = pathlib.Path(self._current_file)
        if not p.is_file():
            log.debug(f"single_play_from_cmd error, no such file:{self._current_file}")
            self.qsignal_mediaengine_error_report.emit(os.strerror(errno.ENOENT).replace(" ", "_" ))
            return

        self.single_play(self._current_file, p.suffix)

    def single_play(self, file_uri: str, file_ext: str):
        log.debug("single_play, file_uri={}".format(file_uri))
        # check play thread alive or not
        log.debug("Need to check play thread alive or not")
        abs_path = os.path.abspath(file_uri)
        if file_ext == ".mp4":
            if platform.machine() == 'x86_64':
                pipeline = f"filesrc location={shlex.quote(abs_path)} ! decodebin ! videoconvert ! autovideosink"
            else:
                pipeline = f"filesrc location={shlex.quote(abs_path)} ! decodebin ! videoconvert ! waylandsink"
            gst_cmd = ["gst-launch-1.0", "-e"] + shlex.split(pipeline)
            self._play_single_file_worker_with_cmd(gst_cmd, auto_kill_after=None)
        elif file_ext in ['jpg', 'jpeg', 'png', 'webp']:
            if platform.machine() == 'x86_64':
                pipeline = f"filesrc location={shlex.quote(abs_path)} ! decodebin ! imagefreeze ! videoconvert ! autovideosink"
            else:
                pipeline = f"filesrc location={shlex.quote(abs_path)} ! decodebin ! imagefreeze ! videoconvert ! waylandsink"
            gst_cmd = ["gst-launch-1.0", "-e"] + shlex.split(pipeline)
            self._play_single_file_worker_with_cmd(gst_cmd, auto_kill_after=self.still_image_play_period)

    def stop_single_file_play(self):
        log.debug("stop_play")
        if self.play_single_file_worker:
            self.play_single_file_worker.stop_if_running()

    def pause_single_file_play(self):
        log.debug("pause_single_file_play")
        if self.play_single_file_worker and self.play_single_file_thread.isRunning():
            self.play_single_file_worker.pause_if_running()

    def resume_single_file_play(self):
        log.debug("resume_single_file_play")
        if self.play_single_file_worker and self.play_single_file_thread.isRunning():
            self.play_single_file_worker.resume_if_running()





