"""Debug database connection issues."""
import asyncio
import asyncpg


async def test_connection():
    """Test database connection with detailed logging."""
    connection_params = {
        "host": "localhost",
        "port": 5432,
        "user": "pazpaz",
        "password": "pazpaz",
        "database": "pazpaz_test",
    }

    print("Connection parameters:")
    for key, value in connection_params.items():
        if key != "password":
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: ****")

    try:
        print("\nAttempting connection...")
        conn = await asyncpg.connect(**connection_params)
        print("✅ Connection successful!")

        # Test query
        result = await conn.fetchval("SELECT version();")
        print(f"\nPostgreSQL version: {result}")

        await conn.close()
        return True
    except asyncpg.exceptions.InvalidPasswordError as e:
        print(f"❌ Invalid password error: {e}")
        print("\nThis usually means:")
        print("  1. Password is incorrect")
        print("  2. pg_hba.conf authentication method mismatch")
        print("  3. User doesn't exist or has no password set")
        return False
    except Exception as e:
        print(f"❌ Connection failed: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    exit(0 if success else 1)
