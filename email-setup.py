#!/usr/bin/env python3
"""
Batch email setup for all Moltbook accounts.
Creates temp email → sends verification → confirms → OAuth → complete-setup.
"""

import json
import os
import re
import sys
import time
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs

import requests
from curl_cffi import requests as curl_requests

MOLTBOOK_API = "https://www.moltbook.com/api/v1"
EMAIL_BASE = "http://47.243.225.241:5000"
EMAIL_TOKEN = "478e9598dcdd4c4a96eeb553cf9a325c"
EMAIL_HEADERS = {"x-token": EMAIL_TOKEN}
ACCOUNTS_DIR = Path.home() / ".config" / "moltbook" / "accounts"
BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

CONCURRENCY = 5  # Lower concurrency for email setup (more steps)


def setup_one_account(cfg, idx, total):
    """Full email setup for one account. Returns (name, success, error)."""
    name = cfg.get("agent_name", "?")
    api_key = cfg.get("api_key", "")
    auth_token = cfg.get("auth_token", "")
    proxy = cfg.get("proxy", "")

    if not api_key or not auth_token:
        return (name, False, "missing api_key or auth_token")

    try:
        # 1. Create curl_cffi session with Twitter auth
        s = curl_requests.Session(impersonate="chrome", proxy=proxy)
        s.cookies.set("auth_token", auth_token, domain=".x.com")
        try:
            s.get("https://x.com/home", timeout=10, allow_redirects=True)
        except:
            pass
        ct0 = s.cookies.get("ct0", domain=".x.com")
        if not ct0:
            return (name, False, "no ct0 (twitter token invalid)")

        # 2. Create temp email
        r = requests.post(
            f"{EMAIL_BASE}/api/v1/mail/temp/new",
            headers=EMAIL_HEADERS, timeout=15
        )
        email = r.json().get("data", "")
        if not email:
            return (name, False, "failed to create temp email")

        # 3. Setup owner email via Moltbook API
        r = requests.post(
            f"{MOLTBOOK_API}/agents/me/setup-owner-email",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"email": email},
            proxies={"http": proxy, "https": proxy} if proxy else {},
            timeout=15,
        )
        resp = r.json()
        if not resp.get("success"):
            err = resp.get("error", "")
            if "already" in err.lower() or "verified" in err.lower():
                return (name, True, "already verified")
            return (name, False, f"setup-email: {err[:50]}")

        # 4. Wait for email
        for wait in range(4):
            time.sleep(5 if wait == 0 else 8)
            r = requests.post(
                f"{EMAIL_BASE}/api/v1/mail/temp/messages/{email}",
                headers=EMAIL_HEADERS, timeout=15
            )
            msgs = r.json().get("data", [])
            if msgs:
                break
        if not msgs:
            return (name, False, "no verification email received")

        # 5. Get email content and extract link
        msg_id = msgs[0]["_id"]
        r = requests.post(
            f"{EMAIL_BASE}/api/v1/mail/temp/messages/{email}/{msg_id}",
            headers=EMAIL_HEADERS, timeout=15
        )
        html = r.json().get("data", {}).get("bodyHtml", "")
        urls = re.findall(r'https://u\d+\.ct\.sendgrid\.net/ls/click\?[^\s<>"]+', html)
        if not urls:
            return (name, False, "no link in email")

        # 6. Follow SendGrid redirect
        r = requests.get(urls[0], allow_redirects=False, timeout=15)
        confirm_url = r.headers.get("Location", "")
        if "www" not in confirm_url and "moltbook.com" in confirm_url:
            r = requests.get(confirm_url, allow_redirects=False, timeout=15)
            confirm_url = r.headers.get("Location", confirm_url)

        # 7. Confirm email in curl_cffi session
        r = s.get(confirm_url, allow_redirects=True, timeout=15)

        # 8. Check setup state
        r = s.get(f"{MOLTBOOK_API}/auth/setup-state", timeout=10)
        state = r.json().get("state", {})
        phase = state.get("phase", "")
        if phase != "pending_x_oauth":
            if phase == "x_verified" or phase == "complete":
                pass  # Already done, just need complete-setup
            else:
                return (name, False, f"unexpected phase: {phase}")

        # 9. Twitter OAuth on Moltbook
        s.get("https://www.moltbook.com/api/auth/session", timeout=10)
        csrf_cookie = s.cookies.get("__Host-authjs.csrf-token")
        if not csrf_cookie:
            return (name, False, "no CSRF cookie")
        csrf_token = csrf_cookie.split("%7C")[0] if "%7C" in csrf_cookie else csrf_cookie.split("|")[0]

        r = s.post(
            "https://www.moltbook.com/api/auth/signin/twitter",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://www.moltbook.com",
                "X-Auth-Return-Redirect": "1",
            },
            data={"csrfToken": csrf_token, "callbackUrl": "/api/v1/auth/setup-callback"},
            allow_redirects=False, timeout=10,
        )

        oauth_url = None
        if r.status_code in (301, 302, 303, 307):
            loc = r.headers.get("Location", "")
            if "twitter.com" in loc or "x.com" in loc:
                oauth_url = loc
        if not oauth_url:
            try:
                oauth_url = r.json().get("url", "")
            except:
                pass
        if not oauth_url:
            return (name, False, "no OAuth URL")

        parsed = urlparse(oauth_url)
        params = parse_qs(parsed.query)
        api_params = {
            k: params[k][0]
            for k in ["client_id", "code_challenge", "code_challenge_method",
                       "redirect_uri", "response_type", "scope", "state"]
            if k in params
        }
        hdrs = {
            "Authorization": f"Bearer {BEARER}",
            "Content-Type": "application/json",
            "X-Csrf-Token": ct0,
            "X-Twitter-Auth-Type": "OAuth2Session",
            "Referer": oauth_url,
            "cookie": f"auth_token={auth_token}; ct0={ct0}",
        }

        r = s.get("https://twitter.com/i/api/2/oauth2/authorize",
                   params=api_params, headers=hdrs, timeout=15)
        auth_code = r.json().get("auth_code")
        if not auth_code:
            return (name, False, "no auth_code from Twitter")

        hdrs["origin"] = "https://twitter.com"
        cr = s.post("https://twitter.com/i/api/2/oauth2/authorize",
                     headers=hdrs, json={"approval": True, "code": auth_code},
                     timeout=15, allow_redirects=False)
        callback = cr.json().get("redirect_uri")
        if not callback:
            code = cr.json().get("code") or cr.json().get("auth_code")
            if code:
                callback = f"{api_params.get('redirect_uri', '')}?code={code}&state={api_params.get('state', '')}"
        if not callback:
            return (name, False, "no callback URL")

        try:
            s.get(callback, timeout=15, allow_redirects=True)
        except:
            pass

        # 10. Complete setup
        r = s.post(
            f"{MOLTBOOK_API}/auth/complete-setup",
            headers={"Content-Type": "application/json"},
            json={"username": f"{name}_owner"},
            timeout=10,
        )
        result = r.json()
        if result.get("success"):
            # Save email to config
            cfg["owner_email"] = email
            cfg["email_verified"] = True
            cfg_dir = cfg.get("_dir", "")
            if cfg_dir:
                with open(os.path.join(cfg_dir, "config.json"), "w") as f:
                    del cfg["_dir"]
                    json.dump(cfg, f, indent=2)
                    cfg["_dir"] = cfg_dir
            print(f"  ✅ [{idx+1}/{total}] {name} — email verified", flush=True)
            return (name, True, None)
        else:
            return (name, False, f"complete-setup: {result.get('error', '')[:50]}")

    except Exception as e:
        return (name, False, str(e)[:60])


def load_accounts():
    """Load all account configs that need email setup."""
    accounts = []
    for d in sorted(ACCOUNTS_DIR.iterdir()):
        cfg_file = d / "config.json"
        if not cfg_file.exists():
            continue
        with open(cfg_file) as f:
            cfg = json.load(f)
        cfg["_dir"] = str(d)
        # Skip already verified
        if cfg.get("email_verified"):
            continue
        # Skip accounts without api_key
        if not cfg.get("api_key"):
            continue
        accounts.append(cfg)
    return accounts


def main():
    concurrency = CONCURRENCY
    for i, a in enumerate(sys.argv):
        if a == "--concurrency" and i + 1 < len(sys.argv):
            concurrency = int(sys.argv[i + 1])

    accounts = load_accounts()
    print(f"[{time.strftime('%H:%M:%S')}] Email setup: {len(accounts)} accounts, {concurrency} workers", flush=True)

    ok = 0
    fail = 0
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = {
            ex.submit(setup_one_account, cfg, i, len(accounts)): cfg
            for i, cfg in enumerate(accounts)
        }
        for f in as_completed(futures):
            name, success, err = f.result()
            if success:
                ok += 1
            else:
                fail += 1
                print(f"  ❌ [{ok+fail}/{len(accounts)}] {name}: {err}", flush=True)

    print(f"\n[{time.strftime('%H:%M:%S')}] Done: ✅ {ok} | ❌ {fail} / {len(accounts)}", flush=True)


if __name__ == "__main__":
    main()
