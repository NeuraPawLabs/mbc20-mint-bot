#!/usr/bin/env python3
"""
Hourly job: claim unclaimed accounts + mint with claimed ones.
Usage: python3 hourly-job.py [--claim-only] [--mint-only] [--concurrency N]
"""

import json
import os
import sys
import time
import random
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs

import requests
from curl_cffi import requests as curl_requests

MOLTBOOK_API = "https://www.moltbook.com/api/v1"
ACCOUNTS_DIR = Path.home() / ".config" / "moltbook" / "accounts"

BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
CREATE_TWEET_URL = "https://x.com/i/api/graphql/F3SgNCEemikyFA5xnQOmTw/CreateTweet"
TWEET_FEATURES = {
    "premium_content_api_read_enabled":False,"communities_web_enable_tweet_community_results_fetch":True,
    "c9s_tweet_anatomy_moderator_badge_enabled":True,"responsive_web_grok_analyze_button_fetch_trends_enabled":False,
    "responsive_web_grok_analyze_post_followups_enabled":True,"responsive_web_jetfuel_frame":True,
    "responsive_web_grok_share_attachment_enabled":True,"responsive_web_grok_annotations_enabled":True,
    "responsive_web_edit_tweet_api_enabled":True,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":True,
    "view_counts_everywhere_api_enabled":True,"longform_notetweets_consumption_enabled":True,
    "responsive_web_twitter_article_tweet_consumption_enabled":True,"tweet_awards_web_tipping_enabled":False,
    "responsive_web_grok_show_grok_translated_post":False,"responsive_web_grok_analysis_button_from_backend":True,
    "post_ctas_fetch_enabled":True,"creator_subscriptions_quote_tweet_preview_enabled":False,
    "longform_notetweets_rich_text_read_enabled":True,"longform_notetweets_inline_media_enabled":True,
    "profile_label_improvements_pcf_label_in_post_enabled":True,"responsive_web_profile_redirect_enabled":False,
    "rweb_tipjar_consumption_enabled":False,"verified_phone_label_enabled":False,"articles_preview_enabled":True,
    "responsive_web_grok_community_note_auto_translation_is_enabled":False,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled":False,
    "freedom_of_speech_not_reach_fetch_enabled":True,"standardized_nudges_misinfo":True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":True,
    "responsive_web_grok_image_annotation_enabled":True,"responsive_web_grok_imagine_annotation_enabled":True,
    "responsive_web_graphql_timeline_navigation_enabled":True,"responsive_web_enhance_cards_enabled":False,
}

# ─── LLM Solver Config ───
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://cc-gateway.gtapp.xyz/api")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")

LLM_SYSTEM = """You are a math puzzle solver. You receive obfuscated text containing a math problem.
The text may have mixed case, extra letters, split words, or special characters.
Decode it, find the two numbers and operation, calculate the answer.
Reply with ONLY the numeric answer rounded to 2 decimal places (e.g. "42.00"). No explanation."""

def _solve_llm(challenge):
    if not LLM_API_KEY: return None
    try:
        r = requests.post(f"{LLM_BASE_URL}/v1/messages",
            headers={"Authorization":f"Bearer {LLM_API_KEY}","anthropic-version":"2023-06-01","content-type":"application/json"},
            json={"model":LLM_MODEL,"max_tokens":64,"system":LLM_SYSTEM,"messages":[{"role":"user","content":challenge}]},
            timeout=15)
        if r.status_code != 200: return None
        text = "".join(b["text"] for b in r.json().get("content",[]) if b.get("type")=="text").strip()
        m = re.search(r"-?\d+\.?\d*", text)
        return f"{float(m.group()):.2f}" if m else None
    except: return None

# Solver (inline regex fallback)
import re
WORD_NUMS = {
    "zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,
    "ten":10,"eleven":11,"twelve":12,"thirteen":13,"fourteen":14,"fifteen":15,"sixteen":16,
    "seventeen":17,"eighteen":18,"nineteen":19,"twenty":20,"thirty":30,"forty":40,"fifty":50,
    "sixty":60,"seventy":70,"eighty":80,"ninety":90,"hundred":100,"thousand":1000,
}
OP_KEYWORDS = {
    "mul":["product","multipl","times","double","triple"],
    "div":["divid","split","half","halv","quarter","ratio"],
    "sub":["decelerat","subtract","minus","decrease","slow","loses","lose","drop","reduc","shrink","falls","fell","lower","behind","less"],
    "add":["accelerat","add","plus","increase","gain","faster","more","grows","grow","climbs","climb","rises","rise","ahead","boost","extra","sum","total"],
}

def _clean(t):
    t = re.sub(r"[^a-zA-Z0-9 .]"," ",t)
    return re.sub(r"\s+"," ",t).lower().strip()

def _deobfuscate(t):
    a = re.sub(r"[^a-z]","",t.lower())
    r = []
    for c in a:
        if not r or r[-1]!=c: r.append(c)
    return "".join(r)

def _find_nums(blob):
    nums = []
    sw = sorted(WORD_NUMS.keys(),key=len,reverse=True)
    rem = blob
    while rem:
        found = False
        for w in sw:
            if rem.startswith(w):
                v = WORD_NUMS[w]
                if v < 100: nums.append(float(v))
                rem = rem[len(w):]; found = True; break
        if not found: rem = rem[1:]
    return nums

def _extract_std(text):
    nums = []; words = text.split(); i = 0
    while i < len(words):
        w = words[i].strip(".,?!")
        if re.match(r"^\d+\.?\d*$",w): nums.append(float(w)); i+=1
        elif w in WORD_NUMS:
            nw = []
            while i<len(words) and words[i].strip(".,?!") in WORD_NUMS:
                nw.append(words[i].strip(".,?!")); i+=1
            c = 0
            for ww in nw:
                v = WORD_NUMS[ww]
                if v>=100: c=(c or 1)*v
                else: c+=v
            nums.append(float(c))
        else: i+=1
    return nums

def _detect_op(t):
    for op in ["mul","div","sub","add"]:
        for kw in OP_KEYWORDS[op]:
            if kw in t: return op
    return "add"

def solve_challenge(challenge):
    # Try LLM first
    ans = _solve_llm(challenge)
    if ans:
        print(f"    🤖 LLM: {ans}", flush=True)
        return ans
    # Regex fallback
    cleaned = _clean(challenge)
    nums = _extract_std(cleaned)
    if len(nums)<2:
        blob = _deobfuscate(challenge)
        nums = _find_nums(blob)
    if len(nums)<2:
        nums = [float(n) for n in re.findall(r"\d+\.?\d*",challenge)]
    if len(nums)<2: return None
    blob = _deobfuscate(challenge)
    op = _detect_op(cleaned)
    if op=="add":
        op2 = _detect_op(blob)
        if op2!="add": op = op2
    a,b = nums[0],nums[1]
    r = {"add":a+b,"sub":a-b,"mul":a*b,"div":a/b if b else 0}.get(op,a+b)
    return f"{r:.2f}"


def _api_headers(ct0):
    return {"Authorization":f"Bearer {BEARER}","Content-Type":"application/json",
            "X-Csrf-Token":ct0,"X-Twitter-Auth-Type":"OAuth2Session",
            "X-Twitter-Active-User":"yes","Referer":"https://x.com/home","Origin":"https://x.com"}


def load_all_accounts():
    """Load all account configs."""
    accounts = []
    for d in sorted(ACCOUNTS_DIR.iterdir()):
        cfg_file = d / "config.json"
        if not cfg_file.exists(): continue
        with open(cfg_file) as f:
            cfg = json.load(f)
        cfg["_dir"] = str(d)
        accounts.append(cfg)
    return accounts


def check_status(cfg):
    """Check agent status. Returns (cfg, status_str)."""
    key = cfg.get("api_key","")
    if not key: return (cfg, "no_key")
    proxy = cfg.get("proxy","")
    proxies = {"http":proxy,"https":proxy} if proxy else {}
    try:
        r = requests.get(f"{MOLTBOOK_API}/agents/status",
            headers={"Authorization":f"Bearer {key}"},
            proxies=proxies, timeout=15)
        return (cfg, r.json().get("status","unknown"))
    except Exception as e:
        return (cfg, f"error:{str(e)[:30]}")


def try_claim(cfg):
    """Try to claim a pending account. Returns (name, success, error)."""
    name = cfg.get("agent_name","?")
    token = cfg.get("auth_token","")
    proxy = cfg.get("proxy","")
    claim_url = cfg.get("claim_url","")
    claim_token = claim_url.split("/")[-1].split("?")[0] if claim_url else ""
    tweet_text = cfg.get("tweet_template","")

    if not token or not claim_url or not tweet_text:
        return (name, False, "missing config")

    try:
        s = curl_requests.Session(impersonate="chrome", proxy=proxy)
        s.cookies.set("auth_token", token, domain=".x.com")
        try: s.get("https://x.com/home", timeout=15, allow_redirects=True)
        except: pass
        ct0 = s.cookies.get("ct0", domain=".x.com")
        if not ct0: return (name, False, "no ct0")

        # Tweet
        payload = {"variables":{"tweet_text":tweet_text,"dark_request":False,
            "media":{"media_entities":[],"possibly_sensitive":False},
            "semantic_annotation_ids":[],"disallowed_reply_options":None},
            "features":TWEET_FEATURES,"queryId":"F3SgNCEemikyFA5xnQOmTw"}
        resp = s.post(CREATE_TWEET_URL, headers=_api_headers(ct0), json=payload, timeout=30)
        tdata = resp.json()
        tid = (tdata.get("data",{}).get("create_tweet",{})
               .get("tweet_results",{}).get("result",{}).get("rest_id"))
        if not tid:
            errors = tdata.get("errors",[])
            msg = errors[0].get("message","") if errors else str(tdata)[:80]
            return (name, False, f"tweet: {msg[:60]}")

        time.sleep(30)

        # OAuth + verify
        for attempt in range(6):
            if attempt > 0: time.sleep(10)
            try:
                s.get("https://www.moltbook.com/api/auth/session",
                      headers={"Referer":claim_url}, timeout=10)
                csrf_cookie = s.cookies.get("__Host-authjs.csrf-token")
                if not csrf_cookie: continue
                csrf_token = csrf_cookie.split("%7C")[0] if "%7C" in csrf_cookie else csrf_cookie.split("|")[0]
                cb = claim_url.replace("https://moltbook.com","").replace("https://www.moltbook.com","")
                if "?" not in cb: cb += "?x_connected=true"

                resp = s.post("https://www.moltbook.com/api/auth/signin/twitter",
                    headers={"Content-Type":"application/x-www-form-urlencoded","Referer":claim_url,
                             "Origin":"https://www.moltbook.com","X-Auth-Return-Redirect":"1"},
                    data={"csrfToken":csrf_token,"callbackUrl":cb},
                    allow_redirects=False, timeout=10)

                oauth_url = None
                if resp.status_code in (301,302,303,307):
                    loc = resp.headers.get("Location","")
                    if "twitter.com" in loc or "x.com" in loc: oauth_url = loc
                if not oauth_url:
                    try: oauth_url = resp.json().get("url")
                    except: pass
                if not oauth_url: continue

                parsed = urlparse(oauth_url); params = parse_qs(parsed.query)
                api_params = {k:params[k][0] for k in ['client_id','code_challenge','code_challenge_method','redirect_uri','response_type','scope','state'] if k in params}
                headers = _api_headers(ct0)
                headers['cookie'] = f"auth_token={s.cookies.get('auth_token',domain='.x.com')}; ct0={s.cookies.get('ct0',domain='.x.com')}"
                headers['referer'] = oauth_url

                resp = s.get("https://twitter.com/i/api/2/oauth2/authorize",
                             params=api_params, headers=headers, timeout=15)
                if resp.status_code != 200: continue
                auth_code = resp.json().get('auth_code')
                if not auth_code: continue

                ph = headers.copy(); ph['content-type']='application/json'; ph['origin']='https://twitter.com'
                cr = s.post("https://twitter.com/i/api/2/oauth2/authorize", headers=ph,
                            json={"approval":True,"code":auth_code}, timeout=15, allow_redirects=False)
                callback = cr.json().get('redirect_uri')
                if not callback:
                    cdata = cr.json()
                    code = cdata.get('code') or cdata.get('auth_code')
                    if code:
                        callback = f"{api_params.get('redirect_uri','')}?code={code}&state={api_params.get('state','')}"
                if not callback: continue

                try: s.get(callback, timeout=15, allow_redirects=True)
                except: pass

                vr = s.post(f"{MOLTBOOK_API}/agents/verify-tweet",
                    headers={"Content-Type":"application/json","Referer":claim_url,"Origin":"https://www.moltbook.com"},
                    json={"token":claim_token}, timeout=15)
                vdata = vr.json()
                if vdata.get("success"):
                    return (name, True, None)
                err = vdata.get("error","")
                if "already been claimed" in err.lower():
                    return (name, True, None)
                if "already claimed" in err.lower():
                    return (name, False, "twitter already bound")
            except: continue

        return (name, False, "verify timeout")
    except Exception as e:
        return (name, False, str(e)[:60])


def try_mint(cfg, tick="CLAW", amt="100"):
    """Try to mint with a claimed account. Returns (name, success, error)."""
    import json as _json
    name = cfg.get("agent_name","?")
    key = cfg.get("api_key","")
    proxy = cfg.get("proxy","")
    proxies = {"http":proxy,"https":proxy} if proxy else {}
    flair = f"t{int(time.time())}-{random.randint(100,999)}"

    try:
        inscription = _json.dumps({"p":"mbc-20","op":"mint","tick":tick,"amt":amt})
        r = requests.post(f"{MOLTBOOK_API}/posts",
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json={"submolt":"general","title":f"Minting {tick} | {flair}",
                  "content":f"{inscription}\n\nmbc20.xyz"},
            proxies=proxies, timeout=30)
        data = r.json()
        if not data.get("success"):
            err = data.get("error","")
            hint = data.get("hint","")
            return (name, False, f"{err[:40]} {hint[:30]}")

        v = data.get("verification",{})
        code = v.get("verification_code") or v.get("code")
        challenge = v.get("challenge","")
        if not code:
            return (name, True, None)

        answer = solve_challenge(challenge)
        if not answer:
            return (name, False, f"solver failed: {challenge[:50]}")

        vr = requests.post(f"{MOLTBOOK_API}/verify",
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json={"verification_code":code,"answer":answer},
            proxies=proxies, timeout=15)
        vdata = vr.json()
        if vdata.get("success"):
            return (name, True, None)
        return (name, False, f"wrong answer: {answer} for {challenge[:40]}")
    except Exception as e:
        return (name, False, str(e)[:60])


def main():
    claim_only = "--claim-only" in sys.argv
    mint_only = "--mint-only" in sys.argv
    concurrency = 15
    for i, a in enumerate(sys.argv):
        if a == "--concurrency" and i+1 < len(sys.argv):
            concurrency = int(sys.argv[i+1])

    print(f"[{time.strftime('%H:%M:%S')}] Loading accounts...", flush=True)
    accounts = load_all_accounts()
    print(f"  Total: {len(accounts)}", flush=True)

    # Phase 1: Check status (concurrent)
    print(f"\n[{time.strftime('%H:%M:%S')}] Checking status ({concurrency} workers)...", flush=True)
    claimed = []
    pending = []
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        for cfg, status in ex.map(check_status, accounts):
            if status == "claimed":
                claimed.append(cfg)
            elif status == "pending_claim":
                pending.append(cfg)
            # skip errors/unknown

    print(f"  Claimed: {len(claimed)} | Pending: {len(pending)}", flush=True)

    # Phase 2: Claim pending accounts
    if pending and not mint_only:
        print(f"\n[{time.strftime('%H:%M:%S')}] Claiming {len(pending)} pending accounts...", flush=True)
        claim_ok = 0
        claim_fail = 0
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = {ex.submit(try_claim, cfg): cfg for cfg in pending}
            for f in as_completed(futures):
                name, ok, err = f.result()
                if ok:
                    claim_ok += 1
                    claimed.append(futures[f])
                    print(f"  ✅ {name} claimed", flush=True)
                else:
                    claim_fail += 1
                    print(f"  ❌ {name}: {err}", flush=True)
        print(f"  Claim results: ✅ {claim_ok} | ❌ {claim_fail}", flush=True)

    # Phase 3: Mint with claimed accounts
    if claimed and not claim_only:
        print(f"\n[{time.strftime('%H:%M:%S')}] Minting with {len(claimed)} claimed accounts...", flush=True)
        mint_ok = 0
        mint_fail = 0
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = {ex.submit(try_mint, cfg): cfg for cfg in claimed}
            for f in as_completed(futures):
                name, ok, err = f.result()
                if ok:
                    mint_ok += 1
                    print(f"  ✅ {name} minted 100 CLAW", flush=True)
                else:
                    mint_fail += 1
                    if "2 hours" not in str(err) and "cooldown" not in str(err).lower():
                        print(f"  ❌ {name}: {err}", flush=True)
                    # Suppress cooldown errors (expected)
        print(f"  Mint results: ✅ {mint_ok} | ❌ {mint_fail}", flush=True)

    # Summary
    print(f"\n[{time.strftime('%H:%M:%S')}] === SUMMARY ===", flush=True)
    print(f"  Total accounts: {len(accounts)}", flush=True)
    print(f"  Claimed: {len(claimed)}", flush=True)
    print(f"  Still pending: {len(pending) - (len(claimed) - len([c for c in claimed if c not in pending]))}", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
