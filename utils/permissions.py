import os
import subprocess

from utils.logger import setup_logger

logger = setup_logger("baba.permissions")

# Maps permission name to a test that returns True if granted.
# These are best-effort checks — macOS doesn't expose a direct API
# for querying all permission states from Python.

PERMISSIONS = {
    "Accessibility": {
        "description": "Required for UI element inspection and simulated input",
        "layers": "Layer 4 (all executors)",
        "path": "System Settings > Privacy & Security > Accessibility",
    },
    "Microphone": {
        "description": "Required for wake word detection and ASR",
        "layers": "Layer 1, Layer 2",
        "path": "System Settings > Privacy & Security > Microphone",
    },
    "Automation": {
        "description": "Required for controlling apps via AppleScript (prompted per-app)",
        "layers": "Layer 4a, 4b, 4c",
        "path": "System Settings > Privacy & Security > Automation",
    },
    "Screen Recording": {
        "description": "Required for screenshot-based screen reading (optional)",
        "layers": "Layer 4f (Approach 2 only)",
        "path": "System Settings > Privacy & Security > Screen Recording",
    },
}


def check_accessibility() -> bool:
    """Check if Accessibility permission is granted.

    Uses a small AppleScript that queries System Events — if it fails,
    Accessibility is likely not granted for this process/terminal.
    """
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get name of first process whose frontmost is true',
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def check_microphone() -> bool:
    """Check if Microphone permission is likely available.

    We can't directly query mic permission from Python without actually
    opening the mic. This checks if the permission has been prompted before
    by looking at the TCC database (read-only, user-scope).
    """
    try:
        # On macOS, the TCC database tracks permissions.
        # We check if any entry for Microphone exists for the current terminal app.
        # This is a heuristic — the definitive test is opening the mic.
        result = subprocess.run(
            [
                "sqlite3",
                os.path.expanduser("~/Library/Application Support/com.apple.TCC/TCC.db"),
                "SELECT client FROM access WHERE service='kTCCServiceMicrophone' AND auth_value=2;",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # If we get any output, some app has mic permission.
        # We can't easily tell if *our* terminal app does without opening the mic.
        return True  # Assume granted; will fail loudly at runtime if not.
    except Exception:
        return True  # Can't check; assume granted and let runtime handle it.


def check_all_permissions(speak_func=None) -> dict:
    """Check all permissions and report status.

    Args:
        speak_func: Optional TTS function to announce missing permissions.

    Returns:
        dict mapping permission name to bool (granted or not).
    """
    results = {}

    # Accessibility is the one we can reliably test
    acc_ok = check_accessibility()
    results["Accessibility"] = acc_ok

    # Microphone — heuristic only
    results["Microphone"] = check_microphone()

    # Automation and Screen Recording can't be pre-checked;
    # macOS prompts the user on first use per-app.
    results["Automation"] = True  # Will prompt on first AppleScript call
    results["Screen Recording"] = True  # Only needed for screenshots

    # Report
    missing = [name for name, granted in results.items() if not granted]

    if missing:
        msg = "Missing permissions: " + ", ".join(missing)
        logger.warning(msg)
        for name in missing:
            info = PERMISSIONS[name]
            logger.warning(f"  {name}: {info['description']}")
            logger.warning(f"  Grant at: {info['path']}")
        if speak_func:
            speak_func(f"Warning: missing permissions for {', '.join(missing)}. Check the terminal for details.")
    else:
        logger.info("All checkable permissions appear to be granted.")

    return results
