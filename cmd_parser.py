from global_def import *


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


    def demo_set_test(self, data: dict):
        data['src'], data['dst'] = data['dst'], data['src']
        log.debug("data : %s", data)

    cmd_function_map = {
        DEMO_GET_SW_VERSION: demo_get_sw_version,
        DEMO_SET_TEST: demo_set_test,
    }