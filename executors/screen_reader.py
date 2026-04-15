"""Executor: Read what's on screen using screenshot + Claude Vision."""

import base64
import os
import subprocess
import tempfile

import anthropic
from dotenv import load_dotenv

from utils.logger import setup_logger

logger = setup_logger("baba.executors.screen_reader")

load_dotenv()


def capture_screenshot() -> str | None:
    """Take a screenshot and return the file path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    result = subprocess.run(
        ["screencapture", "-x", "-C", tmp.name],
        capture_output=True,
        timeout=10,
    )
    if result.returncode != 0:
        os.unlink(tmp.name)
        return None
    return tmp.name


def read_screen(
    query: str | None = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1024,
) -> dict:
    """Take a screenshot and ask Claude to describe what's on screen.

    Args:
        query: Optional specific question about the screen content
        model: Claude model to use
        max_tokens: Max response tokens

    Returns:
        dict with success and message
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "success": False,
            "message": "Claude API key not set. Add ANTHROPIC_API_KEY to your .env file.",
        }

    # Capture screenshot
    logger.info("Taking screenshot...")
    screenshot_path = capture_screenshot()
    if not screenshot_path:
        return {"success": False, "message": "Failed to take screenshot."}

    try:
        # Read and encode the screenshot
        with open(screenshot_path, "rb") as f:
            image_data = base64.standard_b64encode(f.read()).decode("utf-8")

        prompt = query or "Describe what you see on this screen. Be concise — this will be spoken aloud. Focus on the main content, active application, and any notable information."

        logger.info(f"Sending screenshot to Claude for analysis...")

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
            system="You are a screen reader for a voice assistant called Jarvis. Describe what's visible on screen concisely — your response will be spoken aloud via TTS. Keep it to 2-4 sentences unless asked for detail.",
        )

        text = response.content[0].text
        logger.info(f"Screen reading done ({len(text)} chars)")

        return {
            "success": True,
            "message": text,
        }

    except Exception as e:
        logger.error(f"Screen reading failed: {e}")
        return {"success": False, "message": f"Screen reading failed: {e}"}
    finally:
        if os.path.exists(screenshot_path):
            os.unlink(screenshot_path)
