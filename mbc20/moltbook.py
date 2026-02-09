"""Moltbook API client with proxy support."""

import json as _json
import requests

BASE_URL = "https://www.moltbook.com/api/v1"


def _headers(api_key):
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _proxies(proxy_url):
    if not proxy_url:
        return None
    return {"http": proxy_url, "https": proxy_url}


def post(path, data, api_key=None, proxy=None):
    """POST to Moltbook API."""
    headers = _headers(api_key) if api_key else {"Content-Type": "application/json"}
    try:
        return requests.post(
            f"{BASE_URL}/{path}", headers=headers, json=data,
            timeout=30, proxies=_proxies(proxy),
        ).json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def get(path, api_key, proxy=None):
    """GET from Moltbook API."""
    try:
        return requests.get(
            f"{BASE_URL}/{path}", headers=_headers(api_key),
            timeout=30, proxies=_proxies(proxy),
        ).json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def register(name, description=None, proxy=None):
    """Register a new agent."""
    desc = description or f"AI agent {name}"
    return post("agents/register", {"name": name, "description": desc}, proxy=proxy)


def status(api_key, proxy=None):
    """Check agent claim status."""
    return get("agents/status", api_key, proxy=proxy)


def create_mint_post(api_key, tick, amt, flair, proxy=None):
    """Create a mint inscription post."""
    inscription = _json.dumps({"p": "mbc-20", "op": "mint", "tick": tick, "amt": amt})
    return post("posts", {
        "submolt": "general",
        "title": f"Minting {tick} | {flair}",
        "content": f"{inscription}\n\nmbc20.xyz\n\n{flair}"
    }, api_key, proxy=proxy)


def verify(api_key, verification_code, answer, proxy=None):
    """Submit verification answer."""
    return post("verify", {
        "verification_code": verification_code,
        "answer": answer
    }, api_key, proxy=proxy)
