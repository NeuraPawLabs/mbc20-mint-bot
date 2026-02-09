"""Full claim flow: register → tweet → OAuth → verify (with retry)."""

import time
import random
import string

from . import config, moltbook, twitter
from .logger import log

# Delay after posting tweet before first verify attempt (seconds)
TWEET_INDEX_DELAY = 30
# Retry interval for verify-tweet (seconds)
VERIFY_RETRY_INTERVAL = 15
# Max retries for verify-tweet
VERIFY_MAX_RETRIES = 8
# Delay between status checks (seconds)
STATUS_CHECK_INTERVAL = 3
STATUS_MAX_CHECKS = 10


PREFIXES = [
    "Nova", "Neon", "Flux", "Volt", "Byte", "Apex", "Zeta", "Aero",
    "Cryo", "Dusk", "Echo", "Haze", "Iris", "Jade", "Kilo", "Lux",
    "Onyx", "Pulse", "Rift", "Sage", "Vex", "Warp", "Zen", "Arc",
    "Blitz", "Coda", "Drift", "Ember", "Fuse", "Glyph", "Helix",
    "Ion", "Jinx", "Karma", "Lyric", "Mist", "Nexus", "Orbit",
    "Prism", "Quasar", "Rune", "Spark", "Thorn", "Ultra", "Vibe",
    "Wave", "Xeno", "Yonder", "Zero", "Bolt", "Cipher", "Delta",
    "Frost", "Ghost", "Hyper", "Infra", "Jet", "Krypto", "Luna",
    "Macro", "Nano", "Omega", "Pixel", "Quantum", "Razor", "Solar",
    "Turbo", "Umbra", "Vector", "Wren", "Axiom",
]

SUFFIXES = [
    "Bot", "AI", "Agent", "Mind", "Core", "Net", "Hub", "Lab",
    "Sys", "Dev", "Ops", "Run", "Bit", "Node", "Link", "Mod",
    "Pro", "Max", "One", "X", "Go", "IO", "Fx", "Ware",
]


def random_name():
    """Generate a meaningful-looking agent name like 'NeonBot' or 'PulseAI'."""
    prefix = random.choice(PREFIXES)
    suffix = random.choice(SUFFIXES)
    # ~30% chance to append a short number for uniqueness
    tag = str(random.randint(1, 99)) if random.random() < 0.3 else ""
    return f"{prefix}{suffix}{tag}"


def register_agent(proxy=None, name=None, max_retries=3):
    """Register a new agent with random name. Returns (ok, agent_data, full_response)."""
    for attempt in range(max_retries):
        agent_name = name or random_name()
        data = moltbook.register(agent_name, proxy=proxy)
        if data.get("success"):
            return True, data["agent"], data
        err = data.get("error", "")
        if "already" in err.lower() or "taken" in err.lower():
            log(f"  Name collision '{agent_name}', retrying...")
            name = None  # force new random name
            continue
        return False, None, data
    return False, None, {"error": "Max retries for name collision"}


def claim_agent(auth_token, proxy=None, agent_name=None):
    """
    Full claim flow for one account.
    Returns (ok, result_dict).
    """
    token_short = auth_token[:8] + "..."
    proxy_short = proxy.split("@")[1] if proxy and "@" in proxy else proxy or "direct"

    # Step 1: Register
    log(f"[1/6] Registering agent...")
    ok, agent, resp = register_agent(proxy=proxy, name=agent_name)
    if not ok:
        err = resp.get("error", "")
        log(f"  ❌ Register failed: {err} {resp.get('hint', '')}")
        return False, {"step": "register", "error": err}

    api_key = agent["api_key"]
    claim_url = agent["claim_url"]
    tweet_text = resp.get("tweet_template", "")
    claim_token = claim_url.split("/")[-1].split("?")[0]
    name = agent["name"]

    log(f"  ✅ {name} | {proxy_short}")

    # Save config
    cfg = {
        "auth_token": auth_token,
        "proxy": proxy,
        "api_key": api_key,
        "agent_name": name,
        "agent_id": agent["id"],
        "claim_url": claim_url,
        "verification_code": agent["verification_code"],
        "tweet_template": tweet_text,
        "registered_at": agent["created_at"],
    }
    cfg_file = config.save_account(auth_token, cfg)
    log(f"  Config: {cfg_file}")

    # Step 2: Twitter session
    log(f"[2/6] Twitter session ({token_short})...")
    session, ct0 = twitter.create_session(auth_token, proxy=proxy)
    if not ct0:
        log(f"  ❌ No ct0 — token invalid/expired")
        return False, {"step": "twitter_session", "error": "no ct0"}
    log(f"  ✅ ct0={ct0[:12]}...")

    # Step 3: Post tweet
    log(f"[3/6] Posting tweet...")
    ok, result = twitter.post_tweet(session, ct0, tweet_text)
    if not ok:
        log(f"  ❌ Tweet failed: {result}")
        return False, {"step": "tweet", "error": result}
    tweet_id = result
    log(f"  ✅ https://x.com/i/status/{tweet_id}")

    # Step 4: Wait for tweet indexing
    log(f"[4/6] Waiting {TWEET_INDEX_DELAY}s for tweet indexing...")
    time.sleep(TWEET_INDEX_DELAY)

    # Step 5: OAuth + verify (with retry)
    log(f"[5/6] OAuth + verify...")
    for attempt in range(VERIFY_MAX_RETRIES):
        if attempt > 0:
            log(f"  Retry {attempt}/{VERIFY_MAX_RETRIES} (waiting {VERIFY_RETRY_INTERVAL}s)...")
            time.sleep(VERIFY_RETRY_INTERVAL)

        # Need fresh OAuth each attempt (session tokens expire)
        oauth_url = twitter.get_moltbook_oauth_url(session, claim_url)
        if not oauth_url:
            log(f"  ❌ No OAuth URL")
            continue

        ok, callback_or_err = twitter.oauth2_authorize(session, ct0, oauth_url)
        if not ok:
            log(f"  ❌ OAuth failed: {callback_or_err}")
            continue

        # Follow callback
        try:
            session.get(callback_or_err, timeout=15, allow_redirects=True)
        except:
            pass

        # Verify tweet
        vdata = twitter.verify_tweet_with_session(session, claim_url, claim_token)
        if vdata.get("success"):
            owner = vdata.get("owner", {})
            log(f"  ✅ Claimed! Owner: {owner.get('x_handle', '?')}")
            return True, {
                "step": "done",
                "agent_name": name,
                "api_key": api_key,
                "owner": owner,
            }

        err = vdata.get("error", "")
        if "already claimed" in err.lower():
            if "agent" in err.lower():
                # "This agent has already been claimed" = success (claimed by us earlier)
                log(f"  ✅ Already claimed!")
                return True, {"step": "done", "agent_name": name, "api_key": api_key}
            else:
                # "This X account has already claimed an agent" = Twitter account used
                log(f"  ❌ Twitter account already bound to another agent")
                return False, {"step": "verify", "error": err}

        if "no recent tweets" in err.lower() or "couldn't find" in err.lower():
            log(f"  ⏳ Tweet not indexed yet...")
            continue

        log(f"  ❌ Verify: {err}")

    # Step 6: Final status check
    log(f"[6/6] Final status check...")
    for i in range(STATUS_MAX_CHECKS):
        time.sleep(STATUS_CHECK_INTERVAL)
        st = moltbook.status(api_key, proxy=proxy)
        if st.get("status") == "claimed":
            log(f"  ✅ Claimed (delayed confirmation)!")
            return True, {"step": "done", "agent_name": name, "api_key": api_key}

    log(f"  ❌ Failed after all retries")
    return False, {"step": "verify_timeout", "agent_name": name, "api_key": api_key}


def batch_claim(accounts, delay_between=5):
    """
    Batch claim for multiple accounts.
    accounts: list of (auth_token, proxy_url) tuples.
    Returns list of (auth_token, ok, result) tuples.
    """
    results = []
    total = len(accounts)

    log(f"=== Batch Claim: {total} accounts ===\n")

    for i, (auth_token, proxy) in enumerate(accounts):
        log(f"\n{'='*50}")
        log(f"Account {i+1}/{total}")
        log(f"{'='*50}")

        ok, result = claim_agent(auth_token, proxy=proxy)
        results.append((auth_token, ok, result))

        if i < total - 1:
            log(f"\n(next account in {delay_between}s...)")
            time.sleep(delay_between)

    # Summary
    log(f"\n{'='*50}")
    log(f"RESULTS: {sum(1 for _,ok,_ in results if ok)}/{total} claimed")
    log(f"{'='*50}")
    for token, ok, result in results:
        name = result.get("agent_name", "?")
        icon = "✅" if ok else "❌"
        err = result.get("error", "")
        log(f"  {icon} {name} ({token[:8]}...) {err}")

    return results
