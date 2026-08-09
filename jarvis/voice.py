"""Optional voice front-end (push-to-talk), for Raspberry Pi + Whisplay HAT.

Flow (same shape as whisplay-ai-chatbot's ChatFlow):
  hold button / press Enter -> arecord -> ASR -> ChatSession.ask -> TTS -> aplay

Everything degrades gracefully:
  - Whisplay HAT present  -> button push-to-talk + RGB status LED
    (listening green, thinking yellow, answering blue — whisplay colors)
  - no HAT                -> Enter-to-start / Enter-to-stop in the terminal
  - ASR: vosk-transcriber CLI, or a whisper-http server (/recognize with
    {"filePath"| "base64"}), or typed input as fallback
  - TTS: espeak-ng or piper, silent if neither exists

This module only uses subprocess + stdlib, so it adds no dependencies for
people who never run `jarvis voice`.
"""

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

from . import config, emotions, whisplay_app
from .chat import ChatSession

RECORD_ARGS = ["-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "wav"]


def _load_hardware():
    """Preferred: run as a whisplay-daemon foreground app. Fallbacks:
    direct WhisplayBoard access, then plain terminal."""
    if whisplay_app.daemon_available():
        try:
            app = whisplay_app.DaemonApp()
            app.start()
            return app, "daemon"
        except Exception as err:
            print("[voice] daemon mode failed (%s), trying direct access" % err)
    board = _load_whisplay_board()
    if board is not None:
        return board, "direct"
    return None, "terminal"


# ── Whisplay HAT (optional) ──────────────────────────────────────────
def _load_whisplay_board():
    """Try to import WhisplayBoard from the Whisplay driver repo.

    Search order: explicit WHISPLAY_DRIVER_DIR, then ~/Whisplay (the
    standard install location on the device), then copies sitting next to
    this project."""
    candidates = [
        config.get("WHISPLAY_DRIVER_DIR", ""),
        os.path.expanduser("~/Whisplay/runtime"),
        os.path.join(config.PROJECT_ROOT, "Whisplay", "runtime"),
        os.path.join(config.PROJECT_ROOT, "whisplay-ai-chatbot", "python"),
    ]
    candidates = [c for c in candidates if c]
    for path in candidates:
        if os.path.isfile(os.path.join(path, "whisplay.py")):
            sys.path.insert(0, path)
            break
    try:
        from whisplay import WhisplayBoard  # type: ignore

        return WhisplayBoard()
    except Exception:
        return None


# ── ASR backends ─────────────────────────────────────────────────────
def _asr_vosk(wav_path):
    out_path = wav_path + ".txt"
    cmd = ["vosk-transcriber", "-i", wav_path, "-o", out_path]
    if config.vosk_model_path():
        cmd += ["--model", config.vosk_model_path()]
    subprocess.run(
        cmd, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        with open(out_path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    finally:
        if os.path.exists(out_path):
            os.unlink(out_path)


def _asr_whisper_http(wav_path):
    url = config.whisper_http_url().rstrip("/") + "/recognize"
    with open(wav_path, "rb") as fh:
        payload = {"base64": base64.b64encode(fh.read()).decode("ascii")}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (data.get("text") or data.get("result") or "").strip()


def _resolve_asr():
    choice = config.asr_backend()
    if choice == "none":
        return None, "typed input"
    if choice == "vosk" or (
        choice == "auto" and shutil.which("vosk-transcriber")
    ):
        return _asr_vosk, "vosk"
    if choice in ("whisper-http", "auto"):
        try:
            urllib.request.urlopen(config.whisper_http_url(), timeout=2)
            return _asr_whisper_http, "whisper-http"
        except Exception:
            if choice == "whisper-http":
                print(
                    "[voice] whisper-http not reachable at %s"
                    % config.whisper_http_url()
                )
    return None, "typed input"


# ── TTS backends ─────────────────────────────────────────────────────
def _speak_espeak(text, wav_path):
    subprocess.run(
        [
            "espeak-ng", "-w", wav_path,
            "-v", config.get("ESPEAK_NG_VOICE", "en"),
            "-s", config.get("ESPEAK_NG_SPEED", "175"),
            text,
        ],
        check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _speak_piper(text, wav_path):
    subprocess.run(
        [config.piper_binary(), "--model", config.piper_model(),
         "--output_file", wav_path],
        input=text.encode("utf-8"),
        check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _resolve_tts():
    choice = config.tts_backend()
    if choice == "none":
        return None, "silent"
    if choice == "piper" or (
        choice == "auto" and config.piper_model()
        and shutil.which(config.piper_binary())
    ):
        return _speak_piper, "piper"
    if choice in ("espeak-ng", "auto") and shutil.which("espeak-ng"):
        return _speak_espeak, "espeak-ng"
    return None, "silent"


def _aplay(wav_path):
    cmd = ["aplay", "-q"]
    if config.alsa_output_device():
        cmd += ["-D", config.alsa_output_device()]
    subprocess.run(cmd + [wav_path], check=False)


# ── recording ────────────────────────────────────────────────────────
def _start_recording(wav_path):
    cmd = ["arecord", "-q"]
    if config.alsa_input_device():
        cmd += ["-D", config.alsa_input_device()]
    cmd += RECORD_ARGS + ["-d", str(config.record_max_sec()), wav_path]
    return subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def _record_push_to_talk(board, wav_path):
    """Record while the Whisplay button is held (already pressed when
    called), or between two Enter presses without hardware."""
    proc = _start_recording(wav_path)
    if board:
        while board.button_pressed() and proc.poll() is None:
            time.sleep(0.05)
    else:
        try:
            input()  # stop on Enter
        except EOFError:
            pass
    if proc.poll() is None:
        proc.terminate()
        proc.wait()
    time.sleep(0.1)
    return os.path.isfile(wav_path) and os.path.getsize(wav_path) > 1024


# ── main loop ────────────────────────────────────────────────────────
def run_voice_loop(backend=None):
    if not shutil.which("arecord"):
        print("[voice] arecord not found — install alsa-utils first.")
        return 1

    board, hw_kind = _load_hardware()
    asr, asr_name = _resolve_asr()
    tts, tts_name = _resolve_tts()
    session = ChatSession(backend=backend, quiet=True)

    print("[voice] brain: %s | asr: %s | tts: %s | whisplay: %s" % (
        session.backend, asr_name, tts_name, hw_kind))
    if board:
        print("[voice] hold the button to talk"
              + (", 4 rapid clicks to exit." if hw_kind == "daemon"
                 else ", Ctrl-C to quit."))
    else:
        print("[voice] press Enter to start recording, Enter again to stop, "
              "Ctrl-C to quit.")

    def exiting():
        return hw_kind == "daemon" and board.exit_requested.is_set()

    # Animated emotion faces when PIL is available; static fallback else.
    animator = None
    if board is not None and emotions.available():
        blit = (
            board.blit
            if hw_kind == "daemon"
            else lambda data: board.draw_image(
                0, 0, whisplay_app.LCD_WIDTH, whisplay_app.LCD_HEIGHT, data
            )
        )
        try:
            animator = emotions.Animator(blit)
        except Exception as err:
            print("[voice] animations disabled: %s" % err)

    def show(status, text=""):
        if board is None:
            return
        # reaction emotions (happy/sad/...) reuse the answering LED color
        led_key = status if status in whisplay_app.STATUS_STYLE else "answering"
        led = whisplay_app.STATUS_STYLE[led_key][1]
        try:
            board.set_rgb(*led)
        except Exception:
            pass
        if animator is not None:
            animator.play(status, text)
        elif hw_kind == "daemon":
            try:
                board.show_status(status, text)
            except Exception:
                pass

    tmp_dir = tempfile.mkdtemp(prefix="jarvis-voice-")
    try:
        while not exiting():
            show("idle", "Hold the button and speak.")
            if board:
                while not board.button_pressed():
                    if exiting():
                        raise KeyboardInterrupt
                    time.sleep(0.05)
            else:
                try:
                    input("\n[voice] Enter to record> ")
                except EOFError:
                    break

            show("listening", "Speak now, release to stop.")
            wav_path = os.path.join(tmp_dir, "rec-%d.wav" % int(time.time()))
            ok = _record_push_to_talk(board, wav_path)
            if not ok:
                print("[voice] recording too short, try again")
                # if recording failed while the button is still held (e.g.
                # bad ALSA device), wait for release to avoid a tight loop
                while board and board.button_pressed() and not exiting():
                    time.sleep(0.05)
                continue

            show("thinking", "Recognizing speech...")
            if asr:
                try:
                    text = asr(wav_path)
                except Exception as err:
                    print("[voice] ASR failed: %s" % err)
                    show("error", "Speech recognition failed.")
                    time.sleep(1.5)
                    continue
            else:
                try:
                    text = input("[voice] (no ASR) type what you said> ")
                except EOFError:
                    break
            text = text.strip()
            print("[you] %s" % text)
            if not text:
                continue

            show("thinking", text)
            answer = session.ask(text)
            print("[jarvis] %s" % answer)

            # reaction face picked from emoji/sentiment in the reply
            show(emotions.emotion_for_reply(answer), answer)
            if tts and answer:
                speech = emotions.strip_emoji(answer)
                out_wav = os.path.join(tmp_dir, "tts.wav")
                try:
                    tts(speech, out_wav)
                    _aplay(out_wav)
                except Exception as err:
                    print("[voice] TTS failed: %s" % err)
            os.unlink(wav_path)
    except KeyboardInterrupt:
        print("\n[voice] bye")
    finally:
        if animator is not None:
            animator.stop()
        if hw_kind == "daemon":
            board.cleanup()
        elif board is not None:
            try:
                board.set_rgb(0, 0, 0)
            except Exception:
                pass
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return 0
