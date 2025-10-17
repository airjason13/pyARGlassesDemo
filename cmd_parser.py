from global_def import *
from mediaengine.mediaengine import MediaEngine
from utils.file_utils import *

from PyQt5.QtCore import QObject, pyqtSignal

from unix_client import UnixClient


class CmdParser(QObject):
    unix_data_ready_to_send = pyqtSignal(str)
    def __init__(self, msg_unix_client:UnixClient, media_engine:MediaEngine):
        super().__init__()
        self.msg_unix_client = msg_unix_client
        self.media_engine = media_engine

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

    def demo_get_mediafile_file_list(self, data:dict):
        self.get_file_list_handle(data, MEDIAFILE_URI_PATH)

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

    def demo_set_test(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        log.debug("data : %s", data)

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

        DEMO_SET_TEST: demo_set_test,
    }