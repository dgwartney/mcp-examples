"""
Parse a date of birth the way a caller says it, in English or Spanish, after
speech-to-text: "March fourteenth nineteen ninety-one", "the 14th of March,
1991", "14 de marzo de 1991", "catorce de marzo de mil novecientos noventa y
uno". A month name is required; the day and the year may be words or numerals.

Only what a phone caller plausibly says is covered. Anything else returns None
so the caller is asked again rather than verified against a guessed date.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Optional

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# Number words that stand alone: units, teens, Spanish 21-29 and ordinals.
SMALL = {
    "zero": 0, "oh": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
    "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
    "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20, "thirtieth": 30,
    "cero": 0, "uno": 1, "un": 1, "primero": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13,
    "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18,
    "diecinueve": 19, "veintiuno": 21, "veintiun": 21, "veintidos": 22, "veintitres": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27, "veintiocho": 28,
    "veintinueve": 29,
}
TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
    "veinte": 20, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
    "ochenta": 80, "noventa": 90,
}
HUNDREDS = {
    "cien": 100, "ciento": 100, "doscientos": 200, "trescientos": 300, "cuatrocientos": 400,
    "quinientos": 500, "seiscientos": 600, "setecientos": 700, "ochocientos": 800,
    "novecientos": 900,
}
# Words that carry no number: "the 14th of March", "14 de marzo del 1991", "and".
FILLER = {"the", "of", "on", "in", "and", "y", "de", "del", "el", "born", "my", "is", "it's", "its"}


def _tokens(text: str) -> list[str]:
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    plain = re.sub(r"(\d+)(st|nd|rd|th|o|a|ro)\b", r"\1", plain)
    return re.findall(r"[a-z']+|\d+", plain.replace("-", " "))


def _numbers(words: list[str]) -> list[int]:
    """Group number words into values: [fourteen] [nineteen ninety one] -> [14, 1991]."""
    values: list[int] = []
    run: list[str] = []

    def flush() -> None:
        if run:
            values.extend(_run_value(run))
            run.clear()

    for w in words:
        if w.isdigit():
            flush()
            values.append(int(w))
        elif w in SMALL or w in TENS or w in HUNDREDS or w in ("hundred", "thousand", "mil"):
            run.append(w)
        elif w in FILLER:
            if w == "y" and run:
                continue  # "noventa y uno" is one number
            flush()
        else:
            flush()
    flush()
    return values


def _run_value(run: list[str]) -> list[int]:
    """
    Value(s) of one run of number words. A day then a year can share a run
    ("fourteenth nineteen ninety one"), so an ordinal or a leading day word that
    leaves a year behind is split off first.
    """
    if len(run) > 1 and run[0] in SMALL and run[0].endswith(("th", "st", "nd", "rd")):
        return [SMALL[run[0]], *_run_value(run[1:])]
    total = _compose(run)
    if total is not None:
        return [total]
    # Day, then year: "catorce mil novecientos noventa y uno".
    for cut in range(1, len(run)):
        head, tail = _compose(run[:cut]), _compose(run[cut:])
        if head is not None and tail is not None and 1 <= head <= 31 and tail >= 1000:
            return [head, tail]
    return []


def _compose(run: list[str]) -> Optional[int]:
    """One cardinal from non-empty number words, or None when they aren't a single number."""
    # English year pairs: "nineteen ninety one" -> 1991, "twenty oh five" -> 2005.
    if run[0] in ("nineteen", "twenty") and len(run) >= 2 and run[1] not in ("thousand", "hundred"):
        century = (SMALL.get(run[0]) or TENS[run[0]]) * 100
        if run[1] in ("oh", "zero") and len(run) == 3 and run[2] in SMALL:
            return century + SMALL[run[2]]
        rest = _compose(run[1:])
        if rest is not None and 10 <= rest < 100:
            return century + rest
    total, current = 0, 0
    last = ""
    for w in run:
        if w in ("thousand", "mil"):
            total += (current or 1) * 1000
            current = 0
        elif w == "hundred":
            current = (current or 1) * 100
        elif w in HUNDREDS:
            current += HUNDREDS[w]
        elif w in TENS:
            if current % 100:
                return None
            current += TENS[w]
        else:  # a SMALL word: runs hold only number words
            if current % 10 or (last in SMALL):
                return None
            current += SMALL[w]
        last = w
    return total + current


def parse_spoken_date(text: str) -> Optional[date]:
    """A date from spoken English or Spanish, or None. Needs a month name, a day and a 4-digit year."""
    words = _tokens(str(text or ""))
    month = next((MONTHS[w] for w in words if w in MONTHS), None)
    if month is None:
        return None
    numbers = _numbers(words)  # a month word ends a run of number words
    days = [n for n in numbers if 1 <= n <= 31]
    years = [n for n in numbers if 1900 <= n <= 2100]
    if len(days) != 1 or len(years) != 1:
        return None
    try:
        return date(years[0], month, days[0])
    except ValueError:
        return None
