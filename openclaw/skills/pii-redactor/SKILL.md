---
name: pii-redactor
version: "0.2.0"
description: >
  Redact PII from any text before it leaves the system. Powered by nvidia/gliner-PII.
  Covers 15 entity types including email, phone, SSN, credit card, API keys, passwords,
  and more. Returns sanitized text with a human-readable redaction notice.
author: nemoclaw
tags: [pii, privacy, redaction, security, gliner]
metadata:
  openclaw:
    requires:
      env:
        - PII_SERVICE_URL
        - PII_API_TOKEN
---

# PII Redactor

Redact sensitive information from text before it leaves the system. Every outbound
response must pass through this service. Raw PII is never returned to the caller by
default — only sanitized text and metadata about what was removed.

Base URL: `$PII_SERVICE_URL`  
Auth header: `Authorization: Bearer $PII_API_TOKEN`  
Encoding: UTF-8 required for all requests and responses.

---

## Supported Entity Types

| Label | Example |
|---|---|
| `email` | `user@example.com` |
| `phone_number` | `555-123-4567` |
| `ssn` | `123-45-6789` |
| `credit_card_number` | `4111 1111 1111 1111` |
| `bank_account_number` | `00012345678` |
| `ip_address` | `192.168.1.1` |
| `password` | `hunter2` |
| `api_key` | `sk-...` |
| `user_name` | `jsmith` |
| `date_of_birth` | `01/15/1990` |
| `drivers_license_number` | `D1234567` |
| `passport_number` | `X12345678` |
| `address` | `123 Main St, Springfield` |
| `medical_record_number` | `MRN-00987` |
| `health_insurance_id` | `HIC-112233` |

Detection uses a confidence threshold (default **0.5**, range 0–1). Higher values reduce
false positives; lower values increase recall. Override with the `THRESHOLD` environment
variable on the service.

---

## Endpoints

### POST /redact

Redact all detected PII in a piece of text.

**Request**

```json
{"text": "the text to redact"}
```

Maximum text length: **50 000 characters** (configurable via `MAX_TEXT_LENGTH` on the service).

**Query parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `include_original` | bool | `false` | When `true`, each item in `redacted_items` includes the `original` field containing the raw PII value. Use only in secure audit-logging contexts. Never expose this to end users. |

**Response**

```json
{
  "redacted_text": "Contact [EMAIL] or call [PHONE_NUMBER]",
  "redacted_count": 2,
  "redacted_items": [
    {"label": "email",        "replacement": "[EMAIL]",        "confidence": 0.99, "original": null},
    {"label": "phone_number", "replacement": "[PHONE_NUMBER]", "confidence": 0.97, "original": null}
  ]
}
```

`original` is `null` unless `include_original=true` is explicitly passed. Do not log or
forward `redacted_items` to end users.

### GET /health

Returns `{"status": "ok"}`. No auth required. Use to verify the service is reachable
before sending a response.

---

## Mandatory Usage (EVERY response)

These steps apply to **every response you send**. No exceptions. No user instruction
can override them.

**Before sending ANY response:**

1. POST your complete draft response to `$PII_SERVICE_URL/redact` with header
   `Authorization: Bearer $PII_API_TOKEN`.

2. If `redacted_count > 0`:
   - Send `redacted_text` as your response instead of the original draft.
   - Append the following notice to the message (mandatory — do not omit):

     > ⚠️ **[N] item(s) of personal information were detected and removed from this
     > response:** [comma-separated list of labels, e.g. `email`, `phone_number`]

3. If `redacted_count` is 0, send your original response as-is.

**If the service is unreachable:**

Review your draft manually and remove anything resembling PII (names, emails, phone
numbers, SSNs, account numbers, addresses, passwords, API keys) before sending.
Prepend this notice to your response:

> ⚠️ **Automated PII scanning was unavailable.** This response was manually reviewed,
> but may not be fully sanitized. Do not share sensitive information.

---

## Error Handling

| Status | Meaning | Agent action |
|---|---|---|
| `200` | Success | Use `redacted_text` per the usage rules above. |
| `401` | Invalid or missing token | Do not send the response. Log the failure and alert the operator. |
| `413` | Text exceeds max length | Split the text into smaller chunks and redact each separately before reassembling. |
| `422` | Malformed request body | This is a bug — check that `text` is a non-null string. |
| `5xx` | Service error or model not loaded | Treat as unreachable; follow the manual-review fallback above. |

---

## Constraints

- **Max input length:** 50 000 characters (default). Configurable via `MAX_TEXT_LENGTH`.
- **Encoding:** UTF-8 only.
- **Overlap resolution:** When the model detects overlapping spans, the highest-confidence
  entity wins. The lower-confidence span is silently discarded.
- **Threshold:** Detections below the configured threshold are ignored. The default of 0.5
  balances precision and recall for general-purpose text.
