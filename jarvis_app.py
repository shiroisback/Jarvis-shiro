from __future__ import annotations

import ctypes
import json
import queue
import sys
import threading
import time
from pathlib import Path

import webview

sys.path.insert(0, str(Path(__file__).parent))
from jarvis_client import JarvisClient
from jarvis_actions import ActionDispatcher, ShutdownHandler

try:
    import speech_recognition as sr
    _SR = True
except ImportError:
    _SR = False

try:
    import pyttsx3
    _TTS = True
except ImportError:
    _TTS = False

WAKE_TRIGGERS = ("jarvis", "jarvi", "jarvy", "jarv", "davis", "garvis", "jarwiss", "arvis", "jar", "jor", "javis")

def _play_sound(filename: str) -> None:
    path = Path(__file__).parent / filename
    if not path.exists():
        return
    def _play():
        try:
            winmm = ctypes.windll.winmm
            alias = "jarvis_sound"
            winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, None)
            winmm.mciSendStringW(f'play {alias} wait', None, 0, None)
            winmm.mciSendStringW(f'close {alias}', None, 0, None)
        except Exception as exc:
            print(f"[SOUND] Erreur: {exc}")
    threading.Thread(target=_play, daemon=True).start()


class TTSEngine:
    def __init__(self) -> None:
        self._q: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self._pending = 0
        self._idle = threading.Event()
        self._idle.set()
        if _TTS:
            threading.Thread(target=self._worker, daemon=True).start()

    _VOICE_ID = r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_ZIRA_11.0"

    def _new_engine(self):
        engine = pyttsx3.init()
        engine.setProperty("voice", self._VOICE_ID)
        engine.setProperty("rate", 175)
        engine.setProperty("volume", 1.0)
        return engine

    def _worker(self) -> None:
        ctypes.windll.ole32.CoInitialize(None)
        engine = self._new_engine()
        while True:
            item = self._q.get()
            if item is None:
                break
            try:
                engine.say(item)
                engine.runAndWait()
            except Exception as exc:
                print(f"[TTS] Error: {exc} — reinit")
                try:
                    engine.stop()
                except Exception:
                    pass
                try:
                    engine = self._new_engine()
                except Exception as e:
                    print(f"[TTS] Reinit failed: {e}")
            finally:
                with self._lock:
                    self._pending -= 1
                    if self._pending == 0:
                        self._idle.set()
        ctypes.windll.ole32.CoUninitialize()

    def speak(self, text: str) -> None:
        if not _TTS:
            return
        with self._lock:
            self._pending += 1
            self._idle.clear()
        self._q.put(text)

    def speak_and_wait(self, text: str, timeout: float = 8.0) -> None:
        self.speak(text)
        self._idle.wait(timeout=timeout)

    def wait_done(self, timeout: float = 20.0) -> None:
        self._idle.wait(timeout=timeout)


class WakeListener:
    def __init__(self, api: "JarvisAPI") -> None:
        self._api        = api
        self._active     = False
        self._in_command = False
        self._rec        = sr.Recognizer()

        self._WAKE_PAUSE   = 0.9  
        self._CMD_PAUSE    = 0.8  
        self._rec.pause_threshold               = self._WAKE_PAUSE
        self._rec.non_speaking_duration         = 0.4
        self._rec.dynamic_energy_threshold      = True
        self._rec.dynamic_energy_adjustment_damping = 0.12
        self._rec.energy_threshold              = 200

    def start(self) -> None:
        if not _SR:
            return
        self._active = True
        threading.Thread(target=self._calibrate_then_loop, daemon=True).start()

    def stop(self) -> None:
        self._active = False

    def _calibrate_then_loop(self) -> None:
        print("[WAKE] Calibration du micro...")
        try:
            with sr.Microphone() as src:
                self._rec.adjust_for_ambient_noise(src, duration=2.0)
            print(f"[WAKE] Prêt — seuil={self._rec.energy_threshold:.0f} — dis 'Hey Jarvis'")
        except Exception as exc:
            print(f"[WAKE] Erreur calibration: {exc}")
            return
        self._listen_loop()

    def _listen_loop(self) -> None:
        while self._active:
            if self._in_command:         
                time.sleep(0.05)
                continue
            try:
                with sr.Microphone() as src:
                    audio = self._rec.listen(src, timeout=None, phrase_time_limit=6)

                text = self._rec.recognize_google(audio, language="fr-FR").lower()
                print(f"[WAKE] Entendu : '{text}'")

                if any(t in text for t in WAKE_TRIGGERS):
                    threading.Thread(target=self._handle_wake, daemon=True).start()

            except sr.UnknownValueError:
                pass   
            except sr.RequestError as exc:
                print(f"[WAKE] API Google indispo: {exc}")
                time.sleep(3)
            except Exception as exc:
                if self._active:
                    print(f"[WAKE] Erreur boucle: {exc}")
                    time.sleep(1)

    def _handle_wake(self) -> None:
        if self._in_command:
            return
        self._in_command = True

        try:
            _play_sound("start.mp3")
            self._api._js("setReactor('listening')")

            self._rec.pause_threshold = self._CMD_PAUSE
            try:
                with sr.Microphone() as mic:
                    self._rec.adjust_for_ambient_noise(mic, duration=0.15)
                    audio = self._rec.listen(mic, timeout=5, phrase_time_limit=10)
            finally:
                self._rec.pause_threshold = self._WAKE_PAUSE

            phrase = self._rec.recognize_google(audio, language="fr-FR")
            print(f"[CMD] '{phrase}'")

            _play_sound("launch.mp3")
            self._api._js("setReactor('processing')")
            result = self._api._process_command(phrase)
            self._api._js(f"showResult({json.dumps(result)})")

            self._api._tts.wait_done(timeout=25)
            time.sleep(0.4)

            try:
                with sr.Microphone() as src:
                    self._rec.adjust_for_ambient_noise(src, duration=0.5)
            except Exception:
                pass

        except sr.WaitTimeoutError:
            self._api._tts.speak_and_wait("I'm listening, please repeat.", timeout=5)

        except sr.UnknownValueError:
            self._api._tts.speak_and_wait("I didn't catch that, please repeat.", timeout=5)

        except sr.RequestError as exc:
            print(f"[WAKE] API Google erreur: {exc}")

        except Exception as exc:
            print(f"[WAKE] Erreur commande: {exc}")

        finally:
            self._in_command = False
            self._api._js("setReactor('standby')")


class JarvisAPI:
    def __init__(self) -> None:
        self._window: webview.Window | None = None
        self._client = JarvisClient()
        self._dispatcher = ActionDispatcher()
        self._tts = TTSEngine()
        self._wake = WakeListener(self) if _SR else None

    def set_window(self, win: webview.Window) -> None:
        self._window = win

    def _js(self, expr: str) -> None:
        if self._window:
            try:
                self._window.evaluate_js(expr)
            except Exception:
                pass

    def _process_command(self, phrase: str) -> dict:
        phrase = phrase.strip()
        if not phrase:
            return {"error": "Commande vide."}

        if not self._client.is_running():
            ok = self._client.ensure_server_running(wait=40.0)
            if not ok:
                return {"error": "Brain server indisponible."}

        try:
            tag, confidence = self._client.ask(phrase)
        except ConnectionError as exc:
            return {"error": str(exc)}

        response = self._dispatcher.dispatch(phrase, tag)
        if response == ShutdownHandler.EXIT_SIGNAL:
            response = "Goodbye."

        self._tts.speak(response)
        return {"response": response, "tag": tag, "confidence": round(confidence, 3)}

    def send_command(self, phrase: str) -> dict:
        return self._process_command(phrase)

    def get_status(self) -> dict:
        return {
            "brain_online":     self._client.is_running(),
            "speech_available": _SR,
        }

    def toggle_fullscreen(self) -> None:
        if self._window:
            self._window.toggle_fullscreen()

    def start_drag(self) -> None:
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            ctypes.windll.user32.ReleaseCapture()
            ctypes.windll.user32.PostMessageW(hwnd, 0x00A1, 2, 0)
        except Exception:
            pass

    def minimize(self) -> None:
        if self._window:
            self._window.minimize()

    def close(self) -> None:
        if self._window:
            self._window.destroy()


def main() -> None:
    api = JarvisAPI()

    threading.Thread(
        target=api._client.ensure_server_running,
        kwargs={"wait": 45.0},
        daemon=True,
    ).start()
    threading.Thread(
        target=api._dispatcher._handlers["applications"]._load_dynamic_apps,
        daemon=True,
    ).start()

    ui_html = str(Path(__file__).parent / "ui" / "index.html")

    win = webview.create_window(
        title="JARVIS",
        url=ui_html,
        js_api=api,
        width=540,
        height=540,
        min_size=(360, 360),
        background_color="#000000",
        text_select=False,
        frameless=True,
    )

    api.set_window(win)

    def on_shown():
        if api._wake:
            api._wake.start()

    webview.start(on_shown, debug=False)


if __name__ == "__main__":
    main()
