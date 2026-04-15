"""Tests for Layer 3: Intent Parser.

Requires either ANTHROPIC_API_KEY or Ollama running with qwen2.5:3b.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from layers.intent_parser import IntentParser


def _first_intent(parser, text):
    """Helper: parse and return the first intent from the list."""
    results = parser.parse(text)
    return results[0] if results else None


def test_intent_parser():
    """Test intent classification across a range of commands."""
    parser = IntentParser(model="qwen2.5:3b")
    parser.warmup()

    test_cases = [
        ("open Chrome", {"open_app", "open_tab"}),
        ("close Slack", {"close_app"}),
        ("open a new tab and go to github.com", {"open_tab"}),
        ("close this tab", {"close_tab"}),
        ("switch to the second tab", {"switch_tab"}),
        ("write a note meeting at 3pm with the design team", {"write_note"}),
        ("ask Claude how to reverse a linked list in Python", {"query_claude"}),
        ("read what's on screen", {"read_screen"}),
        ("set volume to 50 percent", {"system_control"}),
        ("search for Python asyncio tutorial", {"search_web"}),
        ("launch Safari", {"open_app", "open_tab"}),
        ("open TextEdit", {"open_app"}),
    ]

    passed = 0
    failed = 0

    for transcription, acceptable_actions in test_cases:
        result = _first_intent(parser, transcription)
        actual_action = result["action"]
        confidence = result["confidence"]
        match = actual_action in acceptable_actions

        status = "PASS" if match else "FAIL"
        if match:
            passed += 1
        else:
            failed += 1

        print(f"  {status}: \"{transcription}\"")
        print(f"         acceptable={acceptable_actions}, got={actual_action}, confidence={confidence}")

    print(f"\nResults: {passed}/{passed + failed} passed")
    assert failed == 0, f"{failed} test cases failed"


def test_multi_action():
    """Test that compound commands return at least one valid action.

    Multi-action parsing works best with Claude API. With Ollama fallback,
    it may return a single action which is still acceptable.
    """
    parser = IntentParser(model="qwen2.5:3b")
    parser.warmup()

    results = parser.parse("Open WhatsApp and type hello how are you")
    print(f"  Multi-action: got {len(results)} action(s)")
    for i, r in enumerate(results):
        print(f"    Action {i+1}: {r['action']} (target={r.get('target')})")

    assert len(results) >= 1, "Should parse at least 1 action"
    # With any parser, we should get something reasonable
    first_action = results[0]["action"]
    assert first_action != "unknown", f"First action should not be unknown, got {first_action}"
    print("PASS: test_multi_action")


def test_unknown_intent():
    """Test that gibberish routes to query_claude via hybrid fallback."""
    parser = IntentParser(model="qwen2.5:3b")
    result = _first_intent(parser, "blorp flarg noodle zippity")
    print(f"  Gibberish -> action={result['action']}, confidence={result['confidence']}")
    assert result["action"] in ("unknown", "query_claude"), \
        f"Expected 'unknown' or 'query_claude' for gibberish, got {result['action']}"
    print("PASS: test_unknown_intent")


def test_empty_input():
    """Test empty input handling."""
    parser = IntentParser(model="qwen2.5:3b")
    result = _first_intent(parser, "")
    assert result["action"] == "unknown"
    assert result["confidence"] == 0.0
    print("PASS: test_empty_input")


def test_confirmation_required():
    """Test that destructive actions require confirmation."""
    parser = IntentParser(model="qwen2.5:3b")
    parser.warmup()

    result = _first_intent(parser, "close Safari")
    assert result["requires_confirmation"] is True, \
        f"close_app should require confirmation, got action={result['action']}"
    print(f"PASS: close_app requires_confirmation={result['requires_confirmation']}")

    result = _first_intent(parser, "close this tab")
    assert result["requires_confirmation"] is True, \
        f"close_tab should require confirmation, got action={result['action']}"
    print(f"PASS: close_tab requires_confirmation={result['requires_confirmation']}")


def test_json_validity():
    """Test that all responses have required fields."""
    parser = IntentParser(model="qwen2.5:3b")
    parser.warmup()

    commands = ["open Firefox", "turn brightness up", "type hello world"]
    required_fields = {"event", "action", "target", "parameters", "confidence", "requires_confirmation", "raw_transcription"}

    for cmd in commands:
        result = _first_intent(parser, cmd)
        missing = required_fields - set(result.keys())
        assert not missing, f"Missing fields {missing} for command '{cmd}'"

    print("PASS: test_json_validity (all required fields present)")


def test_greeting_routes_to_claude():
    """Test that greetings go to query_claude, not read_screen."""
    parser = IntentParser(model="qwen2.5:3b")
    parser.warmup()

    greetings = ["How's it going?", "Hello", "What's up Jarvis?", "Hey how are you"]
    for g in greetings:
        result = _first_intent(parser, g)
        assert result["action"] == "query_claude", \
            f"Greeting '{g}' should be query_claude, got {result['action']}"
        print(f"  PASS: \"{g}\" -> query_claude")

    print("PASS: test_greeting_routes_to_claude")


if __name__ == "__main__":
    print("=" * 50)
    print("Intent Parser Tests")
    print("=" * 50)

    test_empty_input()
    test_json_validity()
    test_confirmation_required()
    test_unknown_intent()
    test_greeting_routes_to_claude()
    test_multi_action()
    print()
    test_intent_parser()

    print("\n" + "=" * 50)
    print("All intent parser tests passed!")
    print("=" * 50)
