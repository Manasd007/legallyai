"""Per-language voice, filler and recovery lines.

The agent must answer in the language the caller actually used. Three separate
channels have to agree on that, and only one of them is the LLM:

  * the LLM's reply       — steered by the LANGUAGE rules in the system prompt
  * the TTS voice         — a Hindi voice reading Tamil is unintelligible
  * the spoken ack/errors — pushed straight to TTS by the pipeline, never
                            passing through the LLM at all

That last one is why a caller speaking English used to hear "Achha, samajh
gaya..." mid-call no matter what the model wrote: the filler is hardcoded, not
generated. Everything language-dependent therefore lives here.

Language comes from Deepgram (`TranscriptionFrame.language`) rather than from
guessing at the words, which is the only reliable signal for romanized Hinglish
— it is Latin script, so script detection cannot tell it from English.
"""
from __future__ import annotations

from dataclasses import dataclass

# Edge TTS voices, verified against `edge_tts.list_voices()`. Female voices
# chosen throughout for consistency with the original hi-IN-SwaraNeural.
# Punjabi and Odia/Assamese have no Edge neural voice at all — they fall back
# to Hindi, which is wrong but intelligible, rather than to silence.
_FALLBACK_VOICE = "hi-IN-SwaraNeural"


@dataclass(frozen=True)
class LangProfile:
    code: str
    name: str  # as written into the system prompt
    voice: str
    acks: tuple[str, ...]
    recovery: dict[str, str]
    # Spoken the moment the connection opens, before anything has been heard.
    greeting: str


# The product is "Legally AI" in speech too. Written without punctuation between
# the letters — Edge neural voices read "AI" as the two letters, whereas "A.I."
# invites reading the full stops aloud.
_BRAND = "Legally AI"


# Hindi/Hinglish: the original lines. A Hinglish speaker gets these because
# Deepgram reports romanized Hindi as `hi`.
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

# For languages where authoring idiomatic filler isn't something we can verify,
# the ack falls back to English rather than to invented phrasing — the caller
# still hears speech instead of dead air, and the LLM's actual answer comes
# back in their language. Only the voice is language-specific here.
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
    # No Edge neural voice exists for these; Hindi is the least-bad stand-in.
    "pa": LangProfile("pa", "Punjabi", _FALLBACK_VOICE, _HI_ACKS, _HI_RECOVERY, _HI_GREETING),
    "or": LangProfile("or", "Odia", _FALLBACK_VOICE, _HI_ACKS, _HI_RECOVERY, _HI_GREETING),
    "as": LangProfile("as", "Assamese", _FALLBACK_VOICE, _HI_ACKS, _HI_RECOVERY, _HI_GREETING),
}

# English until the caller says something. Nothing has been heard when the
# greeting plays, so this is a guess either way — and English is the one that
# reads as neutral to a Hindi speaker, where the reverse does not hold. The
# first detected utterance switches immediately (see SessionHub).
DEFAULT_CODE = "en"


def normalize(language: object) -> str | None:
    """Reduce a pipecat `Language`, enum value or raw string to a base code.

    Deepgram reports regional variants (`en-IN`, `hi-IN`); the profile table is
    keyed on the base language, since the voice choice doesn't vary by region.
    Returns None for anything unrecognised so callers can keep what they had —
    a spurious switch mid-call is worse than a stale one.
    """
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
