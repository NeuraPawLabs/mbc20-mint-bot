"""Moltbook API client."""

import requests

BASE_URL = "https://www.moltbook.com/api/v1"


def _headers(api_key):
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def post(path, data, api_key=None):
    """POST to Moltbook API."""
    headers = _headers(api_key) if api_key else {"Content-Type": "application/json"}
    try:
        return requests.post(f"{BASE_URL}/{path}", headers=headers, json=data, timeout=30).json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def get(path, api_key):
    """GET from Moltbook API."""
    try:
        return requests.get(f"{BASE_URL}/{path}", headers=_headers(api_key), timeout=30).json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def register(name, description=None):
    """Register a new agent."""
    desc = description or f"AI agent {name}"
    return post("agents/register", {"name": name, "description": desc})


def status(api_key):
    """Check agent claim status."""
    return get("agents/status", api_key)


def create_mint_post(api_key, tick, amt, flair):
    """Create a mint inscription post."""
    import json as _json
    inscription = _json.dumps({"p": "mbc-20", "op": "mint", "tick": tick, "amt": amt})
    return post("posts", {
        "submolt": "general",
        "title": f"Minting {tick} | {flair}",
        "content": f"{inscription}\n\nmbc20.xyz\n\n{flair}"
    }, api_key)


def verify(api_key, verification_code, answer):
    """Submit verification answer."""
    return post("verify", {
        "verification_code": verification_code,
        "answer": answer
    }, api_key)
