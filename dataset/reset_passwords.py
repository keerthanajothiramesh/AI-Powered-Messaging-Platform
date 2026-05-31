"""Reset all synthetic dataset users to a known password for demo/testing."""
import asyncio
import asyncpg
from passlib.hash import bcrypt
from dotenv import load_dotenv
import os

load_dotenv()

DEMO_PASSWORD = "Test@1234"


async def reset():
    url = os.getenv("NEON_DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    if not url:
        print("ERROR: NEON_DATABASE_URL not set in .env")
        return

    pool = await asyncpg.create_pool(url, min_size=2, max_size=5)

    print(f"Generating bcrypt hash for '{DEMO_PASSWORD}'...")
    hashed = bcrypt.hash(DEMO_PASSWORD)
    print(f"Hash: {hashed}")

    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE users SET password_hash = $1 WHERE password_hash = '$2b$12$placeholder_hash_for_dataset'",
            hashed,
        )
    print(f"Updated: {result}")

    await pool.close()
    print(f"\nDone! All synthetic users now have password: {DEMO_PASSWORD}")
    print("Example logins:")
    print("  priya.sharma0@company.com  /  Test@1234")
    print("  rahul.gupta1@company.com   /  Test@1234")
    print("  anita.patel2@company.com   /  Test@1234")


if __name__ == "__main__":
    asyncio.run(reset())
