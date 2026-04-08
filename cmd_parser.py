from global_def import *
from mediaengine.media_engine_def import PlayStatus_Dict
from mediaengine.mediaengine import MediaEngine
from navengine.nav_def import SUPPORTED_NAV_DIRECTIONS
from navengine.nav_player import ARNavPlayer
from utils.file_utils import *

from PyQt5.QtCore import QObject, pyqtSignal

from unix_client import UnixClient
import shutil
from pathlib import Path
import json

class CmdParser(QObject):
    unix_data_ready_to_send = pyqtSignal(str)
    def __init__(self, msg_unix_client:UnixClient, media_engine:MediaEngine, nav_player:ARNavPlayer):
        super().__init__()
        self.msg_unix_client = msg_unix_client
        self.media_engine = media_engine
        self.nav_player = nav_player
        self.media_engine.install_media_play_status_changed(self.media_engine_status_changed)
        self.media_engine.install_media_engine_error_report(self.media_engine_error_report)

    def parse_cmds(self, data):
        log.debug("data : %s", data)
        d = dict(item.split(':', 1) for item in data.split(';'))
        if 'data' not in data:
            d['data'] = 'no_data'
        else:
            pass
        log.debug("%s", d)
        log.debug("d['cmd']: %s", d['cmd'])
        try:
            self.cmd_function_map[d['cmd']](self, d)
        except Exception as e:
            log.error(e)


    def demo_get_sw_version(self, data:dict):
        data['src'], data['dst'] = data['dst'], data['src']
        data['data'] = Version
        log.debug("data : %s", data)
        # Dict to Str
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def get_file_list_handle(self, data:dict, path:str):
        data['src'], data['dst'] = data['dst'], data['src']
        data['data'] = list_files_by_ext(path)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def get_file_list_handle_test(self, data:dict, str_len:int):
        data['src'], data['dst'] = data['dst'], data['src']
        data['data'] = gen_string(str_len)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_get_mediafile_file_list(self, data:dict):
        self.get_file_list_handle(data, MEDIAFILE_URI_PATH)
        ''' for test transfer max size '''
        # self.get_file_list_handle_test(data, 32768) # -> ok
        # self.get_file_list_handle_test(data, 65535) # -> ok
        # self.get_file_list_handle_test(data, 64*1024)


    def demo_get_snapshots_file_list(self, data:dict):
        self.get_file_list_handle(data, SNAPSHOTS_URI_PATH)

    def demo_get_recordings_file_list(self, data:dict):
        self.get_file_list_handle(data, RECORDINGS_URI_PATH)

    def demo_get_media_file_list(self, data:dict):
        self.get_file_list_handle(data, MEDIA_URI_PATH)

    def demo_get_thumbnails_file_list(self, data:dict):
        self.get_file_list_handle(data, THUMBNAILS_URI_PATH)

    def demo_get_mediaengine_status(self, data:dict):
        data['src'], data['dst'] = data['dst'], data['src']
        data['data'] = self.media_engine.get_status_str()
        # Dict to Str
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_get_mediaengine_still_image_period(self, data:dict):
        data['src'], data['dst'] = data['dst'], data['src']
        data['data'] = self.media_engine.get_still_image_play_period_str()
        # Dict to Str
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_get_mediaengine_file_uri(self, data:dict):
        data['src'], data['dst'] = data['dst'], data['src']
        data['data'] = self.media_engine.get_current_file()
        # Dict to Str
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_mediaengine_still_image_period(self, data:dict):
        log.debug("data : %s", data.get('data'))
        self.media_engine.set_still_image_play_period(int(data.get('data')))

    def demo_set_mediaengine_play_single_file(self, data:dict):
        log.debug("data : %s", data.get('data'))
        self.media_engine.set_current_file(data.get('data'))
        self.media_engine.single_play_from_cmd()

    def demo_set_mediaengine_pause(self, data:dict):
        log.debug("data : %s", data.get('data'))
        if data.get('data') == 'True':
            self.media_engine.pause_single_file_play()

    def demo_set_mediaengine_stop(self, data:dict):
        log.debug("data : %s", data)
        if data.get('data') == 'True':
            self.media_engine.stop_single_file_play()

    def demo_set_mediaengine_resume_playing(self, data:dict):
        log.debug("data : %s", data)
        if data.get('data') == 'True':
            self.media_engine.resume_single_file_play()

    def demo_set_mediaengine_render_subtitle(self, data:dict):
        log.debug("data : %s", data.get('data'))
        # pathSubtitlFolder = Path(MEDIAFILE_URI_PATH)
        # pathSubtitlFolder.mkdir(parents=True, exist_ok=True)

        pathSubtitlFile = Path(TEMPORARY_SUBTITLE_URI_PATH)
        if pathSubtitlFile.exists():
            if pathSubtitlFile.is_file():
                pathSubtitlFile.unlink()                # remove file
            else:
                shutil.rmtree(pathSubtitlFile)          # remove tree
        pathSubtitlFile.touch()                         # create file
        pathSubtitlFile.write_text(data.get('data'))
        self.media_engine.render_subtitle_from_cmd()

    def demo_set_test(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        log.debug("data : %s", data)

    def demo_set_mediaengine_subtitle_color(self, data:dict):
        if data['data'] == 'no_data':
            return
        settings = data['data'].lower()

        result = dict(item.split('=') for item in settings.split(',') if '=' in item)

        r = result.get('r', None)
        g = result.get('g', None)
        b = result.get('b', None)

        if r != None and g != None and b != None:
            self.media_engine.subtitle_color_set(int(r), int(g), int(b))

    def demo_set_mediaengine_subtitle_repeat(self, data:dict):
        if data['data'] == 'no_data':
            return
        times = data['data'].lower()
        self.media_engine.subtitle_repeat_set(times)

    def demo_set_mediaengine_subtitle_color_lines(self, data:dict):
        if data['data'] == 'no_data':
            return
        enable = data['data'].lower()
        self.media_engine.subtitle_color_lines_set(enable)

    # =========================
    # === Playlist Commands ===
    # =========================
    def demo_set_playlist_create(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        result = self.media_engine.playlist_create(data.get("data"))
        # Dict to Str
        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_playlist_select(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        result = self.media_engine.playlist_select(data.get("data"))
        # Dict to Str
        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_get_playlist_get_all(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        result = self.media_engine.playlist_get_all()
        # Dict to Str
        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_playlist_add_item(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        result = self.media_engine.playlist_add_item(data.get("data"))
        # Dict to Str
        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_playlist_remove_item(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        result = self.media_engine.playlist_remove_item(data.get("data"))
        # Dict to Str
        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_get_playlist_get_list(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        result = self.media_engine.playlist_get_current_list(data.get("data"))
        # Dict to Str
        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_playlist_play(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        payload = json.loads(data.get("data", "{}"))
        name = payload.get("name",None)
        raw_index = payload.get("index", 0)
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            index = 0

        result = self.media_engine.playlist_play_at(name=name, index=index)
        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_playlist_stop(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        if data.get('data') == 'True':
            result = self.media_engine.playlist_stop()
        else :
            result = {"status": "NG", "error": "stopped playlist"}

        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_playlist_remove_playlist(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        result = self.media_engine.playlist_remove_playlist(data.get("data"))

        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_playlist_next(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        if data.get('data') == 'True':
            result = self.media_engine.playlist_skip_next()
        else:
            result = {"status": "NG", "error": "cannot skip to next"}
        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_playlist_prev(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        if data.get('data') == 'True':
            result = self.media_engine.playlist_skip_prev()
        else:
            result = {"status": "NG", "error": "cannot skip to prev"}
        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_get_playlist_get_current_file(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        result = self.media_engine.playlist_get_current_file()
        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_playlist_batch_add(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        try:
            payload = json.loads(data.get("data", "{}"))
            result = self.media_engine.playlist_batch_add(payload)
            data['data'] = json.dumps(result, ensure_ascii=False)
        except Exception as e:
            log.error(f"demo_set_playlist_batch_add error: {e}")
            data['data'] = json.dumps({"status": "NG", "error": str(e)}, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_playlist_batch_remove_by_name(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        try:
            payload = json.loads(data.get("data", "{}"))
            # Extract batch remove payload: {"playlists":[{"name":...,"files":[...]},...]}
            result = self.media_engine.playlist_remove_items_by_name_batch(payload)
            data['data'] = json.dumps(result, ensure_ascii=False)
        except Exception as e:
            log.error(f"demo_set_playlist_batch_remove_by_name error: {e}")
            data['data'] = json.dumps({"status": "NG", "error": str(e)}, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_playlist_batch_remove_by_index(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        try:
            payload = json.loads(data.get("data", "{}"))
            result = self.media_engine.playlist_remove_items_by_index_batch(payload)
            data['data'] = json.dumps(result, ensure_ascii=False)
        except Exception as e:
            log.error(f"demo_set_playlist_batch_remove_by_index error: {e}")
            data['data'] = json.dumps({"status": "NG", "error": str(e)}, ensure_ascii=False)

        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_get_playlist_expand_all(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        try:
            result = self.media_engine.playlist_expand_all()
            data['data'] = json.dumps(result, ensure_ascii=False)
        except Exception as e:
            log.error(f"demo_get_playlist_expand_all error: {e}")
            data['data'] = json.dumps({"status": "NG", "error": str(e)}, ensure_ascii=False)

        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_media_volume(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        try:
            payload = json.loads(data.get("data", "{}"))
            volume = float(payload.get("volume"))
            self.media_engine.set_volume(volume)
            result = {
                "status": "OK",
                "volume": self.media_engine.current_volume
            }
            data['data'] = json.dumps(result, ensure_ascii=False)
        except Exception as e:
            log.error(f"demo_set_media_volume error: {e}")
            data['data'] = json.dumps(
                {"status": "NG", "error": str(e)},
                ensure_ascii=False
            )
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_get_media_volume(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']

        try:
            result = {
                "status": "OK",
                "volume": self.media_engine.current_volume,
                "max": self.media_engine.max_volume_boost
            }

            data['data'] = json.dumps(result, ensure_ascii=False)

        except Exception as e:
            log.error(f"demo_get_media_volume error: {e}")
            data['data'] = json.dumps(
                {"status": "NG", "error": str(e)},
                ensure_ascii=False
            )

        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_nav_state(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']

        try:
            # parse JSON
            payload = json.loads(data.get("data", "{}"))

            direction = payload.get("direction")
            road_name = payload.get("road_name")
            distance_m = payload.get("distance_m")

            if direction is None or road_name is None or distance_m is None:
                raise ValueError("Invalid data format")

            if direction not in SUPPORTED_NAV_DIRECTIONS:
                result = {
                    "status": "NG",
                    "error": "Invalid direction"
                }
            else:
                self.nav_player.set_nav_state(direction,road_name,distance_m)
                log.info(f"[NAV] direction={direction}, road={road_name}, dist={distance_m}")
                # self.main_window.switch_page("Nav")

                result = {
                    "status": "OK"
                }

        except Exception as e:
            log.error(f"demo_set_nav_state error: {e}")
            result = {
                "status": "NG",
                "error": "Invalid data format"
            }

        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_nav_stop(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']

        try:
            self.nav_player.stop()
            log.info("[NAV] stop")

            result = {
                "status": "OK"
            }

        except Exception as e:
            log.error(f"demo_set_nav_stop error: {e}")
            result = {
                "status": "NG"
            }
        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    def demo_set_nav_map_image(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']

        try:
            payload = json.loads(data.get("data", "{}"))

            # file_name = payload.get("file_name", "")
            # file_name = "map_image"
            hex_data = payload.get("hex", "")

            self.nav_player.set_nav_map_image(hex_str = hex_data)

            result = {"status": "OK"}

        except Exception as e:
            log.error(f"demo_set_nav_map_image error: {e}")
            result = {"status": "NG", "error": str(e)}

        data['data'] = json.dumps(result, ensure_ascii=False)
        reply = ";".join(f"{k}:{v}" for k, v in data.items())
        self.unix_data_ready_to_send.emit(reply)

    cmd_function_map = {
        DEMO_GET_SW_VERSION: demo_get_sw_version,
        DEMO_GET_MEDIAFILE_FILE_LIST: demo_get_mediafile_file_list,
        DEMO_GET_SNAPSHOTS_FILE_LIST: demo_get_snapshots_file_list,
        DEMO_GET_RECORDINGS_FILE_LIST: demo_get_recordings_file_list,
        DEMO_GET_MEDIA_FILE_LIST: demo_get_media_file_list,
        DEMO_GET_THUMBNAILS_FILE_LIST: demo_get_thumbnails_file_list,
        DEMO_GET_MEDIAENGINE_STATUS: demo_get_mediaengine_status,
        DEMO_GET_MEDIAENGINE_STILL_IMAGE_PERIOD: demo_get_mediaengine_still_image_period,
        DEMO_GET_MEDIAENGINE_FILE_URI: demo_get_mediaengine_file_uri,

        DEMO_SET_MEDIAENGINE_STILL_IMAGE_PERIOD: demo_set_mediaengine_still_image_period,
        DEMO_SET_MEDIAENGINE_PLAY_SINGLE_FILE: demo_set_mediaengine_play_single_file,
        DEMO_SET_MEDIAENGINE_PAUSE: demo_set_mediaengine_pause,
        DEMO_SET_MEDIAENGINE_STOP: demo_set_mediaengine_stop,
        DEMO_SET_MEDIAENGINE_RESUME_PLAYING: demo_set_mediaengine_resume_playing,

        DEMO_SET_MEDIAENGINE_RENDER_SUBTITLE: demo_set_mediaengine_render_subtitle,
        DEMO_SET_MEDIAENGINE_SUBTITLE_COLOR: demo_set_mediaengine_subtitle_color,
        DEMO_SET_MEDIAENGINE_SUBTITLE_REPEAT: demo_set_mediaengine_subtitle_repeat,
        DEMO_SET_MEDIAENGINE_SUBTITLE_COLOR_LINES: demo_set_mediaengine_subtitle_color_lines,

        DEMO_SET_PLAYLIST_CREATE: demo_set_playlist_create,
        DEMO_SET_PLAYLIST_SELECT: demo_set_playlist_select,
        DEMO_GET_PLAYLIST_GET_ALL: demo_get_playlist_get_all,
        DEMO_SET_PLAYLIST_ADD_ITEM: demo_set_playlist_add_item,
        DEMO_SET_PLAYLIST_REMOVE_ITEM: demo_set_playlist_remove_item,
        DEMO_GET_PLAYLIST_GET_LIST: demo_get_playlist_get_list,
        DEMO_SET_PLAYLIST_PLAY: demo_set_playlist_play,
        DEMO_SET_PLAYLIST_STOP: demo_set_playlist_stop,
        DEMO_SET_PLAYLIST_REMOVE_PLAYLIST: demo_set_playlist_remove_playlist,
        DEMO_SET_PLAYLIST_NEXT_ITEM: demo_set_playlist_next,
        DEMO_SET_PLAYLIST_PREV_ITEM: demo_set_playlist_prev,
        DEMO_GET_PLAYLIST_GET_CURRENT_FILE: demo_get_playlist_get_current_file,
        DEMO_SET_PLAYLIST_BATCH_ADD: demo_set_playlist_batch_add,
        DEMO_SET_PLAYLIST_BATCH_REMOVE_BY_NAME: demo_set_playlist_batch_remove_by_name,
        DEMO_SET_PLAYLIST_BATCH_REMOVE_BY_INDEX: demo_set_playlist_batch_remove_by_index,
        DEMO_GET_PLAYLIST_EXPAND_ALL: demo_get_playlist_expand_all,

        DEMO_SET_MEDIA_VOLUME:demo_set_media_volume,
        DEMO_GET_MEDIA_VOLUME:demo_get_media_volume,
        DEMO_SET_TEST: demo_set_test,

        DEMO_SET_NAV_STATE:demo_set_nav_state,
        DEMO_SET_NAV_STOP:demo_set_nav_stop,
        DEMO_SET_NAV_MAP_IMAGE:demo_set_nav_map_image,
    }

    ''''''
    def spec_cmd_pack(self, spec_cmd:str, spec_cmd_data:str):
        data = {}
        data['idx'] = 0
        data['src'] = 'demo'
        data['dst'] = 'mobile'
        data['cmd'] = spec_cmd
        data['data'] = spec_cmd_data
        return data

    def media_engine_status_changed(self, status: int):
        log.debug(f"status : {PlayStatus_Dict.get(status)}")
        str_status = PlayStatus_Dict.get(status)
        reply_dict = self.spec_cmd_pack(DEMO_SPEC_MEDIAENGINE_STATUS_REPORT, str_status)
        reply_str = ";".join(f"{k}:{v}" for k, v in reply_dict.items())
        self.unix_data_ready_to_send.emit(reply_str)

    def media_engine_error_report(self, reason: str):
        log.debug(f"media_engine_error_report : {reason}")
        reply_dict = self.spec_cmd_pack(DEMO_SPEC_MEDIAENGINE_CMD_ERROR_REPORT, reason)
        reply_str = ";".join(f"{k}:{v}" for k, v in reply_dict.items())
        self.unix_data_ready_to_send.emit(reply_str)

