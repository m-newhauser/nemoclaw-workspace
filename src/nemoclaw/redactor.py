"""PII detection and redaction using nvidia/gliner-PII."""

from __future__ import annotations

from dataclasses import dataclass, field

from gliner import GLiNER


DEFAULT_MODEL_ID = "nvidia/gliner-PII"
DEFAULT_THRESHOLD = 0.3

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
        entities = self._model.predict_entities(text, self.labels, threshold=self.threshold)

        # Sort ascending by start for redacted_items (document order),
        # but process in reverse order so replacements don't shift indices.
        sorted_asc = sorted(entities, key=lambda e: e["start"])
        sorted_desc = sorted(entities, key=lambda e: e["start"], reverse=True)

        redacted = text
        for ent in sorted_desc:
            placeholder = f"[{ent['label'].upper()}]"
            redacted = redacted[: ent["start"]] + placeholder + redacted[ent["end"] :]

        redacted_items = [
            {
                "original": ent["text"],
                "label": ent["label"],
                "replacement": f"[{ent['label'].upper()}]",
                "confidence": ent["score"],
            }
            for ent in sorted_asc
        ]

        return RedactResult(
            redacted_text=redacted,
            redacted_count=len(entities),
            redacted_items=redacted_items,
        )
