"""Verification challenge solver — with debug logging."""

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

# Operation keywords — order matters (check specific before generic)
OP_KEYWORDS = {
    "sub": [
        "decelerat", "subtract", "minus", "decrease", "slow",
        "loses", "lose", "drop", "reduc", "shrink", "falls",
        "fell", "lower", "less", "behind",
    ],
    "mul": ["multipl", "times", "double", "triple"],
    "div": ["divid", "split", "half", "halv", "quarter"],
    "add": [
        "accelerat", "add", "plus", "increase", "gain",
        "faster", "more", "grows", "grow", "climbs", "climb",
        "rises", "rise", "ahead", "boost", "extra", "additional",
    ],
}


def _clean(text):
    """Remove obfuscation (mixed case, special chars, hyphens)."""
    # Replace hyphens between letters with space (e.g., "lOb-StEr" → "lOb StEr")
    text = re.sub(r"(?<=[a-zA-Z])-(?=[a-zA-Z])", " ", text)
    # Remove non-alphanumeric except spaces and dots
    text = re.sub(r"[^a-zA-Z0-9 .]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).lower().strip()
    return text


def _words_to_number(words):
    """Convert word-form number to int. Handles compound like 'twenty five'."""
    if not words:
        return 0
    current = 0
    for w in words:
        if w not in WORD_NUMS:
            break
        val = WORD_NUMS[w]
        if val >= 100:
            current = (current or 1) * val
        else:
            current += val
    return current


def _extract_numbers(text):
    """Extract all numbers (digit or word form) from cleaned text."""
    numbers = []
    words = text.split()
    i = 0
    while i < len(words):
        w = words[i].strip(".,?!")
        # Try digit
        if re.match(r"^\d+\.?\d*$", w):
            numbers.append(float(w))
            i += 1
        # Try word number
        elif w in WORD_NUMS:
            nw = []
            while i < len(words) and words[i].strip(".,?!") in WORD_NUMS:
                nw.append(words[i].strip(".,?!"))
                i += 1
            numbers.append(float(_words_to_number(nw)))
        else:
            i += 1
    return numbers


def _detect_op(text):
    """Detect math operation from cleaned text."""
    # Check subtraction first (to avoid "more" matching when "slows" is present)
    for op in ["sub", "mul", "div", "add"]:
        for keyword in OP_KEYWORDS[op]:
            if keyword in text:
                return op
    return "add"  # default


def solve(challenge, debug=True):
    """
    Solve an obfuscated math challenge.
    Returns answer as 'X.XX' string, or None if unsolvable.
    """
    cleaned = _clean(challenge)
    numbers = _extract_numbers(cleaned)

    # Fallback: extract raw digits from original
    if len(numbers) < 2:
        numbers = [float(n) for n in re.findall(r"\d+\.?\d*", challenge)]

    if len(numbers) < 2:
        if debug:
            log(f"  ⚠️ Solver: only {len(numbers)} numbers found")
            log(f"  ⚠️ Cleaned: {cleaned[:100]}")
        return None

    op = _detect_op(cleaned)
    a, b = numbers[0], numbers[1]

    result = {
        "add": a + b,
        "sub": a - b,
        "mul": a * b,
        "div": a / b if b else 0,
    }.get(op, a + b)

    if debug:
        log(f"  🧮 [{a} {op} {b} = {result}] cleaned: {cleaned[:60]}...")

    return f"{result:.2f}"
