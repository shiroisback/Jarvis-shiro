from __future__ import annotations
import sys
import time

from jarvis_client import JarvisClient
from jarvis_actions import ActionDispatcher, ShutdownHandler


BANNER = """
  Jarvis - by Shiro
"""

class Jarvis:
    def __init__(self, retrain: bool = False) -> None:
        self._client = JarvisClient()
        self._dispatcher = ActionDispatcher()
        self._retrain = retrain

    def start(self) -> None:
        if not self._client.is_running():
            print("Starting brain server...", flush=True)
            ok = self._client.ensure_server_running(retrain=self._retrain, wait=40.0)
            if not ok:
                print("Failed to start the brain server.")
                print("Run manually: py jarvis_brain.py")
                sys.exit(1)
            print("Server ready.\n")
        else:
            print("Brain server already running.\n")

        print(BANNER)
        self._loop()

    def _loop(self) -> None:
        while True:
            try:
                phrase = input("Vous > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nAu revoir.")
                break

            if not phrase:
                continue
            if phrase.lower() in ("quit", "exit", "q"):
                print("Au revoir.")
                break

            t0 = time.perf_counter()
            try:
                tag, confidence = self._client.ask(phrase)
            except ConnectionError:
                print("Brain server disconnected. Restart jarvis_brain.py.")
                continue
            ms = (time.perf_counter() - t0) * 1000

            response = self._dispatcher.dispatch(phrase, tag)

            if response == ShutdownHandler.EXIT_SIGNAL:
                print(f"\nAu revoir.  [{tag} {confidence:.0%} | {ms:.0f}ms]")
                break

            print(f"\n{response}\n")
            print(f"  [{tag}  {confidence:.0%}  {ms:.0f}ms]\n")


if __name__ == "__main__":
    retrain = "--retrain" in sys.argv
    Jarvis(retrain=retrain).start()