import os
import signal
import subprocess

from PyQt5.QtCore import QObject, pyqtSignal

from global_def import *
from mediaengine.media_engine_def import *


class GstSingleFileWorker(QObject):
    gst_single_file_play_proc_finished = pyqtSignal(bool, str)  # success, reason
    gst_single_file_play_proc_started = pyqtSignal()
    gst_single_file_play_proc_paused = pyqtSignal()
    gst_single_file_play_proc_status = pyqtSignal(int)

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

    def install_gst_single_file_play_proc_paused(self, slot_func):
        self.gst_single_file_play_proc_paused.connect(slot_func)

    def install_gst_single_file_play_proc_started(self, slot_func):
        self.gst_single_file_play_proc_started.connect(slot_func)

    def install_gst_single_file_play_proc_finished(self, slot_func):
        self.gst_single_file_play_proc_finished.connect(slot_func)

    def install_gst_single_file_play_proc_status(self, slot_func):
        self.gst_single_file_play_proc_status.connect(slot_func)

    def run(self):
        """Run in a QThread"""
        try:
            self.gst_single_file_play_proc_started.emit()
            log.debug("Started gst_single_file_play_proc %d", PlayStatus.PLAYING)
            self.gst_single_file_play_proc_status.emit(PlayStatus.PLAYING)
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
                        self.gst_single_file_play_proc_finished.emit(True, "process exited")
                        self.gst_single_file_play_proc_status.emit(PlayStatus.FINISHED)
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
                        self.gst_single_file_play_proc_finished.emit(True, "killed_by_timer")
                        self.gst_single_file_play_proc_status.emit(PlayStatus.FINISHED)
                        return
                    time.sleep(poll_interval)
                    waited += poll_interval
            else:
                # Wait for process to finish
                out, err = self._proc.communicate()
                # if returncode == 0: success; else still treat as finished
                self.gst_single_file_play_proc_finished.emit(True, "process exited")
                self.gst_single_file_play_proc_status.emit(PlayStatus.FINISHED)
                return
        except Exception as e:
            self.gst_single_file_play_proc_finished.emit(False, f"exception: {e}")
            self.gst_single_file_play_proc_status.emit(PlayStatus.FINISHED)
            return

    def stop_if_running(self):
        log.debug("stop_if_running")
        """Attempt to stop the subprocess if it's running (called from main thread)."""
        try:
            if self._proc and self._proc.poll() is None:
                os.kill(self._proc.pid, signal.SIGCONT)
                self._proc.terminate()
        except Exception as e:
            log.debug(f"stop error:{e}")

    def pause_if_running(self):
        try:
            if self._proc and self._proc.poll() is None:
                os.kill(self._proc.pid, signal.SIGSTOP)
                self.gst_single_file_play_proc_paused.emit()
                self.gst_single_file_play_proc_status.emit(PlayStatus.PAUSED)
        except Exception as e:
            log.debug(f"pause error:{e}")

    def resume_if_running(self):
        try:
            if self._proc and self._proc.poll() is None:
                os.kill(self._proc.pid, signal.SIGCONT)
                self.gst_single_file_play_proc_started.emit()
                self.gst_single_file_play_proc_status.emit(PlayStatus.PLAYING)
        except Exception as e:
            log.debug(f"resume error:{e}")

