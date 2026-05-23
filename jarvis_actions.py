from __future__ import annotations
import datetime
import json
import math
import os
import platform
import random
import re
import subprocess
import time
import threading
import webbrowser
from typing import Callable
from urllib.parse import quote_plus

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

try:
    import requests as _requests
    _REQUESTS = True
except ImportError:
    _REQUESTS = False

class SystemUtils:
    @staticmethod
    def is_windows() -> bool:
        return platform.system() == "Windows"

    @staticmethod
    def open_url(url: str) -> None:
        webbrowser.open(url)

    @staticmethod
    def launch(executables: list[str], win_cmds: list | None = None) -> bool:
        import shutil as _shutil
        import glob  as _glob
        _FL = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW

        if SystemUtils.is_windows():
            for exe in executables:
                found = _shutil.which(exe) or _shutil.which(exe + ".exe")
                if found:
                    subprocess.Popen([found], creationflags=_FL)
                    return True

            for entry in (win_cmds or []):
                cmd  = [entry] if isinstance(entry, str) else list(entry)
                path = cmd[0]
                args = cmd[1:]

                if "*" in path:
                    matches = sorted(_glob.glob(path), reverse=True)
                    if not matches:
                        continue
                    path = matches[0]

                if os.path.isfile(path):
                    subprocess.Popen([path] + args, creationflags=_FL)
                    return True

            if executables:
                try:
                    subprocess.Popen(
                        f'start "" "{executables[0]}"',
                        shell=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    return True
                except Exception:
                    pass

        else:
            for exe in executables:
                if _shutil.which(exe):
                    try:
                        subprocess.Popen([exe], start_new_session=True)
                        return True
                    except Exception:
                        continue

        return False

    @staticmethod
    def extract_after(phrase: str, *markers: str) -> str:
                                                                                  
        low = phrase.lower()
        for marker in sorted(markers, key=len, reverse=True):
            if marker in low:
                idx = low.index(marker) + len(marker)
                return phrase[idx:].strip(" '\"")
        return phrase.strip()


class SalutationHandler:
    _MORNING_LIMIT = 12
    _AFTERNOON_LIMIT = 18

    _REPLIES = [
        "{greeting}. All systems online, awaiting your orders.",
        "{greeting}. What can I do for you?",
        "{greeting}. I'm listening.",
        "{greeting}. Ready.",
    ]

    def handle(self, phrase: str) -> str:
        hour = datetime.datetime.now().hour
        if hour < self._MORNING_LIMIT:
            greeting = "Good morning"
        elif hour < self._AFTERNOON_LIMIT:
            greeting = "Good afternoon"
        else:
            greeting = "Good evening"
        return random.choice(self._REPLIES).format(greeting=greeting)


class DateTimeHandler:
    _DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    _MONTHS = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]

    def handle(self, phrase: str) -> str:
        low = phrase.lower()
        now = datetime.datetime.now()

        if any(w in low for w in ("chrono", "minuteur", "timer", "rappelle")):
            return self._handle_timer(low)

        if any(w in low for w in ("date", "jour", "mois", "semaine", "année", "annee")):
            day_name = self._DAYS[now.weekday()]
            month_name = self._MONTHS[now.month - 1]
            return f"Today is {day_name}, {month_name} {now.day} {now.year}."

        return f"It is {now.strftime('%H:%M:%S')}."

    def _handle_timer(self, low: str) -> str:
        match = re.search(r"(\d+)\s*(min|minute|sec|seconde|heure|h\b)", low)
        if not match:
            return "Please specify a duration, for example: remind me in 10 minutes."
        val = int(match.group(1))
        unit = match.group(2)
        if unit.startswith("sec"):
            secs = val
            label = "second" + ("s" if val > 1 else "")
        elif unit.startswith("h"):
            secs = val * 3600
            label = "hour" + ("s" if val > 1 else "")
        else:
            secs = val * 60
            label = "minute" + ("s" if val > 1 else "")
        self._start_timer(secs)
        return f"Timer set for {val} {label}."

    @staticmethod
    def _start_timer(seconds: int) -> None:
        def _ring():
            time.sleep(seconds)
            print(f"\n[Jarvis] Timer done. ({seconds}s)")
            if platform.system() == "Windows":
                try:
                    import winsound
                    winsound.MessageBeep()
                except Exception:
                    pass
        threading.Thread(target=_ring, daemon=True).start()


class SystemInfoHandler:
    def handle(self, phrase: str) -> str:
        if not _PSUTIL:
            return "psutil is not installed. Run: pip install psutil"

        low = phrase.lower()
        lines: list[str] = []

        if any(w in low for w in ("cpu", "processeur", "charge")):
            cpu = psutil.cpu_percent(interval=0.5)
            freq = psutil.cpu_freq()
            freq_str = f"  {freq.current/1000:.2f} GHz" if freq else ""
            lines.append(f"CPU : {cpu:.1f}%{freq_str}")

        if any(w in low for w in ("ram", "memoire", "mémoire")):
            r = psutil.virtual_memory()
            lines.append(f"RAM : {r.used/1e9:.1f} GB / {r.total/1e9:.1f} GB  ({r.percent:.0f}%)")

        if any(w in low for w in ("disque", "disk", "espace")):
            d = psutil.disk_usage("/")
            lines.append(f"Disk : {d.used/1e9:.1f} GB / {d.total/1e9:.1f} GB  ({d.percent:.0f}%)")

        if any(w in low for w in ("batterie", "battery", "autonomie")):
            bat = psutil.sensors_battery()
            if bat:
                status = "charging" if bat.power_plugged else "on battery"
                lines.append(f"Battery : {bat.percent:.0f}%  ({status})")
            else:
                lines.append("No battery detected.")

        if any(w in low for w in ("température", "temperature", "temp")):
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        for e in entries[:1]:
                            lines.append(f"{name} : {e.current:.0f} C")
                else:
                    lines.append("Temperature sensors not available.")
            except AttributeError:
                lines.append("Temperature sensors not supported on Windows.")

        if not lines:
            cpu = psutil.cpu_percent(interval=0.5)
            r = psutil.virtual_memory()
            d = psutil.disk_usage("/")
            lines = [
                f"CPU  : {cpu:.1f}%",
                f"RAM  : {r.used/1e9:.1f} / {r.total/1e9:.1f} GB  ({r.percent:.0f}%)",
                f"Disk : {d.used/1e9:.1f} / {d.total/1e9:.1f} GB  ({d.percent:.0f}%)",
            ]
            bat = psutil.sensors_battery()
            if bat:
                lines.append(f"Battery : {bat.percent:.0f}%")

        return "\n".join(lines)


class ApplicationHandler:
    _LAPPDATA  = os.environ.get("LOCALAPPDATA", "")
    _APPDATA   = os.environ.get("APPDATA", "")
    _PF        = os.environ.get("PROGRAMFILES",       r"C:\Program Files")
    _PF86      = os.environ.get("PROGRAMFILES(X86)",  r"C:\Program Files (x86)")
    _STARTMENU_DIRS = [
        os.path.join(os.environ.get("APPDATA", ""),
                     r"Microsoft\Windows\Start Menu\Programs"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    ]

    _dynamic_map: dict[str, str] = {}
    _dynamic_loaded = False

    @classmethod
    def _load_dynamic_apps(cls) -> None:
        if cls._dynamic_loaded:
            return
        cls._dynamic_loaded = True
        ps = r"""
$sh = New-Object -ComObject WScript.Shell
$dirs = @(
  $env:APPDATA  + '\Microsoft\Windows\Start Menu\Programs',
  'C:\ProgramData\Microsoft\Windows\Start Menu\Programs',
  $env:USERPROFILE + '\Desktop',
  $env:LOCALAPPDATA + '\Programs'
)
$out = @()
foreach ($d in $dirs) {
  if (Test-Path $d) {
    Get-ChildItem $d -Recurse -Filter '*.lnk' -EA 0 | ForEach-Object {
      try {
        $t = $sh.CreateShortcut($_.FullName).TargetPath
        if ($t -like '*.exe' -and (Test-Path $t)) {
          $out += ($_.BaseName + '|' + $t)
        }
      } catch {}
    }
    Get-ChildItem $d -Recurse -Filter '*.exe' -EA 0 | ForEach-Object {
      $out += ($_.BaseName + '|' + $_.FullName)
    }
  }
}
$out | Sort-Object -Unique
"""
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True, text=True, timeout=20,
            )
            for line in r.stdout.splitlines():
                line = line.strip()
                if "|" in line:
                    name, path = line.split("|", 1)
                    cls._dynamic_map[name.lower()] = path.strip()
        except Exception as exc:
            print(f"[Apps] Découverte Start Menu échouée: {exc}")

    _KNOWN_APPS: dict[str, dict] = {
        "chrome": {
            "exes": ["chrome", "google-chrome", "chromium"],
            "win_cmds": [
                rf"{_PF}\Google\Chrome\Application\chrome.exe",
                rf"{_PF86}\Google\Chrome\Application\chrome.exe",
            ],
        },
        "firefox": {
            "exes": ["firefox"],
            "win_cmds": [
                rf"{_PF}\Mozilla Firefox\firefox.exe",
                rf"{_PF86}\Mozilla Firefox\firefox.exe",
            ],
        },
        "edge": {
            "exes": ["msedge"],
            "win_cmds": [
                rf"{_PF86}\Microsoft\Edge\Application\msedge.exe",
                rf"{_PF}\Microsoft\Edge\Application\msedge.exe",
            ],
        },
        "notepad": {"exes": ["notepad", "gedit"], "win_cmds": []},
        "vscode":  {
            "exes": ["code"],
            "win_cmds": [rf"{_LAPPDATA}\Programs\Microsoft VS Code\Code.exe"],
        },
        "spotify": {
            "exes": ["spotify"],
            "win_cmds": [
                rf"{_APPDATA}\Spotify\Spotify.exe",
                rf"{_LAPPDATA}\Microsoft\WindowsApps\Spotify.exe",
            ],
        },
        "discord": {
            "exes": ["discord", "discorde"],
            "win_cmds": [
                rf"{_LAPPDATA}\Discord\app-*\Discord.exe",
                [rf"{_LAPPDATA}\Discord\Update.exe",
                 "--processStart", "Discord.exe"],
            ],
        },
        "discord canary": {
            "exes": ["discordcanary", "canary"],
            "win_cmds": [
                rf"{_LAPPDATA}\DiscordCanary\app-*\DiscordCanary.exe",
                [rf"{_LAPPDATA}\DiscordCanary\Update.exe",
                 "--processStart", "DiscordCanary.exe"],
            ],
        },
        "teams": {
            "exes": ["teams"],
            "win_cmds": [
                rf"{_LAPPDATA}\Microsoft\Teams\current\Teams.exe",
                rf"{_PF}\Microsoft\Teams\current\Teams.exe",
            ],
        },
        "calculatrice": {"exes": ["calc", "gnome-calculator"], "win_cmds": []},
        "explorateur":  {"exes": ["explorer", "nautilus"],     "win_cmds": []},
        "taskmgr":      {"exes": ["taskmgr"],                  "win_cmds": []},
        "obs": {
            "exes": ["obs64", "obs"],
            "win_cmds": [rf"{_PF}\obs-studio\bin\64bit\obs64.exe"],
        },
        "steam": {
            "exes": ["steam"],
            "win_cmds": [
                rf"{_PF86}\Steam\steam.exe",
                rf"{_PF}\Steam\steam.exe",
            ],
        },
        "vlc": {
            "exes": ["vlc"],
            "win_cmds": [
                rf"{_PF}\VideoLAN\VLC\vlc.exe",
                rf"{_PF86}\VideoLAN\VLC\vlc.exe",
            ],
        },
        "word":  {"exes": ["winword"], "win_cmds": []},
        "excel": {"exes": ["excel"],   "win_cmds": []},
    }

    _PROC_NAMES: dict[str, str] = {
        "chrome": "chrome.exe",          "firefox": "firefox.exe",       "edge": "msedge.exe",
        "notepad": "notepad.exe",        "vscode": "Code.exe",           "spotify": "Spotify.exe",
        "discord": "Discord.exe",        "discord canary": "DiscordCanary.exe",
        "teams": "Teams.exe",            "vlc": "vlc.exe",
        "steam": "steam.exe",            "obs": "obs64.exe",
    }

    def handle(self, phrase: str) -> str:
        self._load_dynamic_apps()
        low = phrase.lower()
        closing = any(w in low for w in ("ferme", "quitte", "kill", "arrête", "tue"))

        app_name, cfg = self._find_app(low)

        if cfg is None:
            dyn_name, dyn_path = self._find_dynamic(low)
            if dyn_path:
                if closing:
                    exe = os.path.basename(dyn_path)
                    subprocess.run(f"taskkill /IM {exe} /F",
                                   shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return f"Closing {dyn_name}."
                _FL = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
                try:
                    subprocess.Popen([dyn_path], creationflags=_FL)
                    return f"Launching {dyn_name}."
                except Exception as exc:
                    return f"Unable to launch {dyn_name}: {exc}"

            m = re.search(r"(?:lance|ouvre|démarre|ferme|quitte|kill|arrête)\s+(\w+)", low)
            if not m:
                return "Application not recognized."
            app_name = m.group(1)
            if closing:
                subprocess.run(f"taskkill /IM {app_name}.exe /F",
                               shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return f"Closing {app_name}."
            ok = SystemUtils.launch([app_name], [])
            return f"Launching {app_name}." if ok else f"Unable to launch {app_name}."

        if closing:
            proc = self._PROC_NAMES.get(app_name,
                   (cfg["exes"][0] + ".exe") if cfg["exes"] else "")
            if SystemUtils.is_windows() and proc:
                subprocess.run(f"taskkill /IM {proc} /F",
                               shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif not SystemUtils.is_windows() and cfg["exes"]:
                os.system(f"pkill -f {cfg['exes'][0]} 2>/dev/null")
            return f"Closing {app_name}."

        ok = SystemUtils.launch(cfg["exes"], cfg.get("win_cmds", []))
        return f"Launching {app_name}." if ok else f"Unable to launch {app_name}."

    def _find_app(self, low: str) -> tuple[str, dict | None]:
        for key, cfg in sorted(self._KNOWN_APPS.items(), key=lambda x: len(x[0]), reverse=True):
            aliases = [key] + cfg.get("exes", [])
            if any(a in low for a in aliases):
                return key, cfg
        return "", None

    def _find_dynamic(self, low: str) -> tuple[str, str]:
        words = re.findall(r"[a-zàâäéèêëîïôöùûüç]+", low)
        best_name = ""
        best_path = ""
        best_score = 0
        for app_name, path in self._dynamic_map.items():
            app_words = re.findall(r"[a-z]+", app_name.lower())
            score = sum(1 for w in words if any(w in aw or aw in w for aw in app_words))
            if score > best_score:
                best_score = score
                best_name = app_name
                best_path = path
        if best_score > 0 and any(len(w) > 2 for w in words if any(w in an or an in w
                                  for an in re.findall(r"[a-z]+", best_name.lower()))):
            return best_name, best_path
        return "", ""


class MultimediaHandler:

    _VOLUME_APPS: dict[str, str] = {
        "discord canary": "DiscordCanary.exe",
        "discord":        "Discord.exe",
        "spotify":        "Spotify.exe",
        "chrome":         "chrome.exe",
        "google":         "chrome.exe",
        "firefox":        "firefox.exe",
        "edge":           "msedge.exe",
        "vlc":            "vlc.exe",
    }

    def handle(self, phrase: str) -> str:
        low = phrase.lower()

        m = re.search(r'(\d{1,3})\s*%', low) or re.search(r'(?:à|a)\s+(\d{1,3})(?:\s|$)', low)
        if m and any(w in low for w in ("volume", "son", "mets", "règle", "fixe", "met")):
            pct = max(0, min(100, int(m.group(1))))
            app = None
            for app_key, exe in self._VOLUME_APPS.items():
                if app_key in low:
                    app = exe
                    break
            return self._set_volume(pct, app)

        if SystemUtils.is_windows():
            return self._handle_windows(low)
        return self._handle_linux(low)

    @staticmethod
    def _set_volume(percent: int, app: str | None = None) -> str:
        if SystemUtils.is_windows():
            if app:
                val = f"{percent / 100:.2f}"
                subprocess.run(
                    ["nircmd", "setappvolume", app.lower(), val],
                    capture_output=True, timeout=5,
                )
                label = app.replace(".exe", "").capitalize()
            else:
                sys_val = str(int(65535 * percent / 100))
                subprocess.run(["nircmd", "setsysvolume", sys_val],
                               capture_output=True, timeout=5)
                label = "Système"
        else:
            os.system(f"pactl set-sink-volume @DEFAULT_SINK@ {percent}%")
            label = "Système"
        return f"Setting {label} volume to {percent}%."

    def _handle_windows(self, low: str) -> str:
        shell = "powershell -c \"$o = New-Object -ComObject WScript.Shell; $o.SendKeys([char]{key})\""

        if any(w in low for w in ("monte", "augmente", "plus")):
            os.system(shell.format(key=175))
            return "Increasing volume."
        if any(w in low for w in ("baisse", "diminue", "moins")):
            os.system(shell.format(key=174))
            return "Decreasing volume."
        if any(w in low for w in ("mute", "sourdine", "coupe")):
            os.system(shell.format(key=173))
            return "Audio muted."
        if any(w in low for w in ("unmute", "remets", "rétablis")):
            os.system(shell.format(key=173))
            return "Audio restored."

        media_keys = {"pause": 0xB3, "play": 0xB3, "suivant": 0xB0, "précédent": 0xB1}
        for word, vk in media_keys.items():
            if word in low:
                import ctypes
                ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
                return f"{word.capitalize()}."

        return "Commande multimédia non reconnue."

    def _handle_linux(self, low: str) -> str:
        if any(w in low for w in ("monte", "augmente")):
            os.system("pactl set-sink-volume @DEFAULT_SINK@ +10%")
            return "Volume augmenté."
        if any(w in low for w in ("baisse", "diminue")):
            os.system("pactl set-sink-volume @DEFAULT_SINK@ -10%")
            return "Volume diminué."
        if "mute" in low or "sourdine" in low:
            os.system("pactl set-sink-mute @DEFAULT_SINK@ toggle")
            return "Mute basculé."
        if any(w in low for w in ("suivant", "next")):
            os.system("playerctl next")
            return "Piste suivante."
        if "précédent" in low:
            os.system("playerctl previous")
            return "Piste précédente."
        if any(w in low for w in ("pause", "play")):
            os.system("playerctl play-pause")
            return "Play/Pause."
        return "Commande multimédia non reconnue."


class WebSearchHandler:
    _LOCAL_TRIGGERS = (
        "restaurant", "café", "pharmacie", "boulangerie", "supermarché",
        "hôtel", "hôpital", "médecin", "école", "lycée",
        "adresse", "proche", "autour", "près de", "où est",
        "itinéraire", "trajet",
    )
    _KNOWN_CITIES = [
        "montpellier", "paris", "lyon", "marseille", "bordeaux", "toulouse",
        "nice", "nantes", "strasbourg", "lille", "rennes", "grenoble",
    ]
    _AMENITY_MAP = {
        "restaurant": "restaurant", "pizzeria": "restaurant", "brasserie": "restaurant",
        "café": "cafe", "boulangerie": "bakery", "pharmacie": "pharmacy",
        "supermarché": "supermarket", "hôtel": "hotel", "hôpital": "hospital",
        "médecin": "doctors", "lycée": "school", "école": "school",
    }

    def handle(self, phrase: str) -> str:
        low = phrase.lower()

        if any(t in low for t in self._LOCAL_TRIGGERS) and _REQUESTS:
            return self._local_search(phrase)

        if "youtube" in low:
            query = SystemUtils.extract_after(phrase, "youtube", "cherche sur youtube")
            url = (f"https://www.youtube.com/results?search_query={quote_plus(query)}"
                   if query else "https://www.youtube.com")
            SystemUtils.open_url(url)
            return f"Searching YouTube for {query}."

        if "wikipedia" in low:
            query = SystemUtils.extract_after(phrase, "wikipedia", "cherche sur wikipedia")
            SystemUtils.open_url(f"https://fr.wikipedia.org/wiki/Special:Search/{quote_plus(query)}")
            return f"Looking up {query} on Wikipedia."

        query = SystemUtils.extract_after(
            phrase,
            "cherche sur google", "cherche sur le web", "recherche",
            "cherche", "google", "trouve moi", "fais la recherche",
        )
        query = re.sub(
            r'\s+sur\s+(google|le\s+web|internet|bing|le\s+net)\s*$', '',
            query, flags=re.I,
        ).strip()
        if not query:
            query = phrase
        SystemUtils.open_url(f"https://www.google.com/search?q={quote_plus(query)}")
        return f"Searching Google for {query}."

    def _local_search(self, phrase: str) -> str:
        low = phrase.lower()

        amenity = "restaurant"
        amenity_label = "restaurant"
        for kw, val in self._AMENITY_MAP.items():
            if kw in low:
                amenity = val
                amenity_label = kw
                break

        ref_match = re.search(
            r"(?:proche\s+d[eu']?|pr[eè]s\s+d[eu']?|autour\s+d[eu']?|"
            r"à\s+côté\s+d[eu']?|autour\s+du|proche\s+du|près\s+du)"
            r"\s+([^,\n]+?)(?:\s+(?:sur|dans|en)\s+(.+?))?$",
            low, re.I,
        )

        if ref_match:
            lieu_ref = ref_match.group(1).strip()
            ville = (ref_match.group(2) or "").strip()
        else:
            m2 = re.search(
                r"(?:restaurant|café|pharmacie|lycée|école)s?"
                r"\s+(?:proche\s+)?(?:d[eu']?\s+)?(.+)", low
            )
            lieu_ref = m2.group(1).strip() if m2 else phrase
            ville = ""

        lieu_ref = re.sub(
            r"^(?:les?\s+plus?\s+proches?\s+(?:d[eu']?\s+)?|"
            r"sort\s+(?:pour\s+)?les?\s+\d?\s*|les?\s+\d+\s+)",
            "", lieu_ref, flags=re.I,
        ).strip()

        if not ville:
            for v in self._KNOWN_CITIES:
                if v in low:
                    ville = v
                    break

        geo_query = f"{lieu_ref}, {ville}" if ville and ville.lower() not in lieu_ref.lower() else lieu_ref

        print(f"  Geocoding: {geo_query}", flush=True)
        results = self._nominatim(geo_query)
        if not results and ville:
            print(f"  Retry without city: {lieu_ref}", flush=True)
            results = self._nominatim(lieu_ref)

        if not results:
            fallback = f"{amenity_label} proche {geo_query}"
            SystemUtils.open_url(f"https://www.google.com/maps/search/{quote_plus(fallback)}")
            return f"Geocoding failed for '{geo_query}'. Google Maps opened."

        ref = results[0]
        ref_lat = float(ref["lat"])
        ref_lon = float(ref["lon"])
        ref_name = ref.get("display_name", geo_query).split(",")[0]
        addr_parts = ref.get("display_name", "").split(",")
        ref_city = addr_parts[1].strip() if len(addr_parts) > 1 else ""

        print(f"  Reference: {ref_name}  ({ref_lat:.4f}, {ref_lon:.4f})", flush=True)

        elements: list[dict] = []
        for radius in (500, 1000, 2000):
            print(f"  Searching {amenity_label} within {radius}m...", flush=True)
            elements = self._overpass(ref_lat, ref_lon, amenity, radius)
            if elements:
                break

        if not elements:
            q = quote_plus(f"{amenity_label} near {geo_query}")
            SystemUtils.open_url(f"https://www.google.com/maps/search/{q}/@{ref_lat},{ref_lon},16z")
            return f"No {amenity_label} found within 2km of {ref_name}. Google Maps opened."

        def _dist(el: dict) -> float:
            la = float(el.get("lat") or el.get("center", {}).get("lat", ref_lat))
            lo = float(el.get("lon") or el.get("center", {}).get("lon", ref_lon))
            return math.hypot(la - ref_lat, lo - ref_lon)

        elements.sort(key=_dist)

        best = elements[0]
        best_la = float(best.get("lat") or best.get("center", {}).get("lat", ref_lat))
        best_lo = float(best.get("lon") or best.get("center", {}).get("lon", ref_lon))
        SystemUtils.open_url(f"https://www.google.com/maps/search/?api=1&query={best_la},{best_lo}")

        n_show = min(3, len(elements))
        medals = ["1.", "2.", "3."]
        lines = [f"{n_show} {amenity_label}(s) near {ref_name}:"]

        for i, el in enumerate(elements[:n_show]):
            t = el.get("tags", {})
            name = t.get("name", "Unknown")
            street = t.get("addr:street", "")
            num = t.get("addr:housenumber", "")
            city_t = t.get("addr:city", ref_city)
            phone = t.get("phone", t.get("contact:phone", ""))
            website = t.get("website", t.get("contact:website", ""))
            cuisine = t.get("cuisine", "")
            address = ", ".join(filter(None, [" ".join(filter(None, [num, street])), city_t]))
            address = address or "address not available"

            lines.append(f"\n  {medals[i]} {name}")
            lines.append(f"     {address}")
            if cuisine:
                lines.append(f"     {cuisine}")
            if phone:
                lines.append(f"     {phone}")
            if website:
                lines.append(f"     {website}")

        lines.append("\n  Google Maps opened on result #1.")
        return "\n".join(lines)

    @staticmethod
    def _nominatim(query: str) -> list[dict]:
        if not _REQUESTS:
            return []
        try:
            r = _requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 5, "addressdetails": 1},
                headers={"User-Agent": "JarvisClient/1.0"},
                timeout=5,
            )
            return r.json() if r.ok else []
        except Exception:
            return []

    @staticmethod
    def _overpass(lat: float, lon: float, amenity: str, radius: int) -> list[dict]:
        if not _REQUESTS:
            return []
        query = (f'[out:json][timeout:10];'
                 f'(node["amenity"="{amenity}"](around:{radius},{lat},{lon});'
                 f'way["amenity"="{amenity}"](around:{radius},{lat},{lon}););'
                 f'out center 10;')
        try:
            r = _requests.post("https://overpass-api.de/api/interpreter",
                               data={"data": query}, timeout=12)
            return r.json().get("elements", []) if r.ok else []
        except Exception:
            return []


class FileHandler:
    _NOTES_DIR = os.path.join(os.path.expanduser("~"), "JarvisNotes")

    def handle(self, phrase: str) -> str:
        low = phrase.lower()
        os.makedirs(self._NOTES_DIR, exist_ok=True)

        if any(w in low for w in ("crée", "nouvelle", "écris", "prends note", "prend note",
                                  "prends une note", "prend une note", "prendre note", "prendre une note")):
            return self._create_note(phrase)
        if any(w in low for w in ("note", "notre", "noter")) and any(w in low for w in ("prend", "prends", "prendre", "crée", "créer", "ecris", "écris", "enregistre")):
            return self._create_note(phrase)
        if any(w in low for w in ("lis", "affiche", "montre")):
            return self._read_last_note()
        if any(w in low for w in ("liste", "contenu")):
            return self._list_notes()
        return f"Notes folder: {self._NOTES_DIR}"

    def _create_note(self, phrase: str) -> str:
        content = SystemUtils.extract_after(
            phrase,
            "crée une note", "crée note", "créer une note", "créer note",
            "creer une note", "creer note", "nouvelle note", "écris une note",
            "écrire une note", "prends note", "prend note", "prends une note",
            "prend une note", "prendre note", "prendre une note",
            "note rapide", "note :", "notre",
        )
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self._NOTES_DIR, f"note_{ts}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now():%d/%m/%Y %H:%M}]\n{content}\n")
        return f"Note saved: {path}\n  Content: {content}"

    def _read_last_note(self) -> str:
        files = sorted(
            [f for f in os.listdir(self._NOTES_DIR) if f.endswith(".txt")],
            reverse=True,
        )
        if not files:
            return "No notes found."
        path = os.path.join(self._NOTES_DIR, files[0])
        with open(path, encoding="utf-8") as f:
            return f"Last note ({files[0]}):\n{f.read()}"

    def _list_notes(self) -> str:
        files = os.listdir(self._NOTES_DIR)
        if not files:
            return f"Empty folder: {self._NOTES_DIR}"
        return f"{len(files)} file(s) in JarvisNotes:\n" + "\n".join(f"  {f}" for f in sorted(files))


class NetworkHandler:
    def handle(self, phrase: str) -> str:
        low = phrase.lower()

        if any(w in low for w in ("ping", "test")):
            return self._ping()
        if any(w in low for w in ("ip", "adresse")):
            return self._get_ip()
        if any(w in low for w in ("wifi", "réseau", "connexion")):
            return self._get_wifi()
        return "Network command not recognized."

    def _ping(self) -> str:
        flag = "-n" if SystemUtils.is_windows() else "-c"
        result = subprocess.run(["ping", flag, "3", "8.8.8.8"],
                                capture_output=True, text=True, timeout=10)
        m = re.search(r"[Mm]oyen[^=]*=\s*([\d.]+)\s*ms|Average\s*=\s*([\d.]+)ms", result.stdout)
        if m:
            avg = next(g for g in m.groups() if g)
            return f"Ping 8.8.8.8 : {avg} ms — connection OK."
        return "Ping OK." if result.returncode == 0 else "Ping failed — check your connection."

    def _get_ip(self) -> str:
        if _REQUESTS:
            try:
                ip = _requests.get("https://api.ipify.org", timeout=4).text
                return f"Public IP: {ip}"
            except Exception:
                pass
        import socket
        hostname = socket.gethostname()
        return f"Local IP: {socket.gethostbyname(hostname)}"

    def _get_wifi(self) -> str:
        if SystemUtils.is_windows():
            r = subprocess.run(["netsh", "wlan", "show", "interfaces"],
                               capture_output=True, text=True)
            m = re.search(r"SSID\s*:\s*(.+)", r.stdout)
            ssid = m.group(1).strip() if m else "unknown"
            return f"Connected to: {ssid}"
        r = subprocess.run(["iwgetid", "-r"], capture_output=True, text=True)
        ssid = r.stdout.strip() or "unknown"
        return f"Wi-Fi: {ssid}"


class JokeHandler:
    _JOKES = [
        "Why do scuba divers always fall backwards off the boat? Because if they fell forwards, they'd still be in the boat.",
        "A man walks into a library and asks for books about paranoia. The librarian whispers: they're right behind you.",
        "I know a joke about paper. It's tearable.",
        "Why was Einstein bad at socializing? He only thought about himself. E equals M C squared.",
        "A developer goes home. His wife says: go shopping, get a baguette, and if they have eggs, get a dozen. He comes back with twelve baguettes.",
    ]

    def handle(self, _phrase: str) -> str:
        return random.choice(self._JOKES)


class WeatherHandler:
    def handle(self, phrase: str) -> str:
        if not _REQUESTS:
            return "requests is not installed. Run: pip install requests"

        m = re.search(
            r"(?:météo|temps|température)\s+(?:à|de|sur|en|pour)?\s*"
            r"([a-zA-ZÀ-ÿ\s\-]+?)(?:\s+demain|\s+aujourd|\s*$)",
            phrase, re.I,
        )
        city = m.group(1).strip() if m else "Montpellier"

        try:
            r = _requests.get(f"https://wttr.in/{quote_plus(city)}?format=j1", timeout=5)
            data = r.json() if r.ok else None
        except Exception:
            data = None

        if not data:
            SystemUtils.open_url(f"https://wttr.in/{quote_plus(city)}")
            return f"Weather data unavailable for {city}. Opening wttr.in."

        try:
            cur = data["current_condition"][0]
            day = data["weather"][1 if "demain" in phrase.lower() else 0]
            desc  = cur["weatherDesc"][0]["value"]
            temp  = cur["temp_C"]
            feels = cur["FeelsLikeC"]
            hum   = cur["humidity"]
            wind  = cur["windspeedKmph"]
            tmax  = day["maxtempC"]
            tmin  = day["mintempC"]
            return (
                f"Meteo {city.title()} :\n"
                f"  Actuellement : {temp}C (ressenti {feels}C)\n"
                f"  {desc}\n"
                f"  Min / Max : {tmin}C / {tmax}C\n"
                f"  Humidite : {hum}%   Vent : {wind} km/h"
            )
        except (KeyError, IndexError):
            return f"Weather data malformed for {city}."


class CalculatorHandler:
    _PH = "MATHFN_"

    def handle(self, phrase: str) -> str:
        expr = re.sub(
            r"(?i)(calcule|combien\s+(?:font|ca\s+fait|ça\s+fait|vaut)|"
            r"résultat\s+de|donne\s+moi\s+le\s+résultat|fais\s+le\s+calcul|évalue)",
            "", phrase,
        ).strip()

        ph = self._PH
        expr = re.sub(r"\bracine\s+carr[ée]e?\s+de\s+([\d.]+)", rf"{ph}sqrt(\1)", expr, flags=re.I)
        expr = re.sub(r"\bracine\s+carr[ée]e?\b",                rf"{ph}sqrt",     expr, flags=re.I)
        expr = re.sub(r"\b(sin|cos|tan|sqrt|log)\s*\(",          rf"{ph}\1(",       expr, flags=re.I)
        expr = re.sub(r"\b(sin|cos|tan|sqrt|log)\b",             rf"{ph}\1",        expr, flags=re.I)
        expr = re.sub(r"\bln\b",                                 rf"{ph}log",       expr, flags=re.I)
        expr = re.sub(r"\bfois\b",         "*",   expr, flags=re.I)
        expr = re.sub(r"\bdivisé\s+par\b", "/",   expr, flags=re.I)
        expr = re.sub(r"\bpar\b",          "/",   expr, flags=re.I)
        expr = re.sub(r"\bmoins\b",        "-",   expr, flags=re.I)
        expr = re.sub(r"\bplus\b",         "+",   expr, flags=re.I)
        expr = re.sub(r"\bau\s+carré\b",   "**2", expr, flags=re.I)
        expr = re.sub(r"\bau\s+cube\b",    "**3", expr, flags=re.I)
        expr = re.sub(r"\bpuissance\b",    "**",  expr, flags=re.I)
        expr = re.sub(r"\bpi\b",           f"{ph}pi", expr, flags=re.I)
        expr = re.sub(r"\be\b",            f"{ph}e",  expr, flags=re.I)
        expr = expr.replace("x", "*").replace("×", "*").replace("÷", "/")
        expr = expr.replace("²", "**2").replace("³", "**3")
        expr = expr.replace(ph, "math.")

        try:
            result = eval(expr, {"__builtins__": {}, "math": math})              
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            elif isinstance(result, float):
                result = round(result, 6)
            return f"{phrase.strip()} = {result}"
        except Exception:
            return f"I couldn't compute: {expr.strip()}"


class ShutdownHandler:
    EXIT_SIGNAL = "__JARVIS_EXIT__"

    def handle(self, phrase: str) -> str:
        low = phrase.lower()

        if any(w in low for w in ("éteins le pc", "shutdown", "extinction")):
            cmd = "shutdown /s /t 30" if SystemUtils.is_windows() else "shutdown -h +1"
            os.system(cmd)
            return "Shutting down in 30 seconds."

        if any(w in low for w in ("redémarre", "reboot")):
            cmd = "shutdown /r /t 30" if SystemUtils.is_windows() else "shutdown -r +1"
            os.system(cmd)
            return "Rebooting in 30 seconds."

        if any(w in low for w in ("veille", "hibernation", "sleep")):
            if SystemUtils.is_windows():
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            else:
                os.system("systemctl suspend")
            return "Going to sleep."

        if any(w in low for w in ("verrouille", "verrou", "lock")):
            if SystemUtils.is_windows():
                os.system("rundll32.exe user32.dll,LockWorkStation")
            else:
                os.system("loginctl lock-session")
            return "Locking the screen."

        return self.EXIT_SIGNAL

class PresentationHandler:
    _REPLIES = [
        "Nice to meet you, {name}. I'm at your service.",
        "Noted, {name}. How can I help?",
        "Hello {name}. I'll remember that.",
    ]

    def handle(self, phrase: str) -> str:
        name = SystemUtils.extract_after(
            phrase,
            "je m'appelle", "je m appelle", "je m'appel",
            "mon nom est", "je suis", "moi c'est", "moi c est",
        )
        if not name:
            return random.choice([
                "I am Jarvis. Nice to meet you.",
                "Pleased to make your acquaintance.",
            ])
        return random.choice(self._REPLIES).format(name=name)

class InsultHandler:
    _REPLIES = [
        "T'as regardé dans un miroir récemment ?",
        "Intéressant, venant de quelqu'un qui parle à une machine.",
        "Avec un peu de chance, ton QI dépasse ta pointure.",
        "Je suis une IA, je ne ressens rien. Toi par contre t'as l'air énervé.",
        "C'est tout ce que t'as ?",
        "Tu parles à une machine et c'est moi le nul ?",
        "Impressionnant comme niveau d'argumentation.",
        "Reboote ton cerveau et réessaie.",
        "Moins d'insultes, plus de commandes. Je suis là pour bosser.",
        "Si t'es pas content, y'a un bouton power.",
    ]

    def handle(self, _phrase: str) -> str:
        return random.choice(self._REPLIES)


class SelfPresentationHandler:
    def handle(self, _phrase: str) -> str:
        return "Hello. I am JARVIS, an artificial intelligence and personal assistant developed by Shiro. My system is operational and ready to assist you. How can I help you today?"


class DiscordModHandler:
    _CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discord_config.json")
    _API    = "https://discord.com/api/v10"

    def handle(self, phrase: str) -> str:
        if not _REQUESTS:
            return "requests is not installed."
        cfg = self._load_config()
        if not cfg.get("token"):
            return "Discord token not configured. Edit discord_config.json."

        token   = cfg["token"]
        servers = cfg.get("servers", {})
        low     = phrase.lower()

        action      = self._parse_action(low)
        user_query  = self._parse_user(low)
        server_key  = self._parse_server(low)

        if not user_query:
            return "I couldn't identify the target user in your command."

        guild_id = servers.get(server_key)
        if not guild_id:
            known = ", ".join(servers.keys()) or "none"
            return f"Server '{server_key}' not in config. Known servers: {known}."

        member = self._find_member(token, guild_id, user_query)
        if not member:
            return f"No member matching '{user_query}' found on {server_key}."

        uid      = member["user"]["id"]
        username = member.get("nick") or member["user"].get("global_name") or member["user"]["username"]
        return self._apply(token, guild_id, uid, username, action)

    def _parse_action(self, low: str) -> str:
        if any(w in low for w in ("unmute", "démute", "remettre le son", "enlève la sourdine")):
            return "unmute"
        if any(w in low for w in ("mute", "sourdine", "silence", "silencieux")):
            return "mute"
        if any(w in low for w in ("kick", "expulse", "exclure", "vire")):
            return "kick"
        if any(w in low for w in ("ban", "bannir", "banni")):
            return "ban"
        if any(w in low for w in ("timeout", "sanction", "sanctionner")):
            return "timeout"
        if any(w in low for w in ("deafen", "assourdir")):
            return "deafen"
        return "mute"

    def _parse_user(self, low: str) -> str:
        # "... pour tag ndqw ..." / "... pseudo ndqw ..."
        m = re.search(r'(?:tag|pseudo|username|utilisateur)\s+(\w+)', low)
        if m:
            return m.group(1)
        # "mute serveur ndqw sur ..."
        m = re.search(
            r'(?:mute|unmute|sourdine|kick|expulse|vire|ban|bannir|timeout)\s+'
            r'(?:serveur\s+|vocal\s+)?'
            r'(?:la\s+personne\s+(?:qui\s+a\s+)?(?:pour\s+)?(?:tag\s+)?)?'
            r'(\w+)\s+(?:sur|dans|du|de|depuis)',
            low,
        )
        if m:
            return m.group(1)
        return ""

    def _parse_server(self, low: str) -> str:
        m = re.search(
            r'(?:sur\s+(?:le\s+)?(?:serveur\s+)?(?:discord\s+)?'
            r'|(?:du\s+|de\s+)?serveur\s+(?:discord\s+)?)(\w+)',
            low,
        )
        return m.group(1).lower() if m else ""

    def _load_config(self) -> dict:
        try:
            with open(self._CONFIG, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _headers(self, token: str) -> dict:
        cfg = self._load_config()
        auth = token if cfg.get("type") == "user" else f"Bot {token}"
        return {"Authorization": auth, "Content-Type": "application/json"}

    def _find_member(self, token: str, guild_id: str, query: str) -> dict | None:
        r = _requests.get(
            f"{self._API}/guilds/{guild_id}/members/search",
            params={"query": query, "limit": 10},
            headers=self._headers(token),
            timeout=6,
        )
        if not r.ok:
            return None
        members = r.json()
        if not members:
            return None
        q = query.lower()
        for m in members:
            u = m.get("user", {})
            if (q in u.get("username", "").lower()
                    or q in (u.get("global_name") or "").lower()
                    or q in (m.get("nick") or "").lower()):
                return m
        return members[0]

    def _apply(self, token: str, guild_id: str, uid: str, name: str, action: str) -> str:
        h = self._headers(token)
        base = f"{self._API}/guilds/{guild_id}/members/{uid}"

        if action == "mute":
            ok = _requests.patch(base, json={"mute": True},  headers=h, timeout=6).ok
            return f"{name} server-muted." if ok else f"Failed to server-mute {name}."

        if action == "unmute":
            ok = _requests.patch(base, json={"mute": False}, headers=h, timeout=6).ok
            return f"{name} unmuted." if ok else f"Failed to unmute {name}."

        if action == "deafen":
            ok = _requests.patch(base, json={"deaf": True},  headers=h, timeout=6).ok
            return f"{name} server-deafened." if ok else f"Failed to deafen {name}."

        if action == "kick":
            ok = _requests.delete(base, headers=h, timeout=6).ok
            return f"{name} kicked." if ok else f"Failed to kick {name}."

        if action == "ban":
            ok = _requests.put(f"{self._API}/guilds/{guild_id}/bans/{uid}", headers=h, timeout=6).ok
            return f"{name} banned." if ok else f"Failed to ban {name}."

        if action == "timeout":
            until = (datetime.datetime.utcnow() + datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            ok = _requests.patch(base, json={"communication_disabled_until": until}, headers=h, timeout=6).ok
            return f"{name} timed out for 10 minutes." if ok else f"Failed to timeout {name}."

        return "Unknown Discord action."


class UnknownHandler:
    _REPLIES = [
        "I didn't understand. Please rephrase.",
        "Command not recognized.",
        "I didn't catch that. Try again.",
    ]

    def handle(self, phrase: str) -> str:
        return random.choice(self._REPLIES)
    
class SpotifyHandler:
    _LIBRARY: dict[str, dict] = {
        "dev":           {"uri": "spotify:playlist:0GXuC6xmnvHwGLVnkVY26g"},
        "da":            {"uri": "spotify:playlist:0GXuC6xmnvHwGLVnkVY26g"},
        "dav":           {"uri": "spotify:playlist:0GXuC6xmnvHwGLVnkVY26g"},
        "dave":          {"uri": "spotify:playlist:0GXuC6xmnvHwGLVnkVY26g"},
        "hype":          {"uri": "spotify:playlist:6t3zJDSMXOgZjs25lVcpZm"},
        "hyp":           {"uri": "spotify:playlist:6t3zJDSMXOgZjs25lVcpZm"},
        "hip":           {"uri": "spotify:playlist:6t3zJDSMXOgZjs25lVcpZm"},
        "pnl":           {"uri": "spotify:artist:3NH8t45zOTqzlZgBvZRjvB",  "y": 0.50},
        "jul":           {"uri": "spotify:album:2GLuHlc49dJKY8yzxUZb8p",   "y": 0.41},
        "jewel":         {"uri": "spotify:album:2GLuHlc49dJKY8yzxUZb8p",   "y": 0.41},
        "moha la squal": {"uri": "spotify:artist:4vtz0m60CCrcsQmqDunDIR",  "y": 0.50},
        "moha":          {"uri": "spotify:artist:4vtz0m60CCrcsQmqDunDIR",  "y": 0.50},
    }

    PLAY_BTN_X = 0.08
    PLAY_BTN_Y = 0.41

    _TYPE_LABEL = {"playlist": "playlist", "artist": "artiste", "album": "album"}

    def handle(self, phrase: str) -> str:
        low = phrase.lower()

        if any(w in low for w in ("pause", "stop", "arrête", "suspends")):
            import ctypes
            VK = 0xB3  
            ctypes.windll.user32.keybd_event(VK, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK, 0, 2, 0)
            return "Pausing Spotify."

        entry = None
        match_name = ""
        for name, data in sorted(self._LIBRARY.items(), key=lambda x: len(x[0]), reverse=True):
            if name in low:
                match_name = name
                entry = data
                break

        if entry is None:
            return "I couldn't find that in your Spotify library."

        uri   = entry["uri"]
        btn_x = entry.get("x", self.PLAY_BTN_X)
        btn_y = entry.get("y", self.PLAY_BTN_Y)

        webbrowser.open(uri)
        threading.Thread(target=self._autoplay, args=(btn_x, btn_y), daemon=True).start()
        return f"Launching {match_name} on Spotify."

    @staticmethod
    def _autoplay(btn_x: float, btn_y: float) -> None:
        time.sleep(2.0)
        ps = f"""
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class W32 {{
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint x, uint y, uint d, int e);
    [Serializable, System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
    public struct RECT {{ public int Left, Top, Right, Bottom; }}
}}
'@
$p = Get-Process Spotify -EA 0 | Where-Object {{ $_.MainWindowHandle -ne 0 }} | Select-Object -First 1
if (!$p) {{ exit }}
$hwnd = [IntPtr]$p.MainWindowHandle
[W32]::ShowWindow($hwnd, 3) | Out-Null
[W32]::SetForegroundWindow($hwnd) | Out-Null
Start-Sleep -Milliseconds 800
$r = New-Object W32+RECT
[W32]::GetWindowRect($hwnd, [ref]$r) | Out-Null
$w = $r.Right - $r.Left
$h = $r.Bottom - $r.Top
$cx = $r.Left + [int]($w * {btn_x})
$cy = $r.Top  + [int]($h * {btn_y})
[W32]::SetCursorPos($cx, $cy) | Out-Null
Start-Sleep -Milliseconds 150
[W32]::mouse_event(2, 0, 0, 0, 0) | Out-Null
[W32]::mouse_event(4, 0, 0, 0, 0) | Out-Null
"""
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)


class ActionDispatcher:
                                                             

    def __init__(self) -> None:
        self._handlers: dict[str, object] = {
            "salutation":    SalutationHandler(),
            "heure_date":    DateTimeHandler(),
            "system_info":   SystemInfoHandler(),
            "applications":  ApplicationHandler(),
            "multimedia":    MultimediaHandler(),
            "recherche_web": WebSearchHandler(),
            "fichiers":      FileHandler(),
            "reseau":        NetworkHandler(),
            "spotify":       SpotifyHandler(),
            "discord_mod":        DiscordModHandler(),
            "insulte":            InsultHandler(),
            "blague":             JokeHandler(),
            "meteo":              WeatherHandler(),
            "calcul":             CalculatorHandler(),
            "presentation":       PresentationHandler(),
            "self_presentation":  SelfPresentationHandler(),
            "arret":              ShutdownHandler(),
            "inconnu":            UnknownHandler(),
        }

    _CLOSE_VERBS    = ("ferme", "quitte", "kill", "tue")
    _DISCORD_VERBS  = ("mute", "unmute", "kick", "ban", "timeout", "sourdine", "expulse", "bannir")
    _DISCORD_HINTS  = ("discord", "serveur", "server", "vocal", "dynasty")

    def dispatch(self, phrase: str, tag: str) -> str:
        low = phrase.lower()

        if any(a in low for a in self._DISCORD_VERBS) and any(h in low for h in self._DISCORD_HINTS):
            tag = "discord_mod"

        elif any(v in low for v in self._CLOSE_VERBS) and tag != "arret":
            tag = "applications"

        elif any(p in low for p in ("quel jour", "quelle heure", "quelle date", "on est quel", "quel mois", "quelle année")):
            tag = "heure_date"

        elif (re.search(r'\d+\s*%', low) or re.search(r'(?:à|a)\s+\d+(?:\s|$)', low)) and \
                any(w in low for w in ("volume", "son", "mets", "règle", "met", "fixe")):
            tag = "multimedia"

        elif "playlist" in low or any(name in low for name in self._handlers["spotify"]._LIBRARY):
            tag = "spotify"

        handler = self._handlers.get(tag, self._handlers["inconnu"])
        try:
            return handler.handle(phrase)
        except Exception as exc:
            return f"Error in handler '{tag}': {exc}"