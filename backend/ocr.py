"""OCR for scanned / handwritten / multilingual document uploads.

Two interchangeable backends, selected by config `ocr_backend`:

  * "vision_llm"     (default) — a multimodal LLM (Groq Llama-4-Scout) reads the
                      image directly. Free tier, no extra credentials, and strong
                      on messy handwriting because it uses document context.
  * "google_vision"  — Google Cloud Vision DOCUMENT_TEXT_DETECTION. A dedicated
                      OCR engine with first-class support for 50+ languages incl.
                      Indic scripts (Hindi, Tamil, Bengali, ...). Needs a GCP
                      service-account credential (GOOGLE_APPLICATION_CREDENTIALS).

Either backend can be followed by an optional translate-to-English pass
(`ocr_translate`) so a regional-language or handwritten filing becomes English
text the downstream analysis/reasoning models handle best. Google Vision only
transcribes (it does not translate), so this pass is what makes the
"poor handwriting in a different language" case usable end-to-end.

The public surface is unchanged: doc_extract.py calls ocr_image() / ocr_pdf().
"""
from __future__ import annotations

import base64
import logging

from config import get_settings

log = logging.getLogger("legally.ocr")

OCR_PROMPT = (
    "You are an OCR engine. Transcribe ALL text visible in this image of a document, "
    "exactly as written — including handwriting. Preserve line breaks, headings, "
    "clause/section numbers, and tables (as plain text). Do NOT summarize, translate, "
    "explain, or add anything that is not in the image. Output only the transcribed "
    "text. If a word is genuinely illegible, write [illegible]."
)

TRANSLATE_SYSTEM = (
    "You translate legal documents into English. If the text is already in English, "
    "return it unchanged. Otherwise translate it faithfully into clear English, "
    "preserving legal terms, names, dates, section/clause numbers, and structure. "
    "Do NOT summarize, add commentary, or omit anything. Output only the text."
)


def _data_url(img: bytes, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(img).decode("ascii")


# ── Backend 1: vision LLM (default) ───────────────────────────────────────────
def _llm_image(img: bytes, mime: str) -> str:
    """Transcribe a single image's text via the multimodal model."""
    import litellm

    s = get_settings()
    resp = litellm.completion(
        model=s.vision_model,
        api_key=s.groq_api_key,
        temperature=0,
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": OCR_PROMPT},
                    {"type": "image_url", "image_url": {"url": _data_url(img, mime)}},
                ],
            }
        ],
    )
    return (resp["choices"][0]["message"]["content"] or "").strip()


# ── Backend 2: Google Cloud Vision ────────────────────────────────────────────
def _gcv_image(img: bytes) -> str:
    """Transcribe a single image via Google Cloud Vision DOCUMENT_TEXT_DETECTION.

    Credentials are read by the client library from the GOOGLE_APPLICATION_CREDENTIALS
    env var (a service-account JSON path). Optional language_hints bias recognition
    toward the scripts we expect (e.g. hi, ta, bn) — helps on mixed/regional pages.
    """
    from google.cloud import vision  # google-cloud-vision

    s = get_settings()
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=img)
    ctx = (
        vision.ImageContext(language_hints=s.ocr_language_hints)
        if s.ocr_language_hints
        else None
    )
    resp = client.document_text_detection(image=image, image_context=ctx)
    if resp.error.message:
        # Vision returns errors in-band rather than raising.
        raise RuntimeError(f"Google Vision error: {resp.error.message}")
    return (resp.full_text_annotation.text or "").strip()


# ── Optional translate-to-English pass ────────────────────────────────────────
def _translate_to_english(text: str) -> str:
    """Translate non-English OCR output to English via the configured LLM.

    Best-effort: on any LLM failure we keep the original transcription rather than
    losing the document. Uses llm.complete() so it inherits the provider fallback.
    """
    if not text.strip():
        return text
    from llm import complete

    s = get_settings()
    try:
        out = complete(
            model=s.ocr_translate_model,
            system=TRANSLATE_SYSTEM,
            user=text,
            temperature=0,
            max_tokens=4000,
        )
        return (out or "").strip() or text
    except Exception as e:  # noqa: BLE001 - translation is a nicety, never fatal
        log.warning("OCR translate step failed, keeping original text: %s", e)
        return text


# ── Public API (unchanged signatures) ─────────────────────────────────────────
def ocr_image(img: bytes, mime: str = "image/png") -> str:
    """Transcribe a single image's text using the configured OCR backend."""
    s = get_settings()
    if s.ocr_backend == "google_vision":
        text = _gcv_image(img)
    else:
        text = _llm_image(img, mime)
    if s.ocr_translate:
        text = _translate_to_english(text)
    return text


def ocr_pdf(data: bytes) -> str:
    """Render each PDF page to an image and OCR it (up to ocr_max_pages).

    The translate pass runs once over the whole document rather than per page, so
    cross-page context is preserved and we make fewer LLM calls.
    """
    import fitz  # PyMuPDF

    s = get_settings()
    out: list[str] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        n = min(len(doc), s.ocr_max_pages)
        for i in range(n):
            pix = doc[i].get_pixmap(dpi=200)
            png = pix.tobytes("png")
            try:
                # Transcribe only here; defer translation to one pass below.
                if s.ocr_backend == "google_vision":
                    page_text = _gcv_image(png)
                else:
                    page_text = _llm_image(png, "image/png")
            except Exception as e:  # noqa: BLE001 - skip a bad page, keep the rest
                log.warning("OCR failed on page %d: %s", i + 1, e)
                continue
            if page_text:
                out.append(page_text)

    text = "\n\n".join(out).strip()
    if s.ocr_translate:
        text = _translate_to_english(text)
    return text
