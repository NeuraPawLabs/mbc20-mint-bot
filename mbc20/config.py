"""Config management — supports global + per-account configs."""

import json
import os
import hashlib
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "moltbook"
CONFIG_FILE = CONFIG_DIR / "credentials.json"
ACCOUNTS_DIR = CONFIG_DIR / "accounts"


def load():
    """Load global config."""
    if not CONFIG_FILE.exists():
        return None
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save(data):
    """Save global config."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)


def account_dir(auth_token):
    """Get per-account config directory (by token hash)."""
    h = hashlib.sha256(auth_token.encode()).hexdigest()[:12]
    d = ACCOUNTS_DIR / h
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_account(auth_token):
    """Load per-account config."""
    cfg_file = account_dir(auth_token) / "config.json"
    if not cfg_file.exists():
        return None
    with open(cfg_file) as f:
        return json.load(f)


def save_account(auth_token, data):
    """Save per-account config."""
    d = account_dir(auth_token)
    cfg_file = d / "config.json"
    with open(cfg_file, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(cfg_file, 0o600)
    return cfg_file


def list_accounts():
    """List all saved account configs."""
    if not ACCOUNTS_DIR.exists():
        return []
    configs = []
    for cfg_file in sorted(ACCOUNTS_DIR.glob("*/config.json")):
        with open(cfg_file) as f:
            configs.append(json.load(f))
    return configs
