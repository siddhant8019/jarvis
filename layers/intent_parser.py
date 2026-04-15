"""Layer 3: Intent Parser using Claude API (primary) with Ollama fallback.

Takes transcribed text and classifies it into structured intents.
Supports multi-action commands like "Open WhatsApp and type hi how are you".
"""

import json
import os
import time

import anthropic
from dotenv import load_dotenv

from utils.logger import setup_logger

logger = setup_logger("baba.intent_parser")
load_dotenv()

VALID_ACTIONS = {
    "open_app", "close_app", "open_tab", "close_tab", "switch_tab",
    "write_note", "dictate_to_app", "query_claude", "read_screen",
    "system_control", "search_web", "unknown",
}

SYSTEM_PROMPT = """You are an intent classifier for a macOS voice assistant called Jarvis. Parse voice commands into a JSON array of actions to execute in order.

Action types:
- open_app: Launch or switch to an application (NOT for websites)
- close_app: Quit an application
- open_tab: Open a URL/website in browser
- close_tab: Close current browser tab
- switch_tab: Switch to a specific browser tab by index
- write_note: Write text to a note file
- dictate_to_app: Type/paste text into the currently focused application
- query_claude: Conversation, questions, greetings, chitchat, or anything needing AI
- read_screen: ONLY when user explicitly asks to read/describe/look at the screen
- system_control: Volume, brightness, do not disturb, sleep
- search_web: Search the web for something

Output a JSON object: {"actions": [...]}

Each action in the array:
{"action": "<type>", "target": "<app name or null>", "parameters": {"text": "<text or null>", "query": "<query or null>", "url": "<URL or null>", "setting": "<setting or null>", "value": "<value or null>", "index": "<tab index or null>"}, "confidence": 0.0-1.0, "requires_confirmation": false}

CRITICAL RULES:
- For COMPOUND commands like "Open WhatsApp and type hi", return MULTIPLE actions in the array
- Greetings, chitchat, questions → query_claude (NEVER read_screen)
- read_screen ONLY for "read my screen", "what's on my screen", "describe my screen"
- Website/URL → open_tab (put URL in parameters.url, browser name in target or null)
- "Open Gmail and send email to X saying Y" → [open_tab gmail.com, dictate_to_app with the email text]
- "Open WhatsApp and say hi" → [open_app WhatsApp, dictate_to_app "hi"]
- requires_confirmation=true ONLY for close_app and close_tab
- Output ONLY valid JSON. No explanation.

Examples:
"How's it going?" → {"actions":[{"action":"query_claude","target":null,"parameters":{"query":"How's it going?"},"confidence":0.95,"requires_confirmation":false}]}
"Open WhatsApp and type hello how are you" → {"actions":[{"action":"open_app","target":"WhatsApp","parameters":{},"confidence":0.95,"requires_confirmation":false},{"action":"dictate_to_app","target":null,"parameters":{"text":"hello how are you"},"confidence":0.95,"requires_confirmation":false}]}
"Open YouTube" → {"actions":[{"action":"open_tab","target":null,"parameters":{"url":"youtube.com"},"confidence":0.95,"requires_confirmation":false}]}
"Set volume to 50" → {"actions":[{"action":"system_control","target":null,"parameters":{"setting":"volume","value":50},"confidence":0.95,"requires_confirmation":false}]}"""

# Simpler prompt for Ollama fallback
OLLAMA_SYSTEM_PROMPT = """You are an intent classifier for a macOS voice assistant. Classify the command into JSON.

Action types: open_app, close_app, open_tab, close_tab, switch_tab, write_note, dictate_to_app, query_claude, read_screen, system_control, search_web, unknown

Output: {"actions": [{"action": "<type>", "target": "<app/null>", "parameters": {"text": null, "query": null, "url": null, "setting": null, "value": null}, "confidence": 0.0-1.0, "requires_confirmation": false}]}

Rules:
- Greetings/questions → query_claude
- read_screen ONLY for "read/describe my screen"
- Website → open_tab with parameters.url
- Compound commands → multiple actions in array
- Output ONLY JSON."""


class IntentParser:
    """Parses transcribed text into structured intents.

    Uses Claude API as primary parser (faster + smarter), falls back to
    local Ollama if Claude is unavailable.
    """

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        temperature: float = 0,
        max_tokens: int = 256,
    ):
        self.ollama_model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._claude_client = None
        self._claude_available = False
        self._ollama_available = False

    def warmup(self):
        """Check Claude API availability and warm up Ollama as fallback."""
        # Check Claude API
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                self._claude_client = anthropic.Anthropic(api_key=api_key)
                # Quick test
                self._claude_client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=10,
                    messages=[{"role": "user", "content": "hi"}],
                )
                self._claude_available = True
                logger.info("Claude API available for intent parsing (haiku-4.5)")
            except Exception as e:
                logger.warning(f"Claude API not available: {e}")
                self._claude_client = None

        # Warm up Ollama as fallback
        if not self._claude_available:
            logger.info(f"Warming up Ollama fallback: {self.ollama_model}")
            try:
                import ollama
                ollama.chat(
                    model=self.ollama_model,
                    messages=[{"role": "user", "content": "test"}],
                    format="json",
                    options={"num_predict": 1},
                )
                self._ollama_available = True
                logger.info("Ollama warmed up as fallback")
            except Exception as e:
                logger.error(f"Ollama warmup failed: {e}")
        else:
            # Still warm up Ollama in case Claude fails later
            try:
                import ollama
                ollama.chat(
                    model=self.ollama_model,
                    messages=[{"role": "user", "content": "test"}],
                    format="json",
                    options={"num_predict": 1},
                )
                self._ollama_available = True
                logger.info(f"Ollama fallback ready: {self.ollama_model}")
            except Exception:
                pass

    def parse(self, transcription: str) -> list[dict]:
        """Parse transcribed text into a list of structured intents.

        Args:
            transcription: Raw transcribed text from ASR

        Returns:
            list of intent dicts (supports multi-action commands)
        """
        if not transcription or not transcription.strip():
            return [self._unknown_intent(transcription, reason="empty transcription")]

        start = time.time()
        logger.info(f"Parsing intent: '{transcription}'")

        # Try Claude first (faster + smarter)
        if self._claude_available:
            result = self._parse_with_claude(transcription)
            if result is not None:
                elapsed = time.time() - start
                logger.info(f"Intent parsed via Claude in {elapsed:.1f}s: {len(result)} action(s)")
                return result

        # Fall back to Ollama
        if self._ollama_available:
            result = self._parse_with_ollama(transcription)
            if result is not None:
                elapsed = time.time() - start
                logger.info(f"Intent parsed via Ollama in {elapsed:.1f}s: {len(result)} action(s)")
                return result

        # Both failed — route to query_claude as last resort
        logger.error("All parsers failed, routing to query_claude")
        return [{
            "event": "intent_parsed",
            "action": "query_claude",
            "target": None,
            "parameters": {"query": transcription},
            "confidence": 0.5,
            "requires_confirmation": False,
            "raw_transcription": transcription,
        }]

    def _parse_with_claude(self, transcription: str) -> list[dict] | None:
        """Parse using Claude API (Haiku for speed)."""
        try:
            response = self._claude_client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=self.max_tokens,
                temperature=0,
                messages=[{"role": "user", "content": transcription}],
                system=SYSTEM_PROMPT,
            )
            content = response.content[0].text
            return self._parse_response(content, transcription)
        except Exception as e:
            logger.warning(f"Claude intent parse failed: {e}")
            return None

    def _parse_with_ollama(self, transcription: str) -> list[dict] | None:
        """Parse using local Ollama."""
        try:
            import ollama
            response = ollama.chat(
                model=self.ollama_model,
                messages=[
                    {"role": "system", "content": OLLAMA_SYSTEM_PROMPT},
                    {"role": "user", "content": transcription},
                ],
                format="json",
                options={
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            )
            content = response["message"]["content"]
            return self._parse_response(content, transcription)
        except Exception as e:
            logger.warning(f"Ollama intent parse failed: {e}")
            return None

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Strip markdown code fences from LLM response."""
        import re
        # Match ```json ... ``` or ``` ... ```
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _parse_response(self, content: str, transcription: str) -> list[dict] | None:
        """Parse JSON response from either Claude or Ollama."""
        content = self._strip_markdown_fences(content)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON: {content[:200]}")
            return None

        # Handle both {"actions": [...]} and single-action format
        if "actions" in parsed and isinstance(parsed["actions"], list):
            actions_raw = parsed["actions"]
        else:
            actions_raw = [parsed]

        intents = []
        for raw in actions_raw:
            intent = self._normalize_intent(raw, transcription)
            intents.append(intent)

        if not intents:
            return None

        # If any action is unknown with low confidence, route whole thing to Claude
        for intent in intents:
            if intent["action"] == "unknown" or intent["confidence"] < 0.6:
                logger.info(f"Low confidence or unknown action — routing to query_claude")
                return [{
                    "event": "intent_parsed",
                    "action": "query_claude",
                    "target": None,
                    "parameters": {"query": transcription},
                    "confidence": 0.8,
                    "requires_confirmation": False,
                    "raw_transcription": transcription,
                }]

        return intents

    def _normalize_intent(self, parsed: dict, transcription: str) -> dict:
        """Validate and normalize a parsed intent."""
        action = parsed.get("action", "unknown")
        if action not in VALID_ACTIONS:
            corrected = self._fuzzy_match_action(action)
            if corrected != "unknown":
                logger.info(f"Corrected action '{action}' -> '{corrected}'")
            action = corrected

        confidence = parsed.get("confidence", 0.5)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        confidence = max(0.0, min(1.0, float(confidence)))

        target = parsed.get("target")
        if target in ("null", "None", ""):
            target = None

        parameters = parsed.get("parameters", {})
        if not isinstance(parameters, dict):
            parameters = {}

        requires_confirmation = parsed.get("requires_confirmation", False)
        if action in ("close_app", "close_tab"):
            requires_confirmation = True

        return {
            "event": "intent_parsed",
            "action": action,
            "target": target,
            "parameters": parameters,
            "confidence": confidence,
            "requires_confirmation": requires_confirmation,
            "raw_transcription": transcription,
        }

    @staticmethod
    def _fuzzy_match_action(action: str) -> str:
        """Fix common LLM misspellings of action names."""
        if action in VALID_ACTIONS:
            return action
        from difflib import get_close_matches
        matches = get_close_matches(action, VALID_ACTIONS, n=1, cutoff=0.6)
        return matches[0] if matches else "unknown"

    @staticmethod
    def _unknown_intent(transcription: str, reason: str = "") -> dict:
        """Return an unknown intent."""
        return {
            "event": "intent_parsed",
            "action": "unknown",
            "target": None,
            "parameters": {},
            "confidence": 0.0,
            "requires_confirmation": False,
            "raw_transcription": transcription or "",
            "error": reason,
        }
