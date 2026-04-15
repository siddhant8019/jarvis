"""Test Layer 2: ASR (Speech-to-Text).

Run this, speak into your microphone, and see the transcription.
Press Ctrl+C to stop.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from layers.asr import ASREngine


def main():
    print("=" * 50)
    print("ASR (SPEECH-TO-TEXT) TEST")
    print("Speak into your microphone after each prompt.")
    print("Stay silent for 1.5s to end each recording.")
    print("Press Ctrl+C to stop.")
    print("=" * 50)
    print()

    asr = ASREngine(model_name="base.en", silence_threshold_seconds=1.5)

    attempt = 0
    while True:
        attempt += 1
        print(f"[{attempt}] Speak now...")
        try:
            result = asr.record_and_transcribe()
            text = result["text"]
            duration = result["duration_seconds"]
            if text:
                print(f"  Transcription: \"{text}\"")
                print(f"  Audio duration: {duration:.1f}s")
            else:
                print("  (no speech detected)")
            print()
        except KeyboardInterrupt:
            print("\nStopped.")
            break


if __name__ == "__main__":
    main()
