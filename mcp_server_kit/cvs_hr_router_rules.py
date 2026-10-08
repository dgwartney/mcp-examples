"""
Deterministic interpretation of a caller's free-text reply (English + Spanish).

Artemis specialist agents cannot reliably classify the caller's next words,
so every decision about a free-text reply is made here, by keyword and
phrase rules, with no I/O: the next intent, consent, a PTO target in hours,
the recap language, whether the caller wants Spanish, and which other
language they asked about.

Matching runs on a "folded" copy of the text (lower-case, accents removed),
so "español", "Espanol" and "ESPAÑOL" all match ``espanol``.

Author:
    David Gwartney <david.gwartney@gmail.com>
"""

import re
import unicodedata
from dataclasses import asdict, dataclass

INTENTS = ("pay", "pto", "leave", "recap", "language", "close", "ack", "other", "none")
HOURS_PER_DAY = 8
DAYS_PER_WEEK = 5


def fold(text: str) -> str:
    """Lower-case, strip accents, normalise apostrophes and whitespace."""
    text = unicodedata.normalize("NFKD", (text or "").replace("’", "'").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip()


def _rx(*patterns: str) -> re.Pattern:
    return re.compile("|".join(f"(?:{p})" for p in patterns))


# --------------------------------------------------------------------------- intents

_LEAVE_FAMILY = _rx(  # family/baby words: when present, leave wins over pto
    r"\bpaternity\b", r"\bmaternity\b", r"\bparental\b", r"\bfather\b", r"\bmother\b",
    r"\bdad\b", r"\bmom\b", r"\bbaby\b", r"\bexpecting\b", r"\bpregnan\w*", r"\badoption\b",
    r"\badopt\w*", r"\bbebe\b", r"\bpaternidad\b", r"\bmaternidad\b", r"\bnewborn\b")
_LEAVE = _rx(
    r"\bleave\b(?!\s+(?:it|them|that|this|as is|alone|me)\b)", r"\bfmla\b", r"\bdisability\b",
    r"\bbereavement\b", r"\bbenefits?\b", r"\bhsa\b", r"\benroll\w*", r"\binsurance\b",
    r"\blicencia\b", r"\bbeneficios?\b", _LEAVE_FAMILY.pattern)
_PTO = _rx(
    r"\bpto\b", r"\bpaid time off\b", r"\bvacations?\b", r"\btime off\b", r"\baccru\w*",
    r"\bbalance\b", r"\benough to take\b", r"\b(?:days?|weeks?) off\b", r"\bvacaciones\b",
    r"\bdias libres\b")
_PAY = _rx(  # strong pay words
    r"\bpaychecks?\b", r"\bpay ?checks?\b", r"\bpaystubs?\b", r"\bshort\b", r"\bshorted\b",
    r"\btime ?cards?\b", r"\bovertime\b", r"\bmissing\b", r"\bcheques?\b", r"\bpago\b",
    r"\bcheck(?:'s)?\b(?!\s+(?:with|on|in|out|back)\b)", r"\bunderpaid\b")
_PAY_WEAK = _rx(r"\bpay\b", r"\bhours?\b", r"\bhoras\b")  # only when nothing else matched
_RECAP = _rx(
    r"\brecap\w*", r"\bsummari[sz]e\b", r"\bsummary\b", r"\brepeat everything\b",
    r"\bgo over\b", r"\bsum (?:it )?up\b", r"\bresumen\b", r"\bresuma\b", r"\brepita\b")
_CLOSE = _rx(
    r"\bthat'?s all\b", r"\bthat'?s it\b", r"\bthanks\b", r"\bthank you\b", r"\bbye\b",
    r"\bgoodbye\b", r"\bnothing else\b", r"\bgracias\b", r"\badios\b", r"\bhasta luego\b")
# A question after "thanks" is a follow-up, not a goodbye. Voice transcripts often
# drop the "?", so interrogative words count too.
_QUESTION = _rx(
    r"[?¿]", r"\b(?:what|when|where|why|how|which|who)\b",
    r"\b(?:does|do|is|are|can|could|will|would) (?:that|it|this|i|you|my)\b",
    r"\b(?:cuando|cuanto|cuantos|cuantas|como|donde|por que|incluye)\b")

# Other languages: (pattern on folded text, display name)
_LANGUAGES = [
    (r"\bparlez\b|\bfrancais\b|\bfrench\b", "French"),
    (r"\bportugues\b|\bportuguese\b|\bfala\b", "Portuguese"),
    (r"\bvietnamese\b|\btieng viet\b", "Vietnamese"),
    (r"\bmandarin\b|\bchinese\b|\bcantonese\b", "Chinese"),
    (r"\bgerman\b|\bdeutsch\b", "German"),
    (r"\bitalian\b|\bitaliano\b", "Italian"),
    (r"\bjapanese\b", "Japanese"),
    (r"\bkorean\b", "Korean"),
    (r"\brussian\b", "Russian"),
    (r"\barabic\b", "Arabic"),
    (r"\bhindi\b", "Hindi"),
    (r"\btagalog\b", "Tagalog"),
    (r"\bcreole\b|\bkreyol\b", "Haitian Creole"),
    (r"\bpolish\b", "Polish"),
]
_SPEAK_X = re.compile(r"\b(?:do you|can you|you) speak ([a-z]+)|\bhabla(?:s)? ([a-z]+)")
_ENGLISH_OR_SPANISH = {"english", "spanish", "espanol", "ingles", "castellano"}

# ---------------------------------------------------------------------- consent

_AFFIRM = _rx(
    r"\byes\b", r"\byeah\b", r"\byep\b", r"\byup\b", r"\bsure\b", r"\bok\b", r"\bokay\b",
    r"\bplease\b", r"\bgo ahead\b", r"\bdo it\b", r"\bcorrect it\b", r"\bfix it\b",
    r"\babsolutely\b", r"\bof course\b", r"\bsi\b", r"\bclaro\b", r"\bpor favor\b",
    r"\bdale\b", r"\bde acuerdo\b")
_NEGATE = _rx(
    r"\bno\b", r"\bnope\b", r"\bdon'?t\b", r"\bdo not\b", r"\bleave it\b", r"\bnot now\b",
    r"\bcheck with my (?:manager|supervisor|boss)\b", r"\bhold off\b", r"\bno gracias\b",
    r"\btodavia no\b", r"\bnot yet\b", r"\blet me think\b", r"\bnever ?mind\b")
_WAIT = re.compile(r"\bwait\b|\bhang on\b|\bespere\b")
# A reply that only acknowledges ("Okay.", "Great, got it.") and asks for nothing.
# Checked word by word against fixed sets, so no regex can backtrack on long input.
_ACK_PHRASES = ("all right", "got it", "i see", "sounds good", "uh huh")
_ACK_WORDS = frozenset({
    "ok", "okay", "alright", "great", "good", "sure", "yeah", "yes", "yep", "yup", "cool",
    "perfect", "fine", "right", "excellent", "wonderful", "awesome", "vale", "bueno",
    "claro", "perfecto"})
_ACK_MAX_CHARS = 120


def is_acknowledgment(t: str) -> bool:
    """True when folded text ``t`` is only acknowledgment words ("okay, great")."""
    if not t or len(t) > _ACK_MAX_CHARS:
        return False
    for phrase in _ACK_PHRASES:
        t = t.replace(phrase, " ok ")
    words = [w for w in re.split(r"[\s,.!]+", t) if w]
    return bool(words) and all(
        w in _ACK_WORDS or (len(w) >= 2 and set(w) == {"m"}) for w in words)
# What a question at the consent step is about, answered from values already read.
_ABOUT_DAYS = _rx(r"\bdays?\b", r"\bdates?\b", r"\bwhen\b", r"\bmonday|tuesday|wednesday|thursday|friday|saturday|sunday\b",
                  r"\bwhich (?:shifts?|ones?)\b", r"\bdias?\b", r"\bcuales\b", r"\bfechas?\b")
_ABOUT_AMOUNT = _rx(r"\bhow much\b", r"\bamount\b", r"\bdollars?\b", r"\bmoney\b", r"\bhours?\b",
                    r"\bcuanto\b", r"\bhoras?\b")

# -------------------------------------------------------------------- durations

_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20,
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13,
    "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18,
    "diecinueve": 19, "veinte": 20,
}
_NUM = r"(\d+(?:\.\d+)?|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + r")"
_DURATION = re.compile(
    rf"\b{_NUM}\s+(?:(?:solid|full|whole|more|straight|working|work|business)\s+)?"
    r"(hours?|hrs?|days?|weeks?|horas?|dias?|semanas?)\b")
_UNIT_HOURS = {"h": 1, "d": HOURS_PER_DAY, "w": HOURS_PER_DAY * DAYS_PER_WEEK,
               "s": HOURS_PER_DAY * DAYS_PER_WEEK}

# ----------------------------------------------------------------------- spanish

_SPANISH_WORDS = {
    "el", "la", "los", "las", "de", "del", "que", "mi", "mis", "su", "por", "favor", "quiero",
    "tengo", "cuantas", "cuanto", "cuantos", "horas", "cheque", "pago", "si", "es", "para",
    "con", "una", "un", "se", "esta", "estoy", "como", "cuando", "donde", "gracias", "hola",
    "buenos", "dias", "tardes", "necesito", "puede", "ayuda", "ayudar", "vacaciones",
    "licencia", "bebe", "claro", "pero", "tambien", "muy", "bien", "hablar", "espanol",
    "semana", "semanas", "dinero", "falta", "corto", "nomina", "usted", "yo", "le", "lo",
}
_SPANISH_REQUEST = re.compile(r"\bespanol\b|\bspanish\b|\bdos\b|\ben castellano\b")
_ENGLISH_REQUEST = re.compile(r"\benglish\b|\bingles\b")
_HUMAN = _rx(r"\b(?:talk|speak) (?:to|with) (?:someone|somebody|a person|a human|a real person|an agent|a representative)\b",
             r"\b(?:real|live) person\b", r"\bhuman\b", r"\brepresentative\b", r"\boperator\b",
             r"\bun agente\b", r"\buna persona\b")


@dataclass(frozen=True)
class ReplyInterpretation:
    """
    Flat result of :func:`interpret_reply`. Every field is a string so ABL
    templates and conditions never have to format values: booleans are
    ``"yes"``/``"no"``, ``target_hours`` is ``""`` when absent, and
    ``intents`` is a comma-separated list in the order spoken.
    """

    intent: str
    pending_intent: str = ""
    intents: str = ""
    consent: str = "unclear"
    question_topic: str = ""
    target_hours: str = ""
    recap_language: str = ""
    wants_spanish: str = "no"
    language_name: str = ""
    wants_human: str = "no"
    leave_topic: str = ""
    expecting: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _first_pos(rx: re.Pattern, text: str) -> int:
    m = rx.search(text)
    return m.start() if m else -1


def detect_language_name(text: str) -> str:
    """Name of a language other than English/Spanish the caller asks about, else ``''``."""
    t = fold(text)
    for pattern, name in _LANGUAGES:
        if re.search(pattern, t):
            return name
    m = _SPEAK_X.search(t)
    if m:
        word = m.group(1) or m.group(2)
        if word not in _ENGLISH_OR_SPANISH and word.isalpha():
            return word.capitalize()
    return ""


def detect_intents(text: str) -> list[str]:
    """
    All intents in the order spoken. Leave beats pto when family/baby words
    appear; close counts only when nothing else does; weak pay words
    ("pay", "hours") count only when no other intent matched.
    """
    t = fold(text)
    if not t:
        return []
    positions = {
        "language": _first_pos(re.compile("|".join(p for p, _ in _LANGUAGES)), t)
        if detect_language_name(t) else -1,
        "recap": _first_pos(_RECAP, t),
        "leave": _first_pos(_LEAVE, t),
        "pto": _first_pos(_PTO, t),
        "pay": _first_pos(_PAY, t),
    }
    if positions["language"] < 0 and detect_language_name(t):
        positions["language"] = _first_pos(_SPEAK_X, t)
    if positions["leave"] >= 0 and _LEAVE_FAMILY.search(t):
        positions["pto"] = -1
    found = sorted((pos, name) for name, pos in positions.items() if pos >= 0)
    intents = [name for _, name in found]
    if not intents and _PAY_WEAK.search(t):
        intents = ["pay"]
    if not intents and _CLOSE.search(t) and not _QUESTION.search(t):
        intents = ["close"]
    return intents


def detect_consent(text: str) -> str:
    """
    ``'yes'`` (affirmative, no negation), ``'no'`` (any negation, or a bare
    "wait"), ``'question'`` (the caller asks something instead of answering,
    e.g. a barge-in "Wait, which days?", with or without the "?") or ``'unclear'``.
    """
    t = fold(text)
    if _NEGATE.search(t):
        return "no"
    if _AFFIRM.search(t):
        return "yes"
    if _QUESTION.search(t):
        return "question"
    if _WAIT.search(t):
        return "no"
    return "unclear"


def detect_question_topic(text: str) -> str:
    """For a question: ``'days'``, ``'amount'`` or ``'other'``; ``''`` if it isn't one."""
    t = fold(text)
    if not _QUESTION.search(t):
        return ""
    if _ABOUT_DAYS.search(t):
        return "days"
    if _ABOUT_AMOUNT.search(t):
        return "amount"
    return "other"


def parse_target_hours(text: str) -> float:
    """
    First duration in the text, in PTO hours (8 h a day, 5 days a week):
    "ten solid days" -> 80, "two weeks" -> 80, "a week" -> 40, "40 hours" -> 40.
    Returns 0 when there is none. Whole numbers come back as ``int``.
    """
    return _parse_duration(fold(text))[0]


def _parse_duration(folded: str) -> tuple[float, str]:
    """``(hours, unit initial)`` for the first duration in folded text, else ``(0, '')``."""
    m = _DURATION.search(folded)
    if not m:
        return 0, ""
    raw, unit = m.group(1), m.group(2)
    qty = float(raw) if raw[0].isdigit() else float(_NUMBER_WORDS[raw])
    hours = qty * _UNIT_HOURS[unit[0]]
    return (int(hours) if hours == int(hours) else hours), unit[0]


def detect_recap_language(text: str) -> str:
    """``'es'`` if Spanish is requested, ``'en'`` if English is, else ``''``."""
    t = fold(text)
    if re.search(r"\bespanol\b|\bspanish\b|\ben castellano\b", t):
        return "es"
    if _ENGLISH_REQUEST.search(t):
        return "en"
    return ""


def is_mostly_spanish(text: str) -> bool:
    """At least two words, and at least half of them common Spanish words."""
    words = re.findall(r"[a-z]+", fold(text))
    if len(words) < 2:
        return False
    return sum(w in _SPANISH_WORDS for w in words) / len(words) >= 0.5


def interpret_reply(text: str, expecting: str = "") -> ReplyInterpretation:
    """
    Interpret one caller reply. ``expecting`` (``consent``, ``pto_target``,
    ``next``) is only a hint: every field is always computed. With
    ``expecting="pto_target"``, a bare duration ("five days", "40 hours") is
    read as a PTO target.
    """
    t = fold(text)
    intents = detect_intents(text)
    target, unit = _parse_duration(t)
    if target and (not intents or intents == ["pay"] and not _PAY.search(t)):
        # A bare duration is a PTO target, except plain hours with no hint (pay).
        if expecting == "pto_target" or unit != "h":
            intents = ["pto"]
    if t and not intents:
        intent = "ack" if is_acknowledgment(t) else "other"
    else:
        intent = intents[0] if intents else "none"
    spanish_request = bool(_SPANISH_REQUEST.search(t)) and intent != "recap"
    return ReplyInterpretation(
        intent=intent,
        pending_intent=intents[1] if len(intents) > 1 else "",
        intents=",".join(intents),
        consent=detect_consent(text),
        question_topic=detect_question_topic(text),
        target_hours=str(target) if target else "",
        recap_language=detect_recap_language(text),
        wants_spanish=_yes_no(spanish_request or is_mostly_spanish(text)),
        language_name=detect_language_name(text),
        wants_human=_yes_no(_HUMAN.search(t)),
        leave_topic=detect_leave_topic(text),
        expecting=(expecting or "").strip(),
    )


def _yes_no(flag) -> str:
    return "yes" if flag else "no"


def detect_leave_topic(text: str) -> str:
    """
    ``'parental'`` when family/baby words appear in a leave question,
    ``'other'`` for any other leave or benefits question, else ``''``.
    """
    t = fold(text)
    if not _LEAVE.search(t):
        return ""
    return "parental" if _LEAVE_FAMILY.search(t) else "other"
