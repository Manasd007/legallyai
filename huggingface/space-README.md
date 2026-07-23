---
title: Legally AI API
emoji: ⚖️
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# Legally AI — backend API

FastAPI backend for [Legally AI](https://github.com/Manasd007/legally-ai): precedent-grounded
Indian legal judgment prediction with verified citations.

On startup the app downloads its artifacts from the Hub (pinned revisions):
[corpus index](https://huggingface.co/datasets/ManasDubey/legally-ai-corpus-index) ·
[classifier](https://huggingface.co/ManasDubey/legally-ai-predex-classifier).

Required Space secrets: `GROQ_API_KEY`, `HF_NAMESPACE`, `SUPABASE_URL`,
`SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_JWT_SECRET`.
Recommended vars: `REASONING_MODEL=groq/llama-3.3-70b-versatile`,
`CORPUS_REVISION=v1`, `CLASSIFIER_REVISION=v1`.
