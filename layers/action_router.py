"""Layer 4: Action Router — maps parsed intents to executor functions."""

from utils.logger import setup_logger
from executors.app_control import open_app, close_app
from executors.browser_tabs import open_tab, close_tab, switch_tab
from executors.notes import write_note_to_file
from executors.system_control import (
    set_volume,
    set_mute,
    set_brightness,
    toggle_do_not_disturb,
    prevent_sleep,
    stop_prevent_sleep,
)
from executors.dictation import paste_text
from executors.claude_query import query_claude, add_context as add_claude_context
from executors.screen_reader import read_screen

logger = setup_logger("baba.action_router")


class ActionRouter:
    """Routes parsed intents to the appropriate executor functions."""

    def __init__(self, config: dict):
        self.default_browser = config.get("default_browser", "Google Chrome")
        self.notes_file = config.get("notes_file", "~/Documents/baba_notes.md")
        self.claude_model = config.get("claude_model", "claude-sonnet-4-20250514")
        self.claude_max_tokens = config.get("claude_max_tokens", 1024)

    def execute(self, intent: dict) -> dict:
        """Execute an intent by dispatching to the appropriate executor.

        Args:
            intent: Parsed intent dict from IntentParser

        Returns:
            dict with execution result
        """
        action = intent.get("action", "unknown")
        target = intent.get("target")
        params = intent.get("parameters", {})

        logger.info(f"Routing action: {action} (target={target})")

        handler = self._handlers.get(action)
        if handler is None:
            return {"success": False, "message": f"I don't know how to do '{action}'."}

        try:
            return handler(self, target, params)
        except Exception as e:
            logger.error(f"Action '{action}' failed: {e}", exc_info=True)
            return {"success": False, "message": f"Failed to execute {action}: {e}"}

    # --- Individual action handlers ---

    def _handle_open_app(self, target: str | None, params: dict) -> dict:
        if not target:
            return {"success": False, "message": "Which app should I open?"}
        return open_app(target)

    def _handle_close_app(self, target: str | None, params: dict) -> dict:
        if not target:
            return {"success": False, "message": "Which app should I close?"}
        return close_app(target)

    def _handle_open_tab(self, target: str | None, params: dict) -> dict:
        url = params.get("url") or target or params.get("query")
        if not url:
            return {"success": False, "message": "What URL should I open?"}
        # Ensure it's a proper URL
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        browser = target if target and target != url else self.default_browser
        # Don't use URL as browser name
        if browser and browser.startswith(("http://", "https://", "www.")):
            browser = self.default_browser
        return open_tab(url, browser=browser)

    def _handle_close_tab(self, target: str | None, params: dict) -> dict:
        return close_tab(browser=self.default_browser)

    def _handle_switch_tab(self, target: str | None, params: dict) -> dict:
        index = params.get("index")
        if index is None:
            # Try to extract from target
            if target and target.isdigit():
                index = int(target)
            else:
                return {"success": False, "message": "Which tab number should I switch to?"}
        return switch_tab(int(index), browser=self.default_browser)

    def _handle_write_note(self, target: str | None, params: dict) -> dict:
        text = params.get("text") or target
        if not text:
            return {"success": False, "message": "What should I write?"}
        return write_note_to_file(text, filepath=self.notes_file)

    def _handle_dictate(self, target: str | None, params: dict) -> dict:
        text = params.get("text") or target
        if not text:
            return {"success": False, "message": "What should I type?"}
        return paste_text(text)

    def _handle_query_claude(self, target: str | None, params: dict) -> dict:
        query = params.get("query") or target
        if not query:
            return {"success": False, "message": "What should I ask Claude?"}
        return query_claude(
            query=query,
            model=self.claude_model,
            max_tokens=self.claude_max_tokens,
        )

    def _handle_read_screen(self, target: str | None, params: dict) -> dict:
        query = params.get("query") or target
        result = read_screen(
            query=query,
            model=self.claude_model,
            max_tokens=self.claude_max_tokens,
        )
        # Inject screen reading into conversation history so follow-up queries have context
        if result.get("success") and result.get("message"):
            add_claude_context("user", "Read my screen.")
            add_claude_context("assistant", f"[Screen reading]: {result['message']}")
        return result

    def _handle_system_control(self, target: str | None, params: dict) -> dict:
        setting = (params.get("setting") or target or "").lower()
        value = params.get("value")

        if "volume" in setting:
            if value is not None:
                return set_volume(int(value))
            return {"success": False, "message": "What volume level?"}
        elif "mute" in setting:
            return set_mute(True)
        elif "unmute" in setting:
            return set_mute(False)
        elif "bright" in setting:
            if value is not None:
                return set_brightness(float(value) / 100.0)
            return {"success": False, "message": "What brightness level?"}
        elif "disturb" in setting or "dnd" in setting:
            return toggle_do_not_disturb()
        elif "sleep" in setting or "caffein" in setting:
            return prevent_sleep()
        elif "wake" in setting:
            return stop_prevent_sleep()
        else:
            return {"success": False, "message": f"Unknown system setting: {setting}"}

    def _handle_search_web(self, target: str | None, params: dict) -> dict:
        query = params.get("query") or target
        if not query:
            return {"success": False, "message": "What should I search for?"}
        # URL-encode the query for Google search
        import urllib.parse
        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}"
        return open_tab(url, browser=self.default_browser)

    def _handle_unknown(self, target: str | None, params: dict) -> dict:
        return {"success": False, "message": "I didn't understand that command."}

    # --- Handler dispatch table ---
    _handlers = {
        "open_app": _handle_open_app,
        "close_app": _handle_close_app,
        "open_tab": _handle_open_tab,
        "close_tab": _handle_close_tab,
        "switch_tab": _handle_switch_tab,
        "write_note": _handle_write_note,
        "dictate_to_app": _handle_dictate,
        "query_claude": _handle_query_claude,
        "read_screen": _handle_read_screen,
        "system_control": _handle_system_control,
        "search_web": _handle_search_web,
        "unknown": _handle_unknown,
    }
