import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject
import cairo
import os
import sys
import argparse
import shlex

from PyQt5.QtCore import QObject, pyqtSignal

from global_def import *
from mediaengine.media_engine_def import *

class GstSubtitleWorker(QObject):
    gst_subtitle_render_finished = pyqtSignal(bool, str)  # success, reason
    gst_subtitle_render_started = pyqtSignal()
    gst_subtitle_render_paused = pyqtSignal()
    gst_subtitle_render_status = pyqtSignal(int)

    # CC: Class variable
    color_r = 255
    color_g = 255
    color_b = 255

    def __init__(self, cmd_args, auto_kill_after=None):
        """
        cmd_args: list of command + args (for subprocess.Popen)
        auto_kill_after: seconds (float) after which we kill the process (for JPG); None means wait until exit
        """
        super().__init__()
        self.cmd_args = cmd_args
        self.auto_kill_after = auto_kill_after
        self._killed_by_timer = False

        self.pipeline = None
        self.overlay = None
        self.loop = None
        self.lines = []
        self.scroll_y = 0
        self.line_height = 50
        self.surface_height = 480
        self.running = False

    def install_gst_subtitle_render_paused(self, slot_func):
        self.gst_subtitle_render_paused.connect(slot_func)

    def install_gst_subtitle_render_started(self, slot_func):
        self.gst_subtitle_render_started.connect(slot_func)

    def install_gst_subtitle_render_finished(self, slot_func):
        self.gst_subtitle_render_finished.connect(slot_func)

    def install_gst_subtitle_render_status(self, slot_func):
        self.gst_subtitle_render_status.connect(slot_func)

    def load_text_file(self):
        try:
            with open(f'{self.cmd_args}', "r", encoding="utf-8") as f:
                self.lines = [line.strip() for line in f.readlines() if line.strip()]
        except Exception as e:
            print(f"Failed to load file: {e}")
            self.lines = ["Cannot read file"]

    def create_pipeline(self):
        pipeline = Gst.parse_launch(
            "videotestsrc pattern=black ! video/x-raw, width=640, height=480, framerate=30/1, format=BGRA ! "
            "cairooverlay name=overlay ! videoconvert ! autovideosink"
        )
        self.overlay = pipeline.get_by_name("overlay")
        self.overlay.connect("draw", self.draw_overlay, None)
        return pipeline

    def draw_overlay(self, overlay, context, timestamp, duration, user_data):
        context.select_font_face("Noto Sans TC", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(40)
        context.set_source_rgba(self.color_r / 255, self.color_g / 255, self.color_b / 255, 1.0)

        for i, line in enumerate(self.lines):
            y = self.scroll_y + i * self.line_height
            if -self.line_height < y < self.surface_height:
                context.move_to(50, y)
                context.show_text(line)

    def on_tick(self):
        if not self.running:
            return True

        self.scroll_y -= 1
        last_line_y = self.scroll_y + (len(self.lines) - 1) * self.line_height
        if last_line_y < -self.line_height:
            print("All text scrolled out. Stopping.")
            self.stop_if_running()
            return False

        return True

    def on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            print("End of stream reached.")
            self.stop_if_running()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"[ERROR] {err}, Debug: {debug}")
            self.stop_if_running()

    def run(self):
        """Run in a QThread"""
        Gst.init(None)
        self.load_text_file()
        self.scroll_y = self.surface_height
        self.running = True

        self.pipeline = self.create_pipeline()
        self.loop = GLib.MainLoop()

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        self.pipeline.set_state(Gst.State.PLAYING)
        GLib.timeout_add(33, self.on_tick)

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
            log.debug("cleanning pipeline")
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline.get_bus().remove_signal_watch()
            self.pipeline.get_bus().disable_sync_message_emission()
            self.pipeline = None
        self.gst_subtitle_render_finished.emit(True, "Stoped")

    def pause_if_running(self):
        self.running = False
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PAUSED)

    def resume_if_running(self):
        self.running = True
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)

    @classmethod
    def set_color(cls, r, g, b):
        cls.color_r = r
        cls.color_g = g
        cls.color_b = b