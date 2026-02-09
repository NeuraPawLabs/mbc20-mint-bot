"""Config management."""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "moltbook"
CONFIG_FILE = CONFIG_DIR / "credentials.json"


def load():
    """Load config from file. Returns None if not found."""
    if not CONFIG_FILE.exists():
        return None
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save(data):
    """Save config to file with restricted permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)
