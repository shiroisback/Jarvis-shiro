"use strict";

const reactor = document.getElementById("arc-reactor");
const marks   = document.getElementById("marks-ring");

(function () {
    const frag = document.createDocumentFragment();
    for (let i = 0; i < 60; i++) {
        const li = document.createElement("li");
        li.style.transform      = `rotate(${i * 6}deg)`;
        li.style.animationDelay = `${-(i / 60) * 3}s`;
        frag.appendChild(li);
    }
    marks.appendChild(frag);
})();

function setReactor(mode) {
    reactor.classList.remove("listening", "processing");
    if (mode === "listening" || mode === "processing") {
        reactor.classList.add(mode);
    }
}

function showTranscript(_text) {}

function showResult(_res) {
    setReactor("standby");
}

function setStatus(_msg) {}

document.getElementById("reactor-wrap").addEventListener("mousedown", e => {
    if (e.button !== 0) return;
    window.pywebview.api.start_drag();
});

document.addEventListener("keydown", e => {
    if (e.key === "F11") {
        e.preventDefault();
        window.pywebview.api.toggle_fullscreen();
    }
});
