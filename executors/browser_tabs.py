import subprocess

from utils.logger import setup_logger
from utils.sanitize import sanitize_url

logger = setup_logger("baba.executors.browser_tabs")


def _run_applescript(script: str, timeout: int = 5) -> dict:
    """Run an AppleScript and return result dict."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "AppleScript timed out"}
    if result.returncode != 0:
        return {"success": False, "error": result.stderr.strip()}
    return {"success": True, "output": result.stdout.strip()}


def _validate_tab_index(index: int) -> dict | None:
    """Return an error dict if index is invalid, else None."""
    if not isinstance(index, int) or index < 1:
        return {"success": False, "error": f"Invalid tab index: {index}. Must be a positive integer."}
    if index > 500:
        return {"success": False, "error": f"Tab index {index} seems unreasonably high."}
    return None


# --- Google Chrome ---

def chrome_open_tab(url: str) -> dict:
    """Open a new tab in Chrome with the given URL."""
    safe_url = sanitize_url(url)
    if safe_url is None:
        return {"success": False, "error": f"Invalid URL: {url}"}

    logger.info(f"Chrome: opening tab {url}")
    script = f'''
    tell application "Google Chrome"
        activate
        if (count of windows) is 0 then
            make new window
        end if
        tell front window
            make new tab with properties {{URL:"{safe_url}"}}
        end tell
    end tell
    '''
    result = _run_applescript(script)
    if result["success"]:
        return {"success": True, "message": f"Opened {url} in Chrome"}
    return {"success": False, "error": f"Failed to open tab: {result['error']}"}


def chrome_close_tab() -> dict:
    """Close the active tab in Chrome."""
    logger.info("Chrome: closing active tab")
    script = '''
    tell application "Google Chrome"
        if (count of windows) is 0 then
            return "no windows"
        end if
        tell front window
            if (count of tabs) is 1 then
                close
            else
                close active tab
            end if
        end tell
    end tell
    '''
    result = _run_applescript(script)
    if result["success"]:
        return {"success": True, "message": "Closed active Chrome tab"}
    return {"success": False, "error": f"Failed to close tab: {result['error']}"}


def chrome_switch_tab(index: int) -> dict:
    """Switch to a tab by index (1-based) in Chrome."""
    err = _validate_tab_index(index)
    if err:
        return err

    logger.info(f"Chrome: switching to tab {index}")
    script = f'''
    tell application "Google Chrome"
        if (count of windows) is 0 then
            return "no windows"
        end if
        tell front window
            set tabCount to count of tabs
            if {index} > tabCount then
                return "tab index " & {index} & " exceeds tab count " & tabCount
            end if
            set active tab index to {index}
        end tell
    end tell
    '''
    result = _run_applescript(script)
    if result["success"]:
        return {"success": True, "message": f"Switched to Chrome tab {index}"}
    return {"success": False, "error": f"Failed to switch tab: {result['error']}"}


def chrome_list_tabs() -> dict:
    """List all tab titles in the front Chrome window."""
    script = '''
    tell application "Google Chrome"
        if (count of windows) is 0 then
            return ""
        end if
        tell front window
            set tabTitles to {}
            repeat with t in tabs
                set end of tabTitles to title of t
            end repeat
            return tabTitles
        end tell
    end tell
    '''
    result = _run_applescript(script)
    if result["success"]:
        output = result["output"]
        if not output:
            return {"success": True, "tabs": [], "message": "No tabs found"}
        titles = [t.strip() for t in output.split(",") if t.strip()]
        return {"success": True, "tabs": titles, "message": f"Found {len(titles)} tabs"}
    return {"success": False, "error": f"Failed to list tabs: {result['error']}"}


def chrome_get_active_tab_title() -> dict:
    """Get the title of the active Chrome tab."""
    script = '''
    tell application "Google Chrome"
        if (count of windows) is 0 then
            return ""
        end if
        tell front window
            return title of active tab
        end tell
    end tell
    '''
    result = _run_applescript(script)
    if result["success"]:
        return {"success": True, "title": result["output"]}
    return {"success": False, "error": result["error"]}


# --- Safari ---

def safari_open_tab(url: str) -> dict:
    """Open a new tab in Safari with the given URL."""
    safe_url = sanitize_url(url)
    if safe_url is None:
        return {"success": False, "error": f"Invalid URL: {url}"}

    logger.info(f"Safari: opening tab {url}")
    script = f'''
    tell application "Safari"
        activate
        if (count of windows) is 0 then
            make new document with properties {{URL:"{safe_url}"}}
        else
            tell front window
                set current tab to (make new tab with properties {{URL:"{safe_url}"}})
            end tell
        end if
    end tell
    '''
    result = _run_applescript(script)
    if result["success"]:
        return {"success": True, "message": f"Opened {url} in Safari"}
    return {"success": False, "error": f"Failed to open tab: {result['error']}"}


def safari_close_tab() -> dict:
    """Close the current tab in Safari."""
    logger.info("Safari: closing current tab")
    script = '''
    tell application "Safari"
        if (count of windows) is 0 then
            return "no windows"
        end if
        tell front window
            close current tab
        end tell
    end tell
    '''
    result = _run_applescript(script)
    if result["success"]:
        return {"success": True, "message": "Closed active Safari tab"}
    return {"success": False, "error": f"Failed to close tab: {result['error']}"}


def safari_switch_tab(index: int) -> dict:
    """Switch to a tab by index (1-based) in Safari."""
    err = _validate_tab_index(index)
    if err:
        return err

    logger.info(f"Safari: switching to tab {index}")
    script = f'''
    tell application "Safari"
        if (count of windows) is 0 then
            return "no windows"
        end if
        tell front window
            set current tab to tab {index}
        end tell
    end tell
    '''
    result = _run_applescript(script)
    if result["success"]:
        return {"success": True, "message": f"Switched to Safari tab {index}"}
    return {"success": False, "error": f"Failed to switch tab: {result['error']}"}


# --- Browser-agnostic dispatcher ---

def open_tab(url: str, browser: str = "Google Chrome") -> dict:
    """Open a tab in the specified browser."""
    if browser == "Safari":
        return safari_open_tab(url)
    return chrome_open_tab(url)


def close_tab(browser: str = "Google Chrome") -> dict:
    """Close the active tab in the specified browser."""
    if browser == "Safari":
        return safari_close_tab()
    return chrome_close_tab()


def switch_tab(index: int, browser: str = "Google Chrome") -> dict:
    """Switch to a tab in the specified browser."""
    if browser == "Safari":
        return safari_switch_tab(index)
    return chrome_switch_tab(index)
