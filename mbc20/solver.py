"""Verification challenge solver."""

import re

WORD_NUMS = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
    'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
    'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13,
    'fourteen': 14, 'fifteen': 15, 'sixteen': 16, 'seventeen': 17,
    'eighteen': 18, 'nineteen': 19, 'twenty': 20, 'thirty': 30,
    'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
    'eighty': 80, 'ninety': 90, 'hundred': 100, 'thousand': 1000,
}


def _clean(text):
    """Remove obfuscation from challenge text."""
    return re.sub(r'\s+', ' ', re.sub(r'[^a-zA-Z0-9 .,?]', ' ', text)).lower().strip()


def _words_to_number(words):
    """Convert consecutive number words to a number."""
    current = 0
    for w in words:
        if w not in WORD_NUMS:
            break
        val = WORD_NUMS[w]
        current = ((current or 1) * val) if val >= 100 else (current + val)
    return current


def _extract_numbers(text):
    """Extract all numbers (digit or word form) from text."""
    numbers, words, i = [], text.split(), 0
    while i < len(words):
        w = words[i].strip('.,?!')
        if re.match(r'^\d+\.?\d*$', w):
            numbers.append(float(w))
            i += 1
        elif w in WORD_NUMS:
            nw = []
            while i < len(words) and words[i].strip('.,?!') in WORD_NUMS:
                nw.append(words[i].strip('.,?!'))
                i += 1
            numbers.append(_words_to_number(nw))
        else:
            i += 1
    return numbers


def _detect_op(text):
    """Detect math operation from text."""
    ops = {
        'add': ['accelerat', 'add', 'plus', 'increase', 'gain', 'faster', 'more', 'grows', 'grow', 'climbs', 'rises'],
        'sub': ['decelerat', 'subtract', 'minus', 'decrease', 'slow', 'less', 'lose', 'loses', 'drop', 'reduc', 'shrink', 'falls'],
        'mul': ['multipl', 'times', 'double', 'triple'],
        'div': ['divid', 'split', 'half', 'halv'],
    }
    for op, keywords in ops.items():
        if any(k in text for k in keywords):
            return op
    return 'add'


def solve(challenge):
    """Solve an obfuscated math challenge. Returns answer as 'X.XX' or None."""
    cleaned = _clean(challenge)
    numbers = _extract_numbers(cleaned)

    if len(numbers) < 2:
        numbers = [float(n) for n in re.findall(r'\d+\.?\d*', challenge)]

    if len(numbers) < 2:
        return None

    op = _detect_op(cleaned)
    a, b = numbers[0], numbers[1]
    result = {'add': a + b, 'sub': a - b, 'mul': a * b, 'div': a / b if b else 0}.get(op, a + b)
    return f"{result:.2f}"
