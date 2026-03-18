"""Tests for the FastAPI server -- written first (TDD)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from nemoclaw.redactor import RedactResult


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "test-token")

    mock_redactor = MagicMock()
    mock_redactor.redact.return_value = RedactResult(
        redacted_text="Contact [EMAIL]",
        redacted_count=1,
        redacted_items=[{
            "original": "john@example.com",
            "label": "email",
            "replacement": "[EMAIL]",
            "confidence": 0.99,
        }],
    )

    with patch("nemoclaw.server.PIIRedactor", return_value=mock_redactor):
        import importlib
        import nemoclaw.server as srv
        importlib.reload(srv)
        with TestClient(srv.app) as tc:
            yield tc


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_requires_no_auth(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200


class TestRedactEndpoint:
    def test_valid_request_returns_200(self, client):
        resp = client.post(
            "/redact",
            json={"text": "Contact john@example.com"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200

    def test_response_shape(self, client):
        resp = client.post(
            "/redact",
            json={"text": "Contact john@example.com"},
            headers={"Authorization": "Bearer test-token"},
        )
        data = resp.json()
        assert "redacted_text" in data
        assert "redacted_count" in data
        assert "redacted_items" in data

    def test_redacted_text_returned(self, client):
        resp = client.post(
            "/redact",
            json={"text": "Contact john@example.com"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.json()["redacted_text"] == "Contact [EMAIL]"

    def test_redacted_count_returned(self, client):
        resp = client.post(
            "/redact",
            json={"text": "Contact john@example.com"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.json()["redacted_count"] == 1


class TestAuth:
    def test_missing_auth_rejected(self, client):
        resp = client.post("/redact", json={"text": "hello"})
        assert resp.status_code in (401, 403)

    def test_wrong_token_rejected(self, client):
        resp = client.post(
            "/redact",
            json={"text": "hello"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401

    def test_correct_token_accepted(self, client):
        resp = client.post(
            "/redact",
            json={"text": "hello"},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200


class TestValidation:
    def test_missing_text_field_rejected(self, client):
        resp = client.post(
            "/redact",
            json={},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 422

    def test_empty_text_accepted(self, client):
        resp = client.post(
            "/redact",
            json={"text": ""},
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
