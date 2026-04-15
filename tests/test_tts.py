"""Tests for TTS Engine (edge-tts neural voices)."""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from layers.tts import TTSEngine


def test_speak_and_stop():
    """TTS speaks and can be stopped."""
    tts = TTSEngine(voice="en-US-AndrewNeural")
    tts.speak("Testing Baba text to speech. One two three four five.")
    # Wait for edge-tts generation + playback to start (network latency varies)
    for _ in range(10):
        time.sleep(1)
        if tts.is_speaking():
            break
    assert tts.is_speaking(), "TTS should be speaking"
    tts.stop()
    time.sleep(0.5)
    assert not tts.is_speaking(), "TTS should have stopped"
    print("PASS: test_speak_and_stop")


def test_speak_sync():
    """TTS speak_sync blocks until done."""
    tts = TTSEngine(voice="en-US-AndrewNeural")
    start = time.time()
    tts.speak_sync("Hello.")
    elapsed = time.time() - start
    assert elapsed > 0.3, "speak_sync should block for at least a moment"
    assert not tts.is_speaking(), "Should not be speaking after sync"
    print("PASS: test_speak_sync")


def test_list_voices():
    """Can list available voices."""
    voices = TTSEngine.list_voices()
    assert len(voices) > 0, "Should have at least one voice"
    print(f"PASS: test_list_voices ({len(voices)} voices found)")


if __name__ == "__main__":
    test_speak_and_stop()
    test_speak_sync()
    test_list_voices()
    print("\nAll TTS tests passed!")
