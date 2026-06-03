"""Integration tests for AI chat, RAG-backed semantic search, hybrid BM25+vector search, and catch-up summary — all run against a live server at localhost:8000."""
import pytest
import httpx
import uuid

BASE_URL = "http://localhost:8000"


def _auth_headers(client, prefix="ai_test"):
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    r = client.post("/auth/register", json={
        "email": email, "display_name": "AI User", "password": "password123",
    })
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def client():
    return httpx.Client(base_url=BASE_URL, timeout=60)


def test_ai_chat(client):
    headers = _auth_headers(client, "chat_test")
    r = client.post("/ai/chat", json={"message": "Hello, what can you help me with?"}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "text" in data
    assert len(data["text"]) > 0


def test_ai_search(client):
    headers = _auth_headers(client, "search_test")
    r = client.post("/ai/search", json={"query": "project deadline"}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "answer" in data
    assert "sources" in data


def test_hybrid_search(client):
    headers = _auth_headers(client, "hybrid_test")
    r = client.post("/search", json={"query": "renovation images", "n_results": 5}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert "count" in data


def test_catchup_summary(client):
    headers = _auth_headers(client, "catchup_test")
    r = client.post("/ai/catchup", json={"hours_offline": 24}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "total_missed" in data
