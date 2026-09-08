import os
import platform
import subprocess
from pathlib import Path

import cv2
import numpy as np
import yaml

from global_def import *
from demura.demura_config import *

class DemuraCore:

    WIDTH = 640
    HEIGHT = 480

    # =====================================================
    # Constructor
    # =====================================================

    def __init__(
        self,
        yaml_name=None,
        lut_name=None,
        enabled=None,
    ):

        # -------------------------------------------------
        # Global Config
        # -------------------------------------------------

        if yaml_name is None:
            yaml_name = DEMURA_YAML_NAME

        if lut_name is None:
            lut_name = DEMURA_LUT_NAME

        if enabled is None:
            enabled = DEMURA_ENABLED

        # -------------------------------------------------
        # Path
        # -------------------------------------------------

        self.base_dir = Path(__file__).resolve().parent

        self.yaml_path = (
            self.base_dir / yaml_name
        )

        self.lut_path = (
            self.base_dir / lut_name
        )

        self.transform_src = (
            self.base_dir / "demura_transform.c"
        )

        self.neon_src = (
            self.base_dir / "demura_neon.c"
        )

        # -------------------------------------------------
        # Runtime Path
        # -------------------------------------------------

        self.runtime_dir = Path(
            DEMURA_RUNTIME_DIR
        )

        self.runtime_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.gst_plugin_path = (
            self.runtime_dir / "libgstdemura.so"
        )

        self.gain_q8_path = (
            self.runtime_dir / "gain_q8.bin"
        )

        # -------------------------------------------------
        # Platform
        # -------------------------------------------------

        self.is_x86 = (
            platform.machine() == "x86_64"
        )

        # ARM  : NEON
        # x86  : Generic C
        self.use_neon = (
            not self.is_x86
        )

        # Both ARM and x86 use GStreamer Plugin
        self.use_gst_plugin = True

        # -------------------------------------------------
        # Runtime State
        # -------------------------------------------------

        self.enabled = bool(
            enabled
        )

        self.initialized = False

        # -------------------------------------------------
        # ROI Extension
        #
        # Controlled by global_def.py
        # -------------------------------------------------

        self.extend_top = (
            DEMURA_EXTEND_TOP
        )

        self.extend_bottom = (
            DEMURA_EXTEND_BOTTOM
        )

        self.extend_left = (
            DEMURA_EXTEND_LEFT
        )

        self.extend_right = (
            DEMURA_EXTEND_RIGHT
        )

        # -------------------------------------------------
        # Calibration Data
        # -------------------------------------------------

        self.offset_ori = None
        self.scale_size = None

        self.x_min = 0
        self.y_min = 0
        self.x_max = 0
        self.y_max = 0

        self.work_w = 0
        self.work_h = 0

        self.lut_bgr = None
        self.gain_bgr = None
        self.gain_q8 = None

    # =====================================================
    # Initialize
    # =====================================================

    def initialize(self):

        log.debug(
            "=== DemuraCore Initialize ==="
        )

        # -------------------------------------------------
        # Build Native GStreamer Plugin
        # -------------------------------------------------

        if self.use_gst_plugin:

            self.build_gst_plugin()

        # -------------------------------------------------
        # Load Calibration
        # -------------------------------------------------

        self.load_config()

        self.load_lut()

        self.setup_roi_gain()

        # -------------------------------------------------
        # Generate Q8 Gain
        # -------------------------------------------------

        if self.use_gst_plugin:

            self.generate_q8_gain()

        # -------------------------------------------------
        # Done
        # -------------------------------------------------

        self.initialized = True

        self.print_status()

        return True

    # =====================================================
    # Build GStreamer Plugin
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

            raise RuntimeError(
                "pkg-config not found."
            )

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
                log.debug(
                    result.stdout
                )

        except FileNotFoundError:

            raise RuntimeError(
                "gcc not found."
            )

        except subprocess.CalledProcessError as e:

            log.error(
                "[DemuraCore] "
                "GStreamer Demura Plugin build failed"
            )

            if e.stdout:
                log.error(
                    e.stdout
                )

            if e.stderr:
                log.error(
                    e.stderr
                )

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
    # Load YAML Config
    # =====================================================

    def load_config(self):

        if not self.yaml_path.exists():

            raise FileNotFoundError(
                f"Demura YAML not found: "
                f"{self.yaml_path}"
            )

        with open(
            self.yaml_path,
            "r",
        ) as f:

            data = yaml.safe_load(
                f
            )

        # -------------------------------------------------
        # ROI
        # -------------------------------------------------

        self.offset_ori = np.array(
            [
                data[
                    "offset_ori"
                ]["x_min"],

                data[
                    "offset_ori"
                ]["y_min"],

                data[
                    "offset_ori"
                ]["x_max"],

                data[
                    "offset_ori"
                ]["y_max"],
            ]
        )

        # -------------------------------------------------
        # Working Size
        # -------------------------------------------------

        self.scale_size = np.array(
            [
                data[
                    "scale_size"
                ]["width"],

                data[
                    "scale_size"
                ]["height"],
            ]
        )

        (
            self.x_min,
            self.y_min,
            self.x_max,
            self.y_max,
        ) = self.offset_ori

        (
            self.work_w,
            self.work_h,
        ) = self.scale_size

        log.debug(
            f"[DemuraCore] "
            f"Config loaded: "
            f"{self.yaml_path}"
        )

    # =====================================================
    # Load LUT
    # =====================================================

    def load_lut(self):

        if not self.lut_path.exists():

            raise FileNotFoundError(
                f"Demura LUT not found: "
                f"{self.lut_path}"
            )

        self.lut_bgr = np.load(
            self.lut_path
        )

        if (
            self.lut_bgr.ndim != 3
            or
            self.lut_bgr.shape[2] != 3
        ):

            raise ValueError(
                "BGR LUT must have shape "
                "(H, W, 3), "
                f"got {self.lut_bgr.shape}"
            )

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

    # =====================================================
    # Setup ROI / Gain
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
        ).astype(
            np.float32
        )

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
            self.HEIGHT
            - int(self.y_max),
        )

        ext_left = min(
            int(self.extend_left),
            int(self.x_min),
        )

        ext_right = min(
            int(self.extend_right),
            self.WIDTH
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

    # =====================================================
    # Generate Q8 Gain
    # =====================================================

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
        ).astype(
            np.uint16
        )

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

        self.gain_q8.tofile(
            self.gain_q8_path
        )

        # -------------------------------------------------
        # Validate File Size
        # -------------------------------------------------

        expected_bytes = (
            self.work_w
            * self.work_h
            * 3
            * np.dtype(
                np.uint16
            ).itemsize
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

    # =====================================================
    # Enable / Disable
    # =====================================================

    def enable(self):

        self.enabled = True

        log.debug(
            "[DemuraCore] Enabled"
        )

    def disable(self):

        self.enabled = False

        log.debug(
            "[DemuraCore] Disabled"
        )

    def set_enabled(
        self,
        enabled: bool,
    ):

        self.enabled = bool(
            enabled
        )

        log.debug(
            f"[DemuraCore] "
            f"Enabled = {self.enabled}"
        )

    def is_enabled(self):

        return self.enabled

    # =====================================================
    # GStreamer Properties
    # =====================================================

    def get_gst_properties(self):

        if not self.initialized:

            raise RuntimeError(
                "DemuraCore is not initialized"
            )

        return {

            "enabled":
                bool(
                    self.enabled
                ),

            "x-min":
                int(
                    self.x_min
                ),

            "y-min":
                int(
                    self.y_min
                ),

            "x-max":
                int(
                    self.x_max
                ),

            "y-max":
                int(
                    self.y_max
                ),

            "gain-file":
                str(
                    self.gain_q8_path
                ),
        }

    # =====================================================
    # Offline Frame Processing
    # =====================================================

    def process_frame(
        self,
        frame_bgr,
    ):

        if not self.initialized:

            raise RuntimeError(
                "DemuraCore is not initialized"
            )

        if not self.enabled:

            return frame_bgr

        if frame_bgr is None:

            return None

        if frame_bgr.dtype != np.uint8:

            raise ValueError(
                "frame_bgr must be uint8"
            )

        if (
            frame_bgr.ndim != 3
            or
            frame_bgr.shape[2] != 3
        ):

            raise ValueError(
                "frame_bgr must be BGR HxWx3"
            )

        # -------------------------------------------------
        # ARM streaming uses native GStreamer plugin.
        # -------------------------------------------------

        if self.use_neon:

            return frame_bgr

        # -------------------------------------------------
        # x86 offline fallback
        # -------------------------------------------------

        return self._process_numpy(
            frame_bgr
        )

    # =====================================================
    # NumPy Fallback
    # =====================================================

    def _process_numpy(
        self,
        frame_bgr,
    ):

        roi = frame_bgr[
            self.y_min:self.y_max,
            self.x_min:self.x_max,
        ]

        roi_f = roi.astype(
            np.float32
        )

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

        roi[:] = roi_f.astype(
            np.uint8
        )

        return frame_bgr

    # =====================================================
    # Status
    # =====================================================

    def print_status(self):

        log.debug(
            "================================"
        )

        log.debug(
            "       DemuraCore Status"
        )

        log.debug(
            "================================"
        )

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

            log.debug(
                "Processing     : ARM NEON"
            )

        else:

            log.debug(
                "Processing     : Generic C"
            )

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

        log.debug(
            "================================"
        )