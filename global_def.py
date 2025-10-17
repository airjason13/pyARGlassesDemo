import platform

import utils.log_utils
from version import Version
from arglassescmd.cmd_def import *
LOG_FILE_PREFIX = "ar_glasses_demo.log"

log = utils.log_utils.logging_init(__file__, LOG_FILE_PREFIX)


FULL_SCREEN_UI = True
ENG_UI = False



UNIX_MSG_SERVER_URI = '/tmp/ipc_msg_server.sock'
UNIX_DEMO_APP_SERVER_URI = '/tmp/ipc_demo_app_server.sock'
UNIX_SYS_SERVER_URI = '/tmp/ipc_sys_server.sock'
UNIX_LE_SERVER_URI = '/tmp/ipc_le_server.sock'




# Media File Uri Path
if platform.machine() == 'x86_64':
    MEDIAFILE_URI_PATH = "/home/venom/Videos/"
    SNAPSHOTS_URI_PATH = "/home/venom/Videos/Snapshots/"
    RECORDINGS_URI_PATH = "/home/venom/Videos/Recordings/"
    MEDIA_URI_PATH = "/home/venom/Videos/Media/"
    THUMBNAILS_URI_PATH = "/home/venom/Videos/thumbnails/"
    PLAYLISTS_URI_PATH = "/home/venom/Videos/playlists/"
else:
    MEDIAFILE_URI_PATH = "/root/MediaFiles/"
    SNAPSHOTS_URI_PATH = "/root/MediaFiles/Snapshots/"
    RECORDINGS_URI_PATH = "/root/MediaFiles/Recordings/"
    MEDIA_URI_PATH = "/root/MediaFiles/Media/"
    THUMBNAILS_URI_PATH = "/root/MediaFiles/thumbnails/"
    PLAYLISTS_URI_PATH = "/root/MediaFiles/Playlists/"