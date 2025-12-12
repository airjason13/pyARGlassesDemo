import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject
import platform
import cairo
import os
import sys
import argparse
import shlex
import random

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
    repeat_once = False
    repeat_endless = False
    color_lines = False

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
        if platform.machine() == 'x86_64':
            pipeline = Gst.parse_launch(
                "videotestsrc pattern=black ! video/x-raw, width=640, height=480, framerate=30/1, format=BGRA ! "
                "cairooverlay name=overlay ! videoconvert ! autovideosink"
            )
        else:
            pipeline = Gst.parse_launch(
                "videotestsrc pattern=black ! video/x-raw, width=640, height=480, framerate=30/1, format=BGRA ! "
                "cairooverlay name=overlay ! videoconvert ! waylandsink"
            )
        self.overlay = pipeline.get_by_name("overlay")
        self.overlay.connect("draw", self.draw_overlay, None)
        return pipeline

    def draw_overlay(self, overlay, context, timestamp, duration, user_data):
        context.select_font_face("Noto Sans TC", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(40)

        for i, line in enumerate(self.lines):
            y = self.scroll_y + i * self.line_height
            if -self.line_height < y < self.surface_height:
                if self.color_lines:
                    if (i % 10) == 0:   # Dark gray
                        context.set_source_rgba(0.663, 0.663, 0.663, 1)
                    elif (i % 10) == 1: # Brown
                        context.set_source_rgba(0.65, 0.16, 0.16, 1)
                    elif (i % 10) == 2: # Red
                        context.set_source_rgba(1, 0, 0, 1)
                    elif (i % 10) == 3: # Orange
                        context.set_source_rgba(1, 0.65, 0, 1)
                    elif (i % 10) == 4: # Yellow
                        context.set_source_rgba(1, 1, 0, 1)
                    elif (i % 10) == 5: # Green
                        context.set_source_rgba(0, 1, 0, 1)
                    elif (i % 10) == 6: # Blue
                        context.set_source_rgba(0, 0, 1, 1)
                    elif (i % 10) == 7: # Purple
                        context.set_source_rgba(0.5, 0, 0.5, 1)
                    elif (i % 10) == 8: # Gray
                        context.set_source_rgba(0.5, 0.5, 0.5, 1)
                    elif (i % 10) == 9: # White
                        context.set_source_rgba(1, 1, 1, 1)
                else:
                    context.set_source_rgba(self.color_r / 255, self.color_g / 255, self.color_b / 255, 1.0)
                context.move_to(50, y)
                context.show_text(line)

    def on_tick(self):
        if not self.running:
            return True

        self.scroll_y -= 1
        last_line_y = self.scroll_y + (len(self.lines) - 1) * self.line_height
        if last_line_y < -self.line_height:
            if self.repeat_once or self.repeat_endless:
                self.repeat_once = False
                self.scroll_y = self.surface_height
            else:
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
        Gst.init(None)
        self.load_text_file()
        self.scroll_y = self.surface_height
        self.running = True

        self.pipeline = self.create_pipeline()
        if not self.pipeline:
            self.gst_subtitle_render_finished.emit(False, "Pipeline error")
            return

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        self.pipeline.set_state(Gst.State.PLAYING)
        GLib.timeout_add(33, self.on_tick)
        self.gst_subtitle_render_status.emit(PlayStatus.PLAYING)

    def stop_if_running(self):
        log.debug("stop_if_running")

        self.running = False
        if self.pipeline:
            log.debug("cleanning Gst pipeline")

            self.pipeline.set_state(Gst.State.NULL)
            bus = self.pipeline.get_bus()
            if bus:
                try:
                    bus.remove_signal_watch()
                    if hasattr(bus, "_sync_enabled") and bus._sync_enabled:
                        bus.disable_sync_message_emission()
                except Exception as e:
                    log.debug(f"bus clean up faile: {e}")
            self.pipeline.unref()
            self.pipeline = None
        self.gst_subtitle_render_finished.emit(True, "Stoped")
        self.gst_subtitle_render_status.emit(PlayStatus.FINISHED)

    def pause_if_running(self):
        log.debug(f"pause is called")
        self.running = False
        if self.pipeline:
            log.debug(f"executing pause")
            self.pipeline.set_state(Gst.State.PAUSED)
            self.gst_subtitle_render_status.emit(PlayStatus.PAUSED)

    def resume_if_running(self):
        log.debug(f"resume is called")
        self.running = True
        if self.pipeline:
            log.debug(f"executing resume")
            self.pipeline.set_state(Gst.State.PLAYING)
            self.gst_subtitle_render_status.emit(PlayStatus.PLAYING)

    def is_running(self) -> bool:
        return self.pipeline is not None

    @classmethod
    def set_color(cls, r, g, b):
        cls.color_r = r
        cls.color_g = g
        cls.color_b = b

    @classmethod
    def set_repeat(cls, times:int):
        if 1 == times:
            cls.repeat_once = True
        elif -1 == times:
            cls.repeat_endless = True
        else:
            cls.repeat_once = False
            cls.repeat_endless = False

    @classmethod
    def set_color_lines(cls, en_dis:bool):
        cls.color_lines = en_dis
