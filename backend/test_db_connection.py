"""Quick test to verify database connection for tests."""
import asyncio
import asyncpg


async def test_connection():
    """Test database connection."""
    try:
        conn = await asyncpg.connect(
            host="localhost",
            port=5432,
            user="pazpaz",
            password="pazpaz",
            database="pazpaz_test",
        )
        print("✅ Connection successful!")

        # Test query
        result = await conn.fetchval("SELECT version();")
        print(f"PostgreSQL version: {result}")

        await conn.close()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    exit(0 if success else 1)
