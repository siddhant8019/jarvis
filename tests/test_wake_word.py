"""Test Layer 1: Wake Word Detection.

Run this, then say "HEY JARVIS" into your microphone.
Press Ctrl+C to stop.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from layers.wake_word import WakeWordDetector


def main():
    print("=" * 50)
    print("WAKE WORD TEST")
    print("Say 'HEY JARVIS' into your microphone.")
    print("Press Ctrl+C to stop.")
    print("=" * 50)
    print()

    detector = WakeWordDetector(sensitivity=0.5)

    attempts = 0
    while True:
        attempts += 1
        print(f"[Attempt {attempts}] Listening...")
        try:
            result = detector.listen()
            print(f"  DETECTED! Heard wake word (confidence: {result['confidence']:.3f})")
            print()
            time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nStopped.")
            break


if __name__ == "__main__":
    main()
