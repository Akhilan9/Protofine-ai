"""Integration tests for FastAPI endpoints using TestClient."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "provider" in data
    assert "model" in data
    assert data["evidence_count"] == 10


def test_list_evidence_endpoint():
    response = client.get("/api/v1/evidence")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 10
    assert data[0]["source_id"] == "novatech-001"
    assert "Priya Shah" in data[0]["content"]


def test_answer_endpoint_successful_pipeline():
    payload = {
        "question": "What is the pricing for NovaSync Standard tier?",
        "evidence_ids": ["novatech-004"]
    }
    response = client.post("/api/v1/answer", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == payload["question"]
    assert "draft" in data
    assert "check" in data
    assert "final" in data
    assert data["final"]["status"] in ("verified", "corrected")
    assert "$499" in data["final"]["answer"]


def test_answer_endpoint_unknown_evidence_id_returns_404():
    payload = {
        "question": "Who founded NovaTech?",
        "evidence_ids": ["non-existent-999"]
    }
    response = client.post("/api/v1/answer", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_answer_endpoint_empty_question_returns_422():
    payload = {
        "question": "   ",
        "evidence_ids": ["novatech-001"]
    }
    response = client.post("/api/v1/answer", json=payload)
    assert response.status_code == 422


def test_root_serves_html_ui():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "EvidenceGuard AI" in response.text
