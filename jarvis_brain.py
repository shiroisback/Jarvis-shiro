from __future__ import annotations
import hashlib
import json
import os
import re
import socket
import sys
import time
from typing import Tuple

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

INTENTS: dict = {
    "intents": [
        {
            "tag": "salutation",
            "patterns": [
                "bonjour", "salut", "hello", "coucou", "hey", "bonsoir",
                "bonjour jarvis", "salut jarvis", "hello jarvis", "bjr", "slt",
                "good morning", "good evening", "rebonjour", "tu es là",
                "comment ça va", "comment tu vas", "ça va", "ça roule",
                "quoi de neuf", "comment vas tu", "tu vas bien", "la forme",
                "wesh", "hé jarvis", "eh jarvis", "réveille toi", "debout jarvis",
                "ouais comment ça va", "bien ou bien", "nickel",
            ],
        },
        {
            "tag": "heure_date",
            "patterns": [
                "quelle heure est-il", "quelle heure il est", "donne moi l heure",
                "il est quelle heure", "il est quel heure", "heure actuelle",
                "c est quoi l heure", "t as l heure", "donne l heure",
                "quelle est l heure", "quel jour on est", "on est quel jour",
                "on est quel jours", "quel jour sommes nous", "quel jour est on",
                "quelle date", "date du jour", "date d aujourd hui",
                "donne moi la date", "donne la date", "dis moi la date",
                "c est quel jour", "quel mois", "quel mois on est",
                "on est en quelle année", "jour de la semaine", "on est quel mois",
                "on est quel jour aujourd hui", "quel jour on est aujourd hui",
                "aujourd hui c est quel jour", "quel jour aujourd hui",
                "c est quoi comme jour aujourd hui",
                "démarre un chronomètre", "lance le chrono", "stoppe le chrono",
                "arrête le chrono", "minuteur", "rappelle moi dans",
                "timer", "compte à rebours", "lance un timer", "met un rappel",
            ],
        },
        {
            "tag": "system_info",
            "patterns": [
                "état du système", "santé du pc", "charge cpu",
                "utilisation processeur", "usage cpu", "charge processeur",
                "mémoire ram", "ram disponible", "ram utilisée", "utilisation ram",
                "espace disque", "disque dur", "température cpu", "température gpu",
                "niveau batterie", "état batterie", "autonomie restante",
                "charge de la batterie", "pc en surchauffe", "ventilateur",
                "performances système", "uptime",
            ],
        },
        {
            "tag": "applications",
            "patterns": [
                "ouvre chrome", "lance chrome", "ouvre firefox", "lance firefox",
                "ouvre edge", "ouvre le navigateur", "lance le navigateur",
                "ouvre le bloc notes", "lance notepad", "ouvre notepad",
                "ouvre visual studio", "lance vscode", "ouvre vscode",
                "ferme chrome", "quitte chrome", "ferme firefox",
                "ferme l application", "kill l appli", "tue le processus",
                "ouvre spotify", "lance spotify",
                "ouvre discord", "lance discord", "ouvre discorde", "lance discorde",
                "lance discord canary", "ouvre discord canary", "lance canary",
                "ouvre teams", "lance teams", "ouvre calculatrice",
                "lance l application", "ouvre le gestionnaire de tâches", "task manager",
            ],
        },
        {
            "tag": "multimedia",
            "patterns": [
                "monte le volume", "augmente le volume", "volume plus",
                "baisse le volume", "diminue le volume", "volume moins",
                "mets le volume à", "règle le volume à", "volume à",
                "mets le son à", "met le volume à", "fixe le volume à",
                "volume 50%", "volume 100%", "volume 20%",
                "coupe le son", "sourdine", "mute", "unmute",
                "remets le son", "rétablis le son", "mets en pause", "pause",
                "play", "reprends la lecture", "chanson suivante", "piste suivante",
                "next", "précédent", "chanson précédente", "stop la musique",
                "arrête la musique", "lance la musique", "mets de la musique",
                "quel morceau", "plein écran", "mode cinéma",
            ],
        },
        {
            "tag": "recherche_web",
            "patterns": [
                "cherche sur google", "google", "recherche internet",
                "cherche sur le web", "cherche", "trouve moi", "recherche",
                "wikipedia", "ouvre youtube", "cherche sur youtube", "youtube",
                "va sur le site", "ouvre le site", "navigue vers",
                "bing", "actualités", "les news", "les nouvelles",
                "restaurant proche", "restaurant le plus proche", "les plus proches",
                "restaurant autour", "café proche", "pharmacie proche",
                "trouve un restaurant", "cherche un restaurant", "où manger",
                "donne moi l adresse", "sort pour les restaurant",
                "proche du lycée", "proche de l école", "fais la recherche",
                "google maps", "maps", "itinéraire vers", "comment aller",
                "trajet vers", "plan pour aller",
            ],
        },
        {
            "tag": "fichiers",
            "patterns": [
                "crée une note", "crée note", "créé une note", "créer une note",
                "nouvelle note", "écris une note", "écrire une note", "note rapide",
                "prends note", "prend note", "prends une note", "prend une note",
                "prendre note", "prendre une note", "note :", "note",
                "crée un fichier", "ouvre le fichier", "liste le dossier",
                "liste les fichiers", "affiche le dossier", "contenu du dossier",
                "supprime le fichier", "efface le fichier",
                "renomme le fichier", "déplace le fichier",
                "crée un dossier", "nouveau dossier",
            ],
        },
        {
            "tag": "presentation",
            "patterns": [
                "je m'appelle", "je m appelle", "je m'appel", "mon nom est",
                "je suis", "moi c'est", "moi c est",
            ],
        },
        {
            "tag": "reseau",
            "patterns": [
                "état du réseau", "connexion internet", "suis je connecté",
                "test de connexion", "tester internet", "vérifier connexion",
                "ping google", "fais un ping", "test ping",
                "vitesse internet", "débit réseau", "état wifi", "wifi connecté",
                "quel réseau", "quel wifi", "quelle adresse ip",
                "mon ip", "adresse ip locale", "ip publique",
                "problème de connexion", "internet ne fonctionne pas",
            ],
        },
        {
            "tag": "discord_mod",
            "patterns": [
                "mute sur discord", "mute serveur discord", "sourdine discord",
                "mute la personne sur discord", "mute le tag", "mute le pseudo",
                "réduis au silence sur discord", "silence sur discord",
                "unmute sur discord", "unmute discord", "enlève la sourdine discord",
                "kik sur discord", "expulse du serveur", "vire du serveur discord",
                "ban sur discord", "bannir du serveur", "bannir discord",
                "timeout sur discord", "sanctionner discord", "sanction discord",
                "assourdir discord", "deafen discord",
                "mute serveur la personne", "mute vocal discord",
                "modération discord", "modère discord",
            ],
        },
        {
            "tag": "insulte",
            "patterns": [
                "connard", "con", "idiot", "stupide", "nul", "débile", "crétin",
                "imbécile", "abruti", "tais toi", "ferme la", "t es nul",
                "tu sers à rien", "inutile", "vas te faire", "va te faire",
                "t es con", "t es bête", "bête", "sale machine", "merde jarvis",
                "espèce de", "t es inutile", "tu fais rien", "tu comprends rien",
                "t es une merde", "ferme ta gueule", "ta gueule",
                "casse toi", "dégage", "nul à chier",
            ],
        },
        {
            "tag": "blague",
            "patterns": [
                "fais moi rire", "une blague", "blague", "joke",
                "raconte une blague", "tu connais des blagues",
                "dis moi quelque chose de drôle", "amuse moi",
                "dis moi un secret",
            ],
        },
        {
            "tag": "self_presentation",
            "patterns": [
                "qui es tu", "qui es-tu", "présente toi", "présente-toi",
                "dis moi qui tu es", "parle moi de toi", "tu es qui",
                "c est quoi jarvis", "c'est quoi jarvis", "jarvis c est quoi",
                "qui t a créé", "qui t'a créé", "qui est ton créateur",
                "qui t a fait", "qui t'a fait", "qui a créé jarvis",
                "qui a fait jarvis", "t es capable de quoi", "tu fais quoi",
                "qu est ce que tu fais", "qu est ce que tu sais faire",
                "tes capacités", "tu peux faire quoi", "tu peux quoi",
                "quelles sont tes fonctions", "liste tes fonctions",
                "comment tu t appelles", "ton nom", "tu t appelles comment",
                "t'appelles comment", "quel est ton nom",
                "tu sais faire quoi", "tes fonctionnalités",
            ],
        },
        {
            "tag": "meteo",
            "patterns": [
                "météo", "quel temps fait il", "il fait quel temps",
                "température extérieure", "météo aujourd hui",
                "météo demain", "prévisions météo", "météo de la semaine",
                "va t il pleuvoir", "est ce qu il pleut", "est ce qu il neige",
                "météo à paris", "météo à lyon", "météo locale",
                "vent aujourd hui", "humidité", "risque d orage",
            ],
        },
        {
            "tag": "calcul",
            "patterns": [
                "calcule", "combien font", "combien ça fait",
                "résultat de", "fais le calcul", "addition", "soustraction",
                "multiplication", "division", "racine carrée", "racine carré",
                "puissance", "pourcentage", "log de", "sin de", "cos de",
                "quel est le résultat", "donne moi le résultat",
                "combien vaut", "évalue",
                "fois", "multiplié par", "divisé par", "plus", "moins",
                "combien fait", "combien font", "calcul rapide",
            ],
        },
        {
            "tag": "spotify",
            "patterns": [
                "lance la playlist", "joue la playlist", "mets la playlist",
                "lance la playlist dev", "lance la playlist hype",
                "joue pnl", "mets pnl", "lance pnl",
                "joue jul", "mets jul", "lance jul",
                "joue moha", "mets moha", "lance moha",
                "joue moha la squal", "lance moha la squal",
                "mets de la musique spotify", "ouvre spotify sur",
                "joue sur spotify", "lance sur spotify",
                "playlist dev", "playlist hype",
                "mets la playlist en pause", "stop la playlist",
                "pause spotify", "arrête la playlist", "stoppe spotify",
                "pause la musique spotify",
            ],
        },
        {
            "tag": "arret",
            "patterns": [
                "au revoir", "bye", "adieu", "ciao", "à plus", "à bientôt",
                "see you", "bonne soirée", "bonne nuit jarvis",
                "éteins toi", "arrête toi", "stop jarvis", "ferme toi",
                "quitte", "ferme l assistant", "mode veille", "mise en veille",
                "éteins le pc", "redémarre le pc", "shutdown", "reboot",
                "hibernation", "verrouille l écran",
            ],
        },
    ]
}


class TextProcessor:
                                                                 

    _ACCENT_MAP = str.maketrans(
        "àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ",
        "aaaeeeeiioouuucAAAEEEEIIOOUUUC",
    )

    _STOPWORDS = frozenset({
        "le", "la", "les", "un", "une", "des", "de", "du", "d", "l",
        "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
        "me", "te", "se", "y", "en", "et", "ou", "mais", "donc",
        "or", "ni", "car", "que", "qui", "quoi", "dont", "où",
        "à", "au", "aux", "par", "pour", "sur", "sous", "dans",
        "avec", "sans", "entre", "vers", "chez", "the", "a", "an",
        "is", "it", "in", "on", "of", "to", "for",
        "s", "t", "ce", "est", "pas", "ne", "plus", "très", "bien",
    })

    def normalize(self, text: str) -> str:
        return text.lower().translate(self._ACCENT_MAP).strip()

    def tokenize(self, text: str) -> list[str]:
        normalized = self.normalize(text)
        tokens = re.findall(r"[a-z0-9]+", normalized)
        return [t for t in tokens if t not in self._STOPWORDS and len(t) > 1]

    def build_vocabulary(self, all_token_lists: list[list[str]]) -> list[str]:
        vocab: set[str] = set()
        for tokens in all_token_lists:
            vocab.update(tokens)
        return sorted(vocab)

    def to_bow(self, tokens: list[str], vocabulary: list[str]) -> list[float]:
        bow = [0.0] * len(vocabulary)
        for t in tokens:
            if t in vocabulary:
                bow[vocabulary.index(t)] = 1.0
        return bow

class IntentNet(nn.Module):                                                            
    def __init__(self, input_size: int, output_size: int) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_size, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, output_size),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.layers(x)


class IntentDataset(Dataset):
    def __init__(self, X: list[list[float]], y: list[int]) -> None:
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.X)

    def __getitem__(self, idx: int):
        return self.X[idx], self.y[idx]


class IntentClassifier:

    UNKNOWN = "inconnu"
    _CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_brain.cache")

    def __init__(
        self,
        threshold: float = 0.70,
        epochs: int = 300,
        lr: float = 1e-3,
        batch_size: int = 32,
        patience: int = 20,
        patience_delta: float = 1e-4,
        verbose: bool = True,
        force_retrain: bool = False,
    ) -> None:
        self.threshold = threshold
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.patience = patience
        self.patience_delta = patience_delta
        self.verbose = verbose

        self.vocabulary: list[str] = []
        self.tags: list[str] = []
        self.model: IntentNet | None = None
        self.processor = TextProcessor()
        self.device = torch.device("cpu")

        if not force_retrain and self._load_from_cache():
            return
        self._train()
        self._save_to_cache()


    def _fingerprint(self) -> str:
        raw = json.dumps(INTENTS, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _load_from_cache(self) -> bool:
        if not os.path.exists(self._CACHE_FILE):
            return False
        try:
            t0 = time.perf_counter()
            checkpoint = torch.load(self._CACHE_FILE, map_location=self.device, weights_only=False)
            if checkpoint.get("fingerprint") != self._fingerprint():
                if self.verbose:
                    print("[Jarvis] Training data changed, retraining.")
                return False
            self.vocabulary = checkpoint["vocabulary"]
            self.tags = checkpoint["tags"]
            self.model = IntentNet(len(self.vocabulary), len(self.tags)).to(self.device)
            self.model.load_state_dict(checkpoint["model_state"])
            self.model.eval()
            elapsed = (time.perf_counter() - t0) * 1000
            if self.verbose:
                print(f"[Jarvis] Model loaded from cache in {elapsed:.1f} ms.")
            return True
        except Exception as exc:
            if self.verbose:
                print(f"[Jarvis] Cache unreadable ({exc}), retraining.")
            return False

    def _save_to_cache(self) -> None:
        try:
            torch.save(
                {
                    "fingerprint": self._fingerprint(),
                    "vocabulary": self.vocabulary,
                    "tags": self.tags,
                    "model_state": self.model.state_dict(),
                },
                self._CACHE_FILE,
            )
        except Exception as exc:
            if self.verbose:
                print(f"[Jarvis] Warning: could not write cache ({exc}).")

    def _build_dataset(self) -> tuple[list[list[float]], list[int]]:
        intents = INTENTS["intents"]
        self.tags = [i["tag"] for i in intents]

        all_tokens: list[list[str]] = []
        samples: list[tuple[list[str], int]] = []

        for idx, intent in enumerate(intents):
            for pattern in intent["patterns"]:
                tokens = self.processor.tokenize(pattern)
                all_tokens.append(tokens)
                samples.append((tokens, idx))

        self.vocabulary = self.processor.build_vocabulary(all_tokens)

        X = [self.processor.to_bow(t, self.vocabulary) for t, _ in samples]
        y = [label for _, label in samples]
        return X, y

    def _train(self) -> None:
        t0 = time.perf_counter()
        X, y = self._build_dataset()
        dataset = IntentDataset(X, y)
        loader = DataLoader(
            dataset,
            batch_size=min(self.batch_size, len(dataset)),
            shuffle=True,
            drop_last=False,
            num_workers=0,
        )

        self.model = IntentNet(len(self.vocabulary), len(self.tags)).to(self.device)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(self.model.parameters(), lr=self.lr)

        if self.verbose:
            print(f"[Jarvis] Training — {len(self.vocabulary)} tokens, "
                  f"{len(self.tags)} intents, {len(dataset)} samples.")

        best_loss = float("inf")
        no_improvement = 0

        self.model.train()
        for epoch in range(1, self.epochs + 1):
            epoch_loss = 0.0
            for xb, yb in loader:
                xb, yb = xb.to(self.device), yb.to(self.device)
                optimizer.zero_grad(set_to_none=True)
                loss = criterion(self.model(xb), yb)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()

            avg_loss = epoch_loss / len(loader)

            if avg_loss < best_loss - self.patience_delta:
                best_loss = avg_loss
                no_improvement = 0
            else:
                no_improvement += 1
                if no_improvement >= self.patience:
                    if self.verbose:
                        print(f"  Early stop at epoch {epoch} (loss={avg_loss:.4f})")
                    break

            if self.verbose and epoch % 50 == 0:
                print(f"  Epoch {epoch:>4}/{self.epochs}  loss={avg_loss:.4f}")

        elapsed = time.perf_counter() - t0
        if self.verbose:
            print(f"[Jarvis] Training done in {elapsed:.2f}s.")
        self.model.eval()

    def predict(self, phrase: str) -> tuple[str, float]:
                                                                                        
        if self.model is None:
            raise RuntimeError("Model is not trained.")

        tokens = self.processor.tokenize(phrase)
        bow = self.processor.to_bow(tokens, self.vocabulary)
        x = torch.tensor([bow], dtype=torch.float32)

        with torch.no_grad():
            probs = torch.softmax(self.model(x), dim=1)
            confidence, predicted = torch.max(probs, dim=1)

        score = float(confidence.item())
        tag = self.tags[int(predicted.item())]
        return (self.UNKNOWN, score) if score < self.threshold else (tag, score)

    def top_k(self, phrase: str, k: int = 3) -> list[tuple[str, float]]:
                                                                      
        if self.model is None:
            raise RuntimeError("Model is not trained.")

        tokens = self.processor.tokenize(phrase)
        bow = self.processor.to_bow(tokens, self.vocabulary)
        x = torch.tensor([bow], dtype=torch.float32)

        with torch.no_grad():
            probs = torch.softmax(self.model(x), dim=1).squeeze(0)

        top = torch.topk(probs, k=min(k, len(self.tags)))
        return [(self.tags[int(i)], float(s)) for s, i in zip(top.values, top.indices)]

    def __repr__(self) -> str:
        return (f"IntentClassifier(vocab={len(self.vocabulary)}, "
                f"intents={len(self.tags)}, threshold={self.threshold:.0%})")
                                                                  

class BrainServer:
    PING = "__ping__"
    STOP = "__stop__"

    def __init__(self, host: str = "127.0.0.1", port: int = 62400,
                 force_retrain: bool = False) -> None:
        self.host = host
        self.port = port
        self.classifier = IntentClassifier(verbose=True, force_retrain=force_retrain)

    def run(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(8)
        print(f"[Jarvis] Server ready on {self.host}:{self.port}  (Ctrl+C to stop)")

        try:
            while True:
                conn, _ = srv.accept()
                with conn:
                    data = conn.recv(4096).decode("utf-8", errors="replace").strip()
                    if not data:
                        continue
                    if data == self.STOP:
                        conn.sendall(b"bye\n")
                        break
                    if data == self.PING:
                        conn.sendall(b"pong\n")
                        continue
                    tag, confidence = self.classifier.predict(data)
                    conn.sendall(f"{tag}|{confidence:.4f}\n".encode())
        except KeyboardInterrupt:
            pass
        finally:
            srv.close()
            print("[Jarvis] Server stopped.")


if __name__ == "__main__":
    args = sys.argv[1:]
    retrain = "--retrain" in args
    port = 62400
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    BrainServer(port=port, force_retrain=retrain).run()