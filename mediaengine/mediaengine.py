import errno
import json
import os
import pathlib
import platform
import sys
import os
import shlex
import time

from utils.file_utils import get_persist_config_int, set_persist_config_int
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QTimer

from global_def import *
from .gstSubtitleRenderer import GstSubtitleWorker
from .gst_subproc_player import GstSingleFileWorker
from .media_engine_def import *
from ext_qobjects.system_file_watcher import FileWatcher

from mediaengine.PlaylistManager import PlaylistManager

class MediaEngine(QObject):
    qsignal_play_single_file_finished = pyqtSignal(str)  # success, reason
    qsignal_play_single_file_started = pyqtSignal()
    qsignal_play_single_file_paused = pyqtSignal()
    qsignal_media_play_status_changed = pyqtSignal(int)
    qsignal_mediaengine_error_report = pyqtSignal(str)

    def __init__(self):
        super(MediaEngine, self).__init__()
        # worker/thread holders
        self._playlist_index = None
        self._playlist_files = None
        self._current_playlist = None

        self.playlist_mgr = PlaylistManager(PLAYLISTS_URI_PATH)
        self._current_file = 'None'
        self.gst_player = None
        # self._current_playlist = 'None'
        # need to get default from config file
        self._cancel_auto_next_once = False

        self.media_engine_status = PlayStatus.IDLE
        log.warn("check still_image_play_period later")
        self.still_image_play_period = get_persist_config_int(PERSIST_STILL_IMAGE_PLAY_PERIOD_CONFIG_FILENAME,
                                                              DEFAULT_STILL_IMAGE_PLAY_PERIOD_INT)
        # log.debug("still image playing period is %d", self.still_image_play_period)
        self.still_image_play_period_file_watcher = FileWatcher(
                                                        [os.path.join(PERSIST_CONFIG_URI_PATH,
                                                        PERSIST_STILL_IMAGE_PLAY_PERIOD_CONFIG_FILENAME)])
        self.still_image_play_period_file_watcher.install_file_changed_slot(self.refresh_still_image_play_period)


    def refresh_still_image_play_period(self):
        self.still_image_play_period = get_persist_config_int(PERSIST_STILL_IMAGE_PLAY_PERIOD_CONFIG_FILENAME,
                                                              DEFAULT_STILL_IMAGE_PLAY_PERIOD_INT)
        log.debug("still image play_period : %s", self.still_image_play_period)

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
        self.gst_player = GstSingleFileWorker(cmd_args, auto_kill_after)
        self.gst_player.install_gst_single_file_play_proc_finished(
            self._on_play_single_file_worker_finished)
        self.gst_player.install_gst_single_file_play_proc_started(
            self._on_play_single_file_worker_started)
        self.gst_player.install_gst_single_file_play_proc_paused(
            self._on_play_single_file_worker_paused)
        self.gst_player.install_gst_single_file_play_proc_status(
            self._on_play_single_file_worker_status)
        self.gst_player.start()


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

    def _render_subtitle_worker_with_cmd(self, cmd_args, auto_kill_after=None):
        if self.media_engine_status == PlayStatus.FINISHED or self.media_engine_status == PlayStatus.IDLE:
            self.gst_player = None
        # If previous running, ask to stop first
        if self.gst_player is not None and self.gst_player.is_running():
            log.debug("Playing, Please Stop First")
            return

        # Create worker
        self.gst_player = GstSubtitleWorker(cmd_args, auto_kill_after = auto_kill_after)
        self.gst_player.install_gst_subtitle_render_finished(self._on_render_subtitle_worker_finished)
        self.gst_player.install_gst_subtitle_render_started(self._on_render_subtitle_worker_started)
        self.gst_player.install_gst_subtitle_render_paused(self._on_render_subtitle_worker_paused)
        self.gst_player.install_gst_subtitle_render_status(self._on_render_subtitle_worker_status)
        self.gst_player.run()

    def _on_render_subtitle_worker_finished(self, result, reason):
        log.debug(f"_on_render_subtitle_worker_finished resson:{result}")
        self.qsignal_play_single_file_finished.emit(reason)

    def _on_render_subtitle_worker_started(self):
        log.debug("_on_render_subtitle_worker_started")
        self.qsignal_play_single_file_started.emit()

    def _on_render_subtitle_worker_paused(self):
        log.debug("_on_render_subtitle_worker_paused")
        self.qsignal_play_single_file_paused.emit()

    def _on_render_subtitle_worker_status(self, status: int):
        log.debug(f"_on_render_subtitle_worker_status:{status}")
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

    def set_still_image_play_period(self, _still_image_play_period: int):
        # Change to write to file
        # self.still_image_play_period = still_image_play_period
        if _still_image_play_period not in range(DEFAULT_STILL_IMAGE_PLAY_PERIOD_INT_MIN,
                                                  DEFAULT_STILL_IMAGE_PLAY_PERIOD_INT_MAX):
            error_data = {"func": self.set_still_image_play_period.__name__,
                          "reason": os.strerror(errno.EINVAL).replace(" ", "_")}
            log.error(error_data)
            json_error_data = json.dumps(error_data)
            self.qsignal_mediaengine_error_report.emit(json_error_data)
            return

        log.debug(f"set_still_image_play_period:{_still_image_play_period}")
        set_persist_config_int(PERSIST_STILL_IMAGE_PLAY_PERIOD_CONFIG_FILENAME, _still_image_play_period)

    def set_current_file(self, sub_file_uri: str):
        self._current_file = MEDIAFILE_URI_PATH + sub_file_uri
        log.debug(f"self._current_file :{self._current_file}")

    def single_play_from_cmd(self):
        p = pathlib.Path(self._current_file)
        if not p.is_file():
            error_data = {"func": self.single_play_from_cmd.__name__,
                          "reason": os.strerror(errno.ENOENT).replace(" ", "_")}
            json_error_data = json.dumps(error_data)
            log.error(error_data)
            self.qsignal_mediaengine_error_report.emit(json_error_data)
            return

        self.single_play(self._current_file, p.suffix)

    def render_subtitle_from_cmd(self):
        self._current_file = MEDIAFILE_URI_PATH + FILENAME_SUBTITLE
        p = pathlib.Path(self._current_file)
        if not p.is_file():
            log.debug(f"single_play_from_cmd error, no such file:{self._current_file}")

        self.single_play(self._current_file, p.suffix)

    def subtitle_color_set(self, r:int, g:int, b:int):
        GstSubtitleWorker.set_color(r, g, b)

    def subtitle_repeat_set(self, times:str):
        try:
            values = int(times)
        except Exception as e:
            log.debug(f"Convert to int failed: {e}")
            self.qsignal_mediaengine_error_report.emit(f"Subtitle repeat set invalid: {times}")
            return

        if values != 0 and values != 1 and values != -1:
            self.qsignal_mediaengine_error_report.emit(f"Subtitle repeat set out of range: {values}")
            return
        GstSubtitleWorker.set_repeat(values)

    def subtitle_color_lines_set(self, data:str):
        if data != '0' and data != '1':
            log.debug("Color lines setting is invalid")
            self.qsignal_mediaengine_error_report.emit(f"Subtitle color lines set invalid: {data}")
            return

        if data == '0':
            GstSubtitleWorker.set_color_lines(False)
        else:
            GstSubtitleWorker.set_color_lines(True)

    def single_play(self, file_uri: str, file_ext: str):
        log.debug(f"single_play, file_uri={file_uri}, file_ext={file_ext}")
        # check play thread alive or not
        log.debug("Need to check play thread alive or not")
        # self.stop_single_file_play()
        if self.gst_player is not None:
            self.gst_player.stop_if_running()

        abs_path = os.path.abspath(file_uri)
        if file_ext == ".mp4":
            gst_cmd = f"{shlex.quote(abs_path)}"
            self._play_single_file_worker_with_cmd(gst_cmd, auto_kill_after=None)
        elif file_ext in ['.jpg', '.jpeg', '.png', '.webp']:
            gst_cmd = f"{shlex.quote(abs_path)}"
            self._play_single_file_worker_with_cmd(gst_cmd, auto_kill_after=self.still_image_play_period)
        elif file_ext == '.txt':
            gst_cmd = f"{shlex.quote(abs_path)}"
            self._render_subtitle_worker_with_cmd(gst_cmd, auto_kill_after=None)

    def stop_single_file_play(self):
        log.debug("stop_play")
        if self.gst_player is not None:
            self.gst_player.stop_if_running()

    def pause_single_file_play(self):
        log.debug("pause_single_file_play")
        if self.gst_player is not None:
            self.gst_player.pause_if_running()


    def resume_single_file_play(self):
        log.debug("resume_single_file_play")
        if self.gst_player is not None:
            self.gst_player.resume_if_running()


    # ---------------- Playlist control ----------------
    def playlist_create(self, name: str) -> dict:
        return self.playlist_mgr.create(name)

    def playlist_select(self, name: str) -> dict:
        result = self.playlist_mgr.select(name)

        if result.get("status") == "OK":
            self._current_playlist = self.playlist_mgr.current_list
            log.info(f"[Playlist] Selected playlist: {self._current_playlist}")

        return result

    def playlist_get_all(self) -> dict:
        return self.playlist_mgr.get_all()

    def playlist_add_item(self, filename: str) -> dict:
        return self.playlist_mgr.add_item(filename)

    def playlist_remove_item(self, filename: str) -> dict:
        return self.playlist_mgr.remove_item(filename)

    def playlist_get_current_list(self, name: str | None = None) -> dict:
        return self.playlist_mgr.get_current_list(name)

    def playlist_remove_playlist(self, name: str) -> dict:
        return self.playlist_mgr.remove_playlist(name)

    def _playlist_play_item(self, direction=+1):
        """
        Play the current playlist item.
        direction=+1: next
        direction=-1: prev
        """

        # No playlist
        if not getattr(self, "_playlist_files", None):
            log.warning("[Playlist] No active playlist.")
            return

        total = len(self._playlist_files)
        if total == 0:
            return

        # Prevent index overflow
        self._playlist_index %= total

        f = self._playlist_files[self._playlist_index].lstrip("/")
        abs_path = os.path.join(MEDIAFILE_URI_PATH, f)

        # File does not exist → Still submit to FINISHED
        if not os.path.exists(abs_path):
            log.warning(f"[Playlist] File missing: {abs_path}")

            # TX FINISHED
            self.playlist_notify_status(PlayStatus.FINISHED, reason="FILE_NOT_FOUND")
  
            # Move index
            self._playlist_index = (self._playlist_index + direction) % total

            # Next Video
            self._playlist_play_item(direction)
            return

        # Normal playback
        p = pathlib.Path(abs_path)
        log.info(f"[Playlist] Playing ({self._playlist_index + 1}/{total}): {p}")

        self.single_play(str(p), p.suffix)

    def _handle_playlist_auto_next(self, reason):
        if self._cancel_auto_next_once:
            log.debug("[Playlist] Cancel auto next once (manual skip)")
            self._cancel_auto_next_once = False
            return

        if not hasattr(self, "_playlist_files") or not self._playlist_files:
            log.debug("[Playlist] No playlist active when finished callback triggered.")
            return
        self._playlist_index += 1
        if self._playlist_index >= len(self._playlist_files):
            log.info("[Playlist] Reached end of playlist, restarting from first item.")
            self._playlist_index = 0
        self._playlist_play_item()

    def playlist_skip_next(self):
        self._cancel_auto_next_once = True
        if not getattr(self, "_playlist_files", None):
            log.warning("[Playlist] No playlist is currently playing.")
            return {"status": "NG", "error": "No active playlist"}

        log.info("[Playlist] Skipping current file...")
        self.stop_single_file_play()

        # Move to next index (safe modulo form)
        total = len(self._playlist_files)
        self._playlist_index = (self._playlist_index + 1) % total
        log.info(f"[Playlist] Moving to next ({self._playlist_index + 1}/{total})")

        self._playlist_play_item(direction=+1)
        return {"status": "OK", "message": "Next item started"}

    def playlist_skip_prev(self) -> dict:
        self._cancel_auto_next_once = True

        if not getattr(self, "_playlist_files", None):
            log.warning("[Playlist] No playlist is currently playing.")
            return {"status": "NG", "error": "No active playlist"}

        log.info("[Playlist] Going to previous file, stopping current player...")
        self.stop_single_file_play()

        total = len(self._playlist_files)

        # Move to previous (safe modulo handling)
        self._playlist_index = (self._playlist_index - 1) % total

        log.info(f"[Playlist] Moving to previous ({self._playlist_index + 1}/{total})")

        # Play previous; direction = PREV
        self._playlist_play_item(direction=-1)

        return {"status": "OK", "message": "Previous item started"}

    def playlist_stop(self):
        log.info("[Playlist] Stop requested")

        # Break callbacks first
        try:
            self.qsignal_play_single_file_finished.disconnect(self._handle_playlist_auto_next)
        except Exception:
            pass

        # Stop the actual playback worker
        self.stop_single_file_play()

        # Reset playlist status
        self._playlist_files = []
        self._playlist_index = 0

        self.media_engine_status = PlayStatus.IDLE
        self.qsignal_media_play_status_changed.emit(self.media_engine_status)

        return {"status": "OK", "message": "Playlist stopped"}

    def playlist_get_current_file(self) -> dict:
        if not hasattr(self, "_playlist_files") or not self._playlist_files:
            return {"status": "NG","error": "No file is currently playing. Start playback to view current item."}

        if self._playlist_index is None or self._playlist_index >= len(self._playlist_files):
            return {"status": "NG", "error": "No active playing item"}

        current_file = self._playlist_files[self._playlist_index]
        return {
            "status": "OK",
            "playlist": self._current_playlist,
            "index": self._playlist_index,
            "current_file": current_file
        }

    def playlist_batch_add(self, payload: dict):
        success = {}
        failed = {}

        playlists = payload.get("playlists", [])
        for pl in playlists:
            name = pl.get("name")
            files = pl.get("files", [])
            for f in files:
                result = self.playlist_mgr.add_item_from_playlist(name, f)
                if result.get("status") == "OK":
                    success.setdefault(name, []).append(f)
                else:
                    failed.setdefault(name, []).append(f)
                log.debug(f"[BatchAdd] {name}:{f} -> {result.get('status')}")

        if failed:
            return {"status": "NG", "error": "Add failed", "success": success, "failed": failed}
        else:
            return {"status": "OK", "success": success}

    def playlist_remove_items_by_name_batch(self, payload: dict):
        success = {}
        failed = {}

        playlists = payload.get("playlists", [])
        for pl in playlists:
            name = pl.get("name")
            files = pl.get("files", [])
            for f in files:
                result = self.playlist_mgr.remove_item_from_playlist(name, f)
                if result.get("status") == "OK":
                    success.setdefault(name, []).append(f)
                else:
                    failed.setdefault(name, []).append(f)
                log.debug(f"[BatchRemove] {name}:{f} -> {result.get('status')}")

        if failed:
            return {"status": "NG", "error": "Remove failed", "success": success, "failed": failed}
        else:
            return {"status": "OK", "success": success}

    def playlist_remove_items_by_index_batch(self, payload: dict):
        success = {}
        failed = {}

        playlists = payload.get("playlists", [])
        for pl in playlists:
            name = pl.get("name")
            index_list = pl.get("index", [])

            if not name or not isinstance(index_list, list):
                failed.setdefault(name or "unknown", []).append(
                    {"error": "Invalid playlist or index_list"}
                )
                continue

            for idx in sorted(index_list, reverse=True):

                result = self.playlist_mgr.remove_item_from_playlist_by_index(name, idx)

                if result.get("status") == "OK":
                    removed_obj = result.get("removed", {})
                    success.setdefault(name, []).append(removed_obj)
                else:
                    failed.setdefault(name, []).append(
                        {"index": idx, "error": result.get("error")}
                    )
        if failed:
            return {
                "status": "NG",
                "error": "Remove failed",
                "success": success,
                "failed": failed
            }

        return {
            "status": "OK",
            "success": success
        }

    def playlist_expand_all(self):
        return self.playlist_mgr.expand_all()

    def playlist_play_at(self, name: str | None = None, index: int = 0) -> dict:
        # Stop playing safely first
        self.playlist_stop()

        # Determine playlist name
        if not name:
            name = self.playlist_mgr.current_list

        # Select playlist if needed
        if name != self.playlist_mgr.current_list:
            result = self.playlist_mgr.select(name)
            if result.get("status") != "OK":
                return result
            self._current_playlist = self.playlist_mgr.current_list
        else:
            self._current_playlist = name

        # Load playlist items
        data = self.playlist_mgr._get_files_in_current_list()
        files = data.get("files", [])
        if not files:
            return {"status": "NG", "error": f"Playlist '{name}' is empty"}

        # Validate index
        if index < 0 or index >= len(files):
            return {"status": "NG", "error": f"Index {index} out of range"}

        # Prepare playback list
        self._playlist_files = files
        self._playlist_index = index


        # Ensure auto-next installed
        try:
            self.qsignal_play_single_file_finished.disconnect(self._handle_playlist_auto_next)
        except Exception:
            pass
        self.qsignal_play_single_file_finished.connect(self._handle_playlist_auto_next)

        # Start playing from selected index
        log.info(f"[Playlist] Start playing list '{self._current_playlist}' at index {index}, total={len(files)}")
        self._playlist_play_item()

        return {
            "status": "OK",
            "playlist": name,
            "start_index": index,
            "count": len(files),
            "fpath": files[index]
        }

    def playlist_notify_status(self, status,reason=""):

        self.media_engine_status = status
        self.qsignal_media_play_status_changed.emit(self.media_engine_status)
        log.info(f"[playlist] status sent ({reason})")

        return



