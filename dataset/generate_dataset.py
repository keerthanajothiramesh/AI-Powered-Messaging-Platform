"""Synthetic dataset generator: 150 users, 25 groups, 60,000 messages."""
import uuid
import json
import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from faker import Faker

fake_in = Faker("en_IN")
fake_ja = Faker("ja_JP")
fake_en = Faker("en_US")

OUTPUT_DIR = Path(__file__).parent

JAPANESE_MESSAGES = [
    "おはようございます！今日の会議は何時ですか？",
    "プロジェクトの進捗を確認しました。順調です。",
    "締め切りは来週の金曜日ですね。",
    "資料を共有しました。確認してください。",
    "お疲れ様でした。明日もよろしくお願いします。",
    "会議の議事録を送りました。",
    "新しいデザインについてフィードバックをください。",
    "システムのアップデートが完了しました。",
]

ENGLISH_MESSAGES = [
    "The project deadline is confirmed for March 31st, please ensure all deliverables are ready",
    "Can everyone review the attached document before the meeting?",
    "Great progress on the sprint! Keep it up team.",
    "I've uploaded the office renovation images to the shared folder",
    "Meeting rescheduled to 3 PM tomorrow",
    "Please review the quarterly report before EOD",
    "The client approved our proposal! Celebrating this win!",
    "Server maintenance scheduled for Sunday 2 AM - 4 AM",
    "New feature deployment is live. Please test on staging.",
    "Budget approval received for Q2 initiatives",
    "Team standup moved to 9:30 AM starting Monday",
    "The renovation work on 3rd floor is complete, images shared",
    "Please update your project status in Jira by Friday",
    "We need to finalize the presentation for the board meeting",
    "Hotfix deployed to production, issue resolved",
    "All hands meeting on Thursday at 2 PM in Main Hall",
    "The new office layout images look great!",
    "Reminder: Submit timesheets by today EOD",
    "Infrastructure upgrade completed successfully",
    "Welcome Priya to the team! She joins as Senior PM",
]

GROUP_NAMES = [
    "Project Launch Team", "Engineering Squad", "Design Team",
    "Product Management", "Office Announcements", "HR Updates",
    "Sales Team", "Marketing Team", "DevOps Channel", "QA Team",
    "Leadership Updates", "Finance Team", "Support Team",
    "Data Science Guild", "Frontend Developers", "Backend Developers",
    "Mobile Team", "Security Team", "Infrastructure Team",
    "Innovation Lab", "Customer Success", "Legal & Compliance",
    "Research Team", "Analytics Team", "Executive Team",
]


def generate_users(count_indian: int = 130, count_japanese: int = 20):
    users = []
    indian_names = [
        "Priya Sharma", "Rahul Gupta", "Anita Patel", "Vikram Singh",
        "Kavya Reddy", "Arjun Kumar", "Sneha Iyer", "Rohit Verma",
        "Meera Nair", "Sanjay Mehta", "Pooja Joshi", "Amit Tiwari",
        "Divya Rao", "Karthik Subramanian", "Sunita Agarwal",
        "Rajesh Bhat", "Keerthana Jayaraman", "Deepak Sharma",
        "Nisha Pillai", "Arun Krishnamurthy",
    ]

    for i in range(count_indian):
        if i < len(indian_names):
            name = indian_names[i]
        else:
            name = fake_in.name()
        email = f"{name.lower().replace(' ', '.').replace('/', '')}{i}@company.com"
        users.append({
            "user_id": str(uuid.uuid4()),
            "email": email,
            "display_name": name,
            "password_hash": "$2b$12$placeholder_hash_for_dataset",
            "user_presence": random.choice(["online", "offline", "offline"]),
            "last_seen": (datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 72))).isoformat(),
            "status": "active",
            "registration_date": (datetime.now(timezone.utc) - timedelta(days=random.randint(30, 730))).date().isoformat(),
            "timezone": "Asia/Kolkata",
            "language_preference": "en",
            "avatar_url": None,
        })

    for i in range(count_japanese):
        name = fake_ja.name()
        email = f"jp.user{i}@company.co.jp"
        users.append({
            "user_id": str(uuid.uuid4()),
            "email": email,
            "display_name": name,
            "password_hash": "$2b$12$placeholder_hash_for_dataset",
            "user_presence": random.choice(["online", "offline"]),
            "last_seen": (datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 48))).isoformat(),
            "status": "active",
            "registration_date": (datetime.now(timezone.utc) - timedelta(days=random.randint(30, 365))).date().isoformat(),
            "timezone": "Asia/Tokyo",
            "language_preference": "ja",
            "avatar_url": None,
        })

    return users


def generate_groups(users):
    groups = []
    group_members = []

    for i, name in enumerate(GROUP_NAMES[:25]):
        group_id = str(uuid.uuid4())
        admin = users[i % len(users)]
        groups.append({
            "group_id": group_id,
            "group_name": name,
            "description": f"Group for {name} discussions",
            "avatar_url": None,
            "created_by": admin["user_id"],
            "max_participants": 100,
            "created_at": (datetime.now(timezone.utc) - timedelta(days=random.randint(30, 365))).isoformat(),
        })

        member_count = random.randint(5, 30)
        members = random.sample(users, min(member_count, len(users)))
        if admin not in members:
            members.insert(0, admin)

        for j, member in enumerate(members):
            group_members.append({
                "group_id": group_id,
                "user_id": member["user_id"],
                "role": "admin" if j == 0 else "member",
                "joined_at": (datetime.now(timezone.utc) - timedelta(days=random.randint(0, 180))).isoformat(),
            })

    return groups, group_members


def generate_messages(users, groups, group_members, target_count: int = 60000):
    messages = []
    events = []

    priya = next((u for u in users if "Priya" in u["display_name"]), users[0])

    project_launch_group = next(
        (g for g in groups if g["group_name"] == "Project Launch Team"), groups[0]
    )
    project_launch_members = [
        gm["user_id"] for gm in group_members if gm["group_id"] == project_launch_group["group_id"]
    ]

    demo_messages = [
        {
            "message_id": str(uuid.uuid4()),
            "sender_id": priya["user_id"],
            "receiver_id": None,
            "group_id": project_launch_group["group_id"],
            "content": "The project deadline is confirmed for March 31st, please ensure all deliverables are ready",
            "media_type": "text",
            "media_url": None,
            "delivery_status": "delivered",
            "read_status": "read",
            "reactions": {"👍": [users[1]["user_id"], users[2]["user_id"]]},
            "read_by": [u for u in project_launch_members[:10]],
            "language": "en",
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat(),
            "conversation_summary": None,
        },
        {
            "message_id": str(uuid.uuid4()),
            "sender_id": priya["user_id"],
            "receiver_id": None,
            "group_id": project_launch_group["group_id"],
            "content": "I've uploaded the office renovation images to the shared folder - third floor looks amazing!",
            "media_type": "image",
            "media_url": "/uploads/renovation_floor3.jpg",
            "delivery_status": "delivered",
            "read_status": "read",
            "reactions": {"🔥": [users[2]["user_id"]], "❤️": [users[3]["user_id"]]},
            "read_by": project_launch_members[:8],
            "language": "en",
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
            "conversation_summary": None,
        },
    ]
    messages.extend(demo_messages)

    media_messages = []
    renovation_keywords = [
        "office renovation images", "renovation photos", "new office layout",
        "third floor renovation", "office makeover images", "construction update photos",
    ]
    for i in range(20):
        sender = random.choice(users[:20])
        keyword = random.choice(renovation_keywords)
        media_messages.append({
            "message_id": str(uuid.uuid4()),
            "sender_id": sender["user_id"],
            "receiver_id": None,
            "group_id": project_launch_group["group_id"],
            "content": f"Check out these {keyword} from today's walk-through",
            "media_type": "image",
            "media_url": f"/uploads/renovation_{i}.jpg",
            "delivery_status": "delivered",
            "read_status": "read",
            "reactions": {},
            "read_by": [],
            "language": "en",
            "timestamp": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))).isoformat(),
            "conversation_summary": None,
        })
    messages.extend(media_messages)

    group_member_map = {}
    for gm in group_members:
        if gm["group_id"] not in group_member_map:
            group_member_map[gm["group_id"]] = []
        group_member_map[gm["group_id"]].append(gm["user_id"])

    base_time = datetime.now(timezone.utc) - timedelta(days=90)
    remaining = target_count - len(messages)

    for i in range(remaining):
        is_group = random.random() < 0.7
        sender = random.choice(users)
        is_japanese = sender["language_preference"] == "ja"
        media_type = random.choices(
            ["text", "image", "voice", "video"],
            weights=[80, 10, 5, 5],
        )[0]

        if is_japanese and random.random() < 0.7:
            content = random.choice(JAPANESE_MESSAGES)
            language = "ja"
        else:
            content = random.choice(ENGLISH_MESSAGES + [fake_en.sentence() for _ in range(5)])
            language = "en"

        if media_type != "text":
            content = f"[{media_type.upper()}] {content[:50]}"

        timestamp = base_time + timedelta(seconds=random.randint(0, 90 * 24 * 3600))
        delivery_status = random.choices(["delivered", "sent", "failed"], weights=[90, 8, 2])[0]

        if is_group:
            group = random.choice(groups)
            members = group_member_map.get(group["group_id"], [sender["user_id"]])
            msg_sender = random.choice(members) if members else sender["user_id"]
            msg = {
                "message_id": str(uuid.uuid4()),
                "sender_id": msg_sender,
                "receiver_id": None,
                "group_id": group["group_id"],
                "content": content,
                "media_type": media_type,
                "media_url": f"/uploads/media_{i}.{media_type}" if media_type != "text" else None,
                "delivery_status": delivery_status,
                "read_status": random.choice(["read", "unread"]),
                "reactions": {},
                "read_by": random.sample(members, min(random.randint(0, 5), len(members))),
                "language": language,
                "timestamp": timestamp.isoformat(),
                "conversation_summary": None,
            }
        else:
            receiver = random.choice([u for u in users if u["user_id"] != sender["user_id"]])
            msg = {
                "message_id": str(uuid.uuid4()),
                "sender_id": sender["user_id"],
                "receiver_id": receiver["user_id"],
                "group_id": None,
                "content": content,
                "media_type": media_type,
                "media_url": f"/uploads/media_{i}.{media_type}" if media_type != "text" else None,
                "delivery_status": delivery_status,
                "read_status": random.choice(["read", "unread"]),
                "reactions": {},
                "read_by": [],
                "language": language,
                "timestamp": timestamp.isoformat(),
                "conversation_summary": None,
            }

        messages.append(msg)

        event = {
            "event_id": str(uuid.uuid4()),
            "message_id": msg["message_id"],
            "event_type": "delivered" if delivery_status == "delivered" else "sent",
            "timestamp": timestamp.isoformat(),
        }
        events.append(event)

    return messages, events


def save_to_files(users, groups, group_members, messages, events):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_DIR / "users.json", "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_DIR / "groups.json", "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_DIR / "group_members.json", "w", encoding="utf-8") as f:
        json.dump(group_members, f, ensure_ascii=False, indent=2)

    chunk_size = 10000
    for i in range(0, len(messages), chunk_size):
        chunk = messages[i:i + chunk_size]
        with open(OUTPUT_DIR / f"messages_{i//chunk_size}.json", "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_DIR / "events.json", "w", encoding="utf-8") as f:
        json.dump(events[:10000], f, ensure_ascii=False, indent=2)

    with open(OUTPUT_DIR / "users.csv", "w", newline="", encoding="utf-8") as f:
        if users:
            writer = csv.DictWriter(f, fieldnames=users[0].keys())
            writer.writeheader()
            writer.writerows(users)

    summary = {
        "users": len(users),
        "groups": len(groups),
        "group_members": len(group_members),
        "messages": len(messages),
        "events": len(events),
    }
    with open(OUTPUT_DIR / "dataset_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Dataset generated:")
    for k, v in summary.items():
        print(f"  {k}: {v:,}")


if __name__ == "__main__":
    print("Generating synthetic dataset...")
    users = generate_users(130, 20)
    print(f"  Users: {len(users)}")
    groups, group_members = generate_groups(users)
    print(f"  Groups: {len(groups)}, Members: {len(group_members)}")
    messages, events = generate_messages(users, groups, group_members, 60000)
    print(f"  Messages: {len(messages)}")
    save_to_files(users, groups, group_members, messages, events)
    print("Done!")
