import subprocess

from utils.logger import setup_logger

logger = setup_logger("baba.executors.system_control")

# Track caffeinate process so we can stop it later
_caffeinate_proc = None


def set_volume(level: int) -> dict:
    """Set system output volume (0-100)."""
    clamped = max(0, min(100, level))
    logger.info(f"Setting volume to {clamped}%")
    subprocess.run(
        ["osascript", "-e", f"set volume output volume {clamped}"],
        timeout=5,
    )
    return {"success": True, "message": f"Volume set to {clamped}%"}


def get_volume() -> dict:
    """Get current system output volume."""
    result = subprocess.run(
        ["osascript", "-e", "output volume of (get volume settings)"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode == 0:
        vol = result.stdout.strip()
        return {"success": True, "volume": int(vol), "message": f"Volume is {vol}%"}
    return {"success": False, "error": "Could not get volume"}


def set_mute(muted: bool) -> dict:
    """Mute or unmute system audio."""
    state = "true" if muted else "false"
    logger.info(f"Setting mute to {muted}")
    subprocess.run(
        ["osascript", "-e", f"set volume output muted {state}"],
        timeout=5,
    )
    action = "Muted" if muted else "Unmuted"
    return {"success": True, "message": f"{action} system audio"}


def set_brightness(level: float) -> dict:
    """Set screen brightness (0.0 - 1.0). Requires `brightness` CLI tool."""
    clamped = max(0.0, min(1.0, level))
    logger.info(f"Setting brightness to {int(clamped * 100)}%")
    result = subprocess.run(
        ["brightness", str(clamped)],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        return {
            "success": False,
            "error": "Failed to set brightness. Is `brightness` installed? (brew install brightness)",
        }
    return {"success": True, "message": f"Brightness set to {int(clamped * 100)}%"}


def toggle_do_not_disturb() -> dict:
    """Toggle Do Not Disturb via Shortcuts.app.

    Requires a Shortcut named 'Toggle DND' to exist. Create it in
    Shortcuts.app with a single 'Set Focus' action.
    """
    logger.info("Toggling Do Not Disturb")
    result = subprocess.run(
        ["shortcuts", "run", "Toggle DND"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        error = result.stderr.strip()
        return {
            "success": False,
            "error": f"Failed to toggle DND. Create a Shortcut named 'Toggle DND': {error}",
        }
    return {"success": True, "message": "Toggled Do Not Disturb"}


def prevent_sleep(duration_seconds: int = 3600) -> dict:
    """Prevent Mac from sleeping for the given duration."""
    global _caffeinate_proc
    logger.info(f"Preventing sleep for {duration_seconds}s")
    # Kill existing caffeinate if running
    stop_prevent_sleep()
    _caffeinate_proc = subprocess.Popen(
        ["caffeinate", "-d", "-i", "-t", str(duration_seconds)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    minutes = duration_seconds // 60
    return {"success": True, "message": f"Preventing sleep for {minutes} minutes"}


def stop_prevent_sleep() -> dict:
    """Stop caffeinate if running."""
    global _caffeinate_proc
    if _caffeinate_proc and _caffeinate_proc.poll() is None:
        _caffeinate_proc.terminate()
        _caffeinate_proc = None
        return {"success": True, "message": "Stopped preventing sleep"}
    _caffeinate_proc = None
    return {"success": True, "message": "Caffeinate was not running"}
