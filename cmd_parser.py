from global_def import *
from utils.file_utils import *

from PyQt5.QtCore import QObject, pyqtSignal

from unix_client import UnixClient


class CmdParser(QObject):
    unix_data_ready_to_send = pyqtSignal(str)
    def __init__(self, msg_unix_client:UnixClient):
        super().__init__()
        self.msg_unix_client = msg_unix_client

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

    def demo_get_playlists_file_list(self, data:dict):
        self.get_file_list_handle(data, PLAYLISTS_URI_PATH)

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
        DEMO_GET_PLAYLISTS_FILE_LIST: demo_get_playlists_file_list,
        DEMO_SET_TEST: demo_set_test,
    }