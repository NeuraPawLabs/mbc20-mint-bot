"""Twitter API client using curl_cffi."""

import re
import time
from urllib.parse import urlparse, parse_qs

from curl_cffi import requests as curl_requests

from .logger import log

BEARER = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
CREATE_TWEET_URL = "https://x.com/i/api/graphql/F3SgNCEemikyFA5xnQOmTw/CreateTweet"
CREATE_TWEET_QUERY_ID = "F3SgNCEemikyFA5xnQOmTw"

TWEET_FEATURES = {
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
}


def _api_headers(ct0):
    """Common headers for Twitter API calls."""
    return {
        "Authorization": f"Bearer {BEARER}",
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
        "Sec-Ch-Ua": '"Not(A:Brand";v="8", "Chromium";v="144", "Google Chrome";v="144"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Linux"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }


def create_session(auth_token, proxy=None):
    """Create a Twitter session and return (session, ct0)."""
    kwargs = {"impersonate": "chrome"}
    if proxy:
        kwargs["proxies"] = {"http": proxy, "https": proxy}
    s = curl_requests.Session(**kwargs)
    s.cookies.set("auth_token", auth_token, domain=".x.com")
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    try:
        s.get("https://x.com/home", timeout=15, allow_redirects=True)
    except:
        pass
    ct0 = s.cookies.get("ct0", domain=".x.com")
    return s, ct0


def post_tweet(session, ct0, text):
    """Post a tweet. Returns (ok, tweet_id_or_error)."""
    payload = {
        "variables": {
            "tweet_text": text,
            "dark_request": False,
            "media": {"media_entities": [], "possibly_sensitive": False},
            "semantic_annotation_ids": [],
            "disallowed_reply_options": None,
        },
        "features": TWEET_FEATURES,
        "queryId": CREATE_TWEET_QUERY_ID,
    }
    try:
        resp = session.post(CREATE_TWEET_URL, headers=_api_headers(ct0), json=payload, timeout=30)
        data = resp.json()
        tweet_id = (data.get("data", {}).get("create_tweet", {})
                    .get("tweet_results", {}).get("result", {}).get("rest_id"))
        if tweet_id:
            return True, tweet_id
        errors = data.get("errors", [])
        if errors:
            return False, errors[0].get("message", str(errors))
        return False, f"Unexpected: {str(data)[:200]}"
    except Exception as e:
        return False, str(e)


def oauth_authorize(session, ct0, oauth_url):
    """
    Automate Twitter OAuth 1.0a authorization.
    Returns (ok, callback_url_or_error).
    """
    log("  Fetching OAuth authorize page...")
    try:
        resp = session.get(oauth_url, timeout=15, allow_redirects=True)
    except Exception as e:
        return False, f"Failed to load OAuth page: {e}"

    if "/login" in resp.url or "oauth" not in resp.url:
        return False, f"Redirected to login. URL: {resp.url}"

    html = resp.text

    if "oauth_verifier" in resp.url:
        return True, resp.url

    auth_match = re.search(r'name="authenticity_token"\s+value="([^"]+)"', html)
    if not auth_match:
        return False, "Could not find authenticity_token"

    oauth_match = re.search(r'name="oauth_token"\s+value="([^"]+)"', html)
    if not oauth_match:
        oauth_match = re.search(r'oauth_token=([^&"]+)', resp.url)
    if not oauth_match:
        return False, "Could not find oauth_token"

    log("  Authorizing app...")
    try:
        auth_resp = session.post(
            "https://api.x.com/oauth/authorize",
            data={
                "authenticity_token": auth_match.group(1),
                "redirect_after_login": resp.url,
                "oauth_token": oauth_match.group(1),
            },
            timeout=15,
            allow_redirects=False,
        )
    except Exception as e:
        return False, f"OAuth POST failed: {e}"

    if auth_resp.status_code in (301, 302, 303, 307):
        loc = auth_resp.headers.get("Location", "")
        if "oauth_verifier" in loc or "moltbook" in loc:
            return True, loc
        return False, f"Unexpected redirect: {loc}"

    for pattern in [
        r'href="([^"]*oauth_verifier[^"]*)"',
        r'(https?://[^\s"<>]*oauth_verifier=[^\s"<>]*)',
    ]:
        m = re.search(pattern, auth_resp.text)
        if m:
            return True, m.group(1)

    return False, f"OAuth returned {auth_resp.status_code}, no redirect"


def oauth2_authorize(session, ct0, oauth_url):
    """
    Automate Twitter OAuth 2.0 authorization.
    Returns (ok, callback_url_or_error).
    """
    log("  Parsing OAuth URL...")
    try:
        parsed = urlparse(oauth_url)
        params = parse_qs(parsed.query)

        client_id = params.get('client_id', [''])[0]
        code_challenge = params.get('code_challenge', [''])[0]
        code_challenge_method = params.get('code_challenge_method', [''])[0]
        redirect_uri = params.get('redirect_uri', [''])[0]
        response_type = params.get('response_type', [''])[0]
        scope = params.get('scope', [''])[0]
        state = params.get('state', [''])[0]

        log(f"  client_id: {client_id[:20]}...")
        log(f"  redirect_uri: {redirect_uri}")

        api_url = "https://twitter.com/i/api/2/oauth2/authorize"
        api_params = {
            'client_id': client_id, 'code_challenge': code_challenge,
            'code_challenge_method': code_challenge_method,
            'redirect_uri': redirect_uri, 'response_type': response_type,
            'scope': scope, 'state': state,
        }

        headers = _api_headers(ct0)

        auth_token_cookie = (session.cookies.get('auth_token', domain='.x.com')
                             or session.cookies.get('auth_token', domain='x.com'))
        ct0_cookie = (session.cookies.get('ct0', domain='.x.com')
                      or session.cookies.get('ct0', domain='x.com'))

        if not auth_token_cookie or not ct0_cookie:
            return False, "Missing required cookies"

        headers['cookie'] = f'auth_token={auth_token_cookie}; ct0={ct0_cookie}'
        headers['referer'] = oauth_url

        log("  Calling Twitter OAuth2 API...")
        resp = session.get(api_url, params=api_params, headers=headers, timeout=15)

        if resp.status_code != 200:
            return False, f"API returned {resp.status_code}"

        data = resp.json()
        auth_code = data.get('auth_code')
        if not auth_code:
            return False, f"No auth_code: {data}"

        log(f"  ✅ Got auth_code: {auth_code[:20]}...")

        # Confirm authorization
        log("  Confirming authorization...")
        post_headers = headers.copy()
        post_headers['content-type'] = 'application/x-www-form-urlencoded'
        post_headers['origin'] = 'https://twitter.com'

        confirm_resp = session.post(
            api_url, headers=post_headers,
            data=f'approval=true&code={auth_code}',
            timeout=15, allow_redirects=False,
        )

        if confirm_resp.status_code in [302, 303, 307]:
            loc = confirm_resp.headers.get('Location')
            if loc:
                return True, loc

        try:
            cdata = confirm_resp.json()
            if 'redirect_uri' in cdata:
                return True, cdata['redirect_uri']
            code = cdata.get('code') or cdata.get('auth_code')
            if code:
                return True, f"{redirect_uri}?code={code}&state={state}"
        except:
            pass

        return False, f"Unexpected confirm response: {confirm_resp.text[:300]}"

    except Exception as e:
        return False, f"Error: {e}"


def get_moltbook_oauth_url(session, claim_url):
    """
    Get OAuth URL from Moltbook using NextAuth flow.
    Returns oauth_url or None.
    """
    try:
        log("  Getting CSRF token...")
        session.get(
            "https://www.moltbook.com/api/auth/session",
            headers={"Referer": claim_url, "Accept": "*/*"},
            timeout=10,
        )

        csrf_token = None
        csrf_cookie = session.cookies.get("__Host-authjs.csrf-token")
        if csrf_cookie:
            csrf_token = csrf_cookie.split("%7C")[0] if "%7C" in csrf_cookie else csrf_cookie.split("|")[0]

        if not csrf_token:
            log("  ❌ Could not get CSRF token")
            return None

        log("  ✅ Got CSRF token")
        log("  Requesting OAuth URL...")

        callback_url = claim_url.replace("https://www.moltbook.com", "")
        if "?" not in callback_url:
            callback_url += "?x_connected=true"

        resp = session.post(
            "https://www.moltbook.com/api/auth/signin/twitter",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": claim_url,
                "Origin": "https://www.moltbook.com",
                "X-Auth-Return-Redirect": "1",
                "Accept": "*/*",
            },
            data={"csrfToken": csrf_token, "callbackUrl": callback_url},
            allow_redirects=False,
            timeout=10,
        )

        if resp.status_code in (301, 302, 303, 307):
            loc = resp.headers.get("Location", "")
            if "twitter.com" in loc or "x.com" in loc:
                log("  ✅ Got OAuth URL")
                return loc

        try:
            data = resp.json()
            if "url" in data and ("twitter.com" in data["url"] or "x.com" in data["url"]):
                log("  ✅ Got OAuth URL from JSON")
                return data["url"]
        except:
            pass

        log(f"  ❌ Unexpected response: {resp.status_code}")
        return None

    except Exception as e:
        log(f"  ❌ Error: {e}")
        return None
