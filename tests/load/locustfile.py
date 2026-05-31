"""
Locust load test for the AI-Powered Messaging Platform.

Run:
    locust -f tests/load/locustfile.py --host http://localhost:8000 --users 50 --spawn-rate 5

Scenarios simulated:
    - AuthUser  : login → token stored per-user, runs all authenticated flows
    - ReadOnlyUser: just hits read endpoints (history, search) — simulates passive viewers
"""
import json
import random
from locust import HttpUser, task, between, events

# ── Test data fixtures ────────────────────────────────────────────────────────

DEMO_CREDENTIALS = [
    {"email": "priya.sharma@techcorp.in", "password": "Test@1234"},
    {"email": "arjun.mehta@techcorp.in",  "password": "Test@1234"},
    {"email": "kavya.reddy@techcorp.in",  "password": "Test@1234"},
]

SAMPLE_MESSAGES = [
    "Hey, what's the status on the Q2 report?",
    "Can we schedule a call for tomorrow?",
    "The deadline is Friday — let's wrap up.",
    "urgent: build is broken on main branch",
    "Great work on the presentation slides!",
    "When does the sprint end?",
    "Please review the PR when you get a chance.",
    "重要: 明日の会議は10時からです",
]

SEARCH_QUERIES = [
    "project deadline",
    "meeting schedule",
    "report Q2",
    "urgent issue",
    "presentation slides",
]


# ── Base authenticated user ───────────────────────────────────────────────────

class AuthenticatedUser(HttpUser):
    abstract = True
    wait_time = between(1, 3)
    _token: str = None
    _user_id: str = None
    _group_id: str = None

    def on_start(self):
        creds = random.choice(DEMO_CREDENTIALS)
        with self.client.post(
            "/auth/login",
            json=creds,
            catch_response=True,
            name="/auth/login",
        ) as r:
            if r.status_code == 200:
                data = r.json()
                self._token  = data.get("access_token")
                self._user_id = data.get("user", {}).get("user_id")
                r.success()
            else:
                r.failure(f"Login failed: {r.status_code}")

    def _headers(self):
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    def _get_group_id(self):
        if self._group_id:
            return self._group_id
        r = self.client.get("/groups", headers=self._headers(), name="/groups")
        if r.status_code == 200:
            groups = r.json()
            if groups:
                self._group_id = groups[0]["group_id"]
        return self._group_id


# ── Scenario 1: Full active user ──────────────────────────────────────────────

class ActiveMessagingUser(AuthenticatedUser):
    """Simulates a user sending messages, reading history, searching, and using AI."""
    weight = 3

    @task(5)
    def send_group_message(self):
        gid = self._get_group_id()
        if not gid:
            return
        self.client.post(
            f"/messages/group/{gid}",
            json={"content": random.choice(SAMPLE_MESSAGES), "media_type": "text"},
            headers=self._headers(),
            name="/messages/group/{id}",
        )

    @task(3)
    def fetch_group_history(self):
        gid = self._get_group_id()
        if not gid:
            return
        self.client.get(
            f"/messages/group/{gid}/history?limit=20",
            headers=self._headers(),
            name="/messages/group/{id}/history",
        )

    @task(2)
    def search_messages(self):
        self.client.post(
            "/search/",
            json={"query": random.choice(SEARCH_QUERIES)},
            headers=self._headers(),
            name="/search/",
        )

    @task(1)
    def ai_chat(self):
        gid = self._get_group_id()
        self.client.post(
            "/ai/chat",
            json={
                "message": random.choice(SEARCH_QUERIES),
                "conv_id": gid or "default",
                "is_group": bool(gid),
            },
            headers=self._headers(),
            name="/ai/chat",
        )

    @task(1)
    def suggest_replies(self):
        self.client.post(
            "/messages/suggest-replies",
            json={"message": random.choice(SAMPLE_MESSAGES), "context": []},
            headers=self._headers(),
            name="/messages/suggest-replies",
        )

    @task(1)
    def check_notifications(self):
        self.client.get(
            "/notifications/",
            headers=self._headers(),
            name="/notifications/",
        )


# ── Scenario 2: Read-only observer ────────────────────────────────────────────

class ReadOnlyUser(AuthenticatedUser):
    """Simulates a passive user browsing history and searching."""
    weight = 1

    @task(4)
    def read_history(self):
        gid = self._get_group_id()
        if not gid:
            return
        self.client.get(
            f"/messages/group/{gid}/history?limit=50",
            headers=self._headers(),
            name="/messages/group/{id}/history",
        )

    @task(2)
    def search(self):
        self.client.post(
            "/search/",
            json={"query": random.choice(SEARCH_QUERIES)},
            headers=self._headers(),
            name="/search/",
        )

    @task(1)
    def health_check(self):
        self.client.get("/health", name="/health")


# ── Event hooks for reporting ─────────────────────────────────────────────────

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, **kwargs):
    """Log slow requests (> 3 s) to locust's output."""
    if response_time > 3000:
        print(f"[SLOW] {request_type} {name}: {response_time:.0f}ms")
