#!/usr/bin/env python3
"""
MBC-20 Mint Bot — CLI entry point.

Usage:
  python3 mbc20-bot.py register --name MyAgent
  python3 mbc20-bot.py tweet --auth-token TOKEN
  python3 mbc20-bot.py verify --auth-token TOKEN
  python3 mbc20-bot.py claim --auth-token TOKEN   # tweet + verify all-in-one
  python3 mbc20-bot.py status
  python3 mbc20-bot.py mint [--loop] [--tick CLAW] [--amt 1000] [--interval 7200]
"""

import sys
import time
import random
import argparse

from mbc20.logger import log
from mbc20 import config, moltbook, twitter, solver


# ─── Commands ───

def cmd_register(args):
    name, desc = args.name, args.desc or f"AI agent {name}"
    log(f"Registering agent: {name}")
    data = moltbook.register(name, desc)
    if not data.get("success"):
        log(f"❌ Failed: {data.get('error','')} {data.get('hint','')}")
        return
    agent = data["agent"]
    cfg = {
        "api_key": agent["api_key"],
        "agent_name": agent["name"],
        "agent_id": agent["id"],
        "claim_url": agent["claim_url"],
        "verification_code": agent["verification_code"],
        "profile_url": agent["profile_url"],
        "tweet_template": data.get("tweet_template", ""),
        "registered_at": agent["created_at"],
    }
    config.save(cfg)
    print(f"\n{'='*60}")
    print(f"✅ Agent registered: {agent['name']}")
    print(f"{'='*60}")
    print(f"API Key: {agent['api_key']}")
    print(f"\n📋 Next: python3 {sys.argv[0]} claim --auth-token YOUR_TOKEN")
    print(f"{'='*60}")


def cmd_tweet(args):
    """Post verification tweet only."""
    cfg = config.load()
    if not cfg:
        log("❌ No config. Run 'register' first.")
        return

    tweet_text = cfg.get("tweet_template", "")
    if not tweet_text:
        log("❌ No tweet template. Re-run 'register'.")
        return

    log("Setting up Twitter session...")
    session, ct0 = twitter.create_session(args.auth_token)
    if not ct0:
        log("❌ Failed to get CSRF token. Check auth_token.")
        return
    log("  ✅ Twitter session ready")

    log("Posting verification tweet...")
    ok, result = twitter.post_tweet(session, ct0, tweet_text)
    if not ok:
        log(f"❌ Tweet failed: {result}")
        return

    log(f"  ✅ Tweet posted: https://x.com/i/status/{result}")
    log(f"\nNext: python3 {sys.argv[0]} verify --auth-token YOUR_TOKEN")


def cmd_verify(args):
    """Complete OAuth verification (assumes tweet already posted)."""
    cfg = config.load()
    if not cfg:
        log("❌ No config. Run 'register' first.")
        return

    api_key = cfg["api_key"]
    claim_url = cfg.get("claim_url", "")

    if moltbook.status(api_key).get("status") == "claimed":
        log("✅ Already claimed!")
        return

    log("Setting up Twitter session...")
    session, ct0 = twitter.create_session(args.auth_token)
    if not ct0:
        log("❌ Failed to get CSRF token.")
        return
    log("  ✅ Twitter session ready")

    log("Getting OAuth URL from Moltbook...")
    oauth_url = twitter.get_moltbook_oauth_url(session, claim_url)

    if not oauth_url:
        log("❌ Could not get OAuth URL. Falling back to manual...")
        log(f"   Open: {claim_url}")
        _wait_for_claim(api_key)
        return

    log("Authorizing via Twitter OAuth 2.0...")
    ok, result = twitter.oauth2_authorize(session, ct0, oauth_url)

    if not ok:
        log(f"❌ OAuth failed: {result}")
        return

    log(f"  Callback URL: {result}")
    log("Completing OAuth flow...")
    try:
        session.get(result, timeout=10, allow_redirects=True)
    except Exception as e:
        log(f"  ⚠️ Callback: {e}")

    # Verify tweet
    log("Verifying tweet...")
    claim_token = claim_url.split("/")[-1].split("?")[0]
    try:
        session.post(
            "https://www.moltbook.com/api/v1/agents/verify-tweet",
            headers={
                "Content-Type": "application/json",
                "Referer": claim_url,
                "Origin": "https://www.moltbook.com",
            },
            json={"token": claim_token},
            timeout=10,
        )
    except:
        pass

    _wait_for_claim(api_key, max_tries=10, interval=3)


def cmd_claim(args):
    """All-in-one: tweet + verify."""
    cfg = config.load()
    if not cfg:
        log("❌ No config. Run 'register' first.")
        return

    api_key = cfg["api_key"]
    tweet_text = cfg.get("tweet_template", "")
    claim_url = cfg.get("claim_url", "")

    if moltbook.status(api_key).get("status") == "claimed":
        log("✅ Already claimed!")
        return

    log("Setting up Twitter session...")
    session, ct0 = twitter.create_session(args.auth_token)
    if not ct0:
        log("❌ Failed to get CSRF token.")
        return
    log("  ✅ Twitter session ready")

    # Tweet
    log("Posting verification tweet...")
    ok, result = twitter.post_tweet(session, ct0, tweet_text)
    if not ok:
        log(f"❌ Tweet failed: {result}")
        return
    log(f"  ✅ Tweet posted: https://x.com/i/status/{result}")

    # OAuth
    log("Getting OAuth URL...")
    oauth_url = twitter.get_moltbook_oauth_url(session, claim_url)

    if not oauth_url:
        log("❌ Could not get OAuth URL automatically.")
        log(f"   Open manually: {claim_url}")
        _wait_for_claim(api_key)
        return

    log("Authorizing via Twitter OAuth 2.0...")
    ok, callback = twitter.oauth2_authorize(session, ct0, oauth_url)
    if not ok:
        log(f"❌ OAuth failed: {callback}")
        log(f"   Open manually: {claim_url}")
        return

    log("Completing claim...")
    try:
        session.get(callback, timeout=15, allow_redirects=True)
    except:
        pass

    _wait_for_claim(api_key, max_tries=10, interval=3)


def cmd_status(args):
    cfg = config.load()
    if not cfg:
        log("❌ No config. Run 'register' first.")
        return
    data = moltbook.status(cfg["api_key"])
    st = data.get("status", "unknown")
    if st == "claimed":
        print(f"✅ Agent '{cfg['agent_name']}' is active! Run: python3 {sys.argv[0]} mint --loop")
    elif st == "pending_claim":
        print(f"⏳ Pending. Run: python3 {sys.argv[0]} claim --auth-token TOKEN")
    else:
        print(f"❓ {st} {data.get('error','')} {data.get('hint','')}")


def cmd_mint(args):
    cfg = config.load()
    if not cfg:
        log("❌ No config. Run 'register' first.")
        return
    api_key, tick, amt, interval = cfg["api_key"], args.tick, args.amt, args.interval
    if args.loop:
        log(f"🔄 Loop: {amt} {tick} every {interval}s")
        count, fails = 0, 0
        while True:
            if _do_mint(api_key, tick, amt):
                count += 1
                fails = 0
                log(f"📊 Total: {count} | Next in {interval}s...")
            else:
                fails += 1
                wait = min(interval, 300 * fails)
                log(f"⏳ Fail #{fails}, retry in {wait}s...")
                time.sleep(wait)
                continue
            time.sleep(interval)
    else:
        _do_mint(api_key, tick, amt)


# ─── Helpers ───

def _do_mint(api_key, tick, amt):
    log(f"⛏️  Minting {amt} {tick}...")
    flair = f"t{int(time.time())}-{random.randint(100, 999)}"

    data = moltbook.create_mint_post(api_key, tick, amt, flair)
    if not data.get("success"):
        log(f"  ❌ {data.get('error','')} {data.get('hint','')}")
        return False

    post_id = data.get("post", {}).get("id", "?")
    v = data.get("verification", {})
    code, challenge = v.get("code"), v.get("challenge")

    if not code:
        log(f"  ✅ Minted (no verify): {post_id}")
        return True

    answer = solver.solve(challenge)
    if not answer:
        log("  ❌ Can't solve challenge")
        return False
    log(f"  💡 {answer}")

    vd = moltbook.verify(api_key, code, answer)
    if vd.get("success"):
        log(f"  ✅ Minted {amt} {tick}!")
        return True
    log(f"  ❌ Verify failed: {vd.get('error','')}")
    return False


def _wait_for_claim(api_key, max_tries=120, interval=10):
    log("Checking claim status...")
    for i in range(max_tries):
        time.sleep(interval)
        if moltbook.status(api_key).get("status") == "claimed":
            log("✅ Agent claimed successfully!")
            log(f"   Start minting: python3 {sys.argv[0]} mint --loop")
            return True
        if i % 6 == 0 and i > 0:
            log(f"  Still waiting... ({(i * interval) // 60} min)")
    log("⏳ Timeout. Check: python3 mbc20-bot.py status")
    return False


# ─── Main ───

def main():
    p = argparse.ArgumentParser(description="MBC-20 Mint Bot")
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("register", help="Register agent")
    r.add_argument("--name", required=True)
    r.add_argument("--desc", default=None)

    t = sub.add_parser("tweet", help="Step 1: Post verification tweet")
    t.add_argument("--auth-token", required=True)

    v = sub.add_parser("verify", help="Step 2: Complete OAuth verification")
    v.add_argument("--auth-token", required=True)

    c = sub.add_parser("claim", help="All-in-one: tweet + verify")
    c.add_argument("--auth-token", required=True)

    sub.add_parser("status", help="Check status")

    m = sub.add_parser("mint", help="Mint tokens")
    m.add_argument("--tick", default="CLAW")
    m.add_argument("--amt", default="1000")
    m.add_argument("--loop", action="store_true")
    m.add_argument("--interval", type=int, default=7200)

    args = p.parse_args()
    cmds = {
        "register": cmd_register, "tweet": cmd_tweet,
        "verify": cmd_verify, "claim": cmd_claim,
        "status": cmd_status, "mint": cmd_mint,
    }
    cmds.get(args.cmd, lambda _: p.print_help())(args)


if __name__ == "__main__":
    main()
