#!/usr/bin/env python3
"""
MBC-20 Mint Bot — CLI entry point.

Single account:
  python3 mbc20-bot.py register --name MyAgent
  python3 mbc20-bot.py claim --auth-token TOKEN [--proxy URL]
  python3 mbc20-bot.py status
  python3 mbc20-bot.py mint [--loop] [--tick CLAW] [--amt 1000]

Batch operations:
  python3 mbc20-bot.py batch-claim --accounts accounts.txt
  python3 mbc20-bot.py batch-mint --loop
  python3 mbc20-bot.py batch-status
"""

import sys
import time
import random
import argparse

from mbc20.logger import log
from mbc20 import config, moltbook, twitter, solver


# ─── Single Account Commands ───

def cmd_register(args):
    name = args.name
    proxy = getattr(args, "proxy", None)
    log(f"Registering agent: {name}")
    data = moltbook.register(name, proxy=proxy)
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
        "profile_url": agent.get("profile_url", ""),
        "tweet_template": data.get("tweet_template", ""),
        "registered_at": agent["created_at"],
    }
    config.save(cfg)
    print(f"\n{'='*60}")
    print(f"✅ Agent registered: {agent['name']}")
    print(f"API Key: {agent['api_key']}")
    print(f"Claim: {agent['claim_url']}")
    print(f"{'='*60}")


def cmd_claim(args):
    """Full claim: register + tweet + OAuth + verify."""
    from mbc20.claim import claim_agent
    ok, result = claim_agent(
        args.auth_token,
        proxy=getattr(args, "proxy", None),
        agent_name=getattr(args, "name", None),
    )
    if ok:
        log(f"\n✅ Success! Agent: {result.get('agent_name')}")
        log(f"   API Key: {result.get('api_key', '(check config)')}")
    else:
        log(f"\n❌ Failed at step: {result.get('step')}")
        log(f"   Error: {result.get('error', '')}")


def cmd_status(args):
    cfg = config.load()
    if not cfg:
        log("❌ No config. Run 'register' first.")
        return
    proxy = getattr(args, "proxy", None)
    data = moltbook.status(cfg["api_key"], proxy=proxy)
    st = data.get("status", "unknown")
    if st == "claimed":
        print(f"✅ Agent '{cfg['agent_name']}' is active!")
    elif st == "pending_claim":
        print(f"⏳ Pending claim.")
    else:
        print(f"❓ {st} {data.get('error','')} {data.get('hint','')}")


def cmd_mint(args):
    cfg = config.load()
    if not cfg:
        log("❌ No config. Run 'register' first.")
        return
    proxy = getattr(args, "proxy", None)
    api_key, tick, amt, interval = cfg["api_key"], args.tick, args.amt, args.interval
    if args.loop:
        log(f"🔄 Loop: {amt} {tick} every {interval}s")
        count, fails = 0, 0
        while True:
            if _do_mint(api_key, tick, amt, proxy=proxy):
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
        _do_mint(api_key, tick, amt, proxy=proxy)


# ─── Batch Commands ───

def cmd_batch_claim(args):
    """Batch claim from accounts.txt (format: auth_token,proxy_url per line)."""
    from mbc20.claim import batch_claim

    accounts = []
    with open(args.accounts) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",", 1)
            token = parts[0].strip()
            proxy = parts[1].strip() if len(parts) > 1 else None
            accounts.append((token, proxy))

    if not accounts:
        log("❌ No accounts found in file.")
        return

    log(f"Loaded {len(accounts)} accounts from {args.accounts}")
    batch_claim(accounts, delay_between=args.delay)


def cmd_batch_status(args):
    """Check status of all saved accounts."""
    accounts = config.list_accounts()
    if not accounts:
        log("No saved accounts.")
        return

    log(f"=== {len(accounts)} accounts ===\n")
    for cfg in accounts:
        name = cfg.get("agent_name", "?")
        proxy = cfg.get("proxy")
        api_key = cfg.get("api_key")
        data = moltbook.status(api_key, proxy=proxy)
        st = data.get("status", "unknown")
        icon = "✅" if st == "claimed" else "⏳" if st == "pending_claim" else "❓"
        print(f"  {icon} {name:12s} | {st}")


def cmd_batch_mint(args):
    """Mint with all claimed accounts."""
    accounts = config.list_accounts()
    claimed = [a for a in accounts if True]  # filter later by status

    if not claimed:
        log("No saved accounts.")
        return

    tick, amt, interval = args.tick, args.amt, args.interval
    log(f"=== Batch Mint: {len(claimed)} accounts | {tick} | {amt}/mint | {interval}s interval ===\n")

    if args.loop:
        count = 0
        while True:
            for cfg in claimed:
                name = cfg.get("agent_name", "?")
                api_key = cfg.get("api_key")
                proxy = cfg.get("proxy")

                # Check if claimed
                st = moltbook.status(api_key, proxy=proxy)
                if st.get("status") != "claimed":
                    log(f"  ⏭️  {name}: not claimed, skipping")
                    continue

                if _do_mint(api_key, tick, amt, proxy=proxy, label=name):
                    count += 1

                # Small delay between accounts
                time.sleep(2)

            log(f"\n📊 Round done. Total mints: {count}. Next round in {interval}s...")
            time.sleep(interval)
    else:
        for cfg in claimed:
            name = cfg.get("agent_name", "?")
            api_key = cfg.get("api_key")
            proxy = cfg.get("proxy")
            st = moltbook.status(api_key, proxy=proxy)
            if st.get("status") != "claimed":
                log(f"  ⏭️  {name}: not claimed")
                continue
            _do_mint(api_key, tick, amt, proxy=proxy, label=name)


# ─── Helpers ───

def _do_mint(api_key, tick, amt, proxy=None, label=""):
    prefix = f"[{label}] " if label else ""
    log(f"{prefix}⛏️  Minting {amt} {tick}...")
    flair = f"t{int(time.time())}-{random.randint(100, 999)}"

    data = moltbook.create_mint_post(api_key, tick, amt, flair, proxy=proxy)
    if not data.get("success"):
        log(f"{prefix}  ❌ {data.get('error','')} {data.get('hint','')}")
        return False

    post_id = data.get("post", {}).get("id", "?")
    v = data.get("verification", {})
    code, challenge = v.get("code"), v.get("challenge")

    if not code:
        log(f"{prefix}  ✅ Minted (no verify): {post_id}")
        return True

    log(f"{prefix}  🔒 Challenge: {challenge[:80]}...")
    answer = solver.solve(challenge)
    if not answer:
        log(f"{prefix}  ❌ Can't solve challenge")
        return False

    vd = moltbook.verify(api_key, code, answer, proxy=proxy)
    if vd.get("success"):
        log(f"{prefix}  ✅ Minted {amt} {tick}!")
        return True
    log(f"{prefix}  ❌ Verify failed: {vd.get('error','')}")
    return False


# ─── Main ───

def main():
    p = argparse.ArgumentParser(description="MBC-20 Mint Bot")
    sub = p.add_subparsers(dest="cmd")

    # Single account
    r = sub.add_parser("register", help="Register agent")
    r.add_argument("--name", required=True)
    r.add_argument("--proxy", default=None)

    c = sub.add_parser("claim", help="Full claim: register + tweet + OAuth + verify")
    c.add_argument("--auth-token", required=True)
    c.add_argument("--proxy", default=None)
    c.add_argument("--name", default=None, help="Agent name (random if omitted)")

    s = sub.add_parser("status", help="Check status")
    s.add_argument("--proxy", default=None)

    m = sub.add_parser("mint", help="Mint tokens")
    m.add_argument("--tick", default="CLAW")
    m.add_argument("--amt", default="1000")
    m.add_argument("--loop", action="store_true")
    m.add_argument("--interval", type=int, default=7200)
    m.add_argument("--proxy", default=None)

    # Batch
    bc = sub.add_parser("batch-claim", help="Batch claim from accounts.txt")
    bc.add_argument("--accounts", required=True, help="Path to accounts.txt")
    bc.add_argument("--delay", type=int, default=5, help="Delay between accounts (s)")

    sub.add_parser("batch-status", help="Status of all saved accounts")

    bm = sub.add_parser("batch-mint", help="Mint with all claimed accounts")
    bm.add_argument("--tick", default="CLAW")
    bm.add_argument("--amt", default="1000")
    bm.add_argument("--loop", action="store_true")
    bm.add_argument("--interval", type=int, default=7200)

    args = p.parse_args()
    cmds = {
        "register": cmd_register,
        "claim": cmd_claim,
        "status": cmd_status,
        "mint": cmd_mint,
        "batch-claim": cmd_batch_claim,
        "batch-status": cmd_batch_status,
        "batch-mint": cmd_batch_mint,
    }
    fn = cmds.get(args.cmd)
    if fn:
        fn(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
