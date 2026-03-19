"""PII detection and redaction using nvidia/gliner-PII."""

from __future__ import annotations

from dataclasses import dataclass, field

from gliner import GLiNER


DEFAULT_MODEL_ID = "nvidia/gliner-PII"
DEFAULT_THRESHOLD = 0.5

DEFAULT_LABELS: list[str] = [
    "email",
    "phone_number",
    "ssn",
    "credit_card_number",
    "bank_account_number",
    "ip_address",
    "password",
    "api_key",
    "user_name",
    "date_of_birth",
    "drivers_license_number",
    "passport_number",
    "address",
    "medical_record_number",
    "health_insurance_id",
]


@dataclass
class RedactResult:
    redacted_text: str
    redacted_count: int
    redacted_items: list[dict] = field(default_factory=list)


def _resolve_overlaps(entities: list[dict]) -> list[dict]:
    """Remove overlapping spans, keeping the highest-confidence entity per region."""
    sorted_by_conf = sorted(entities, key=lambda e: e["score"], reverse=True)
    kept: list[dict] = []
    for ent in sorted_by_conf:
        if any(ent["start"] < k["end"] and ent["end"] > k["start"] for k in kept):
            continue
        kept.append(ent)
    return sorted(kept, key=lambda e: e["start"])


class PIIRedactor:
    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        threshold: float = DEFAULT_THRESHOLD,
        labels: list[str] | None = None,
    ):
        self.threshold = threshold
        self.labels = labels or DEFAULT_LABELS
        self._model = GLiNER.from_pretrained(model_id)

    def redact(self, text: str) -> RedactResult:
        """Detect PII in text and replace each span with [LABEL_UPPER]."""
        raw_entities = self._model.predict_entities(text, self.labels, threshold=self.threshold)
        entities = _resolve_overlaps(raw_entities)

        parts: list[str] = []
        cursor = 0
        redacted_items: list[dict] = []

        for ent in entities:
            parts.append(text[cursor : ent["start"]])
            placeholder = f"[{ent['label'].upper()}]"
            parts.append(placeholder)
            cursor = ent["end"]
            redacted_items.append(
                {
                    "original": text[ent["start"] : ent["end"]],
                    "label": ent["label"],
                    "replacement": placeholder,
                    "confidence": ent["score"],
                }
            )

        parts.append(text[cursor:])

        return RedactResult(
            redacted_text="".join(parts),
            redacted_count=len(entities),
            redacted_items=redacted_items,
        )
