"""Verification challenge solver — uses Claude Haiku LLM with regex fallback.

Primary: Claude Haiku via Anthropic Messages API (fast, accurate)
Fallback: Regex-based solver for when LLM is unavailable
"""

import os
import re
import json

import requests

from .logger import log

# ─── LLM Config ───

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://cc-gateway.gtapp.xyz/api")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001")
LLM_TIMEOUT = 15

SYSTEM_PROMPT = """You are a math puzzle solver. You will receive an obfuscated text that contains a math problem.

The text may have:
- Mixed case letters (tHiRtY = thirty)
- Extra letters inserted (tHiRrTy = thirty)
- Words split by spaces or special characters
- Numbers written as words (twenty-three = 23)

Your job:
1. Decode the obfuscated text to find the actual math problem
2. Identify the two numbers and the operation (add/subtract/multiply/divide)
3. Calculate the answer
4. Reply with ONLY the numeric answer rounded to 2 decimal places (e.g. "42.00")

Do NOT include any explanation. Just the number."""


def _solve_llm(challenge):
    """Solve using Claude Haiku. Returns 'X.XX' string or None."""
    if not LLM_API_KEY:
        return None

    try:
        url = f"{LLM_BASE_URL}/v1/messages"
        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": LLM_MODEL,
            "max_tokens": 64,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": challenge}],
        }
        r = requests.post(url, headers=headers, json=body, timeout=LLM_TIMEOUT)
        if r.status_code != 200:
            log(f"  ⚠️ LLM error: {r.status_code} {r.text[:100]}")
            return None

        data = r.json()
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]

        text = text.strip()
        # Extract number from response
        match = re.search(r"-?\d+\.?\d*", text)
        if match:
            num = float(match.group())
            return f"{num:.2f}"
        log(f"  ⚠️ LLM response not a number: {text[:50]}")
        return None

    except Exception as e:
        log(f"  ⚠️ LLM exception: {e}")
        return None


# ─── Regex Fallback ───

WORD_NUMS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
}

OP_KEYWORDS = {
    "mul": ["product", "multipl", "times", "double", "triple"],
    "div": ["divid", "split", "half", "halv", "quarter", "ratio"],
    "sub": [
        "decelerat", "subtract", "minus", "decrease", "slow",
        "loses", "lose", "drop", "reduc", "shrink", "falls",
        "fell", "lower", "behind", "less",
    ],
    "add": [
        "accelerat", "add", "plus", "increase", "gain",
        "faster", "more", "grows", "grow", "climbs", "climb",
        "rises", "rise", "ahead", "boost", "extra", "sum", "total",
    ],
}


def _clean(text):
    text = re.sub(r"[^a-zA-Z0-9 .]", " ", text)
    text = re.sub(r"\s+", " ", text).lower().strip()
    return text


def _deobfuscate(text):
    alpha = re.sub(r"[^a-z]", "", text.lower())
    collapsed = []
    for ch in alpha:
        if not collapsed or collapsed[-1] != ch:
            collapsed.append(ch)
    return alpha, "".join(collapsed)


def _find_numbers_in_blob(blob):
    entries = []
    sorted_words = sorted(WORD_NUMS.keys(), key=len, reverse=True)
    pos = 0
    while pos < len(blob):
        found = False
        for word in sorted_words:
            if blob[pos:].startswith(word):
                val = WORD_NUMS[word]
                if val < 100:
                    entries.append((val, pos, pos + len(word)))
                pos += len(word)
                found = True
                break
        if not found:
            pos += 1

    numbers = []
    i = 0
    while i < len(entries):
        val, start, end = entries[i]
        if val in (20, 30, 40, 50, 60, 70, 80, 90) and i + 1 < len(entries):
            next_val, next_start, next_end = entries[i + 1]
            if 1 <= next_val <= 9 and next_start == end:
                numbers.append(float(val + next_val))
                i += 2
                continue
        numbers.append(float(val))
        i += 1
    return numbers


def _extract_numbers_standard(text):
    numbers = []
    words = text.split()
    i = 0
    while i < len(words):
        w = words[i].strip(".,?!")
        if re.match(r"^\d+\.?\d*$", w):
            numbers.append(float(w))
            i += 1
        elif w in WORD_NUMS:
            nw = []
            while i < len(words) and words[i].strip(".,?!") in WORD_NUMS:
                nw.append(words[i].strip(".,?!"))
                i += 1
            current = 0
            for ww in nw:
                val = WORD_NUMS[ww]
                if val >= 100:
                    current = (current or 1) * val
                else:
                    current += val
            numbers.append(float(current))
        else:
            i += 1
    return numbers


def _detect_op(text):
    for op in ["mul", "div", "sub", "add"]:
        for keyword in OP_KEYWORDS[op]:
            if keyword in text:
                return op
    return "add"


def _solve_regex(challenge, debug=True):
    """Regex-based fallback solver."""
    cleaned = _clean(challenge)
    raw_blob, collapsed_blob = _deobfuscate(challenge)

    std_nums = _extract_numbers_standard(cleaned)
    raw_nums = _find_numbers_in_blob(raw_blob)
    col_nums = _find_numbers_in_blob(collapsed_blob)
    blob_nums = raw_nums if len(raw_nums) >= len(col_nums) else col_nums

    if len(blob_nums) >= 2:
        numbers = blob_nums
    elif len(std_nums) >= 2:
        numbers = std_nums
    else:
        numbers = [float(n) for n in re.findall(r"\d+\.?\d*", challenge)]

    if len(numbers) < 2:
        if debug:
            log(f"  ⚠️ Regex solver: only {len(numbers)} numbers found")
        return None

    op = _detect_op(cleaned)
    if op == "add":
        op = _detect_op(raw_blob)
    if op == "add":
        op = _detect_op(collapsed_blob)

    a, b = numbers[0], numbers[1]
    result = {
        "add": a + b, "sub": a - b,
        "mul": a * b, "div": a / b if b else 0,
    }.get(op, a + b)

    if debug:
        log(f"  🧮 Regex: [{a} {op} {b} = {result}]")
    return f"{result:.2f}"


# ─── Public API ───

def solve(challenge, debug=True):
    """
    Solve an obfuscated math challenge.
    Primary: Claude Haiku LLM
    Fallback: Regex-based solver
    Returns answer as 'X.XX' string, or None if unsolvable.
    """
    if debug:
        log(f"  🔒 Challenge: {challenge[:80]}...")

    # Try LLM first
    answer = _solve_llm(challenge)
    if answer:
        if debug:
            log(f"  🤖 LLM answer: {answer}")
        return answer

    # Fallback to regex
    if debug:
        log(f"  ⚠️ LLM unavailable, using regex fallback")
    return _solve_regex(challenge, debug=debug)
