"""Animated emotion faces for the Whisplay LCD (and the debug console).

Each state of the assistant maps to a looping animation:

    idle        calm face, slow blink
    listening   wide eyes + growing sound waves
    thinking    eyes up + cycling dots
    answering   talking mouth
    happy/sad/surprised/love/angry   reaction faces for replies
    error       dizzy X-eyes

Frames are drawn procedurally with PIL, so no assets ship with the
project — but you can override any of them by dropping your own GIF at
emotions/<name>.gif (it is scaled into the face area). The reply text is
scanned for emoji / sentiment keywords to pick a reaction face while the
answer is spoken.

The Animator plays frames through a `blit(rgb565_bytes)` callback, which
works for both the daemon shared framebuffer and a direct WhisplayBoard.
"""

import io
import os
import re
import threading
import time

from . import config

LCD_WIDTH = 240
LCD_HEIGHT = 280
FACE_HEIGHT = 170  # top region for the face; text panel lives below

EMOTIONS = [
    "idle", "listening", "thinking", "answering",
    "happy", "sad", "surprised", "love", "angry", "error",
]

# (background, face color) per emotion
PALETTE = {
    "idle": ((16, 24, 32), (255, 205, 84)),
    "listening": ((8, 56, 28), (120, 230, 140)),
    "thinking": ((60, 44, 10), (255, 205, 84)),
    "answering": ((10, 30, 80), (120, 190, 255)),
    "happy": ((20, 50, 20), (255, 205, 84)),
    "sad": ((25, 30, 55), (150, 180, 230)),
    "surprised": ((60, 30, 60), (255, 205, 84)),
    "love": ((70, 15, 40), (255, 150, 170)),
    "angry": ((70, 20, 10), (255, 120, 90)),
    "error": ((70, 12, 12), (240, 150, 150)),
}

_EMOJI_MAP = [
    ("love", "❤🥰😍💕💖😘"),
    ("happy", "😀😃😄😁😊🙂😉🤣😂👍🎉✨"),
    ("sad", "😢😭😞😔☹🙁💔"),
    ("surprised", "😮😲😯🤯😱"),
    ("angry", "😠😡🤬"),
]

_KEYWORDS = [
    ("sad", ("sorry", "unfortunately", "sadly", "can't help", "cannot help")),
    ("happy", ("great", "awesome", "congratulations", "well done", "perfect")),
    ("surprised", ("wow", "amazing", "incredible")),
]

_EMOJI_STRIP_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002700-\U000027BF\U0000FE0F\U00002764\U0001F900-\U0001F9FF]+"
)


def strip_emoji(text):
    """Remove emoji so TTS does not read them and fonts need not render
    them."""
    return _EMOJI_STRIP_RE.sub("", text or "").strip()


def emotion_for_reply(text):
    """Pick a reaction emotion for an answer (emoji first, then words)."""
    text = text or ""
    for emotion, chars in _EMOJI_MAP:
        if any(ch in text for ch in chars):
            return emotion
    lower = text.lower()
    for emotion, words in _KEYWORDS:
        if any(word in lower for word in words):
            return emotion
    return "answering"


def available():
    try:
        import PIL  # noqa: F401

        return True
    except ImportError:
        return False


def emotions_dir():
    path = config.get(
        "JARVIS_EMOTIONS_DIR", os.path.join(config.PROJECT_ROOT, "emotions")
    )
    os.makedirs(path, exist_ok=True)
    return path


# ── procedural face frames ───────────────────────────────────────────
def _face_frame(emotion, phase):
    """Draw one face frame (240x170). phase runs 0..1 over the loop."""
    from PIL import Image, ImageDraw

    bg, face = PALETTE.get(emotion, PALETTE["idle"])
    img = Image.new("RGB", (LCD_WIDTH, FACE_HEIGHT), bg)
    draw = ImageDraw.Draw(img)

    cx, cy, radius = LCD_WIDTH // 2, FACE_HEIGHT // 2 + 4, 64
    dark = tuple(max(0, c - 190) for c in face)

    bounce = 0
    if emotion in ("happy", "love"):
        bounce = int(4 * abs(2 * phase - 1)) - 2
    if emotion == "surprised":
        radius += int(4 * abs(2 * phase - 1))
    cy += bounce

    draw.ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=face, outline=dark, width=3,
    )

    eye_dx, eye_y, eye_r = 26, cy - 14, 9

    def eye(x, kind="open"):
        if kind == "open":
            draw.ellipse(
                (x - eye_r, eye_y - eye_r, x + eye_r, eye_y + eye_r),
                fill=(30, 30, 34),
            )
        elif kind == "closed":
            draw.line(
                (x - eye_r, eye_y, x + eye_r, eye_y), fill=(30, 30, 34), width=4
            )
        elif kind == "happy":  # ^ ^
            draw.arc(
                (x - eye_r, eye_y - 6, x + eye_r, eye_y + 8),
                200, 340, fill=(30, 30, 34), width=4,
            )
        elif kind == "up":
            draw.ellipse(
                (x - eye_r, eye_y - eye_r - 6, x + eye_r, eye_y + eye_r - 6),
                fill=(30, 30, 34),
            )
        elif kind == "wide":
            r = eye_r + 3
            draw.ellipse((x - r, eye_y - r, x + r, eye_y + r), fill=(250, 250, 250))
            draw.ellipse((x - 5, eye_y - 5, x + 5, eye_y + 5), fill=(30, 30, 34))
        elif kind == "x":
            for a, b in ((-1, -1), (-1, 1)):
                draw.line(
                    (x + a * 8, eye_y + b * 8, x - a * 8, eye_y - b * 8),
                    fill=(120, 20, 20), width=4,
                )
        elif kind == "heart":
            _heart(draw, x, eye_y, 12, (220, 30, 70))
        elif kind == "angry":
            draw.ellipse(
                (x - eye_r, eye_y - eye_r, x + eye_r, eye_y + eye_r),
                fill=(30, 30, 34),
            )
            slope = 6 if x < cx else -6
            draw.line(
                (x - eye_r - 2, eye_y - eye_r - 2 + (0 if x < cx else slope),
                 x + eye_r + 2, eye_y - eye_r - 2 + (slope if x < cx else 0)),
                fill=(60, 20, 10), width=5,
            )

    mouth_y = cy + 26

    if emotion == "idle":
        kind = "closed" if phase >= 0.85 else "open"
        eye(cx - eye_dx, kind)
        eye(cx + eye_dx, kind)
        draw.arc((cx - 18, mouth_y - 8, cx + 18, mouth_y + 10),
                 20, 160, fill=dark, width=4)
    elif emotion == "listening":
        eye(cx - eye_dx, "wide")
        eye(cx + eye_dx, "wide")
        draw.ellipse((cx - 8, mouth_y - 4, cx + 8, mouth_y + 8), fill=dark)
        # growing sound waves on both sides
        n = 1 + int(phase * 3) % 3
        for i in range(1, n + 1):
            gap = radius + 8 + i * 12
            for side in (-1, 1):
                x0 = cx + side * gap
                draw.arc(
                    (x0 - 10, cy - 22, x0 + 10, cy + 22),
                    -60 if side > 0 else 120,
                    60 if side > 0 else 240,
                    fill=(200, 240, 210), width=3,
                )
    elif emotion == "thinking":
        eye(cx - eye_dx, "up")
        eye(cx + eye_dx, "up")
        draw.line((cx - 14, mouth_y + 2, cx + 14, mouth_y + 2), fill=dark, width=4)
        active = int(phase * 3) % 3
        for i in range(3):
            x = cx + radius - 4 + i * 16
            y = cy - radius - 4 - i * 10
            r = 5 + (3 if i == active else 0)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(240, 240, 240))
    elif emotion == "answering":
        eye(cx - eye_dx)
        eye(cx + eye_dx)
        openness = abs(2 * ((phase * 2) % 1) - 1)  # talk cycle
        h = 4 + int(14 * openness)
        draw.ellipse((cx - 16, mouth_y - h // 2, cx + 16, mouth_y + h // 2 + 4),
                     fill=(40, 30, 30))
    elif emotion == "happy":
        eye(cx - eye_dx, "happy")
        eye(cx + eye_dx, "happy")
        draw.arc((cx - 26, mouth_y - 16, cx + 26, mouth_y + 14),
                 10, 170, fill=dark, width=5)
    elif emotion == "sad":
        eye(cx - eye_dx, "closed")
        eye(cx + eye_dx, "closed")
        draw.arc((cx - 20, mouth_y, cx + 20, mouth_y + 22),
                 190, 350, fill=dark, width=4)
        # falling tear
        ty = eye_y + 8 + int(26 * phase)
        draw.ellipse((cx - eye_dx - 4, ty, cx - eye_dx + 4, ty + 10),
                     fill=(140, 200, 250))
    elif emotion == "surprised":
        eye(cx - eye_dx, "wide")
        eye(cx + eye_dx, "wide")
        r = 10 + int(3 * abs(2 * phase - 1))
        draw.ellipse((cx - r, mouth_y - r, cx + r, mouth_y + r), fill=(40, 30, 30))
    elif emotion == "love":
        eye(cx - eye_dx, "heart")
        eye(cx + eye_dx, "heart")
        draw.arc((cx - 20, mouth_y - 12, cx + 20, mouth_y + 10),
                 10, 170, fill=dark, width=4)
        if phase < 0.5:
            _heart(draw, cx + radius + 18, cy - radius + 6, 10, (255, 90, 120))
    elif emotion == "angry":
        eye(cx - eye_dx, "angry")
        eye(cx + eye_dx, "angry")
        draw.arc((cx - 18, mouth_y + 2, cx + 18, mouth_y + 20),
                 200, 340, fill=(60, 20, 10), width=5)
    elif emotion == "error":
        eye(cx - eye_dx, "x")
        eye(cx + eye_dx, "x")
        draw.arc((cx - 18, mouth_y, cx + 18, mouth_y + 18),
                 200, 340, fill=(120, 20, 20), width=4)

    return img


def _heart(draw, x, y, size, color):
    half = size // 2
    draw.ellipse((x - size, y - half - 2, x, y + half - 2), fill=color)
    draw.ellipse((x, y - half - 2, x + size, y + half - 2), fill=color)
    draw.polygon(
        (x - size, y, x + size, y, x, y + size), fill=color
    )


# ── EMO-style face: big glowing eyes on a near-black screen ──────────
EMO_BG = (6, 8, 14)
EMO_COLORS = {
    "idle": (95, 225, 255),
    "listening": (120, 255, 205),
    "thinking": (255, 215, 130),
    "answering": (100, 195, 255),
    "happy": (130, 245, 255),
    "sad": (115, 155, 255),
    "surprised": (210, 235, 255),
    "love": (255, 125, 175),
    "angry": (255, 115, 85),
    "error": (255, 95, 95),
}


def _emo_frame(emotion, phase):
    """One EMO-style frame: everything is said with two glowing eyes."""
    import math

    from PIL import Image, ImageDraw, ImageFilter

    color = EMO_COLORS.get(emotion, EMO_COLORS["idle"])
    frame = Image.new("RGB", (LCD_WIDTH, FACE_HEIGHT), EMO_BG)
    mask = Image.new("L", (LCD_WIDTH, FACE_HEIGHT), 0)
    draw = ImageDraw.Draw(mask)

    cx = LCD_WIDTH // 2
    eye_y = FACE_HEIGHT // 2 + 2
    spacing = 60  # center offset of each eye from the middle
    w, h = 52, 68  # base eye size
    bob = math.sin(2 * math.pi * phase) * 3
    wave = math.sin(2 * math.pi * phase)
    tear_xy = None
    draw_highlight = True

    def eye_box(side, ww, hh, dx=0, dy=0):
        ex = cx + side * spacing + dx
        ey = eye_y + dy + bob
        return (ex - ww / 2, ey - hh / 2, ex + ww / 2, ey + hh / 2)

    def rounded(box, radius=None):
        radius = radius if radius is not None else min(
            box[2] - box[0], box[3] - box[1]
        ) / 2.6
        draw.rounded_rectangle(box, radius=radius, fill=255)

    if emotion == "idle":
        # calm gaze with a quick blink at the end of the loop
        blink = max(0.12, min(1.0, abs(phase - 0.92) / 0.08)) if phase > 0.84 else 1.0
        rounded(eye_box(-1, w, h * blink))
        rounded(eye_box(1, w, h * blink))
        draw_highlight = blink > 0.6
    elif emotion == "listening":
        grow = 1.08 + 0.06 * wave
        rounded(eye_box(-1, w * grow, h * grow))
        rounded(eye_box(1, w * grow, h * grow))
        # little equalizer bars under the eyes
        for i in range(3):
            bh = 6 + 10 * abs(math.sin(2 * math.pi * (phase + i / 3.0)))
            bx = cx - 20 + i * 20
            by = FACE_HEIGHT - 18
            draw.rounded_rectangle(
                (bx - 4, by - bh, bx + 4, by), radius=4, fill=255
            )
    elif emotion == "thinking":
        # narrowed eyes drifting up and to the side
        drift = 8 * math.sin(2 * math.pi * phase / 2)
        rounded(eye_box(-1, w * 0.9, h * 0.55, dx=8 + drift, dy=-10))
        rounded(eye_box(1, w * 0.9, h * 0.55, dx=8 + drift, dy=-10))
    elif emotion == "answering":
        talk = 0.75 + 0.25 * abs(math.sin(2 * math.pi * phase * 2))
        rounded(eye_box(-1, w, h * talk))
        rounded(eye_box(1, w, h * talk))
    elif emotion == "happy":
        # smiling crescent eyes: full eye with the lower half carved away
        rounded(eye_box(-1, w * 1.05, h))
        rounded(eye_box(1, w * 1.05, h))
        for side in (-1, 1):
            ex = cx + side * spacing
            ey = eye_y + bob
            draw.ellipse(
                (ex - w, ey - h * 0.05, ex + w, ey + h), fill=0
            )
        draw_highlight = False
    elif emotion == "sad":
        # droopy eyes tilted outward, plus a falling tear
        for side in (-1, 1):
            eye = Image.new("L", (w * 2, h * 2), 0)
            ImageDraw.Draw(eye).rounded_rectangle(
                (w // 2, h // 2, w // 2 + w, h // 2 + int(h * 0.8)),
                radius=w // 2.6, fill=255,
            )
            eye = eye.rotate(-14 * side, resample=Image.BILINEAR)
            mask.paste(
                eye,
                (int(cx + side * spacing - w), int(eye_y + bob - h + 6)),
                eye,
            )
        tear_xy = (cx - spacing - 8, eye_y + 26 + int(30 * phase))
        draw_highlight = False
    elif emotion == "surprised":
        r = (h * 0.62) * (1.0 + 0.08 * abs(wave))
        for side in (-1, 1):
            ex = cx + side * spacing
            draw.ellipse(
                (ex - r, eye_y + bob - r, ex + r, eye_y + bob + r), fill=255
            )
    elif emotion == "love":
        beat = 1.0 + 0.12 * abs(math.sin(2 * math.pi * phase))
        for side in (-1, 1):
            ex = cx + side * spacing
            ey = eye_y + bob
            s = int(30 * beat)
            half = s // 2
            draw.ellipse((ex - s, ey - half - s // 2, ex, ey + half - s // 2),
                         fill=255)
            draw.ellipse((ex, ey - half - s // 2, ex + s, ey + half - s // 2),
                         fill=255)
            draw.polygon(
                (ex - s, ey - s // 6, ex + s, ey - s // 6, ex, ey + s),
                fill=255,
            )
        draw_highlight = False
    elif emotion == "angry":
        # slanted eyes, inner corners pulled down
        for side in (-1, 1):
            ex = cx + side * spacing
            ey = eye_y + bob
            inner, outer = ex - side * w / 2, ex + side * w / 2
            draw.polygon(
                (
                    (inner, ey - h * 0.12),
                    (outer, ey - h * 0.42),
                    (outer, ey + h * 0.40),
                    (inner, ey + h * 0.40),
                ),
                fill=255,
            )
        draw_highlight = False
    elif emotion == "error":
        # dizzy X eyes with a flicker
        if int(phase * 8) % 4 != 3:
            for side in (-1, 1):
                ex = cx + side * spacing
                ey = eye_y + bob
                for a, b in ((-1, -1), (-1, 1)):
                    draw.line(
                        (ex + a * 22, ey + b * 22, ex - a * 22, ey - b * 22),
                        fill=255, width=13,
                    )
        draw_highlight = False
    else:
        rounded(eye_box(-1, w, h))
        rounded(eye_box(1, w, h))

    # glow: soft halo + anti-aliased core
    halo = mask.filter(ImageFilter.GaussianBlur(12))
    core = mask.filter(ImageFilter.GaussianBlur(1.2))
    frame.paste(Image.new("RGB", frame.size, tuple(c // 3 for c in color)),
                (0, 0), halo)
    frame.paste(Image.new("RGB", frame.size, color), (0, 0), core)

    extra = ImageDraw.Draw(frame)
    if draw_highlight:
        # tiny white sparkle in each eye = instant cuteness
        for side in (-1, 1):
            hx = cx + side * spacing - w // 5
            hy = eye_y + bob - h // 4
            extra.ellipse((hx - 6, hy - 7, hx + 6, hy + 7),
                          fill=(245, 252, 255))
    if tear_xy is not None:
        tx, ty = tear_xy
        extra.ellipse((tx - 5, ty, tx + 5, ty + 13), fill=(140, 200, 255))

    return frame


FRAME_COUNTS = {"idle": 10}
DEFAULT_FRAMES = 8
FRAME_MS = {"idle": 180}
DEFAULT_FRAME_MS = 120


def style_bg(emotion):
    """Screen background for the active face style."""
    if config.face_style() == "classic":
        return PALETTE.get(emotion, PALETTE["idle"])[0]
    return EMO_BG


def build_face_frames(emotion):
    """[(PIL face image, duration_ms)] — custom GIF override wins."""
    custom = os.path.join(emotions_dir(), "%s.gif" % emotion)
    if os.path.isfile(custom):
        frames = _load_gif_frames(custom, emotion)
        if frames:
            return frames
    count = FRAME_COUNTS.get(emotion, DEFAULT_FRAMES)
    ms = FRAME_MS.get(emotion, DEFAULT_FRAME_MS)
    render = _face_frame if config.face_style() == "classic" else _emo_frame
    return [
        (render(emotion, i / float(count)), ms) for i in range(count)
    ]


def _load_gif_frames(path, emotion):
    from PIL import Image, ImageSequence

    bg, _face = PALETTE.get(emotion, PALETTE["idle"])
    frames = []
    try:
        with Image.open(path) as gif:
            for frame in ImageSequence.Iterator(gif):
                duration = int(frame.info.get("duration", DEFAULT_FRAME_MS)) or DEFAULT_FRAME_MS
                rgba = frame.convert("RGBA")
                scale = min(LCD_WIDTH / rgba.width, FACE_HEIGHT / rgba.height)
                new_size = (
                    max(1, int(rgba.width * scale)),
                    max(1, int(rgba.height * scale)),
                )
                rgba = rgba.resize(new_size)
                canvas = Image.new("RGB", (LCD_WIDTH, FACE_HEIGHT), bg)
                canvas.paste(
                    rgba,
                    ((LCD_WIDTH - new_size[0]) // 2,
                     (FACE_HEIGHT - new_size[1]) // 2),
                    rgba,
                )
                frames.append((canvas, duration))
                if len(frames) >= 30:
                    break
    except Exception as err:
        print("[emotions] failed to load %s: %s" % (path, err))
        return []
    return frames


def compose_screen_frames(emotion, text=""):
    """Full 240x280 frames: animated face on top, text panel below."""
    from PIL import Image

    from .whisplay_app import image_to_rgb565, render_status_frame  # noqa

    face_frames = build_face_frames(emotion)
    panel = _text_panel(emotion, text)
    frames = []
    for face, ms in face_frames:
        screen = Image.new(
            "RGB", (LCD_WIDTH, LCD_HEIGHT), style_bg(emotion)
        )
        screen.paste(face, (0, 0))
        if panel is not None:
            screen.paste(panel, (0, FACE_HEIGHT))
        frames.append((image_to_rgb565(screen), ms))
    return frames


def _text_panel(emotion, text):
    from PIL import Image, ImageDraw

    from .whisplay_app import _load_fonts

    bg = style_bg(emotion)
    panel = Image.new(
        "RGB", (LCD_WIDTH, LCD_HEIGHT - FACE_HEIGHT),
        tuple(min(255, c + 12) for c in bg),
    )
    draw = ImageDraw.Draw(panel)
    _title_font, body_font = _load_fonts()
    text = strip_emoji(text)
    if not text:
        return panel

    max_width = LCD_WIDTH - 24
    words = text.split()
    lines = []
    line = ""
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
        if len(lines) >= 4:
            break
    if line and len(lines) < 4:
        lines.append(line)
    if len(lines) == 4 and len(words) > sum(len(l.split()) for l in lines):
        lines[-1] += " …"
    y = 8
    for row in lines:
        draw.text((12, y), row, fill=(235, 238, 242), font=body_font)
        y += 24
    return panel


def export_gif(emotion, path=None):
    """Write the default animation as a GIF (preview / starting point for
    a custom one)."""
    frames = build_face_frames(emotion)
    path = path or os.path.join(emotions_dir(), "_default_%s.gif" % emotion)
    images = [f for f, _ in frames]
    durations = [ms for _, ms in frames]
    images[0].save(
        path, save_all=True, append_images=images[1:],
        duration=durations, loop=0,
    )
    return path


def gif_bytes(emotion):
    """Animated GIF bytes for the debug console preview."""
    frames = build_face_frames(emotion)
    buf = io.BytesIO()
    images = [f for f, _ in frames]
    durations = [ms for _, ms in frames]
    images[0].save(
        buf, format="GIF", save_all=True, append_images=images[1:],
        duration=durations, loop=0,
    )
    return buf.getvalue()


class Animator:
    """Plays emotion animations through a blit(rgb565_bytes) callback."""

    def __init__(self, blit):
        self.blit = blit
        self._lock = threading.Lock()
        self._current = None  # (emotion, text)
        self._frames = []
        self._cache = {}
        self._running = True
        self._wake = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def play(self, emotion, text=""):
        key = (emotion, text)
        with self._lock:
            if self._current == key:
                return
            if key not in self._cache:
                if len(self._cache) > 24:
                    self._cache.clear()
                self._cache[key] = compose_screen_frames(emotion, text)
            self._current = key
            self._frames = self._cache[key]
        self._wake.set()

    def stop(self):
        self._running = False
        self._wake.set()

    def _loop(self):
        index = 0
        while self._running:
            with self._lock:
                frames = self._frames
                key = self._current
            if not frames:
                self._wake.wait(0.2)
                self._wake.clear()
                continue
            index = index % len(frames)
            data, ms = frames[index]
            try:
                self.blit(data)
            except Exception:
                pass
            index += 1
            self._wake.wait(ms / 1000.0)
            if self._wake.is_set():
                self._wake.clear()
                with self._lock:
                    if self._current != key:
                        index = 0
