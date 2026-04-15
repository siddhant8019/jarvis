<div align="center">

```
 ____        _
| __ )  __ _| |__   __ _
|  _ \ / _` | '_ \ / _` |
| |_) | (_| | |_) | (_| |
|____/ \__,_|_.__/ \__,_|

 ╭──────────────────────────────╮
 │  "Hey Jarvis"  →  🎙️  →  🧠  →  ⚡  │
 ╰──────────────────────────────╯
```

**Local voice assistant for macOS**<br>
Wake word · ASR · Intent parsing · Actions · TTS

<br>

[![Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-261c46?style=for-the-badge&logo=apache&logoColor=white)](LICENSE)
![macOS](https://img.shields.io/badge/platform-macOS-000000?style=for-the-badge&logo=apple&logoColor=white)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Ollama](https://img.shields.io/badge/LLM-Ollama-4B8BBE?style=for-the-badge)
![Whisper](https://img.shields.io/badge/ASR-Whisper-74AA9C?style=for-the-badge)

<br>

<kbd>Hey Jarvis</kbd> &nbsp;→&nbsp; hands-free session &nbsp;→&nbsp; speak naturally &nbsp;→&nbsp; <kbd>goodbye</kbd> to sleep

</div>

<br>

---

<br>

## What it does

**Baba** is a session-based, on-device voice pipeline for macOS. Say a wake word, talk naturally, and your Mac does what you asked. No cloud required (Claude is optional).

```
You:    "Hey Jarvis"
Baba:   🔔 *beep* — Session started! Speak freely.

You:    "Open YouTube in Chrome"
Baba:   ⚡ Intent: open_browser (target=youtube.com)
        ✅ Done.

You:    "What's the weather like in San Francisco?"
Baba:   🧠 Routing to Claude...
        "Currently 62°F and partly cloudy in San Francisco."

You:    "Goodbye"
Baba:   📴 Session ended. Say Hey Jarvis when you need me.
```

<br>

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     BABA PIPELINE                    │
├──────────┬──────────┬──────────┬──────────┬─────────┤
│          │          │          │          │         │
│  🎤 Wake │  📝 ASR  │  🧠 Intent│  ⚡ Router│  🔊 TTS │
│   Word   │          │  Parser  │          │         │
│          │          │          │          │         │
│  VAD +   │ faster-  │  Ollama  │ Dispatch │ edge-   │
│  phrase  │ whisper  │  LLM     │ to exec  │ tts     │
│  detect  │          │          │          │         │
└──────────┴──────────┴──────────┴──────────┴─────────┘
     ↓           ↓           ↓           ↓
 "hey jarvis"  "open       {action:    browser.
  detected     youtube"    open_browser, open(yt)
                           target: yt}
```

<br>

### Layers

| Layer | What it does | Default engine |
|:------|:-------------|:---------------|
| **Wake** | VAD + phrase detection — starts a conversation session | `vad_whisper` |
| **ASR** | Speech-to-text — transcribes what you said | `faster-whisper` (`small.en`) |
| **Intent** | LLM maps natural language → structured action | `ollama` (`qwen2.5:7b`) |
| **Router** | Dispatches intent to the right executor | — |
| **TTS** | Neural text-to-speech — spoken feedback | `edge-tts` |

### Executors

| Executor | Examples |
|:---------|:---------|
| **Browser** | Open URLs, search the web |
| **Notes** | Append to a markdown notes file |
| **System** | Volume, brightness, app control |
| **Claude** | Complex questions via Anthropic API (optional) |

<br>

## Quick start

### Prerequisites

| Requirement | Notes |
|:------------|:------|
| **macOS** | Accessibility + mic permissions (prompted on first run) |
| **Python 3.10+** | Recommended |
| **Ollama** | Running locally with a model pulled (e.g. `qwen2.5:7b`) |
| **Anthropic API key** | Optional — only for Claude-backed features |

### Install & run

```bash
git clone https://github.com/siddhant8019/jarvis.git
cd jarvis

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: add your Anthropic key for Claude features
cp .env.example .env

python main.py
```

### Configure

Everything lives in **`config.yaml`** — wake phrase, Whisper model size, TTS voice, session timeout, default browser, notes path, and logging level.

<br>

## How a session works

```
          ┌──────────────┐
          │  IDLE MODE   │◄──────────────────────┐
          │  Listening    │                       │
          │  for wake word│                       │
          └──────┬───────┘                       │
                 │ "Hey Jarvis"                   │
                 ▼                                │
          ┌──────────────┐                       │
     ┌───►│   SESSION    │                       │
     │    │   ACTIVE     │                       │
     │    └──────┬───────┘                       │
     │           │ speech detected                │
     │           ▼                                │
     │    ┌──────────────┐                       │
     │    │  ASR → Intent │                       │
     │    │  → Execute    │                       │
     │    └──────┬───────┘                       │
     │           │                                │
     │           ├── more commands ──────►┘       │
     │           │                                │
     │           ├── "goodbye" ──────────────────►│
     │           │                                │
     │           └── 2min silence ──────────────►│
     │                                            │
     └── (loop back for next command)             │
                                                  │
```

1. **Say the wake phrase** (default: *Hey Jarvis*) — a session opens
2. **Speak commands freely** — no need to repeat the wake word
3. **End the session** — say *goodbye*, *that's all*, or just wait for the silence timeout

<br>

## Development

```bash
# Run tests
pytest

# Enable verbose logging
# Set logging.level to "DEBUG" in config.yaml
```

<br>

## Project structure

```
jarvis/
├── main.py              # Orchestrator — session loop
├── config.yaml          # All configuration
├── .env.example         # API key template
├── requirements.txt
├── layers/
│   ├── wake_word.py     # Wake word detection
│   ├── asr.py           # Speech-to-text
│   ├── intent_parser.py # LLM intent parsing
│   ├── action_router.py # Intent → executor dispatch
│   └── tts.py           # Text-to-speech
├── executors/
│   ├── browser.py       # Browser control
│   ├── notes.py         # Notes management
│   ├── system_control.py# System actions
│   └── claude_query.py  # Claude API queries
├── utils/
│   ├── logger.py        # Logging setup
│   ├── permissions.py   # macOS permission checks
│   └── sounds.py        # Audio feedback
└── tests/
```

<br>

## Security

> **This project drives real actions on your machine** — apps, browser, accessibility tooling.

- Run only in environments you trust
- Review executors before use
- API keys stay in `.env` (gitignored) — never committed

<br>

## Contributing

This is early-stage and rough around the edges. **That's the point.**

If you try it and something breaks, feels wrong, or could be better — [open an issue](https://github.com/siddhant8019/jarvis/issues). PRs are welcome.

Some areas where feedback would be especially useful:
- **Intent parsing accuracy** — does the LLM route correctly?
- **Session UX** — timeout behavior, exit phrases, audio cues
- **New executors** — what actions should Baba support?
- **Cross-platform** — interested in Linux/Windows support?

<br>

## License

Licensed under the [Apache License, Version 2.0](LICENSE).

<br>

---

<div align="center">
<sub>Built for clarity and hackability.</sub>
</div>
