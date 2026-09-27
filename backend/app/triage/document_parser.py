"""
Scanned referral-document parsing (new requirement: the referral is
now initiated by the patient/attendant themselves — they either scan
a doctor's referral letter or enter the details manually — rather
than a hospital creating it on the patient's behalf).

Reuses the same loaded MedGemma model as app/triage/model.py (it is
multimodal) rather than loading a second model into memory. This is
best-effort document extraction, not OCR ground truth: the frontend
always shows the extracted fields to the patient/attendant for review
and editing before a referral is actually created (never auto-submits
without human confirmation — a misread field here could route a
critical case incorrectly).
"""

import json
import re
from dataclasses import dataclass
from typing import Optional

from app.config import get_config
from app.triage.model import _run_chat, _model_state  # reuse the loaded pipeline
from app.triage.policy import REQUIREMENT_RULES_BY_PRESENTING_CONCERN

DOCUMENT_PARSE_SYSTEM_PROMPT = (
    "You read scanned medical referral letters. Extract only what is "
    "explicitly written on the page — never infer or guess a diagnosis. "
    "Reply with ONLY a JSON object, no other text, matching exactly this "
    "shape: "
    '{"reason_for_referral": string, "clinical_summary": string, '
    '"referring_doctor_name": string or null, '
    '"presenting_concerns": array of strings, each one of '
    '["SUSPECTED_STROKE","SEVERE_TRAUMA","CARDIAC_SYMPTOMS","GENERAL_EMERGENCY"]}. '
    "Pick presenting_concerns only when the letter clearly supports it; "
    "use an empty array if unsure."
)


@dataclass
class DocumentParseResult:
    ok: bool
    reason_for_referral: Optional[str] = None
    clinical_summary: Optional[str] = None
    referring_doctor_name: Optional[str] = None
    requirements: Optional[list] = None
    raw_model_output: Optional[str] = None
    error: Optional[str] = None


def _extract_json(text: str) -> Optional[dict]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def parse_referral_document(image_base64: Optional[str], extra_text: str = "") -> DocumentParseResult:
    """
    `image_base64` is a data-URL-free base64 JPEG/PNG string of the
    scanned referral letter (optional — a patient may also just paste
    typed text from the letter into `extra_text` instead of a photo).
    """
    cfg = get_config()
    if image_base64 is None and not extra_text.strip():
        return DocumentParseResult(ok=False, error="No image or text provided")

    try:
        content = [{"type": "text", "text": extra_text or "(see attached image)"}]
        if image_base64:
            content.insert(0, {"type": "image", "image": f"data:image/jpeg;base64,{image_base64}"})

        messages = [
            {"role": "system", "content": [{"type": "text", "text": DOCUMENT_PARSE_SYSTEM_PROMPT}]},
            {"role": "user", "content": content},
        ]

        raw = _run_chat(messages)
        parsed = _extract_json(raw)
        if parsed is None:
            return DocumentParseResult(ok=False, raw_model_output=raw, error="Could not parse model output as JSON")

        concerns = parsed.get("presenting_concerns", []) or []
        requirements = []
        seen = set()
        for concern in concerns:
            for rule in REQUIREMENT_RULES_BY_PRESENTING_CONCERN.get(concern, []):
                if rule["requirement_type"] not in seen:
                    requirements.append(rule)
                    seen.add(rule["requirement_type"])

        return DocumentParseResult(
            ok=True,
            reason_for_referral=parsed.get("reason_for_referral"),
            clinical_summary=parsed.get("clinical_summary"),
            referring_doctor_name=parsed.get("referring_doctor_name"),
            requirements=requirements,
            raw_model_output=raw,
        )
    except Exception as exc:  # noqa: BLE001
        return DocumentParseResult(ok=False, error=str(exc))
