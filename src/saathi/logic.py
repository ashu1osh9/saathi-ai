import re
import unicodedata
from datetime import datetime, timedelta, timezone

READ_WORDS = ("पढ़", "पढ", "सुनाओ", "read", "sunao", "padho", "padh", "sunao")
MESSAGE_WORDS = ("message", "मैसेज", "संदेश", "msg", "inbox")
SUMMARY_WORDS = ("summary", "summarize", "summarise", "सारांश", "समझाओ", "short", "brief", "samjhao", "saransh")
DRAFT_WORDS = ("लिखो", "likho", "draft", "compose", "type", "लिखना")
REMIND_WORDS = ("remind", "reminder", "याद", "yaad", "याद दिला", "alarm")
HELP_WORDS = ("help", "मदद", "madad", "क्या कर", "what can")


def decide_command(text: str) -> str:
    s = normalize(text)
    if s in {"haan", "han", "ha", "yes", "confirm", "हाँ", "हां", "जी हाँ", "save", "save karo", "पक्का", "कर दो"}:
        return "confirm"
    if s in {"no", "nahi", "nahin", "cancel", "cancel karo", "नहीं", "नही", "रद्द", "रद्द करो", "मत करो"}:
        return "cancel"
    if s in {"stop", "stop speaking", "chup", "रुको", "बंद करो", "चुप"}:
        return "stop"
    if re.match(r"^(?:don't|do not|mat|मत|नहीं)\s", s):
        return "unknown"
    # An authored reply can itself mention a reminder/summary. Parse its prefix first.
    if parse_draft(text)["matched"]:
        return "draft"
    if re.search(r"(?<!\w)(?:mat|मत|nahi|nahin|नहीं|नही|don't|do not)(?!\w)", s):
        return "unknown"
    if contains(s, HELP_WORDS):
        return "help"
    if contains(s, REMIND_WORDS + ("dilana", "दिलाना", "रिमाइंडर")):
        return "reminder"
    if contains(s, SUMMARY_WORDS + ("समरी", "सार", "मतलब", "matalab")):
        return "summary"
    if contains(s, DRAFT_WORDS):
        return "draft"
    if contains(s, MESSAGE_WORDS + ("messages", "मैसेजेस", "संदेशों")) and contains(s, READ_WORDS + ("सुनाओ", "पढ़ो", "पढ़कर", "suno", "padhna")):
        return "read"
    return "unknown"


def extract_draft(text: str) -> str:
    return parse_draft(text)["body"]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold().strip()
    text = re.sub(r"^(?:hey\s+)?(?:saathi|साथी)[,।!\s]+", "", text)
    return re.sub(r"\s+", " ", text).strip(" .,!?:;।\"“”")


def contains(text: str, words: tuple) -> bool:
    # Unicode-aware token boundaries prevent 'type' in 'prototype', 'read' in 'already'.
    return any(re.search(r"(?<!\w)" + re.escape(unicodedata.normalize("NFKC", w).casefold()) + r"(?!\w)", text) for w in words)


def parse_draft(text: str) -> dict:
    s = re.sub(r"^(?:hey\s+)?(?:saathi|साथी)[,।!\s]+", "", text.strip(), flags=re.I)
    recipient = ""
    target = re.match(r"^(.{1,80}?)\s+(?:ko|को)\s+", s, re.I)
    if target:
        recipient, s = target[1].strip(), s[target.end():]
    pattern = (
        r"^(?:(?:एक\s+|a\s+)?(?:मैसेज|message|संदेश|reply|जवाब|उत्तर)\s+"
        # Observed Prisma code-mixed transcript: 'message लाखो, ...' for 'message likho'.
        # Accept only in this explicit drafting prefix; never rewrite authored reply text.
        r"(?:लिखो|लिखना|लिख\s+दो|likho|likh\s+do|draft|compose|बनाओ|लाखो)|"
        r"(?:draft|compose|write|लिखो|likho)\s+(?:(?:a|एक)\s+)?"
        r"(?:reply|message|जवाब|संदेश|मैसेज))\s*[:,-]?\s*"
    )
    match = re.match(pattern, s, re.I)
    body = s[match.end():].strip() if match else ""
    if match and not recipient:
        target = re.match(r"^(?:to|for)\s+([^:,]{1,80})\s*[:,]\s*", body, re.I)
        if target:
            recipient, body = target[1].strip(), body[target.end():].strip()
    return {"matched": bool(match), "recipient": recipient if match else "", "body": body}


NUMBERS = {
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6,
    "सात": 7, "आठ": 8, "नौ": 9, "दस": 10, "ग्यारह": 11, "बारह": 12,
    "पंद्रह": 15, "बीस": 20, "तीस": 30, "साठ": 60,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5,
    "panch": 5, "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    "pandrah": 15, "bees": 20, "tees": 30,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "sixty": 60,
}


def parse_reminder(text: str, now: datetime | None = None, utc_offset_minutes: int = 330) -> dict:
    """Deliberately bounded time grammar. Ambiguous times require an explicit choice."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone(timedelta(minutes=utc_offset_minutes)))
    s = normalize(text)
    for word, number in NUMBERS.items():
        s = re.sub(r"(?<!\w)" + re.escape(word) + r"(?=\s*(?:minutes?|mins?|मिनट|hours?|hrs?|घंटे|घंटा|बजे|baje|am|pm)(?!\w))", str(number), s)
    # Convert Devanagari digits too, so the browser always receives ISO ASCII digits.
    s = "".join(str(unicodedata.digit(c)) if c.isdigit() else c for c in s)
    due = None
    time_spans = []
    relative = re.search(r"(?:(?:in|after)\s+)?(\d+)\s*(minutes?|mins?|मिनट|hours?|hrs?|घंटे|घंटा)(?:\s+(?:में|बाद|baad|mein))?", s)
    if relative:
        amount = int(relative[1])
        if 0 < amount <= 10080:
            due = now + timedelta(**({"hours": amount} if contains(relative[2], ("hour", "hours", "hr", "hrs", "घंटे", "घंटा")) else {"minutes": amount}))
            time_spans = [relative.span()]
    else:
        day = re.search(r"(?<!\w)(today|aaj|आज|tomorrow|kal|कल|\d{4}-\d{2}-\d{2})(?!\w)", s)
        clock = re.search(r"(?<![\w:])(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.|बजे|baje)?(?!\w)", s[day.end():] if day else s)
        period = re.search(r"(?<!\w)(सुबह|subah|morning|शाम|shaam|sham|evening|रात|raat|night|दोपहर|dopahar|afternoon)(?!\w)", s)
        if day and clock:
            hour, minute, suffix = int(clock[1]), int(clock[2] or 0), clock[3] or ""
            meridiem = suffix.replace(".", "") if "m" in suffix else ""
            if period and not meridiem:
                meridiem = "am" if period[1] in {"सुबह", "subah", "morning"} else "pm"
            unambiguous = bool(meridiem or clock[2])
            if minute < 60 and ((meridiem and 1 <= hour <= 12) or (not meridiem and hour <= 23)) and unambiguous:
                if meridiem:
                    hour = hour % 12 + (12 if meridiem == "pm" else 0)
                try:
                    date = datetime.fromisoformat(day[1]).date() if "-" in day[1] else (now + timedelta(days=1 if day[1] in {"tomorrow", "kal", "कल"} else 0)).date()
                    due = datetime.combine(date, datetime.min.time(), tzinfo=now.tzinfo).replace(hour=hour, minute=minute)
                    time_spans = [day.span(), (day.end() + clock.start(), day.end() + clock.end())]
                    if period:
                        time_spans.append(period.span())
                except ValueError:
                    pass
    note = text.strip()
    # Work on normalized text only for reminders; draft content is always preserved above.
    if time_spans:
        note = s
        for start, end in sorted(time_spans, reverse=True):
            note = note[:start] + " " + note[end:]
    note = re.sub(r"(?<!\w)(?:mujhe|मुझे|remind me|reminder|रिमाइंडर|set karo|सेट करो|yaad dilana|yaad dilao|याद दिलाना|याद दिलाओ|याद|दिलाना|दिलाओ)(?!\w)", " ", note, flags=re.I)
    note = re.sub(r"\s+", " ", note).strip(" ,:.-।")
    note = re.sub(r"^(?:at|to|को|ko)\s+", "", note).strip()
    clarification = ""
    if due is None:
        clarification = "समय साफ़ बताइए, जैसे ‘कल शाम 4 बजे’ या ‘5 मिनट बाद’। Choose a date and time in the form."
    elif due <= now:
        due = None
        clarification = "यह समय बीत चुका है। Please choose a future time."
    if not note:
        clarification = "किस बात की याद दिलाऊँ? Please add a reminder note."
    return {"note": note, "due_at": due.isoformat() if due else None, "clarification": clarification}


def digest_message(text: str) -> dict:
    """Explainable extractive digest; not an LLM-generated summary."""
    clean = re.sub(r"\s+", " ", text).strip()
    chunks = [x.strip() for x in re.split(r"(?<=[.!?।])\s+|\n+", text) if x.strip()]
    if not chunks:
        chunks = [clean]
    def score(chunk: str) -> int:
        points = 0
        if re.search(r"\d|₹|rs\.?|rupee|रुपये", chunk, re.I): points += 3
        if re.search(r"कल|आज|बजे|time|today|tomorrow|date|due|meeting|delivery|payment|भुगतान|मुलाकात", chunk, re.I): points += 2
        if re.search(r"please|कृपया|ज़रूर|must|important|urgent|जरूरी|confirm", chunk, re.I): points += 1
        return points
    selected = sorted(range(len(chunks)), key=lambda i: (-score(chunks[i]), i))[:3]
    selected.sort()
    bullets = [chunks[i] if len(chunks[i]) <= 240 else chunks[i][:237].rsplit(" ", 1)[0] + "…" for i in selected]
    warnings = []
    if re.search(r"\b(?:otp|pin|password|cvv)\b|ओटीपी|पासवर्ड", clean, re.I):
        warnings.append("Sensitive code/password mentioned. Do not share a secret without checking who requested it.")
    if re.search(r"https?://|www\.|bit\.ly|tinyurl", clean, re.I):
        warnings.append("This message contains a link. Verify its destination independently before opening it.")
    if re.search(r"\b(?:upi|transfer|payment|pay now)\b|भुगतान|पैसे भेज", clean, re.I):
        warnings.append("Payment-related wording detected. Verify the sender and details independently.")
    return {"bullets": bullets, "warnings": warnings, "method": "extractive"}
