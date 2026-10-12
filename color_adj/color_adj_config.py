"""Color adjustment defaults and persistent settings."""
import os
import tempfile
from pathlib import Path
import yaml

# Calibration reference: width x height, top-left -> bottom-right (exclusive).
# APL10: 201x151, (219,164) -> (420,315)
# APL25: 399x299, (120,90) -> (519,389)
# FULL: 640x480, (0,0) -> (640,480)

DEMURA_DEFAULT_LUT_NPY = '/bgr_lut.npy'
DEMURA_LUT_MAX_BYTES = 16 * 1024 * 1024
DEMURA_LUT_CHUNK_BYTES = 16 * 1024
DEMURA_LUT_NAME = 'bgr_lut.npy'
VIDEO_FRAME_W_SIZE_MAX = 640
VIDEO_FRAME_H_SIZE_MAX = 480
DEFAULT_CONFIG = {
    'demura': True,
    'video_frame_size': {'width': 640, 'height': 480},
    'offset_ori': {'x_min': 0, 'y_min': 0, 'x_max': 640, 'y_max': 480},
    'DEMURA_EDGE_TOP': 0,
    'DEMURA_EDGE_BOTTOM': 0,
    'DEMURA_EDGE_LEFT': 0,
    'DEMURA_EDGE_RIGHT': 0,
}


class ColorAdjConfig:
    EDGE_KEYS = {side: 'DEMURA_EDGE_' + side.upper()
                 for side in ('top', 'bottom', 'left', 'right')}

    def __init__(self, directory):
        self.path = Path(directory) / 'color_adj.yaml'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open('x', encoding='utf-8') as stream:
                yaml.safe_dump(DEFAULT_CONFIG, stream, sort_keys=False)
        except FileExistsError:
            pass

    def _read(self):
        with self.path.open(encoding='utf-8') as stream:
            config = yaml.safe_load(stream)
        if not isinstance(config, dict):
            raise ValueError('color_adj.yaml must contain a mapping')
        return config

    def _save(self, config):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                yaml.safe_dump(config, stream, sort_keys=False)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(self.path.stat().st_mode & 0o777)
            temporary.replace(self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _update(self, values):
        config = self._read()
        config.update(values)
        self._save(config)
    '''=============================== Demura-related  ==============================='''
    def get_demura(self):
        enabled = self._read()['demura']
        self._validate_demura(enabled)
        return enabled

    def set_demura(self, enabled):
        self._validate_demura(enabled)
        self._update({'demura': enabled})

    def get_video_frame_size(self):
        video_frame_size = self._read().get('video_frame_size', DEFAULT_CONFIG['video_frame_size'])
        self._validate_video_frame_size(video_frame_size)
        return dict(video_frame_size)

    def set_video_frame_size(self, video_frame_size):
        self._validate_video_frame_size(video_frame_size)
        self._validate_offset_ori(self.get_offset_ori(), video_frame_size)
        self._validate_edge(self.get_edge(), video_frame_size)
        self._update({'video_frame_size': video_frame_size})

    def get_edge(self):
        config = self._read()
        edge = {side: config[key] for side, key in self.EDGE_KEYS.items()}
        self._validate_edge(edge, self.get_video_frame_size())
        return edge

    def set_edge(self, edge):
        self._validate_edge(edge, self.get_video_frame_size())
        self._update({self.EDGE_KEYS[side]: value for side, value in edge.items()})

    def get_offset_ori(self):
        offset = self._read()['offset_ori']
        self._validate_offset_ori(offset, self.get_video_frame_size())
        return offset

    def set_offset_ori(self, offset):
        self._validate_offset_ori(offset, self.get_video_frame_size())
        self._update({'offset_ori': offset})

    @staticmethod
    def _validate_demura(enabled):
        if type(enabled) is not bool:
            raise ValueError('demura must be true or false')

    @classmethod
    def _validate_edge(cls, edge, video_frame_size):
        if not isinstance(edge, dict) or set(edge) != set(cls.EDGE_KEYS):
            raise ValueError('edge requires top, bottom, left, right')
        for side, value in edge.items():
            limit = video_frame_size['height'] if side in ('top', 'bottom') else video_frame_size['width']
            if type(value) is not int or not 0 <= value <= limit:
                raise ValueError(f'{side} must be an integer from 0 to {limit}')

    @staticmethod
    def _validate_video_frame_size(video_frame_size):
        if not isinstance(video_frame_size, dict) or set(video_frame_size) != {'width', 'height'}:
            raise ValueError('video_frame_size requires width and height')
        if any(type(value) is not int for value in video_frame_size.values()):
            raise ValueError('video_frame_size width and height must be integers')
        if not 1 <= video_frame_size['width'] <= VIDEO_FRAME_W_SIZE_MAX:
            raise ValueError(f'video_frame_size width must be within 1 to {VIDEO_FRAME_W_SIZE_MAX}')
        if not 1 <= video_frame_size['height'] <= VIDEO_FRAME_H_SIZE_MAX:
            raise ValueError(f'video_frame_size height must be within 1 to {VIDEO_FRAME_H_SIZE_MAX}')

    @staticmethod
    def _validate_offset_ori(offset, video_frame_size):
        if not isinstance(offset, dict) or set(offset) != {'x_min', 'y_min', 'x_max', 'y_max'}:
            raise ValueError('offset_ori requires x_min, y_min, x_max, y_max')
        if any(type(value) is not int for value in offset.values()):
            raise ValueError('offset_ori coordinates must be integers')
        if not (0 <= offset['x_min'] < offset['x_max'] <= video_frame_size['width'] and
                0 <= offset['y_min'] < offset['y_max'] <= video_frame_size['height']):
            raise ValueError('ROI must have positive size within video_frame_size')

    '''=============================== End  ==============================='''
