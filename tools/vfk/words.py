"""Words: normalising text for matching, numbers spelled out as spoken (for wav2vec2), transcript I/O."""
import json
import re

_U = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
      "seventeen eighteen nineteen").split()
_D = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def integer_words(n):
    """1234 → 'one thousand two hundred thirty four' (English)."""
    if n < 20:
        return _U[n]
    if n < 100:
        return _D[n // 10] + ("" if n % 10 == 0 else " " + _U[n % 10])
    if n < 1000:
        return _U[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + integer_words(n % 100))
    for v, name in ((10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")):
        if n >= v:
            return integer_words(n // v) + " " + name + ("" if n % v == 0 else " " + integer_words(n % v))
    return str(n)


def spoken_word(token):
    """How a written number is SAID: '$210,000' → 'two hundred ten thousand dollars', '16.6%' → 'sixteen point six percent'.
    wav2vec2 aligns letters: a number with no letters gets no time and squashes the words after it."""
    core = token.strip(".,?!:;\"«»()")
    m = re.fullmatch(r"(\$?)(\d[\d,]*)(\.\d+)?(%?)", core)
    if not m:
        return token
    dol, num, dec, pct = m.groups()
    n = int(num.replace(",", ""))
    if 2010 <= n <= 2099 and not dol and not dec and "," not in num:
        t = "twenty " + integer_words(n % 100)
    else:
        t = integer_words(n)
    if dec:
        t += " point " + " ".join(_U[int(c)] for c in dec[1:])
    return t + (" percent" if pct else "") + (" dollars" if dol else "")


def spoken_text(text, language="en"):
    """Numbers in a whole text → words (English only; other languages are returned as they are)."""
    if language != "en":
        return text
    return " ".join(spoken_word(t) for t in text.split())


def norm(w):
    """For finding phrases in a transcript: lower case, no punctuation."""
    return re.sub(r"[^\w]", "", w.lower().replace("’", "'"))


def norm_spoken(t):
    """Comparable text: no punctuation, numbers as words, without 'dollars'/'percent' (Whisper writes them or not)."""
    t = t.lower().replace("’", "'").replace("'", "")
    t = re.sub(r"(\d),(\d)", r"\1\2", t)
    t = re.sub(r"\d+(\.\d+)?", lambda m: spoken_word(m.group(0)).replace(" dollars", ""), t)
    t = re.sub(r"[^a-z]", "", t)
    for x in ("dollars", "dollar", "percent"):
        t = t.replace(x, "")
    t = t.replace("hundredand", "hundred")
    for big in ("hundred", "thousand", "million", "billion"):   # 'a hundred' = 'one hundred'
        t = t.replace("a" + big, "one" + big)
    return t


def tokens(t):
    """Tokens for comparing a script with what Whisper hears."""
    t = t.lower().replace("’", "'").replace("'", "").replace("%", " percent ").replace("$", "")
    t = re.sub(r"(\d),(\d)", r"\1\2", t)
    return [x.strip(".") for x in re.split(r"[^\w.]+", t) if x.strip(".")]


def load_words(path):
    """Flat word list [{w, s, e, p?, aligned?}] of a .words.json transcript."""
    j = json.loads(path.read_text(encoding="utf-8"))
    return [w for s in j["segments"] for w in s["words"]]
