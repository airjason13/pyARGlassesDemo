import sys
import os
import shlex
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QLabel, QSpinBox, QHBoxLayout, QMessageBox
)
from PyQt5.QtCore import QObject, pyqtSignal, QThread, Qt, QTimer
from global_def import *
from mediaengine.gst_subproc_player import GstSingleFileWorker


class MediaEngine(QObject):
    play_single_file_finished = pyqtSignal(bool, str)  # success, reason
    play_single_file_started = pyqtSignal()
    media_play_status_changed = pyqtSignal()

    def __init__(self):
        super(MediaEngine, self).__init__()
        # worker/thread holders
        self.play_single_file_thread = None
        self.play_single_file_worker = None
        self._current_file = None
        # need to get default from config file
        log.warn("check still_image_play_period later")
        self.still_image_play_period = 30

    def install_media_play_status_changed(self, slot_func):
        self.media_play_status_changed.connect(slot_func)

    def install_play_single_file_started(self, slot_func):
        self.play_single_file_finished.connect(slot_func)

    def install_play_single_file_finished(self, slot_func):
        self.play_single_file_finished.connect(slot_func)

    def _play_single_file_worker_with_cmd(self, cmd_args, auto_kill_after=None):
        # If previous running, ask to stop first
        if self.play_single_file_thread is not None and self.play_single_file_thread.isRunning():
            log.debug("Playing", "Please Stop First")
            return

        # Create worker + thread
        self.play_single_file_worker = GstSingleFileWorker(cmd_args, auto_kill_after=auto_kill_after)
        self.play_single_file_thread = QThread()
        self.play_single_file_worker.moveToThread(self.play_single_file_thread)
        self.play_single_file_thread.started.connect(self.play_single_file_worker.run)
        self.play_single_file_worker.finished.connect(self._on_play_single_file_worker_finished)
        self.play_single_file_worker.started.connect(self._on_play_single_file_worker_started)
        # cleanup when thread finishes
        self.play_single_file_worker.finished.connect(lambda ok, reason: self.play_single_file_thread.quit())
        self.play_single_file_thread.finished.connect(self.play_single_file_thread.deleteLater)
        self.play_single_file_thread.start()

    def _on_play_single_file_worker_finished(self, result):
        log.debug(f"_on_play_single_file_worker_finished res:{result}")

    def _on_play_single_file_worker_started(self):
        log.debug("_on_play_single_file_worker_started")

    def single_play(self, file_uri: str, file_ext: str):
        log.debug("single_play, file_uri={}".format(file_uri))
        # check play thread alive or not
        log.debug("Need to check play thread alive or not")
        abs_path = os.path.abspath(file_uri)
        if file_ext == ".mp4":
            pipeline = f"filesrc location={shlex.quote(abs_path)} ! decodebin ! videoconvert ! autovideosink"
            gst_cmd = ["gst-launch-1.0", "-e"] + shlex.split(pipeline)
            self._play_single_file_worker_with_cmd(gst_cmd, auto_kill_after=None)
        elif file_ext in ['jpg', 'jpeg', 'png', 'webp']:
            pipeline = f"filesrc location={shlex.quote(abs_path)} ! decodebin ! imagefreeze ! videoconvert ! autovideosink"
            gst_cmd = ["gst-launch-1.0", "-e"] + shlex.split(pipeline)
            self._play_single_file_worker_with_cmd(gst_cmd, auto_kill_after=self.still_image_play_period)


    def stop_play(self):
        log.debug("stop_play")
        if self.play_single_file_worker:
            self.play_single_file_worker.stop_if_running()

