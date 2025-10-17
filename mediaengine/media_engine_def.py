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