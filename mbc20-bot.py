#!/usr/bin/env python3
"""
MBC-20 Mint Bot — Multi-account CLI.

Single account:
  python3 mbc20-bot.py register --name MyAgent
  python3 mbc20-bot.py claim --auth-token TOKEN
  python3 mbc20-bot.py mint --loop

Multi-account (accounts.txt: auth_token,proxy_url per line):
  python3 mbc20-bot.py batch-register --accounts accounts.txt
  python3 mbc20-bot.py batch-claim --accounts accounts.txt
  python3 mbc20-bot.py batch-mint --accounts accounts.txt
  python3 mbc20-bot.py batch-status --accounts accounts.txt
"""

import sys
import time
import random
import argparse
import hashlib
import threading

from mbc20.logger import log
from mbc20 import config, moltbook, twitter, solver


# ─── Single Account Commands ───

def cmd_register(args):
    name, desc = args.name, args.desc or f"AI agent {name}"
    proxy = getattr(args, 'proxy', None)
    log(f"Registering agent: {name}")
    data = moltbook.register(name, desc, proxy=proxy)
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
    cfg = config.load()
    if not cfg:
        log("❌ No config. Run 'register' first."); return
    tweet_text = cfg.get("tweet_template", "")
    if not tweet_text:
        log("❌ No tweet template."); return

    log("Setting up Twitter session...")
    session, ct0 = twitter.create_session(args.auth_token, proxy=getattr(args, 'proxy', None))
    if not ct0:
        log("❌ Failed to get CSRF token."); return
    log("  ✅ Ready")

    ok, result = twitter.post_tweet(session, ct0, tweet_text)
    if ok:
        log(f"  ✅ Tweet: https://x.com/i/status/{result}")
    else:
        log(f"❌ Failed: {result}")


def cmd_verify(args):
    cfg = config.load()
    if not cfg:
        log("❌ No config."); return
    api_key, claim_url = cfg["api_key"], cfg.get("claim_url", "")
    proxy = getattr(args, 'proxy', None)

    if moltbook.status(api_key, proxy=proxy).get("status") == "claimed":
        log("✅ Already claimed!"); return

    session, ct0 = twitter.create_session(args.auth_token, proxy=proxy)
    if not ct0:
        log("❌ CSRF token failed."); return

    _do_verify(session, ct0, api_key, claim_url, proxy)


def cmd_claim(args):
    cfg = config.load()
    if not cfg:
        log("❌ No config."); return
    api_key = cfg["api_key"]
    tweet_text = cfg.get("tweet_template", "")
    claim_url = cfg.get("claim_url", "")
    proxy = getattr(args, 'proxy', None)

    if moltbook.status(api_key, proxy=proxy).get("status") == "claimed":
        log("✅ Already claimed!"); return

    session, ct0 = twitter.create_session(args.auth_token, proxy=proxy)
    if not ct0:
        log("❌ CSRF token failed."); return

    ok, result = twitter.post_tweet(session, ct0, tweet_text)
    if not ok:
        log(f"❌ Tweet failed: {result}"); return
    log(f"  ✅ Tweet: https://x.com/i/status/{result}")

    _do_verify(session, ct0, api_key, claim_url, proxy)


def cmd_status(args):
    cfg = config.load()
    if not cfg:
        log("❌ No config."); return
    data = moltbook.status(cfg["api_key"])
    st = data.get("status", "unknown")
    if st == "claimed":
        print(f"✅ '{cfg['agent_name']}' active")
    elif st == "pending_claim":
        print(f"⏳ '{cfg['agent_name']}' pending")
    else:
        print(f"❓ {st} {data.get('error','')} {data.get('hint','')}")


def cmd_mint(args):
    cfg = config.load()
    if not cfg:
        log("❌ No config."); return
    api_key = cfg["api_key"]
    proxy = getattr(args, 'proxy', None)
    tick, amt, interval = args.tick, args.amt, args.interval

    if args.loop:
        log(f"🔄 Loop: {amt} {tick} every {interval}s")
        count, fails = 0, 0
        while True:
            if _do_mint(api_key, tick, amt, proxy):
                count += 1; fails = 0
                log(f"📊 Total: {count} | Next in {interval}s...")
            else:
                fails += 1
                wait = min(interval, 300 * fails)
                log(f"⏳ Fail #{fails}, retry in {wait}s...")
                time.sleep(wait); continue
            time.sleep(interval)
    else:
        _do_mint(api_key, tick, amt, proxy)


# ─── Batch (Multi-Account) Commands ───

def _account_id(auth_token):
    """Generate a stable account ID from auth_token."""
    return hashlib.sha256(auth_token.encode()).hexdigest()[:12]


def _load_accounts(args):
    """Load accounts from file."""
    path = getattr(args, 'accounts', None)
    accounts = config.load_accounts_file(path)
    if not accounts:
        log(f"❌ No accounts found in {path or config.ACCOUNTS_FILE}")
    return accounts


def cmd_batch_register(args):
    accounts = _load_accounts(args)
    if not accounts:
        return

    for i, acc in enumerate(accounts):
        aid = _account_id(acc["auth_token"])
        proxy = acc.get("proxy")
        name = f"agent_{aid}"

        log(f"\n[{i+1}/{len(accounts)}] Registering {name} (proxy: {proxy or 'none'})...")

        # Check if already registered
        existing = config.load(aid)
        if existing:
            log(f"  ⏭️  Already registered: {existing['agent_name']}")
            continue

        data = moltbook.register(name, proxy=proxy)
        if not data.get("success"):
            log(f"  ❌ {data.get('error','')} {data.get('hint','')}")
            continue

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
            "auth_token": acc["auth_token"],
            "proxy": proxy,
        }
        config.save(cfg, aid)
        log(f"  ✅ Registered: {agent['name']}")

    log(f"\n✅ Done. {len(accounts)} accounts processed.")


def cmd_batch_claim(args):
    accounts = _load_accounts(args)
    if not accounts:
        return

    for i, acc in enumerate(accounts):
        aid = _account_id(acc["auth_token"])
        proxy = acc.get("proxy")
        cfg = config.load(aid)

        log(f"\n[{i+1}/{len(accounts)}] Claiming {cfg['agent_name'] if cfg else aid}...")

        if not cfg:
            log("  ❌ Not registered. Run batch-register first.")
            continue

        api_key = cfg["api_key"]
        if moltbook.status(api_key, proxy=proxy).get("status") == "claimed":
            log("  ✅ Already claimed")
            continue

        tweet_text = cfg.get("tweet_template", "")
        claim_url = cfg.get("claim_url", "")

        session, ct0 = twitter.create_session(acc["auth_token"], proxy=proxy)
        if not ct0:
            log("  ❌ Twitter session failed")
            continue

        ok, result = twitter.post_tweet(session, ct0, tweet_text)
        if not ok:
            log(f"  ❌ Tweet failed: {result}")
            continue
        log(f"  ✅ Tweet posted")

        _do_verify(session, ct0, api_key, claim_url, proxy, quiet=True)

        time.sleep(3)  # Rate limit between accounts


def cmd_batch_status(args):
    accounts = _load_accounts(args)
    if not accounts:
        # Fall back to listing all registered accounts
        aids = config.list_accounts()
        if not aids:
            log("No accounts found."); return
        for aid in aids:
            cfg = config.load(aid)
            if cfg:
                st = moltbook.status(cfg["api_key"]).get("status", "?")
                icon = "✅" if st == "claimed" else "⏳" if st == "pending_claim" else "❓"
                print(f"  {icon} {cfg['agent_name']} ({aid}) — {st}")
        return

    for i, acc in enumerate(accounts):
        aid = _account_id(acc["auth_token"])
        cfg = config.load(aid)
        if not cfg:
            print(f"  ❌ {aid[:8]}... — not registered")
            continue
        proxy = acc.get("proxy")
        st = moltbook.status(cfg["api_key"], proxy=proxy).get("status", "?")
        icon = "✅" if st == "claimed" else "⏳" if st == "pending_claim" else "❓"
        print(f"  {icon} {cfg['agent_name']} ({aid}) — {st}")


def cmd_batch_mint(args):
    accounts = _load_accounts(args)
    if not accounts:
        return

    tick, amt, interval = args.tick, args.amt, args.interval

    if args.loop:
        log(f"🔄 Batch loop: {len(accounts)} accounts, {amt} {tick} every {interval}s")
        count = 0
        while True:
            for i, acc in enumerate(accounts):
                aid = _account_id(acc["auth_token"])
                cfg = config.load(aid)
                if not cfg:
                    continue
                proxy = acc.get("proxy")
                api_key = cfg["api_key"]
                name = cfg.get("agent_name", aid)

                log(f"[{i+1}/{len(accounts)}] {name}...")
                if _do_mint(api_key, tick, amt, proxy):
                    count += 1
                time.sleep(2)  # Small delay between accounts

            log(f"📊 Round complete. Total mints: {count} | Next round in {interval}s...")
            time.sleep(interval)
    else:
        for i, acc in enumerate(accounts):
            aid = _account_id(acc["auth_token"])
            cfg = config.load(aid)
            if not cfg:
                log(f"[{i+1}] {aid[:8]}... — not registered, skip")
                continue
            proxy = acc.get("proxy")
            name = cfg.get("agent_name", aid)
            log(f"[{i+1}/{len(accounts)}] {name}...")
            _do_mint(cfg["api_key"], tick, amt, proxy)
            time.sleep(2)


# ─── Helpers ───

def _do_verify(session, ct0, api_key, claim_url, proxy=None, quiet=False):
    """Complete OAuth verification."""
    if not quiet:
        log("Getting OAuth URL...")
    oauth_url = twitter.get_moltbook_oauth_url(session, claim_url)

    if not oauth_url:
        if not quiet:
            log("❌ Could not get OAuth URL.")
            log(f"   Open manually: {claim_url}")
        _wait_for_claim(api_key, proxy, max_tries=10, interval=3)
        return

    if not quiet:
        log("Authorizing via OAuth 2.0...")
    ok, result = twitter.oauth2_authorize(session, ct0, oauth_url)

    if not ok:
        if not quiet:
            log(f"❌ OAuth failed: {result}")
        return

    try:
        session.get(result, timeout=10, allow_redirects=True)
    except:
        pass

    # Verify tweet
    claim_token = claim_url.split("/")[-1].split("?")[0]
    try:
        session.post(
            "https://www.moltbook.com/api/v1/agents/verify-tweet",
            headers={"Content-Type": "application/json", "Referer": claim_url, "Origin": "https://www.moltbook.com"},
            json={"token": claim_token},
            timeout=10,
        )
    except:
        pass

    _wait_for_claim(api_key, proxy, max_tries=10, interval=3)


def _do_mint(api_key, tick, amt, proxy=None):
    """Execute one mint."""
    flair = f"t{int(time.time())}-{random.randint(100, 999)}"
    data = moltbook.create_mint_post(api_key, tick, amt, flair, proxy=proxy)
    if not data.get("success"):
        log(f"  ❌ {data.get('error','')} {data.get('hint','')}")
        return False

    v = data.get("verification", {})
    code, challenge = v.get("code"), v.get("challenge")
    if not code:
        log(f"  ✅ Minted (no verify)")
        return True

    answer = solver.solve(challenge)
    if not answer:
        log("  ❌ Can't solve challenge")
        return False
    log(f"  💡 {answer}")

    vd = moltbook.verify(api_key, code, answer, proxy=proxy)
    if vd.get("success"):
        log(f"  ✅ Minted {amt} {tick}!")
        return True
    log(f"  ❌ Verify failed: {vd.get('error','')}")
    return False


def _wait_for_claim(api_key, proxy=None, max_tries=10, interval=3):
    for i in range(max_tries):
        time.sleep(interval)
        if moltbook.status(api_key, proxy=proxy).get("status") == "claimed":
            log("  ✅ Claimed!")
            return True
    return False


# ─── Main ───

def main():
    p = argparse.ArgumentParser(description="MBC-20 Mint Bot")
    sub = p.add_subparsers(dest="cmd")

    # Single account
    r = sub.add_parser("register", help="Register agent")
    r.add_argument("--name", required=True)
    r.add_argument("--desc", default=None)
    r.add_argument("--proxy", default=None, help="Proxy URL")

    t = sub.add_parser("tweet", help="Post verification tweet")
    t.add_argument("--auth-token", required=True)
    t.add_argument("--proxy", default=None)

    v = sub.add_parser("verify", help="Complete OAuth verification")
    v.add_argument("--auth-token", required=True)
    v.add_argument("--proxy", default=None)

    c = sub.add_parser("claim", help="Tweet + verify all-in-one")
    c.add_argument("--auth-token", required=True)
    c.add_argument("--proxy", default=None)

    sub.add_parser("status", help="Check status")

    m = sub.add_parser("mint", help="Mint tokens")
    m.add_argument("--tick", default="CLAW")
    m.add_argument("--amt", default="1000")
    m.add_argument("--loop", action="store_true")
    m.add_argument("--interval", type=int, default=7200)
    m.add_argument("--proxy", default=None)

    # Batch (multi-account)
    br = sub.add_parser("batch-register", help="Register all accounts")
    br.add_argument("--accounts", default=None, help="Accounts file (default: ~/.config/moltbook/accounts.txt)")

    bc = sub.add_parser("batch-claim", help="Claim all accounts")
    bc.add_argument("--accounts", default=None)

    bs = sub.add_parser("batch-status", help="Status of all accounts")
    bs.add_argument("--accounts", default=None)

    bm = sub.add_parser("batch-mint", help="Mint for all accounts")
    bm.add_argument("--accounts", default=None)
    bm.add_argument("--tick", default="CLAW")
    bm.add_argument("--amt", default="1000")
    bm.add_argument("--loop", action="store_true")
    bm.add_argument("--interval", type=int, default=7200)

    args = p.parse_args()
    cmds = {
        "register": cmd_register, "tweet": cmd_tweet,
        "verify": cmd_verify, "claim": cmd_claim,
        "status": cmd_status, "mint": cmd_mint,
        "batch-register": cmd_batch_register,
        "batch-claim": cmd_batch_claim,
        "batch-status": cmd_batch_status,
        "batch-mint": cmd_batch_mint,
    }
    cmds.get(args.cmd, lambda _: p.print_help())(args)


if __name__ == "__main__":
    main()
