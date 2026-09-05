from __future__ import annotations

from dataclasses import dataclass

_FALLBACK_VOICE = "hi-IN-SwaraNeural"


@dataclass(frozen=True)
class LangProfile:
    code: str
    name: str
    voice: str
    acks: tuple[str, ...]
    recovery: dict[str, str]
    greeting: str


_BRAND = "Legally AI"


_HI_ACKS = (
    "Achha, samajh gaya. Ek second, dekhta hoon.",
    "Theek hai, main check karta hoon.",
    "Hmm, iske baare mein dekhta hoon, ek moment.",
    "Ek minute, Supreme Court ke judgments dekh leta hoon.",
    "Achha, yeh dekhna padega, ek second.",
    "Ruko zara, case law check karta hoon.",
    "Haan, iska jawaab judgments mein hoga — ek second.",
)
_HI_RECOVERY = {
    "stt_empty": "Sorry, aapki baat clear nahi aayi. Thoda phir se boliye?",
    "llm_error": "Sorry, thodi technical dikkat ho gayi. Ek baar phir se try karein?",
    "tool_timeout": "Case database se abhi jawaab nahi mila. Main dobara try karun?",
}

_EN_ACKS = (
    "Right, I see. One second, let me check.",
    "Okay, let me look that up.",
    "Hmm, let me check the case law on that.",
    "Give me a moment, I'll look through the Supreme Court judgments.",
    "Sure — one second while I check.",
    "Let me pull up the relevant cases.",
    "Good question. The judgments will have this — one moment.",
)
_EN_RECOVERY = {
    "stt_empty": "Sorry, I didn't catch that clearly. Could you say it again?",
    "llm_error": "Sorry, I hit a technical problem there. Shall we try once more?",
    "tool_timeout": "I couldn't reach the case database just then. Want me to try again?",
}

_EN_GREETING = f"Hi, this is {_BRAND}. What's the legal issue you're dealing with?"
_HI_GREETING = f"Namaste, main {_BRAND} hoon. Apna legal sawaal poochhiye."

_PROFILES: dict[str, LangProfile] = {
    "en": LangProfile("en", "English", "en-IN-NeerjaNeural", _EN_ACKS, _EN_RECOVERY, _EN_GREETING),
    "hi": LangProfile("hi", "Hindi/Hinglish", "hi-IN-SwaraNeural", _HI_ACKS, _HI_RECOVERY, _HI_GREETING),
    "bn": LangProfile("bn", "Bengali", "bn-IN-TanishaaNeural", _EN_ACKS, _EN_RECOVERY, _EN_GREETING),
    "ta": LangProfile("ta", "Tamil", "ta-IN-PallaviNeural", _EN_ACKS, _EN_RECOVERY, _EN_GREETING),
    "te": LangProfile("te", "Telugu", "te-IN-ShrutiNeural", _EN_ACKS, _EN_RECOVERY, _EN_GREETING),
    "mr": LangProfile("mr", "Marathi", "mr-IN-AarohiNeural", _EN_ACKS, _EN_RECOVERY, _EN_GREETING),
    "gu": LangProfile("gu", "Gujarati", "gu-IN-DhwaniNeural", _EN_ACKS, _EN_RECOVERY, _EN_GREETING),
    "kn": LangProfile("kn", "Kannada", "kn-IN-SapnaNeural", _EN_ACKS, _EN_RECOVERY, _EN_GREETING),
    "ml": LangProfile("ml", "Malayalam", "ml-IN-SobhanaNeural", _EN_ACKS, _EN_RECOVERY, _EN_GREETING),
    "ur": LangProfile("ur", "Urdu", "ur-IN-GulNeural", _EN_ACKS, _EN_RECOVERY, _EN_GREETING),
    "pa": LangProfile("pa", "Punjabi", _FALLBACK_VOICE, _HI_ACKS, _HI_RECOVERY, _HI_GREETING),
    "or": LangProfile("or", "Odia", _FALLBACK_VOICE, _HI_ACKS, _HI_RECOVERY, _HI_GREETING),
    "as": LangProfile("as", "Assamese", _FALLBACK_VOICE, _HI_ACKS, _HI_RECOVERY, _HI_GREETING),
}

DEFAULT_CODE = "en"


def normalize(language: object) -> str | None:
    if language is None:
        return None
    raw = getattr(language, "value", language)
    code = str(raw).strip().lower().replace("_", "-")
    if not code:
        return None
    base = code.split("-")[0]
    return base if base in _PROFILES else None


def profile_for(code: str | None) -> LangProfile:
    return _PROFILES.get(code or "", _PROFILES[DEFAULT_CODE])
