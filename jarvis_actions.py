from __future__ import annotations
import datetime
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
    def launch(cmd: list[str]) -> None:
        try:
            if SystemUtils.is_windows():
                subprocess.Popen(cmd, shell=False,
                                 creationflags=subprocess.DETACHED_PROCESS)
            else:
                subprocess.Popen(cmd, start_new_session=True)
        except FileNotFoundError:
            pass

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
        "{greeting}. Tout est en ordre, j'attends vos instructions.",
        "{greeting}. Qu'est-ce que je peux faire pour vous ?",
        "{greeting}. Je vous écoute.",
        "{greeting}. Prêt.",
    ]

    def handle(self, phrase: str) -> str:
        hour = datetime.datetime.now().hour
        if hour < self._MORNING_LIMIT:
            greeting = "Bonjour"
        elif hour < self._AFTERNOON_LIMIT:
            greeting = "Bonne après-midi"
        else:
            greeting = "Bonsoir"
        return random.choice(self._REPLIES).format(greeting=greeting)


class DateTimeHandler:
    _DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    _MONTHS = [
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]

    def handle(self, phrase: str) -> str:
        low = phrase.lower()
        now = datetime.datetime.now()

        if any(w in low for w in ("chrono", "minuteur", "timer", "rappelle")):
            return self._handle_timer(low)

        if any(w in low for w in ("date", "jour", "mois", "semaine", "année", "annee")):
            day_name = self._DAYS[now.weekday()]
            month_name = self._MONTHS[now.month - 1]
            return f"Nous sommes {day_name} {now.day} {month_name} {now.year}."

        return f"Il est {now.strftime('%H:%M:%S')}."

    def _handle_timer(self, low: str) -> str:
        match = re.search(r"(\d+)\s*(min|minute|sec|seconde|heure|h\b)", low)
        if not match:
            return "Precisez la durée, par exemple : rappelle moi dans 10 minutes."
        val = int(match.group(1))
        unit = match.group(2)
        if unit.startswith("sec"):
            secs = val
            label = "seconde(s)"
        elif unit.startswith("h"):
            secs = val * 3600
            label = "heure(s)"
        else:
            secs = val * 60
            label = "minute(s)"
        self._start_timer(secs)
        return f"Timer de {val} {label} lancé."

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
                    lines.append("Temperature sensors not available on this system.")
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
    _KNOWN_APPS: dict[str, list[str]] = {
        "chrome":       ["chrome", "google-chrome"],
        "firefox":      ["firefox"],
        "edge":         ["msedge", "microsoft-edge"],
        "notepad":      ["notepad", "gedit"],
        "vscode":       ["code"],
        "spotify":      ["spotify"],
        "discord":      ["discord"],
        "teams":        ["teams"],
        "calculatrice": ["calc", "gnome-calculator"],
        "explorateur":  ["explorer", "nautilus"],
        "taskmgr":      ["taskmgr", "gnome-system-monitor"],
    }

    def handle(self, phrase: str) -> str:
        low = phrase.lower()
        closing = any(w in low for w in ("ferme", "quitte", "kill", "arrête", "tue"))

        app_name, cmds = self._find_app(low)
        if not cmds:
            m = re.search(r"(?:lance|ouvre|démarre|ferme|quitte|kill)\s+(\w+)", low)
            if m:
                app_name = m.group(1)
                cmds = [m.group(1)]
            else:
                return "Aucune application reconnue dans cette commande."

        if closing:
            if SystemUtils.is_windows():
                os.system(f"taskkill /IM {cmds[0]}.exe /F >nul 2>&1")
            else:
                os.system(f"pkill -f {cmds[0]} 2>/dev/null")
            return f"{app_name.capitalize()} fermé."

        for cmd in cmds:
            try:
                SystemUtils.launch([cmd])
                return f"{app_name.capitalize()} lancé."
            except Exception:
                continue
        return f"Impossible de trouver {app_name} dans le PATH."

    def _find_app(self, low: str) -> tuple[str, list[str]]:
        for key, cmds in self._KNOWN_APPS.items():
            if key in low or any(c in low for c in cmds):
                return key, cmds
        return "", []


class MultimediaHandler:
    def handle(self, phrase: str) -> str:
        low = phrase.lower()

        if SystemUtils.is_windows():
            return self._handle_windows(low)
        return self._handle_linux(low)

    def _handle_windows(self, low: str) -> str:
        shell = "powershell -c \"$o = New-Object -ComObject WScript.Shell; $o.SendKeys([char]{key})\""

        if any(w in low for w in ("monte", "augmente", "plus")):
            os.system(shell.format(key=175))
            return "Volume augmenté."
        if any(w in low for w in ("baisse", "diminue", "moins")):
            os.system(shell.format(key=174))
            return "Volume diminué."
        if any(w in low for w in ("mute", "sourdine", "coupe")):
            os.system(shell.format(key=173))
            return "Son coupé."
        if any(w in low for w in ("unmute", "remets", "rétablis")):
            os.system(shell.format(key=173))
            return "Son rétabli."

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
            return f"Recherche YouTube : {query}"

        if "wikipedia" in low:
            query = SystemUtils.extract_after(phrase, "wikipedia", "cherche sur wikipedia")
            SystemUtils.open_url(f"https://fr.wikipedia.org/wiki/Special:Search/{quote_plus(query)}")
            return f"Recherche Wikipedia : {query}"

        query = SystemUtils.extract_after(
            phrase,
            "cherche sur google", "cherche sur le web", "recherche",
            "cherche", "google", "trouve moi", "fais la recherche",
        )
        if not query:
            query = phrase
        SystemUtils.open_url(f"https://www.google.com/search?q={quote_plus(query)}")
        return f"Recherche Google : {query}"

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
        "Pourquoi les plongeurs plongent-ils toujours en arriere ?\nParce que sinon ils tomberaient dans le bateau.",
        "Un homme entre dans une bibliotheque et demande : avez-vous des livres sur la paranoia ?\nLe bibliothecaire chuchote : ils sont juste derriere vous.",
        "Je connais une blague sur le papier. Elle est dechirante.",
        "Pourquoi Einstein etait-il mauvais en societe ? Parce qu'il ne pensait qu'a lui. E=mc2.",
        "Un developpeur rentre chez lui. Sa femme lui dit : va faire les courses, achete une baguette, et si tu vois des oeufs prends-en douze.\nIl revient avec douze baguettes.",
    ]

    _ABOUT = [
        "Je suis Jarvis, l'assistant de Shiro. Developpement local, zero cloud.",
        "Shiro m'a cree. Je tourne entierement sur cette machine, sans aucune connexion externe.",
        "Je suis un assistant en ligne de commande. Pas d'interface graphique, pas de serveur tiers.",
    ]

    def handle(self, phrase: str) -> str:
        low = phrase.lower()
        if any(w in low for w in ("qui", "quoi", "crée", "créé", "cree", "présente", "capable")):
            return random.choice(self._ABOUT)
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
            return f"Weather data unavailable for {city}. wttr.in opened."

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
            return f"Impossible de calculer : {expr.strip()}"


class ShutdownHandler:
    EXIT_SIGNAL = "__JARVIS_EXIT__"

    def handle(self, phrase: str) -> str:
        low = phrase.lower()

        if any(w in low for w in ("éteins le pc", "shutdown", "extinction")):
            cmd = "shutdown /s /t 30" if SystemUtils.is_windows() else "shutdown -h +1"
            os.system(cmd)
            return "Extinction dans 30 secondes."

        if any(w in low for w in ("redémarre", "reboot")):
            cmd = "shutdown /r /t 30" if SystemUtils.is_windows() else "shutdown -r +1"
            os.system(cmd)
            return "Redémarrage dans 30 secondes."

        if any(w in low for w in ("veille", "hibernation", "sleep")):
            if SystemUtils.is_windows():
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            else:
                os.system("systemctl suspend")
            return "Mise en veille."

        if any(w in low for w in ("verrouille", "verrou", "lock")):
            if SystemUtils.is_windows():
                os.system("rundll32.exe user32.dll,LockWorkStation")
            else:
                os.system("loginctl lock-session")
            return "Ecran verrouille."

        return self.EXIT_SIGNAL

class PresentationHandler:
    _REPLIES = [
        "Enchanté, {name}. Je suis là pour vous aider.",
        "Ravi de faire votre connaissance, {name}.",
        "Bonjour {name}. Je retiens votre nom.",
    ]

    def handle(self, phrase: str) -> str:
        name = SystemUtils.extract_after(
            phrase,
            "je m'appelle", "je m appelle", "je m'appel",
            "mon nom est", "je suis", "moi c'est", "moi c est",
        )
        if not name:
            return random.choice([
                "Enchanté. Je suis Jarvis.",
                "Ravi de faire votre connaissance.",
            ])
        return random.choice(self._REPLIES).format(name=name)

class UnknownHandler:
    _REPLIES = [
        "Je n'ai pas compris. Reformulez.",
        "Commande non reconnue.",
        "Je n'ai pas saisi. Essayez autrement.",
    ]

    def handle(self, phrase: str) -> str:
        return random.choice(self._REPLIES)


                                                                             
            
                                                                             

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
            "blague":        JokeHandler(),
            "meteo":         WeatherHandler(),
            "calcul":        CalculatorHandler(),
            "presentation":  PresentationHandler(),
            "arret":         ShutdownHandler(),
            "inconnu":       UnknownHandler(),
        }

    def dispatch(self, phrase: str, tag: str) -> str:
        handler = self._handlers.get(tag, self._handlers["inconnu"])
        try:
            return handler.handle(phrase)
        except Exception as exc:
            return f"Error in handler '{tag}': {exc}"