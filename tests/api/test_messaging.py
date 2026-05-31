"""Messaging API tests."""
import pytest
import httpx
import uuid

BASE_URL = "http://localhost:8000"


def _register_and_login(client, prefix="test"):
    email = f"{prefix}_{uuid.uuid4().hex[:6]}@test.com"
    r = client.post("/auth/register", json={
        "email": email, "display_name": f"User {prefix}", "password": "password123",
    })
    return r.json()["access_token"], r.json()["user_id"]


@pytest.fixture
def client():
    return httpx.Client(base_url=BASE_URL, timeout=30)


def test_create_group_and_send_message(client):
    token, uid = _register_and_login(client, "group_test")
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/groups", json={"group_name": "Test Group", "description": "Testing"}, headers=headers)
    assert r.status_code == 201
    group_id = r.json()["group_id"]

    r = client.post(f"/messages/group/{group_id}", json={"content": "Hello group!"}, headers=headers)
    assert r.status_code == 201
    assert r.json()["content"] == "Hello group!"


def test_get_group_history(client):
    token, uid = _register_and_login(client, "hist_test")
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/groups", json={"group_name": "Hist Group"}, headers=headers)
    group_id = r.json()["group_id"]
    client.post(f"/messages/group/{group_id}", json={"content": "Msg 1"}, headers=headers)
    client.post(f"/messages/group/{group_id}", json={"content": "Msg 2"}, headers=headers)

    r = client.get(f"/messages/group/{group_id}/history", headers=headers)
    assert r.status_code == 200
    msgs = r.json()
    assert len(msgs) >= 2


def test_my_groups(client):
    token, _ = _register_and_login(client, "mygrp")
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/groups", json={"group_name": "MyGroup"}, headers=headers)
    r = client.get("/groups/me", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1
