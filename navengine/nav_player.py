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

        # Resolution Settings
        self.nav_window_width = 640
        self.nav_window_height = 480

    # ---------------------------------------------------------
    # External Engine and Media Control
    # ---------------------------------------------------------

    def set_media_engine(self, media_engine):
        """Inject external media engine instance"""
        self.media_engine = media_engine

    def _stop_media_if_running(self):
        """Stop background media playback to release hardware decoding resources before starting navigation"""
        try:
            if self.media_engine:
                print("[NAV] Background media detected, stopping to release resources...")
                self.media_engine.playlist_stop()
        except Exception as e:
            print(f"[NAV] Failed to stop media: {e}")

    # ---------------------------------------------------------
    # Core Pipeline and UI Bin Construction (Seamless Switching)
    # ---------------------------------------------------------

    def _create_overlay_bin(self):
        """Build UI Bin, detecting and using i.MX93 PXP hardware acceleration if available"""
        bin = Gst.Bin.new("nav-ui-bin")

        # 1. Select conversion element based on architecture (x86 vs i.MX93)
        if self.is_x86:
            vconv = Gst.ElementFactory.make("videoconvert", "bin_vconv")
            vscale = Gst.ElementFactory.make("videoscale", "bin_vscale")
        else:
            # i.MX93: Force PXP 2D engine for hardware conversion and scaling
            vconv = Gst.ElementFactory.make("imxpxpvideoconvert", "bin_vconv")
            if not vconv:
                vconv = Gst.ElementFactory.make("videoconvert", "bin_vconv")
            vscale = Gst.ElementFactory.make("videoscale", "bin_vscale")

        caps_filter = Gst.ElementFactory.make("capsfilter", "bin_caps")
        caps = Gst.Caps.from_string(
            f"video/x-raw,width={self.nav_window_width},height={self.nav_window_height},pixel-aspect-ratio=1/1"
        )
        caps_filter.set_property("caps", caps)

        # 2. Create all overlay elements (Link order: Image -> Map -> Text A -> Text B...)
        self.map_overlay = Gst.ElementFactory.make("gdkpixbufoverlay", "nav_map")
        self.road_overlay = Gst.ElementFactory.make("textoverlay", "nav_road")
        self.hint_overlay = Gst.ElementFactory.make("textoverlay", "nav_hint")
        self.dist_value_overlay = Gst.ElementFactory.make("textoverlay", "nav_dist_val")
        self.dist_unit_overlay = Gst.ElementFactory.make("textoverlay", "nav_dist_unit")

        # 3. Add to Bin and link
        elements = [vconv, vscale, caps_filter, self.map_overlay, self.road_overlay,
                    self.hint_overlay, self.dist_value_overlay, self.dist_unit_overlay]

        for el in elements:
            if not el: raise RuntimeError(f"Failed to create element")
            bin.add(el)

        # Linking path
        vconv.link(vscale)
        vscale.link(caps_filter)
        caps_filter.link(self.map_overlay)
        self.map_overlay.link(self.road_overlay)
        self.road_overlay.link(self.hint_overlay)
        self.hint_overlay.link(self.dist_value_overlay)
        self.dist_value_overlay.link(self.dist_unit_overlay)

        # 4. Create Ghost Pads (Public interfaces)
        sink_pad = Gst.GhostPad.new("sink", vconv.get_static_pad("sink"))
        src_pad = Gst.GhostPad.new("src", self.dist_unit_overlay.get_static_pad("src"))
        bin.add_pad(sink_pad)
        bin.add_pad(src_pad)

        return bin

    def _build_pipeline(self, video_uri):
        """Initialize playbin3 player"""
        self.pipeline = Gst.ElementFactory.make("playbin3", "nav_pipeline")

        # Attach custom UI Bin to video-filter to keep UI independent of video swaps
        self.pipeline.set_property("video-filter", self._create_overlay_bin())

        # Select Sink based on platform
        sink_name = "autovideosink" if self.is_x86 else "waylandsink"
        video_sink = Gst.ElementFactory.make(sink_name, "video_sink")
        self.pipeline.set_property("video-sink", video_sink)

        # Set URI
        self.pipeline.set_property("uri", video_uri)
        self.current_video_uri = video_uri

        # Message monitoring
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self._on_message)

        self._setup_overlay_styles()

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
        """Execute smooth transition while keeping the window alive"""
        if self.current_video_uri == video_uri:
            return

        log.info(f"[NAV] Switching video to: {video_uri}")

        # Core optimization: Don't go back to READY. Use Flush Seek with URI switch.
        # This keeps the Sink (window) open and holding the last frame until the new video arrives.
        try:
            # 1. Set new URI
            self.pipeline.set_property("uri", video_uri)

            # 2. Trigger a Flush Seek if playbin3 supports it
            # Clears old frame remnants in buffer and loads the new URI immediately
            self.pipeline.seek_simple(
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                0
            )

            self.current_video_uri = video_uri
        except Exception as e:
            log.error(f"[NAV] Failed to switch video: {e}")

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
            if Image is None: raise RuntimeError("Pillow Required")
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
            out = subprocess.check_output(["gdk-pixbuf-query-loaders"], stderr=subprocess.DEVNULL).decode()
            return "webp" in out.lower()
        except:
            return False

    # ---------------------------------------------------------
    # Messages and Resource Cleanup
    # ---------------------------------------------------------

    def _on_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            self.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, 0)
        elif t == Gst.MessageType.ERROR:
            err, dbg = message.parse_error()
            print(f"[NAV] Error: {err}")
            self.stop()

    def stop(self):
        self.nav_active = False
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
            self.bus = None

    def is_running(self):
        return self.pipeline is not None

