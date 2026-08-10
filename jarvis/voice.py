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

from . import config, emotions, trace, whisplay_app
from .chat import ChatSession


def _wav_stats(wav_path):
    """(duration_sec, peak_amplitude 0..32767) — peak near zero means the
    microphone recorded silence."""
    import array
    import wave

    try:
        with wave.open(wav_path, "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate() or 16000
            data = wf.readframes(frames)
        samples = array.array("h")
        samples.frombytes(data[: len(data) // 2 * 2])
        peak = max((abs(s) for s in samples), default=0)
        return frames / float(rate), peak
    except Exception:
        return 0.0, 0

RECORD_ARGS = ["-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "wav"]


def _daemon_service_active():
    try:
        return subprocess.run(
            ["systemctl", "is-active", "--quiet", "whisplay-daemon"],
            timeout=5,
        ).returncode == 0
    except Exception:
        return False


def _load_hardware():
    """Preferred: run as a whisplay-daemon foreground app. Fallbacks:
    direct WhisplayBoard access, then plain terminal.

    Safety: if the whisplay-daemon *service* is active but its socket is
    not answering, do NOT grab the hardware directly — two owners fighting
    over GPIO blanks the screen and wedges the daemon. Set
    JARVIS_FORCE_DIRECT_HW=true to override."""
    if whisplay_app.daemon_available():
        try:
            app = whisplay_app.DaemonApp()
            app.start()
            return app, "daemon"
        except Exception as err:
            print("[voice] daemon mode failed (%s)" % err)
    if _daemon_service_active() and not config.get_bool(
        "JARVIS_FORCE_DIRECT_HW", False
    ):
        print(
            "[voice] whisplay-daemon service is active but its socket is "
            "not responding — refusing direct hardware access to avoid a "
            "GPIO conflict.\n"
            "[voice] fix the daemon first: sudo systemctl restart "
            "whisplay-daemon\n"
            "[voice] (or stop it: sudo systemctl stop whisplay-daemon — "
            "or set JARVIS_FORCE_DIRECT_HW=true to override)"
        )
        return None, "terminal"
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
_vosk_model = None


def _load_vosk_model():
    """Load the vosk model once and keep it — reloading per utterance
    (what the CLI does) costs 10s+ on a Pi Zero 2W."""
    global _vosk_model
    if _vosk_model is not None:
        return _vosk_model
    from vosk import Model, SetLogLevel

    SetLogLevel(-1)
    path = config.vosk_model_path()
    started = time.time()
    if path:
        if not os.path.isdir(path):
            raise RuntimeError(
                "VOSK_MODEL_PATH does not exist: %s" % path
            )
        print("[asr] loading vosk model from %s ..." % path)
        _vosk_model = Model(path)
    else:
        print("[asr] VOSK_MODEL_PATH not set — using/downloading the "
              "default en-us model (set the path in .env for offline use)")
        _vosk_model = Model(lang="en-us")
    print("[asr] vosk model ready in %.1fs" % (time.time() - started))
    return _vosk_model


def _asr_vosk_python(wav_path):
    import json as _json
    import wave

    from vosk import KaldiRecognizer

    model = _load_vosk_model()
    with wave.open(wav_path, "rb") as wf:
        rec = KaldiRecognizer(model, wf.getframerate())
        while True:
            data = wf.readframes(4000)
            if not data:
                break
            rec.AcceptWaveform(data)
    result = _json.loads(rec.FinalResult())
    return (result.get("text") or "").strip()


def _asr_vosk_cli(wav_path):
    cmd = ["vosk-transcriber"]
    if config.vosk_model_path():
        cmd += ["--model", config.vosk_model_path()]
    cmd += ["--input", wav_path]
    proc = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "vosk-transcriber failed: %s"
            % proc.stderr.decode("utf-8", "replace")[-200:]
        )
    return proc.stdout.decode("utf-8", "replace").strip()


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
    """Pick a speech recognizer. Preference: in-process vosk (model kept
    loaded), vosk CLI, whisper-http server. Loud about what failed."""
    choice = config.asr_backend()
    if choice == "none":
        return None, "typed input"
    if choice in ("vosk", "auto"):
        try:
            import vosk  # noqa: F401

            _load_vosk_model()
            return _asr_vosk_python, "vosk"
        except ImportError:
            if choice == "vosk":
                print("[asr] python module 'vosk' not installed "
                      "(pip3 install vosk --break-system-packages)")
        except Exception as err:
            print("[asr] vosk unavailable: %s" % err)
        if shutil.which("vosk-transcriber"):
            return _asr_vosk_cli, "vosk-cli"
        if choice == "vosk":
            return None, "typed input"
    if choice in ("whisper-http", "auto"):
        try:
            urllib.request.urlopen(config.whisper_http_url(), timeout=2)
            return _asr_whisper_http, "whisper-http"
        except Exception:
            if choice == "whisper-http":
                print(
                    "[asr] whisper-http not reachable at %s"
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


# ── mic test ─────────────────────────────────────────────────────────
def run_mic_test(seconds=4, wav_file=None):
    """Diagnose the speech pipeline step by step: record -> level check
    -> playback -> speech recognition. `jarvis mic-test`."""
    print("== JARVIS microphone / speech test ==")
    asr, asr_name = _resolve_asr()
    print("speech recognizer: %s" % asr_name)
    if asr is None:
        print("!! no ASR available — recognition will be skipped.")
        print("   fix: pip3 install vosk --break-system-packages, then")
        print("   download a model (bash setup_pi.sh) and set "
              "VOSK_MODEL_PATH in .env")

    if wav_file:
        wav_path = wav_file
        print("using existing file: %s" % wav_path)
    else:
        if not shutil.which("arecord"):
            print("!! arecord not found — install alsa-utils")
            return 1
        device = config.alsa_input_device() or "(default)"
        wav_path = os.path.join(
            tempfile.gettempdir(), "jarvis-mic-test.wav"
        )
        print("recording %ds from ALSA device %s — speak now!"
              % (seconds, device))
        cmd = ["arecord", "-q"]
        if config.alsa_input_device():
            cmd += ["-D", config.alsa_input_device()]
        cmd += RECORD_ARGS + ["-d", str(seconds), wav_path]
        proc = subprocess.run(cmd, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            print("!! arecord failed: %s"
                  % proc.stderr.decode("utf-8", "replace").strip())
            print("   list capture devices with: arecord -l")
            return 1

    duration, peak = _wav_stats(wav_path)
    size = os.path.getsize(wav_path) if os.path.isfile(wav_path) else 0
    print("recorded: %.1fs, %d bytes, peak level %d/32767"
          % (duration, size, peak))
    if peak == 0:
        print("!! completely silent — wrong capture device? try: "
              "arecord -l, then set ALSA_INPUT_DEVICE in .env")
    elif peak < 500:
        print("!! very low level — raise capture volume with alsamixer "
              "(F4 for capture) or get closer to the mic")
    else:
        print("   level looks OK")

    if not wav_file and shutil.which("aplay"):
        print("playing back — you should hear yourself...")
        _aplay(wav_path)

    if asr is not None:
        print("recognizing...")
        started = time.time()
        try:
            text = asr(wav_path)
        except Exception as err:
            print("!! recognition failed: %s" % err)
            return 1
        print("asr (%s) took %.1fs" % (asr_name, time.time() - started))
        print("recognized: %r" % text)
        if not text:
            print("!! nothing recognized — if the level was OK, make sure "
                  "the model language matches (English model: "
                  "vosk-model-small-en-us-0.15)")
    return 0


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
    if asr is None and config.asr_backend() != "none":
        print(
            "[voice] *** NO SPEECH RECOGNITION AVAILABLE ***\n"
            "[voice] install offline ASR on this device with:\n"
            "[voice]   pip3 install vosk --break-system-packages\n"
            "[voice]   then download a model (bash setup_pi.sh does both)\n"
            "[voice] or point WHISPER_HTTP_URL at a whisper server on "
            "your LAN."
        )
        if not sys.stdin.isatty():
            # daemon-launched with no terminal: typing is impossible,
            # show the problem on screen instead of dying silently
            if board is not None and hw_kind == "daemon":
                try:
                    board.show_status(
                        "error", "No speech recognition installed. "
                        "Run: bash setup_pi.sh"
                    )
                except Exception:
                    pass
                time.sleep(8)
            if hw_kind == "daemon":
                board.cleanup()
            return 1
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

            duration, peak = _wav_stats(wav_path)
            print("[voice] recorded %.1fs, peak level %d/32767%s" % (
                duration, peak,
                "  (very low — check mic / alsamixer capture volume)"
                if peak < 500 else ""))
            trace.default.emit(
                "record", seconds=round(duration, 2), peak=peak
            )

            show("thinking", "Recognizing speech...")
            if asr:
                asr_started = time.time()
                try:
                    text = asr(wav_path)
                except Exception as err:
                    print("[voice] ASR failed: %s" % err)
                    trace.default.emit("asr", error=str(err))
                    show("error", "Speech recognition failed.")
                    time.sleep(1.5)
                    continue
                asr_seconds = time.time() - asr_started
                print("[voice] asr (%s) took %.1fs" % (asr_name, asr_seconds))
                trace.default.emit(
                    "asr", backend=asr_name,
                    seconds=round(asr_seconds, 2), text=text,
                )
            else:
                try:
                    text = input("[voice] (no ASR) type what you said> ")
                except EOFError:
                    break
            text = text.strip()
            print("[you] %s" % text)
            if not text:
                print("[voice] heard nothing — speak while holding the "
                      "button, closer to the microphone")
                show("error", "I heard nothing. Hold the button and speak.")
                time.sleep(1.5)
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
