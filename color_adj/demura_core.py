import hashlib
import io
import os
import platform
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

from global_def import *
from color_adj.color_adj_config import ColorAdjConfig, DEMURA_LUT_NAME, DEMURA_LUT_MAX_BYTES, DEMURA_DEFAULT_LUT_NPY, DEMURA_LUT_CHUNK_BYTES


class DemuraCore:
    # =====================================================
    # Lifecycle / runtime reload
    # =====================================================

    def __init__(self, config_dir=None, lut_name=None):
        # -------------------------------------------------
        # Global Config
        # -------------------------------------------------

        if config_dir is None:
            config_dir = COLOR_ADJ_CONFIG_URI_PATH
        self.config = ColorAdjConfig(config_dir)
        self.yaml_path = self.config.path
        edge = self.config.get_edge()

        # -------------------------------------------------
        # Path
        # -------------------------------------------------

        self.base_dir = Path(__file__).resolve().parent

        self.lut_path = self.config.path.parent / DEMURA_LUT_NAME
        if not self.lut_path.exists():
            source = self.base_dir / (lut_name or DEMURA_DEFAULT_LUT_NPY)
            self._write_lut(source.read_bytes())

        self.transform_src = self.base_dir / "demura_transform.c"

        self.neon_src = self.base_dir / "demura_neon.c"

        # -------------------------------------------------
        # Runtime Path
        # -------------------------------------------------

        self.runtime_dir = Path(DEMURA_RUNTIME_DIR)

        self.runtime_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.gst_plugin_path = self.runtime_dir / "libgstdemura.so"

        self.gain_q8_path = self.runtime_dir / "gain_q8.bin"
        self._lut_upload = None

        # -------------------------------------------------
        # Platform
        # -------------------------------------------------

        self.is_x86 = (platform.machine() == "x86_64")

        # ARM  : NEON
        # x86  : Generic C
        self.use_neon = not self.is_x86

        # Both ARM and x86 use GStreamer Plugin
        self.use_gst_plugin = True

        # -------------------------------------------------
        # Runtime State
        # -------------------------------------------------

        self.enabled = self.config.get_demura()

        self.initialized = False

        # -------------------------------------------------
        # ROI Extension
        #
        # Loaded from color_adj.yaml
        # -------------------------------------------------

        self.extend_top = edge['top']

        self.extend_bottom = edge['bottom']

        self.extend_left = edge['left']

        self.extend_right = edge['right']

        # -------------------------------------------------
        # Calibration Data
        # -------------------------------------------------

        self.offset_ori = None
        self.frame_width = 0
        self.frame_height = 0

        self.x_min = 0
        self.y_min = 0
        self.x_max = 0
        self.y_max = 0

        self.work_w = 0
        self.work_h = 0

        self.lut_bgr = None
        self.gain_bgr = None
        self.gain_q8 = None

    def initialize(self):
        log.debug("=== DemuraCore Initialize ===")

        if self.use_gst_plugin:
            self.build_gst_plugin()

        self.reload_runtime(
            reload_config=True,
            reload_lut=True,
        )

        self.initialized = True

        self.print_status()

        return True

    def reload_runtime(self, reload_config=True, reload_lut=False):
        log.debug(
            "[DemuraCore] reload_runtime: "
            "config=%s lut=%s",
            reload_config,
            reload_lut,
        )

        if reload_config:
            self.load_config()

        if reload_lut:
            self.load_lut()

        self.setup_roi_gain()

        if self.use_gst_plugin:
            self.generate_q8_gain()

    # =====================================================
    # Command API: On/Off, ROI, Edge and LUT
    # =====================================================

    # Stop both players before calling ROI, Edge or LUT setters.

    def get_enabled(self):
        return self.config.get_demura()

    def set_enabled(self, enabled):
        self.config.set_demura(enabled)
        self.enabled = bool(enabled)
        log.debug('[DemuraCore] Enabled = %s', self.enabled)
        return self.enabled

    def get_offset_ori(self):
        return self.config.get_offset_ori()

    def get_video_frame_size(self):
        return self.config.get_video_frame_size()

    def set_video_frame_size(self, video_frame_size):
        self.config.set_video_frame_size(video_frame_size)
        self.reload_runtime(reload_config=True, reload_lut=True)
        return self.get_video_frame_size()

    def set_offset_ori(self, offset):
        self.config.set_offset_ori(offset)
        self.reload_runtime(reload_config=True, reload_lut=True)
        return self.get_offset_ori()

    def get_edge(self):
        return self.config.get_edge()

    def set_edge(self, edge):
        self.config.set_edge(edge)
        self.reload_runtime(reload_config=True, reload_lut=True)
        return self.get_edge()

    def receive_lut_chunk(self, payload):
        """Append one ordered chunk. Return verified bytes only when complete."""
        try:
            if not isinstance(payload, dict):
                raise ValueError('LUT requires id, size, sha256 and hex')
            upload_id = payload.get('id')
            size, checksum, hex_data = (payload.get(key) for key in ('size', 'sha256', 'hex'))
            if not isinstance(upload_id, str) or not 1 <= len(upload_id) <= 64:
                raise ValueError('id must be a nonempty string of at most 64 characters')
            if type(size) is not int or not 0 < size <= DEMURA_LUT_MAX_BYTES:
                raise ValueError('LUT size must be between 1 byte and 16 MiB')
            if (not isinstance(checksum, str) or len(checksum) != 64
                    or any(c not in '0123456789abcdefABCDEF' for c in checksum)):
                raise ValueError('sha256 must contain 64 hex characters')
            checksum = checksum.lower()
            if (not isinstance(hex_data, str) or not 0 < len(hex_data) <= DEMURA_LUT_CHUNK_BYTES * 2
                    or len(hex_data) % 2 or any(c not in '0123456789abcdefABCDEF' for c in hex_data)):
                raise ValueError('hex must encode 1 to 16384 bytes')
            chunk = bytes.fromhex(hex_data)
            upload = self._lut_upload
            if upload and upload['id'] != upload_id:
                self.clear_lut_upload()
                upload = None
            if upload is None:
                directory = self.runtime_dir / 'uploads'
                directory.mkdir(parents=True, exist_ok=True)
                # Never use the caller-provided id as a filesystem path.
                with tempfile.NamedTemporaryFile(dir=directory, suffix='.part', delete=False) as stream:
                    path = Path(stream.name)
                upload = self._lut_upload = dict(id=upload_id, size=size, sha256=checksum,
                                                path=path, received=0)
            if upload['size'] != size or upload['sha256'] != checksum:
                raise ValueError('size and sha256 must stay unchanged for the same id')
            if upload['received'] + len(chunk) > size:
                raise ValueError('LUT received bytes exceed size')
            with upload['path'].open('ab') as stream:
                stream.write(chunk)
            upload['received'] += len(chunk)
            result = dict(id=upload_id, received=upload['received'], size=size)
            if upload['received'] < size:
                return result, None
            raw = upload['path'].read_bytes()
            if len(raw) != size or hashlib.sha256(raw).hexdigest() != checksum:
                raise ValueError('LUT size or SHA-256 mismatch')
            self._read_lut(raw)
            return result, raw
        except Exception:
            self.clear_lut_upload()
            raise

    def clear_lut_upload(self):
        if self._lut_upload is None:
            return

        path = self._lut_upload['path']

        if DEMURA_KEEP_UPLOAD_TEMP:
            log.debug('[DemuraCore] Keep upload temp: %s', path)
        else:
            path.unlink(missing_ok=True)

        self._lut_upload = None

    def set_lut(self, raw):
        # Caller stops both players before replacing runtime gain.
        self._read_lut(raw)
        previous = self.lut_path.read_bytes()
        previous_state = self.__dict__.copy()
        previous_gain = self.gain_q8_path.read_bytes() if self.gain_q8_path.exists() else None
        try:
            self._write_lut(raw)
            self.reload_runtime(reload_config=True, reload_lut=True)
        except Exception:
            self._write_lut(previous)
            self.__dict__.update(previous_state)
            if previous_gain is None:
                self.gain_q8_path.unlink(missing_ok=True)
            else:
                self.gain_q8_path.write_bytes(previous_gain)
            raise
        return {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

    # =====================================================
    # Player API / diagnostics
    # =====================================================

    def get_gst_properties(self):
        if not self.initialized:

            raise RuntimeError("DemuraCore is not initialized")

        return {

            "enabled":
                bool(self.enabled),

            "x-min":
                int(self.x_min),

            "y-min":
                int(self.y_min),

            "x-max":
                int(self.x_max),

            "y-max":
                int(self.y_max),

            "gain-file":
                str(self.gain_q8_path),
        }

    def process_frame(self, frame_bgr):
        if not self.initialized:

            raise RuntimeError("DemuraCore is not initialized")

        if not self.enabled:

            return frame_bgr

        if frame_bgr is None:

            return None

        if frame_bgr.dtype != np.uint8:

            raise ValueError("frame_bgr must be uint8")

        if (
            frame_bgr.ndim != 3
            or
            frame_bgr.shape[2] != 3
        ):

            raise ValueError("frame_bgr must be BGR HxWx3")

        # -------------------------------------------------
        # ARM streaming uses native GStreamer plugin.
        # -------------------------------------------------

        if self.use_neon:

            return frame_bgr

        # -------------------------------------------------
        # x86 offline fallback
        # -------------------------------------------------

        return self._process_numpy(frame_bgr)

    def print_status(self):
        log.debug("================================")

        log.debug("       DemuraCore Status")

        log.debug("================================")

        log.debug(
            f"Platform       : "
            f"{platform.machine()}"
        )

        log.debug(
            f"GST Plugin     : "
            f"{self.use_gst_plugin}"
        )

        log.debug(
            f"NEON           : "
            f"{self.use_neon}"
        )

        if self.use_neon:

            log.debug("Processing     : ARM NEON")

        else:

            log.debug("Processing     : Generic C")

        log.debug(
            f"Enabled        : "
            f"{self.enabled}"
        )

        log.debug(
            f"YAML           : "
            f"{self.yaml_path.name}"
        )

        log.debug(
            f"LUT            : "
            f"{self.lut_path.name}"
        )

        log.debug(
            f"ROI Extend     : "
            f"T={self.extend_top}, "
            f"B={self.extend_bottom}, "
            f"L={self.extend_left}, "
            f"R={self.extend_right}"
        )

        log.debug(
            f"ROI            : "
            f"x={self.x_min}~{self.x_max}, "
            f"y={self.y_min}~{self.y_max}"
        )

        log.debug(
            f"Video Frame Size     : "
            f"{self.frame_width} x {self.frame_height}"
        )

        log.debug(
            f"Work Size      : "
            f"{self.work_w} x "
            f"{self.work_h}"
        )

        if self.gain_bgr is not None:

            log.debug(
                f"Gain Shape     : "
                f"{self.gain_bgr.shape}"
            )

        if self.gain_q8 is not None:

            log.debug(
                f"Q8 Shape       : "
                f"{self.gain_q8.shape}"
            )

            log.debug(
                f"Q8 File        : "
                f"{self.gain_q8_path}"
            )

        if self.use_gst_plugin:

            log.debug(
                f"GST Plugin File: "
                f"{self.gst_plugin_path}"
            )

        log.debug("================================")

    # =====================================================
    # Internal: plugin build
    # =====================================================

    def build_gst_plugin(self):
        """
        Build:

            demura_transform.c
                    +
            demura_neon.c
                    |
                    v
            libgstdemura.so

        demura_neon.c:

            ARM  -> NEON
            x86  -> Generic C
        """

        # -------------------------------------------------
        # Check Source
        # -------------------------------------------------

        if not self.transform_src.exists():

            raise FileNotFoundError(
                f"Demura Transform source not found: "
                f"{self.transform_src}"
            )

        if not self.neon_src.exists():

            raise FileNotFoundError(
                f"Demura Processing source not found: "
                f"{self.neon_src}"
            )

        # -------------------------------------------------
        # Get GStreamer Build Flags
        # -------------------------------------------------

        try:

            pkg_result = subprocess.run(
                [
                    "pkg-config",
                    "--cflags",
                    "--libs",
                    "gstreamer-1.0",
                    "gstreamer-base-1.0",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        except FileNotFoundError:

            raise RuntimeError("pkg-config not found.")

        except subprocess.CalledProcessError as e:

            log.error(
                "[DemuraCore] "
                "Failed to get GStreamer build flags"
            )

            if e.stdout:
                log.error(e.stdout)

            if e.stderr:
                log.error(e.stderr)

            raise

        gst_flags = (
            pkg_result.stdout
            .strip()
            .split()
        )

        # -------------------------------------------------
        # Architecture Flags
        # -------------------------------------------------

        if self.is_x86:

            arch_flags = []

            log.debug(
                "[DemuraCore] "
                "Build target: x86_64 / Generic C"
            )

        else:

            arch_flags = [
                "-march=armv8-a"
            ]

            log.debug(
                "[DemuraCore] "
                "Build target: ARM / NEON"
            )

        # -------------------------------------------------
        # Build Command
        # -------------------------------------------------

        cmd = [
            "gcc",

            "-O3",
            "-shared",
            "-fPIC",

            *arch_flags,

            str(self.transform_src),
            str(self.neon_src),

            "-o",
            str(self.gst_plugin_path),

            *gst_flags,
        ]

        log.debug(
            "[DemuraCore] "
            "Building GStreamer Demura Plugin"
        )

        log.debug(
            "[DemuraCore] "
            + " ".join(cmd)
        )

        # -------------------------------------------------
        # Compile
        # -------------------------------------------------

        try:

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )

            if result.stdout:
                log.debug(result.stdout)

        except FileNotFoundError:

            raise RuntimeError("gcc not found.")

        except subprocess.CalledProcessError as e:

            log.error(
                "[DemuraCore] "
                "GStreamer Demura Plugin build failed"
            )

            if e.stdout:
                log.error(e.stdout)

            if e.stderr:
                log.error(e.stderr)

            raise

        # -------------------------------------------------
        # Success
        # -------------------------------------------------

        log.debug(
            f"[DemuraCore] "
            f"Plugin build success: "
            f"{self.gst_plugin_path}"
        )

        return True

    # =====================================================
    # Internal: config and LUT loading
    # =====================================================

    def load_config(self):
        self.enabled = self.config.get_demura()
        video_frame_size = self.config.get_video_frame_size()
        self.frame_width = video_frame_size['width']
        self.frame_height = video_frame_size['height']
        edge = self.config.get_edge()
        self.extend_top = edge['top']
        self.extend_bottom = edge['bottom']
        self.extend_left = edge['left']
        self.extend_right = edge['right']


        offset = self.config.get_offset_ori()

        # -------------------------------------------------
        # ROI
        # -------------------------------------------------

        self.offset_ori = np.array(
            [
                offset["x_min"],

                offset["y_min"],

                offset["x_max"],

                offset["y_max"],
            ]
        )

        # -------------------------------------------------
        # Working Size
        # -------------------------------------------------

        (
            self.x_min,
            self.y_min,
            self.x_max,
            self.y_max,
        ) = self.offset_ori

        self.work_w = int(self.x_max - self.x_min)
        self.work_h = int(self.y_max - self.y_min)

        log.debug(
            f"[DemuraCore] "
            f"Config loaded: "
            f"{self.yaml_path}"
        )

    def load_lut(self):
        if not self.lut_path.exists():

            raise FileNotFoundError(
                f"Demura LUT not found: "
                f"{self.lut_path}"
            )

        self.lut_bgr = self._read_lut(self.lut_path.read_bytes())

        log.debug(
            f"[DemuraCore] "
            f"LUT loaded: "
            f"{self.lut_path}"
        )

        log.debug(
            f"[DemuraCore] "
            f"LUT shape: "
            f"{self.lut_bgr.shape}"
        )

    @staticmethod
    def _read_lut(raw):
        if not 0 < len(raw) <= DEMURA_LUT_MAX_BYTES:
            raise ValueError('LUT must be between 1 byte and 16 MiB')
        stream = io.BytesIO(raw)
        lut = np.load(stream, allow_pickle=False)
        if not isinstance(lut, np.ndarray):
            if hasattr(lut, 'close'):
                lut.close()
            raise ValueError('LUT must be a .npy array')
        if stream.tell() != len(raw):
            raise ValueError('Unexpected trailing LUT data')
        if lut.ndim != 3 or lut.shape[2] != 3 or min(lut.shape) <= 0:
            raise ValueError('BGR LUT must have shape (H, W, 3)')
        if lut.dtype.kind not in 'uif' or not np.isfinite(lut).all():
            raise ValueError('LUT must contain finite real numbers')
        with np.errstate(over='ignore'):
            lut = lut.astype(np.float32)
        if not np.isfinite(lut).all():
            raise ValueError('LUT values exceed float32 range')
        return lut

    def _write_lut(self, raw):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.lut_path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.lut_path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    # =====================================================
    # Internal: gain generation / NumPy processing
    # =====================================================

    def setup_roi_gain(self):
        # -------------------------------------------------
        # Resize LUT
        # -------------------------------------------------

        self.gain_bgr = cv2.resize(
            self.lut_bgr,
            (
                int(self.work_w),
                int(self.work_h),
            ),
            interpolation=cv2.INTER_CUBIC,
        ).astype(np.float32)

        # -------------------------------------------------
        # Gain Safety Range
        # -------------------------------------------------

        np.clip(
            self.gain_bgr,
            0.1,
            10.0,
            out=self.gain_bgr,
        )

        # -------------------------------------------------
        # ROI Extension
        # -------------------------------------------------

        ext_top = min(
            int(self.extend_top),
            int(self.y_min),
        )

        ext_bottom = min(
            int(self.extend_bottom),
            self.frame_height
            - int(self.y_max),
        )

        ext_left = min(
            int(self.extend_left),
            int(self.x_min),
        )

        ext_right = min(
            int(self.extend_right),
            self.frame_width
            - int(self.x_max),
        )

        # -------------------------------------------------
        # Extend Gain Map
        #
        # Copy edge Gain outward.
        # -------------------------------------------------

        self.gain_bgr = cv2.copyMakeBorder(
            self.gain_bgr,

            ext_top,
            ext_bottom,
            ext_left,
            ext_right,

            cv2.BORDER_REPLICATE,
        )

        # -------------------------------------------------
        # Update Runtime ROI
        # -------------------------------------------------

        self.x_min = (
            int(self.x_min)
            - ext_left
        )

        self.x_max = (
            int(self.x_max)
            + ext_right
        )

        self.y_min = (
            int(self.y_min)
            - ext_top
        )

        self.y_max = (
            int(self.y_max)
            + ext_bottom
        )

        self.work_w = (
            self.x_max
            - self.x_min
        )

        self.work_h = (
            self.y_max
            - self.y_min
        )

        # -------------------------------------------------
        # Validate
        # -------------------------------------------------

        expected_shape = (
            self.work_h,
            self.work_w,
            3,
        )

        if (
            self.gain_bgr.shape
            != expected_shape
        ):

            raise ValueError(
                "[DemuraCore] "
                "Gain / ROI size mismatch: "
                f"Gain={self.gain_bgr.shape}, "
                f"Expected={expected_shape}"
            )

        log.debug(
            "[DemuraCore] "
            "ROI/Gain setup complete"
        )

    def generate_q8_gain(self):
        # -------------------------------------------------
        # Float -> Q8
        #
        # Gain 1.0 -> 256
        # Gain 1.5 -> 384
        # -------------------------------------------------

        self.gain_q8 = np.clip(
            self.gain_bgr * 256.0,
            0,
            65535,
        ).astype(np.uint16)

        # -------------------------------------------------
        # Contiguous Memory
        # -------------------------------------------------

        self.gain_q8 = (
            np.ascontiguousarray(
                self.gain_q8,
                dtype=np.uint16,
            )
        )

        # -------------------------------------------------
        # Validate Shape
        # -------------------------------------------------

        expected_shape = (
            self.work_h,
            self.work_w,
            3,
        )

        if (
            self.gain_q8.shape
            != expected_shape
        ):

            raise ValueError(
                "[DemuraCore] "
                "Q8 Gain shape mismatch: "
                f"{self.gain_q8.shape}, "
                f"Expected={expected_shape}"
            )

        # -------------------------------------------------
        # Export
        # -------------------------------------------------

        self.gain_q8.tofile(self.gain_q8_path)

        # -------------------------------------------------
        # Validate File Size
        # -------------------------------------------------

        expected_bytes = (
            self.work_w
            * self.work_h
            * 3
            * np.dtype(np.uint16).itemsize
        )

        actual_bytes = (
            self.gain_q8_path
            .stat()
            .st_size
        )

        if (
            actual_bytes
            != expected_bytes
        ):

            raise RuntimeError(
                "[DemuraCore] "
                "Q8 Gain file size mismatch: "
                f"expected={expected_bytes}, "
                f"actual={actual_bytes}"
            )

        log.debug(
            f"[DemuraCore] "
            f"Q8 Gain generated: "
            f"{self.gain_q8.shape}"
        )

        log.debug(
            f"[DemuraCore] "
            f"Q8 Gain exported: "
            f"{self.gain_q8_path}"
        )

        log.debug(
            f"[DemuraCore] "
            f"Q8 Gain bytes: "
            f"{actual_bytes}"
        )

    def _process_numpy(self, frame_bgr):
        roi = frame_bgr[
            self.y_min:self.y_max,
            self.x_min:self.x_max,
        ]

        roi_f = roi.astype(np.float32)

        np.multiply(
            roi_f,
            self.gain_bgr,
            out=roi_f,
        )

        np.clip(
            roi_f,
            0.0,
            255.0,
            out=roi_f,
        )

        roi[:] = roi_f.astype(np.uint8)

        return frame_bgr
