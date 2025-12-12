import enum
from enum import Enum


class PlayStatus(enum.IntEnum):
    IDLE = 0
    PLAYING = 1
    PAUSED = 2
    FINISHED = 3

PlayStatus_Dict = {
    PlayStatus.IDLE: "IDLE",
    PlayStatus.PLAYING: "PLAYING",
    PlayStatus.PAUSED: "PAUSED",
    PlayStatus.FINISHED: "FINISHED",
}

''' persist config '''
DEFAULT_STILL_IMAGE_PLAY_PERIOD_INT = 30
DEFAULT_STILL_IMAGE_PLAY_PERIOD_INT_MIN = 1
DEFAULT_STILL_IMAGE_PLAY_PERIOD_INT_MAX = 60
DEFAULT_STILL_IMAGE_PLAY_PERIOD_INT_RANGE = range(DEFAULT_STILL_IMAGE_PLAY_PERIOD_INT_MIN,
                                                  DEFAULT_STILL_IMAGE_PLAY_PERIOD_INT_MAX)
PERSIST_STILL_IMAGE_PLAY_PERIOD_CONFIG_FILENAME = "persist_still_image_play_period"
''' Audio config '''
PERSIST_VOLUME_CONFIG_FILENAME = "persist_volume"
DEFAULT_VOLUME_FLOAT = 0.6