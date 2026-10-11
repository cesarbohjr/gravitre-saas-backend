"""Deterministic spoken formatting and abbreviation-aware sentence cuts for TTS.

Two jobs, both pure string work with no I/O:

1. **Sentence cuts** (``split_sentence_chunks``). Streamed answer text is cut
   into sentences before it reaches TTS. A period is not always a sentence
   end: "e.g.", "Dr.", "U.S.", initials ("J. Smith"), decimals ("3.5"), times
   ("10.30"), version numbers, domains and e-mail addresses all carry one.
   Cutting there splits one thought into two TTS requests and breaks prosody.

2. **Spoken formatting** (``format_for_speech``). ElevenLabs Flash reads raw
   symbols poorly ("$1,250.50", "2026-10-11", "14:30", UUIDs, URLs), so the
   spoken copy of each sentence is rewritten into words. Only the spoken copy:
   the client keeps the displayed text, and history stores the displayed text.

The rewrites never guess. An ambiguous date ("03/04/2026") is read literally,
amounts keep every digit, a UUID is never read in full, and nothing that is
not in the text is invented.

Alignment. Playback accounting maps the words the TTS spoke back to the
displayed draft. ``spoken_alignment_tokens`` gives the draft's word tokens in
their spoken form, each tied to a character offset in the displayed text: the
words of one rewrite all point at its start except the last, which points at
its end, so an amount or date counts as heard only once all of it was spoken.
"""
from __future__ import annotations

import calendar
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

# Same word tokens as voice_reply_playback / voice_conversational_polish.
_WORD_RE = re.compile(r"[\w'’-]+")

# ---------------------------------------------------------------------------
# Sentence cuts
# ---------------------------------------------------------------------------

# Never a sentence end: always followed by more of the same sentence.
_NEVER_ENDS = frozenset(
    {
        "e.g.",
        "i.e.",
        "eg.",
        "ie.",
        "dr.",
        "mr.",
        "mrs.",
        "ms.",
        "mx.",
        "prof.",
        "vs.",
        "approx.",
        "cf.",
        "viz.",
        "fig.",
        "sr.",
        "jr.",
        "st.",
        "mt.",
        "no.",
        "nos.",
        "ext.",
        "dept.",
        "est.",
    }
)
# Mid-sentence usually, but can end one ("... pears, etc. Then"): a sentence
# end only when the next word starts with a capital letter.
_AMBIGUOUS_ENDS = frozenset({"etc.", "inc.", "ltd.", "co.", "corp.", "a.m.", "p.m.", "am.", "pm."})
_INITIALISM = re.compile(r"(?:[A-Za-z]\.){2,}")
_INITIAL = re.compile(r"[A-Za-z]\.")
_LEADING_OPENERS = "([{\"'“‘"
_BOUNDARY_SPACE = re.compile(r"(?<=[.!?])\s+")
# "No." opens a sentence as often as it abbreviates "number": only a number
# after it makes it an abbreviation.
_NUMBER_ONLY_ABBREVIATIONS = frozenset({"no.", "nos."})


def _last_token(text: str) -> str:
    idx = max(text.rfind(" "), text.rfind("\n"), text.rfind("\t"))
    return text[idx + 1 :].lstrip(_LEADING_OPENERS)


def period_ends_sentence(token: str, next_char: str | None) -> bool:
    """Whether the period closing ``token`` ends its sentence.

    ``next_char`` is the first character after the whitespace that follows the
    period, or ``None`` when nothing has arrived yet (then an ambiguous period
    waits for more text).
    """
    low = token.lower()
    if low in _NUMBER_ONLY_ABBREVIATIONS:
        return not (next_char is not None and next_char.isdigit())
    if low in _NEVER_ENDS:
        return False
    if _INITIAL.fullmatch(token):
        return False
    if low in _AMBIGUOUS_ENDS or _INITIALISM.fullmatch(token):
        return next_char is not None and next_char.isupper()
    return True


def trailing_period_ends_sentence(text: str) -> bool:
    """Whether ``text`` (ending in ".", nothing after it yet) is a complete sentence.

    The fast path that sends a sentence as soon as its period arrives. Anything
    that may continue past the period waits for the next delta instead: a digit
    before it ("3." of "3.5", "10." of "10.30", "2.1." of a version), an address
    ("bob@acme." or "acme." of "acme.com"), or an abbreviation.
    """
    stripped = text.rstrip()
    if not stripped.endswith("."):
        return False
    token = _last_token(stripped)
    if len(token) < 2:
        return False
    before = token[-2]
    if before.isdigit():
        return False
    if "@" in token or "/" in token or token.lower().startswith("www"):
        return False
    if "." in token[:-1].rstrip(".") and not token.endswith(".."):
        # "acme.com." / "v2.1." / "U.S." : may still be growing.
        return False
    return period_ends_sentence(token, None)


def sentence_cut_points(buffer: str) -> list[tuple[int, int]]:
    """(end of sentence, start of next) for every real sentence boundary in ``buffer``."""
    cuts: list[tuple[int, int]] = []
    for match in _BOUNDARY_SPACE.finditer(buffer):
        end = match.start()
        if buffer[end - 1] in "!?":
            cuts.append((end, match.end()))
            continue
        token = _last_token(buffer[:end])
        next_char = buffer[match.end()] if match.end() < len(buffer) else None
        if period_ends_sentence(token, next_char):
            cuts.append((end, match.end()))
    return cuts


def split_sentence_chunks(buffer: str) -> tuple[list[str], str] | None:
    """Complete sentences at the start of ``buffer`` and the rest, or ``None``.

    ``None`` means no complete sentence yet (the caller may still apply its own
    long-buffer fallback).
    """
    cuts = sentence_cut_points(buffer)
    if cuts:
        ready: list[str] = []
        start = 0
        for end, nxt in cuts:
            piece = buffer[start:end].strip()
            if piece:
                ready.append(piece)
            start = nxt
        return ready, buffer[start:]
    stripped = buffer.rstrip()
    if len(stripped) >= 2 and (stripped[-1] in "!?" or trailing_period_ends_sentence(stripped)):
        return [stripped], ""
    return None


# ---------------------------------------------------------------------------
# Spoken formatting
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpokenRewrite:
    start: int
    end: int
    spoken: str


_MONTHS = [calendar.month_name[i] for i in range(1, 13)]
_MONTH_LOOKUP: dict[str, int] = {}
for _i, _name in enumerate(_MONTHS, start=1):
    _MONTH_LOOKUP[_name.lower()] = _i
    _MONTH_LOOKUP[_name[:3].lower()] = _i
_MONTH_LOOKUP["sept"] = 9

_DIGIT_NAMES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]

_CURRENCY_WORDS = {
    "$": ("dollar", "dollars", "cent", "cents"),
    "€": ("euro", "euros", "cent", "cents"),
    "£": ("pound", "pounds", "penny", "pence"),
}
_MAGNITUDES = {
    "k": "thousand",
    "m": "million",
    "mm": "million",
    "b": "billion",
    "bn": "billion",
    "t": "trillion",
    "thousand": "thousand",
    "million": "million",
    "billion": "billion",
    "trillion": "trillion",
}


def ordinal(day: int) -> str:
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def _spell(chars: str) -> str:
    return " ".join(ch.upper() if ch.isalpha() else ch for ch in chars)


def _digit_groups(digits: str) -> str:
    """Digits read one by one, in groups: "48213" -> "4 8 2, 1 3"."""
    if len(digits) <= 4:
        return " ".join(digits)
    groups = [digits[i : i + 3] for i in range(0, len(digits), 3)]
    return ", ".join(" ".join(g) for g in groups)


def _dotted(host: str) -> str:
    return " dot ".join(part for part in host.split(".") if part)


# Shared numeric pieces.
_NUM = r"\d{1,3}(?:,\d{3})+|\d+"
_MAG_SUFFIX = r"(?:(?P<{p}magc>[kKmMbBtT]|bn|BN|MM|mm)(?![\w])|\s(?P<{p}magw>thousand|million|billion|trillion)\b)"


def _amount_pattern(prefix: str) -> str:
    return (
        rf"(?P<{prefix}cur>[$€£])?\s?(?P<{prefix}int>{_NUM})(?:\.(?P<{prefix}dec>\d+))?"
        rf"{_MAG_SUFFIX.format(p=prefix)}?(?P<{prefix}pct>\s?%)?"
    )


@dataclass
class _Amount:
    cur: str | None
    int_part: str
    dec: str | None
    mag: str | None
    pct: bool

    @classmethod
    def from_match(cls, m: re.Match[str], prefix: str = "") -> _Amount:
        mag_raw = m.group(f"{prefix}magc") or m.group(f"{prefix}magw")
        return cls(
            cur=m.group(f"{prefix}cur"),
            int_part=m.group(f"{prefix}int"),
            dec=m.group(f"{prefix}dec"),
            mag=_MAGNITUDES.get(mag_raw.lower()) if mag_raw else None,
            pct=bool(m.group(f"{prefix}pct")),
        )

    def value(self) -> float:
        base = float(self.int_part.replace(",", "") + (f".{self.dec}" if self.dec else ""))
        scale = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}.get(self.mag or "", 1.0)
        return base * scale

    def number_words(self) -> str:
        """The number as written, with its magnitude spelled out ("2.5 million")."""
        text = self.int_part + (f".{self.dec}" if self.dec else "")
        return f"{text} {self.mag}" if self.mag else text

    def has_cents(self) -> bool:
        return bool(self.cur and self.dec and not self.mag)


def _render_money(amount: _Amount) -> str | None:
    cur = amount.cur or "$"
    one, many, minor_one, minor_many = _CURRENCY_WORDS[cur]
    if amount.mag:
        return f"{amount.number_words()} {many}"
    major = f"{amount.int_part} {one if amount.int_part == '1' else many}"
    if not amount.dec:
        return major
    if len(amount.dec) > 2:
        # Fractions of a cent are read as written: never rounded.
        return f"{amount.int_part}.{amount.dec} {many}"
    cents = int(amount.dec.ljust(2, "0"))
    if cents == 0:
        return major
    minor = f"{cents} {minor_one if cents == 1 else minor_many}"
    if amount.int_part.replace(",", "").strip("0") == "":
        return minor
    return f"{major} and {minor}"


def _render_amount(amount: _Amount) -> str | None:
    if amount.cur and amount.pct:
        return None
    if amount.cur:
        return _render_money(amount)
    if amount.pct:
        return f"{amount.number_words()} percent"
    return None


# --- rules ---------------------------------------------------------------------

_TRAILING_URL_PUNCT = ".,;:!?)]}'\""

_URL = re.compile(r"\b(?:https?://|www\.)[^\s<>()\[\]{}\"']+", re.IGNORECASE)
_EMAIL = re.compile(
    r"(?<![\w.+-])(?P<local>[A-Za-z0-9][A-Za-z0-9._%+-]*)@(?P<domain>[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})(?![\w-])"
)
_BARE_DOMAIN = re.compile(
    r"(?<![\w@./-])(?P<host>(?:[A-Za-z0-9-]+\.)+(?:com|org|net|io|ai|co|dev|app|edu|gov|us|uk|de|ca|au|info|biz))"
    r"(?P<path>/[^\s]*)?(?![\w-])",
    re.IGNORECASE,
)
_UUID = re.compile(
    r"(?:(?<![\w-])(?P<label>IDs?|Ids?|ids?)[:#]?\s+)?"
    r"(?<![\w-])(?P<id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{16,})(?![\w-])"
)
_ISO_DATE = re.compile(
    r"(?<![\w/.-])(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})"
    r"(?:T(?P<h>\d{2}):(?P<mi>\d{2})(?::(?P<s>00))?(?P<z>Z)?)?(?![\w:+/-]|\.\d)"
)
_SLASH_DATE = re.compile(r"(?<![\w/.-])(?P<a>\d{1,2})/(?P<b>\d{1,2})/(?P<y>\d{4}|\d{2})(?![\w/-]|[.,]\d)")
_PHONE = re.compile(
    r"(?<![\w+(])(?P<phone>(?:\+?1[\s.-])?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}"
    r"|\+\d{1,3}(?:[\s.-]\d{1,4}){2,5})(?![\w-]|[.,]\d)"
)
_TICKET = re.compile(
    r"(?<![\w-])(?P<ticket>(?:[A-Z]{2,6}-)+(?:\d+-)*\d{3,})(?![\w-])"
    r"|(?<![\w&#])#(?P<number>\d{3,})(?![\w-])"
)
_TIME_AMPM = re.compile(
    r"(?<![\w:.$€£])(?P<h>\d{1,2})(?::(?P<m>[0-5]\d))?\s?(?P<ap>[aApP])\.?[mM](?P<dot>\.(?=\s+[a-z,;]|[,;]))?(?![\w])"
)
_TIME_24 = re.compile(r"(?<![\w:.$€£/])(?P<h>\d{1,2}):(?P<m>[0-5]\d)(?![\d:]|\s?[aApP]\.?[mM](?![\w]))")
_RANGE = re.compile(
    rf"(?<![\w.,/$€£-]){_amount_pattern('l')}\s?[-–—]\s?{_amount_pattern('r')}(?![\w/-]|[.,]\d)"
)
_MONEY = re.compile(
    rf"(?<![\w.,])(?P<cur>[$€£])\s?(?P<int>{_NUM})(?:\.(?P<dec>\d+))?{_MAG_SUFFIX.format(p='')}?(?P<pct>)(?![\d,]\d|\.\d)"
)
_PERCENT = re.compile(rf"(?<![\w.,])(?P<cur>)(?P<int>{_NUM})(?:\.(?P<dec>\d+))?(?P<magc>)(?P<magw>)(?P<pct>\s?%)")
_MONTH_DATE = re.compile(
    r"\b(?P<mon>January|February|March|April|May|June|July|August|September|October|November|December"
    r"|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(?P<d>\d{1,2})(?:st|nd|rd|th)?"
    r"(?:,?\s+(?P<y>\d{4}))?(?![\w:%]|[.,]\d)"
)


def _strip_trailing(m: re.Match[str], group: int | str = 0) -> tuple[int, str]:
    text = m.group(group)
    trimmed = text.rstrip(_TRAILING_URL_PUNCT)
    return m.start(group) + len(trimmed), trimmed


def _rule_url(text: str) -> list[SpokenRewrite]:
    out: list[SpokenRewrite] = []
    for m in _URL.finditer(text):
        end, raw = _strip_trailing(m)
        host = re.sub(r"^(?:https?://)?", "", raw, flags=re.IGNORECASE).split("/", 1)[0]
        host = host.split("?", 1)[0].split("#", 1)[0].split(":", 1)[0]
        if host.lower().startswith("www."):
            host = host[4:]
        if not host or "." not in host:
            continue
        out.append(SpokenRewrite(m.start(), end, _dotted(host)))
    return out


def _rule_email(text: str) -> list[SpokenRewrite]:
    out: list[SpokenRewrite] = []
    for m in _EMAIL.finditer(text):
        local = m.group("local").rstrip(".")
        spoken_local = (
            local.replace(".", " dot ").replace("_", " underscore ").replace("-", " dash ").replace("+", " plus ")
        )
        spoken = f"{' '.join(spoken_local.split())} at {_dotted(m.group('domain'))}"
        out.append(SpokenRewrite(m.start(), m.end(), spoken))
    return out


def _rule_bare_domain(text: str) -> list[SpokenRewrite]:
    out: list[SpokenRewrite] = []
    for m in _BARE_DOMAIN.finditer(text):
        end = m.end("host")
        if m.group("path"):
            end, _ = _strip_trailing(m)
            end = max(end, m.end("host"))
        out.append(SpokenRewrite(m.start(), end, _dotted(m.group("host"))))
    return out


def _rule_uuid(text: str) -> list[SpokenRewrite]:
    out: list[SpokenRewrite] = []
    for m in _UUID.finditer(text):
        ident = m.group("id").replace("-", "")
        out.append(SpokenRewrite(m.start(), m.end(), f"ID ending in {_spell(ident[-4:].lower())}"))
    return out


def _clock(hour: int, minute: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    h12 = hour % 12 or 12
    return f"{h12} {suffix}" if minute == 0 else f"{h12}:{minute:02d} {suffix}"


def _rule_iso_date(text: str) -> list[SpokenRewrite]:
    out: list[SpokenRewrite] = []
    for m in _ISO_DATE.finditer(text):
        try:
            when = date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
        except ValueError:
            continue
        spoken = f"{_MONTHS[when.month - 1]} {ordinal(when.day)}, {when.year}"
        if m.group("h") is not None:
            hour, minute = int(m.group("h")), int(m.group("mi"))
            if hour > 23:
                continue
            spoken += f" at {_clock(hour, minute)}"
            if m.group("z"):
                spoken += " UTC"
        out.append(SpokenRewrite(m.start(), m.end(), spoken))
    return out


def _literal_date_part(part: str) -> str:
    # "03" -> "zero three": read as written, not as a guessed month or day.
    if len(part) > 1 and part.startswith("0"):
        return " ".join(_DIGIT_NAMES[int(ch)] for ch in part)
    return part


def _rule_slash_date(text: str) -> list[SpokenRewrite]:
    out: list[SpokenRewrite] = []
    for m in _SLASH_DATE.finditer(text):
        a, b, y = int(m.group("a")), int(m.group("b")), m.group("y")
        month_day: tuple[int, int] | None = None
        if len(y) == 4:
            if 1 <= a <= 12 and (a == b or b > 12):
                month_day = (a, b)
            elif 1 <= b <= 12 < a:
                month_day = (b, a)
        if month_day is not None:
            try:
                when = date(int(y), month_day[0], month_day[1])
            except ValueError:
                month_day = None
            else:
                spoken = f"{_MONTHS[when.month - 1]} {ordinal(when.day)}, {when.year}"
        if month_day is None:
            # Ambiguous (or not a valid date): read literally, never guess.
            spoken = " slash ".join(
                _literal_date_part(p) for p in (m.group("a"), m.group("b"), m.group("y"))
            )
        out.append(SpokenRewrite(m.start(), m.end(), spoken))
    return out


def _rule_phone(text: str) -> list[SpokenRewrite]:
    out: list[SpokenRewrite] = []
    for m in _PHONE.finditer(text):
        raw = m.group("phone")
        digits = re.sub(r"\D", "", raw)
        if not 7 <= len(digits) <= 15:
            continue
        groups = [g for g in re.split(r"[\s.()\-]+", raw.lstrip("+")) if g]
        spoken = ", ".join(" ".join(g) for g in groups)
        if raw.startswith("+"):
            spoken = f"plus {spoken}"
        out.append(SpokenRewrite(m.start(), m.end(), spoken))
    return out


def _rule_ticket(text: str) -> list[SpokenRewrite]:
    out: list[SpokenRewrite] = []
    for m in _TICKET.finditer(text):
        if m.group("number"):
            spoken = f"number {_digit_groups(m.group('number'))}"
        else:
            parts = m.group("ticket").split("-")
            spoken = ", ".join(_spell(p) if p.isalpha() else _digit_groups(p) for p in parts)
        out.append(SpokenRewrite(m.start(), m.end(), spoken))
    return out


def _rule_time_ampm(text: str) -> list[SpokenRewrite]:
    out: list[SpokenRewrite] = []
    for m in _TIME_AMPM.finditer(text):
        hour = int(m.group("h"))
        if not 1 <= hour <= 12:
            continue
        minute = int(m.group("m") or 0)
        suffix = "AM" if m.group("ap").lower() == "a" else "PM"
        spoken = f"{hour} {suffix}" if minute == 0 and not m.group("m") else f"{hour}:{minute:02d} {suffix}"
        out.append(SpokenRewrite(m.start(), m.end(), spoken))
    return out


def _rule_time_24(text: str) -> list[SpokenRewrite]:
    out: list[SpokenRewrite] = []
    for m in _TIME_24.finditer(text):
        raw_h = m.group("h")
        hour, minute = int(raw_h), int(m.group("m"))
        if hour > 23:
            continue
        # 1:00-11:59 without a leading zero could be morning or evening: as written.
        if 1 <= hour <= 11 and not raw_h.startswith("0"):
            continue
        out.append(SpokenRewrite(m.start(), m.end(), _clock(hour, minute)))
    return out


def _rule_range(text: str) -> list[SpokenRewrite]:
    out: list[SpokenRewrite] = []
    for m in _RANGE.finditer(text):
        left, right = _Amount.from_match(m, "l"), _Amount.from_match(m, "r")
        if left.int_part.startswith("0") and len(left.int_part) > 1:
            continue
        if left.cur and right.cur and left.cur != right.cur:
            continue
        cur = left.cur or right.cur
        pct = left.pct or right.pct
        if cur and pct:
            continue
        if left.pct and not right.pct:
            continue
        # A right side with a magnitude ("$2-3M") scales the left side too.
        if right.mag and not left.mag:
            left.mag = right.mag
        if left.value() >= right.value():
            continue  # "3-2" is a score, "2024-25" a season: not a range.
        left.cur = right.cur = cur
        left.pct = right.pct = pct
        if cur:
            if left.has_cents() or right.has_cents():
                lt, rt = _render_money(left), _render_money(right)
                if not lt or not rt:
                    continue
                spoken = f"{lt} to {rt}"
            else:
                many = _CURRENCY_WORDS[cur][1]
                spoken = f"{left.number_words()} to {right.number_words()} {many}"
        elif pct:
            spoken = f"{left.number_words()} to {right.number_words()} percent"
        else:
            spoken = f"{left.number_words()} to {right.number_words()}"
        out.append(SpokenRewrite(m.start(), m.end(), spoken))
    return out


def _rule_amount(pattern: re.Pattern[str]) -> Callable[[str], list[SpokenRewrite]]:
    def rule(text: str) -> list[SpokenRewrite]:
        out: list[SpokenRewrite] = []
        for m in pattern.finditer(text):
            spoken = _render_amount(_Amount.from_match(m))
            if spoken:
                out.append(SpokenRewrite(m.start(), m.end(), spoken))
        return out

    return rule


def _rule_month_date(text: str) -> list[SpokenRewrite]:
    out: list[SpokenRewrite] = []
    for m in _MONTH_DATE.finditer(text):
        month = _MONTH_LOOKUP[m.group("mon").lower()]
        day = int(m.group("d"))
        year = m.group("y")
        try:
            date(int(year) if year else 2024, month, day)  # 2024: a leap year, so Feb 29 stays valid
        except ValueError:
            continue
        spoken = f"{_MONTHS[month - 1]} {ordinal(day)}"
        if year:
            spoken += f", {year}"
        out.append(SpokenRewrite(m.start(), m.end(), spoken))
    return out


# Priority order: an earlier rule claims its text first.
_RULES: tuple[Callable[[str], list[SpokenRewrite]], ...] = (
    _rule_url,
    _rule_email,
    _rule_bare_domain,
    _rule_uuid,
    _rule_iso_date,
    _rule_slash_date,
    _rule_phone,
    _rule_ticket,
    _rule_time_ampm,
    _rule_time_24,
    _rule_range,
    _rule_amount(_MONEY),
    _rule_amount(_PERCENT),
    _rule_month_date,
)


def spoken_rewrites(text: str) -> list[SpokenRewrite]:
    """Non-overlapping rewrites of ``text`` in order, highest-priority rule first."""
    if not text or not any(ch.isdigit() or ch in "@$€£%#./" for ch in text):
        return []
    taken: list[SpokenRewrite] = []
    for rule in _RULES:
        for rw in rule(text):
            if rw.end <= rw.start or rw.spoken == text[rw.start : rw.end]:
                continue
            if any(rw.start < t.end and t.start < rw.end for t in taken):
                continue
            taken.append(rw)
    return sorted(taken, key=lambda r: r.start)


def format_for_speech(text: str) -> str:
    """``text`` with numbers, dates, times, ids and addresses written as they are said."""
    rewrites = spoken_rewrites(text)
    if not rewrites:
        return text
    pieces: list[str] = []
    cursor = 0
    for rw in rewrites:
        pieces.append(text[cursor : rw.start])
        pieces.append(rw.spoken)
        cursor = rw.end
    pieces.append(text[cursor:])
    return "".join(pieces)


def to_spoken_form(text: str, custom_aliases_json: str | None = None) -> str:
    """Spoken formatting, then spoken aliases: the last step before TTS."""
    from app.services.pipecat_voice.spoken_pronunciations import apply_spoken_aliases

    return apply_spoken_aliases(format_for_speech(text), custom_aliases_json)


def spoken_alignment_tokens(text: str) -> list[tuple[str, int]]:
    """Word tokens of ``text`` as they are spoken, each with its displayed char end.

    Outside a rewrite this is the plain word list. Inside one, every spoken
    word maps to the rewrite's start except the last, which maps to its end:
    "$1,250.50" counts as heard only once "cents" was spoken.
    """
    tokens: list[tuple[str, int]] = []
    cursor = 0

    def _plain(segment_start: int, segment_end: int) -> None:
        for m in _WORD_RE.finditer(text, segment_start, segment_end):
            tokens.append((m.group(0).casefold(), m.end()))

    for rw in spoken_rewrites(text):
        _plain(cursor, rw.start)
        words = [w.casefold() for w in _WORD_RE.findall(rw.spoken)]
        for idx, word in enumerate(words):
            tokens.append((word, rw.end if idx == len(words) - 1 else rw.start))
        cursor = rw.end
    _plain(cursor, len(text))
    return tokens


__all__ = [
    "SpokenRewrite",
    "format_for_speech",
    "ordinal",
    "period_ends_sentence",
    "sentence_cut_points",
    "split_sentence_chunks",
    "spoken_alignment_tokens",
    "spoken_rewrites",
    "to_spoken_form",
    "trailing_period_ends_sentence",
]
