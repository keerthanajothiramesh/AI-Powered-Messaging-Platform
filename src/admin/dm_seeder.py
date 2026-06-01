"""Seeds demo DM conversations between real user and synthetic users."""
from datetime import datetime, timedelta, timezone
from random import choice, randint, sample
from uuid import uuid4

from src.common.logger import get_logger

logger = get_logger(__name__)

_DM_THREADS = [
    [("Can you review my PR when you get a chance?", 0), ("Sure! Sending you feedback shortly.", 1),
     ("Thanks, I've addressed your comments.", 0), ("Looks great — approved!", 1)],
    [("Are you joining the standup today?", 0), ("Yes, dialing in now.", 1), ("Great, see you there!", 0)],
    [("Did you see the Q2 report Priya shared?", 0), ("Just going through it now.", 1),
     ("Strong APAC numbers. EMEA needs attention.", 0), ("Agreed. Flag it in Friday's review.", 1)],
    [("Can we shift our 3 pm to 4 pm?", 0), ("No problem, 4 pm works.", 1), ("Thanks! Updating invite.", 0)],
    [("The client call went really well!", 0), ("Excellent! Did they sign?", 1),
     ("Not yet but very positive signals.", 0), ("Keep me posted.", 1)],
    [("I've updated the shared doc with new requirements.", 0), ("Saw it — looks comprehensive.", 1),
     ("Let me know if anything's missing.", 0), ("Will do. Starting the estimate now.", 1)],
]


async def seed_demo_dms(db, users: list, requester_user_id: str = None) -> None:
    """Seed DM threads; first 6 always involve the requester so they appear in DM list."""
    user_ids = [u["user_id"] for u in users if u.get("user_id")]
    if len(user_ids) < 2:
        return

    now = datetime.now(timezone.utc)
    messages = []
    pairs_used: set = set()

    for thread_idx, thread in enumerate(_DM_THREADS):
        force_requester = requester_user_id and thread_idx < 6
        for _ in range(10):
            u1, u2 = (requester_user_id, choice(user_ids)) if force_requester else tuple(sample(user_ids, 2))
            key = tuple(sorted([u1, u2]))
            if key not in pairs_used and u1 != u2:
                pairs_used.add(key)
                break
        else:
            continue

        pair = [u1, u2]
        base = now - timedelta(days=randint(1, 14), hours=randint(0, 10))
        for offset, (content, sender_idx) in enumerate(thread):
            mid = str(uuid4())
            messages.append({
                "_id": mid, "message_id": mid,
                "sender_id": pair[sender_idx], "receiver_id": pair[1 - sender_idx],
                "group_id": None, "content": content, "media_type": "text",
                "timestamp": base + timedelta(minutes=offset * randint(3, 12)),
                "delivery_status": "delivered", "language": "en",
                "is_demo": True, "deleted": False, "read": True,
            })

    if messages:
        try:
            await db.messages.insert_many(messages, ordered=False)
            logger.info("demo_dms_seeded", count=len(messages))
        except Exception as exc:
            logger.warning("demo_dms_partial", error=str(exc))
