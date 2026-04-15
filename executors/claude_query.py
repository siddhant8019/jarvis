"""Executor: Query Claude AI via the Anthropic API.

Maintains conversation history within a session for context-aware responses.
"""

import os
import anthropic
from dotenv import load_dotenv

from utils.logger import setup_logger

logger = setup_logger("baba.executors.claude_query")

load_dotenv()

# Session conversation history (list of {"role": ..., "content": ...})
_conversation_history: list[dict] = []
_MAX_HISTORY = 20  # keep last 20 messages to avoid token overflow

SYSTEM_MESSAGE = (
    "You are Jarvis, a helpful voice assistant. "
    "Keep responses concise and conversational — they will be spoken aloud via TTS. "
    "Aim for 1-3 sentences unless the user asks for detail. "
    "You have access to the user's screen when they ask you to read it — "
    "if context from a screen reading appears in the conversation, use it."
)


def clear_history():
    """Clear conversation history (called when session ends)."""
    global _conversation_history
    _conversation_history = []
    logger.info("Conversation history cleared")


def add_context(role: str, content: str):
    """Add context to conversation history without querying Claude.

    Used to inject screen reading results, action outcomes, etc.
    """
    global _conversation_history
    _conversation_history.append({"role": role, "content": content})
    # Trim if needed
    if len(_conversation_history) > _MAX_HISTORY:
        _conversation_history = _conversation_history[-_MAX_HISTORY:]


def query_claude(
    query: str,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1024,
) -> dict:
    """Send a question to Claude with conversation history.

    Args:
        query: The user's question
        model: Claude model to use
        max_tokens: Max response tokens

    Returns:
        dict with success, message, and response fields
    """
    global _conversation_history

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "success": False,
            "message": "Claude API key not set. Add ANTHROPIC_API_KEY to your .env file.",
        }

    logger.info(f"Querying Claude: '{query[:80]}...' " if len(query) > 80 else f"Querying Claude: '{query}'")

    # Add user message to history
    _conversation_history.append({"role": "user", "content": query})

    # Trim history if too long
    if len(_conversation_history) > _MAX_HISTORY:
        _conversation_history = _conversation_history[-_MAX_HISTORY:]

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=_conversation_history,
            system=SYSTEM_MESSAGE,
        )

        text = response.content[0].text

        # Add assistant response to history
        _conversation_history.append({"role": "assistant", "content": text})

        logger.info(f"Claude response ({len(text)} chars): '{text[:100]}...' " if len(text) > 100 else f"Claude response: '{text}'")

        return {
            "success": True,
            "message": text,
            "response": text,
        }

    except anthropic.AuthenticationError:
        _conversation_history.pop()  # Remove the failed user message
        return {"success": False, "message": "Invalid Claude API key. Check your .env file."}
    except anthropic.RateLimitError:
        _conversation_history.pop()
        return {"success": False, "message": "Claude rate limit hit. Try again in a moment."}
    except Exception as e:
        _conversation_history.pop()
        logger.error(f"Claude query failed: {e}")
        return {"success": False, "message": f"Claude query failed: {e}"}
