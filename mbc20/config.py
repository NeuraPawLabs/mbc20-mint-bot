"""Config management — multi-account support."""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "moltbook"
ACCOUNTS_DIR = CONFIG_DIR / "accounts"
ACCOUNTS_FILE = CONFIG_DIR / "accounts.txt"

# Legacy single-account
LEGACY_FILE = CONFIG_DIR / "credentials.json"


def load_accounts_file(path=None):
    """
    Load accounts from file. Format: auth_token,proxy_url (one per line).
    Returns list of {"auth_token": ..., "proxy": ...}.
    """
    p = Path(path) if path else ACCOUNTS_FILE
    if not p.exists():
        return []
    accounts = []
    for line in p.read_text().strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",", 1)
        auth_token = parts[0].strip()
        proxy = parts[1].strip() if len(parts) > 1 else None
        accounts.append({"auth_token": auth_token, "proxy": proxy})
    return accounts


def account_dir(account_id):
    """Get config dir for a specific account."""
    d = ACCOUNTS_DIR / account_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def load(account_id=None):
    """Load config for an account. Falls back to legacy single-account."""
    if account_id:
        f = ACCOUNTS_DIR / account_id / "credentials.json"
        if f.exists():
            with open(f) as fh:
                return json.load(fh)
        return None
    # Legacy
    if LEGACY_FILE.exists():
        with open(LEGACY_FILE) as f:
            return json.load(f)
    return None


def save(data, account_id=None):
    """Save config for an account."""
    if account_id:
        d = ACCOUNTS_DIR / account_id
        d.mkdir(parents=True, exist_ok=True)
        f = d / "credentials.json"
    else:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        f = LEGACY_FILE
    with open(f, 'w') as fh:
        json.dump(data, fh, indent=2)
    os.chmod(f, 0o600)


def list_accounts():
    """List all registered account IDs."""
    if not ACCOUNTS_DIR.exists():
        return []
    return sorted([
        d.name for d in ACCOUNTS_DIR.iterdir()
        if d.is_dir() and (d / "credentials.json").exists()
    ])
