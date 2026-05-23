from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path


class JarvisClient:
                                                                    

    PING_CMD = "__ping__"
    STOP_CMD = "__stop__"
    UNKNOWN  = "inconnu"

    def __init__(self, host: str = "127.0.0.1", port: int = 62400,
                 timeout: float = 2.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self._brain_path = Path(__file__).parent / "jarvis_brain.py"

    def is_running(self) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=0.3) as s:
                s.sendall(b"__ping__\n")
                return s.recv(16).strip() == b"pong"
        except OSError:
            return False

    def ensure_server_running(self, retrain: bool = False,
                              wait: float = 40.0) -> bool:
                                                                               
        if self.is_running():
            return True

        cmd = [sys.executable, str(self._brain_path), "--port", str(self.port)]
        if retrain:
            cmd.append("--retrain")

        kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True

        subprocess.Popen(cmd, **kwargs)

        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            if self.is_running():
                return True
            time.sleep(0.1)
        return False

    def ask(self, phrase: str) -> tuple[str, float]:
                                                                                                
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
                s.sendall((phrase.strip() + "\n").encode("utf-8"))
                raw = s.recv(256).decode("utf-8", errors="replace").strip()
            tag, _, conf_str = raw.partition("|")
            return tag, float(conf_str) if conf_str else 0.0
        except OSError as exc:
            raise ConnectionError(
                f"Brain server not reachable at {self.host}:{self.port}."
            ) from exc

    def stop_server(self) -> None:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
                s.sendall(b"__stop__\n")
        except OSError:
            pass

def _cli() -> None:
    client = JarvisClient()
    args = sys.argv[1:]

    if "--stop" in args:
        client.stop_server()
        print("Stop signal sent to the server.")
        return

    if "--ping" in args:
        status = "online" if client.is_running() else "offline"
        print(f"Server is {status}.")
        return

    if not client.is_running():
        print("Server not running, starting in background...", flush=True)
        if not client.ensure_server_running():
            print("Failed to start the server.")
            sys.exit(1)
        print("Server ready.\n")

    if args:
        phrase = " ".join(args)
        t0 = time.perf_counter()
        tag, conf = client.ask(phrase)
        ms = (time.perf_counter() - t0) * 1000
        print(f"{tag:<20} {conf:>6.1%}  ({ms:.1f} ms)")
        return

    while True:
        try:
            phrase = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not phrase:
            continue
        if phrase.lower() in ("quit", "exit", "q"):
            break
        t0 = time.perf_counter()
        try:
            tag, conf = client.ask(phrase)
        except ConnectionError as exc:
            print(f"  Error: {exc}")
            continue
        ms = (time.perf_counter() - t0) * 1000
        print(f"  {tag:<20} {conf:>6.1%}  ({ms:.1f} ms)\n")


if __name__ == "__main__":
    _cli()