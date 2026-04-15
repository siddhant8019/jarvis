import subprocess

from utils.logger import setup_logger
from utils.sanitize import sanitize_app_name

logger = setup_logger("baba.executors.app_control")


def open_app(app_name: str) -> dict:
    """Launch or bring to front an application."""
    logger.info(f"Opening app: {app_name}")
    # open -a uses the raw name (no AppleScript), so just basic validation
    clean = app_name.strip()
    if not clean:
        return {"success": False, "error": "Empty app name"}
    result = subprocess.run(
        ["open", "-a", clean],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        error = result.stderr.strip()
        logger.error(f"Failed to open {clean}: {error}")
        return {"success": False, "error": f"Could not open {clean}: {error}"}
    logger.info(f"Opened {clean}")
    return {"success": True, "message": f"Opened {clean}"}


def close_app(app_name: str) -> dict:
    """Quit an application gracefully via AppleScript."""
    safe_name = sanitize_app_name(app_name)
    if safe_name is None:
        return {"success": False, "error": f"Invalid app name: {app_name}"}

    logger.info(f"Closing app: {app_name}")
    script = f'tell application "{safe_name}" to quit'
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        error = result.stderr.strip()
        logger.error(f"Failed to close {app_name}: {error}")
        return {"success": False, "error": f"Could not close {app_name}: {error}"}
    logger.info(f"Closed {app_name}")
    return {"success": True, "message": f"Closed {app_name}"}


def is_app_running(app_name: str) -> bool:
    """Check if an application is currently running."""
    safe_name = sanitize_app_name(app_name)
    if safe_name is None:
        return False

    script = f'''
    tell application "System Events"
        set appRunning to (name of processes) contains "{safe_name}"
        return appRunning
    end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=5,
    )
    return result.stdout.strip().lower() == "true"


def get_frontmost_app() -> str | None:
    """Return the name of the frontmost application."""
    script = '''
    tell application "System Events"
        return name of first application process whose frontmost is true
    end tell
    '''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None
