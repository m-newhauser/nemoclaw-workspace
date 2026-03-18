"""Tests for PIIRedactor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nemoclaw.redactor import (
    DEFAULT_LABELS,
    DEFAULT_THRESHOLD,
    PIIRedactor,
    RedactResult,
    _resolve_overlaps,
)


def _make_redactor(predict_return: list[dict]) -> PIIRedactor:
    with patch("nemoclaw.redactor.GLiNER") as MockGLiNER:
        mock_model = MagicMock()
        MockGLiNER.from_pretrained.return_value = mock_model
        mock_model.predict_entities.return_value = predict_return
        redactor = PIIRedactor()
    return redactor


class TestDefaults:
    def test_default_labels_is_nonempty_list(self):
        assert isinstance(DEFAULT_LABELS, list)
        assert len(DEFAULT_LABELS) > 0

    def test_loads_nvidia_model_by_default(self):
        with patch("nemoclaw.redactor.GLiNER") as MockGLiNER:
            MockGLiNER.from_pretrained.return_value = MagicMock()
            PIIRedactor()
            MockGLiNER.from_pretrained.assert_called_once_with("nvidia/gliner-PII")

    def test_default_threshold_is_0_5(self):
        with patch("nemoclaw.redactor.GLiNER") as MockGLiNER:
            MockGLiNER.from_pretrained.return_value = MagicMock()
            r = PIIRedactor()
            assert r.threshold == 0.5

    def test_default_threshold_constant(self):
        assert DEFAULT_THRESHOLD == 0.5


class TestRedactCleanText:
    def test_clean_text_unchanged(self):
        redactor = _make_redactor([])
        result = redactor.redact("What is the capital of France?")
        assert result.redacted_text == "What is the capital of France?"
        assert result.redacted_count == 0
        assert result.redacted_items == []

    def test_returns_redact_result(self):
        redactor = _make_redactor([])
        result = redactor.redact("hello")
        assert isinstance(result, RedactResult)


class TestRedactSingleEntity:
    def test_email_redacted(self):
        redactor = _make_redactor([
            {"text": "john@example.com", "label": "email", "start": 12, "end": 28, "score": 0.99},
        ])
        result = redactor.redact("Contact me: john@example.com")
        assert "john@example.com" not in result.redacted_text
        assert "[EMAIL]" in result.redacted_text
        assert result.redacted_count == 1

    def test_phone_redacted(self):
        redactor = _make_redactor([
            {"text": "555-123-4567", "label": "phone_number", "start": 9, "end": 21, "score": 0.97},
        ])
        result = redactor.redact("Call me: 555-123-4567")
        assert "555-123-4567" not in result.redacted_text
        assert "[PHONE_NUMBER]" in result.redacted_text

    def test_ssn_redacted(self):
        redactor = _make_redactor([
            {"text": "123-45-6789", "label": "ssn", "start": 12, "end": 23, "score": 0.98},
        ])
        result = redactor.redact("My SSN is: 123-45-6789")
        assert "123-45-6789" not in result.redacted_text
        assert "[SSN]" in result.redacted_text

    def test_label_uppercased(self):
        redactor = _make_redactor([
            {"text": "foo@bar.com", "label": "email", "start": 0, "end": 11, "score": 0.95},
        ])
        result = redactor.redact("foo@bar.com")
        assert result.redacted_text == "[EMAIL]"


class TestRedactMultipleEntities:
    def test_two_entities_both_redacted(self):
        redactor = _make_redactor([
            {"text": "john@example.com", "label": "email", "start": 0, "end": 16, "score": 0.99},
            {"text": "555-123-4567", "label": "phone_number", "start": 20, "end": 32, "score": 0.97},
        ])
        result = redactor.redact("john@example.com and 555-123-4567")
        assert result.redacted_count == 2
        assert "[EMAIL]" in result.redacted_text
        assert "[PHONE_NUMBER]" in result.redacted_text
        assert "john@example.com" not in result.redacted_text
        assert "555-123-4567" not in result.redacted_text


class TestOverlapResolution:
    def test_higher_confidence_wins_on_overlap(self):
        """When two spans overlap, the higher-confidence entity is kept."""
        redactor = _make_redactor([
            {"text": "john", "label": "user_name", "start": 0, "end": 4, "score": 0.9},
            {"text": "john@example.com", "label": "email", "start": 0, "end": 16, "score": 0.99},
        ])
        result = redactor.redact("john@example.com")
        assert result.redacted_text == "[EMAIL]"
        assert result.redacted_count == 1

    def test_nested_span_discarded(self):
        """A span fully contained within a higher-confidence span is dropped."""
        redactor = _make_redactor([
            {"text": "john@example.com", "label": "email", "start": 0, "end": 16, "score": 0.99},
            {"text": "john", "label": "user_name", "start": 0, "end": 4, "score": 0.5},
        ])
        result = redactor.redact("john@example.com")
        assert result.redacted_text == "[EMAIL]"
        assert result.redacted_count == 1

    def test_non_overlapping_spans_both_kept(self):
        redactor = _make_redactor([
            {"text": "john@example.com", "label": "email", "start": 0, "end": 16, "score": 0.99},
            {"text": "555-123-4567", "label": "phone_number", "start": 20, "end": 32, "score": 0.97},
        ])
        result = redactor.redact("john@example.com and 555-123-4567")
        assert result.redacted_count == 2

    def test_resolve_overlaps_unit(self):
        """_resolve_overlaps keeps highest-confidence and returns document order."""
        entities = [
            {"text": "john", "label": "user_name", "start": 0, "end": 4, "score": 0.9},
            {"text": "john@example.com", "label": "email", "start": 0, "end": 16, "score": 0.99},
            {"text": "555-123-4567", "label": "phone_number", "start": 20, "end": 32, "score": 0.97},
        ]
        kept = _resolve_overlaps(entities)
        assert len(kept) == 2
        assert kept[0]["label"] == "email"
        assert kept[1]["label"] == "phone_number"


class TestRedactItems:
    def test_redacted_items_contain_metadata(self):
        redactor = _make_redactor([
            {"text": "john@example.com", "label": "email", "start": 0, "end": 16, "score": 0.99},
        ])
        result = redactor.redact("john@example.com")
        assert len(result.redacted_items) == 1
        item = result.redacted_items[0]
        assert item["original"] == "john@example.com"
        assert item["label"] == "email"
        assert item["replacement"] == "[EMAIL]"
        assert item["confidence"] == 0.99

    def test_redacted_items_ordered_by_appearance(self):
        """Items should appear in document order (left to right) in redacted_items."""
        redactor = _make_redactor([
            {"text": "555-123-4567", "label": "phone_number", "start": 20, "end": 32, "score": 0.97},
            {"text": "john@example.com", "label": "email", "start": 0, "end": 16, "score": 0.99},
        ])
        result = redactor.redact("john@example.com and 555-123-4567")
        assert result.redacted_items[0]["label"] == "email"
        assert result.redacted_items[1]["label"] == "phone_number"


class TestRedactPassesConfig:
    def test_custom_threshold_passed_to_model(self):
        with patch("nemoclaw.redactor.GLiNER") as MockGLiNER:
            mock_model = MagicMock()
            MockGLiNER.from_pretrained.return_value = mock_model
            mock_model.predict_entities.return_value = []
            redactor = PIIRedactor(threshold=0.8)

        redactor.redact("test text")
        args, kwargs = mock_model.predict_entities.call_args
        threshold = kwargs.get("threshold") or (args[2] if len(args) > 2 else None)
        assert threshold == 0.8

    def test_custom_model_id_used(self):
        with patch("nemoclaw.redactor.GLiNER") as MockGLiNER:
            MockGLiNER.from_pretrained.return_value = MagicMock()
            PIIRedactor(model_id="custom/model")
            MockGLiNER.from_pretrained.assert_called_once_with("custom/model")
