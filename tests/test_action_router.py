"""Tests for Layer 4: Action Router.

Tests that intents are correctly dispatched to executors.
These perform REAL macOS actions.
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from layers.action_router import ActionRouter
from executors.app_control import close_app


def make_intent(action, target=None, **params):
    """Helper to create an intent dict."""
    return {
        "event": "intent_parsed",
        "action": action,
        "target": target,
        "parameters": params,
        "confidence": 0.9,
        "requires_confirmation": False,
        "raw_transcription": "test",
    }


def test_open_close_app():
    """Route open_app and close_app intents."""
    print("\n--- test_open_close_app ---")
    router = ActionRouter({"default_browser": "Google Chrome"})

    result = router.execute(make_intent("open_app", target="TextEdit"))
    assert result["success"], f"Failed: {result}"
    print(f"  open_app TextEdit: {result['message']}")
    time.sleep(1)

    result = router.execute(make_intent("close_app", target="TextEdit"))
    assert result["success"], f"Failed: {result}"
    print(f"  close_app TextEdit: {result['message']}")
    print("PASS")


def test_open_tab():
    """Route open_tab intent."""
    print("\n--- test_open_tab ---")
    router = ActionRouter({"default_browser": "Google Chrome"})

    result = router.execute(make_intent("open_tab", target="https://example.com"))
    assert result["success"], f"Failed: {result}"
    print(f"  open_tab: {result['message']}")
    time.sleep(2)

    # Clean up
    from executors.browser_tabs import chrome_close_tab
    chrome_close_tab()
    print("PASS")


def test_system_control():
    """Route system_control intents."""
    print("\n--- test_system_control ---")
    router = ActionRouter({"default_browser": "Google Chrome"})

    # Get current volume to restore later
    from executors.system_control import get_volume
    orig = get_volume()["volume"]

    result = router.execute(make_intent("system_control", target="volume", setting="volume", value=25))
    assert result["success"], f"Failed: {result}"
    print(f"  volume: {result['message']}")

    # Restore
    from executors.system_control import set_volume
    set_volume(orig)
    print("PASS")


def test_write_note():
    """Route write_note intent."""
    print("\n--- test_write_note ---")
    router = ActionRouter({
        "default_browser": "Google Chrome",
        "notes_file": "/tmp/baba_router_test_notes.md",
    })

    result = router.execute(make_intent("write_note", text="Test note from action router"))
    assert result["success"], f"Failed: {result}"
    print(f"  write_note: {result['message']}")

    # Verify
    with open("/tmp/baba_router_test_notes.md") as f:
        content = f.read()
    assert "Test note from action router" in content
    os.remove("/tmp/baba_router_test_notes.md")
    print("PASS")


def test_search_web():
    """Route search_web intent."""
    print("\n--- test_search_web ---")
    router = ActionRouter({"default_browser": "Google Chrome"})

    result = router.execute(make_intent("search_web", query="Python tutorial"))
    assert result["success"], f"Failed: {result}"
    print(f"  search_web: {result['message']}")
    time.sleep(2)

    from executors.browser_tabs import chrome_close_tab
    chrome_close_tab()
    print("PASS")


def test_missing_target():
    """Route intents with missing required fields."""
    print("\n--- test_missing_target ---")
    router = ActionRouter({"default_browser": "Google Chrome"})

    result = router.execute(make_intent("open_app", target=None))
    assert not result["success"]
    print(f"  open_app(no target): {result['message']}")

    result = router.execute(make_intent("unknown"))
    assert not result["success"]
    print(f"  unknown: {result['message']}")
    print("PASS")


if __name__ == "__main__":
    print("=" * 50)
    print("Action Router Tests")
    print("These perform REAL macOS actions.")
    print("=" * 50)

    test_missing_target()
    test_write_note()
    test_system_control()
    test_open_close_app()
    test_open_tab()
    test_search_web()

    print("\n" + "=" * 50)
    print("All action router tests passed!")
    print("=" * 50)
