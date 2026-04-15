"""Tests for Phase 2: All Executors.

These tests perform REAL macOS actions — they open/close apps,
modify volume, write files, etc. Run manually and observe results.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from executors.app_control import open_app, close_app, is_app_running, get_frontmost_app
from executors.browser_tabs import (
    chrome_open_tab,
    chrome_close_tab,
    chrome_list_tabs,
    chrome_get_active_tab_title,
)
from executors.notes import write_note_to_file
from executors.system_control import set_volume, get_volume, set_mute, prevent_sleep, stop_prevent_sleep
from executors.dictation import paste_text


def test_app_control():
    """Test opening and closing an app."""
    print("\n--- test_app_control ---")

    # Open TextEdit
    result = open_app("TextEdit")
    assert result["success"], f"Failed to open TextEdit: {result}"
    print(f"  open_app: {result['message']}")
    time.sleep(1)

    # Check it's running
    running = is_app_running("TextEdit")
    assert running, "TextEdit should be running"
    print(f"  is_app_running: {running}")

    # Get frontmost
    front = get_frontmost_app()
    print(f"  frontmost app: {front}")

    # Close TextEdit
    result = close_app("TextEdit")
    assert result["success"], f"Failed to close TextEdit: {result}"
    print(f"  close_app: {result['message']}")
    time.sleep(1)

    print("PASS: test_app_control")


def test_notes_to_file():
    """Test writing a note to a file."""
    print("\n--- test_notes_to_file ---")
    test_file = "/tmp/baba_test_notes.md"

    # Clean up from previous runs
    if os.path.exists(test_file):
        os.remove(test_file)

    result = write_note_to_file("This is a test note from Baba.", filepath=test_file)
    assert result["success"], f"Failed to write note: {result}"
    print(f"  write_note: {result['message']}")

    # Verify file was created and has content
    assert os.path.exists(test_file), "Notes file should exist"
    with open(test_file, "r") as f:
        content = f.read()
    assert "This is a test note from Baba." in content
    print(f"  file content verified ({len(content)} bytes)")

    os.remove(test_file)
    print("PASS: test_notes_to_file")


def test_volume_control():
    """Test getting and setting volume."""
    print("\n--- test_volume_control ---")

    # Get current volume so we can restore it
    vol = get_volume()
    assert vol["success"], f"Failed to get volume: {vol}"
    original = vol["volume"]
    print(f"  current volume: {original}%")

    # Set to 30
    result = set_volume(30)
    assert result["success"], f"Failed to set volume: {result}"
    print(f"  set_volume(30): {result['message']}")

    # Verify
    vol = get_volume()
    assert vol["volume"] == 30, f"Expected 30, got {vol['volume']}"

    # Restore original
    set_volume(original)
    print(f"  restored to {original}%")

    print("PASS: test_volume_control")


def test_mute():
    """Test mute/unmute."""
    print("\n--- test_mute ---")
    result = set_mute(True)
    assert result["success"]
    print(f"  mute: {result['message']}")
    time.sleep(0.5)

    result = set_mute(False)
    assert result["success"]
    print(f"  unmute: {result['message']}")

    print("PASS: test_mute")


def test_caffeinate():
    """Test prevent_sleep / stop."""
    print("\n--- test_caffeinate ---")
    result = prevent_sleep(duration_seconds=60)
    assert result["success"]
    print(f"  prevent_sleep: {result['message']}")
    time.sleep(1)

    result = stop_prevent_sleep()
    assert result["success"]
    print(f"  stop: {result['message']}")

    print("PASS: test_caffeinate")


def test_browser_tabs():
    """Test Chrome tab operations. Requires Chrome to be installed."""
    print("\n--- test_browser_tabs ---")

    # Open Chrome first
    open_app("Google Chrome")
    time.sleep(2)

    # Open a tab
    result = chrome_open_tab("https://example.com")
    if not result["success"]:
        print(f"  SKIP (Chrome not available): {result['error']}")
        return
    print(f"  open_tab: {result['message']}")
    time.sleep(2)

    # List tabs
    result = chrome_list_tabs()
    if result["success"]:
        print(f"  list_tabs: {result['message']}")

    # Get active tab
    result = chrome_get_active_tab_title()
    if result["success"]:
        print(f"  active tab: {result['title']}")

    # Close the tab we opened
    result = chrome_close_tab()
    print(f"  close_tab: {result.get('message', result.get('error'))}")

    print("PASS: test_browser_tabs")


def test_paste():
    """Test paste_text. Opens TextEdit, pastes, then closes."""
    print("\n--- test_paste ---")

    import subprocess

    open_app("TextEdit")
    time.sleep(2)

    # Create a new document via AppleScript (longer timeout for permission prompts)
    subprocess.run(
        ["osascript", "-e", 'tell application "TextEdit" to make new document'],
        capture_output=True,
        timeout=15,
    )
    time.sleep(1)

    result = paste_text("Hello from Baba! This text was pasted automatically.")
    assert result["success"], f"Failed to paste: {result}"
    print(f"  paste_text: {result['message']}")
    time.sleep(1)

    # Close TextEdit without saving
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "TextEdit" to close front document saving no',
            ],
            capture_output=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        pass
    close_app("TextEdit")
    print("PASS: test_paste")


if __name__ == "__main__":
    print("=" * 50)
    print("BABA Phase 2 Executor Tests")
    print("These tests perform REAL macOS actions.")
    print("=" * 50)

    test_notes_to_file()
    test_volume_control()
    test_mute()
    test_caffeinate()
    test_app_control()
    test_browser_tabs()
    test_paste()

    print("\n" + "=" * 50)
    print("All executor tests passed!")
    print("=" * 50)
