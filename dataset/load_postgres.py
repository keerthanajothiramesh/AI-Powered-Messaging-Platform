"""Load users, groups, group_members from JSON into Neon PostgreSQL."""
import asyncio
import json
from pathlib import Path
from datetime import datetime, date
import asyncpg
from dotenv import load_dotenv
import os


def _parse_dt(val):
    if not val:
        return None
    if isinstance(val, (datetime, date)):
        return val
    return datetime.fromisoformat(val.replace("Z", "+00:00"))


def _parse_date(val):
    if not val:
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(val[:10])

load_dotenv()
DATA_DIR = Path(__file__).parent


async def load_data():
    url = os.getenv("NEON_DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    if not url:
        print("ERROR: NEON_DATABASE_URL not set in .env")
        return

    pool = await asyncpg.create_pool(url, min_size=2, max_size=10)
    print("Connected to PostgreSQL")

    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id UUID PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                display_name VARCHAR(255) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                user_presence VARCHAR(50) DEFAULT 'offline',
                last_seen TIMESTAMPTZ,
                status VARCHAR(50) DEFAULT 'active',
                registration_date DATE,
                timezone VARCHAR(100) DEFAULT 'Asia/Kolkata',
                language_preference VARCHAR(10) DEFAULT 'en',
                avatar_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS groups (
                group_id UUID PRIMARY KEY,
                group_name VARCHAR(255) NOT NULL,
                description TEXT,
                avatar_url TEXT,
                created_by UUID,
                max_participants INTEGER DEFAULT 100,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS group_members (
                id SERIAL PRIMARY KEY,
                group_id UUID,
                user_id UUID,
                role VARCHAR(50) DEFAULT 'member',
                joined_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(group_id, user_id)
            );
        """)
        print("Tables ensured")

    users = json.loads((DATA_DIR / "users.json").read_text(encoding="utf-8"))
    print(f"Loading {len(users)} users...")
    async with pool.acquire() as conn:
        for u in users:
            try:
                await conn.execute(
                    """INSERT INTO users
                       (user_id, email, display_name, password_hash, user_presence,
                        last_seen, status, registration_date, timezone, language_preference)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                       ON CONFLICT (email) DO NOTHING""",
                    u["user_id"], u["email"], u["display_name"], u["password_hash"],
                    u["user_presence"], _parse_dt(u.get("last_seen")), u["status"],
                    _parse_date(u.get("registration_date")), u["timezone"], u["language_preference"],
                )
            except Exception as e:
                print(f"  User error ({u['email']}): {e}")
    print(f"  Users loaded")

    groups = json.loads((DATA_DIR / "groups.json").read_text(encoding="utf-8"))
    print(f"Loading {len(groups)} groups...")
    async with pool.acquire() as conn:
        for g in groups:
            try:
                await conn.execute(
                    """INSERT INTO groups (group_id, group_name, description, created_by, max_participants)
                       VALUES ($1,$2,$3,$4,$5) ON CONFLICT (group_id) DO NOTHING""",
                    g["group_id"], g["group_name"], g.get("description"),
                    g["created_by"], g.get("max_participants", 100),
                )
            except Exception as e:
                print(f"  Group error: {e}")
    print(f"  Groups loaded")

    members = json.loads((DATA_DIR / "group_members.json").read_text(encoding="utf-8"))
    print(f"Loading {len(members)} group memberships...")
    async with pool.acquire() as conn:
        for m in members:
            try:
                await conn.execute(
                    """INSERT INTO group_members (group_id, user_id, role)
                       VALUES ($1,$2,$3) ON CONFLICT (group_id, user_id) DO NOTHING""",
                    m["group_id"], m["user_id"], m.get("role", "member"),
                )
            except Exception as e:
                pass
    print(f"  Members loaded")

    await pool.close()
    print("PostgreSQL loading complete!")


if __name__ == "__main__":
    asyncio.run(load_data())
