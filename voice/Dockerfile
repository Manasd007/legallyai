# Legally AI Voice — the voice service, deployed SEPARATELY from backend/.
#
# Not on Hugging Face Spaces by default: a call is a long-lived WebRTC session,
# and free tiers that sleep on idle are survivable for an API but fatal
# mid-call. Render / Fly / a small VM are the intended targets. Whichever host
# you pick generally needs a TURN server for NAT traversal.
#
# Required env at runtime (see .env.example):
#   DEEPGRAM_API_KEY, GROQ_API_KEY, RAG_BASE_URL, ALLOWED_ORIGINS

FROM python:3.11-slim

# Silero VAD runs on torch; the CPU wheel avoids ~4 GB of unusable CUDA libs.
# ffmpeg/libsndfile back the MP3→PCM decode on the TTS path.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --user -r requirements.txt

COPY --chown=user server/ ./server/
COPY --chown=user vocab/ ./vocab/

EXPOSE 7860

# One worker, deliberately: sessions and turn telemetry are in-process, and a
# WebRTC connection is pinned to the worker that negotiated it — a second
# worker would answer signalling for calls it doesn't hold.
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "7860"]
