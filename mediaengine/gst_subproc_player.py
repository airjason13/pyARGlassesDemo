import os
import pathlib
import shlex
import signal
import subprocess
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib, GObject,GstPbutils
from PyQt5.QtCore import QObject, pyqtSignal

from global_def import *
from mediaengine.media_engine_def import *


class GstSingleFileWorker(QObject):
    gst_single_file_play_proc_finished = pyqtSignal(bool, str)
    gst_single_file_play_proc_started = pyqtSignal()
    gst_single_file_play_proc_paused = pyqtSignal()
    gst_single_file_play_proc_status = pyqtSignal(int)

    def __init__(self, cmd_args, auto_kill_after=None , parent_engine=None):
        super().__init__()
        self.cmd_args = cmd_args
        self.auto_kill_after = auto_kill_after
        self.pipeline = None
        self.running = False
        self.still_image_fps = 5
        self.volume_elem = None
        self.parent_engine = parent_engine

    def install_gst_single_file_play_proc_paused(self, slot_func):
        self.gst_single_file_play_proc_paused.connect(slot_func)

    def install_gst_single_file_play_proc_started(self, slot_func):
        self.gst_single_file_play_proc_started.connect(slot_func)

    def install_gst_single_file_play_proc_finished(self, slot_func):
        self.gst_single_file_play_proc_finished.connect(slot_func)

    def install_gst_single_file_play_proc_status(self, slot_func):
        self.gst_single_file_play_proc_status.connect(slot_func)

    def has_audio_stream(self, file_path):
        discoverer = GstPbutils.Discoverer.new(Gst.SECOND)
        try:
            uri = pathlib.Path(os.path.abspath(file_path)).as_uri()
            info = discoverer.discover_uri(uri)

            audio_streams = info.get_audio_streams()
            return len(audio_streams) > 0
        except Exception as e:
            log.error(f"Discoverer failed: {e}")
            return False

    def setup_audio_session(self):
        if platform.machine() == "x86_64":
            return
        os.environ["XDG_RUNTIME_DIR"] = "/run/user/0"
        try:
            result = subprocess.run(["pgrep", "-x", "pipewire-pulse"], capture_output=True)
            if result.returncode != 0:
                log.debug("Starting pipewire-pulse within ARGlassesDemo...")
                subprocess.Popen(["pipewire-pulse"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            log.error(f"Failed to manage pipewire-pulse: {e}")

    def create_pipeline(self):
        log.debug("create_pipeline")

        p = pathlib.Path(self.cmd_args)
        file_path = shlex.quote(self.cmd_args)
        has_audio = self.has_audio_stream(file_path)
        # ---------------------------
        # 1. MP4 → Video + Audio
        # ---------------------------
        if p.suffix.lower() == ".mp4":

            if platform.machine() == "x86_64":
                video_sink = "autovideosink"
                audio_sink = "autoaudiosink"
                video_convert = "videoconvert"
            else:
                video_sink = "waylandsink"
                # audio_sink = "alsasink device=hw:1,0"
                audio_sink = "pulsesink"
                video_convert = "imxvideoconvert_pxp"

            if has_audio:
                self.setup_audio_session()
                str_pipeline = (
                    f"filesrc location={shlex.quote(file_path)} ! decodebin name=d "
                    f"d. ! queue ! {video_convert} ! {video_sink} "
                    f"d. ! queue ! audioconvert ! audioresample ! "
                    f"volume name=vol ! {audio_sink} "
                )
            else:
                str_pipeline = (
                    f"filesrc location={shlex.quote(file_path)} ! "
                    f"decodebin ! videoconvert ! {video_sink}"
                )

        # ---------------------------
        # 2. Image（JPG / PNG / WEBP）
        # ---------------------------
        else:
            str_pipeline = (
                f"multifilesrc location={file_path} ! decodebin ! "
                "imagefreeze ! videoconvert ! video/x-raw ! autovideosink"
            )

        # Log pipeline for debugging
        log.debug(f"pipeline: {str_pipeline}")

        # ---------------------------
        # 3. Pipeline launch
        # ---------------------------
        try:
            pipeline = Gst.parse_launch(str_pipeline)
            return pipeline
        except Exception as e:
            log.error(f"Failed to parse pipeline: {e}")
            return None

    def start(self):
        """Called inside a QThread"""
        Gst.init(None)
        self.running = True

        # Create GStreamer pipeline
        self.pipeline = self.create_pipeline()
        if not self.pipeline:
            self.gst_single_file_play_proc_finished.emit(False, "Pipeline error")
            return
        # Optional: make videosink non-blocking (avoid sync issues)
        sink = self.pipeline.get_by_name("sink")
        if sink:
            sink.set_property("sync", False)

        #  Volume Element Initialization
        self.volume_elem = self.pipeline.get_by_name("vol")
        if self.volume_elem is None:
            log.warning("[GstWorker] volume element not found in pipeline")
        else:
            log.debug("[GstWorker] volume element initialized")
            try:
                self.volume_elem.set_property("volume", self.parent_engine.current_volume)
            except:
                pass

        # ✅ 用 bus signal，不用 GLib.MainLoop
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        self.pipeline.set_state(Gst.State.PLAYING)

        # ✅ still image → timeout（也會由 Qt event loop 觸發）
        p = pathlib.Path(self.cmd_args)
        if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
            GLib.timeout_add(self.auto_kill_after * 1000, self.on_timeout)

    def on_timeout(self):
        log.debug("Timeout reached, stopping")
        self.stop_if_running()
        return False  # don't repeat

    def on_message(self, bus, message):
        msg_type = message.type

        if msg_type == Gst.MessageType.EOS:
            log.debug("EOS")
            self.stop_if_running()

        elif msg_type == Gst.MessageType.ERROR:
            err, dbg = message.parse_error()
            log.debug(f"ERROR: {err}, dbg={dbg}")
            self.stop_if_running()

        elif msg_type == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old, new, pending = message.parse_state_changed()
                match new.value_nick:
                    case "playing":
                        self.gst_single_file_play_proc_started.emit()
                        self.gst_single_file_play_proc_status.emit(PlayStatus.PLAYING)
                    case "paused":
                        self.gst_single_file_play_proc_paused.emit()
                        self.gst_single_file_play_proc_status.emit(PlayStatus.PAUSED)
                    case _:
                        pass

    def stop_if_running(self):
        if not self.running:
            return
        self.running = False

        log.debug("Stopping pipeline")
        ''' For clean file handling '''
        if self.pipeline:
            bus = self.pipeline.get_bus()
            try:
                bus.remove_signal_watch()
            except Exception as e:
                log.error(f"Failed to remove gst bus signal: {e}")

            self.pipeline.set_state(Gst.State.NULL)

            # 很重要：釋放 pipeline 物件
            self.pipeline = None

        self.gst_single_file_play_proc_finished.emit(True, "Stopped")
        self.gst_single_file_play_proc_status.emit(PlayStatus.FINISHED)

    def pause_if_running(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PAUSED)

    def resume_if_running(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)



class GstSingleFileWorker_PRE(QObject):
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


    def start(self):
        self.run()

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
                '''str_pipeline = (
                    f"filesrc location=\"{shlex.quote(self.cmd_args)}\" ! "
                    "qtdemux name=d "
                    "d.video_0 ! queue ! h264parse ! avdec_h264 max-threads=2 ! queue ! videoconvert ! waylandsink sync=false name=sink "
                )'''
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
            log.debug("End of stream reached.")
            self.stop_if_running()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            log.debug(f"[ERROR] {err}, Debug: {debug}")
            self.stop_if_running()
        elif t == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipeline:
                old, new, pending = message.parse_state_changed()
                match new.value_nick:
                    case "null":
                        log.debug("→ Pipeline is NULL")
                    case "ready":
                        log.debug("→ Pipeline is READY")
                    case "paused":
                        log.debug("→ Pipeline is PAUSED")
                        self.gst_single_file_play_proc_paused.emit()
                        self.gst_single_file_play_proc_status.emit(PlayStatus.PAUSED)
                    case "playing":
                        log.debug("→ Pipeline is PLAYING")
                        self.gst_single_file_play_proc_started.emit()
                        self.gst_single_file_play_proc_status.emit(PlayStatus.PLAYING)
                    case "void-pending":
                        log.debug("→ VOID_PENDING (internal)")
                    case _:
                        log.debug(f"→ Unknown state: {new.value_nick}")

    def on_timeout(self):
        log.debug("on_timeout")
        self.stop_if_running()

    def run(self):
        """Run in a QThread"""
        Gst.init(None)
        self.running = True

        self.pipeline = self.create_pipeline()
        sink = self.pipeline.get_by_name("sink")
        if sink:
            sink.set_property("sync", False)
        # if self.auto_kill_after is None:
        #     return
        self.loop = GLib.MainLoop()

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        self.pipeline.set_state(Gst.State.PLAYING)

        p = pathlib.Path(self.cmd_args)
        if p.suffix in [".jpg", ".jpeg", ".png", ".webp"]:
            GLib.timeout_add(self.auto_kill_after * 1000, self.on_timeout)



        try:
            self.loop.run()
        except Exception as e:
            log.debug(f"Run loop failed: {e}")
        finally:
            log.debug("GStreamer main loop finished")
            self.pipeline.set_state(Gst.State.NULL)

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
        log.debug("pause_if_running")
        self.running = False
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PAUSED)
            log.debug("Gst.State.PAUSED")
            self.gst_single_file_play_proc_paused.emit()
            self.gst_single_file_play_proc_status.emit(PlayStatus.PAUSED)

    def resume_if_running(self):
        self.running = True
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)
            self.gst_single_file_play_proc_status.emit(PlayStatus.PLAYING)

