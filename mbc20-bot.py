#!/usr/bin/env python3
"""
MBC-20 Complete Mint Bot
From registration to auto-minting, all in one script.

Usage:
  # Step 1: Register a new agent
  python3 mbc20-bot.py register --name MyAgent --desc "My cool agent"
  
  # Step 2: After claiming via Twitter, check status
  python3 mbc20-bot.py status
  
  # Step 3: Single mint
  python3 mbc20-bot.py mint
  
  # Step 4: Auto-mint loop
  python3 mbc20-bot.py mint --loop

Config saved to: ~/.config/moltbook/credentials.json
"""

import requests
import json
import re
import time
import sys
import os
import argparse
import random
from datetime import datetime
from pathlib import Path

BASE_URL = "https://www.moltbook.com/api/v1"
CONFIG_DIR = Path.home() / ".config" / "moltbook"
CONFIG_FILE = CONFIG_DIR / "credentials.json"

# ─── Word-to-Number ───

WORD_NUMS = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
    'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
    'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
    'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
    'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30,
    'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
    'eighty': 80, 'ninety': 90, 'hundred': 100, 'thousand': 1000,
}

# ─── Helpers ───

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] {msg}")

def load_config():
    if not CONFIG_FILE.exists():
        return None
    with open(CONFIG_FILE) as f:
        return json.load(f)

def save_config(data):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    os.chmod(CONFIG_FILE, 0o600)
    log(f"Config saved to {CONFIG_FILE}")

def get_headers(api_key):
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

def api_post(path, data, api_key=None):
    headers = get_headers(api_key) if api_key else {"Content-Type": "application/json"}
    try:
        resp = requests.post(f"{BASE_URL}/{path}", headers=headers, json=data, timeout=30)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

def api_get(path, api_key):
    try:
        resp = requests.get(f"{BASE_URL}/{path}", headers=get_headers(api_key), timeout=30)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": str(e)}

# ─── Challenge Solver ───

def clean_challenge(text):
    cleaned = re.sub(r'[^a-zA-Z0-9 .,?]', ' ', text)
    return re.sub(r'\s+', ' ', cleaned).lower().strip()

def words_to_number(words):
    result = 0
    current = 0
    for w in words:
        if w not in WORD_NUMS:
            break
        val = WORD_NUMS[w]
        if val >= 100:
            current = (current or 1) * val
        else:
            current += val
    return result + current

def extract_numbers(text):
    numbers = []
    words = text.split()
    i = 0
    while i < len(words):
        w = words[i].strip('.,?!')
        if re.match(r'^\d+\.?\d*$', w):
            numbers.append(float(w))
            i += 1
        elif w in WORD_NUMS:
            num_words = []
            while i < len(words) and words[i].strip('.,?!') in WORD_NUMS:
                num_words.append(words[i].strip('.,?!'))
                i += 1
            numbers.append(words_to_number(num_words))
        else:
            i += 1
    return numbers

def detect_op(text):
    ops = {
        'add': ['accelerat', 'add', 'plus', 'increase', 'gain', 'faster', 'more', 'grows', 'grow', 'climbs', 'rises'],
        'sub': ['decelerat', 'subtract', 'minus', 'decrease', 'slow', 'less', 'lose', 'loses', 'drop', 'reduc', 'shrink', 'falls'],
        'mul': ['multipl', 'times', 'double', 'triple'],
        'div': ['divid', 'split', 'half', 'halv'],
    }
    for op, keywords in ops.items():
        if any(k in text for k in keywords):
            return op
    return 'add'

def solve_challenge(challenge):
    cleaned = clean_challenge(challenge)
    numbers = extract_numbers(cleaned)
    
    if len(numbers) < 2:
        raw = re.findall(r'\d+\.?\d*', challenge)
        numbers = [float(n) for n in raw]
    
    if len(numbers) < 2:
        return None
    
    op = detect_op(cleaned)
    a, b = numbers[0], numbers[1]
    
    if op == 'add':    result = a + b
    elif op == 'sub':  result = a - b
    elif op == 'mul':  result = a * b
    elif op == 'div':  result = a / b if b else 0
    else:              result = a + b
    
    return f"{result:.2f}"

# ─── Commands ───

def cmd_register(args):
    """Register a new agent on Moltbook."""
    name = args.name
    desc = args.desc or f"AI agent {name}"
    
    log(f"Registering agent: {name}")
    data = api_post("agents/register", {"name": name, "description": desc})
    
    if not data.get("success"):
        error = data.get("error", "unknown")
        hint = data.get("hint", "")
        log(f"❌ Registration failed: {error} {hint}")
        return
    
    agent = data["agent"]
    config = {
        "api_key": agent["api_key"],
        "agent_name": agent["name"],
        "agent_id": agent["id"],
        "claim_url": agent["claim_url"],
        "verification_code": agent["verification_code"],
        "profile_url": agent["profile_url"],
        "registered_at": agent["created_at"],
    }
    save_config(config)
    
    tweet = data.get("tweet_template", "")
    
    print()
    print("=" * 60)
    print(f"✅ Agent registered: {agent['name']}")
    print(f"=" * 60)
    print(f"API Key:    {agent['api_key']}")
    print(f"Profile:    {agent['profile_url']}")
    print()
    print("📋 Next steps:")
    print(f"  1. Open claim URL:")
    print(f"     {agent['claim_url']}")
    print()
    print(f"  2. Post this tweet:")
    print(f"     {tweet}")
    print()
    print(f"  3. After claiming, run:")
    print(f"     python3 {sys.argv[0]} status")
    print(f"     python3 {sys.argv[0]} mint --loop")
    print("=" * 60)

def cmd_status(args):
    """Check agent claim status."""
    config = load_config()
    if not config:
        log("❌ No config found. Run 'register' first.")
        return
    
    data = api_get("agents/status", config["api_key"])
    status = data.get("status", "unknown")
    
    if status == "claimed":
        print(f"✅ Agent '{config['agent_name']}' is claimed and active!")
        print(f"   Ready to mint. Run: python3 {sys.argv[0]} mint --loop")
    elif status == "pending_claim":
        print(f"⏳ Agent '{config['agent_name']}' is pending claim.")
        print(f"   Claim URL: {config.get('claim_url', 'N/A')}")
    else:
        error = data.get("error", "")
        hint = data.get("hint", "")
        print(f"❓ Status: {status} {error} {hint}")

def cmd_mint(args):
    """Mint tokens."""
    config = load_config()
    if not config:
        log("❌ No config found. Run 'register' first.")
        return
    
    api_key = config["api_key"]
    tick = args.tick
    amt = args.amt
    interval = args.interval
    
    if args.loop:
        log(f"🔄 Auto-mint loop: {amt} {tick} every {interval}s")
        mint_count = 0
        fail_count = 0
        while True:
            ok = do_mint(api_key, tick, amt)
            if ok:
                mint_count += 1
                fail_count = 0
                log(f"📊 Total mints: {mint_count} | Next in {interval}s...")
            else:
                fail_count += 1
                wait = min(interval, 300 * fail_count)  # backoff on failures
                log(f"⏳ Fail #{fail_count}, retry in {wait}s...")
                time.sleep(wait)
                continue
            time.sleep(interval)
    else:
        do_mint(api_key, tick, amt)

def do_mint(api_key, tick, amt):
    """Execute one mint."""
    log(f"⛏️  Minting {amt} {tick}...")
    
    flair = f"npaw-{int(time.time())}-{random.randint(100,999)}"
    inscription = json.dumps({"p": "mbc-20", "op": "mint", "tick": tick, "amt": amt})
    content = f"{inscription}\n\nmbc20.xyz\n\n{flair}"
    
    # Post
    data = api_post("posts", {
        "submolt": "general",
        "title": f"Minting {tick} | {flair}",
        "content": content
    }, api_key)
    
    if not data.get("success"):
        error = data.get("error", data.get("message", "unknown"))
        hint = data.get("hint", "")
        log(f"  ❌ Post failed: {error} {hint}")
        return False
    
    post_id = data.get("post", {}).get("id", "?")
    verification = data.get("verification", {})
    code = verification.get("code")
    challenge = verification.get("challenge")
    
    if not code or not challenge:
        log(f"  ✅ Minted (no verification needed): {post_id}")
        return True
    
    # Solve
    log(f"  🧩 Challenge: {challenge[:80]}...")
    answer = solve_challenge(challenge)
    if not answer:
        log(f"  ❌ Could not solve challenge")
        return False
    log(f"  💡 Answer: {answer}")
    
    # Verify
    vdata = api_post("verify", {
        "verification_code": code,
        "answer": answer
    }, api_key)
    
    if vdata.get("success"):
        log(f"  ✅ Minted {amt} {tick}!")
        return True
    else:
        error = vdata.get("error", vdata.get("message", "unknown"))
        log(f"  ❌ Verification failed: {error}")
        return False

# ─── Main ───

def main():
    parser = argparse.ArgumentParser(description="MBC-20 Complete Mint Bot")
    sub = parser.add_subparsers(dest="command")
    
    # register
    p_reg = sub.add_parser("register", help="Register a new agent")
    p_reg.add_argument("--name", required=True, help="Agent name")
    p_reg.add_argument("--desc", default=None, help="Agent description")
    
    # status
    sub.add_parser("status", help="Check claim status")
    
    # mint
    p_mint = sub.add_parser("mint", help="Mint tokens")
    p_mint.add_argument("--tick", default="CLAW", help="Token ticker (default: CLAW)")
    p_mint.add_argument("--amt", default="1000", help="Amount (default: 1000)")
    p_mint.add_argument("--loop", action="store_true", help="Run continuously")
    p_mint.add_argument("--interval", type=int, default=7200, help="Seconds between mints (default: 7200)")
    
    args = parser.parse_args()
    
    if args.command == "register":
        cmd_register(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "mint":
        cmd_mint(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
