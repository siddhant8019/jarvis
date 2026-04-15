"""Full Voice Pipeline Test — Wake Word to Execution.

This is the end-to-end test:
1. Say "HEY JARVIS"
2. Speak a command (e.g., "open Safari", "set volume to 50")
3. Watch it get transcribed, classified, and executed
4. Baba speaks the result back

Loops until you press Ctrl+C.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from layers.wake_word import WakeWordDetector
from layers.asr import ASREngine
from layers.intent_parser import IntentParser
from layers.action_router import ActionRouter
from layers.tts import TTSEngine
from utils.logger import setup_logger, load_config

logger = setup_logger("baba.test_pipeline")


def main():
    config = load_config()
    baba_cfg = config["baba"]

    print("=" * 50)
    print("BABA — Full Pipeline Test")
    print("Wake word: HEY JARVIS")
    print("=" * 50)
    print()
    print("Components loading...")

    # Init all layers
    tts = TTSEngine(
        voice=baba_cfg["tts"]["voice"],
        rate=baba_cfg["tts"]["rate"],
    )

    detector = WakeWordDetector(
        sensitivity=baba_cfg["wake_word"]["sensitivity"],
    )

    asr = ASREngine(
        model_name=baba_cfg["asr"]["model"],
        silence_threshold_seconds=baba_cfg["asr"]["silence_threshold_seconds"],
        max_recording_seconds=baba_cfg["asr"]["max_recording_seconds"],
    )

    parser = IntentParser(
        model=baba_cfg["llm"]["model"],
        temperature=baba_cfg["llm"]["temperature"],
        max_tokens=baba_cfg["llm"]["max_tokens"],
    )

    router = ActionRouter(baba_cfg["actions"])

    # Warmup LLM
    print("Warming up LLM...")
    parser.warmup()

    print()
    print("All systems ready.")
    print("Say 'HEY JARVIS' to start a command.")
    print("Press Ctrl+C at any time to quit.")
    print("=" * 50)
    print()

    tts.speak_sync("Baba is ready.")

    cycle = 0
    try:
        while True:
            cycle += 1

            # --- Step 1: Wake Word ---
            print(f"[Cycle {cycle}] Listening for wake word...")
            try:
                wake_result = detector.listen()
            except KeyboardInterrupt:
                raise
            confidence = wake_result["confidence"]
            print(f"  Wake word detected (confidence={confidence:.2f})")
            tts.speak_sync("Yes?")

            # --- Step 2: ASR ---
            print("  Speak your command...")
            asr_result = asr.record_and_transcribe()
            text = asr_result["text"]
            duration = asr_result["duration_seconds"]

            if not text:
                print("  No speech detected.")
                tts.speak_sync("I didn't hear anything.")
                print()
                continue

            print(f"  Heard: \"{text}\" ({duration:.1f}s)")

            # --- Step 3: Intent Parsing ---
            print("  Parsing intent...")
            intent = parser.parse(text)
            action = intent["action"]
            target = intent.get("target")
            conf = intent["confidence"]
            print(f"  Intent: {action} (target={target}, confidence={conf})")

            if action == "unknown":
                tts.speak_sync(f"I heard: {text}. But I don't know what to do with that.")
                print()
                continue

            # --- Step 3b: Confirmation for destructive actions ---
            if intent.get("requires_confirmation"):
                desc = f"{action} {target}" if target else action
                tts.speak_sync(f"I'm about to {desc}. Should I proceed?")
                print("  Waiting for confirmation (say yes or no)...")
                confirm_result = asr.record_and_transcribe()
                confirm_text = confirm_result["text"].lower()
                if any(w in confirm_text for w in ["yes", "yeah", "confirm", "go ahead", "do it", "sure"]):
                    print("  Confirmed.")
                else:
                    print(f"  Cancelled (heard: \"{confirm_result['text']}\")")
                    tts.speak_sync("Cancelled.")
                    print()
                    continue

            # --- Step 4: Execute ---
            print(f"  Executing {action}...")
            result = router.execute(intent)
            success = result.get("success", False)
            message = result.get("message") or result.get("response") or "Done."

            if success:
                print(f"  Result: {message}")
            else:
                print(f"  Failed: {message}")

            # --- Step 5: TTS Response ---
            tts.speak_sync(message)
            print()

    except KeyboardInterrupt:
        print("\n\nBaba shutting down.")
        tts.speak_sync("Goodbye.")


if __name__ == "__main__":
    main()
