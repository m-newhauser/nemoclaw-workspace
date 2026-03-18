---
name: pii-redactor
description: Redact PII from text using nvidia/gliner-PII before sending any response. Detects and replaces emails, phone numbers, SSNs, credit cards, passwords, API keys, and 10+ other entity types.
metadata: {"openclaw": {"requires": {"env": ["PII_SERVICE_URL", "PII_API_TOKEN"]}}}
---

# PII Redactor

Redact sensitive information from text before it leaves the system.

Base URL: `$PII_SERVICE_URL`
Auth header: `Authorization: Bearer $PII_API_TOKEN`

## POST /redact

Replace all detected PII in text with `[LABEL]` placeholders.

Request:
```json
{"text": "the text to redact"}
```

Response:
```json
{
  "redacted_text": "Contact [EMAIL] or call [PHONE_NUMBER]",
  "redacted_count": 2,
  "redacted_items": [
    {"original": "john@example.com", "label": "email", "replacement": "[EMAIL]", "confidence": 0.99},
    {"original": "555-123-4567", "label": "phone_number", "replacement": "[PHONE_NUMBER]", "confidence": 0.97}
  ]
}
```

- Use `redacted_text` as your response when `redacted_count > 0`.
- Report `redacted_count` and the detected `label` types to the user as a notification.

## GET /health

Returns `{"status": "ok"}`. No auth required. Use to verify the service is reachable.
