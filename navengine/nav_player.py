import io
import os
import platform
import subprocess
import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst

from navengine.nav_def import *
from global_def import *
from gi.repository import GLib
import math
try:
    from PIL import Image
except Exception:
    Image = None




class ARNavPlayer:
    def __init__(self):
        Gst.init(None)

        self.asset_dir = NAV_ASSET_URI_PATH
        self.media_engine = None
        self.demura_core = None
        self.demura_filter = None
        self.pipeline = None
        self.bus = None
        self.nav_active = False

        # UI Component References
        self.map_overlay = None
        self.road_overlay = None
        self.hint_overlay = None
        self.dist_value_overlay = None
        self.dist_unit_overlay = None

        self.current_map_image_path = None
        self.nav_tmp_dir = "/tmp"
        self.webp_supported = self._system_support_webp()

        # Navigation State Records
        self.direction = None
        self.road_name = ""
        self.distance_m = 0
        self.current_video_uri = None

        # System Hardware Detection
        self.is_x86 = platform.machine() == "x86_64"

    # ---------------------------------------------------------
    # External Engine and Media Control
    # ---------------------------------------------------------
    def set_demura_core(self, demura_core):
        self.demura_core = demura_core
        log.debug("[ARNavPlayer] DemuraCore attached: %s",
                  self.demura_core is not None)

    def set_media_engine(self, media_engine):
        self.media_engine = media_engine

    def _stop_media_if_running(self):
        try:
            if self.media_engine:
                print("[NAV] Background media detected, stopping to release resources...")
                self.media_engine.playlist_stop()
        except Exception as e:
            print(f"[NAV] Failed to stop media: {e}")

    # ---------------------------------------------------------
    # Demura Plugin
    # ---------------------------------------------------------
    def _scan_demura_plugin(self):
        if self.demura_core is None or not self.demura_core.use_gst_plugin:
            return False

        plugin_dir = str(self.demura_core.runtime_dir)
        result = Gst.Registry.get().scan_path(plugin_dir)

        log.debug("[ARNavPlayer] Scan Demura Plugin: path=%s, result=%s",
                  plugin_dir, result)

        return Gst.ElementFactory.find("demuratransform") is not None

    def _create_demura_filter(self):
        if self.demura_core is not None and self.demura_core.use_gst_plugin:
            self.demura_filter = Gst.ElementFactory.make(
                "demuratransform", "nav_demura_filter"
            )
            if not self.demura_filter:
                raise RuntimeError("Failed to create demuratransform")
        else:
            self.demura_filter = Gst.ElementFactory.make(
                "identity", "nav_demura_filter"
            )

        return self.demura_filter

    def _apply_demura_properties(self):
        if (self.demura_filter is None or
                self.demura_core is None or
                not self.demura_core.use_gst_plugin):
            return

        props = self.demura_core.get_gst_properties()

        for name, value in props.items():
            self.demura_filter.set_property(name, value)

        print("========== NAV DEMURA ==========")
        print("Plugin     : demuratransform")
        print(f"Enabled    : {props.get('enabled')}")
        print(f"ROI        : {props.get('x-min')}, {props.get('y-min')} "
              f"-> {props.get('x-max')}, {props.get('y-max')}")
        print(f"Gain File  : {props.get('gain-file')}")
        print("================================")

        log.debug("[ARNavPlayer] Demura properties applied: %s", props)

    def set_demura_enabled(self, enabled):
        enabled = bool(enabled)

        if self.demura_core:
            self.demura_core.set_enabled(enabled)

        if (self.demura_filter is not None and
                self.demura_core is not None and
                self.demura_core.use_gst_plugin):
            self.demura_filter.set_property("enabled", enabled)

    # ---------------------------------------------------------
    # Core Pipeline and UI Bin Construction
    # ---------------------------------------------------------
    def _create_overlay_bin(self):
        bin = Gst.Bin.new("nav-ui-bin")

        # Video Convert
        if self.is_x86:
            vconv = Gst.ElementFactory.make("videoconvert", "bin_vconv")
            vscale = Gst.ElementFactory.make("videoscale", "bin_vscale")
        else:
            vconv = Gst.ElementFactory.make("imxpxpvideoconvert", "bin_vconv")
            if not vconv:
                vconv = Gst.ElementFactory.make("videoconvert", "bin_vconv")
            vscale = Gst.ElementFactory.make("videoscale", "bin_vscale")

        video_frame_size = self.demura_core.get_video_frame_size() if self.demura_core else {
            "width": 640, "height": 480
        }
        # Force the configured BGR frame size for Demura.
        caps_filter = Gst.ElementFactory.make("capsfilter", "bin_caps")
        caps = Gst.Caps.from_string(
            f"video/x-raw,format=BGR,"
            f"width={video_frame_size['width']},height={video_frame_size['height']},"
            f"pixel-aspect-ratio=1/1"
        )
        caps_filter.set_property("caps", caps)

        # Navigation Overlay
        self.map_overlay = Gst.ElementFactory.make("gdkpixbufoverlay", "nav_map")
        self.road_overlay = Gst.ElementFactory.make("textoverlay", "nav_road")
        self.hint_overlay = Gst.ElementFactory.make("textoverlay", "nav_hint")
        self.dist_value_overlay = Gst.ElementFactory.make("textoverlay", "nav_dist_val")
        self.dist_unit_overlay = Gst.ElementFactory.make("textoverlay", "nav_dist_unit")

        # Demura Plugin
        demura_filter = self._create_demura_filter()
        # Add to Bin and link
        elements = [
            vconv, vscale, caps_filter,
            self.map_overlay, self.road_overlay, self.hint_overlay,
            self.dist_value_overlay, self.dist_unit_overlay,
            demura_filter
        ]

        for el in elements:
            if not el:
                raise RuntimeError("Failed to create pipeline element")
            bin.add(el)

        # Linking path
        vconv.link(vscale)
        vscale.link(caps_filter)
        caps_filter.link(self.map_overlay)
        self.map_overlay.link(self.road_overlay)
        self.road_overlay.link(self.hint_overlay)
        self.hint_overlay.link(self.dist_value_overlay)
        self.dist_value_overlay.link(self.dist_unit_overlay)
        self.dist_unit_overlay.link(demura_filter)

        # Ghost Pads
        sink_pad = Gst.GhostPad.new("sink", vconv.get_static_pad("sink"))
        src_pad = Gst.GhostPad.new("src", demura_filter.get_static_pad("src"))
        bin.add_pad(sink_pad)
        bin.add_pad(src_pad)

        return bin

    def _build_pipeline(self, video_uri):
        """Initialize playbin3 player"""
        # Scan Demura plugin
        self._scan_demura_plugin()

        # Create playbin3
        self.pipeline = Gst.ElementFactory.make("playbin3", "nav_pipeline")

        # i.MX93 / GStreamer 1.24:
        # Enable instant URI switching and avoid extra flush seek.
        if not self.is_x86 and self.pipeline.find_property("instant-uri"):
            self.pipeline.set_property("instant-uri", True)
            log.info("[NAV] instant-uri enabled")

        # Overlay + Demura
        overlay_bin = self._create_overlay_bin()
        self.pipeline.set_property("video-filter", overlay_bin)

        # Apply ROI / Gain / Enable
        self._apply_demura_properties()

        # Video Sink
        sink_name = "autovideosink" if self.is_x86 else "waylandsink"
        video_sink = Gst.ElementFactory.make(sink_name, "video_sink")
        self.pipeline.set_property("video-sink", video_sink)

        # URI
        self.pipeline.set_property("uri", video_uri)
        self.current_video_uri = video_uri

        # Bus
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self._on_message)

        self._setup_overlay_styles()

    # ---------------------------------------------------------
    # Overlay Style
    # ---------------------------------------------------------
    def _setup_overlay_styles(self):
        """Initialize fonts, positions, and colors for all UI layers"""
        # Map
        self.map_overlay.set_property("alpha", 0.0)
        self.map_overlay.set_property("offset-x", 430)
        self.map_overlay.set_property("offset-y", 220)

        # Road Name
        self.road_overlay.set_property("font-desc", "Sans Bold 28")
        self.road_overlay.set_property("color", 0xFFFFFFFF)
        self.road_overlay.set_property("halignment", "center")
        self.road_overlay.set_property("valignment", "top")

        # Direction Hint
        self.hint_overlay.set_property("font-desc", "Sans Bold 20")
        self.hint_overlay.set_property("color", 0xFF00FF00)  # Bright Green
        self.hint_overlay.set_property("halignment", "position")
        self.hint_overlay.set_property("valignment", "position")
        self.hint_overlay.set_property("xpos", 0.20)  # Left aligned with value
        self.hint_overlay.set_property("ypos", 0.5)
        self.hint_overlay.set_property("shaded-background", True)  # Add shadow for better visibility

        # Distance Value
        self.dist_value_overlay.set_property("font-desc", "Sans Bold 72")
        self.dist_value_overlay.set_property("color", 0xFFFFFF00)
        self.dist_value_overlay.set_property("halignment", "position")
        self.dist_value_overlay.set_property("valignment", "position")
        self.dist_value_overlay.set_property("xpos", 0.18)
        self.dist_value_overlay.set_property("ypos", 0.68)

        # Distance Unit
        self.dist_unit_overlay.set_property("font-desc", "Sans Bold 24")
        self.dist_unit_overlay.set_property("color", 0xFFCCCCCC)
        self.dist_unit_overlay.set_property("halignment", "position")
        self.dist_unit_overlay.set_property("valignment", "position")
        self.dist_unit_overlay.set_property("xpos", 0.18)
        self.dist_unit_overlay.set_property("ypos", 0.78)

    # ---------------------------------------------------------
    # State Transition Logic
    # ---------------------------------------------------------

    def set_nav_state(self, direction: str, road_name: str, distance_m: int):
        if not self.nav_active:
            self._stop_media_if_running()
            self.nav_active = True

        self.direction = direction
        self.road_name = str(road_name)
        self.distance_m = int(distance_m)

        video_name = ASSET_MAP.get(direction)
        if not video_name: return

        video_path = os.path.join(self.asset_dir, video_name)
        video_uri = "file://" + os.path.abspath(video_path)

        if self.pipeline is None:
            self._build_pipeline(video_uri)
            self.pipeline.set_state(Gst.State.PLAYING)
        else:
            self._switch_video(video_uri)

        self._refresh_ui_text()

    def _switch_video(self, video_uri):
        if self.current_video_uri == video_uri:
            return

        try:
            if self.is_x86:
                # x86 / GStreamer 1.20
                self.pipeline.set_state(Gst.State.READY)
                self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

                self.pipeline.set_property("uri", video_uri)
                self.pipeline.set_state(Gst.State.PLAYING)

            else:
                # i.MX93 / GStreamer 1.24
                # instant-uri handles source switching.
                self.pipeline.set_property("uri", video_uri)

            self.current_video_uri = video_uri

            log.debug("[NAV] Video switched: %s", video_uri)

        except Exception:
            log.exception("[NAV] Video switch failed")
    def _refresh_ui_text(self):
        dist_val, dist_unit = self._format_distance(self.distance_m)
        hint_text = NAV_HINT_TEXT_MAP.get(self.direction, "")

        if self.distance_m <= 10:
            target_color = 0xFFFF0000  # Red
        elif self.distance_m <= 20:
            target_color = 0xFFFFA500  # Orange
        else:
            target_color = 0xFFFFFF00  # Yellow

        self.hint_overlay.set_property("text", hint_text)
        self.hint_overlay.set_property("font-desc", "Sans Bold 24")
        self.hint_overlay.set_property("color", 0xFF00FF00)
        self.dist_value_overlay.set_property("color", target_color)
        self.dist_value_overlay.set_property("text", dist_val)

        self.road_overlay.set_property("text", self.road_name)
        self.dist_unit_overlay.set_property("text", dist_unit)

    def _format_distance(self, dist_m):
        try:
            dist_m = int(dist_m)
        except:
            return "0", "m"
        if dist_m >= 1000:
            return f"{dist_m / 1000:.1f}", "km"
        return str(dist_m), "m"

    # ---------------------------------------------------------
    # Map Image Processing
    # ---------------------------------------------------------
    def set_nav_map_image(self, file_name: str = "nav_map_image", hex_str: str = ""):
        if not hex_str.strip():
            if self.map_overlay:
                self.map_overlay.set_property("alpha", 0.0)
            return

        try:
            out_path = self._save_webp_or_convert_to_png(file_name, hex_str)
            if self.map_overlay:
                self.map_overlay.set_property("location", out_path)
                self.map_overlay.set_property("alpha", 1.0)
        except Exception as e:
            print(f"[NAV] Map Error: {e}")

    def _save_webp_or_convert_to_png(self, file_name: str, hex_str: str) -> str:
        os.makedirs(self.nav_tmp_dir, exist_ok=True)
        raw = self._fast_validate_webp(hex_str)
        base_name = os.path.basename(file_name).split('.')[0]

        if self.webp_supported:
            out_path = os.path.join(self.nav_tmp_dir, f"{base_name}.webp")
            with open(out_path, "wb") as f:
                f.write(raw)
            return out_path
        else:
            if Image is None:
                raise RuntimeError("Pillow Required")
            out_path = os.path.join(self.nav_tmp_dir, f"{base_name}.png")
            img = Image.open(io.BytesIO(raw))
            img.save(out_path, "PNG")
            return out_path

    def _fast_validate_webp(self, hex_str: str) -> bytes:
        hex_str = hex_str.strip().replace("0x", "").replace(" ", "")
        raw = bytes.fromhex(hex_str)
        if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WEBP":
            raise ValueError("Invalid WebP")
        return raw

    def _system_support_webp(self) -> bool:
        try:
            out = subprocess.check_output(
                ["gdk-pixbuf-query-loaders"],
                stderr=subprocess.DEVNULL
            ).decode()

            return "webp" in out.lower()

        except:
            return False

    # ---------------------------------------------------------
    # Messages and Resource Cleanup
    # ---------------------------------------------------------
    def _on_message(self, bus, message):
        t = message.type

        if t == Gst.MessageType.EOS:
            if not self.pipeline:
                return

            self.pipeline.seek_simple(
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                0
            )

        elif t == Gst.MessageType.ERROR:
            err, dbg = message.parse_error()

            log.error(
                "[NAV][GST] ERROR src=%s error=%s",
                message.src.get_name(),
                err
            )

            if dbg:
                log.debug("[NAV][GST] debug=%s", dbg)

            self.stop()

        elif t == Gst.MessageType.WARNING:
            warn, dbg = message.parse_warning()

            log.warning(
                "[NAV][GST] WARNING src=%s warning=%s",
                message.src.get_name(),
                warn
            )

            if dbg:
                log.debug("[NAV][GST] debug=%s", dbg)

    def stop(self):
        self.nav_active = False
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.bus = None

        self.demura_filter = None
        self.current_video_uri = None

    def is_running(self):
        return self.pipeline is not None
