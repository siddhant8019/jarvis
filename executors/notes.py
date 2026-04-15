import os
import subprocess
from datetime import datetime

from utils.logger import setup_logger

logger = setup_logger("baba.executors.notes")


def write_note_to_file(
    text: str, filepath: str = "~/Documents/baba_notes.md"
) -> dict:
    """Append a timestamped note to a markdown file."""
    expanded = os.path.expanduser(filepath)
    os.makedirs(os.path.dirname(expanded), exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## {timestamp}\n\n{text}\n"

    logger.info(f"Writing note to {filepath}")
    with open(expanded, "a") as f:
        f.write(entry)

    return {"success": True, "message": f"Note saved to {filepath}"}


def write_note_to_notes_app(text: str, title: str | None = None) -> dict:
    """Create a new note in Apple Notes.app via AppleScript."""
    note_title = title or f"Baba Note {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    # Escape double quotes and backslashes for AppleScript
    escaped_text = text.replace("\\", "\\\\").replace('"', '\\"')
    escaped_title = note_title.replace("\\", "\\\\").replace('"', '\\"')

    script = f'''
    tell application "Notes"
        tell account "iCloud"
            make new note at folder "Notes" with properties {{name:"{escaped_title}", body:"{escaped_text}"}}
        end tell
    end tell
    '''
    logger.info(f"Creating note in Notes.app: {note_title}")
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        error = result.stderr.strip()
        logger.error(f"Failed to create note: {error}")
        return {"success": False, "error": f"Could not create note: {error}"}
    return {"success": True, "message": f"Created note '{note_title}' in Notes.app"}
