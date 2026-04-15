<!-- GitHub-friendly markup: semantic HTML + tables; avoid inline styles (often stripped). -->

<h1 align="center">Baba</h1>
<p align="center">
  <sub>Local voice assistant for macOS · wake word · ASR · intent · actions</sub>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-261c46?style=for-the-badge&logo=apache&logoColor=white" alt="Apache 2.0" /></a>
  <img src="https://img.shields.io/badge/platform-macOS-000000?style=for-the-badge&logo=apple&logoColor=white" alt="macOS" />
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+" />
</p>

<p align="center">
  <kbd>Hey Jarvis</kbd> → hands-free session → speak naturally → <kbd>goodbye</kbd> to sleep
</p>

---

## Overview

**Baba** is a session-based, on-device–friendly voice pipeline for macOS: wake-word detection, speech-to-text, a small LLM for intent parsing (via **Ollama** by default), neural **TTS**, and pluggable **executors** (browser, notes, system helpers, optional **Claude** queries, and more).

<table>
  <thead>
    <tr>
      <th>Layer</th>
      <th>Role</th>
    </tr>
  </thead>
  <tbody>
    <tr><td><strong>Wake</strong></td><td>VAD + phrase — start a conversation session</td></tr>
    <tr><td><strong>ASR</strong></td><td><code>faster-whisper</code> — what you said</td></tr>
    <tr><td><strong>Intent</strong></td><td>LLM maps speech → structured action</td></tr>
    <tr><td><strong>Router</strong></td><td>Dispatches to the right executor</td></tr>
    <tr><td><strong>TTS</strong></td><td><code>edge-tts</code> — spoken feedback</td></tr>
  </tbody>
</table>

---

## Requirements

| Item | Notes |
|------|--------|
| **macOS** | Accessibility / mic permissions as prompted |
| **Python** | 3.10+ recommended |
| **Ollama** | Default intent model (e.g. `qwen2.5:7b`) — see `config.yaml` |
| **Anthropic** | Optional — copy `.env.example` → `.env` for Claude-backed features |

---

## Quick start

```bash
cd jarvis
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # add keys only if you use Claude / cloud features
python main.py
```

**Configure** behavior in `config.yaml` (wake phrase, Whisper model, TTS voice, session timeout, default browser, notes path, logging).

---

## Session flow

<ol>
  <li>Say the wake phrase (default: <strong>Hey Jarvis</strong>) — a session opens.</li>
  <li>Issue commands without repeating the wake word until you exit or idle out.</li>
  <li>Say <em>goodbye</em>, <em>that's all</em>, or other exit phrases from config — or wait for the silence timeout.</li>
</ol>

---

## Development

```bash
pytest
```

---

## Security & responsibility

This project can drive **real actions** on your machine (apps, browser, accessibility-related tooling). Run only in environments you trust, review executors before use, and keep **API keys out of git** (use `.env`, which is gitignored).

---

## License

Licensed under the **Apache License, Version 2.0**. See [`LICENSE`](LICENSE).

---

<p align="center">
  <sub>Built for clarity and hackability — PRs welcome.</sub>
</p>
