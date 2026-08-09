"""Whisplay daemon app client — lets JARVIS run as a daemon-managed app.

Implements the whisplay-daemon IPC contract (APP_INTEGRATION.md, protocol
version 1, line-delimited JSON over /tmp/whisplay-daemon.sock):

    register -> subscribe events -> acquire focus -> mmap framebuffer
    -> draw RGB565 status screens -> release focus on exit

With the daemon running, JARVIS appears on the Whisplay desktop (long
press launches it), button events arrive as daemon events, the LED goes
through led.set, and four rapid clicks request exit. Without the daemon,
voice mode falls back to direct WhisplayBoard access.

Stdlib only; PIL is used for status-screen text when available, otherwise
screens are plain status colors.
"""

import json
import mmap
import os
import socket
import threading

from . import config

SOCKET_PATH = config.get("WHISPLAY_DAEMON_SOCKET", "/tmp/whisplay-daemon.sock")
APP_ID = "jarvis-ai"
DISPLAY_NAME = "JARVIS"
ICON = "JV"
LCD_WIDTH = 240
LCD_HEIGHT = 280

# status -> (background RGB, LED RGB) — whisplay chatbot color language
STATUS_STYLE = {
    "idle": ((16, 24, 32), (0, 40, 0)),
    "listening": ((8, 64, 24), (0, 255, 0)),
    "thinking": ((72, 52, 8), (255, 180, 0)),
    "answering": ((10, 30, 80), (0, 80, 255)),
    "error": ((70, 12, 12), (255, 0, 0)),
}


def _send_request(cmd, payload=None, socket_path=SOCKET_PATH, timeout=3.0):
    body = {"version": 1, "cmd": cmd, "payload": payload or {}}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(socket_path)
        client.sendall((json.dumps(body) + "\n").encode("utf-8"))
        line = client.makefile("r").readline().strip()
    if not line:
        raise RuntimeError("empty response from whisplay-daemon")
    response = json.loads(line)
    if not response.get("ok"):
        raise RuntimeError(response.get("error", "daemon request failed"))
    return response


def daemon_available(socket_path=SOCKET_PATH):
    if not os.path.exists(socket_path):
        return False
    try:
        _send_request("health.ping", socket_path=socket_path, timeout=1.5)
        return True
    except Exception:
        return False


def launch_command():
    entry = os.path.join(config.PROJECT_ROOT, "run_jarvis.py")
    return "python3 %s voice" % entry


def register_payload():
    return {
        "app_id": APP_ID,
        "display_name": DISPLAY_NAME,
        "icon": ICON,
        "launch_command": launch_command(),
        "cwd": config.PROJECT_ROOT,
        "exit_gesture": "quad_click",
        "use_daemon_default_log": True,
        "persist": True,
    }


def register_app():
    """One-shot registration so JARVIS appears on the daemon desktop."""
    _send_request("app.register", register_payload())


def persisted_app_file():
    return os.path.expanduser("~/.whisplay-daemon/app/%s.json" % APP_ID)


# ── RGB565 rendering ─────────────────────────────────────────────────
def _rgb565_slow(rgb_bytes):
    out = bytearray(len(rgb_bytes) // 3 * 2)
    j = 0
    for i in range(0, len(rgb_bytes), 3):
        r = rgb_bytes[i]
        g = rgb_bytes[i + 1]
        b = rgb_bytes[i + 2]
        value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        out[j] = value >> 8
        out[j + 1] = value & 0xFF
        j += 2
    return bytes(out)


def image_to_rgb565(image):
    """PIL image -> big-endian RGB565 bytes (the LCD/framebuffer format)."""
    rgb = image.convert("RGB")
    try:
        raw = rgb.tobytes("raw", "BGR;16")  # 565 little-endian, fast path
        swapped = bytearray(len(raw))
        swapped[0::2] = raw[1::2]
        swapped[1::2] = raw[0::2]
        return bytes(swapped)
    except Exception:
        return _rgb565_slow(rgb.tobytes())


def _load_fonts():
    try:
        from PIL import ImageFont
    except ImportError:
        return None, None
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    custom = config.get("CUSTOM_FONT_PATH", "")
    if custom:
        candidates.insert(0, custom)
    for path in candidates:
        if os.path.isfile(path):
            try:
                return (
                    ImageFont.truetype(path, 30),
                    ImageFont.truetype(path, 19),
                )
            except Exception:
                continue
    default = ImageFont.load_default()
    return default, default


def render_status_frame(status, text=""):
    """Render a 240x280 status screen; None if PIL is unavailable."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    bg, _led = STATUS_STYLE.get(status, STATUS_STYLE["idle"])
    image = Image.new("RGB", (LCD_WIDTH, LCD_HEIGHT), bg)
    draw = ImageDraw.Draw(image)
    title_font, body_font = _load_fonts()

    title = status.upper()
    draw.text((16, 18), title, fill=(255, 255, 255), font=title_font)
    draw.line((16, 62, LCD_WIDTH - 16, 62), fill=(255, 255, 255), width=1)

    # simple word wrap for the body text
    y = 78
    max_width = LCD_WIDTH - 32
    words = (text or "").split()
    line = ""
    lines = []
    for word in words:
        candidate = (line + " " + word).strip()
        try:
            width = draw.textlength(candidate, font=body_font)
        except AttributeError:
            width = body_font.getsize(candidate)[0]
        if width <= max_width:
            line = candidate
        else:
            lines.append(line)
            line = word
        if len(lines) >= 8:
            break
    if line and len(lines) < 8:
        lines.append(line)
    for row in lines:
        draw.text((16, y), row, fill=(230, 235, 240), font=body_font)
        y += 24
    return image


class DaemonApp:
    """Foreground-app session with the whisplay daemon.

    Exposes the same surface voice.py uses on a direct WhisplayBoard
    (button_pressed / set_rgb) plus show_status() and exit_requested."""

    def __init__(self, socket_path=SOCKET_PATH):
        self.socket_path = socket_path
        self.exit_requested = threading.Event()
        self._button_down = False
        self._session_token = None
        self._fb = None
        self._fb_file = None
        self._fb_stride = LCD_WIDTH * 2
        self._running = False
        self._thread = None

    # ── lifecycle ────────────────────────────────────────────────
    def start(self, focus_timeout=8.0):
        _send_request("app.register", register_payload(),
                      socket_path=self.socket_path)
        self._running = True
        self._thread = threading.Thread(target=self._event_loop, daemon=True)
        self._thread.start()
        self._acquire_foreground(focus_timeout)

    def _acquire_foreground(self, timeout):
        import time as _time

        deadline = _time.time() + timeout
        last_error = None
        while _time.time() < deadline:
            try:
                response = _send_request(
                    "app.focus.acquire", {"app_id": APP_ID},
                    socket_path=self.socket_path,
                )
                self._session_token = response["payload"]["session_token"]
                fb = _send_request(
                    "framebuffer.acquire",
                    {"app_id": APP_ID, "session_token": self._session_token},
                    socket_path=self.socket_path,
                )["payload"]
                self._attach_framebuffer(
                    fb["buffer_handle"], int(fb.get("stride", self._fb_stride))
                )
                return
            except Exception as err:
                last_error = err
                _time.sleep(0.2)
        raise RuntimeError("could not acquire foreground: %s" % last_error)

    def _attach_framebuffer(self, handle, stride):
        self._detach_framebuffer()
        self._fb_stride = stride
        self._fb_file = open(handle, "r+b")
        self._fb = mmap.mmap(self._fb_file.fileno(), 0)

    def _detach_framebuffer(self):
        if self._fb is not None:
            try:
                self._fb.close()
            except Exception:
                pass
            self._fb = None
        if self._fb_file is not None:
            try:
                self._fb_file.close()
            except Exception:
                pass
            self._fb_file = None

    def release_focus(self):
        if self._session_token:
            try:
                _send_request(
                    "app.focus.release",
                    {"app_id": APP_ID, "session_token": self._session_token},
                    socket_path=self.socket_path,
                )
            except Exception:
                pass
        self._session_token = None
        self._detach_framebuffer()

    def cleanup(self):
        self._running = False
        self.release_focus()

    # ── events ───────────────────────────────────────────────────
    def _event_loop(self):
        import time as _time

        while self._running:
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.connect(self.socket_path)
                    body = {
                        "version": 1,
                        "cmd": "events.subscribe",
                        "payload": {"app_id": APP_ID},
                    }
                    client.sendall((json.dumps(body) + "\n").encode("utf-8"))
                    reader = client.makefile("r")
                    if not reader.readline().strip():
                        raise RuntimeError("subscription ack missing")
                    for line in reader:
                        if not self._running:
                            return
                        line = line.strip()
                        if not line:
                            continue
                        event = json.loads(line).get("event")
                        if event == "button_pressed":
                            self._button_down = True
                        elif event == "button_released":
                            self._button_down = False
                        elif event == "app_exit_requested":
                            self.exit_requested.set()
                        elif event == "app_focus_revoked":
                            self._session_token = None
                            self._detach_framebuffer()
                            self.exit_requested.set()
            except Exception:
                _time.sleep(0.5)

    # ── hardware surface used by voice.py ────────────────────────
    def button_pressed(self):
        return self._button_down

    def set_rgb(self, r, g, b):
        try:
            _send_request(
                "led.set", {"r": int(r), "g": int(g), "b": int(b)},
                socket_path=self.socket_path,
            )
        except Exception:
            pass

    def fill_screen(self, color565):
        if self._fb is None:
            return
        high = (int(color565) >> 8) & 0xFF
        low = int(color565) & 0xFF
        self._fb.seek(0)
        self._fb.write(bytes([high, low]) * (LCD_WIDTH * LCD_HEIGHT))

    def show_status(self, status, text=""):
        """Draw a status screen (PIL) or a plain status color without PIL,
        and set the matching LED color."""
        bg, led = STATUS_STYLE.get(status, STATUS_STYLE["idle"])
        self.set_rgb(*led)
        if self._fb is None:
            return
        image = render_status_frame(status, text)
        if image is None:
            r, g, b = bg
            color565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            self.fill_screen(color565)
            return
        data = image_to_rgb565(image)
        row_bytes = LCD_WIDTH * 2
        for row in range(LCD_HEIGHT):
            dst = row * self._fb_stride
            src = row * row_bytes
            self._fb[dst:dst + row_bytes] = data[src:src + row_bytes]
