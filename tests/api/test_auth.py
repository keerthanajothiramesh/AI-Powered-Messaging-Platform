"""Auth API tests."""
import pytest
import httpx
import asyncio

BASE_URL = "http://localhost:8000"


@pytest.fixture
def client():
    return httpx.Client(base_url=BASE_URL, timeout=30)


def test_register(client):
    import uuid
    email = f"test_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/auth/register", json={
        "email": email,
        "display_name": "Test User",
        "password": "password123",
    })
    assert r.status_code == 201
    data = r.json()
    assert "access_token" in data
    assert data["email"] == email


def test_login(client):
    import uuid
    email = f"login_{uuid.uuid4().hex[:8]}@test.com"
    client.post("/auth/register", json={
        "email": email, "display_name": "Login User", "password": "password123",
    })
    r = client.post("/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password(client):
    r = client.post("/auth/login", json={"email": "noone@test.com", "password": "wrong"})
    assert r.status_code == 401


def test_get_me(client):
    import uuid
    email = f"me_{uuid.uuid4().hex[:8]}@test.com"
    reg = client.post("/auth/register", json={
        "email": email, "display_name": "Me User", "password": "password123",
    })
    token = reg.json()["access_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == email


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
