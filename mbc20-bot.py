#!/usr/bin/env python3
"""
MBC-20 Complete Mint Bot
Full automation: register → tweet → OAuth claim → auto-mint

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
from urllib.parse import urlparse, parse_qs, urlencode
from curl_cffi import requests as curl_requests

BASE_URL = "https://www.moltbook.com/api/v1"
CONFIG_DIR = Path.home() / ".config" / "moltbook"
CONFIG_FILE = CONFIG_DIR / "credentials.json"

TWITTER_BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
TWITTER_CREATE_TWEET_URL = "https://x.com/i/api/graphql/F3SgNCEemikyFA5xnQOmTw/CreateTweet"

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

def get_headers(api_key):
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

def api_post(path, data, api_key=None):
    headers = get_headers(api_key) if api_key else {"Content-Type": "application/json"}
    try:
        return requests.post(f"{BASE_URL}/{path}", headers=headers, json=data, timeout=30).json()
    except Exception as e:
        return {"success": False, "error": str(e)}

def api_get(path, api_key):
    try:
        return requests.get(f"{BASE_URL}/{path}", headers=get_headers(api_key), timeout=30).json()
    except Exception as e:
        return {"success": False, "error": str(e)}

# ─── Twitter ───

def twitter_session(auth_token):
    """Create a Twitter session with auth_token and get ct0."""
    s = curl_requests.Session(impersonate="chrome")
    s.cookies.set("auth_token", auth_token, domain=".x.com")
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    # Get ct0
    try:
        s.get("https://x.com/home", timeout=15, allow_redirects=True)
    except:
        pass
    ct0 = s.cookies.get("ct0", domain=".x.com")
    return s, ct0

def post_tweet(session, ct0, text):
    """Post a tweet."""
    headers = {
        "Authorization": f"Bearer {TWITTER_BEARER}",
        "Content-Type": "application/json",
        "X-Csrf-Token": ct0,
        "X-Twitter-Auth-Type": "OAuth2Session",
        "X-Twitter-Active-User": "yes",
        "X-Twitter-Client-Language": "en",
        "Referer": "https://x.com/home",
        "Origin": "https://x.com",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    payload = {
        "variables": {
            "tweet_text": text,
            "dark_request": False,
            "media": {"media_entities": [], "possibly_sensitive": False},
            "semantic_annotation_ids": [],
            "disallowed_reply_options": None,
        },
        "features": {
            "premium_content_api_read_enabled": False,
            "communities_web_enable_tweet_community_results_fetch": True,
            "c9s_tweet_anatomy_moderator_badge_enabled": True,
            "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
            "responsive_web_grok_analyze_post_followups_enabled": True,
            "responsive_web_jetfuel_frame": True,
            "responsive_web_grok_share_attachment_enabled": True,
            "responsive_web_grok_annotations_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": True,
            "tweet_awards_web_tipping_enabled": False,
            "responsive_web_grok_show_grok_translated_post": False,
            "responsive_web_grok_analysis_button_from_backend": True,
            "post_ctas_fetch_enabled": True,
            "creator_subscriptions_quote_tweet_preview_enabled": False,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "profile_label_improvements_pcf_label_in_post_enabled": True,
            "responsive_web_profile_redirect_enabled": False,
            "rweb_tipjar_consumption_enabled": False,
            "verified_phone_label_enabled": False,
            "articles_preview_enabled": True,
            "responsive_web_grok_community_note_auto_translation_is_enabled": False,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "responsive_web_grok_image_annotation_enabled": True,
            "responsive_web_grok_imagine_annotation_enabled": True,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_enhance_cards_enabled": False,
        },
        "queryId": "F3SgNCEemikyFA5xnQOmTw",
    }
    try:
        resp = session.post(TWITTER_CREATE_TWEET_URL, headers=headers, json=payload, timeout=30)
        data = resp.json()
        tweet_id = data.get("data", {}).get("create_tweet", {}).get("tweet_results", {}).get("result", {}).get("rest_id")
        if tweet_id:
            return True, tweet_id
        errors = data.get("errors", [])
        if errors:
            return False, errors[0].get("message", str(errors))
        return False, f"Unexpected: {json.dumps(data)[:200]}"
    except Exception as e:
        return False, str(e)

def twitter_oauth_authorize(session, ct0, oauth_url):
    """
    Automate Twitter OAuth authorization.
    1. GET the OAuth authorize page
    2. Extract authenticity_token and oauth_token
    3. POST to authorize (approve the app)
    4. Return the callback URL with oauth_verifier
    """
    log("  Fetching OAuth authorize page...")
    
    try:
        resp = session.get(oauth_url, timeout=15, allow_redirects=True)
    except Exception as e:
        return False, f"Failed to load OAuth page: {e}"
    
    # Check if we got redirected to login
    if "/login" in resp.url or "oauth" not in resp.url:
        return False, f"Redirected to login. auth_token may be invalid. URL: {resp.url}"
    
    html = resp.text
    
    # Extract authenticity_token
    auth_match = re.search(r'name="authenticity_token"\s+value="([^"]+)"', html)
    if not auth_match:
        # Maybe already authorized, check for callback redirect
        if "oauth_verifier" in resp.url:
            return True, resp.url
        return False, "Could not find authenticity_token in OAuth page"
    
    authenticity_token = auth_match.group(1)
    
    # Extract oauth_token
    oauth_match = re.search(r'name="oauth_token"\s+value="([^"]+)"', html)
    if not oauth_match:
        oauth_match = re.search(r'oauth_token=([^&"]+)', resp.url)
    
    if not oauth_match:
        return False, "Could not find oauth_token"
    
    oauth_token = oauth_match.group(1)
    
    log("  Authorizing app...")
    
    # POST to authorize
    authorize_data = {
        "authenticity_token": authenticity_token,
        "redirect_after_login": resp.url,
        "oauth_token": oauth_token,
    }
    
    try:
        auth_resp = session.post(
            "https://api.x.com/oauth/authorize",
            data=authorize_data,
            timeout=15,
            allow_redirects=False,
        )
    except Exception as e:
        return False, f"OAuth authorize POST failed: {e}"
    
    # Should get a redirect to the callback URL
    if auth_resp.status_code in (301, 302, 303, 307):
        callback_url = auth_resp.headers.get("Location", "")
        if "oauth_verifier" in callback_url or "moltbook" in callback_url:
            return True, callback_url
        return False, f"Unexpected redirect: {callback_url}"
    
    # Check response body for redirect
    redirect_match = re.search(r'href="([^"]*oauth_verifier[^"]*)"', auth_resp.text)
    if redirect_match:
        return True, redirect_match.group(1)
    
    # Maybe the response itself contains the callback
    if "oauth_verifier" in auth_resp.text:
        url_match = re.search(r'(https?://[^\s"<>]*oauth_verifier=[^\s"<>]*)', auth_resp.text)
        if url_match:
            return True, url_match.group(1)
    
    return False, f"OAuth authorize returned {auth_resp.status_code}, no redirect found"

# ─── Challenge Solver ───

def clean_challenge(text):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-zA-Z0-9 .,?]', ' ', text)).lower().strip()

def words_to_number(words):
    current = 0
    for w in words:
        if w not in WORD_NUMS: break
        val = WORD_NUMS[w]
        current = ((current or 1) * val) if val >= 100 else (current + val)
    return current

def extract_numbers(text):
    numbers, words, i = [], text.split(), 0
    while i < len(words):
        w = words[i].strip('.,?!')
        if re.match(r'^\d+\.?\d*$', w):
            numbers.append(float(w)); i += 1
        elif w in WORD_NUMS:
            nw = []
            while i < len(words) and words[i].strip('.,?!') in WORD_NUMS:
                nw.append(words[i].strip('.,?!')); i += 1
            numbers.append(words_to_number(nw))
        else:
            i += 1
    return numbers

def detect_op(text):
    for op, kw in {
        'add': ['accelerat','add','plus','increase','gain','faster','more','grows','grow','climbs','rises'],
        'sub': ['decelerat','subtract','minus','decrease','slow','less','lose','loses','drop','reduc','shrink','falls'],
        'mul': ['multipl','times','double','triple'],
        'div': ['divid','split','half','halv'],
    }.items():
        if any(k in text for k in kw): return op
    return 'add'

def solve_challenge(challenge):
    cleaned = clean_challenge(challenge)
    numbers = extract_numbers(cleaned)
    if len(numbers) < 2:
        numbers = [float(n) for n in re.findall(r'\d+\.?\d*', challenge)]
    if len(numbers) < 2: return None
    op = detect_op(cleaned)
    a, b = numbers[0], numbers[1]
    r = {'add': a+b, 'sub': a-b, 'mul': a*b, 'div': a/b if b else 0}.get(op, a+b)
    return f"{r:.2f}"

# ─── Commands ───

def cmd_tweet(args):
    """Step 1: Post verification tweet only."""
    config = load_config()
    if not config:
        log("❌ No config. Run 'register' first."); return

    auth_token = args.auth_token
    tweet_text = config.get("tweet_template", "")

    if not tweet_text:
        log("❌ No tweet template in config. Re-run 'register'."); return

    # Create Twitter session
    log("Setting up Twitter session...")
    session, ct0 = twitter_session(auth_token)
    if not ct0:
        log("❌ Failed to get Twitter CSRF token. Check auth_token."); return
    log("  ✅ Twitter session ready")

    # Post verification tweet
    log("Posting verification tweet...")
    ok, result = post_tweet(session, ct0, tweet_text)
    if not ok:
        log(f"❌ Tweet failed: {result}"); return

    log(f"  ✅ Tweet posted: https://x.com/i/status/{result}")
    log("")
    log("Next step: Run OAuth verification")
    log(f"  python3 {sys.argv[0]} verify --auth-token YOUR_TOKEN")

def get_oauth_url_from_moltbook(session, claim_url):
    """
    Get OAuth URL from Moltbook using NextAuth flow.
    1. Get CSRF token from /api/auth/session
    2. Use CSRF token to call /api/auth/signin/twitter
    """
    try:
        # Step 1: Get CSRF token
        log("  Getting CSRF token...")
        session_resp = session.get(
            "https://www.moltbook.com/api/auth/session",
            headers={
                "Referer": claim_url,
                "Accept": "*/*",
            },
            timeout=10
        )

        # Extract CSRF token from cookies
        csrf_token = None

        # Try to get cookie directly
        csrf_cookie = session.cookies.get("__Host-authjs.csrf-token")
        if csrf_cookie:
            # Format: token%7Chash or token|hash
            csrf_token = csrf_cookie.split("%7C")[0] if "%7C" in csrf_cookie else csrf_cookie.split("|")[0]

        # If not found, try parsing from Set-Cookie header
        if not csrf_token and "Set-Cookie" in session_resp.headers:
            set_cookie = session_resp.headers.get("Set-Cookie", "")
            if "__Host-authjs.csrf-token=" in set_cookie:
                # Extract: __Host-authjs.csrf-token=TOKEN%7CHASH; ...
                cookie_part = set_cookie.split("__Host-authjs.csrf-token=")[1].split(";")[0]
                csrf_token = cookie_part.split("%7C")[0] if "%7C" in cookie_part else cookie_part.split("|")[0]

        if not csrf_token:
            log("  ❌ Could not get CSRF token")
            return None

        log("  ✅ Got CSRF token")

        # Step 2: Call signin endpoint with CSRF token
        log("  Requesting OAuth URL...")

        # Prepare callback URL
        callback_url = claim_url.replace("https://www.moltbook.com", "")
        if "?" not in callback_url:
            callback_url += "?x_connected=true"

        signin_resp = session.post(
            "https://www.moltbook.com/api/auth/signin/twitter",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": claim_url,
                "Origin": "https://www.moltbook.com",
                "X-Auth-Return-Redirect": "1",
                "Accept": "*/*",
            },
            data={
                "csrfToken": csrf_token,
                "callbackUrl": callback_url,
            },
            allow_redirects=False,
            timeout=10
        )

        # Check for redirect to Twitter OAuth
        if signin_resp.status_code in (301, 302, 303, 307):
            location = signin_resp.headers.get("Location", "")
            if "twitter.com" in location or "x.com" in location:
                log("  ✅ Got OAuth URL")
                return location

        # Try to parse JSON response
        try:
            data = signin_resp.json()
            if "url" in data:
                oauth_url = data["url"]
                if "twitter.com" in oauth_url or "x.com" in oauth_url:
                    log("  ✅ Got OAuth URL from JSON")
                    return oauth_url
        except:
            pass

        log(f"  ❌ Unexpected response: {signin_resp.status_code}")
        return None

    except Exception as e:
        log(f"  ❌ Error: {e}")
        return None

def twitter_oauth2_authorize(session, oauth_url):
    """
    Automate Twitter OAuth 2.0 authorization.
    1. Visit the OAuth URL (user should already be logged in via auth_token)
    2. Click authorize button
    3. Follow redirect back to Moltbook
    """
    log("  Visiting OAuth page...")

    try:
        # Visit OAuth page
        resp = session.get(oauth_url, timeout=15, allow_redirects=True)

        # Check if we're on the authorization page
        if "oauth2/authorize" not in resp.url:
            # Maybe already authorized or redirected
            if "moltbook.com" in resp.url:
                log("  Already authorized, redirected to Moltbook")
                return True, resp.url
            return False, f"Unexpected redirect: {resp.url}"

        html = resp.text

        # Look for the authorize form
        # OAuth 2.0 uses a form with authenticity_token
        auth_match = re.search(r'name="authenticity_token"\s+value="([^"]+)"', html)
        if not auth_match:
            # Maybe already authorized
            if "moltbook.com" in resp.url:
                return True, resp.url
            return False, "Could not find authenticity_token"

        authenticity_token = auth_match.group(1)

        log("  Authorizing app...")

        # Submit authorization form
        auth_data = {
            "authenticity_token": authenticity_token,
            "approval": "true",
        }

        auth_resp = session.post(
            resp.url,
            data=auth_data,
            timeout=15,
            allow_redirects=True,
        )

        # Should be redirected back to Moltbook
        if "moltbook.com" in auth_resp.url:
            log("  ✅ Authorization successful")
            return True, auth_resp.url

        return False, f"Authorization failed, ended at: {auth_resp.url}"

    except Exception as e:
        return False, f"OAuth error: {e}"

def cmd_verify(args):
    """Step 2: Complete OAuth verification (assumes tweet already posted)."""
    config = load_config()
    if not config:
        log("❌ No config. Run 'register' first."); return

    auth_token = args.auth_token
    api_key = config["api_key"]
    claim_url = config.get("claim_url", "")

    # Check if already claimed
    if api_get("agents/status", api_key).get("status") == "claimed":
        log("✅ Already claimed!"); return

    # Create Twitter session with curl_cffi
    log("Setting up Twitter session...")
    session, ct0 = twitter_session(auth_token)
    if not ct0:
        log("❌ Failed to get Twitter CSRF token. Check auth_token."); return
    log("  ✅ Twitter session ready")

    # Get OAuth URL from Moltbook
    log("Getting OAuth URL from Moltbook...")
    oauth_url = get_oauth_url_from_moltbook(session, claim_url)

    if not oauth_url:
        log("❌ Could not get OAuth URL")
        log("   Falling back to manual mode...")
        log(f"   Open: {claim_url}")
        log("   Complete the OAuth flow in your browser")
        log("")
        log("⏳ Waiting for verification...")

        for i in range(120):
            time.sleep(10)
            status = api_get("agents/status", api_key).get("status")
            if status == "claimed":
                log("✅ Agent claimed successfully!")
                log(f"   Start minting: python3 {sys.argv[0]} mint --loop")
                return
            if i % 6 == 0 and i > 0:
                log(f"  Still waiting... ({(i*10)//60} min)")

        log("⏳ Timeout")
        return

    # Authorize via OAuth 2.0
    log("Authorizing via Twitter OAuth 2.0...")
    ok, result = twitter_oauth2_authorize(session, oauth_url)

    if not ok:
        log(f"❌ OAuth failed: {result}")
        return

    # Check status
    log("Verifying claim...")
    time.sleep(3)
    for i in range(10):
        status = api_get("agents/status", api_key).get("status")
        if status == "claimed":
            log("✅ Agent claimed successfully!")
            log(f"   Start minting: python3 {sys.argv[0]} mint --loop")
            return
        time.sleep(3)

    log("⏳ Claim pending. Check status:")
    log(f"   python3 {sys.argv[0]} status")

def cmd_register(args):
    name, desc = args.name, args.desc or f"AI agent {name}"
    log(f"Registering agent: {name}")
    data = api_post("agents/register", {"name": name, "description": desc})
    if not data.get("success"):
        log(f"❌ Failed: {data.get('error','')} {data.get('hint','')}")
        return
    agent = data["agent"]
    config = {
        "api_key": agent["api_key"], "agent_name": agent["name"],
        "agent_id": agent["id"], "claim_url": agent["claim_url"],
        "verification_code": agent["verification_code"],
        "profile_url": agent["profile_url"],
        "tweet_template": data.get("tweet_template", ""),
        "registered_at": agent["created_at"],
    }
    save_config(config)
    print(f"\n{'='*60}")
    print(f"✅ Agent registered: {agent['name']}")
    print(f"{'='*60}")
    print(f"API Key: {agent['api_key']}")
    print(f"\n📋 Next: python3 {sys.argv[0]} claim --auth-token YOUR_TOKEN")
    print(f"{'='*60}")

def cmd_claim(args):
    config = load_config()
    if not config:
        log("❌ No config. Run 'register' first."); return
    
    auth_token = args.auth_token
    api_key = config["api_key"]
    tweet_text = config.get("tweet_template", "")
    claim_url = config.get("claim_url", "")
    
    # Check if already claimed
    if api_get("agents/status", api_key).get("status") == "claimed":
        log("✅ Already claimed!"); return
    
    # Step 1: Create Twitter session
    log("Setting up Twitter session...")
    session, ct0 = twitter_session(auth_token)
    if not ct0:
        log("❌ Failed to get Twitter CSRF token. Check auth_token."); return
    log("  ✅ Twitter session ready")
    
    # Step 2: Post verification tweet
    log("Posting verification tweet...")
    ok, result = post_tweet(session, ct0, tweet_text)
    if not ok:
        log(f"❌ Tweet failed: {result}"); return
    log(f"  ✅ Tweet posted: https://x.com/i/status/{result}")
    
    # Step 3: Get OAuth URL from Moltbook claim page
    log("Getting OAuth URL from claim page...")
    
    # The claim page's "Connect with X" button triggers an OAuth flow
    # We need to find the OAuth initiation URL
    # It's typically: /api/auth/twitter or similar
    
    # Try common Moltbook OAuth endpoints
    oauth_init_urls = [
        f"https://www.moltbook.com/api/auth/twitter?claim_token={claim_url.split('/')[-1]}",
        f"https://www.moltbook.com/api/v1/auth/twitter/claim?token={claim_url.split('/')[-1]}",
        f"https://www.moltbook.com/api/auth/callback/twitter",
    ]
    
    # First, try to get the OAuth URL by visiting the claim page
    try:
        claim_resp = session.get(claim_url, timeout=15)
        # Look for OAuth URL in the page source
        oauth_match = re.search(r'(https://api\.(?:twitter|x)\.com/oauth/authorize\?oauth_token=[^"\'&\s]+)', claim_resp.text)
        if oauth_match:
            oauth_url = oauth_match.group(1)
            log(f"  Found OAuth URL in page")
        else:
            # Try the Next.js API route pattern
            # The "Connect with X" button likely calls a Next.js API route
            claim_token = claim_url.split("/")[-1]
            
            # Try fetching the OAuth init endpoint
            oauth_url = None
            for init_url in [
                f"https://www.moltbook.com/api/auth/twitter?claim={claim_token}",
                f"https://www.moltbook.com/api/auth/twitter/authorize?claim={claim_token}",
                f"https://www.moltbook.com/api/v1/claim/{claim_token}/auth",
            ]:
                try:
                    r = requests.get(init_url, timeout=10, allow_redirects=False)
                    if r.status_code in (301, 302, 303, 307):
                        loc = r.headers.get("Location", "")
                        if "oauth" in loc or "twitter" in loc or "x.com" in loc:
                            oauth_url = loc
                            log(f"  Found OAuth redirect: {init_url}")
                            break
                    elif r.status_code == 200:
                        data = r.json() if 'json' in r.headers.get('content-type','') else {}
                        if 'url' in data:
                            oauth_url = data['url']
                            break
                except:
                    continue
            
            if not oauth_url:
                log("❌ Could not find OAuth URL automatically.")
                log("   The claim page uses client-side JavaScript to initiate OAuth.")
                log("   You need to open the claim URL in a browser and click 'Connect with X':")
                log(f"   {claim_url}")
                log("   (Tweet is already posted, just need to click Connect with X)")
                return
    except Exception as e:
        log(f"❌ Failed to access claim page: {e}"); return
    
    # Step 4: Authorize via OAuth
    log("Authorizing via Twitter OAuth...")
    ok, callback = twitter_oauth_authorize(session, ct0, oauth_url)
    if not ok:
        log(f"❌ OAuth failed: {callback}")
        log(f"   Open manually: {claim_url}")
        return
    
    # Step 5: Follow callback to Moltbook
    log("Completing claim...")
    try:
        final_resp = session.get(callback, timeout=15, allow_redirects=True)
        log(f"  Callback status: {final_resp.status_code}")
    except Exception as e:
        log(f"  Callback request: {e}")
    
    # Step 6: Verify claim
    time.sleep(3)
    for i in range(10):
        status = api_get("agents/status", api_key).get("status")
        if status == "claimed":
            log("✅ Agent claimed successfully!")
            log(f"   Start minting: python3 {sys.argv[0]} mint --loop")
            return
        time.sleep(3)
    
    log("⏳ Claim not confirmed yet. Tweet is posted, OAuth attempted.")
    log(f"   Try opening manually: {claim_url}")

def cmd_status(args):
    config = load_config()
    if not config:
        log("❌ No config. Run 'register' first."); return
    data = api_get("agents/status", config["api_key"])
    status = data.get("status", "unknown")
    if status == "claimed":
        print(f"✅ Agent '{config['agent_name']}' is active! Run: python3 {sys.argv[0]} mint --loop")
    elif status == "pending_claim":
        print(f"⏳ Pending. Claim: python3 {sys.argv[0]} claim --auth-token TOKEN")
    else:
        print(f"❓ {status} {data.get('error','')} {data.get('hint','')}")

def cmd_mint(args):
    config = load_config()
    if not config:
        log("❌ No config. Run 'register' first."); return
    api_key, tick, amt, interval = config["api_key"], args.tick, args.amt, args.interval
    if args.loop:
        log(f"🔄 Loop: {amt} {tick} every {interval}s")
        count, fails = 0, 0
        while True:
            if do_mint(api_key, tick, amt):
                count += 1; fails = 0
                log(f"📊 Total: {count} | Next in {interval}s...")
            else:
                fails += 1
                wait = min(interval, 300 * fails)
                log(f"⏳ Fail #{fails}, retry in {wait}s...")
                time.sleep(wait); continue
            time.sleep(interval)
    else:
        do_mint(api_key, tick, amt)

def do_mint(api_key, tick, amt):
    log(f"⛏️  Minting {amt} {tick}...")
    flair = f"t{int(time.time())}-{random.randint(100,999)}"
    inscription = json.dumps({"p": "mbc-20", "op": "mint", "tick": tick, "amt": amt})
    data = api_post("posts", {
        "submolt": "general",
        "title": f"Minting {tick} | {flair}",
        "content": f"{inscription}\n\nmbc20.xyz\n\n{flair}"
    }, api_key)
    if not data.get("success"):
        log(f"  ❌ {data.get('error','')} {data.get('hint','')}"); return False
    post_id = data.get("post", {}).get("id", "?")
    v = data.get("verification", {})
    code, challenge = v.get("code"), v.get("challenge")
    if not code: log(f"  ✅ Minted (no verify): {post_id}"); return True
    answer = solve_challenge(challenge)
    if not answer: log("  ❌ Can't solve challenge"); return False
    log(f"  💡 {answer}")
    vd = api_post("verify", {"verification_code": code, "answer": answer}, api_key)
    if vd.get("success"): log(f"  ✅ Minted {amt} {tick}!"); return True
    log(f"  ❌ Verify failed: {vd.get('error','')}"); return False

# ─── Main ───

def main():
    p = argparse.ArgumentParser(description="MBC-20 Mint Bot")
    sub = p.add_subparsers(dest="cmd")
    
    r = sub.add_parser("register", help="Register agent")
    r.add_argument("--name", required=True)
    r.add_argument("--desc", default=None)

    t = sub.add_parser("tweet", help="Step 1: Post verification tweet")
    t.add_argument("--auth-token", required=True, help="Twitter auth_token cookie")

    v = sub.add_parser("verify", help="Step 2: Complete OAuth verification")
    v.add_argument("--auth-token", required=True, help="Twitter auth_token cookie")

    c = sub.add_parser("claim", help="Complete flow: tweet + OAuth (all-in-one)")
    c.add_argument("--auth-token", required=True, help="Twitter auth_token cookie")

    sub.add_parser("status", help="Check status")

    m = sub.add_parser("mint", help="Mint tokens")
    m.add_argument("--tick", default="CLAW")
    m.add_argument("--amt", default="1000")
    m.add_argument("--loop", action="store_true")
    m.add_argument("--interval", type=int, default=7200)

    args = p.parse_args()
    {"register": cmd_register, "tweet": cmd_tweet, "verify": cmd_verify, "claim": cmd_claim, "status": cmd_status, "mint": cmd_mint}.get(args.cmd, lambda _: p.print_help())(args)

if __name__ == "__main__":
    main()
