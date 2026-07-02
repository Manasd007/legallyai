---
license: apache-2.0
base_model: law-ai/InLegalBERT
language:
  - en
library_name: transformers
pipeline_tag: text-classification
tags:
  - legal
  - indian-law
  - judgment-prediction
  - legal-nlp
  - inlegalbert
metrics:
  - f1
  - accuracy
model-index:
  - name: legally-ai-predex-classifier
    results:
      - task:
          type: text-classification
          name: Legal Judgment Prediction (applicant win / lose)
        dataset:
          name: PredEx (held-out test split)
          type: predex
        metrics:
          - type: f1
            name: Macro F1
            value: 0.605
          - type: accuracy
            name: Accuracy
            value: 0.610
---

# Legally AI — PredEx Win/Lose Classifier (InLegalBERT)

A fine-tuned [`law-ai/InLegalBERT`](https://huggingface.co/law-ai/InLegalBERT) that predicts,
for an Indian appeal-shaped legal situation, a **single binary outcome for the applicant**
(appellant / petitioner): **1 = applicant prevails, 0 = does not**. It outputs a calibrated
probability `P(applicant wins)`.

This is **one of three signals** in the Legally AI win/lose ensemble — it is deliberately the
weakest, most conservative signal, and the application only trusts it when it agrees with the
other two (a precedent vote over real retrieved outcomes, and a reasoning-LLM forecast).

> ⚠️ **Not legal advice.** A research/educational tool. It can be wrong or incomplete.
> Consult a qualified advocate before acting on anything it produces.

## Intended use

- **In scope:** appeal-shaped questions where a binary Granted/Dismissed outcome is meaningful.
- **Out of scope:** non-appellate situations, "partly allowed" / withdrawn / disposed matters
  (no forced side), and any use as a standalone verdict. In the app, the classifier never speaks
  alone — its probability is only surfaced via the agreement-gated ensemble.

## How to use

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

tok = AutoTokenizer.from_pretrained("<HF_NAMESPACE>/legally-ai-predex-classifier", revision="v1")
model = AutoModelForSequenceClassification.from_pretrained(
    "<HF_NAMESPACE>/legally-ai-predex-classifier", revision="v1"
).eval()

enc = tok(situation_text, truncation=True, max_length=512, return_tensors="pt")
with torch.no_grad():
    prob_win = torch.softmax(model(**enc).logits, dim=-1)[0, 1].item()  # class 1 == applicant wins
```

**Label convention:** index `1` = applicant prevailed, index `0` = did not.

## Training

- **Base model:** `law-ai/InLegalBERT` (12-layer BERT encoder, 768-dim, 512-token max).
- **Task:** single-label sequence classification (`BertForSequenceClassification`, 2 classes).
- **Training data:** the **PredEx** legal-judgment-prediction dataset (Indian courts).

## Evaluation

On the held-out **PredEx** test split:

| Metric    | Value |
|-----------|-------|
| Macro F1  | 0.605 |
| Accuracy  | 0.610 |

Retraining on NyayaAnumana (20k balanced) did **not** beat this on the PredEx benchmark
(0.525 cross-domain; 0.636 in-domain), so the PredEx-trained checkpoint was kept.

## Limitations

- A 512-token encoder caps performance around **0.60–0.65** macro-F1 on this task; larger gains
  need a long-context model (planned for v2). Long judgments are truncated to the first 512 tokens.
- Trained on Indian-court text — **do not** apply to other jurisdictions.
- Calibration is decent but not perfect; this is exactly why the application gates it behind
  agreement with two independent signals rather than trusting its probability outright.

## License & attribution

Released under the **Apache-2.0** license. This is compatible with both upstream sources —
the base model is MIT and the training dataset is Apache-2.0, both permissive and with no
non-commercial restriction. Apache-2.0 is chosen because it honors both (it satisfies MIT's
notice requirement and matches the dataset's license). Credit to both:

- **Base model:** [`law-ai/InLegalBERT`](https://huggingface.co/law-ai/InLegalBERT) — Law-AI
  (IIT Kharagpur), **MIT** license.
- **Training data:** [`L-NLProc/PredEx`](https://huggingface.co/datasets/L-NLProc/PredEx) —
  **Apache-2.0** license. Cite: Nigam et al., *"Legal Judgment Reimagined: PredEx and the Rise
  of Intelligent AI Interpretation in Indian Courts"*, Findings of ACL 2024 (arXiv:2406.04136).
