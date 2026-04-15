import subprocess

from utils.logger import setup_logger

logger = setup_logger("baba.executors.dictation")


def type_text(text: str) -> dict:
    """Simulate keyboard input into the focused application.

    For short text only. For long text, use paste_text().
    """
    logger.info(f"Typing {len(text)} characters")
    # Escape for AppleScript string
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    script = f'tell application "System Events" to keystroke "{escaped}"'
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        error = result.stderr.strip()
        logger.error(f"Failed to type text: {error}")
        return {"success": False, "error": f"Failed to type text: {error}"}
    return {"success": True, "message": f"Typed {len(text)} characters"}


def paste_text(text: str) -> dict:
    """Copy text to clipboard and paste it via Cmd+V.

    More reliable for long text than keystroke simulation.
    """
    logger.info(f"Pasting {len(text)} characters")
    # Write to clipboard via pbcopy
    proc = subprocess.Popen(
        ["pbcopy"],
        stdin=subprocess.PIPE,
    )
    proc.communicate(text.encode("utf-8"))

    if proc.returncode != 0:
        return {"success": False, "error": "Failed to copy text to clipboard"}

    # Simulate Cmd+V
    result = subprocess.run(
        [
            "osascript",
            "-e",
            'tell application "System Events" to keystroke "v" using command down',
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        error = result.stderr.strip()
        logger.error(f"Failed to paste: {error}")
        return {"success": False, "error": f"Failed to paste: {error}"}
    return {"success": True, "message": f"Pasted {len(text)} characters"}
