"""Locust load test simulating 100 concurrent users sending messages, fetching group history, searching, and hitting the health endpoint to measure throughput and latency under load."""
import uuid
import json
from locust import HttpUser, task, between


class MessagingUser(HttpUser):
    wait_time = between(0.5, 2)
    token = None
    user_id = None
    group_id = None

    def on_start(self):
        email = f"load_{uuid.uuid4().hex[:8]}@test.com"
        r = self.client.post("/auth/register", json={
            "email": email, "display_name": "Load User", "password": "password123",
        })
        if r.status_code == 201:
            data = r.json()
            self.token = data["access_token"]
            self.user_id = data["user_id"]

        if self.token:
            r = self.client.post(
                "/groups",
                json={"group_name": f"Load Group {uuid.uuid4().hex[:4]}"},
                headers={"Authorization": f"Bearer {self.token}"},
            )
            if r.status_code == 201:
                self.group_id = r.json()["group_id"]

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def send_group_message(self):
        if not self.token or not self.group_id:
            return
        self.client.post(
            f"/messages/group/{self.group_id}",
            json={"content": "Load test message " + uuid.uuid4().hex[:8]},
            headers=self._headers(),
        )

    @task(2)
    def get_group_history(self):
        if not self.token or not self.group_id:
            return
        self.client.get(f"/messages/group/{self.group_id}/history?limit=20", headers=self._headers())

    @task(1)
    def search_messages(self):
        if not self.token:
            return
        self.client.post(
            "/search",
            json={"query": "project meeting deadline", "n_results": 10},
            headers=self._headers(),
        )

    @task(1)
    def health_check(self):
        self.client.get("/health")

    @task(1)
    def get_my_groups(self):
        if not self.token:
            return
        self.client.get("/groups/me", headers=self._headers())
