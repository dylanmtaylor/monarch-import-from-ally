"""CDP connection and token extraction for Ally Bank."""

import json
import time
import urllib.request
import websocket
from typing import Optional, Dict, Any


DEFAULT_API_KEY = "XhnbsDYmBensf2vqVXAfv0uD7SJBA27u"


class CDPError(Exception):
    """Raised when CDP connection or token capture fails."""
    pass


def find_ally_tab(port: int = 9222) -> Dict[str, Any]:
    """Find the Ally Bank tab in Chrome DevTools Protocol."""
    try:
        url = f"http://127.0.0.1:{port}/json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            tabs = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise CDPError(
            f"Could not connect to Chrome debugging port {port}: {e}. "
            f"Ensure Chrome is running with --remote-debugging-port={port}"
        )

    # First look for active secure.ally.com tab
    for tab in tabs:
        tab_url = tab.get("url", "")
        if "secure.ally.com" in tab_url and tab.get("type") == "page":
            return tab

    # Fallback to any ally.com tab
    for tab in tabs:
        tab_url = tab.get("url", "")
        if "ally.com" in tab_url and tab.get("type") == "page":
            return tab

    raise CDPError(
        "No open Ally Bank tab found. Please log in to https://secure.ally.com in Chrome."
    )


def capture_session(port: int = 9222, timeout_seconds: float = 12.0) -> Dict[str, Any]:
    """Connect to the Ally tab via CDP and capture active bearer token and session metadata."""
    tab = find_ally_tab(port=port)
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        raise CDPError(f"Tab {tab.get('id')} has no webSocketDebuggerUrl available.")

    ws = websocket.create_connection(ws_url, suppress_origin=True, timeout=5)
    try:
        # Enable network monitoring
        ws.send(json.dumps({"id": 1, "method": "Network.enable"}))

        # Check if tab is on dashboard or statements
        curr_url = tab.get("url", "")
        target_url = "https://secure.ally.com/dashboard"
        
        # Navigate to dashboard to trigger full re-authentication / token issuance
        ws.send(json.dumps({
            "id": 2,
            "method": "Page.navigate",
            "params": {"url": target_url}
        }))

        start = time.time()
        bearer_token: Optional[str] = None
        api_key: str = DEFAULT_API_KEY
        customer_id: Optional[str] = None

        while time.time() - start < timeout_seconds:
            try:
                ws.settimeout(0.5)
                raw = ws.recv()
                msg = json.loads(raw)
                method = msg.get("method")
                if method == "Network.requestWillBeSent":
                    params = msg.get("params", {})
                    req = params.get("request", {})
                    headers = req.get("headers", {})
                    u = req.get("url", "")

                    # Check for Bearer token in headers
                    for h_name, h_val in headers.items():
                        if h_name.lower() == "authorization" and "bearer tstk" in h_val.lower():
                            # Remove "Bearer " prefix
                            parts = h_val.split()
                            if len(parts) == 2:
                                bearer_token = parts[1]
                        if h_name.lower() == "api-key" and h_val:
                            api_key = h_val

                    # Check for customerId in url
                    if "customerId=" in u:
                        cid = u.split("customerId=")[1].split("&")[0]
                        if cid and cid.isdigit():
                            customer_id = cid

                    if bearer_token and customer_id:
                        break
            except websocket.WebSocketTimeoutException:
                pass

        if not bearer_token:
            # Fallback: evaluate script to check if we can get token
            eval_script = """
            (async () => {
                return window.__token || null;
            })()
            """
            ws.send(json.dumps({
                "id": 3,
                "method": "Runtime.evaluate",
                "params": {"expression": eval_script, "returnByValue": True}
            }))

        if not bearer_token:
            raise CDPError(
                "Failed to capture active Ally Bearer token. Please ensure you are logged into Ally Bank."
            )

        return {
            "token": bearer_token,
            "api_key": api_key,
            "customer_id": customer_id,
            "tab_id": tab.get("id"),
            "tab_title": tab.get("title")
        }
    finally:
        try:
            ws.close()
        except Exception:
            pass
