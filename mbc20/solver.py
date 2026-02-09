"""Verification challenge solver — handles Moltbook's obfuscation.

Moltbook obfuscation patterns:
  1. Mixed case: tHiRtY → thirty
  2. Extra letters inserted: tHiRrTy → thirty (extra 'r')
  3. Words split by spaces: tHiRrT y → thirty
  4. Special chars injected: A] LoOoObSstT-eR's → A Lobster's
  5. Multiple patterns combined
"""

import re

from .logger import log

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
    """Basic clean: lowercase, remove special chars."""
    text = re.sub(r"[^a-zA-Z0-9 .]", " ", text)
    text = re.sub(r"\s+", " ", text).lower().strip()
    return text


def _deobfuscate(text):
    """
    Advanced deobfuscation:
    1. Remove all non-alpha chars
    2. Collapse consecutive duplicate letters
    Returns a single string with no spaces.
    """
    # Keep only letters
    alpha = re.sub(r"[^a-z]", "", text.lower())
    # Collapse consecutive duplicates: 'thhiirrrttyy' → 'thirty'
    result = []
    for ch in alpha:
        if not result or result[-1] != ch:
            result.append(ch)
    return "".join(result)


def _find_numbers_in_blob(blob):
    """
    Find number words in a deobfuscated blob string.
    Returns list of floats. Does NOT combine compound numbers
    since word boundaries are lost in the blob.
    """
    numbers = []
    # Sort by length descending to match longer words first
    # (e.g., "thirteen" before "three", "eighteen" before "eight")
    sorted_words = sorted(WORD_NUMS.keys(), key=len, reverse=True)

    remaining = blob
    while remaining:
        found = False
        for word in sorted_words:
            if remaining.startswith(word):
                val = WORD_NUMS[word]
                # Skip "hundred"/"thousand" as standalone (they're multipliers)
                if val < 100:
                    numbers.append(float(val))
                remaining = remaining[len(word):]
                found = True
                break
        if not found:
            remaining = remaining[1:]  # skip one char

    return numbers


def _extract_numbers_standard(text):
    """Extract numbers from cleaned text (standard method)."""
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
    """Detect math operation. Check mul/div first (more specific)."""
    for op in ["mul", "div", "sub", "add"]:
        for keyword in OP_KEYWORDS[op]:
            if keyword in text:
                return op
    return "add"


def solve(challenge, debug=True):
    """
    Solve an obfuscated math challenge.
    Returns answer as 'X.XX' string, or None if unsolvable.
    """
    cleaned = _clean(challenge)

    # Method 1: Standard extraction from cleaned text
    numbers = _extract_numbers_standard(cleaned)

    # Method 2: If not enough numbers, try deobfuscation
    if len(numbers) < 2:
        blob = _deobfuscate(challenge)
        numbers = [float(n) for n in _find_numbers_in_blob(blob)]
        if debug and numbers:
            log(f"  🔍 Deobfuscated numbers: {numbers}")

    # Method 3: Fallback to raw digit extraction
    if len(numbers) < 2:
        numbers = [float(n) for n in re.findall(r"\d+\.?\d*", challenge)]

    if len(numbers) < 2:
        if debug:
            log(f"  ⚠️ Solver: only {len(numbers)} numbers found")
            log(f"  ⚠️ Cleaned: {cleaned[:100]}")
            blob = _deobfuscate(challenge)
            log(f"  ⚠️ Blob: {blob[:100]}")
        return None

    # Detect operation from both cleaned and deobfuscated text
    blob = _deobfuscate(challenge)
    op = _detect_op(cleaned)
    if op == "add":
        # Double-check with blob (deobfuscated might reveal "product" etc.)
        op2 = _detect_op(blob)
        if op2 != "add":
            op = op2

    a, b = numbers[0], numbers[1]
    result = {
        "add": a + b,
        "sub": a - b,
        "mul": a * b,
        "div": a / b if b else 0,
    }.get(op, a + b)

    if debug:
        log(f"  🧮 [{a} {op} {b} = {result}]")

    return f"{result:.2f}"
