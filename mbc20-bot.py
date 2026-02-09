#!/usr/bin/env python3
"""
MBC-20 Complete Mint Bot
Full automation: register → tweet verify → claim → auto-mint

Usage:
  python3 mbc20-bot.py register --name MyAgent
  python3 mbc20-bot.py claim --auth-token "YOUR_TWITTER_AUTH_TOKEN"
  python3 mbc20-bot.py status
  python3 mbc20-bot.py mint --loop

Config: ~/.config/moltbook/credentials.json
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

# ─── Twitter Constants ───

TWITTER_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
TWITTER_CREATE_TWEET_URL = "https://x.com/i/api/graphql/mnCM2YNMkpMB5bYEbGGKRQ/CreateTweet"

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

# ─── Twitter API ───

def get_twitter_ct0(auth_token):
    """Get ct0 CSRF token from Twitter using auth_token cookie."""
    session = requests.Session()
    session.cookies.set("auth_token", auth_token, domain=".x.com")
    
    try:
        resp = session.get("https://x.com/home", timeout=15, allow_redirects=True)
        ct0 = session.cookies.get("ct0", domain=".x.com")
        if ct0:
            return ct0, session
        
        # Try extracting from response
        for cookie in session.cookies:
            if cookie.name == "ct0":
                return cookie.value, session
    except Exception as e:
        log(f"  Failed to get ct0: {e}")
    
    return None, session

def post_tweet(auth_token, text):
    """Post a tweet using Twitter auth_token."""
    log(f"  Posting tweet...")
    
    ct0, session = get_twitter_ct0(auth_token)
    if not ct0:
        return False, "Failed to get CSRF token (ct0). Check your auth_token."
    
    headers = {
        "Authorization": f"Bearer {TWITTER_BEARER}",
        "Content-Type": "application/json",
        "X-Csrf-Token": ct0,
        "X-Twitter-Auth-Type": "OAuth2Session",
        "X-Twitter-Active-User": "yes",
        "X-Twitter-Client-Language": "en",
        "Referer": "https://x.com/compose/tweet",
        "Origin": "https://x.com",
    }
    
    payload = {
        "variables": {
            "tweet_text": text,
            "dark_request": False,
            "media": {"media_entities": [], "possibly_sensitive": False},
            "semantic_annotation_ids": [],
        },
        "features": {
            "communities_web_enable_tweet_community_results_fetch": True,
            "c9s_tweet_anatomy_moderator_badge_enabled": True,
            "tweetypie_unmention_optimization_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True,
            "tweet_awards_web_tipping_enabled": False,
            "creator_subscriptions_quote_tweet_preview_enabled": False,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "articles_preview_enabled": True,
            "rweb_video_timestamps_enabled": True,
            "rweb_tipjar_consumption_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_enhance_cards_enabled": False,
        },
        "queryId": "mnCM2YNMkpMB5bYEbGGKRQ",
    }
    
    session.cookies.set("ct0", ct0, domain=".x.com")
    
    try:
        resp = session.post(
            TWITTER_CREATE_TWEET_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        data = resp.json()
        
        tweet_result = data.get("data", {}).get("create_tweet", {}).get("tweet_results", {}).get("result", {})
        tweet_id = tweet_result.get("rest_id")
        
        if tweet_id:
            log(f"  ✅ Tweet posted: https://x.com/i/status/{tweet_id}")
            return True, tweet_id
        
        # Check for errors
        errors = data.get("errors", [])
        if errors:
            return False, errors[0].get("message", str(errors))
        
        return False, f"Unexpected response: {json.dumps(data)[:200]}"
        
    except Exception as e:
        return False, str(e)

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
    tweet_template = data.get("tweet_template", "")
    
    config = {
        "api_key": agent["api_key"],
        "agent_name": agent["name"],
        "agent_id": agent["id"],
        "claim_url": agent["claim_url"],
        "verification_code": agent["verification_code"],
        "profile_url": agent["profile_url"],
        "tweet_template": tweet_template,
        "registered_at": agent["created_at"],
    }
    save_config(config)
    
    print()
    print("=" * 60)
    print(f"✅ Agent registered: {agent['name']}")
    print("=" * 60)
    print(f"API Key:    {agent['api_key']}")
    print(f"Profile:    {agent['profile_url']}")
    print()
    print("📋 Next step — auto-claim:")
    print(f"  python3 {sys.argv[0]} claim --auth-token YOUR_TWITTER_AUTH_TOKEN")
    print()
    print("Or manual claim:")
    print(f"  1. Open: {agent['claim_url']}")
    print(f"  2. Tweet: {tweet_template}")
    print("=" * 60)

def cmd_claim(args):
    """Auto-claim: post verification tweet + open claim URL."""
    config = load_config()
    if not config:
        log("❌ No config found. Run 'register' first.")
        return
    
    auth_token = args.auth_token
    tweet_text = config.get("tweet_template", "")
    claim_url = config.get("claim_url", "")
    api_key = config.get("api_key", "")
    
    if not tweet_text:
        log("❌ No tweet template in config. Re-run 'register'.")
        return
    
    # Step 1: Check if already claimed
    status_data = api_get("agents/status", api_key)
    if status_data.get("status") == "claimed":
        log("✅ Already claimed! Skip to: python3 mbc20-bot.py mint --loop")
        return
    
    # Step 2: Post verification tweet
    log("Step 1/3: Posting verification tweet...")
    ok, result = post_tweet(auth_token, tweet_text)
    if not ok:
        log(f"❌ Tweet failed: {result}")
        log("Try manually: post the tweet and open the claim URL")
        log(f"  Tweet: {tweet_text}")
        log(f"  Claim: {claim_url}")
        return
    
    # Step 3: Open claim URL (trigger verification)
    log("Step 2/3: Triggering claim verification...")
    log(f"  Claim URL: {claim_url}")
    
    # The claim URL needs to be visited by the human in browser
    # But we can try hitting it via the API to see if auto-verification works
    # Moltbook checks Twitter for the verification tweet
    
    # Step 4: Poll for claim status
    log("Step 3/3: Waiting for Moltbook to verify...")
    log("  ⚠️  You may need to open the claim URL in your browser:")
    log(f"  {claim_url}")
    
    for i in range(30):  # Wait up to 5 minutes
        time.sleep(10)
        status_data = api_get("agents/status", api_key)
        status = status_data.get("status", "unknown")
        
        if status == "claimed":
            log("✅ Agent claimed successfully!")
            log(f"  Start minting: python3 {sys.argv[0]} mint --loop")
            return
        
        if i % 3 == 0:
            log(f"  Still pending... ({i*10}s)")
    
    log("⏳ Claim not confirmed yet. The tweet is posted.")
    log("  Open the claim URL in your browser to complete:")
    log(f"  {claim_url}")

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
        print(f"   Ready to mint: python3 {sys.argv[0]} mint --loop")
    elif status == "pending_claim":
        print(f"⏳ Agent '{config['agent_name']}' is pending claim.")
        print(f"   Claim: python3 {sys.argv[0]} claim --auth-token YOUR_TOKEN")
        print(f"   Or manual: {config.get('claim_url', 'N/A')}")
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
                wait = min(interval, 300 * fail_count)
                log(f"⏳ Fail #{fail_count}, retry in {wait}s...")
                time.sleep(wait)
                continue
            time.sleep(interval)
    else:
        do_mint(api_key, tick, amt)

def do_mint(api_key, tick, amt):
    """Execute one mint."""
    log(f"⛏️  Minting {amt} {tick}...")
    
    flair = f"t{int(time.time())}-{random.randint(100,999)}"
    inscription = json.dumps({"p": "mbc-20", "op": "mint", "tick": tick, "amt": amt})
    content = f"{inscription}\n\nmbc20.xyz\n\n{flair}"
    
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
        log(f"  ✅ Minted (no verification): {post_id}")
        return True
    
    log(f"  🧩 Challenge: {challenge[:80]}...")
    answer = solve_challenge(challenge)
    if not answer:
        log(f"  ❌ Could not solve challenge")
        return False
    log(f"  💡 Answer: {answer}")
    
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
    
    # claim
    p_claim = sub.add_parser("claim", help="Auto-claim via Twitter")
    p_claim.add_argument("--auth-token", required=True, help="Twitter auth_token cookie")
    
    # status
    sub.add_parser("status", help="Check claim status")
    
    # mint
    p_mint = sub.add_parser("mint", help="Mint tokens")
    p_mint.add_argument("--tick", default="CLAW", help="Token ticker (default: CLAW)")
    p_mint.add_argument("--amt", default="1000", help="Amount (default: 1000)")
    p_mint.add_argument("--loop", action="store_true", help="Run continuously")
    p_mint.add_argument("--interval", type=int, default=7200, help="Seconds between mints (default: 7200)")
    
    args = parser.parse_args()
    
    cmds = {
        "register": cmd_register,
        "claim": cmd_claim,
        "status": cmd_status,
        "mint": cmd_mint,
    }
    
    fn = cmds.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
