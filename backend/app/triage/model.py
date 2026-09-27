"""
Stage-1 medical-triage model loader — google/medgemma-1.5-4b-it
(step 4.4 / section 41S).

MedGemma is a generative, multimodal (text + image) instruction-
tuned model, not a text-classification model with a fixed label head.
That changes how "inference" works here compared to a classifier:

  - There are no native class scores. We prompt the model with a
    strict instruction to answer with exactly one of a small fixed
    vocabulary of tokens, then parse the first matching token out of
    its response. If the response doesn't contain a recognized token,
    we treat it as ASSESSMENT_UNAVAILABLE (step 4.5) rather than
    guessing.
  - `model_scores_optional` is therefore always None for this model.
  - Because MedGemma is multimodal, this same loaded model/processor is
    reused by app/triage/document_parser.py to read a scanned referral
    letter (image input). The model is loaded exactly once at process
    startup either way (never per request).

LOCAL LOADING NOTES (debugged the hard way — do not change casually):

  - MUST use bfloat16, not float16, for both `dtype` and
    `bnb_4bit_compute_dtype`. Gemma-family models (Gemma 2/3, and
    MedGemma which is built on Gemma 3) are trained in bf16 and are
    numerically unstable in fp16 — fp16 produces corrupted,
    multilingual-garbage token output that still "generates" without
    erroring, which makes it a nasty silent failure. This bit us once;
    don't reintroduce float16 here.
  - MUST use `attn_implementation="eager"`. Some SDPA + bitsandbytes-
    quantization combinations for Gemma3-family image-text-to-text
    models produce the same kind of corrupted output as the fp16 bug
    above, even with bf16 correctly set. Eager attention avoided it in
    testing.
  - Avoid mixed-precision CPU offload (e.g.
    `llm_int8_enable_fp32_cpu_offload=True` combined with GPU int8).
    The fp32-CPU / int8-GPU boundary was another source of corrupted
    output. Prefer `device_map={"": 0}` (everything on one GPU) with
    4-bit NF4 quantization. If that OOMs on your GPU, revisit offload
    but keep dtypes consistent across the boundary — don't casually
    reach for fp32 CPU + int8 GPU again without retesting output
    quality first.

API-only mode (HF_USE_HOSTED_INFERENCE_API=true): calls a dedicated HF
Inference Endpoint's OpenAI-compatible Messages API instead of any of
the above. MedGemma is NOT on HF's free shared serverless API, so
HF_INFERENCE_ENDPOINT_URL must be set — see config.py.
"""

import re
import time
from dataclasses import dataclass
from typing import Optional, Dict

import requests

from app.config import get_config

_model_state: Dict = {
    "loaded": False,
    "processor": None,
    "model": None,
    "load_seconds": None,
    "model_name": None,
    "model_revision": None,
}

TRIAGE_LABELS = ["URGENT", "CONSULT_GP", "SELF_MONITOR"]

TRIAGE_SYSTEM_PROMPT = (
    "You are a broad pre-triage assistant. You do NOT diagnose. Read the "
    "patient's description and reply with EXACTLY ONE WORD from this list, "
    "nothing else, no punctuation, no explanation: "
    "URGENT, CONSULT_GP, SELF_MONITOR. "
    "Use URGENT for anything suggesting a medical emergency (e.g. stroke, "
    "heart attack, severe trauma, breathing difficulty, loss of "
    "consciousness). Use CONSULT_GP for concerning but non-emergency "
    "symptoms. Use SELF_MONITOR for mild/minor symptoms."
)


@dataclass
class TriageResult:
    label: str  # one of TRIAGE_LABELS, or "ASSESSMENT_UNAVAILABLE"
    scores: Optional[dict] = None  # always None for MedGemma — see module docstring
    model_name: str = ""
    model_version: str = ""


def is_ready() -> bool:
    """Used by GET /ready — never report ready if the model isn't usable."""
    cfg = get_config()
    if cfg.HF_USE_HOSTED_INFERENCE_API:
        return bool(cfg.HF_API_TOKEN) and bool(cfg.HF_INFERENCE_ENDPOINT_URL)
    return _model_state["loaded"]


def warm_up():
    """
    Call once at process startup (see app/__init__.py — currently run
    in a background thread so the rest of the app can start serving
    immediately; /ready reports not-ready until this finishes).

    Local mode loads google/medgemma-1.5-4b-it with 4-bit NF4
    quantization, entirely on GPU (device_map={"": 0}), in bfloat16,
    with eager attention — see the module docstring for why each of
    those specific choices matters; this configuration was arrived at
    after debugging corrupted-output failures with float16 and with
    mixed CPU/GPU offload.

    google/medgemma-1.5-4b-it is a GATED model on Hugging Face: your
    HF_API_TOKEN's account must have accepted Google's license on the
    model page, or this will fail with a 401/403 — that failure is
    caught and surfaced through get_load_metrics()["load_error"], not
    raised, so the rest of the app can still start.
    """
    cfg = get_config()
    if cfg.HF_USE_HOSTED_INFERENCE_API:
        # Nothing to preload locally; readiness just checks config is present.
        _model_state["model_name"] = cfg.HF_TRIAGE_MODEL_NAME
        _model_state["model_revision"] = cfg.HF_TRIAGE_MODEL_REVISION
        if not cfg.HF_INFERENCE_ENDPOINT_URL:
            _model_state["load_error"] = (
                "HF_USE_HOSTED_INFERENCE_API=true but HF_INFERENCE_ENDPOINT_URL "
                "is not set. MedGemma is not on HF's free shared serverless "
                "API — deploy a dedicated Inference Endpoint at "
                "https://ui.endpoints.huggingface.co/ and set its URL."
            )
        return

    start = time.time()
    try:
        import torch
        from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig

        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,  # NOT float16 — see module docstring
            bnb_4bit_use_double_quant=True,
        )

        processor = AutoProcessor.from_pretrained(
            cfg.HF_TRIAGE_MODEL_NAME,
            token=cfg.HF_API_TOKEN or None,
        )
        model = AutoModelForImageTextToText.from_pretrained(
            cfg.HF_TRIAGE_MODEL_NAME,
            revision=cfg.HF_TRIAGE_MODEL_REVISION,
            token=cfg.HF_API_TOKEN or None,
            quantization_config=quant_config,
            device_map={"": 0},          # everything on one GPU — no CPU offload
            dtype=torch.bfloat16,
            attn_implementation="eager",  # avoids corrupted-output bug on Gemma3 family
        )

        _model_state["processor"] = processor
        _model_state["model"] = model
        _model_state["loaded"] = True
        _model_state["model_name"] = cfg.HF_TRIAGE_MODEL_NAME
        _model_state["model_revision"] = cfg.HF_TRIAGE_MODEL_REVISION
        _model_state["load_seconds"] = time.time() - start
    except Exception as exc:  # noqa: BLE001 - deliberate: log and stay not-ready
        _model_state["loaded"] = False
        _model_state["load_error"] = str(exc)


def get_load_metrics() -> dict:
    """Section 41S: measure load time / memory during development."""
    return {
        "loaded": _model_state["loaded"],
        "load_seconds": _model_state.get("load_seconds"),
        "model_name": _model_state.get("model_name"),
        "model_revision": _model_state.get("model_revision"),
        "load_error": _model_state.get("load_error"),
    }


def _parse_label(generated_text: str) -> Optional[str]:
    upper = generated_text.upper()
    for label in TRIAGE_LABELS:
        if re.search(rf"\b{label}\b", upper):
            return label
    return None


def _to_openai_content(content_items: list) -> list:
    """
    Convert our internal message-content shape (used for local
    generation, e.g. {"type": "image", "image": "data:..."}) into the
    OpenAI-compatible shape a dedicated HF Inference Endpoint's
    Messages API expects (e.g. {"type": "image_url", "image_url": {"url": "data:..."}}).
    """
    converted = []
    for item in content_items:
        if item["type"] == "image":
            converted.append({"type": "image_url", "image_url": {"url": item["image"]}})
        else:
            converted.append(item)
    return converted


def _run_chat(messages: list) -> str:
    """Shared chat-completion call used by both triage and document parsing."""
    cfg = get_config()

    if cfg.HF_USE_HOSTED_INFERENCE_API:
        if not cfg.HF_INFERENCE_ENDPOINT_URL:
            raise RuntimeError(
                "HF_INFERENCE_ENDPOINT_URL is not set. MedGemma is not available "
                "on HF's free shared serverless API — deploy a dedicated Inference "
                "Endpoint and set its URL. See docs/PROTOTYPE_LIMITATIONS.md."
            )

        url = f"{cfg.HF_INFERENCE_ENDPOINT_URL.rstrip('/')}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {cfg.HF_API_TOKEN}",
            "Content-Type": "application/json",
        }
        openai_messages = [
            {"role": m["role"], "content": _to_openai_content(m["content"])}
            for m in messages
        ]
        payload = {"model": "tgi", "messages": openai_messages, "max_tokens": 64}

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    # --- Local generation ---------------------------------------------------
    import torch

    processor = _model_state["processor"]
    model = _model_state["model"]
    if model is None or processor is None:
        raise RuntimeError("MedGemma model not loaded")

    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=64, do_sample=False)

    decoded = processor.batch_decode(
        output[:, inputs["input_ids"].shape[-1]:], skip_special_tokens=True
    )
    return decoded[0]


def infer(text: str) -> TriageResult:
    """
    Run triage inference. On any failure — model not loaded, gated-
    access error, malformed/unparseable output — returns
    ASSESSMENT_UNAVAILABLE rather than fabricating an urgency result
    (step 4.5).
    """
    cfg = get_config()
    try:
        if not text or not text.strip():
            raise ValueError("empty input")

        messages = [
            {"role": "system", "content": [{"type": "text", "text": TRIAGE_SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "text", "text": text}]},
        ]
        raw = _run_chat(messages)
        label = _parse_label(raw)
        if label is None:
            raise ValueError(f"unparseable model output: {raw!r}")

        return TriageResult(
            label=label,
            scores=None,
            model_name=cfg.HF_TRIAGE_MODEL_NAME,
            model_version=cfg.HF_TRIAGE_MODEL_REVISION,
        )
    except Exception:
        return TriageResult(
            label="ASSESSMENT_UNAVAILABLE",
            scores=None,
            model_name=cfg.HF_TRIAGE_MODEL_NAME,
            model_version=cfg.HF_TRIAGE_MODEL_REVISION,
        )