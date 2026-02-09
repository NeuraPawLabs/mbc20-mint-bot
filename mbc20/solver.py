"""Verification challenge solver — handles heavy obfuscation."""

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
    "sub": [
        "decelerat", "subtract", "minus", "decrease", "slow",
        "loses", "lose", "drop", "reduc", "shrink", "falls",
        "fell", "lower", "less", "behind",
    ],
    "mul": ["multipl", "times", "double", "triple", "product"],
    "div": ["divid", "split", "half", "halv", "quarter", "ratio"],
    "add": [
        "accelerat", "add", "plus", "increase", "gain",
        "faster", "more", "grows", "grow", "climbs", "climb",
        "rises", "rise", "ahead", "boost", "extra", "additional",
        "total", "sum", "combined",
    ],
}


def _deobfuscate_word(word):
    """
    Remove duplicate/inserted letters from an obfuscated word.
    e.g. 'tHiRrTy' → 'thirty', 'LoOoObSstTeR' → 'lobster'

    Strategy: collapse consecutive duplicate letters, then try fuzzy match.
    """
    w = word.lower()
    # Step 1: collapse runs of same letter (e.g., 'ooo' → 'o', 'ss' → 's', 'tt' → 't')
    collapsed = re.sub(r"(.)\1+", r"\1", w)
    return collapsed


def _clean(text):
    """Remove obfuscation from challenge text."""
    # Replace hyphens between letters with space
    text = re.sub(r"(?<=[a-zA-Z])-(?=[a-zA-Z])", " ", text)
    # Remove non-alphanumeric except spaces and dots
    text = re.sub(r"[^a-zA-Z0-9 .]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip().lower()

    # Deobfuscate: collapse duplicate letters in each word
    words = [re.sub(r"(.)\1+", r"\1", w) for w in text.split()]

    # Merge fragmented tokens: try joining adjacent words to form number words
    merged = []
    i = 0
    while i < len(words):
        found = False
        # Try merging up to 3 adjacent tokens
        for span in range(3, 0, -1):
            if i + span <= len(words):
                combo = "".join(words[i : i + span])
                # Also try with collapsed duplicates
                combo_collapsed = re.sub(r"(.)\1+", r"\1", combo)
                if combo_collapsed in WORD_NUMS or combo in WORD_NUMS:
                    merged.append(combo_collapsed if combo_collapsed in WORD_NUMS else combo)
                    i += span
                    found = True
                    break
        if not found:
            merged.append(words[i])
            i += 1

    return " ".join(merged)


def _fuzzy_match_number(word):
    """Try to fuzzy-match a word to a number word."""
    if word in WORD_NUMS:
        return word

    # Try with collapsed duplicates
    collapsed = re.sub(r"(.)\1+", r"\1", word)
    if collapsed in WORD_NUMS:
        return collapsed

    # Try matching against known number words with edit distance
    for num_word in WORD_NUMS:
        # Check if the collapsed word contains the number word as subsequence
        if _is_subsequence(num_word, word):
            return num_word

    return None


def _is_subsequence(short, long):
    """Check if 'short' is a subsequence of 'long'."""
    it = iter(long)
    return all(c in it for c in short)


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
            continue

        # Try exact match
        if w in WORD_NUMS:
            nw = []
            while i < len(words) and words[i].strip(".,?!") in WORD_NUMS:
                nw.append(words[i].strip(".,?!"))
                i += 1
            numbers.append(float(_words_to_number(nw)))
            continue

        # Try fuzzy match
        matched = _fuzzy_match_number(w)
        if matched:
            nw = [matched]
            i += 1
            while i < len(words):
                next_w = words[i].strip(".,?!")
                next_match = _fuzzy_match_number(next_w) or (next_w if next_w in WORD_NUMS else None)
                if next_match:
                    nw.append(next_match)
                    i += 1
                else:
                    break
            numbers.append(float(_words_to_number(nw)))
            continue

        i += 1

    return numbers


def _words_to_number(words):
    """Convert word-form number to int."""
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


def _detect_op(text):
    """Detect math operation from cleaned text."""
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
    numbers = _extract_numbers(cleaned)

    # Fallback: extract raw digits from original
    if len(numbers) < 2:
        numbers = [float(n) for n in re.findall(r"\d+\.?\d*", challenge)]

    if len(numbers) < 2:
        if debug:
            log(f"  ⚠️ Solver: only {len(numbers)} numbers in: {cleaned[:80]}")
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
        log(f"  🧮 [{a} {op} {b} = {result}] {cleaned[:60]}...")

    return f"{result:.2f}"
