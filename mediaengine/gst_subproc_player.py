import os
import pathlib
import shlex
import signal
import subprocess
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject
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

        ''' gst paras'''
        self.pipeline = None
        self.loop = None
        self.running = False
        self.still_image_fps = 5


    def install_gst_single_file_play_proc_paused(self, slot_func):
        self.gst_single_file_play_proc_paused.connect(slot_func)

    def install_gst_single_file_play_proc_started(self, slot_func):
        self.gst_single_file_play_proc_started.connect(slot_func)

    def install_gst_single_file_play_proc_finished(self, slot_func):
        self.gst_single_file_play_proc_finished.connect(slot_func)

    def install_gst_single_file_play_proc_status(self, slot_func):
        self.gst_single_file_play_proc_status.connect(slot_func)

    def create_pipeline(self):
        log.debug("create_pipeline")
        str_pipeline = ""
        pipeline = None
        p = pathlib.Path(self.cmd_args)
        if p.suffix == ".mp4":
            if platform.machine() == 'x86_64':
                str_pipeline = \
                    f"filesrc location={shlex.quote(self.cmd_args)} ! decodebin ! videoconvert ! autovideosink"
            else:
                str_pipeline = \
                    f"filesrc location={shlex.quote(self.cmd_args)} ! decodebin ! videoconvert ! waylandsink"
        elif p.suffix in [".jpg", ".jpeg", ".png", ".webp"]:

            if platform.machine() == 'x86_64':
                cmd = [
                    "multifilesrc", f"location={shlex.quote(self.cmd_args)}",
                    "!", "decodebin",
                    "!", "imagefreeze",
                    "!", "videoconvert",
                    "!", "video/x-raw",
                    "!", "autovideosink"
                ]
                str_pipeline = " ".join(cmd)

            else:
                cmd = [
                    "multifilesrc", f"location={shlex.quote(self.cmd_args)}",
                    "!", "decodebin",
                    "!", "imagefreeze",
                    "!", "videoconvert",
                    "!", "video/x-raw",
                    "!", "autovideosink"
                ]
                str_pipeline = " ".join(cmd)

        log.debug(f"pipeline: {str_pipeline}")
        try:
            pipeline = Gst.parse_launch(str_pipeline)
        except Exception as e:
            log.error(f"Failed to parse pipeline: {e}")
        return pipeline

    def on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            print("End of stream reached.")
            self.stop_if_running()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"[ERROR] {err}, Debug: {debug}")
            self.stop_if_running()

    def on_timeout(self):
        log.debug("on_timeout")
        self.stop_if_running()


    def run(self):
        """Run in a QThread"""
        Gst.init(None)
        self.running = True


        self.pipeline = self.create_pipeline()
        if self.auto_kill_after is None:
            return
        self.loop = GLib.MainLoop()

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        self.pipeline.set_state(Gst.State.PLAYING)
        p = pathlib.Path(self.cmd_args)
        if p.suffix in [".jpg", ".jpeg", ".png", ".webp"]:
            GLib.timeout_add(self.auto_kill_after * 1000, self.on_timeout)
        self.gst_single_file_play_proc_started.emit()
        self.gst_single_file_play_proc_status.emit(PlayStatus.PLAYING)

        try:
            self.loop.run()
        except Exception as e:
            log.debug(f"Run loop failed: {e}")

    def stop_if_running(self):
        log.debug("stop_if_running")

        self.running = False
        if self.loop and self.loop.is_running():
            self.loop.quit()
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        self.gst_single_file_play_proc_finished.emit(True, "Stoped")
        self.gst_single_file_play_proc_status.emit(PlayStatus.FINISHED)

    def pause_if_running(self):
        self.running = False
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PAUSED)
            self.gst_single_file_play_proc_paused.emit()
            self.gst_single_file_play_proc_status.emit(PlayStatus.PAUSED)

    def resume_if_running(self):
        self.running = True
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)
            self.gst_single_file_play_proc_status.emit(PlayStatus.PLAYING)

