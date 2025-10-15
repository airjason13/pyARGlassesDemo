import sys
import os
import shlex
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QLabel, QSpinBox, QHBoxLayout, QMessageBox
)
from PyQt5.QtCore import QObject, pyqtSignal, QThread, Qt, QTimer

class GstSingleFileWorker(QObject):
    finished = pyqtSignal(bool, str)  # success, reason
    started = pyqtSignal()

    def __init__(self, cmd_args, auto_kill_after=None):
        """
        cmd_args: list of command + args (for subprocess.Popen)
        auto_kill_after: seconds (float) after which we kill the process (for JPG); None means wait until exit
        """
        super().__init__()
        self.cmd_args = cmd_args
        self.auto_kill_after = auto_kill_after
        self._proc = None
        self._killed_by_timer = False

    def run(self):
        """Run in a QThread"""
        try:
            self.started.emit()
            # Start subprocess (do not use shell=True)
            self._proc = subprocess.Popen(self.cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if self.auto_kill_after is not None:
                # Use a timer loop to wait and then kill (we cannot use Qt timers inside this worker thread reliably for cross-platform,
                # so use polling sleep loop; keep it responsive)
                import time
                deadline = self.auto_kill_after
                waited = 0.0
                poll_interval = 0.1
                while True:
                    ret = self._proc.poll()
                    if ret is not None:
                        # process exited earlier than deadline
                        out, err = self._proc.communicate()
                        # success if returncode==0 (but many gst-launch produce non-zero on close; we treat normal exit as success)
                        self.finished.emit(True, "process exited")
                        return
                    if waited >= deadline:
                        # time's up: terminate
                        try:
                            self._killed_by_timer = True
                            self._proc.terminate()
                            # wait short time, then kill if necessary
                            try:
                                self._proc.wait(timeout=1.0)
                            except subprocess.TimeoutExpired:
                                self._proc.kill()
                                self._proc.wait(timeout=1.0)
                        except Exception as e:
                            # ignore errors on termination
                            pass
                        self.finished.emit(True, "killed_by_timer")
                        return
                    time.sleep(poll_interval)
                    waited += poll_interval
            else:
                # Wait for process to finish
                out, err = self._proc.communicate()
                # if returncode == 0: success; else still treat as finished
                self.finished.emit(True, "process exited")
                return
        except Exception as e:
            self.finished.emit(False, f"exception: {e}")
            return

    def stop_if_running(self):
        """Attempt to stop the subprocess if it's running (called from main thread)."""
        try:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
        except Exception:
            pass
