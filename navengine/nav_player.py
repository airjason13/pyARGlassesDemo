import io
import os
import platform
import subprocess
import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst

from navengine.nav_def import *
from global_def import *

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
        self.src = None
        self.decodebin = None
        self.video_convert = None
        self.video_scale = None
        self.caps_filter = None
        self.video_sink = None

        self.map_overlay = None
        self.current_map_image_path = None
        self.nav_tmp_dir = "/tmp"
        self.webp_supported = self._system_support_webp()

        self.road_overlay = None
        self.hint_overlay = None
        self.dist_value_overlay = None
        self.dist_unit_overlay = None

        self.direction = None
        self.road_name = ""
        self.distance_m = 0
        self.current_video_path = None

        self.fixed_window_size = True
        self.nav_window_width = 640
        self.nav_window_height = 480

        self.bus = None

        log.info(f"[NAV] gdk-pixbuf webp support: {self.webp_supported}")

    def set_media_engine(self, media_engine):
        self.media_engine = media_engine

    def _stop_media_if_running(self):
        try:
            if self.media_engine:
                log.info("[NAV] stop media (playlist) before nav playback")
                self.media_engine.playlist_stop()
        except Exception as e:
            log.error(f"[NAV] failed to stop media: {e}")

    def _get_video_sink_name(self):
        if platform.machine() == "x86_64":
            return "autovideosink"
        return "waylandsink"

    def _format_distance(self, distance_m):
        try:
            distance_m = int(distance_m)
        except Exception:
            return "", ""

        if distance_m >= 1000:
            return f"{distance_m / 1000:.1f}", "km"
        return str(distance_m), "m"

    def _get_hint_text(self, direction: str) -> str:
        return NAV_HINT_TEXT_MAP.get(direction, "")

    def _setup_overlays(self):
        self.road_overlay.set_property("text", "")
        self.road_overlay.set_property("font-desc", "Sans Bold 24")
        self.road_overlay.set_property("color", 0xFF0000FF)
        self.road_overlay.set_property("halignment", "center")
        self.road_overlay.set_property("valignment", "top")
        self.road_overlay.set_property("shaded-background", False)

        self.hint_overlay.set_property("text", "")
        self.hint_overlay.set_property("font-desc", "Sans Bold 32")
        self.hint_overlay.set_property("color", 0xFF00FF00)
        self.hint_overlay.set_property("halignment", "center")
        self.hint_overlay.set_property("valignment", "position")
        self.hint_overlay.set_property("ypos", 0.22)
        self.hint_overlay.set_property("shaded-background", False)

        self.dist_value_overlay.set_property("text", "")
        self.dist_value_overlay.set_property("font-desc", "Sans Bold 72")
        self.dist_value_overlay.set_property("color", 0xFFFFFFFF)
        self.dist_value_overlay.set_property("halignment", "position")
        self.dist_value_overlay.set_property("valignment", "position")
        self.dist_value_overlay.set_property("xpos", 0.18)
        self.dist_value_overlay.set_property("ypos", 0.68)
        self.dist_value_overlay.set_property("shaded-background", False)

        self.dist_unit_overlay.set_property("text", "")
        self.dist_unit_overlay.set_property("font-desc", "Sans Bold 24")
        self.dist_unit_overlay.set_property("color", 0xFFFFFFFF)
        self.dist_unit_overlay.set_property("halignment", "position")
        self.dist_unit_overlay.set_property("valignment", "position")
        self.dist_unit_overlay.set_property("xpos", 0.18)
        self.dist_unit_overlay.set_property("ypos", 0.78)
        self.dist_unit_overlay.set_property("shaded-background", False)

        self._refresh_text_only()

    def _refresh_text_only(self):
        dist_value, dist_unit = self._format_distance(self.distance_m)
        hint_text = self._get_hint_text(self.direction)

        if self.road_overlay:
            self.road_overlay.set_property("text", self.road_name)

        if self.hint_overlay:
            self.hint_overlay.set_property("text", hint_text)

        if self.dist_value_overlay:
            self.dist_value_overlay.set_property("text", dist_value)

        if self.dist_unit_overlay:
            self.dist_unit_overlay.set_property("text", dist_unit)

    def _on_decode_pad_added(self, decodebin, pad):
        if not self.video_convert:
            return

        sink_pad = self.video_convert.get_static_pad("sink")
        if sink_pad and not sink_pad.is_linked():
            ret = pad.link(sink_pad)
            if ret != Gst.PadLinkReturn.OK:
                log.error(f"[NAV] decodebin pad link failed: {ret}")

    def _connect_bus(self):
        if not self.pipeline:
            return

        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self._on_message)

    def _build_pipeline(self, video_path):
        self.pipeline = Gst.Pipeline.new("nav-pipeline")

        self.src = Gst.ElementFactory.make("filesrc", "src")
        self.decodebin = Gst.ElementFactory.make("decodebin", "decode")
        self.video_convert = Gst.ElementFactory.make("videoconvert", "vconv")
        self.video_scale = Gst.ElementFactory.make("videoscale", "vscale")
        self.caps_filter = Gst.ElementFactory.make("capsfilter", "caps")

        self.map_overlay = Gst.ElementFactory.make("gdkpixbufoverlay", "map_overlay")

        self.road_overlay = Gst.ElementFactory.make("textoverlay", "road")
        self.hint_overlay = Gst.ElementFactory.make("textoverlay", "hint")
        self.dist_value_overlay = Gst.ElementFactory.make("textoverlay", "dist_value")
        self.dist_unit_overlay = Gst.ElementFactory.make("textoverlay", "dist_unit")

        self.video_sink = Gst.ElementFactory.make(self._get_video_sink_name(), "video_sink")

        if not all([
            self.pipeline,
            self.src,
            self.decodebin,
            self.video_convert,
            self.video_scale,
            self.caps_filter,
            self.map_overlay,
            self.road_overlay,
            self.hint_overlay,
            self.dist_value_overlay,
            self.dist_unit_overlay,
            self.video_sink,
        ]):
            raise RuntimeError("Failed to create GStreamer elements")

        self.src.set_property("location", video_path)

        if self.fixed_window_size:
            caps = Gst.Caps.from_string(
                f"video/x-raw,width={self.nav_window_width},height={self.nav_window_height},pixel-aspect-ratio=1/1"
            )
            self.caps_filter.set_property("caps", caps)

        # Map layer Positon
        self.map_overlay.set_property("alpha", 0.0)
        self.map_overlay.set_property("offset-x", 430)
        self.map_overlay.set_property("offset-y", 220)

        self.pipeline.add(self.src)
        self.pipeline.add(self.decodebin)
        self.pipeline.add(self.video_convert)
        self.pipeline.add(self.video_scale)
        self.pipeline.add(self.caps_filter)
        self.pipeline.add(self.map_overlay)
        self.pipeline.add(self.road_overlay)
        self.pipeline.add(self.hint_overlay)
        self.pipeline.add(self.dist_value_overlay)
        self.pipeline.add(self.dist_unit_overlay)
        self.pipeline.add(self.video_sink)

        if not self.src.link(self.decodebin):
            raise RuntimeError("Failed to link filesrc -> decodebin")

        self.decodebin.connect("pad-added", self._on_decode_pad_added)

        if not self.video_convert.link(self.video_scale):
            raise RuntimeError("Failed to link videoconvert -> videoscale")

        if not self.video_scale.link(self.caps_filter):
            raise RuntimeError("Failed to link videoscale -> capsfilter")

        if not self.caps_filter.link(self.map_overlay):
            raise RuntimeError("Failed to link capsfilter -> map_overlay")

        if not self.map_overlay.link(self.road_overlay):
            raise RuntimeError("Failed to link map_overlay -> road_overlay")

        if not self.road_overlay.link(self.hint_overlay):
            raise RuntimeError("Failed to link road_overlay -> hint_overlay")

        if not self.hint_overlay.link(self.dist_value_overlay):
            raise RuntimeError("Failed to link hint_overlay -> dist_value_overlay")

        if not self.dist_value_overlay.link(self.dist_unit_overlay):
            raise RuntimeError("Failed to link dist_value_overlay -> dist_unit_overlay")

        if not self.dist_unit_overlay.link(self.video_sink):
            raise RuntimeError("Failed to link dist_unit_overlay -> video_sink")

        self._setup_overlays()
        self.current_video_path = video_path
        self._connect_bus()

        if self.current_map_image_path:
            try:
                self.map_overlay.set_property("location", self.current_map_image_path)
            except Exception as e:
                log.error(f"[NAV] apply existing map overlay failed: {e}")

    def _switch_video(self, video_path):
        if not self.pipeline or not self.src:
            return

        if self.current_video_path == video_path:
            log.info(f"[NAV] same video, keep playing: {video_path}")
            return

        log.info(f"[NAV] switch video (READY swap): {self.current_video_path} -> {video_path}")

        try:
            # 1. Move to READY so filesrc can close the current file.
            self.pipeline.set_state(Gst.State.READY)
            self.pipeline.get_state(Gst.CLOCK_TIME_NONE)

            # 2. Change to the new video file
            self.src.set_property("location", video_path)
            self.current_video_path = video_path

            # 3. Start playing the new video
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                log.error(f"[NAV] failed to PLAYING: {video_path}")

        except Exception as e:
            log.error(f"[NAV] switch video error: {e}")

    def _on_message(self, bus, message):
        msg_type = message.type

        if msg_type == Gst.MessageType.EOS:
            # log.info(f"[NAV] EOS -> loop current video, direction={self.direction}")
            if self.pipeline:
                self.pipeline.seek_simple(
                    Gst.Format.TIME,
                    Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                    0
                )

        elif msg_type == Gst.MessageType.ERROR:
            err, dbg = message.parse_error()
            log.error(f"[NAV] ERROR: {err}, dbg={dbg}")
            self._stop_pipeline()

    def set_nav_state(self, direction: str, road_name: str, distance_m: int):
        self._stop_media_if_running()

        if direction not in SUPPORTED_NAV_DIRECTIONS:
            raise ValueError(f"Invalid direction: {direction}")

        self.direction = direction
        self.road_name = str(road_name)
        self.distance_m = int(distance_m)

        log.info(
            f"[NAV] set_nav_state: direction={self.direction}, "
            f"road={self.road_name}, dist={self.distance_m}"
        )

        video_name = ASSET_MAP.get(direction)
        if not video_name:
            raise ValueError(f"No asset mapped for direction: {direction}")

        video_path = os.path.join(self.asset_dir, video_name)

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if self.pipeline is None:
            self._build_pipeline(video_path)
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError(f"Failed to start pipeline with: {video_path}")
        else:
            self._switch_video(video_path)

        self._refresh_text_only()

    def set_nav_map_image(self, file_name: str = "nav_map_image", hex_str: str = ""):
        """
        Convert WebP HEX data to /tmp/<name>.webp.
        If gdk-pixbuf does not support WebP, convert it to PNG.
        If hex_str is empty, hide the map layer.
        """
        file_name = (file_name or "").strip()
        hex_str = (hex_str or "").strip()

        if not hex_str:
            log.info("[NAV] clear NAV_MAP_IMAGE")
            self.current_map_image_path = None

            if self.map_overlay:
                try:
                    self.map_overlay.set_property("alpha", 0.0)
                except Exception as e:
                    log.error(f"[NAV] clear map overlay failed: {e}")
            return

        try:
            out_path = self._save_webp_or_convert_to_png(file_name, hex_str)
            self.current_map_image_path = out_path
            log.info(f"[NAV] NAV_MAP_IMAGE updated: {out_path}")

            if self.map_overlay:
                try:
                    # Hide → Output Map → Show
                    self.map_overlay.set_property("alpha", 0.0)
                    self.map_overlay.set_property("location", out_path)
                    self.map_overlay.set_property("alpha", 1.0)
                except Exception as e:
                    log.error(f"[NAV] apply map overlay failed: {e}")

        except Exception as e:
            log.error(f"[NAV] set_nav_map_image error: {e}")

    def _system_support_webp(self) -> bool:
        try:
            out = subprocess.check_output(
                ["gdk-pixbuf-query-loaders"],
                stderr=subprocess.DEVNULL
            ).decode(errors="ignore")
            return "webp" in out.lower()
        except Exception as e:
            log.warning(f"[NAV] query webp loader failed: {e}")
            return False

    def _fast_validate_webp(self, hex_str: str) -> bytes:
        hex_str = hex_str.strip().replace("0x", "").replace(" ", "").replace("\n", "")

        if not hex_str:
            raise ValueError("empty hex")

        if len(hex_str) % 2 != 0:
            raise ValueError("invalid hex length")

        # Max Image 256kB 
        if len(hex_str) > 256 * 1024 * 2:
            raise ValueError("hex too large")

        try:
            raw = bytes.fromhex(hex_str)
        except Exception:
            raise ValueError("invalid hex")

        if len(raw) < 12 or raw[:4] != b"RIFF" or raw[8:12] != b"WEBP":
            raise ValueError("not webp")

        return raw

    def _sanitize_map_filename(self, file_name: str) -> str:
        name = os.path.basename(file_name.strip())
        if not name:
            raise ValueError("empty file name")

        name_no_ext, _ext = os.path.splitext(name)
        if not name_no_ext:
            raise ValueError("invalid file name")

        return name_no_ext

    def _save_webp_direct(self, file_name: str, raw: bytes) -> str:
        base_name = self._sanitize_map_filename(file_name)
        out_path = os.path.join(self.nav_tmp_dir, f"{base_name}.webp")

        with open(out_path, "wb") as f:
            f.write(raw)

        return out_path

    def _save_png_from_webp(self, file_name: str, raw: bytes) -> str:
        if Image is None:
            raise RuntimeError("Pillow is required for webp->png conversion")

        base_name = self._sanitize_map_filename(file_name)
        out_path = os.path.join(self.nav_tmp_dir, f"{base_name}.png")

        img = Image.open(io.BytesIO(raw))
        img.save(out_path, "PNG")

        return out_path

    def _save_webp_or_convert_to_png(self, file_name: str, hex_str: str) -> str:
        os.makedirs(self.nav_tmp_dir, exist_ok=True)

        raw = self._fast_validate_webp(hex_str)

        if self.webp_supported: # i.MX93 supported gdkpixbuf decode
             log.debug("supported web")
             return self._save_webp_direct(file_name, raw)

        log.debug("convert to png")
        return self._save_png_from_webp(file_name, raw)

    def _stop_pipeline(self):
        if self.pipeline:
            try:
                if self.bus:
                    self.bus.remove_signal_watch()
            except Exception:
                pass

            self.pipeline.set_state(Gst.State.NULL)

        self.pipeline = None
        self.src = None
        self.decodebin = None
        self.video_convert = None
        self.video_scale = None
        self.caps_filter = None
        self.video_sink = None
        self.map_overlay = None

        self.road_overlay = None
        self.hint_overlay = None
        self.dist_value_overlay = None
        self.dist_unit_overlay = None

        self.current_video_path = None
        self.bus = None

    def stop(self):
        self._stop_pipeline()

    def is_running(self):
        return self.pipeline is not None
