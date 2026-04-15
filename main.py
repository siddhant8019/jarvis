"""Baba — Local Voice-Controlled macOS Assistant.

Orchestrator with session-based conversation mode:
- Say "Hey Jarvis" to start a session
- Speak commands freely — no wake word needed between commands
- Say "goodbye" / "that's all" / etc. to end the session
- Session auto-ends after 2 minutes of silence
"""

import sys
import os
import re
import time

sys.path.insert(0, os.path.dirname(__file__))

from utils.logger import setup_logger, load_config
from utils.permissions import check_all_permissions
from utils.sounds import beep, soft_beep, double_beep, descending_beep
from layers.wake_word import WakeWordDetector
from layers.asr import ASREngine
from layers.intent_parser import IntentParser
from layers.action_router import ActionRouter
from layers.tts import TTSEngine
from executors.claude_query import clear_history as clear_claude_history

logger = setup_logger("baba")

# Strip wake word prefix from transcriptions
WAKE_WORD_STRIP = re.compile(r"^(hey\s+jarvis[,.\s]*)", re.IGNORECASE)


class Orchestrator:
    """Session-based voice assistant orchestrator."""

    def __init__(self):
        config = load_config()
        self.cfg = config["baba"]

        self.tts = TTSEngine(
            voice=self.cfg["tts"]["voice"],
            rate=self.cfg["tts"]["rate"],
        )
        self.detector = WakeWordDetector(
            sensitivity=self.cfg["wake_word"]["sensitivity"],
        )
        self.asr = ASREngine(
            model_name=self.cfg["asr"]["model"],
            silence_threshold_seconds=self.cfg["asr"]["silence_threshold_seconds"],
            max_recording_seconds=self.cfg["asr"]["max_recording_seconds"],
        )
        self.parser = IntentParser(
            model=self.cfg["llm"]["model"],
            temperature=self.cfg["llm"]["temperature"],
            max_tokens=self.cfg["llm"]["max_tokens"],
        )
        self.router = ActionRouter(self.cfg["actions"])

        # Session config
        session_cfg = self.cfg.get("session", {})
        self.session_timeout = session_cfg.get("timeout_seconds", 120)
        self.exit_phrases = session_cfg.get("exit_phrases", [
            "goodbye", "bye bye", "stop listening", "that's all",
            "go to sleep", "i'm done", "end session",
        ])

        self.in_session = False
        self.last_interaction = 0.0
        self.empty_count = 0  # consecutive no-speech results

    def boot(self):
        """Initialize all components."""
        logger.info("=== Baba starting ===")

        # Start TTS phrase caching in background immediately
        self.tts.precache()

        logger.info("Checking macOS permissions...")
        perms = check_all_permissions(speak_func=self.tts.speak_sync)
        if not perms.get("Accessibility"):
            logger.error("Accessibility permission required.")
            self.tts.speak_sync("Accessibility permission is missing.")
            sys.exit(1)

        logger.info("Warming up intent parser...")
        self.parser.warmup()

        logger.info("=== Baba ready ===")
        self.tts.speak_sync("Jarvis is ready.")

    def _is_exit_phrase(self, text: str) -> bool:
        """Check if text is a session-ending phrase."""
        words = text.split()
        if len(words) > 7:
            return False
        text_lower = text.lower().strip()
        for phrase in self.exit_phrases:
            if phrase in text_lower:
                return True
        return False

    def _strip_wake_word(self, text: str) -> str:
        """Remove 'Hey Jarvis' prefix from transcription if present."""
        return WAKE_WORD_STRIP.sub("", text).strip()

    def _end_session(self):
        """End the current conversation session."""
        self.in_session = False
        self.empty_count = 0
        clear_claude_history()
        descending_beep()
        self.tts.speak_sync("Session ended. Say hey Jarvis when you need me.")
        logger.info("Session ended")

    def _process_command(self, text: str):
        """Parse into one or more intents, execute each in sequence."""
        print(f"  Parsing intent...")
        intents = self.parser.parse(text)

        for i, intent in enumerate(intents):
            action = intent["action"]
            target = intent.get("target")
            if len(intents) > 1:
                print(f"  Step {i+1}/{len(intents)}: {action} (target={target})")
            else:
                print(f"  Intent: {action} (target={target}, confidence={intent['confidence']})")

            if action == "unknown":
                self.tts.speak_sync(f"I heard: {text}. But I don't know what to do with that.")
                return

            # Confirmation for destructive actions
            if intent.get("requires_confirmation"):
                desc = f"{action} {target}" if target else action
                self.tts.speak_sync(f"I'm about to {desc}. Should I proceed?")
                print("  Waiting for confirmation...")
                beep()
                confirm_result = self.asr.record_and_transcribe()
                confirm_text = confirm_result["text"].lower()
                if any(w in confirm_text for w in ["yes", "yeah", "confirm", "go ahead", "do it", "sure"]):
                    print("  Confirmed.")
                else:
                    print(f'  Cancelled (heard: "{confirm_result["text"]}")')
                    self.tts.speak_sync("Cancelled.")
                    return

            # Execute
            print(f"  Executing {action}...")
            result = self.router.execute(intent)
            success = result.get("success", False)
            message = result.get("message") or result.get("response") or "Done."

            if success:
                print(f"  Result: {message}")
            else:
                print(f"  Failed: {message}")

            # Only speak for the last action, or if something failed
            if i == len(intents) - 1 or not success:
                self.tts.speak_sync(message)
                if self.tts.barged_in:
                    print("  (User interrupted)")
                if not success:
                    return  # Stop executing remaining steps on failure
            else:
                # Brief pause between multi-step actions
                time.sleep(0.5)

    def run(self):
        """Main loop — wake word triggers session, session loops until exit."""
        self.boot()

        print()
        print("=" * 50)
        print("BABA — Voice Assistant (Jarvis)")
        print("Wake word: HEY JARVIS")
        print("Say 'goodbye' to end a session.")
        print("Press Ctrl+C to quit.")
        print("=" * 50)
        print()

        try:
            while True:
                if not self.in_session:
                    # --- IDLE: Wait for wake word ---
                    print("[Idle] Listening for 'Hey Jarvis'...")
                    try:
                        wake_result = self.detector.listen()
                    except KeyboardInterrupt:
                        raise

                    # Wake word detected — start session
                    self.in_session = True
                    self.last_interaction = time.time()
                    self.empty_count = 0
                    beep()
                    print("\n  Session started! Speak freely.")

                    # Check if wake word had trailing text (e.g. "Hey Jarvis, open Chrome")
                    trailing = wake_result.get("trailing_text", "")
                    if trailing and len(trailing.split()) >= 2:
                        print(f'  Wake word included command: "{trailing}"')
                        double_beep()
                        self._process_command(trailing)
                        print()
                    else:
                        self.tts.speak_sync("I'm listening.")

                # --- SESSION: Continuously listen for commands ---
                soft_beep()
                asr_result = self.asr.record_and_transcribe()
                text = asr_result["text"]

                if not text:
                    self.empty_count += 1
                    elapsed_since_last = time.time() - self.last_interaction

                    # Session timeout
                    if elapsed_since_last > self.session_timeout:
                        print("  Session timed out.")
                        self._end_session()
                        print()
                        continue

                    # Nudge once, then stay quiet
                    if self.empty_count == 1:
                        print("  No speech detected. Still listening...")
                    elif self.empty_count == 3:
                        self.tts.speak_sync("Are you still there?")
                    elif self.empty_count >= 5:
                        print("  Too many empty attempts, ending session.")
                        self._end_session()
                        print()
                    continue

                # Got speech — reset counters
                self.empty_count = 0
                self.last_interaction = time.time()
                double_beep()

                # Strip wake word if user said "Hey Jarvis open Chrome"
                text = self._strip_wake_word(text)
                print(f'  Heard: "{text}" ({asr_result["duration_seconds"]:.1f}s)')

                # Check for exit phrase
                if self._is_exit_phrase(text):
                    self._end_session()
                    print()
                    continue

                # Process the command
                self._process_command(text)
                print()

        except KeyboardInterrupt:
            print("\n\nBaba shutting down.")
            self.tts.speak_sync("Goodbye.")
            logger.info("=== Baba stopped ===")


def main():
    orchestrator = Orchestrator()
    orchestrator.run()


if __name__ == "__main__":
    main()
